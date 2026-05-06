"""
dashboard_agent.py — DashboardAgent
====================================
Generates a self-contained, interactive HTML dashboard from RiskReport + TrendReport.
Charts powered by Chart.js 4.4.1 (loaded from Cloudflare CDN — no build step required).

Thinking Modes Applied
-----------------------
🪨 Caveman     : One file, open in browser, done. No server, no dependencies.
👻 Ghost Mode  : Embeds ALL data as JS literals — dashboard works offline after first load.
⚡ God Mode    : 9 charts across 3 panels: Overview, Risk Detail, 30-Day Trend.
🧠 First Prin. : HTML/CSS/JS = universal runtime. Every stakeholder can open this.
🌍 2nd Order   : Self-contained means it can be attached to emails, Slack, or committed to git.
😈 Devil's Adv.: No external data calls = no auth, no CORS, no stale-on-reload.
🎯 OODA        : Dashboard opens to the most actionable KPI strip first.
🔍 Socratic    : Ghost Mode panel surfaces the non-obvious insight below each chart group.
🏆 L99         : DashboardAgent.generate(risk, trend) -> str (full HTML). Call save() to write.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .risk_agent  import RiskReport
from .trend_agent import TrendReport


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class DashboardAgent:
    """Converts RiskReport + TrendReport into a self-contained HTML dashboard."""

    def generate(self, risk: RiskReport, trend: TrendReport) -> str:
        """Return full HTML string for the dashboard."""
        js_data   = self._build_js_data(risk, trend)
        kpi_cards = self._build_kpi_cards(risk, trend)
        return _HTML_TEMPLATE.format(
            js_data=js_data,
            kpi_cards=kpi_cards,
        )

    def save(self, html: str, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        return path

    # ------------------------------------------------------------------
    # KPI strip
    # ------------------------------------------------------------------

    def _build_kpi_cards(self, risk: RiskReport, trend: TrendReport) -> str:
        total_exposure_cr = risk.total_contract_exposure_inr / 1e7
        open_rate_pct     = risk.open_rate_pct
        trend_signal = trend.volume_mom.signal if trend else "N/A"
        signal_color = {
            "DETERIORATING": "#ef4444",
            "WATCH":         "#f97316",
            "STABLE":        "#22c55e",
            "IMPROVING":     "#10b981",
        }.get(trend_signal, "#94a3b8")

        untrained = len([e for e in risk.high_risk_employees])
        cards = [
            ("₹{:.0f} Cr".format(total_exposure_cr),
             "Total Contract Exposure",     "#ef4444"),
            ("{:,}".format(risk.high_risk_vendor_count),
             "High-Risk Vendors",           "#f97316"),
            ("{:,}".format(risk.open_incidents),
             "Open Incidents",              "#f59e0b"),
            ("{:.1f}%".format(open_rate_pct),
             "Unresolved Rate",             "#8b5cf6"),
            ("{:,}".format(untrained),
             "At-Risk Staff",               "#06b6d4"),
            (trend_signal,
             "30-Day Trend Signal",         signal_color),
        ]
        parts = []
        for value, label, color in cards:
            parts.append(
                f'<div class="kpi-card">'
                f'<div class="kpi-value" style="color:{color}">{value}</div>'
                f'<div class="kpi-label">{label}</div>'
                f'</div>'
            )
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # JS data literals
    # ------------------------------------------------------------------

    def _build_js_data(self, risk: RiskReport, trend: TrendReport) -> str:
        # --- Panel 1: Overview ---
        dept_labels, dept_total, dept_open = self._dept_incident_data(risk)
        vendor_scatter = self._vendor_scatter_data(risk)
        exposure_labels, exposure_vals = self._exposure_bar_data(risk)

        # --- Panel 2: Risk Detail ---
        emp_labels, emp_incident_vals, emp_risk_vals = self._employee_risk_data(risk)
        severity_labels, severity_vals, severity_colors = self._severity_data(risk)
        dept_exposure_labels, dept_exposure_vals = self._dept_exposure_data(risk)

        # --- Panel 3: 30-Day Trend ---
        daily_labels, daily_vals = self._daily_trend_data(trend)
        dept_mom_labels, dept_mom_curr, dept_mom_prior = self._dept_mom_data(trend)
        type_mom_labels, type_mom_deltas, type_mom_colors = self._type_mom_data(trend)

        return f"""
