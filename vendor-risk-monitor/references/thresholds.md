# Risk Thresholds Reference

## Default Thresholds

| Signal | Field(s) | Condition | Priority | Env Override |
|--------|----------|-----------|----------|--------------|
| Vendor: High Risk | `risk_score` | `> 7.0` | P1 | `VENDOR_RISK_SCORE_HIGH` |
| Vendor: High Risk | `payment_delay_days` | `> 15` | P1 | `VENDOR_DELAY_DAYS_HIGH` |
| Vendor: Critical | `risk_score` | `>= 9.5` | P0 | `VENDOR_SCORE_CRITICAL` |
| Incident: High Risk | `resolved` + `financial_impact_inr` | `False AND > ₹1,00,000` | P1 | `INCIDENT_MIN_IMPACT_INR` |
| Employee: At Risk | `training_completed` + `compliance_incidents` | `False AND > 3` | P1 | `EMPLOYEE_MIN_INCIDENTS` |
| Vendor Anomaly | `risk_score` + `payment_delay_days` | `>= 9.5 AND < 10` | FLAG | — |
| Data Cap Flag | `financial_impact_inr` | `> 1% at exactly ₹5,00,000` | WARN | — |

## Trend Signal Classification

Applied to MoM delta percentage (current 30-day vs prior 30-day):

| Condition (higher_is_bad=True) | Signal | Action |
|--------------------------------|--------|--------|
| delta_pct > +15% | DETERIORATING 🔴 | Escalate to CXO immediately |
| delta_pct > +5% | WATCH 🟡 | Review in next governance cycle |
| abs(delta_pct) ≤ 5% | STABLE 🟢 | Monitor — no action required |
| delta_pct < -5% | IMPROVING 🔵 | Acknowledge in board update |

## Overriding Thresholds

### Via Environment Variables (recommended for CI/CD)

```bash
export VENDOR_RISK_SCORE_HIGH=6.0      # Lower = stricter vendor screening
export VENDOR_SCORE_CRITICAL=8.5       # Lower = more critical vendors flagged
export VENDOR_DELAY_DAYS_HIGH=10       # Lower = flag earlier payment delays
export INCIDENT_MIN_IMPACT_INR=50000   # Lower = surface more incidents
export EMPLOYEE_MIN_INCIDENTS=2        # Lower = flag more employees
export TREND_WINDOW_DAYS=14            # Shorter window for faster signal
```

### Via .env File

Copy `.env.example` to `.env` and edit:
```
VENDOR_RISK_SCORE_HIGH=6.0
VENDOR_SCORE_CRITICAL=8.5
```

### Via settings.py (for code-based override)

```python
from config.settings import Settings

settings = Settings(
    vendor_risk_score_high=6.0,
    vendor_score_critical=8.5,
    vendor_delay_days_high=10,
)
```

## Priority Department Configuration

Default priority departments (appear first in all outputs):
1. Procurement
2. Compliance  
3. Vendor Management

Override via `Settings(priority_departments=["Finance", "Legal", "Operations"])`.

## INR Parsing Notes

Source CSV uses Indian comma grouping: `"1,50,548.00"` → `150548.0`

Non-numeric values (`"N/A"`, empty strings) return `0.0` gracefully — always check
`DataBundle.errors` for data quality warnings before acting on exposure numbers.
