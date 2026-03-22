# tests/conftest.py
import sqlite3
import sys
from pathlib import Path

import pytest

# Make backend modules importable
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

import audit as audit_module  # noqa: E402
import main as main_module    # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# ---------------------------------------------------------------------------
# Sample rows — match seed.py exactly so privacy logic is realistic
# ---------------------------------------------------------------------------

ENGINEERING_ROWS = [
    ("ENG-001", "WR-ZONE-001", "engineering", "water_main",    0.86, 3, 2027, "2024-03-15", "internal", "2024-01-01"),
    ("ENG-002", "WR-ZONE-002", "engineering", "water_main",    0.91, 2, 2025, "2024-01-10", "internal", "2024-01-01"),
    ("ENG-003", "WR-ZONE-003", "engineering", "pump_station",  0.74, 4, 2029, "2024-06-01", "internal", "2024-01-01"),
    ("ENG-004", "WR-ZONE-042", "engineering", "water_main",    0.97, 2, 2024, "2023-11-20", "internal", "2024-01-01"),
    ("ENG-005", "WR-ZONE-005", "engineering", "reservoir",     0.62, 5, 2031, "2024-08-12", "internal", "2024-01-01"),
    ("ENG-006", "WR-ZONE-006", "engineering", "water_main",    0.78, 3, 2028, "2024-05-30", "internal", "2024-01-01"),
]

PLANNING_ROWS = [
    ("PLN-001", "WR-ZONE-001", "planning", "infill",      "R4",   42,  "approved", 85.0,  "public", "2024-01-01"),
    ("PLN-002", "WR-ZONE-001", "planning", "infill",      "R4",   18,  "pending",  85.0,  "public", "2024-01-01"),
    ("PLN-003", "WR-ZONE-002", "planning", "subdivision", "R2",  120,  "approved", 35.0,  "public", "2024-01-01"),
    ("PLN-004", "WR-ZONE-042", "planning", "infill",      "MU-2", 65,  "approved", 120.0, "public", "2024-01-01"),
    ("PLN-005", "WR-ZONE-042", "planning", "infill",      "MU-2", 38,  "pending",  120.0, "public", "2024-01-01"),
    ("PLN-006", "WR-ZONE-003", "planning", "commercial",  "C1",    0,  "approved",  0.0,  "public", "2024-01-01"),
]

HEALTH_ROWS = [
    ("HLT-001", "WR-ZONE-001", "health", 0.87, 2, 58, 0.9, "confidential", "2024-01-01"),
    ("HLT-002", "WR-ZONE-002", "health", 0.72, 3, 42, 1.1, "confidential", "2024-01-01"),
    ("HLT-003", "WR-ZONE-042", "health", 0.93, 1, 71, 0.7, "confidential", "2024-01-01"),
    ("HLT-004", "WR-ZONE-005", "health", 0.61, 4, 31, 1.4, "confidential", "2024-01-01"),
    ("HLT-005", "WR-ZONE-003", "health", 0.79, 2, 49, 1.0, "confidential", "2024-01-01"),
    ("HLT-006", "WR-ZONE-006", "health", 0.68, 3, 38, 1.2, "confidential", "2024-01-01"),
]

TRANSIT_ROWS = [
    ("TRN-001", "WR-ZONE-001", "transit", "RT-7",   "Uptown Waterloo King St",    12, 3200, "high",   "public", "2024-01-01"),
    ("TRN-002", "WR-ZONE-002", "transit", "RT-200", "Fairway Station",            20, 1850, "medium", "public", "2024-01-01"),
    ("TRN-003", "WR-ZONE-042", "transit", "RT-7",   "King/Victoria Kitchener",    12, 2900, "high",   "public", "2024-01-01"),
    ("TRN-004", "WR-ZONE-005", "transit", "RT-29",  "Columbia/Fischer-Hallman",   25,  980, "low",    "public", "2024-01-01"),
    ("TRN-005", "WR-ZONE-003", "transit", "RT-12",  "University Ave",             15, 2100, "high",   "public", "2024-01-01"),
    ("TRN-006", "WR-ZONE-006", "transit", "RT-22",  "Ottawa St S",                30,  720, "low",    "public", "2024-01-01"),
]

# ---------------------------------------------------------------------------
# Fixtures: raw dicts for unit tests (privacy.py takes list[dict])
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def engineering_rows():
    cols = ["record_id", "zone_id", "department", "asset_type", "capacity_pct",
            "condition_score", "upgrade_year", "last_inspected", "sensitivity_level", "timestamp"]
    return [dict(zip(cols, r)) for r in ENGINEERING_ROWS]


