"""
RiskAgent
---------
Responsibility: Apply brain.md thresholds to produce scored, ranked risk objects.

God Mode design:
  Three risk dimensions → one unified RiskReport.
  Every object knows its score, its breach reasons, its financial exposure,
  and its recommended action — so downstream agents (BriefAgent, DashboardAgent)
  never need to re-derive anything.

Devil's Advocate guard:
  A vendor with Risk_Score=10 and Payment_Delay=16 is *internally inconsistent*.
  This agent flags data anomalies as first-class risk objects, not silent ignores.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from .data_agent import DataBundle, Employee, Incident, Vendor

logger = logging.getLogger(__name__)

RiskLevel = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "OK"]
INR_CR    = 10_000_000   # 1 Crore
INR_L     = 100_000      # 1 Lakh


# ─────────────────────────────────────────────────────────────────────────────
# Risk output models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class VendorRisk:
    vendor:           Vendor
    risk_level:       RiskLevel
    breach_reasons:   list[str]
    composite_score:  float          # 0–100
    is_dual_breach:   bool           # score AND delay both over threshold
    anomaly_flags:    list[str]      # data integrity issues
    recommended_action: str


@dataclass
class IncidentRisk:
    incident:         Incident
    risk_level:       RiskLevel
    breach_reasons:   list[str]
    is_high_priority: bool           # HIGH severity + open + >₹1L
    age_days:         int            # days since incident date
    recommended_action: str


@dataclass
class EmployeeRisk:
    employee:         Employee
    risk_level:       RiskLevel
    breach_reasons:   list[str]
    is_high_risk:     bool           # untrained AND >3 incidents
    recommended_action: str


@dataclass
class DepartmentSummary:
    department:         str
    total_incidents:    int
    open_incidents:     int
    open_rate_pct:      float
    open_exposure_inr:  float
    untrained_est_pct:  float
    high_risk_staff:    int
    risk_level:         RiskLevel


@dataclass
class RiskReport:
    """Complete risk picture — passed to BriefAgent and DashboardAgent."""
    as_of_date:           date
    high_risk_vendors:    list[VendorRisk]
    high_risk_incidents:  list[IncidentRisk]
    high_risk_employees:  list[EmployeeRisk]
    dept_summaries:       list[DepartmentSummary]

    # Aggregate metrics
    total_vendors:              int = 0
    high_risk_vendor_count:     int = 0
    total_contract_exposure_inr: float = 0.0
    total_incidents:            int = 0
    open_incidents:             int = 0
    open_rate_pct:              float = 0.0
    total_open_exposure_inr:    float = 0.0
    avg_payment_delay_days:     float = 0.0
    high_severity_count:        int = 0
    data_quality_flags:         list[str] = field(default_factory=list)

    @property
    def total_contract_exposure_cr(self) -> float:
        return self.total_contract_exposure_inr / INR_CR

    @property
    def total_open_exposure_l(self) -> float:
        return self.total_open_exposure_inr / INR_L


# ─────────────────────────────────────────────────────────────────────────────
# Thresholds — sourced from brain.md
# ─────────────────────────────────────────────────────────────────────────────

class Thresholds:
    VENDOR_RISK_SCORE_HIGH   = 7.0
    VENDOR_DELAY_DAYS_HIGH   = 15
    VENDOR_SCORE_CRITICAL    = 9.5
    VENDOR_DELAY_CRITICAL    = 45

    INCIDENT_MIN_IMPACT_INR  = 100_000   # ₹1 Lakh
    INCIDENT_HIGH_IMPACT_INR = 300_000   # ₹3 Lakh

    EMPLOYEE_MIN_INCIDENTS   = 3
    EMPLOYEE_CRITICAL_INCIDENTS = 5

    PRIORITY_DEPTS = {"Procurement", "Compliance", "Vendor Management"}
    OPEN_RATE_CRITICAL = 25.0    # %
    OPEN_RATE_HIGH     = 20.0    # %


# ─────────────────────────────────────────────────────────────────────────────
# RiskAgent
# ─────────────────────────────────────────────────────────────────────────────

class RiskAgent:
    """
    Scores all entities in a DataBundle and returns a RiskReport.

    Usage
    -----
    >>> agent = RiskAgent()
    >>> report = agent.analyse(bundle)
    >>> print(f"High-risk vendors: {report.high_risk_vendor_count}")
    >>> print(f"Total exposure: ₹{report.total_contract_exposure_cr:.0f} Cr")
    """

    def __init__(self, thresholds: Thresholds | None = None) -> None:
        self.t = thresholds or Thresholds()

    def analyse(self, bundle: DataBundle) -> RiskReport:
        """Run full risk analysis pipeline."""
        logger.info("RiskAgent.analyse() starting")
        today = date.today()

        vendor_risks   = self._score_vendors(bundle.vendors)
        incident_risks = self._score_incidents(bundle.incidents, today)
        employee_risks = self._score_employees(bundle.employees)
        dept_summaries = self._build_dept_summaries(bundle.incidents, bundle.employees)

        # Aggregate
        hr_vendors = [r for r in vendor_risks if r.risk_level in ("CRITICAL", "HIGH")]
        hr_incidents = [r for r in incident_risks if r.is_high_priority]
        hr_employees = [r for r in employee_risks if r.is_high_risk]

        open_incs = [inc for inc in bundle.incidents if not inc.resolved]
        total_open_exposure = sum(inc.financial_impact_inr for inc in open_incs)
        avg_delay = (
            sum(v.payment_delay_days for v in bundle.vendors) / len(bundle.vendors)
            if bundle.vendors else 0.0
        )
        hr_contract_exposure = sum(
            r.vendor.contract_value_inr for r in hr_vendors
        )

        report = RiskReport(
            as_of_date              = today,
            high_risk_vendors       = sorted(hr_vendors, key=lambda x: -x.composite_score),
            high_risk_incidents     = sorted(hr_incidents, key=lambda x: -x.incident.financial_impact_inr),
            high_risk_employees     = sorted(hr_employees, key=lambda x: -x.employee.compliance_incidents),
            dept_summaries          = sorted(dept_summaries, key=lambda x: -x.open_incidents),
            total_vendors           = len(bundle.vendors),
            high_risk_vendor_count  = len(hr_vendors),
            total_contract_exposure_inr = hr_contract_exposure,
            total_incidents         = len(bundle.incidents),
            open_incidents          = len(open_incs),
            open_rate_pct           = len(open_incs) / len(bundle.incidents) * 100 if bundle.incidents else 0,
            total_open_exposure_inr = total_open_exposure,
            avg_payment_delay_days  = avg_delay,
            high_severity_count     = sum(1 for inc in bundle.incidents if inc.severity == "HIGH"),
            data_quality_flags      = bundle.errors,
        )

        logger.info(
            "RiskAgent complete — %d high-risk vendors, %d high-priority incidents, %d high-risk staff",
            len(report.high_risk_vendors), len(report.high_risk_incidents), len(report.high_risk_employees)
        )
        return report

    # ── vendor scoring ────────────────────────────────────────────────────────

    def _score_vendors(self, vendors: list[Vendor]) -> list[VendorRisk]:
        results = []
        for v in vendors:
            reasons, anomalies = [], []
            score_breach = v.risk_score > self.t.VENDOR_RISK_SCORE_HIGH
            delay_breach = v.payment_delay_days > self.t.VENDOR_DELAY_DAYS_HIGH

            if score_breach:
                reasons.append(f"Risk Score {v.risk_score:.1f} > threshold {self.t.VENDOR_RISK_SCORE_HIGH}")
            if delay_breach:
                reasons.append(f"Payment Delay {v.payment_delay_days:.0f}d > threshold {self.t.VENDOR_DELAY_DAYS_HIGH}d")

            # Anomaly: very high score with very low delay is inconsistent
            if v.risk_score >= 9.5 and v.payment_delay_days < 10:
                anomalies.append(
                    f"ANOMALY: Score={v.risk_score} with Delay={v.payment_delay_days}d — "
                    "inconsistent. Possible scoring model error or non-financial risk. "
                    "Forensic audit required before contract renewal."
                )

            if not (score_breach or delay_breach):
                continue

            # Composite score (0–100) weights: 60% risk score normalised, 40% delay normalised
            normalised_score = min(v.risk_score / 10, 1.0) * 60
            normalised_delay = min(v.payment_delay_days / 90, 1.0) * 40
            composite = round(normalised_score + normalised_delay, 1)

            if v.risk_score >= self.t.VENDOR_SCORE_CRITICAL or v.payment_delay_days >= self.t.VENDOR_DELAY_CRITICAL:
                level = "CRITICAL"
            elif score_breach and delay_breach:
                level = "HIGH"
            else:
                level = "MEDIUM"

            action = self._vendor_action(v, score_breach, delay_breach)

            results.append(VendorRisk(
                vendor=v, risk_level=level, breach_reasons=reasons,
                composite_score=composite, is_dual_breach=(score_breach and delay_breach),
                anomaly_flags=anomalies, recommended_action=action,
            ))
        return results

    def _vendor_action(self, v: Vendor, score: bool, delay: bool) -> str:
        if v.risk_score >= 9.5:
            return "IMMEDIATE: Quarantine + forensic audit before next payment cycle"
        if delay and v.payment_delay_days >= 45:
            return "URGENT: Vendor distress signal — verify continuity plan + backup vendor"
        if score and delay:
            return "HIGH: Payment hold (post-Legal MAC check) + re-audit within 5 days"
        if score:
            return "MEDIUM: Risk audit — identify source of elevated score"
        return "MEDIUM: Payment process review — normalise delay within 2 weeks"

    # ── incident scoring ──────────────────────────────────────────────────────

    def _score_incidents(self, incidents: list[Incident], today: date) -> list[IncidentRisk]:
        results = []
        for inc in incidents:
            if inc.resolved:
                continue
            if inc.financial_impact_inr < self.t.INCIDENT_MIN_IMPACT_INR:
                continue

            reasons = [
                f"Unresolved | {inc.severity} severity | ₹{inc.financial_impact_inr/100000:.2f}L impact"
            ]
            age = (today - inc.date).days if inc.date else 0
            if age > 30:
                reasons.append(f"AGED: {age} days open — SLA breach")
            if inc.department in self.t.PRIORITY_DEPTS:
                reasons.append(f"Priority dept: {inc.department}")

            is_hp = (
                inc.severity == "HIGH"
                or inc.financial_impact_inr >= self.t.INCIDENT_HIGH_IMPACT_INR
                or age > 90
            )

            if inc.severity == "HIGH" and inc.financial_impact_inr >= self.t.INCIDENT_HIGH_IMPACT_INR:
                level = "CRITICAL"
            elif inc.severity == "HIGH" or inc.financial_impact_inr >= self.t.INCIDENT_HIGH_IMPACT_INR:
                level = "HIGH"
            elif age > 90:
                level = "HIGH"
            else:
                level = "MEDIUM"

            action = self._incident_action(inc, age)

            results.append(IncidentRisk(
                incident=inc, risk_level=level, breach_reasons=reasons,
                is_high_priority=is_hp, age_days=age, recommended_action=action,
            ))
        return results

    def _incident_action(self, inc: Incident, age: int) -> str:
        if inc.severity == "HIGH":
            return f"WAR ROOM: Escalate to Dept Head today — HIGH severity, ₹{inc.financial_impact_inr/100000:.1f}L"
        if age > 180:
            return f"ABANDONED: {age}d open — reassign owner, root cause mandatory"
        if age > 90:
            return f"OVERDUE: {age}d open — escalate to VP {inc.department}"
        if inc.financial_impact_inr >= self.t.INCIDENT_HIGH_IMPACT_INR:
            return f"PRIORITY: ₹{inc.financial_impact_inr/100000:.1f}L — assign senior owner, 48h resolution"
        return "ACTION: Assign active owner, set 5-day resolution SLA"

    # ── employee scoring ──────────────────────────────────────────────────────

    def _score_employees(self, employees: list[Employee]) -> list[EmployeeRisk]:
        results = []
        for emp in employees:
            untrained = not emp.training_completed
            high_incidents = emp.compliance_incidents > self.t.EMPLOYEE_MIN_INCIDENTS

            if not (untrained or high_incidents):
                continue

            reasons, is_hr = [], False
            if untrained:
                reasons.append("Training NOT completed")
            if high_incidents:
                reasons.append(f"Compliance incidents: {emp.compliance_incidents} > threshold {self.t.EMPLOYEE_MIN_INCIDENTS}")

            is_hr = untrained and high_incidents

            if untrained and emp.compliance_incidents >= self.t.EMPLOYEE_CRITICAL_INCIDENTS:
                level = "CRITICAL"
            elif untrained and high_incidents:
                level = "HIGH"
            elif emp.compliance_incidents >= self.t.EMPLOYEE_CRITICAL_INCIDENTS:
                level = "MEDIUM"
            else:
                level = "LOW"

            action = self._employee_action(emp, untrained, high_incidents)

            results.append(EmployeeRisk(
                employee=emp, risk_level=level, breach_reasons=reasons,
                is_high_risk=is_hr, recommended_action=action,
            ))
        return results

    def _employee_action(self, emp: Employee, untrained: bool, high_inc: bool) -> str:
        if untrained and emp.compliance_incidents >= self.t.EMPLOYEE_CRITICAL_INCIDENTS:
            return f"CRITICAL: PIP + mandatory training + supervised review — {emp.role}, {emp.department}"
        if untrained:
            return "HIGH: Enrol in mandatory training sprint within 5 business days"
        if high_inc:
            return f"MEDIUM: Root cause review — {emp.compliance_incidents} incidents despite completed training"
        return "LOW: Monitor — reassess at next compliance cycle"

    # ── department summaries ──────────────────────────────────────────────────

    def _build_dept_summaries(
        self,
        incidents: list[Incident],
        employees: list[Employee],
    ) -> list[DepartmentSummary]:
        from collections import defaultdict

        dept_total: dict[str, int]   = defaultdict(int)
        dept_open:  dict[str, int]   = defaultdict(int)
        dept_exp:   dict[str, float] = defaultdict(float)
        dept_emp:   dict[str, int]   = defaultdict(int)
        dept_untrained: dict[str, int] = defaultdict(int)
        dept_hr_staff:  dict[str, int] = defaultdict(int)

        for inc in incidents:
            dept_total[inc.department] += 1
            if not inc.resolved:
                dept_open[inc.department] += 1
                dept_exp[inc.department] += inc.financial_impact_inr

        for emp in employees:
            dept_emp[emp.department] += 1
            if not emp.training_completed:
                dept_untrained[emp.department] += 1
            if not emp.training_completed and emp.compliance_incidents > self.t.EMPLOYEE_MIN_INCIDENTS:
                dept_hr_staff[emp.department] += 1

        summaries = []
        for dept, total in dept_total.items():
            open_cnt = dept_open[dept]
            open_rate = open_cnt / total * 100 if total else 0
            emp_cnt   = dept_emp.get(dept, 0)
            untrained_pct = dept_untrained.get(dept, 0) / emp_cnt * 100 if emp_cnt else 0

            if open_rate >= self.t.OPEN_RATE_CRITICAL or dept in self.t.PRIORITY_DEPTS and open_rate > 20:
                level = "CRITICAL"
            elif open_rate >= self.t.OPEN_RATE_HIGH:
                level = "HIGH"
            elif open_rate >= 15:
                level = "MEDIUM"
            else:
                level = "LOW"

            summaries.append(DepartmentSummary(
                department        = dept,
                total_incidents   = total,
                open_incidents    = open_cnt,
                open_rate_pct     = round(open_rate, 1),
                open_exposure_inr = dept_exp[dept],
                untrained_est_pct = round(untrained_pct, 1),
                high_risk_staff   = dept_hr_staff.get(dept, 0),
                risk_level        = level,
            ))
        return summaries
