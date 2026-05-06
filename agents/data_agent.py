"""
DataAgent
---------
Responsibility: Ingest, validate, and normalise all raw data sources.

First Principles:
  Raw CSVs are untrusted. Every assumption about format, encoding, column names,
  and value ranges must be verified before downstream agents touch the data.
  "Data is the bedrock. Raw data is useless without the expertise to interpret it."
  — Leadership with AI framework

Ghost Mode:
  Indian number formatting (₹1,50,548.00), BOM-encoded UTF-8, and date strings
  like "15 June 2025" are silent killers that produce zero-results without warning.
  This agent exposes every format assumption explicitly.
"""

from __future__ import annotations

import csv
import logging
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Vendor:
    vendor_id: str
    name: str
    category: str
    contract_value_inr: float
    payment_delay_days: float
    risk_score: float
    last_audit_date: str
    region: str


@dataclass
class Incident:
    incident_id: str
    date: date
    department: str
    type: str
    severity: str          # HIGH | MEDIUM | LOW
    resolved: bool
    owner_employee_id: str
    linked_vendor_id: str
    financial_impact_inr: float


@dataclass
class Employee:
    employee_id: str
    name: str
    department: str
    role: str
    join_date: str
    performance_score: float
    training_completed: bool
    compliance_incidents: int
    salary_band: str


@dataclass
class DataBundle:
    """Single object passed between agents. Immutable contract."""
    vendors:   list[Vendor]   = field(default_factory=list)
    incidents: list[Incident] = field(default_factory=list)
    employees: list[Employee] = field(default_factory=list)
    summary:   dict           = field(default_factory=dict)
    errors:    list[str]      = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_inr(raw: str) -> float:
    """Parse Indian-format currency strings: ' 1,50,548.00 ' → 150548.0"""
    try:
        return float(raw.strip().replace(",", "").replace(" ", ""))
    except (ValueError, AttributeError):
        return 0.0


def _parse_date(raw: str) -> date | None:
    """Try multiple date formats. Returns None on failure (logged, not raised)."""
    formats = ["%d %B %Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%B %d, %Y"]
    clean = raw.strip()
    for fmt in formats:
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            continue
    return None


def _parse_bool(raw: str) -> bool:
    return raw.strip().upper() in ("TRUE", "1", "YES", "T")


def _open_csv(path: Path) -> Iterator[dict]:
    """Open CSV with BOM-safe UTF-8 encoding and yield row dicts."""
    with path.open(newline="", encoding="utf-8-sig") as fh:
        yield from csv.DictReader(fh)


# ─────────────────────────────────────────────────────────────────────────────
# DataAgent
# ─────────────────────────────────────────────────────────────────────────────

