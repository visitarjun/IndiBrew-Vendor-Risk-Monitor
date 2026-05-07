# IndiBrew Vendor Risk Monitor — Blueprint

> **One sentence:** A 5-agent AI pipeline that reads 97,001 raw GCC records and delivers a boardroom-ready risk brief, trend analysis, and interactive dashboard — in a single command, with zero BI tooling.

---

## The Problem (First Principles)

IndiBrew Business Services runs a 5,000-person GCC in Hyderabad.  
Every week, three things are true simultaneously:

| Reality | Hidden Cost |
|---|---|
| 2,000 vendors on contract, no unified risk score | ₹32 Cr exposure is invisible until a vendor fails |
| 90,000+ compliance incidents in CSVs, unread | 226 stay open; 45% unresolved rate compounds weekly |
| 15 employees accumulating max violations despite full training | HR sees training completion, not behavioural risk |

**No BI team. No data pipeline. No pre-built dashboard.** The data existed. The insight did not.

---

## Ghost Mode — What Was Really Happening

The real problem was not *missing data* — it was *missing translation*:

```
Raw CSV → nobody reads it
Excel pivot → takes 3 days, stale by the time it's shared
BI dashboard → requires a data engineer, 2-week setup, ongoing maintenance
```

Three structural gaps drove the risk blind spot:

1. **Payment delay ≠ vendor risk.** Vendors with high risk scores and *low* payment delays were invisible — not caught by any existing SLA filter.
2. **Training completion ≠ compliance behaviour.** HR reported 100% training done; nobody reported the 15 employees still generating max incidents.
3. **Each incident type looked isolated.** Nobody connected Approval Delay → PO Expiry → Contract Non-Compliance → Vendor Risk as a single broken workflow.

---

## The Solution (God Mode)

A **stateless, 5-agent AI pipeline** that runs on raw CSVs and produces three outputs:

```
python orchestrator.py --data-dir data/sample --output-dir reports/
```

| Agent | Input | Output | Time |
|---|---|---|---|
| DataAgent | 3 CSVs + JSON | Validated DataBundle | 0.02s |
| RiskAgent | DataBundle | RiskReport (12 HIGH vendors, 226 open incidents) | 0.01s |
| TrendAgent | DataBundle | TrendReport (MoM +52.2%, DETERIORATING signal) | 0.01s |
| BriefAgent | Risk + Trend | 2 CXO Markdown briefs | 0.00s |
| DashboardAgent | All outputs | 9-chart interactive HTML dashboard | 0.00s |

**Total: 0.04 seconds. 97,001 records. 3 boardroom-ready outputs.**

---

## Why It Matters (Second Order Thinking)

**Immediate:** GCC leadership gets a weekly risk brief with named owners and 48-hour deadlines — without involving a BI team.

**Second order:** Procurement stops approving vendors reactively. The dual-breach logic (score > 7 AND delay > 15d) surfaces risk *before* contract failure.

**Third order:** When this pipeline runs weekly, trend data accumulates. The MoM signal becomes predictive. The system starts forecasting deterioration, not just reporting it.

---

## Devil's Advocate — Why This Might Fail

| Objection | Counter |
|---|---|
| "Data quality will break it" | DataAgent normalises BOM chars, Indian ₹ formats, null coercion, date variants before any scoring |
| "Thresholds are arbitrary" | Configurable via `config/settings.py` — adjustable per business context without touching agent code |
| "One-off output, not a system" | CI/CD tested on Python 3.10/3.11/3.12. Orchestrator accepts any `--data-dir`. Runs as a cron job |
| "No real-time data" | Designed for weekly batch governance. Real-time is a different problem with different infrastructure costs |
| "AI hallucination risk" | Zero LLM in the pipeline. Pure deterministic Python — every number is computed, not generated |

---

## OODA Decision Log

| Phase | What We Observed | What We Decided |
|---|---|---|
| Observe | 52.2% MoM incident volume spike | DETERIORATING signal triggered |
| Orient | Approval Delay is the root node of 4 incident types | Single workflow fix resolves 4 metrics |
| Decide | 12 vendors breach dual-threshold | Escalate to Procurement Head, freeze new POs |
| Act | 15 employees: trained but non-compliant | HR Business Partner review, 30-day watch |

---

## Technical Architecture

```
orchestrator.py
    │
    ├── DataAgent      → ibsh_vendors_2k.csv + ibsh_incidents_90k.csv + ibsh_employees_5k.csv
    │                    → DataBundle (typed, validated, immutable)
    │
    ├── RiskAgent      → DataBundle → RiskReport
    │                    dual-breach: score > 7 AND delay > 15d = HIGH
    │                    score ≥ 9.5 = CRITICAL
    │
    ├── TrendAgent     → DataBundle → TrendReport
    │                    rolling 30-day window vs prior 30-day window
    │                    ghost flag detection on anomalous dept clusters
    │
    ├── BriefAgent     → RiskReport + TrendReport → 2 Markdown briefs
    │                    9 structured thinking frameworks embedded
    │
    └── DashboardAgent → All → IndiBrew_GCC_Dashboard.html
                         9 Chart.js charts, 5 tabs, fully interactive
```

**Zero mandatory third-party dependencies.** Core pipeline uses Python stdlib only (`csv`, `json`, `datetime`).  
Optional: `pandas`, `python-dateutil`, `python-dotenv`.

---

## Outputs

| File | Audience | Key Insight |
|---|---|---|
| `IndiBrew_GCC_Weekly_Risk_Brief.md` | CEO, CFO, CPO | 12 HIGH vendors, ₹32 Cr exposure, 48-hr actions |
| `IndiBrew_GCC_30Day_Trend_Brief.md` | Risk & Audit Head | +52.2% MoM, DETERIORATING, 3 ghost anomalies |
| `IndiBrew_GCC_Dashboard.html` | All stakeholders | 9 charts, clickable, filterable, exportable to CSV |

---

## Run It

```bash
git clone https://github.com/visitarjun/IndiBrew-Vendor-Risk-Monitor
cd IndiBrew-Vendor-Risk-Monitor
pip install -r requirements.txt
python orchestrator.py --data-dir data/sample --output-dir reports/ --verbose
```

Live demo: **https://visitarjun.github.io/IndiBrew-Vendor-Risk-Monitor/**  
CI status: **https://github.com/visitarjun/IndiBrew-Vendor-Risk-Monitor/actions**

---

## Built With

- Python 3.10–3.12 · Chart.js 4.4 · GitHub Actions CI
- Claude (Cowork Mode) — 9 structured thinking frameworks
- 0 BI tools · 0 servers · 0 pre-built dashboards

*IndiBrew Vendor Risk Monitor — turning raw GCC data into governance decisions.*
