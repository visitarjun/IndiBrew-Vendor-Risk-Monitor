"""
tests/test_risk_agent.py
=========================
Unit tests for RiskAgent — scoring, thresholds, anomaly detection,
composite scores, and department rollup.

Business logic:
  Vendor HIGH  = score > 7 AND delay > 15 (dual breach)
  Vendor CRITICAL = score >= 9.5 OR delay >= 60
  Employee HIGH = untrained AND incidents > 3
"""
from __future__ import annotations

from datetime import date

import pytest

from agents.data_agent import DataBundle, Vendor, Incident, Employee
from agents.risk_agent import RiskAgent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _vendor(vid="IV0001", score=8.5, delay=20, contract=5_000_000):
    return Vendor(
        vendor_id=vid,
        name=f"Vendor {vid}",
        category="IT Services",
        contract_value_inr=contract,
        payment_delay_days=delay,
        risk_score=score,
        last_audit_date="2025-06-01",
        region="South",
    )


def _incident(
    iid="INC001",
    dept="Procurement",
    resolved=False,
    impact=250_000,
    severity="HIGH",
    itype="Approval Delay",
    inc_date=date(2026, 4, 1),
    vendor_id="IV0001",
):
    return Incident(
        incident_id=iid,
        date=inc_date,
        department=dept,
        type=itype,
        severity=severity,
        resolved=resolved,
        financial_impact_inr=impact,
        linked_vendor_id=vendor_id,
        owner_employee_id="EMP001",
    )


def _employee(eid="EMP001", dept="Procurement", incidents=4, trained=False):
    return Employee(
        employee_id=eid,
        name=f"Employee {eid}",
        department=dept,
        role="Procurement Manager",
        join_date="2024-01-01",
        performance_score=3.5,
        training_completed=trained,
        compliance_incidents=incidents,
        salary_band="L4",
    )


def _bundle(vendors=None, incidents=None, employees=None):
    return DataBundle(
        vendors=vendors or [],
        incidents=incidents or [],
        employees=employees or [],
        summary={},
        errors=[],
    )


# ---------------------------------------------------------------------------
# Vendor scoring
# ---------------------------------------------------------------------------

class TestVendorScoring:
    def test_high_risk_dual_breach(self):
        # HIGH = score > 7 AND delay > 15
        bundle = _bundle(vendors=[_vendor(score=8.0, delay=20)])
        report = RiskAgent().analyse(bundle)
        assert len(report.high_risk_vendors) == 1

    def test_single_breach_score_only_not_high(self):
        # score > 7 but delay <= 15 -> MEDIUM, not in high_risk_vendors
        bundle = _bundle(vendors=[_vendor(score=8.0, delay=5)])
        report = RiskAgent().analyse(bundle)
        assert len(report.high_risk_vendors) == 0

    def test_single_breach_delay_only_not_high(self):
        # delay > 15 but score <= 7 -> MEDIUM, not in high_risk_vendors
        bundle = _bundle(vendors=[_vendor(score=3.0, delay=20)])
        report = RiskAgent().analyse(bundle)
        assert len(report.high_risk_vendors) == 0

    def test_safe_vendor_not_flagged(self):
        bundle = _bundle(vendors=[_vendor(score=4.0, delay=10)])
        report = RiskAgent().analyse(bundle)
        assert len(report.high_risk_vendors) == 0

    def test_critical_vendor_by_score(self):
        # score >= 9.5 -> CRITICAL (regardless of delay)
        bundle = _bundle(vendors=[_vendor(score=9.5, delay=5)])
        report = RiskAgent().analyse(bundle)
        assert len(report.high_risk_vendors) == 1
        assert report.high_risk_vendors[0].risk_level == "CRITICAL"

    def test_anomaly_flag_high_score_low_delay(self):
        # score >= 9.5 with delay < 10 -> anomaly_flags populated
        bundle = _bundle(vendors=[_vendor(score=10.0, delay=5)])
        report = RiskAgent().analyse(bundle)
        vr = report.high_risk_vendors[0]
        assert len(vr.anomaly_flags) > 0

    def test_exposure_sum(self):
        v1 = _vendor("IV0001", score=8.0, delay=20, contract=5_000_000)
        v2 = _vendor("IV0002", score=8.5, delay=25, contract=3_000_000)
        bundle = _bundle(vendors=[v1, v2])
        report = RiskAgent().analyse(bundle)
        assert report.total_contract_exposure_inr == pytest.approx(8_000_000)

    def test_composite_score_bounds(self):
        bundle = _bundle(vendors=[_vendor(score=10.0, delay=90)])
        report = RiskAgent().analyse(bundle)
        vr = report.high_risk_vendors[0]
        assert 0 <= vr.composite_score <= 100