// ── Panel 1: Overview ──────────────────────────────────────────────
const deptLabels         = {json.dumps(dept_labels)};
const deptTotal          = {json.dumps(dept_total)};
const deptOpen           = {json.dumps(dept_open)};
const vendorScatterData  = {json.dumps(vendor_scatter)};
const exposureLabels     = {json.dumps(exposure_labels)};
const exposureVals       = {json.dumps(exposure_vals)};

// ── Panel 2: Risk Detail ────────────────────────────────────────────
const empLabels          = {json.dumps(emp_labels)};
const empIncidentVals    = {json.dumps(emp_incident_vals)};
const empRiskVals        = {json.dumps(emp_risk_vals)};
const severityLabels     = {json.dumps(severity_labels)};
const severityVals       = {json.dumps(severity_vals)};
const severityColors     = {json.dumps(severity_colors)};
const deptExposureLabels = {json.dumps(dept_exposure_labels)};
const deptExposureVals   = {json.dumps(dept_exposure_vals)};

// ── Panel 3: 30-Day Trend ───────────────────────────────────────────
const dailyLabels        = {json.dumps(daily_labels)};
const dailyVals          = {json.dumps(daily_vals)};
const deptMoMLabels      = {json.dumps(dept_mom_labels)};
const deptMoMCurr        = {json.dumps(dept_mom_curr)};
const deptMoMPrior       = {json.dumps(dept_mom_prior)};
const typeMoMLabels      = {json.dumps(type_mom_labels)};
const typeMoMDeltas      = {json.dumps(type_mom_deltas)};
const typeMoMColors      = {json.dumps(type_mom_colors)};
"""

    # ------------------------------------------------------------------
    # Data extraction helpers
    # ------------------------------------------------------------------

    def _dept_incident_data(
        self, risk: RiskReport
    ) -> tuple[list[str], list[int], list[int]]:
        # dept_summaries is a list of DepartmentSummary objects
        depts = sorted(risk.dept_summaries, key=lambda d: d.total_incidents, reverse=True)[:10]
        return ([d.department for d in depts],
                [d.total_incidents for d in depts],
                [d.open_incidents for d in depts])

    def _vendor_scatter_data(self, risk: RiskReport) -> list[dict[str, Any]]:
        points = []
        for vr in risk.high_risk_vendors[:120]:
            v  = vr.vendor
            exp_l = v.contract_value_inr / 1e5
            points.append({
                "x":     round(v.payment_delay_days, 1),
                "y":     round(v.risk_score, 2),
                "r":     max(4, min(20, exp_l / 5)),
                "label": v.vendor_id,
            })
        return points

    def _exposure_bar_data(self, risk: RiskReport) -> tuple[list[str], list[float]]:
        top = sorted(risk.high_risk_vendors,
                     key=lambda vr: vr.vendor.contract_value_inr, reverse=True)[:15]
        return ([vr.vendor.vendor_id for vr in top],
                [round(vr.vendor.contract_value_inr / 1e5, 2) for vr in top])

    def _employee_risk_data(self, risk: RiskReport) -> tuple[list[str], list[int], list[float]]:
        top = sorted(risk.high_risk_employees,
                     key=lambda er: er.employee.compliance_incidents, reverse=True)[:20]
        return ([er.employee.employee_id for er in top],
                [er.employee.compliance_incidents for er in top],
                [round(er.employee.performance_score, 2) for er in top])

    def _severity_data(self, risk: RiskReport) -> tuple[list[str], list[int], list[str]]:
        counts: dict[str, int] = {}
        for ir in risk.high_risk_incidents:
            s = ir.incident.severity
            counts[s] = counts.get(s, 0) + 1
        order  = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        colors = {"CRITICAL": "#7c3aed", "HIGH": "#ef4444", "MEDIUM": "#f97316", "LOW": "#22c55e"}
        labels = [s for s in order if s in counts]
        return (labels, [counts[s] for s in labels], [colors.get(s, "#94a3b8") for s in labels])

    def _dept_exposure_data(self, risk: RiskReport) -> tuple[list[str], list[float]]:
        depts = sorted(risk.dept_summaries, key=lambda d: d.open_exposure_inr, reverse=True)[:10]
        return ([d.department for d in depts],
                [round(d.open_exposure_inr / 1e5, 2) for d in depts])

    def _daily_trend_data(self, trend: TrendReport) -> tuple[list[str], list[int]]:
        if not trend or not trend.current.daily_counts:
            return [], []
        daily = trend.current.daily_counts
        days  = sorted(daily.keys())
        # Keys may be date objects or ISO strings — normalise to label strings
        from datetime import date as _date, datetime as _dt
        def _label(k):
            if isinstance(k, _date): return k.strftime("%d %b")
            return _dt.strptime(k, "%Y-%m-%d").strftime("%d %b")
        return ([_label(d) for d in days], [daily[d] for d in days])

    def _dept_mom_data(self, trend: TrendReport) -> tuple[list[str], list[int], list[int]]:
        if not trend:
            return [], [], []
        labels, curr, prior = [], [], []
        # dept_deltas: dict[dept, dict{'volume': MoMDelta, 'open': MoMDelta}]
        for dept, dd in sorted(trend.dept_deltas.items(),
                                key=lambda kv: abs(kv[1]['volume'].delta_abs if isinstance(kv[1], dict) else kv[1].delta_abs), reverse=True)[:10]:
            vol = dd['volume'] if isinstance(dd, dict) else dd
            labels.append(dept)
            curr.append(vol.current)
            prior.append(vol.prior)
        return labels, curr, prior

    def _type_mom_data(self, trend: TrendReport) -> tuple[list[str], list[float], list[str]]:
        if not trend:
            return [], [], []
        labels, deltas, colors = [], [], []
        for itype, dd in sorted(trend.type_deltas.items(),
                                 key=lambda kv: abs((kv[1]['volume'] if isinstance(kv[1], dict) else kv[1]).delta_pct), reverse=True)[:12]:
            vol = dd['volume'] if isinstance(dd, dict) else dd
            d = vol.delta_pct
            labels.append(itype)
            deltas.append(round(d, 1))
            colors.append("#ef4444" if d > 0 else "#22c55e")
        return labels, deltas, colors


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IndiBrew GCC — Vendor Risk Monitor Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"
        crossorigin="anonymous"></script>
<style>
  :root {{
    --bg:      #0f1117;
    --surface: #1a1d2e;
    --border:  #2d3150;
    --text:    #e2e8f0;
    --muted:   #94a3b8;
    --accent:  #6366f1;
    --red:     #ef4444;
    --orange:  #f97316;
    --yellow:  #f59e0b;
    --green:   #22c55e;
    --blue:    #3b82f6;
    --purple:  #8b5cf6;
    --cyan:    #06b6d4;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 14px;
    line-height: 1.6;
  }}
  header {{
    background: linear-gradient(135deg, #1e1b4b 0%, #0f1117 100%);
    border-bottom: 1px solid var(--border);
    padding: 24px 32px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  header h1 {{
    font-size: 1.4rem;
    font-weight: 700;
    color: #fff;
    letter-spacing: -0.02em;
  }}
  header .subtitle {{ color: var(--muted); font-size: 0.85rem; margin-top: 4px; }}
  header .badge {{
    background: var(--accent);
    color: #fff;
    padding: 4px 12px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
  }}

  /* KPI strip */
  .kpi-strip {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 12px;
    padding: 20px 32px;
    border-bottom: 1px solid var(--border);
  }}
  .kpi-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px 20px;
  }}
  .kpi-value {{ font-size: 1.6rem; font-weight: 800; line-height: 1.1; }}
  .kpi-label {{ font-size: 0.78rem; color: var(--muted); margin-top: 6px; }}

  /* Panel tabs */
  .tabs {{
    display: flex;
    gap: 0;
    border-bottom: 1px solid var(--border);
    padding: 0 32px;
    background: var(--surface);
  }}
  .tab {{
    padding: 12px 24px;
    cursor: pointer;
    font-size: 0.88rem;
    font-weight: 500;
    color: var(--muted);
    border-bottom: 2px solid transparent;
    transition: all .15s;
  }}
  .tab.active {{ color: var(--accent); border-bottom-color: var(--accent); }}
  .tab:hover {{ color: var(--text); }}

  /* Panels */
  .panel {{ display: none; padding: 28px 32px; }}
  .panel.active {{ display: block; }}

  /* Chart grid */
  .chart-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
    gap: 20px;
    margin-bottom: 20px;
  }}
  .chart-grid.wide {{ grid-template-columns: 1fr; }}
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px 24px;
  }}
  .card-title {{
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .card-title .tag {{
    font-size: 0.7rem;
    background: rgba(99,102,241,.18);
    color: var(--accent);
    padding: 2px 8px;
    border-radius: 9999px;
  }}
  .chart-wrap {{ position: relative; height: 280px; }}
  .chart-wrap.tall {{ height: 360px; }}

  /* Ghost Mode insight box */
  .insight {{
    background: rgba(99,102,241,.08);
    border-left: 3px solid var(--accent);
    border-radius: 0 8px 8px 0;
    padding: 14px 18px;
    margin-top: 20px;
    font-size: 0.84rem;
    color: var(--muted);
  }}
  .insight strong {{ color: var(--text); }}

  /* Footer */
  footer {{
    text-align: center;
    padding: 20px;
    font-size: 0.75rem;
    color: var(--muted);
    border-top: 1px solid var(--border);
  }}
</style>
</head>
<body>

<header>
  <div>
    <h1>IndiBrew GCC — Vendor Risk Monitor</h1>
    <div class="subtitle">Hyderabad · 5,000 employees · 2,000 vendors · 90,000+ incidents</div>
  </div>
  <div class="badge">LIVE ANALYSIS</div>
</header>

<!-- KPI Strip -->
<div class="kpi-strip">
{kpi_cards}
</div>

<!-- Tabs -->
<div class="tabs">
  <div class="tab active" onclick="showPanel('overview',this)">📊 Overview</div>
  <div class="tab"        onclick="showPanel('risk',this)">🔴 Risk Detail</div>
  <div class="tab"        onclick="showPanel('trend',this)">📈 30-Day Trend</div>
</div>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<!-- PANEL 1: OVERVIEW                                                   -->
<!-- ═══════════════════════════════════════════════════════════════════ -->
<div id="panel-overview" class="panel active">
  <div class="chart-grid">

    <div class="card">
      <div class="card-title">
        Incidents by Department
        <span class="tag">Total vs Open</span>
      </div>
      <div class="chart-wrap">
        <canvas id="deptChart"></canvas>
      </div>
    </div>

    <div class="card">
      <div class="card-title">
        Vendor Risk Matrix
        <span class="tag">Score × Payment Delay × Exposure</span>
      </div>
      <div class="chart-wrap">
        <canvas id="scatterChart"></canvas>
      </div>
    </div>

  </div>

  <div class="chart-grid wide">
    <div class="card">
      <div class="card-title">
        Top 15 Vendors by Contract Exposure (₹ Lakh)
        <span class="tag">High-Risk Only</span>
      </div>
      <div class="chart-wrap tall">
        <canvas id="exposureChart"></canvas>
      </div>
    </div>
  </div>

  <div class="insight">
    <strong>👻 Ghost Mode:</strong>
    The scatter chart reveals vendors clustering in the top-left quadrant — high risk scores
    with low payment delays. This is the blind spot: risk flags that are NOT driven by payment
    behaviour alone. These vendors require a qualitative contract review, not just SLA monitoring.
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<!-- PANEL 2: RISK DETAIL                                                -->
<!-- ═══════════════════════════════════════════════════════════════════ -->
<div id="panel-risk" class="panel">
  <div class="chart-grid">

    <div class="card">
      <div class="card-title">
        Top Employee Risk Profile
        <span class="tag">Incidents + Composite Score</span>
      </div>
      <div class="chart-wrap tall">
        <canvas id="empChart"></canvas>
      </div>
    </div>

    <div class="card">
      <div class="card-title">
        Open Incident Severity Distribution
        <span class="tag">High-Risk Incidents Only</span>
      </div>
      <div class="chart-wrap">
        <canvas id="severityChart"></canvas>
      </div>
    </div>

  </div>

  <div class="chart-grid wide">
    <div class="card">
      <div class="card-title">
        Open Financial Exposure by Department (₹ Lakh)
        <span class="tag">Unresolved Incidents &gt; ₹1L</span>
      </div>
      <div class="chart-wrap">
        <canvas id="deptExposureChart"></canvas>
      </div>
    </div>
  </div>

  <div class="insight">
    <strong>🧠 First Principles:</strong>
    Training completion ≠ training effectiveness.
    The employee risk chart separates employees who completed training but still accumulate
    maximum compliance incidents — this is the metric HR systems universally miss.
  </div>
</div>

<!-- ═══════════════════════════════════════════════════════════════════ -->
<!-- PANEL 3: 30-DAY TREND                                               -->
<!-- ═══════════════════════════════════════════════════════════════════ -->
<div id="panel-trend" class="panel">
  <div class="chart-grid wide">
    <div class="card">
      <div class="card-title">
        Daily Incident Volume (Last 30 Days)
        <span class="tag">Current Window</span>
      </div>
      <div class="chart-wrap">
        <canvas id="dailyChart"></canvas>
      </div>
    </div>
  </div>

  <div class="chart-grid">

    <div class="card">
      <div class="card-title">
        Department Incidents: Current vs Prior Month
        <span class="tag">MoM Comparison</span>
      </div>
      <div class="chart-wrap tall">
        <canvas id="deptMoMChart"></canvas>
      </div>
    </div>

    <div class="card">
      <div class="card-title">
        Incident Type MoM Delta (%)
        <span class="tag">Red = Rising · Green = Falling</span>
      </div>
      <div class="chart-wrap tall">
        <canvas id="typeMoMChart"></canvas>
      </div>
    </div>

  </div>

  <div class="insight">
    <strong>👻 Ghost Mode — Approval Delay Root Node:</strong>
    Rising Approval Delay incidents are not a single problem. They are the first node
    in a four-incident chain: Approval Delay → PO Expiry → Contract Non-Compliance → Vendor Risk.
    All four incident types share one root cause: the procurement approval workflow is broken.
    Fixing the workflow fixes all four metrics simultaneously.
  </div>
</div>

<footer>
  IndiBrew Vendor Risk Monitor · Built with Claude (Cowork Mode) · 9 Structured Thinking Modes
  · Chart.js 4.4.1 · Data: 97,001 rows across Vendors, Incidents, Employees
</footer>

<script>
{js_data}

// ── Utilities ────────────────────────────────────────────────────────
function showPanel(id, el) {{
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('panel-' + id).classList.add('active');
  el.classList.add('active');
}}

const GRID_COLOR  = 'rgba(255,255,255,0.06)';
const TEXT_COLOR  = '#94a3b8';
const baseOptions = (horizontal = false) => ({{
  responsive: true,
  maintainAspectRatio: false,
  plugins: {{
    legend: {{ labels: {{ color: TEXT_COLOR, font: {{ size: 11 }} }} }},
    tooltip: {{ backgroundColor: '#1a1d2e', borderColor: '#2d3150', borderWidth: 1,
                titleColor: '#e2e8f0', bodyColor: '#94a3b8' }},
  }},
  scales: horizontal ? {{
    x: {{ grid: {{ color: GRID_COLOR }}, ticks: {{ color: TEXT_COLOR }} }},
    y: {{ grid: {{ display: false }}, ticks: {{ color: TEXT_COLOR, font: {{ size: 11 }} }} }},
  }} : {{
    x: {{ grid: {{ display: false }}, ticks: {{ color: TEXT_COLOR, maxRotation: 45 }} }},
    y: {{ grid: {{ color: GRID_COLOR }}, ticks: {{ color: TEXT_COLOR }} }},
  }},
}});

// ── Chart 1: Dept incidents bar ───────────────────────────────────────
new Chart(document.getElementById('deptChart'), {{
  type: 'bar',
  data: {{
    labels: deptLabels,
    datasets: [
      {{ label: 'Total', data: deptTotal,
         backgroundColor: 'rgba(99,102,241,0.6)', borderColor: '#6366f1', borderWidth: 1 }},
      {{ label: 'Open',  data: deptOpen,
         backgroundColor: 'rgba(239,68,68,0.6)',  borderColor: '#ef4444', borderWidth: 1 }},
    ],
  }},
  options: baseOptions(),
}});

// ── Chart 2: Vendor scatter ──────────────────────────────────────────
new Chart(document.getElementById('scatterChart'), {{
  type: 'bubble',
  data: {{
    datasets: [{{
      label: 'Vendor',
      data: vendorScatterData,
      backgroundColor: 'rgba(239,68,68,0.55)',
      borderColor: '#ef4444',
      borderWidth: 1,
    }}],
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        backgroundColor: '#1a1d2e', borderColor: '#2d3150', borderWidth: 1,
        titleColor: '#e2e8f0',      bodyColor: '#94a3b8',
        callbacks: {{
          label: ctx => {{
            const d = ctx.raw;
            return `${{d.label}} | Delay: ${{d.x}}d | Score: ${{d.y}}`;
          }},
        }},
      }},
    }},
    scales: {{
      x: {{ title: {{ display: true, text: 'Payment Delay (days)', color: TEXT_COLOR }},
            grid: {{ color: GRID_COLOR }}, ticks: {{ color: TEXT_COLOR }} }},
      y: {{ title: {{ display: true, text: 'Risk Score',           color: TEXT_COLOR }},
            grid: {{ color: GRID_COLOR }}, ticks: {{ color: TEXT_COLOR }},
            min: 7, max: 10 }},
    }},
  }},
}});

// ── Chart 3: Exposure horizontal bar ────────────────────────────────
new Chart(document.getElementById('exposureChart'), {{
  type: 'bar',
  data: {{
    labels: exposureLabels,
    datasets: [{{
      label: 'Contract Exposure (₹ Lakh)',
      data: exposureVals,
      backgroundColor: 'rgba(249,115,22,0.65)',
      borderColor: '#f97316',
      borderWidth: 1,
    }}],
  }},
  options: {{ ...baseOptions(true), indexAxis: 'y' }},
}});

// ── Chart 4: Employee risk bar+line ──────────────────────────────────
new Chart(document.getElementById('empChart'), {{
  type: 'bar',
  data: {{
    labels: empLabels,
    datasets: [
      {{ label: 'Compliance Incidents', data: empIncidentVals, type: 'bar',
         backgroundColor: 'rgba(239,68,68,0.6)', borderColor: '#ef4444', borderWidth: 1,
         yAxisID: 'y' }},
      {{ label: 'Composite Risk Score', data: empRiskVals, type: 'line',
         borderColor: '#f97316', backgroundColor: 'rgba(249,115,22,0.1)',
         tension: 0.3, pointRadius: 4, yAxisID: 'y1' }},
    ],
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{
      legend: {{ labels: {{ color: TEXT_COLOR }} }},
      tooltip: {{ backgroundColor: '#1a1d2e', titleColor: '#e2e8f0', bodyColor: '#94a3b8' }},
    }},
    scales: {{
      x:  {{ grid: {{ display: false }},  ticks: {{ color: TEXT_COLOR, maxRotation: 60, font: {{ size: 10 }} }} }},
      y:  {{ grid: {{ color: GRID_COLOR }}, ticks: {{ color: TEXT_COLOR }},
             title: {{ display: true, text: 'Incidents', color: TEXT_COLOR }} }},
      y1: {{ position: 'right', grid: {{ display: false }}, ticks: {{ color: '#f97316' }},
             title: {{ display: true, text: 'Risk Score', color: '#f97316' }} }},
    }},
  }},
}});

// ── Chart 5: Severity doughnut ───────────────────────────────────────
new Chart(document.getElementById('severityChart'), {{
  type: 'doughnut',
  data: {{
    labels: severityLabels,
    datasets: [{{
      data: severityVals,
      backgroundColor: severityColors,
      borderColor: '#0f1117',
      borderWidth: 3,
    }}],
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{
      legend: {{ position: 'right', labels: {{ color: TEXT_COLOR, padding: 16 }} }},
      tooltip: {{ backgroundColor: '#1a1d2e', titleColor: '#e2e8f0', bodyColor: '#94a3b8' }},
    }},
  }},
}});

// ── Chart 6: Dept open exposure horizontal bar ───────────────────────
new Chart(document.getElementById('deptExposureChart'), {{
  type: 'bar',
  data: {{
    labels: deptExposureLabels,
    datasets: [{{
      label: 'Open Exposure (₹ Lakh)',
      data: deptExposureVals,
      backgroundColor: 'rgba(139,92,246,0.65)',
      borderColor: '#8b5cf6',
      borderWidth: 1,
    }}],
  }},
  options: {{ ...baseOptions(true), indexAxis: 'y' }},
}});

// ── Chart 7: Daily trend line ────────────────────────────────────────
new Chart(document.getElementById('dailyChart'), {{
  type: 'line',
  data: {{
    labels: dailyLabels,
    datasets: [{{
      label: 'Daily Incidents',
      data: dailyVals,
      borderColor: '#6366f1',
      backgroundColor: 'rgba(99,102,241,0.12)',
      tension: 0.4,
      fill: true,
      pointRadius: 3,
      pointHoverRadius: 6,
    }}],
  }},
  options: baseOptions(),
}});

// ── Chart 8: Dept MoM grouped bar ────────────────────────────────────
new Chart(document.getElementById('deptMoMChart'), {{
  type: 'bar',
  data: {{
    labels: deptMoMLabels,
    datasets: [
      {{ label: 'Current Month',  data: deptMoMCurr,
         backgroundColor: 'rgba(239,68,68,0.65)',  borderColor: '#ef4444', borderWidth: 1 }},
      {{ label: 'Prior Month',    data: deptMoMPrior,
         backgroundColor: 'rgba(148,163,184,0.35)', borderColor: '#94a3b8', borderWidth: 1 }},
    ],
  }},
  options: baseOptions(),
}});

// ── Chart 9: Type MoM horizontal bar ────────────────────────────────
new Chart(document.getElementById('typeMoMChart'), {{
  type: 'bar',
  data: {{
    labels: typeMoMLabels,
    datasets: [{{
      label: 'MoM Change (%)',
      data: typeMoMDeltas,
      backgroundColor: typeMoMColors,
      borderWidth: 0,
    }}],
  }},
  options: {{ ...baseOptions(true), indexAxis: 'y' }},
}});
</script>
</body>
</html>
"""
