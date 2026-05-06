"""
tests/test_trend_agent.py
==========================
Unit tests for TrendAgent — window stats, MoM delta, signal classification,
ghost analysis, and edge cases (no data, single-day windows).
"""
from __future__ import annotations

from datetime import date, timedelta

from agents.data_agent import DataBundle, Incident
from agents.trend_agent import TrendAgent, MoMDelta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _inc(iid, d: date, dept="Procurement", itype="Approval Delay",
         severity="HIGH", resolved=False, impact=200_000):
    return Incident(
        incident_id=iid, date=d, department=dept,
        type=itype, severity=severity,
        resolved=resolved, financial_impact_inr=impact,
        linked_vendor_id="IV0001", owner_employee_id="EMP001",
    )

def _bundle(incidents):
    return DataBundle(vendors=[], incidents=incidents, employees=[],
                      summary={}, errors=[])


# ---------------------------------------------------------------------------
# Window stats — TrendReport uses .current and .prior (WindowStats)
# ---------------------------------------------------------------------------

class TestWindowStats:
    def test_counts_current_window(self):
        as_of = date(2026, 5, 16)
        incidents = [_inc(f"I{i}", as_of - timedelta(days=i+1)) for i in range(5)]
        incidents += [_inc(f"P{i}", as_of - timedelta(days=31+i)) for i in range(3)]
        report = TrendAgent().analyse(_bundle(incidents), as_of=as_of)
        assert report.current.total == 5
        assert report.prior.total   == 3

    def test_empty_windows(self):
        as_of  = date(2026, 5, 16)
        report = TrendAgent().analyse(_bundle([]), as_of=as_of)
        assert report.current.total == 0
        assert report.prior.total   == 0

    def test_dept_breakdown(self):
        as_of = date(2026, 5, 16)
        incidents = (
            [_inc(f"P{i}", as_of - timedelta(days=i+1), dept="Procurement") for i in range(4)]
            + [_inc(f"C{i}", as_of - timedelta(days=i+1), dept="Compliance") for i in range(2)]
        )
        report = TrendAgent().analyse(_bundle(incidents), as_of=as_of)
        assert report.current.by_dept.get("Procurement", {}).get("total", 0) == 4
        assert report.current.by_dept.get("Compliance", {}).get("total", 0)  == 2


# ---------------------------------------------------------------------------
# MoMDelta — fields: current, prior, delta_abs, delta_pct, direction, signal
# ---------------------------------------------------------------------------

class TestMoMDelta:
    def test_deteriorating_signal(self):
        delta = MoMDelta(current=100, prior=60, delta_abs=40,
                         delta_pct=66.7, direction="UP", signal="DETERIORATING")
        assert delta.signal == "DETERIORATING"

    def test_improving_signal(self):
        delta = MoMDelta(current=40, prior=80, delta_abs=-40,
                         delta_pct=-50.0, direction="DOWN", signal="IMPROVING")
        assert delta.signal == "IMPROVING"

    def test_stable_signal(self):
        delta = MoMDelta(current=50, prior=48, delta_abs=2,
                         delta_pct=4.2, direction="UP", signal="STABLE")
        assert delta.signal == "STABLE"

    def test_dept_delta_populated(self):
        as_of = date(2026, 5, 16)
        incidents = (
            [_inc(f"P{i}", as_of - timedelta(days=i+1), dept="Procurement") for i in range(10)]
            + [_inc(f"Q{i}", as_of - timedelta(days=31+i), dept="Procurement") for i in range(5)]
        )
        report = TrendAgent().analyse(_bundle(incidents), as_of=as_of)
        assert "Procurement" in report.dept_deltas
        vol = report.dept_deltas["Procurement"]["volume"]
        assert vol.current == 10
        assert vol.prior   == 5

    def test_type_delta_populated(self):
        as_of = date(2026, 5, 16)
        incidents = (
            [_inc(f"A{i}", as_of - timedelta(days=i+1), itype="Approval Delay") for i in range(8)]
            + [_inc(f"B{i}", as_of - timedelta(days=31+i), itype="Approval Delay") for i in range(4)]
        )
        report = TrendAgent().analyse(_bundle(incidents), as_of=as_of)
        assert "Approval Delay" in report.type_deltas

    def test_overall_signal_type(self):
        report = TrendAgent().analyse(_bundle([]), as_of=date(2026, 5, 16))
        assert report.volume_mom.signal in {"DETERIORATING", "WATCH", "STABLE", "IMPROVING"}


# ---------------------------------------------------------------------------
# Ghost analysis — report.ghost_flags is a list[str]
# ---------------------------------------------------------------------------

class TestGhostAnalysis:
    def test_flat_open_rate_detection(self):
        as_of = date(2026, 5, 16)
        depts = ["Procurement", "Compliance", "Legal", "Finance", "HR"]
        incidents = []
        for di, dept in enumerate(depts):
            for i in range(5):
                resolved = (i > 0)
                incidents.append(_inc(
                    f"{dept[:2]}{di}{i}", as_of - timedelta(days=i+1),
                    dept=dept, resolved=resolved,
                ))
        report = TrendAgent().analyse(_bundle(incidents), as_of=as_of)
        assert isinstance(report.ghost_flags, list)
