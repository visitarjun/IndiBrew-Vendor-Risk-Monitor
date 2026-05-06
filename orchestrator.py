"""
orchestrator.py — IndiBrew Vendor Risk Monitor
================================================
Main CLI entry point. Orchestrates all five agents in sequence and writes
all output artefacts (HTML dashboard, Markdown briefs) to the output directory.

Usage
-----
    python orchestrator.py --data-dir data/sample --output-dir reports
    python orchestrator.py --data-dir /path/to/csvs --as-of 2026-05-16
    python orchestrator.py --help

Thinking Modes Applied
-----------------------
🪨 Caveman     : One command. Five agents. Done.
👻 Ghost Mode  : --as-of flag lets you backdate analysis without touching the data.
⚡ God Mode    : Fail-fast on bad data; partial results still written on non-fatal errors.
🧠 First Prin. : Orchestrator owns NO business logic — it wires agents, nothing else.
🌍 2nd Order   : Exit codes propagate to CI — a broken data file breaks the pipeline.
😈 Devil's Adv.: --dry-run flag lets you validate data loading without writing outputs.
🎯 OODA        : Observe (load) → Orient (risk+trend) → Decide (brief) → Act (dashboard+save).
🔍 Socratic    : --verbose flag surfaces agent-level timing for performance investigation.
🏆 L99         : Makefile target `make run` wraps this with sensible defaults.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime
from pathlib import Path

from agents import DataAgent, RiskAgent, TrendAgent, BriefAgent, DashboardAgent
from config.settings import Settings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="indibrew-risk-monitor",
        description="IndiBrew GCC Vendor Risk Monitor — AI governance agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python orchestrator.py --data-dir data/sample
  python orchestrator.py --data-dir /data/gcc --as-of 2026-05-16
  python orchestrator.py --data-dir data/sample --dry-run
        """,
    )
    p.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/sample"),
        help="Directory containing vendors.csv, incidents.csv, employees.csv, summary.json",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports"),
        help="Directory to write dashboard.html, weekly_brief.md, trend_brief.md",
    )
    p.add_argument(
        "--as-of",
        type=str,
        default=None,
        help="Analysis reference date ISO format YYYY-MM-DD (default: today)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Load and validate data only — do not write output files",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-agent timing and row counts",
    )
    p.add_argument(
        "--skip-trend",
        action="store_true",
        help="Skip 30-day trend analysis (faster for large datasets)",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> int:
    """
    Execute the full pipeline. Returns exit code (0 = success, 1 = error).

    Pipeline
    --------
    DataAgent → RiskAgent → TrendAgent → BriefAgent → DashboardAgent
    """
    Settings.from_env()  # validate env on startup
    t_total  = time.perf_counter()

    # ── Reference date ─────────────────────────────────────────────────────
    if args.as_of:
        try:
            as_of = datetime.strptime(args.as_of, "%Y-%m-%d").date()
        except ValueError:
            _err(f"Invalid --as-of date '{args.as_of}'. Use YYYY-MM-DD.")
            return 1
    else:
        as_of = date.today()

    _log("IndiBrew GCC Vendor Risk Monitor", bold=True)
    _log(f"Reference date : {as_of}")
    _log(f"Data directory : {args.data_dir}")
    _log(f"Output dir     : {args.output_dir}")
    _log("")

    # ── Stage 1: Load ───────────────────────────────────────────────────────
    t0 = time.perf_counter()
    _log("▶ [1/5] DataAgent — loading CSV sources …")
    try:
        bundle = DataAgent(data_dir=args.data_dir).load()
    except FileNotFoundError as exc:
        _err(f"Data file not found: {exc}")
        return 1
    except Exception as exc:
        _err(f"DataAgent failed: {exc}")
        return 1

    if bundle.errors:
        for e in bundle.errors:
            _warn(f"  Data warning: {e}")

    if args.verbose:
        _log(f"   Loaded {len(bundle.vendors):,} vendors, "
             f"{len(bundle.incidents):,} incidents, "
             f"{len(bundle.employees):,} employees "
             f"({time.perf_counter()-t0:.2f}s)")

    # ── Stage 2: Risk analysis ──────────────────────────────────────────────
    t0 = time.perf_counter()
    _log("▶ [2/5] RiskAgent — scoring vendors, incidents, employees …")
    try:
        risk_report = RiskAgent().analyse(bundle)
    except Exception as exc:
        _err(f"RiskAgent failed: {exc}")
        return 1

    if args.verbose:
        _log(f"   {risk_report.high_risk_vendor_count:,} high-risk vendors | "
             f"{risk_report.open_incidents:,} open incidents "
             f"({time.perf_counter()-t0:.2f}s)")

    # ── Stage 3: Trend analysis ─────────────────────────────────────────────
    trend_report = None
    if not args.skip_trend:
        t0 = time.perf_counter()
        _log("▶ [3/5] TrendAgent — 30-day MoM trend analysis …")
        try:
            trend_report = TrendAgent().analyse(bundle, as_of=as_of)
        except Exception as exc:
            _warn(f"TrendAgent error (non-fatal): {exc}")
            _warn("  Continuing without trend data.")

        if args.verbose and trend_report:
            _log(f"   Volume MoM signal: {trend_report.volume_mom.signal} "
                 f"({time.perf_counter()-t0:.2f}s)")
    else:
        _log("▶ [3/5] TrendAgent — skipped (--skip-trend)")

    # ── Dry-run exit ────────────────────────────────────────────────────────
    if args.dry_run:
        _log("")
        _log("✅ Dry run complete — data loaded and validated successfully.")
        _log("   Remove --dry-run to generate output files.")
        return 0

    # ── Stage 4: Generate briefs ────────────────────────────────────────────
    t0 = time.perf_counter()
    _log("▶ [4/5] BriefAgent — generating Notion Markdown briefs …")
    brief_agent = BriefAgent()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    weekly_path = args.output_dir / "IndiBrew_GCC_Weekly_Risk_Brief.md"
    trend_path  = args.output_dir / "IndiBrew_GCC_30Day_Trend_Brief.md"

    try:
        weekly_md = brief_agent.weekly_brief(risk_report, trend_report)
        brief_agent.save(weekly_md, weekly_path)
        _log(f"   Weekly brief → {weekly_path}")

        if trend_report:
            trend_md = brief_agent.trend_brief(trend_report)
            brief_agent.save(trend_md, trend_path)
            _log(f"   Trend brief  → {trend_path}")
    except Exception as exc:
        _err(f"BriefAgent failed: {exc}")
        return 1

    if args.verbose:
        _log(f"   ({time.perf_counter()-t0:.2f}s)")

    # ── Stage 5: Generate dashboard ─────────────────────────────────────────
    t0 = time.perf_counter()
    _log("▶ [5/5] DashboardAgent — generating interactive HTML dashboard …")
    dash_path = args.output_dir / "IndiBrew_GCC_Dashboard.html"

    try:
        dash_agent = DashboardAgent()
        html       = dash_agent.generate(risk_report, trend_report)
        dash_agent.save(html, dash_path)
        _log(f"   Dashboard    → {dash_path}")
    except Exception as exc:
        _err(f"DashboardAgent failed: {exc}")
        return 1

    if args.verbose:
        _log(f"   ({time.perf_counter()-t0:.2f}s)")

    # ── Summary ─────────────────────────────────────────────────────────────
    elapsed = time.perf_counter() - t_total
    _log("")
    _log("─" * 56)
    _log(f"✅ Pipeline complete in {elapsed:.1f}s", bold=True)
    _log(f"   ₹{risk_report.total_contract_exposure_inr/1e7:.0f} Cr contract exposure scanned")
    _log(f"   {risk_report.high_risk_vendor_count:,} high-risk vendors flagged")
    _log(f"   {risk_report.open_incidents:,} open incidents tracked")
    if trend_report:
        _log(f"   30-day signal: {trend_report.volume_mom.signal}")
    _log("─" * 56)
    _log(f"\nOpen dashboard: {dash_path.resolve()}")
    return 0


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def _log(msg: str, bold: bool = False) -> None:
    if bold:
        print(f"\033[1m{msg}\033[0m")
    else:
        print(msg)


def _warn(msg: str) -> None:
    print(f"\033[33m⚠  {msg}\033[0m", file=sys.stderr)


def _err(msg: str) -> None:
    print(f"\033[31m✗  {msg}\033[0m", file=sys.stderr)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(run(_parse_args()))
