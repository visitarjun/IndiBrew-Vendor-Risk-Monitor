"""
IndiBrew GCC Vendor Risk Monitor — Agent Package
-------------------------------------------------
Five-agent architecture for enterprise governance intelligence:
  DataAgent      → ingests & validates all data sources
  RiskAgent      → applies brain.md thresholds, scores vendors/people/incidents
  TrendAgent     → 30-day rolling window analysis with MoM comparison
  BriefAgent     → generates CXO-grade Notion-Markdown risk briefs
  DashboardAgent → builds self-contained HTML dashboards

All agents are stateless, independently testable, and composable via Orchestrator.
"""

from .data_agent      import DataAgent
from .risk_agent      import RiskAgent
from .trend_agent     import TrendAgent
from .brief_agent     import BriefAgent
from .dashboard_agent import DashboardAgent

__all__ = ["DataAgent", "RiskAgent", "TrendAgent", "BriefAgent", "DashboardAgent"]
__version__ = "1.0.0"