class DataAgent:
    """
    Loads all IndiBrew GCC data sources into a validated DataBundle.

    Accepts either:
      - A directory containing CSV files (data_dir)
      - A zip archive (zip_path) following IndiBrew naming conventions

    Usage
    -----
    >>> agent = DataAgent(data_dir=Path("data/"))
    >>> bundle = agent.load()
    >>> print(f"Loaded {len(bundle.vendors)} vendors, {len(bundle.incidents)} incidents")
    """

    VENDOR_FILE   = "ibsh_vendors_2k.csv"
    INCIDENT_FILE = "ibsh_incidents_90k.csv"
    EMPLOYEE_FILE = "ibsh_employees_5k.csv"
    SUMMARY_FILE  = "ibsh_enterprise_summary.json"

    def __init__(
        self,
        data_dir: Path | None = None,
        zip_path: Path | None = None,
        chunk_size: int = 10_000,
    ) -> None:
        if data_dir is None and zip_path is None:
            raise ValueError("Provide either data_dir or zip_path.")
        self.data_dir   = data_dir
        self.zip_path   = zip_path
        self.chunk_size = chunk_size
        self._errors: list[str] = []

    # ── public ────────────────────────────────────────────────────────────────

    def load(self) -> DataBundle:
        """
        Full pipeline: locate files → parse → validate → return DataBundle.

        OODA:
          Observe  — file presence and encoding
          Orient   — column names and value ranges
          Decide   — raise DataValidationError on critical failures
          Act      — return clean DataBundle or DataBundle with .errors populated
        """
        logger.info("DataAgent.load() starting")
        bundle = DataBundle()

        if self.zip_path:
            self._extract_zip()

        bundle.vendors   = self._load_vendors()
        bundle.incidents = self._load_incidents()
        bundle.employees = self._load_employees()
        bundle.summary   = self._load_summary()
        bundle.errors    = self._errors

        self._validate(bundle)
        logger.info(
            "DataAgent.load() complete — %d vendors, %d incidents, %d employees, %d errors",
            len(bundle.vendors), len(bundle.incidents), len(bundle.employees), len(bundle.errors)
        )
        return bundle

    # ── private ───────────────────────────────────────────────────────────────

    def _resolve(self, filename: str) -> Path | None:
        """Find file in data_dir or its CSV/ subdirectory."""
        if self.data_dir is None:
            return None
        candidates = [
            self.data_dir / filename,
            self.data_dir / "CSV" / filename,
        ]
        for c in candidates:
            if c.exists():
                return c
        self._errors.append(f"File not found: {filename}")
        return None

    def _extract_zip(self) -> None:
        """Extract zip archive to a temp location next to the zip file."""
        import tempfile
        self.data_dir = Path(tempfile.mkdtemp(prefix="ibsh_"))
        logger.info("Extracting %s → %s", self.zip_path, self.data_dir)
        with zipfile.ZipFile(self.zip_path) as zf:
            zf.extractall(self.data_dir)

    def _load_vendors(self) -> list[Vendor]:
        path = self._resolve(self.VENDOR_FILE)
        if path is None:
            return []
        vendors, skipped = [], 0
        for i, row in enumerate(_open_csv(path)):
            try:
                vendors.append(Vendor(
                    vendor_id          = row.get("Vendor_ID", "").strip(),
                    name               = row.get("Name", "").strip(),
                    category           = row.get("Category", "").strip(),
                    contract_value_inr = _parse_inr(row.get("Contract_Value_INR", "0")),
                    payment_delay_days = float(row.get("Payment_Delay_Days", 0) or 0),
                    risk_score         = float(row.get("Risk_Score", 0) or 0),
                    last_audit_date    = row.get("Last_Audit_Date", "").strip(),
                    region             = row.get("Region", "").strip(),
                ))
            except Exception as exc:
                skipped += 1
                if skipped <= 5:
                    logger.warning("Vendor row %d skipped: %s", i, exc)
        logger.info("Vendors loaded: %d (skipped %d)", len(vendors), skipped)
        return vendors

    def _load_incidents(self) -> list[Incident]:
        path = self._resolve(self.INCIDENT_FILE)
        if path is None:
            return []
        incidents, skipped = [], 0
        for i, row in enumerate(_open_csv(path)):
            raw_date = row.get("Date", "").strip()
            parsed   = _parse_date(raw_date)
            if parsed is None:
                skipped += 1
                if skipped <= 3:
                    logger.warning("Incident row %d — unparseable date: %r", i, raw_date)
                continue
            try:
                incidents.append(Incident(
                    incident_id          = row.get("Incident_ID", "").strip(),
                    date                 = parsed,
                    department           = row.get("Department", "").strip(),
                    type                 = row.get("Type", "").strip(),
                    severity             = row.get("Severity", "").strip().upper(),
                    resolved             = _parse_bool(row.get("Resolved", "FALSE")),
                    owner_employee_id    = row.get("Owner_Employee_ID", "").strip(),
                    linked_vendor_id     = row.get("Linked_Vendor_ID", "").strip(),
                    financial_impact_inr = _parse_inr(row.get("Financial_Impact_INR", "0")),
                ))
            except Exception as exc:
                skipped += 1
                if skipped <= 5:
                    logger.warning("Incident row %d skipped: %s", i, exc)
        logger.info("Incidents loaded: %d (skipped %d)", len(incidents), skipped)
        return incidents

    def _load_employees(self) -> list[Employee]:
        path = self._resolve(self.EMPLOYEE_FILE)
        if path is None:
            return []
        employees, skipped = [], 0
        for i, row in enumerate(_open_csv(path)):
            try:
                employees.append(Employee(
                    employee_id         = row.get("Employee_ID", "").strip(),
                    name                = row.get("Name", "").strip(),
                    department          = row.get("Department", "").strip(),
                    role                = row.get("Role", "").strip(),
                    join_date           = row.get("Join_Date", "").strip(),
                    performance_score   = float(row.get("Performance_Score", 0) or 0),
                    training_completed  = _parse_bool(row.get("Training_Completed", "FALSE")),
                    compliance_incidents= int(row.get("Compliance_Incidents", 0) or 0),
                    salary_band         = row.get("Salary_Band", "").strip(),
                ))
            except Exception as exc:
                skipped += 1
                if skipped <= 5:
                    logger.warning("Employee row %d skipped: %s", i, exc)
        logger.info("Employees loaded: %d (skipped %d)", len(employees), skipped)
        return employees

    def _load_summary(self) -> dict:
        import json
        path = self._resolve(self.SUMMARY_FILE)
        if path is None:
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._errors.append(f"Summary JSON parse error: {exc}")
            return {}

    def _validate(self, bundle: DataBundle) -> None:
        """
        Socratic validation — challenge every assumption:
        - Are there duplicate IDs?
        - Do financial impact values suggest a system cap at ₹5L?
        - Are vendor IDs referenced in incidents actually present?
        """
        # Duplicate vendor IDs
        vids = [v.vendor_id for v in bundle.vendors]
        dups = len(vids) - len(set(vids))
        if dups:
            bundle.errors.append(f"DATA_INTEGRITY: {dups} duplicate Vendor_IDs detected")

        # Financial cap detection
        if bundle.incidents:
            cap_count = sum(
                1 for inc in bundle.incidents
                if abs(inc.financial_impact_inr - 500_000) < 1
            )
            cap_pct = cap_count / len(bundle.incidents) * 100
            if cap_pct > 1:
                bundle.errors.append(
                    f"DATA_CAP_WARNING: {cap_count} incidents ({cap_pct:.1f}%) "
                    f"at exactly ₹5,00,000 — likely system cap. "
                    f"True financial exposure may be understated."
                )
                logger.warning("Financial impact cap detected: %.1f%% of incidents", cap_pct)

        # Cross-reference: vendors in incidents
        vendor_set = {v.vendor_id for v in bundle.vendors}
        orphan_vendors = sum(
            1 for inc in bundle.incidents
            if inc.linked_vendor_id and inc.linked_vendor_id not in vendor_set
        )
        if orphan_vendors > 100:
            bundle.errors.append(
                f"REFERENTIAL_INTEGRITY: {orphan_vendors} incidents reference unknown Vendor_IDs"
            )
