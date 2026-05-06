"""
TrendAgent
----------
Responsibility: Compute rolling 30-day window metrics and MoM (month-on-month)
comparisons for all incident dimensions.

First Principles:
  A 30-day window is only meaningful if compared against a matched prior window.
  Both windows must be the same length. Normalise to daily rates before comparing
  to avoid artefacts from month-length differences (28 vs 31 days).

Second Order Thinking:
  A falling incident count is NOT always good (under-reporting).
  A rising open rate on flat volume signals process degradation, not volume growth.
  A flat Training Overdue count signals the root cause factory is running unchanged.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from .data_agent import DataBundle, Incident

logger = logging.getLogger(__name__)


@dataclass
class WindowStats:
    """Metrics for a single 30-day window."""
    start:          date
    end:            date
    total:          int
    open_count:     int
    open_rate_pct:  float
    fin_impact_inr: float
    open_fin_inr:   float
    high_count:     int
    daily_avg:      float
    by_dept:        dict[str, dict[str, Any]] = field(default_factory=dict)
    by_type:        dict[str, int]             = field(default_factory=dict)
    by_severity:    dict[str, int]             = field(default_factory=dict)
    daily_counts:   dict[str, int]             = field(default_factory=dict)   # ISO date → count


@dataclass
class MoMDelta:
    """Month-on-month delta for a single metric."""
    current:    float
    prior:      float
    delta_abs:  float
    delta_pct:  float
    direction:  str    # "UP" | "DOWN" | "FLAT"
    signal:     str    # "IMPROVING" | "DETERIORATING" | "STABLE" | "WATCH"


@dataclass
class TrendReport:
    """Full trend report passed to BriefAgent and DashboardAgent."""
    current:          WindowStats
    prior:            WindowStats
    volume_mom:       MoMDelta
    open_rate_mom:    MoMDelta
    open_fin_mom:     MoMDelta
    high_sev_mom:     MoMDelta
    dept_deltas:      dict[str, dict[str, MoMDelta]]  # dept → {volume, open}
    type_deltas:      dict[str, MoMDelta]
    ghost_flags:      list[str]   # hidden-reality observations
    top_open_incidents: list[Incident]


class TrendAgent:
    """
    Computes 30-day rolling metrics with MoM comparisons.

    Usage
    -----
    >>> agent = TrendAgent()
    >>> report = agent.analyse(bundle, as_of=date(2026, 5, 16))
    >>> print(f"Open rate trend: {report.open_rate_mom.delta_pct:+.1f}%")
    """

    def __init__(self, window_days: int = 30, impact_threshold_inr: float = 100_000) -> None:
        self.window_days     = window_days
        self.impact_threshold = impact_threshold_inr

    def analyse(self, bundle: DataBundle, as_of: date | None = None) -> TrendReport:
        today = as_of or date.today()

        cur_end   = today
        cur_start = today - timedelta(days=self.window_days)
        pri_end   = cur_start - timedelta(days=1)
        pri_start = pri_end   - timedelta(days=self.window_days)

        logger.info(
            "TrendAgent: current %s–%s, prior %s–%s",
            cur_start, cur_end, pri_start, pri_end
        )

        current = self._window_stats(bundle.incidents, cur_start, cur_end)
        prior   = self._window_stats(bundle.incidents, pri_start, pri_end)

        dept_deltas = self._dept_deltas(current, prior)
        type_deltas = self._type_deltas(current, prior)
        ghost_flags = self._ghost_analysis(current, prior, type_deltas)

        top_open = sorted(
            [
                inc for inc in bundle.incidents
                if not inc.resolved
                and cur_start <= inc.date <= cur_end
                and inc.financial_impact_inr >= self.impact_threshold
            ],
            key=lambda x: -x.financial_impact_inr,
        )[:15]

        return TrendReport(
            current          = current,
            prior            = prior,
            volume_mom       = self._delta(current.total,          prior.total,          higher_is_bad=True),
            open_rate_mom    = self._delta(current.open_rate_pct,  prior.open_rate_pct,  higher_is_bad=True),
            open_fin_mom     = self._delta(current.open_fin_inr,   prior.open_fin_inr,   higher_is_bad=True),
            high_sev_mom     = self._delta(current.high_count,     prior.high_count,     higher_is_bad=True),
            dept_deltas      = dept_deltas,
            type_deltas      = type_deltas,
            ghost_flags      = ghost_flags,
            top_open_incidents = top_open,
        )

    # ── window builder ────────────────────────────────────────────────────────

    def _window_stats(self, incidents: list[Incident], start: date, end: date) -> WindowStats:
        by_dept:     dict[str, dict] = defaultdict(lambda: {"total": 0, "open": 0, "impact": 0.0, "open_impact": 0.0})
        by_type:     dict[str, int]  = defaultdict(int)
        by_severity: dict[str, int]  = defaultdict(int)
        daily:       dict[str, int]  = defaultdict(int)

        total, open_cnt, fin, open_fin, high = 0, 0, 0.0, 0.0, 0

        for inc in incidents:
            if not (start <= inc.date <= end):
                continue
            total += 1
            fin   += inc.financial_impact_inr
            by_dept[inc.department]["total"]  += 1
            by_dept[inc.department]["impact"] += inc.financial_impact_inr
            by_type[inc.type]     += 1
            by_severity[inc.severity] += 1
            daily[inc.date.isoformat()] += 1
            if inc.severity == "HIGH":
                high += 1
            if not inc.resolved:
                open_cnt += 1
                open_fin += inc.financial_impact_inr
                by_dept[inc.department]["open"]        += 1
                by_dept[inc.department]["open_impact"] += inc.financial_impact_inr

        days_in_window = (end - start).days + 1
        return WindowStats(
            start          = start,
            end            = end,
            total          = total,
            open_count     = open_cnt,
            open_rate_pct  = round(open_cnt / total * 100, 2) if total else 0.0,
            fin_impact_inr = round(fin, 2),
            open_fin_inr   = round(open_fin, 2),
            high_count     = high,
            daily_avg      = round(total / days_in_window, 1),
            by_dept        = dict(by_dept),
            by_type        = dict(by_type),
            by_severity    = dict(by_severity),
            daily_counts   = dict(daily),
        )

    # ── delta calculator ──────────────────────────────────────────────────────

    def _delta(self, current: float, prior: float, higher_is_bad: bool = True) -> MoMDelta:
        delta_abs = current - prior
        delta_pct = (delta_abs / prior * 100) if prior else 0.0
        direction = "UP" if delta_abs > 0 else ("DOWN" if delta_abs < 0 else "FLAT")

        if higher_is_bad:
            if delta_pct > 10:
                signal = "DETERIORATING"
            elif delta_pct > 3:
                signal = "WATCH"
            elif delta_pct < -5:
                signal = "IMPROVING"
            else:
                signal = "STABLE"
        else:
            if delta_pct < -10:
                signal = "DETERIORATING"
            elif delta_pct < -3:
                signal = "WATCH"
            elif delta_pct > 5:
                signal = "IMPROVING"
            else:
                signal = "STABLE"

        return MoMDelta(
            current=current, prior=prior,
            delta_abs=round(delta_abs, 2), delta_pct=round(delta_pct, 2),
            direction=direction, signal=signal,
        )

    # ── dept deltas ───────────────────────────────────────────────────────────

    def _dept_deltas(self, cur: WindowStats, pri: WindowStats) -> dict[str, dict[str, MoMDelta]]:
        all_depts = set(cur.by_dept) | set(pri.by_dept)
        result = {}
        for dept in all_depts:
            cd = cur.by_dept.get(dept, {"total": 0, "open": 0})
            pd = pri.by_dept.get(dept, {"total": 0, "open": 0})
            result[dept] = {
                "volume": self._delta(cd["total"], pd["total"], higher_is_bad=True),
                "open":   self._delta(cd["open"],  pd["open"],  higher_is_bad=True),
            }
        return result

    # ── type deltas ───────────────────────────────────────────────────────────

    def _type_deltas(self, cur: WindowStats, pri: WindowStats) -> dict[str, MoMDelta]:
        all_types = set(cur.by_type) | set(pri.by_type)
        return {
            t: self._delta(cur.by_type.get(t, 0), pri.by_type.get(t, 0), higher_is_bad=True)
            for t in all_types
        }

    # ── ghost mode analysis ───────────────────────────────────────────────────

    def _ghost_analysis(
        self,
        cur: WindowStats,
        pri: WindowStats,
        type_deltas: dict[str, MoMDelta],
    ) -> list[str]:
        """
        Ghost Mode: surface hidden realities that raw metrics don't reveal.
        Second Order Thinking: interpret what each trend *means*, not just what it measures.
        """
        flags = []

        # 1. Volume flat + open rising = resolution collapse
        if abs(cur.total - pri.total) / max(pri.total, 1) < 0.05:
            if (cur.open_count - pri.open_count) > 30:
                flags.append(
                    "GHOST: Volume is flat (+{:.0f}%) but open incidents rose {:+d}. "
                    "This is a resolution collapse, not a volume problem. "
                    "The incident management workflow is degrading.".format(
                        (cur.total - pri.total) / max(pri.total, 1) * 100,
                        cur.open_count - pri.open_count,
                    )
                )

        # 2. Approval Delay chain — God Mode root node detection
        approval_delta = type_deltas.get("Approval Delay")
        po_delta       = type_deltas.get("PO Expiry")
        cnc_delta      = type_deltas.get("Contract Non-Compliance")
        vendor_delta   = type_deltas.get("Vendor Risk")
        chain = [d for d in [approval_delta, po_delta, cnc_delta, vendor_delta] if d and d.delta_pct > 0]
        if len(chain) >= 3:
            flags.append(
                "GOD MODE: Approval Delay → PO Expiry → Contract Non-Compliance → Vendor Risk "
                "are ALL rising simultaneously. This is one broken approval chain expressed in four "
                "incident types. Fix approval delegation once; four metrics improve."
            )

        # 3. Late Payment falling — ambiguous signal
        late_delta = type_deltas.get("Late Payment")
        if late_delta and late_delta.delta_pct < -10:
            flags.append(
                "GHOST: Late Payment incidents fell {:.1f}%. Devil's Advocate check required — "
                "is this because payments improved, or because vendors have stopped logging complaints "
                "after repeated non-resolution? Cross-check against avg payment delay metric.".format(
                    late_delta.delta_pct
                )
            )

        # 4. Training Overdue flat = root cause factory running unchanged
        training_delta = type_deltas.get("Training Overdue")
        if training_delta and abs(training_delta.delta_pct) < 2:
            flags.append(
                "FIRST PRINCIPLES: Training Overdue incidents are flat ({}%). "
                "This type is the root cause factory for ALL other incident categories. "
                "Until Training Overdue declines, expect all downstream incident types to remain elevated.".format(
                    f"{training_delta.delta_pct:+.1f}"
                )
            )

        # 5. Dept with falling volume + rising open = under-reporting
        for dept, deltas in {}.items():  # placeholder — real analysis in BriefAgent
            pass

        # 6. ₹5L cap detection
        _cap_count = sum(
            1 for d in [cur.by_dept.get(dept, {}) for dept in cur.by_dept]
        )  # simplified — full check in DataAgent

        return flags
