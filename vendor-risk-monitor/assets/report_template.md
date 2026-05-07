# IndiBrew GCC Vendor Risk Monitor — Weekly Risk Brief
**Organisation:** IndiBrew Business Services Hyderabad GCC
**Period:** {{PERIOD_START}} – {{PERIOD_END}}
**Generated:** {{GENERATED_DATE}}
**Pipeline Signal:** {{OVERALL_SIGNAL}}

---

> [!WARNING]
> **RISK STATUS: {{OVERALL_SIGNAL}}** — {{HIGH_RISK_VENDOR_COUNT}} vendors flagged,
> ₹{{EXPOSURE_CR}} Cr at risk, {{OPEN_INCIDENTS}} open incidents

---

## Executive Summary

{{EXEC_SUMMARY_SENTENCE_1}} {{EXEC_SUMMARY_SENTENCE_2}}

| KPI | Value | Change MoM |
|-----|-------|------------|
| High-Risk Vendors | {{HIGH_RISK_VENDOR_COUNT}} | {{VENDOR_MOM_DELTA}} |
| Total INR Exposure | ₹{{EXPOSURE_CR}} Cr | — |
| Open Incidents | {{OPEN_INCIDENTS}} / {{TOTAL_INCIDENTS}} | {{INCIDENT_MOM_DELTA}} |
| Undertrained Employees | {{UNDERTRAINED_COUNT}} | — |
| Overall Signal | {{OVERALL_SIGNAL}} | — |

---

## Top 10 Procurement Risks

| ID | Type | Severity | Owner Dept | INR Impact | Age (days) |
|----|------|----------|------------|------------|------------|
| {{ID_1}} | {{TYPE_1}} | {{SEV_1}} | {{DEPT_1}} | ₹{{INR_1}} | {{AGE_1}} |
| {{ID_2}} | {{TYPE_2}} | {{SEV_2}} | {{DEPT_2}} | ₹{{INR_2}} | {{AGE_2}} |
| ... | | | | | |

---

## Top 5 Employee Risks

| Employee ID | Role | Department | Compliance Incidents | Training |
|-------------|------|------------|----------------------|----------|
| {{EMP_ID_1}} | {{ROLE_1}} | {{DEPT_1}} | {{INC_1}} | ❌ Not Completed |
| ... | | | | |

---

## Department Risk Gaps

| Department | Total Incidents | Open | Open % | Exposure ₹ | Trend |
|------------|-----------------|------|--------|------------|-------|
| Procurement | {{PROC_TOTAL}} | {{PROC_OPEN}} | {{PROC_PCT}}% | ₹{{PROC_EXP}} | {{PROC_TREND}} |
| Compliance | {{COMP_TOTAL}} | {{COMP_OPEN}} | {{COMP_PCT}}% | ₹{{COMP_EXP}} | {{COMP_TREND}} |
| Vendor Management | {{VM_TOTAL}} | {{VM_OPEN}} | {{VM_PCT}}% | ₹{{VM_EXP}} | {{VM_TREND}} |

---

## 30-Day Trend Analysis

**Signal: {{OVERALL_SIGNAL}}**

Current window ({{CURR_START}} – {{CURR_END}}): {{CURR_TOTAL}} incidents
Prior window ({{PRIOR_START}} – {{PRIOR_END}}): {{PRIOR_TOTAL}} incidents
**MoM Delta: {{MOM_DELTA_PCT}}%**

{{#GHOST_NOTES}}
> [!NOTE]
> 👻 **Ghost Mode — Hidden Pattern:** {{GHOST_NOTE}}
{{/GHOST_NOTES}}

---

## Immediate Actions Required

> [!IMPORTANT]
> **Action 1 — {{ACTION_1_OWNER}}**
> {{ACTION_1_DESCRIPTION}}
> **Deadline:** {{ACTION_1_DEADLINE}} | **INR Impact if Unresolved:** ₹{{ACTION_1_INR}}

> [!IMPORTANT]
> **Action 2 — {{ACTION_2_OWNER}}**
> {{ACTION_2_DESCRIPTION}}
> **Deadline:** {{ACTION_2_DEADLINE}} | **INR Impact if Unresolved:** ₹{{ACTION_2_INR}}

> [!IMPORTANT]
> **Action 3 — {{ACTION_3_OWNER}}**
> {{ACTION_3_DESCRIPTION}}
> **Deadline:** {{ACTION_3_DEADLINE}} | **INR Impact if Unresolved:** ₹{{ACTION_3_INR}}

---

## CXO Board Questions

1. {{BOARD_QUESTION_1}}

2. {{BOARD_QUESTION_2}}

---

## Methodology

**Pipeline:** DataAgent → RiskAgent → TrendAgent → BriefAgent → DashboardAgent
**Data:** {{VENDOR_COUNT}} vendors, {{INCIDENT_COUNT}} incidents, {{EMPLOYEE_COUNT}} employees
**Thinking Modes:** Caveman · Ghost Mode · God Mode · First Principles · Second Order · Devil's Advocate · OODA · Socratic · L99

**Thresholds Applied:**
- Vendor High Risk: `risk_score > 7.0` OR `payment_delay_days > 15`
- Vendor Critical: `risk_score >= 9.5`
- Incident High Risk: `resolved = False AND financial_impact_inr > ₹1,00,000`
- Employee At Risk: `training_completed = False AND compliance_incidents > 3`

*Every finding in this brief traces to a specific data point. No black-box scores.*
