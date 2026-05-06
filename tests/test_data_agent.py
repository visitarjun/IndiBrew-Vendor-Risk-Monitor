"""
tests/test_data_agent.py
========================
Unit tests for DataAgent — covers CSV loading, INR parsing, date parsing,
BOM handling, duplicate detection, and ₹5L cap flag.
"""
from __future__ import annotations

import csv
import json
import tempfile
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
        # Non-numeric should return 0.0 gracefully
        assert _parse_inr("N/A") == 0.0

    def test_empty_returns_zero(self):
        assert _parse_inr("") == 0.0


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_dd_month_yyyy(self):
        from datetime import date
        d = _parse_date("15 June 2025")
        assert d == date(2025, 6, 15)

    def test_iso_format(self):
        from datetime import date
        d = _parse_date("2025-06-15")
        assert d == date(2025, 6, 15)

    def test_slash_format(self):
        from datetime import date
        d = _parse_date("15/06/2025")
        assert d == date(2025, 6, 15)

    def test_invalid_returns_none(self):
        assert _parse_date("not-a-date") is None

    def test_empty_returns_none(self):
        assert _parse_date("") is None

    def test_single_digit_day(self):
        from datetime import date
        d = _parse_date("5 January 2026")
        assert d == date(2026, 1, 5)


# ---------------------------------------------------------------------------
# DataAgent.load — integration tests using temp files
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_data_dir(tmp_path: Path) -> Path:
    """Create minimal valid CSV + JSON files for testing."""
    # vendors.csv
    with (tmp_path / "vendors.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Vendor_ID", "Risk_Score", "Payment_Delay_Days",
                    "Contract_Value_INR", "Category", "Active"])
        w.writerow(["IV0001", "8.5", "20", " 5,00,000.00 ", "IT Services", "True"])
        w.writerow(["IV0002", "3.2", "5",  " 1,00,000.00 ", "Consulting",  "True"])
        w.writerow(["IV0001", "8.5", "20", " 5,00,000.00 ", "IT Services", "True"])  # duplicate

    # incidents.csv
    with (tmp_path / "incidents.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Incident_ID", "Date", "Department", "Incident_Type",
                    "Severity", "Resolved", "Financial_Impact_INR",
                    "Vendor_ID", "Employee_ID"])
        w.writerow(["INC001", "1 January 2026", "Procurement", "Approval Delay",
                    "HIGH", "False", " 2,50,000.00 ", "IV0001", "EMP001"])
        w.writerow(["INC002", "15 April 2026",  "Compliance", "Audit Finding",
                    "LOW",  "True",  "   50,000.00 ", "IV0002", "EMP002"])
        # ₹5L cap test
        w.writerow(["INC003", "1 May 2026", "Legal", "Policy Violation",
                    "MEDIUM", "False", " 5,00,000.00 ", "", "EMP003"])
        w.writerow(["INC004", "2 May 2026", "Finance", "Data Quality",
                    "MEDIUM", "False", " 5,00,000.00 ", "", "EMP004"])

    # employees.csv
    with (tmp_path / "employees.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Employee_ID", "Role", "Department",
                    "Training_Completed", "Compliance_Incidents"])
        w.writerow(["EMP001", "Procurement Manager", "Procurement", "False", "4"])
        w.writerow(["EMP002", "Compliance Officer",  "Compliance",  "True",  "1"])

    # summary.json
    with (tmp_path / "summary.json").open("w") as f:
        json.dump({"organisation": "Test GCC", "as_of": "2026-05-16"}, f)

    return tmp_path


class TestDataAgent:
    def test_loads_vendors(self, sample_data_dir):
        bundle = DataAgent().load(sample_data_dir)
        assert len(bundle.vendors) >= 2

    def test_loads_incidents(self, sample_data_dir):
        bundle = DataAgent().load(sample_data_dir)
        assert len(bundle.incidents) >= 2

    def test_loads_employees(self, sample_data_dir):
        bundle = DataAgent().load(sample_data_dir)
        assert len(bundle.employees) == 2

    def test_duplicate_vendor_warning(self, sample_data_dir):
        bundle = DataAgent().load(sample_data_dir)
        dup_warnings = [e for e in bundle.errors if "duplicate" in e.lower()]
        assert len(dup_warnings) > 0, "Expected duplicate vendor warning"

    def test_five_lakh_cap_flag(self, sample_data_dir):
        bundle = DataAgent().load(sample_data_dir)
        cap_warnings = [e for e in bundle.errors if "5,00,000" in e or "500000" in e]
        assert len(cap_warnings) > 0, "Expected ₹5L cap warning"

    def test_vendor_risk_score_parsed(self, sample_data_dir):
        bundle = DataAgent().load(sample_data_dir)
        high_risk = [v for v in bundle.vendors if v.risk_score > 7]
        assert len(high_risk) >= 1

    def test_incident_resolved_false(self, sample_data_dir):
        bundle = DataAgent().load(sample_data_dir)
        open_inc = [i for i in bundle.incidents if not i.resolved]
        assert len(open_inc) >= 1

    def test_employee_training_false(self, sample_data_dir):
        bundle = DataAgent().load(sample_data_dir)
        untrained = [e for e in bundle.employees if not e.training_completed]
        assert len(untrained) == 1

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            DataAgent().load(tmp_path / "nonexistent")

    def test_bom_encoding(self, tmp_path):
        """BOM-prefixed CSV should parse without \\ufeff in field names."""
        with (tmp_path / "vendors.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Vendor_ID", "Risk_Score", "Payment_Delay_Days",
                        "Contract_Value_INR", "Category", "Active"])
            w.writerow(["IV0099", "5.0", "10", " 2,00,000.00 ", "IT", "True"])
        (tmp_path / "incidents.csv").write_text(
            "Incident_ID,Date,Department,Incident_Type,Severity,Resolved,"
            "Financial_Impact_INR,Vendor_ID,Employee_ID\n"
        )
        (tmp_path / "employees.csv").write_text(
            "Employee_ID,Role,Department,Training_Completed,Compliance_Incidents\n"
        )
        (tmp_path / "summary.json").write_text('{"organisation":"Test"}')
        bundle = DataAgent().load(tmp_path)
        assert bundle.vendors[0].vendor_id == "IV0099"
