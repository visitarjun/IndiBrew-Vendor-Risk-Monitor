"""
tests/test_risk_agent.py
=========================
Unit tests for RiskAgent — scoring, threshold enforcement, anomaly detection,
composite scores, and department rollup accuracy.
"""
from __future__ import annotations

from datetime import date

import pytest

from agents.data_agent import DataBundle, Vendor, Incident, Employee
from agents.risk_agent import RiskAgent, Thresholds


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _vendor(vid="IV0001", score=8.5, delay=20, contract=5_000_000):
    return Vendor(
        vendor_id=vid, vendor_name=f"Vendor {vid}",
        category="IT Services",
        risk_score=score, payment_delay_days=delay,
        contract_value_inr=contract, active=True,
        last_audit_date=date(2025, 6, 1),
    )

def _incident(iid="INC001", dept="Procurement", resolved=False,
              impact=250_000, severity="HIGH", itype="Approval Delay",
              inc_date=date(2026, 4, 1), vendor_id="IV0001"):
    return Incident(
        incident_id=iid, date=inc_date, department=dept,
        incident_type=itype, severity=severity,
        resolved=resolved, financial_impact_inr=impact,
        vendor_id=vendor_id, employee_id="EMP001",
    )

def _employee(eid="EMP001", dept="Procurement", incidents=4, trained=False):
    return Employee(
        employee_id=eid, name=f"Employee {eid}",
        role="Procurement Manager", department=dept,
        training_completed=trained,
        compliance_incidents=incidents,
        last_training_date=date(2025, 1, 1),
    )

def _bundle(vendors=None, incidents=None, employees=None):
    return DataBundle(
        vendors   = vendors   or [],
        incidents = incidents or [],
        employees = employees or [],
        summary   = {},
        errors    = [],
    )


# ---------------------------------------------------------------------------
# Vendor scoring
# ---------------------------------------------------------------------------

class TestVendorScoring:
    def test_high_risk_by_score(self):
        bundle = _bundle(vendors=[_vendor(score=8.0, delay=5)])
        report = RiskAgent().analyse(bundle)
        assert len(report.high_risk_vendors) == 1

    def test_high_risk_by_delay(self):
        bundle = _bundle(vendors=[_vendor(score=3.0, delay=20)])
        report = RiskAgent().analyse(bundle)
        assert len(report.high_risk_vendors) == 1

    def test_safe_vendor_not_flagged(self):
        bundle = _bundle(vendors=[_vendor(score=4.0, delay=10)])
        report = RiskAgent().analyse(bundle)
        assert len(report.high_risk_vendors) == 0

    def test_critical_vendor_anomaly(self):
        """risk_score >= 9.5 but payment_delay < 10 → anomaly flag."""
        bundle = _bundle(vendors=[_vendor(score=10.0, delay=5)])
        report = RiskAgent().analyse(bundle)
        vr = report.high_risk_vendors[0]
        assert vr.is_anomaly is True

    def test_exposure_sum(self):
        v1 = _vendor("IV0001", score=8.0, contract=5_000_000)
        v2 = _vendor("IV0002", score=8.5, contract=3_000_000)
        bundle = _bundle(vendors=[v1, v2])
        report = RiskAgent().analyse(bundle)
        assert report.total_high_risk_exposure_inr == pytest.approx(8_000_000)

    def test_composite_score_bounds(self):
        bundle = _bundle(vendors=[_vendor(score=10.0, delay=90)])
        report = RiskAgent().analyse(bundle)
        vr = report.high_risk_vendors[0]
        assert 0 <= vr.composite_risk_score <= 100


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
        inc = [
            _incident(f"INC{i:03d}", resolved=(i % 5 == 0))
            for i in range(10)
        ]
        bundle = _bundle(incidents=inc)
        report = RiskAgent().analyse(bundle)
        assert report.open_incidents == 8  # 8 out of 10 are unresolved


# ---------------------------------------------------------------------------
# Employee scoring
# ---------------------------------------------------------------------------

class TestEmployeeScoring:
    def test_untrained_high_incidents_flagged(self):
        bundle = _bundle(employees=[_employee(incidents=4, trained=False)])
        report = RiskAgent().analyse(bundle)
        assert len(report.high_risk_employees) == 1

    def test_trained_but_high_incidents_not_flagged(self):
        # training_completed=True → not flagged by default threshold
        bundle = _bundle(employees=[_employee(incidents=5, trained=True)])
        report = RiskAgent().analyse(bundle)
        assert len(report.high_risk_employees) == 0

    def test_low_incidents_not_flagged(self):
        bundle = _bundle(employees=[_employee(incidents=2, trained=False)])
        report = RiskAgent().analyse(bundle)
        assert len(report.high_risk_employees) == 0

    def test_undertrained_count(self):
        emps = [
            _employee(f"E{i:03d}", incidents=4, trained=(i % 3 == 0))
            for i in range(9)
        ]
        bundle = _bundle(employees=emps)
        report = RiskAgent().analyse(bundle)
        assert report.undertrained_employee_count == 6


# ---------------------------------------------------------------------------
# Department rollup
# ---------------------------------------------------------------------------

class TestDepartmentRollup:
    def test_dept_total_count(self):
        inc = [_incident(f"I{i}", dept="Procurement") for i in range(5)]
        bundle = _bundle(incidents=inc)
        report = RiskAgent().analyse(bundle)
        proc = report.department_summaries.get("Procurement")
        assert proc is not None
        assert proc.total_incidents == 5

    def test_dept_open_count(self):
        inc = [
            _incident(f"I{i}", dept="Compliance", resolved=(i >= 3))
            for i in range(6)
        ]
        bundle = _bundle(incidents=inc)
        report = RiskAgent().analyse(bundle)
        comp = report.department_summaries["Compliance"]
        assert comp.open_incidents == 3

    def test_multiple_depts(self):
        inc = (
            [_incident(f"P{i}", dept="Procurement") for i in range(3)] +
            [_incident(f"L{i}", dept="Legal")       for i in range(2)]
        )
        bundle = _bundle(incidents=inc)
        report = RiskAgent().analyse(bundle)
        assert "Procurement" in report.department_summaries
        assert "Legal"       in report.department_summaries
