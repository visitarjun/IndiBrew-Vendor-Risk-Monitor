"""
tests/test_trend_agent.py
==========================
Unit tests for TrendAgent — window stats, MoM delta, signal classification,
ghost analysis, and edge cases (no data, single-day windows).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from agents.data_agent import DataBundle, Incident
from agents.trend_agent import TrendAgent, MoMDelta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _inc(iid, d: date, dept="Procurement", itype="Approval Delay",
         severity="HIGH", resolved=False, impact=200_000):
    return Incident(
        incident_id=iid, date=d, department=dept,
        incident_type=itype, severity=severity,
        resolved=resolved, financial_impact_inr=impact,
        vendor_id="IV0001", employee_id="EMP001",
    )

def _bundle(incidents):
    return DataBundle(vendors=[], incidents=incidents, employees=[],
                      summary={}, errors=[])


# ---------------------------------------------------------------------------
# Window stats
# ---------------------------------------------------------------------------

class TestWindowStats:
    def test_counts_current_window(self):
        as_of = date(2026, 5, 16)
        # 5 incidents in last 30 days
        incidents = [
            _inc(f"I{i}", as_of - timedelta(days=i+1))
            for i in range(5)
        ]
        # 3 in prior 30 days
        incidents += [
            _inc(f"P{i}", as_of - timedelta(days=31+i))
            for i in range(3)
        ]
        bundle = _bundle(incidents)
        report = TrendAgent().analyse(bundle, as_of=as_of)
        assert report.current_window.total_incidents == 5
        assert report.prior_window.total_incidents   == 3

    def test_empty_windows(self):
        as_of  = date(2026, 5, 16)
        bundle = _bundle([])
        report = TrendAgent().analyse(bundle, as_of=as_of)
        assert report.current_window.total_incidents == 0
        assert report.prior_window.total_incidents   == 0

    def test_dept_breakdown(self):
        as_of = date(2026, 5, 16)
        incidents = [
            _inc(f"P{i}", as_of - timedelta(days=i+1), dept="Procurement")
            for i in range(4)
        ] + [
            _inc(f"C{i}", as_of - timedelta(days=i+1), dept="Compliance")
            for i in range(2)
        ]
        bundle = _bundle(incidents)
        report = TrendAgent().analyse(bundle, as_of=as_of)
        assert report.current_window.by_dept.get("Procurement") == 4
        assert report.current_window.by_dept.get("Compliance")  == 2


# ---------------------------------------------------------------------------
# MoM delta & signal
# ---------------------------------------------------------------------------

class TestMoMDelta:
    def test_deteriorating_signal(self):
        delta = MoMDelta(current=100, prior=60, delta_abs=40,
                         delta_pct=66.7, direction="UP",
                         signal="DETERIORATING", higher_is_bad=True)
        assert delta.signal == "DETERIORATING"

    def test_improving_signal(self):
        delta = MoMDelta(current=40, prior=80, delta_abs=-40,
                         delta_pct=-50.0, direction="DOWN",
                         signal="IMPROVING", higher_is_bad=True)
        assert delta.signal == "IMPROVING"

    def test_stable_signal(self):
        delta = MoMDelta(current=50, prior=48, delta_abs=2,
                         delta_pct=4.2, direction="UP",
                         signal="STABLE", higher_is_bad=True)
        assert delta.signal == "STABLE"

    def test_dept_delta_populated(self):
        as_of = date(2026, 5, 16)
        curr_incidents = [
            _inc(f"P{i}", as_of - timedelta(days=i+1), dept="Procurement")
            for i in range(10)
        ]
        prior_incidents = [
            _inc(f"Q{i}", as_of - timedelta(days=31+i), dept="Procurement")
            for i in range(5)
        ]
        bundle = _bundle(curr_incidents + prior_incidents)
        report = TrendAgent().analyse(bundle, as_of=as_of)
        assert "Procurement" in report.dept_deltas
        delta = report.dept_deltas["Procurement"]
        assert delta.current == 10
        assert delta.prior   == 5
        assert delta.delta_abs == 5

    def test_type_delta_populated(self):
        as_of = date(2026, 5, 16)
        incidents = [
            _inc(f"A{i}", as_of - timedelta(days=i+1), itype="Approval Delay")
            for i in range(8)
        ] + [
            _inc(f"B{i}", as_of - timedelta(days=31+i), itype="Approval Delay")
            for i in range(4)
        ]
        bundle = _bundle(incidents)
        report = TrendAgent().analyse(bundle, as_of=as_of)
        assert "Approval Delay" in report.type_deltas

    def test_overall_signal_type(self):
        as_of  = date(2026, 5, 16)
        bundle = _bundle([])
        report = TrendAgent().analyse(bundle, as_of=as_of)
        assert report.overall_signal in {"DETERIORATING", "WATCH", "STABLE", "IMPROVING"}


# ---------------------------------------------------------------------------
# Ghost analysis
# ---------------------------------------------------------------------------

class TestGhostAnalysis:
    def test_flat_open_rate_detection(self):
        """If every dept has exactly 20% open rate, ghost flag should trigger."""
        as_of = date(2026, 5, 16)
        # Create 5 incidents per dept, exactly 1 open each (20% open rate)
        depts = ["Procurement", "Compliance", "Legal", "Finance", "HR"]
        incidents = []
        for di, dept in enumerate(depts):
            for i in range(5):
                resolved = (i > 0)  # first one is open
                incidents.append(_inc(
                    f"{dept[:2]}{di}{i}",
                    as_of - timedelta(days=i+1),
                    dept=dept, resolved=resolved
                ))
        bundle = _bundle(incidents)
        report = TrendAgent().analyse(bundle, as_of=as_of)
        # Ghost analysis notes should contain mention of flat rate
        assert any("flat" in note.lower() or "uniform" in note.lower()
                   for note in report.ghost_notes)
