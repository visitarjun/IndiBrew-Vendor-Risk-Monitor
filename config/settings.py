"""
config/settings.py — Runtime configuration
===========================================
Loads thresholds and paths from environment variables or .env file.
All values have safe defaults so the project runs out-of-the-box with
no configuration required.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    # Risk thresholds (mirror brain.md)
    vendor_risk_score_high:   float = 7.0
    vendor_delay_days_high:   int   = 15
    vendor_score_critical:    float = 9.5
    incident_min_impact_inr:  float = 100_000.0
    employee_min_incidents:   int   = 3

    # Priority departments
    priority_departments: list[str] = field(
        default_factory=lambda: ["Procurement", "Compliance", "Vendor Management"]
    )

    # Trend windows (days)
    trend_window_days: int = 30

    # Output formatting
    organisation_name: str = "IndiBrew Business Services Hyderabad GCC"
    currency_symbol:   str = "₹"

    # File paths (relative defaults)
    data_dir:   Path = Path("data/sample")
    output_dir: Path = Path("reports")

    @classmethod
    def from_env(cls) -> "Settings":
        """Override defaults with environment variables if present."""
        return cls(
            vendor_risk_score_high  = float(os.getenv("VENDOR_RISK_SCORE_HIGH",  "7.0")),
            vendor_delay_days_high  = int(os.getenv("VENDOR_DELAY_DAYS_HIGH",    "15")),
            vendor_score_critical   = float(os.getenv("VENDOR_SCORE_CRITICAL",   "9.5")),
            incident_min_impact_inr = float(os.getenv("INCIDENT_MIN_IMPACT_INR", "100000")),
            employee_min_incidents  = int(os.getenv("EMPLOYEE_MIN_INCIDENTS",    "3")),
            trend_window_days       = int(os.getenv("TREND_WINDOW_DAYS",         "30")),
            organisation_name       = os.getenv(
                "ORG_NAME", "IndiBrew Business Services Hyderabad GCC"
            ),
            data_dir   = Path(os.getenv("DATA_DIR",   "data/sample")),
            output_dir = Path(os.getenv("OUTPUT_DIR", "reports")),
        )
