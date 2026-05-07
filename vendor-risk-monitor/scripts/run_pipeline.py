"""
scripts/run_pipeline.py — Complete runnable pipeline example
=============================================================
Demonstrates how to run the full 5-agent IndiBrew Vendor Risk Monitor
pipeline programmatically (as opposed to the CLI via orchestrator.py).

Usage
-----
    python vendor-risk-monitor/scripts/run_pipeline.py
    python vendor-risk-monitor/scripts/run_pipeline.py --data-dir /path/to/csvs
    python vendor-risk-monitor/scripts/run_pipeline.py --output-dir /path/to/reports

Run from the repo root (indibrew-vendor-risk-monitor/).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure repo root is on path when running from skill folder
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from agents import DataAgent, RiskAgent, TrendAgent, BriefAgent, DashboardAgent
from config.settings import Settings


def run(data_dir: Path, output_dir: Path, verbose: bool = False) -> int:
    """
    Execute the full pipeline. Returns exit code (0 = success, 1 = error).

    Pipeline stages
    ---------------
    1. DataAgent   — Load + validate CSV files → DataBundle
    2. RiskAgent   — Score vendors/incidents/employees → RiskReport
    3. TrendAgent  — 30-day MoM trend analysis → TrendReport
    4. BriefAgent  — Generate Notion Markdown briefs
    5. DashboardAgent — Generate Chart.js HTML dashboard
    """
    settings = Settings.from_env()
    settings.data_dir = data_dir
    settings.output_dir = output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()

    # ── Stage 1: Load Data ──────────────────────────────────────────────────
    print("▶  DataAgent: loading data...")
    agent1 = DataAgent(settings)
    bundle = agent1.run(data_dir)
    if bundle.errors:
        print(f"   ⚠  Data quality warnings ({len(bundle.errors)}):")
        for err in bundle.errors[:5]:
            print(f"      {err}")
    if verbose:
        print(f"   ✓  {len(bundle.vendors)} vendors, {len(bundle.incidents)} incidents,"
              f" {len(bundle.employees)} employees  ({time.perf_counter()-t0:.2f}s)")

    # ── Stage 2: Score Risks ────────────────────────────────────────────────
    t1 = time.perf_counter()
    print("▶  RiskAgent: scoring risks...")
    risk_report = RiskAgent(settings).run(bundle)
    if verbose:
        print(f"   ✓  {risk_report.high_risk_vendor_count} high-risk vendors,"
              f" ₹{risk_report.total_high_risk_exposure_inr/1e7:.2f} Cr exposure"
              f"  ({time.perf_counter()-t1:.2f}s)")

    # ── Stage 3: Trend Analysis ─────────────────────────────────────────────
    t2 = time.perf_counter()
    print("▶  TrendAgent: analyzing 30-day trend...")
    trend_report = TrendAgent(settings).run(bundle)
    if verbose:
        print(f"   ✓  Signal: {trend_report.overall_signal}"
              f"  ({time.perf_counter()-t2:.2f}s)")
        if trend_report.ghost_notes:
            print("   👻 Ghost Mode findings:")
            for note in trend_report.ghost_notes:
                print(f"      {note}")

    # ── Stage 4: Generate Briefs ────────────────────────────────────────────
    t3 = time.perf_counter()
    print("▶  BriefAgent: generating Notion briefs...")
    BriefAgent(settings).run(risk_report, trend_report, output_dir)
    if verbose:
        print(f"   ✓  Briefs written  ({time.perf_counter()-t3:.2f}s)")

    # ── Stage 5: Generate Dashboard ────────────────────────────────────────
    t4 = time.perf_counter()
    print("▶  DashboardAgent: building HTML dashboard...")
    DashboardAgent(settings).run(risk_report, trend_report, output_dir)
    if verbose:
        print(f"   ✓  Dashboard written  ({time.perf_counter()-t4:.2f}s)")

    total = time.perf_counter() - t0
    print(f"\n✅  Pipeline complete in {total:.2f}s")
    print(f"   📄  {output_dir}/IndiBrew_GCC_Weekly_Risk_Brief.md")
    print(f"   📈  {output_dir}/IndiBrew_GCC_30Day_Trend_Brief.md")
    print(f"   🌐  {output_dir}/IndiBrew_GCC_Dashboard.html")

    # ── Print executive headline ────────────────────────────────────────────
    print("\n" + "─" * 60)
    signal_emoji = {"DETERIORATING": "🔴", "WATCH": "🟡",
                    "STABLE": "🟢", "IMPROVING": "🔵"}.get(trend_report.overall_signal, "⚪")
    print(f"{signal_emoji}  {risk_report.high_risk_vendor_count} high-risk vendors "
          f"| ₹{risk_report.total_high_risk_exposure_inr/1e7:.1f} Cr at risk "
          f"| Signal: {trend_report.overall_signal}")
    print("─" * 60)

    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="IndiBrew GCC Vendor Risk Monitor — pipeline runner",
    )
    p.add_argument("--data-dir", type=Path, default=Path("data/sample"))
    p.add_argument("--output-dir", type=Path, default=Path("reports"))
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(run(args.data_dir, args.output_dir, args.verbose))