@pytest.fixture(scope="session")
def planning_rows():
    cols = ["record_id", "zone_id", "department", "permit_type", "zoning_class",
            "unit_count", "status", "density_approved", "sensitivity_level", "timestamp"]
    return [dict(zip(cols, r)) for r in PLANNING_ROWS]


@pytest.fixture(scope="session")
def health_rows():
    cols = ["record_id", "zone_id", "department", "er_utilization_pct", "clinic_count",
            "vulnerability_index", "gp_ratio", "sensitivity_level", "timestamp"]
    return [dict(zip(cols, r)) for r in HEALTH_ROWS]


@pytest.fixture(scope="session")
def transit_rows():
    cols = ["record_id", "zone_id", "department", "route_id", "corridor",
            "frequency_min", "avg_ridership", "service_level", "sensitivity_level", "timestamp"]
    return [dict(zip(cols, r)) for r in TRANSIT_ROWS]


# ---------------------------------------------------------------------------
# Integration test client with isolated temp DBs
# ---------------------------------------------------------------------------

def _seed_db(db_path: Path, table: str, schema: str, rows: list[tuple]) -> None:
    c = sqlite3.connect(str(db_path))
    c.execute(schema)
    placeholders = ",".join(["?"] * len(rows[0]))
    c.executemany(f"INSERT OR REPLACE INTO {table} VALUES ({placeholders})", rows)
    c.commit()
    c.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient backed by fresh temp SQLite DBs seeded with realistic data."""
    schemas = {
        "engineering": (
            "water_capacity",
            """CREATE TABLE IF NOT EXISTS water_capacity (
                record_id TEXT PRIMARY KEY, zone_id TEXT, department TEXT,
                asset_type TEXT, capacity_pct REAL, condition_score INTEGER,
                upgrade_year INTEGER, last_inspected TEXT,
                sensitivity_level TEXT, timestamp TEXT)""",
            ENGINEERING_ROWS,
        ),
        "planning": (
            "permits",
            """CREATE TABLE IF NOT EXISTS permits (
                record_id TEXT PRIMARY KEY, zone_id TEXT, department TEXT,
                permit_type TEXT, zoning_class TEXT, unit_count INTEGER,
                status TEXT, density_approved REAL,
                sensitivity_level TEXT, timestamp TEXT)""",
            PLANNING_ROWS,
        ),
        "health": (
            "zone_health",
            """CREATE TABLE IF NOT EXISTS zone_health (
                record_id TEXT PRIMARY KEY, zone_id TEXT, department TEXT,
                er_utilization_pct REAL, clinic_count INTEGER,
                vulnerability_index INTEGER, gp_ratio REAL,
                sensitivity_level TEXT, timestamp TEXT)""",
            HEALTH_ROWS,
        ),
        "transit": (
            "routes",
            """CREATE TABLE IF NOT EXISTS routes (
                record_id TEXT PRIMARY KEY, zone_id TEXT, department TEXT,
                route_id TEXT, corridor TEXT, frequency_min INTEGER,
                avg_ridership INTEGER, service_level TEXT,
                sensitivity_level TEXT, timestamp TEXT)""",
            TRANSIT_ROWS,
        ),
    }

    new_db_map = {}
    for dept, (table, schema, rows) in schemas.items():
        db_path = tmp_path / f"{dept}.db"
        _seed_db(db_path, table, schema, rows)
        new_db_map[dept] = (str(db_path), table)

    monkeypatch.setattr(main_module, "DB_MAP", new_db_map)

    # Redirect audit DB to a temp file
    audit_db_path = tmp_path / "audit.db"

    def _mock_conn() -> sqlite3.Connection:
        c = sqlite3.connect(str(audit_db_path))
        c.execute("""CREATE TABLE IF NOT EXISTS audit_log (
            query_id TEXT PRIMARY KEY, timestamp TEXT, requester_role TEXT,
            department TEXT, zone_filter TEXT, access_level_applied TEXT,
            record_count INTEGER, suppressed INTEGER)""")
        c.commit()
        return c

    monkeypatch.setattr(audit_module, "_conn", _mock_conn)
    monkeypatch.setattr(main_module, "_conn", _mock_conn)

    return TestClient(main_module.app)
