"""
tests/test_brief_agent.py
==========================
Unit tests for BriefAgent — verifies Markdown structure, section presence,
INR formatting, callout blocks, and save functionality.
"""
from __future__ import annotations

from datetime import date


from agents.data_agent import DataBundle, Vendor, Incident, Employee
from agents.risk_agent  import RiskAgent
from agents.trend_agent import TrendAgent
from agents.brief_agent import BriefAgent, _inr_l, _inr_cr


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bundle():
    # Vendor(vendor_id, name, category, contract_value_inr, payment_delay_days, risk_score, last_audit_date, region)
    vendors = [
        Vendor("IV0001", "Vendor A", "IT Services",  5_000_000, 25, 8.5, "2025-06-01", "South"),
        Vendor("IV0002", "Vendor B", "Consulting",   1_000_000,  5, 3.0, "2025-08-01", "West"),
    ]
    # Incident(incident_id, date, department, type, severity, resolved, owner_employee_id, linked_vendor_id, financial_impact_inr)
    incidents = [
        Incident("INC001", date(2026,4,20), "Procurement", "Approval Delay", "HIGH",   False, "EMP001", "IV0001", 250_000.0),
        Incident("INC002", date(2026,4,15), "Compliance",  "Audit Finding",  "MEDIUM", True,  "EMP002", "IV0002", 120_000.0),
        Incident("INC003", date(2026,5,1),  "Procurement", "PO Expiry",      "HIGH",   False, "EMP001", "IV0001", 180_000.0),
    ]
    # Employee(employee_id, name, department, role, join_date, performance_score, training_completed, compliance_incidents, salary_band)
    employees = [
        Employee("EMP001", "Manager", "Procurement", "Procurement Manager", "2025-01-01", 3.5, False, 4, "L4"),
        Employee("EMP002", "Analyst", "Compliance",  "Compliance Officer",  "2025-06-01", 4.0, True,  1, "L3"),
    ]
    return DataBundle(vendors=vendors, incidents=incidents,
                      employees=employees, summary={}, errors=[])


# ---------------------------------------------------------------------------
# INR formatting helpers
# ---------------------------------------------------------------------------

class TestInrFormatting:
    def test_inr_l_thousands(self):
        assert "L" in _inr_l(150_000)

    def test_inr_cr_millions(self):
        assert "Cr" in _inr_cr(10_000_000)

    def test_inr_l_zero(self):
        result = _inr_l(0)
        assert "0" in result

    def test_inr_cr_large(self):
        result = _inr_cr(1_560_000_000)
        # 1,560,000,000 = 156 Cr
        assert "156" in result


# ---------------------------------------------------------------------------
# weekly_brief
# ---------------------------------------------------------------------------

class TestWeeklyBrief:
    def _brief(self):
        bundle = _make_bundle()
        risk   = RiskAgent().analyse(bundle)
        trend  = TrendAgent().analyse(bundle, as_of=date(2026, 5, 16))
        return BriefAgent().weekly_brief(risk, trend)

    def test_returns_string(self):
        assert isinstance(self._brief(), str)

    def test_has_executive_summary(self):
        md = self._brief()
        assert "Executive Summary" in md or "EXECUTIVE SUMMARY" in md

    def test_has_risk_section(self):
        md = self._brief()
        assert "Risk" in md

    def test_has_department_section(self):
        md = self._brief()
        assert "Department" in md

    def test_has_actions_section(self):
        md = self._brief()
        assert "Action" in md

    def test_has_cxo_questions(self):
        md = self._brief()
        assert "?" in md  # at least one question mark

    def test_has_inr_symbol(self):
        md = self._brief()
        assert "₹" in md

    def test_notion_warning_callout(self):
        md = self._brief()
        assert "[!WARNING]" in md or "[!NOTE]" in md

    def test_not_empty(self):
        md = self._brief()
        assert len(md) > 500


# ---------------------------------------------------------------------------
# trend_brief
# ---------------------------------------------------------------------------

class TestTrendBrief:
    def _trend_brief(self):
        bundle = _make_bundle()
        trend  = TrendAgent().analyse(bundle, as_of=date(2026, 5, 16))
        return BriefAgent().trend_brief(trend)

    def test_returns_string(self):
        assert isinstance(self._trend_brief(), str)

    def test_has_trend_content(self):
        md = self._trend_brief()
        assert "Trend" in md or "MoM" in md or "30-Day" in md

    def test_not_empty(self):
        assert len(self._trend_brief()) > 200


# ---------------------------------------------------------------------------
# save
# ---------------------------------------------------------------------------

class TestBriefAgentSave:
    def test_save_creates_file(self, tmp_path):
        path    = tmp_path / "test_brief.md"
        content = "# Test\n\nSome content here."
        BriefAgent().save(content, path)
        assert path.exists()
        assert path.read_text(encoding="utf-8") == content

    def test_save_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "nested" / "dir" / "brief.md"
        BriefAgent().save("# Brief", path)
        assert path.exists()
