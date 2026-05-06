"""
tests/test_data_agent.py
========================
Unit tests for DataAgent — CSV loading, INR parsing, date parsing,
BOM handling, duplicate detection, and 5L cap flag.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from agents.data_agent import DataAgent, _parse_inr, _parse_date


# ---------------------------------------------------------------------------
# _parse_inr
# ---------------------------------------------------------------------------

class TestParseInr:
    def test_standard(self):
        assert _parse_inr(" 1,50,548.00 ") == 150548.0

    def test_no_spaces(self):
        assert _parse_inr("500000.00") == 500000.0

    def test_integer_string(self):
        assert _parse_inr("100000") == 100000.0

    def test_large_crore(self):
        assert _parse_inr(" 1,00,00,000.00 ") == 10000000.0

    def test_zero(self):
        assert _parse_inr("0.00") == 0.0

    def test_invalid_returns_zero(self):
        assert _parse_inr("N/A") == 0.0

    def test_empty_returns_zero(self):
        assert _parse_inr("") == 0.0


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_dd_month_yyyy(self):
        from datetime import date
        assert _parse_date("15 June 2025") == date(2025, 6, 15)

    def test_iso_format(self):
        from datetime import date
        assert _parse_date("2025-06-15") == date(2025, 6, 15)

    def test_slash_format(self):
        from datetime import date
        assert _parse_date("15/06/2025") == date(2025, 6, 15)

    def test_invalid_returns_none(self):
        assert _parse_date("not-a-date") is None

    def test_empty_returns_none(self):
        assert _parse_date("") is None


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _write_vendors(path: Path, rows=None):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Vendor_ID", "Name", "Category", "Contract_Value_INR",
                    "Payment_Delay_Days", "Risk_Score", "Last_Audit_Date", "Region"])
        for r in (rows or [
            ["IV0001", "Vendor A", "IT Services", " 5,00,000.00 ", "20", "8.5", "2025-06-01", "South"],
            ["IV0002", "Vendor B", "Consulting",  " 1,00,000.00 ", "5",  "3.2", "2025-08-01", "West"],
            ["IV0001", "Vendor A", "IT Services", " 5,00,000.00 ", "20", "8.5", "2025-06-01", "South"],  # dup
        ]):
            w.writerow(r)


def _write_incidents(path: Path, rows=None):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Incident_ID", "Date", "Department", "Type",
                    "Severity", "Resolved", "Financial_Impact_INR",
                    "Linked_Vendor_ID", "Owner_Employee_ID"])
        for r in (rows or [
            ["INC001", "1 January 2026",  "Procurement", "Approval Delay", "HIGH",   "False", " 2,50,000.00 ", "IV0001", "EMP001"],
            ["INC002", "15 April 2026",   "Compliance",  "Audit Finding",  "LOW",    "True",  "   50,000.00 ", "IV0002", "EMP002"],
            ["INC003", "1 May 2026",      "Legal",       "Policy Violation","MEDIUM","False", " 5,00,000.00 ", "",       "EMP003"],
            ["INC004", "2 May 2026",      "Finance",     "Data Quality",    "MEDIUM","False", " 5,00,000.00 ", "",       "EMP004"],
        ]):
            w.writerow(r)


def _write_employees(path: Path, rows=None):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Employee_ID", "Name", "Department", "Role",
                    "Join_Date", "Performance_Score", "Training_Completed",
                    "Compliance_Incidents", "Salary_Band"])
        for r in (rows or [
            ["EMP001", "Alice", "Procurement", "Procurement Manager", "2024-01-01", "3.5", "False", "4", "L4"],
            ["EMP002", "Bob",   "Compliance",  "Compliance Officer",  "2024-06-01", "4.0", "True",  "1", "L3"],
        ]):
            w.writerow(r)


def _write_summary(path: Path):
    path.write_text(json.dumps({"organisation": "Test GCC", "as_of": "2026-05-16"}))


@pytest.fixture
def sample_data_dir(tmp_path: Path) -> Path:
    _write_vendors(tmp_path / "ibsh_vendors_2k.csv")
    _write_incidents(tmp_path / "ibsh_incidents_90k.csv")
    _write_employees(tmp_path / "ibsh_employees_5k.csv")
    _write_summary(tmp_path / "ibsh_enterprise_summary.json")
    return tmp_path


# ---------------------------------------------------------------------------
# DataAgent.load integration tests
# ---------------------------------------------------------------------------

class TestDataAgent:
    def test_loads_vendors(self, sample_data_dir):
        bundle = DataAgent(data_dir=sample_data_dir).load()
        assert len(bundle.vendors) >= 2

    def test_loads_incidents(self, sample_data_dir):
        bundle = DataAgent(data_dir=sample_data_dir).load()
        assert len(bundle.incidents) >= 2

    def test_loads_employees(self, sample_data_dir):
        bundle = DataAgent(data_dir=sample_data_dir).load()
        assert len(bundle.employees) == 2

    def test_duplicate_vendor_warning(self, sample_data_dir):
        bundle = DataAgent(data_dir=sample_data_dir).load()
        dup_warnings = [e for e in bundle.errors if "duplicate" in e.lower()]
        assert len(dup_warnings) > 0

    def test_five_lakh_cap_flag(self, sample_data_dir):
        bundle = DataAgent(data_dir=sample_data_dir).load()
        cap_warnings = [e for e in bundle.errors
                        if "cap" in e.lower() or "5,00,000" in e or "500000" in e]
        assert len(cap_warnings) > 0

    def test_vendor_risk_score_parsed(self, sample_data_dir):
        bundle = DataAgent(data_dir=sample_data_dir).load()
        assert any(v.risk_score > 7 for v in bundle.vendors)

    def test_incident_resolved_false(self, sample_data_dir):
        bundle = DataAgent(data_dir=sample_data_dir).load()
        assert any(not i.resolved for i in bundle.incidents)

    def test_employee_training_false(self, sample_data_dir):
        bundle = DataAgent(data_dir=sample_data_dir).load()
        assert any(not e.training_completed for e in bundle.employees)

    def test_missing_file_raises(self, tmp_path):
        bundle = DataAgent(data_dir=tmp_path).load()
        assert len(bundle.errors) > 0

    def test_bom_encoding(self, tmp_path):
        """BOM-prefixed vendor CSV should parse correctly."""
        with (tmp_path / "ibsh_vendors_2k.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Vendor_ID", "Name", "Category", "Contract_Value_INR",
                        "Payment_Delay_Days", "Risk_Score", "Last_Audit_Date", "Region"])
            w.writerow(["IV0099", "BOM Vendor", "IT", " 2,00,000.00 ", "10", "5.0", "2025-01-01", "East"])
        _write_incidents(tmp_path / "ibsh_incidents_90k.csv", rows=[])
        _write_employees(tmp_path / "ibsh_employees_5k.csv", rows=[])
        _write_summary(tmp_path / "ibsh_enterprise_summary.json")
        bundle = DataAgent(data_dir=tmp_path).load()
        assert len(bundle.vendors) >= 1
        assert bundle.vendors[0].vendor_id == "IV0099"