# ---------------------------------------------------------------------------
# Incident scoring
# ---------------------------------------------------------------------------

class TestIncidentScoring:
    def test_open_high_impact_flagged(self):
        bundle = _bundle(incidents=[_incident(resolved=False, impact=150_000)])
        report = RiskAgent().analyse(bundle)
        assert len(report.high_risk_incidents) == 1

    def test_resolved_not_flagged(self):
        bundle = _bundle(incidents=[_incident(resolved=True, impact=500_000)])
        report = RiskAgent().analyse(bundle)
        assert len(report.high_risk_incidents) == 0

    def test_low_impact_not_flagged(self):
        bundle = _bundle(incidents=[_incident(resolved=False, impact=50_000)])
        report = RiskAgent().analyse(bundle)
        assert len(report.high_risk_incidents) == 0

    def test_open_count(self):
        inc = [_incident(f"INC{i:03d}", resolved=(i % 5 == 0)) for i in range(10)]
        bundle = _bundle(incidents=inc)
        report = RiskAgent().analyse(bundle)
        assert report.open_incidents == 8


# ---------------------------------------------------------------------------
# Employee scoring
# ---------------------------------------------------------------------------

class TestEmployeeScoring:
    def test_untrained_high_incidents_flagged(self):
        # is_high_risk = untrained AND incidents > 3
        bundle = _bundle(employees=[_employee(incidents=4, trained=False)])
        report = RiskAgent().analyse(bundle)
        assert len(report.high_risk_employees) == 1

    def test_trained_not_flagged(self):
        bundle = _bundle(employees=[_employee(incidents=5, trained=True)])
        report = RiskAgent().analyse(bundle)
        assert len(report.high_risk_employees) == 0

    def test_low_incidents_not_flagged(self):
        bundle = _bundle(employees=[_employee(incidents=2, trained=False)])
        report = RiskAgent().analyse(bundle)
        assert len(report.high_risk_employees) == 0


# ---------------------------------------------------------------------------
# Department rollup
# ---------------------------------------------------------------------------

class TestDepartmentRollup:
    def _dept_map(self, report):
        return {d.department: d for d in report.dept_summaries}

    def test_dept_total_count(self):
        inc = [_incident(f"I{i}", dept="Procurement") for i in range(5)]
        report = RiskAgent().analyse(_bundle(incidents=inc))
        assert self._dept_map(report)["Procurement"].total_incidents == 5

    def test_dept_open_count(self):
        inc = [_incident(f"I{i}", dept="Compliance", resolved=(i >= 3)) for i in range(6)]
        report = RiskAgent().analyse(_bundle(incidents=inc))
        assert self._dept_map(report)["Compliance"].open_incidents == 3

    def test_multiple_depts(self):
        inc = (
            [_incident(f"P{i}", dept="Procurement") for i in range(3)]
            + [_incident(f"L{i}", dept="Legal") for i in range(2)]
        )
        report = RiskAgent().analyse(_bundle(incidents=inc))
        depts = self._dept_map(report)
        assert "Procurement" in depts
        assert "Legal" in depts
