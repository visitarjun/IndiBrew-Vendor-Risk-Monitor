# Architecture Reference

## System Summary

**5-agent stateless pipeline** → raw CSV data → CXO governance intelligence

```
vendors.csv + incidents.csv + employees.csv + summary.json
    │
    ▼
[DataAgent] → DataBundle (validated, typed)
    │
    ├──▶ [RiskAgent] → RiskReport (scores, flags, dept summaries)
    │        │
    └──▶ [TrendAgent] → TrendReport (MoM deltas, ghost notes, signal)
              │
              ├──▶ [BriefAgent] → weekly_brief.md + trend_brief.md
              │
              └──▶ [DashboardAgent] → dashboard.html (self-contained, offline)
```

## Agent Contracts

### DataBundle
```python
@dataclass
class DataBundle:
    vendors:   list[Vendor]
    incidents: list[Incident]
    employees: list[Employee]
    summary:   dict
    errors:    list[str]        # non-fatal data quality warnings
```
Immutable. RiskAgent and TrendAgent never modify it.

### RiskReport
```python
@dataclass
class RiskReport:
    high_risk_vendors:              list[VendorRisk]
    high_risk_incidents:            list[IncidentRisk]
    high_risk_employees:            list[EmployeeRisk]
    department_summaries:           dict[str, DepartmentSummary]
    total_high_risk_exposure_inr:   float
    high_risk_vendor_count:         int
    open_incidents:                 int
    total_incidents:                int
    undertrained_employee_count:    int
```

### TrendReport
```python
@dataclass
class TrendReport:
    current_window: WindowStats
    prior_window:   WindowStats
    dept_deltas:    dict[str, MoMDelta]
    type_deltas:    dict[str, MoMDelta]
    sev_deltas:     dict[str, MoMDelta]
    overall_signal: str              # DETERIORATING | WATCH | STABLE | IMPROVING
    ghost_notes:    list[str]        # Hidden pattern observations
    as_of:          date
```

## Input Data Schema

### vendors.csv
| Column | Type | Notes |
|--------|------|-------|
| Vendor_ID | str | Unique key |
| Vendor_Name | str | |
| Risk_Score | float | 0–10 |
| Contract_Value_INR | str | Indian comma format: "1,50,000.00" |
| Payment_Delay_Days | int | |
| Compliance_Status | str | "Compliant" / "Non-Compliant" / "Under Review" |

### incidents.csv
| Column | Type | Notes |
|--------|------|-------|
| Incident_ID | str | Unique key |
| Type | str | e.g. "Vendor Delay", "Policy Breach" |
| Severity | str | "Critical" / "High" / "Medium" / "Low" |
| Financial_Impact_INR | str | Indian comma format |
| Resolved | bool | True/False |
| Date_Reported | str | "15 June 2025" or ISO |
| Assigned_Dept | str | |

### employees.csv
| Column | Type | Notes |
|--------|------|-------|
| Employee_ID | str | Unique key |
| Name | str | |
| Role | str | |
| Department | str | |
| Compliance_Incidents | int | |
| Training_Completed | bool | |

## Key Design Decisions

**No pandas (core pipeline)** — stdlib only (`csv`, `json`, `datetime`).
Runs on any Python 3.10+ with zero `pip install`. Pandas is optional.

**Self-contained HTML dashboard** — all data embedded as JS literals.
No server, no API, no auth. CXO opens it from email or Slack attachment.

**Stateless agents** — explicit inputs, explicit outputs, no shared state.
Every agent is independently testable. Pipeline is trivially parallelisable.

**Notion Markdown output** — `> [!WARNING]` and `> [!NOTE]` render natively
in Notion, GitHub, and Obsidian. Zero reformatting needed.

**Explainable AI** — every flag traces to a specific data point. No black-box scores.

## CI/CD

GitHub Actions: `.github/workflows/ci.yml`
- ruff (lint)
- mypy (type check)
- pytest (unit tests)
- smoke test: `python orchestrator.py --data-dir data/sample --dry-run`
- Matrix: Python 3.10, 3.11, 3.12

Run locally: `make ci` or `make run`

## Performance

| Data Size | Pipeline Time |
|-----------|---------------|
| 50 vendors, 500 incidents, 100 employees (sample) | < 1s |
| 2,000 vendors, 90,000 incidents, 5,000 employees (full) | < 7s |
