"""
Integration tests for main.py API endpoints.
Uses FastAPI TestClient with a temporary SQLite database.
"""
import sys
import os
import sqlite3
import tempfile
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from fastapi.testclient import TestClient

# ── Temp DB fixture ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def test_db():
    """Create a temporary SQLite database with realistic test data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS building_permits (
            permit_no TEXT PRIMARY KEY,
            permit_type TEXT,
            permit_status TEXT,
            work_type TEXT,
            sub_work_type TEXT,
            application_date TEXT,
            issue_date TEXT,
            issue_year REAL,
            construction_value REAL,
            permit_description TEXT,
            folder_name TEXT,
            owners TEXT,
            applicant TEXT,
            contractor TEXT,
            contractor_contact TEXT,
            roll_no TEXT,
            legal_description TEXT,
            parcel_id TEXT,
            folder_rsn TEXT,
            source_id TEXT DEFAULT 'kitchener',
            synced_at TEXT DEFAULT '2026-01-01T00:00:00'
        );
        CREATE TABLE IF NOT EXISTS water_mains (
            watmain_id TEXT PRIMARY KEY,
            status TEXT,
            pressure_zone TEXT,
            pipe_size REAL,
            material TEXT,
            criticality REAL,
            source_id TEXT DEFAULT 'kitchener',
            synced_at TEXT DEFAULT '2026-01-01T00:00:00'
        );
        CREATE TABLE IF NOT EXISTS bus_stops (
            stop_id TEXT PRIMARY KEY,
            street TEXT,
            crossstreet TEXT,
            municipality TEXT,
            ixpress TEXT,
            status TEXT,
            source_id TEXT DEFAULT 'kitchener',
            synced_at TEXT DEFAULT '2026-01-01T00:00:00'
        );
    """)

    # Insert 20 planning rows across different types
    for i in range(20):
        conn.execute("""
            INSERT INTO building_permits
            (permit_no, permit_type, permit_status, work_type, issue_year,
             construction_value, issue_date, owners, applicant, contractor,
             contractor_contact, roll_no, legal_description, parcel_id, folder_rsn)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"24-{i:06d}",
            ["Residential Building (House)", "Plumbing", "Non-Residential Alteration"][i % 3],
            "Issued",
            "New Construction",
            2024.0,
            100000.0 + i * 5000,
            "2024-06-01",
            f"Owner {i}", f"Applicant {i}", f"Contractor {i}",
            "555-0100", f"ROLL{i}", f"LOT {i}", f"PARCEL{i}", f"RSN{i}",
        ))

    # Insert 20 engineering rows across different pressure zones
    zones = ["KIT 1", "KIT 2E", "KIT 4", "BRIDGEPORT", "CAM 1"]
    for i in range(20):
        conn.execute("""
            INSERT INTO water_mains (watmain_id, status, pressure_zone, pipe_size, material, criticality)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (f"WM{i:04d}", "ACTIVE", zones[i % len(zones)], 150.0 + i * 10, "PVC", float(i % 5 + 1)))

    # Insert 20 transit rows
    munis = ["Kitchener", "Waterloo", "Cambridge"]
    for i in range(20):
        conn.execute("""
            INSERT INTO bus_stops (stop_id, street, crossstreet, municipality, ixpress, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (f"STOP{i:04d}", "King St", f"Ave {i}", munis[i % 3], "Y" if i % 5 == 0 else "N", "Active"))

    conn.commit()
    conn.close()
    yield db_path
    os.unlink(db_path)


@pytest.fixture(scope="module")
def client(test_db):
    """FastAPI test client with patched DB_MAP pointing to test DB."""
    import main
    original_db_map = dict(main.DB_MAP)
    main.DB_MAP["planning"]    = (test_db, "building_permits")
    main.DB_MAP["engineering"] = (test_db, "water_mains")
    main.DB_MAP["transit"]     = (test_db, "bus_stops")

    with TestClient(main.app) as c:
        yield c

    main.DB_MAP.clear()
    main.DB_MAP.update(original_db_map)


# ── Health ────────────────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Version header ────────────────────────────────────────────────────────────

def test_version_header_on_health(client):
    r = client.get("/health")
    assert r.headers.get("x-citymind-version") == "1.0"


def test_version_header_on_catalog(client):
    r = client.get("/catalog")
    assert r.headers.get("x-citymind-version") == "1.0"


# ── Catalog ───────────────────────────────────────────────────────────────────

def test_catalog_returns_datasets(client):
    r = client.get("/catalog")
    assert r.status_code == 200
    data = r.json()
    assert "datasets" in data
    assert data["count"] >= 1


def test_catalog_search_by_query(client):
    r = client.post("/catalog/search", json={"query": "permits"})
    assert r.status_code == 200
    results = r.json()["results"]
    assert any("permit" in d["name"].lower() for d in results)


def test_catalog_search_by_department(client):
    r = client.post("/catalog/search", json={"department": "transit"})
    assert r.status_code == 200
    results = r.json()["results"]
    for d in results:
        assert d["department"] == "transit"


def test_catalog_quality_returns_datasets(client):
    r = client.get("/catalog/quality")
    assert r.status_code == 200
    data = r.json()
    assert "datasets" in data
    for ds in data["datasets"]:
        assert "quality_score" in ds
        assert "field_null_pct" in ds
        assert 0 <= ds["quality_score"] <= 100


# ── /query endpoint ───────────────────────────────────────────────────────────

def test_query_unknown_department_returns_400(client):
    r = client.post("/query", json={"role": "admin", "department": "health"})
    assert r.status_code == 400


def test_query_admin_planning_returns_full(client):
    r = client.post("/query", json={"role": "admin", "department": "planning", "limit": 5})
    assert r.status_code == 200
    data = r.json()
    assert data["access_level"] == "full"
    assert len(data["rows"]) > 0
    # PII should be present for full access
    assert "owners" in data["rows"][0]


def test_query_analyst_planning_strips_pii(client):
    r = client.post("/query", json={"role": "analyst", "department": "planning", "limit": 20})
    assert r.status_code == 200
    data = r.json()
    # analyst gets read access to planning — PII stripped
    assert data["access_level"] in ("read", "suppressed")
    if data["access_level"] == "read":
        for row in data["rows"]:
            assert "owners" not in row
            assert "applicant" not in row


def test_query_analyst_engineering_anonymized_or_suppressed(client):
    r = client.post("/query", json={"role": "analyst", "department": "engineering", "limit": 20})
    assert r.status_code == 200
    data = r.json()
    assert data["access_level"] in ("anonymized", "suppressed")


def test_query_planner_engineering_aggregated(client):
    r = client.post("/query", json={"role": "planner", "department": "engineering", "limit": 20})
    assert r.status_code == 200
    data = r.json()
    assert data["access_level"] in ("aggregated", "suppressed")
    if data["access_level"] == "aggregated":
        for row in data["rows"]:
            assert "pressure_zone" in row
            assert "record_count" in row


def test_query_sql_injection_rejected(client):
    """Filter field not in whitelist should be silently ignored."""
    r = client.post("/query", json={
        "role": "admin",
        "department": "planning",
        "filters": {"'; DROP TABLE building_permits; --": "value"},
        "limit": 5,
    })
    assert r.status_code == 200
    # Injection attempt is silently ignored (field not in ALLOWED_FILTERS)
    assert "rows" in r.json()


def test_query_filter_permit_type(client):
    r = client.post("/query", json={
        "role": "admin",
        "department": "planning",
        "filters": {"permit_type": "Plumbing"},
        "limit": 50,
    })
    assert r.status_code == 200
    data = r.json()
    if data["access_level"] == "full" and data["rows"]:
        for row in data["rows"]:
            assert row["permit_type"] == "Plumbing"


def test_query_as_of_filters_by_date(client):
    r = client.post("/query", json={
        "role": "admin",
        "department": "planning",
        "as_of": "2024-01-01",
        "limit": 50,
    })
    assert r.status_code == 200
    data = r.json()
    # All rows should have issue_date <= 2024-01-01 (test data is 2024-06-01, so expect 0)
    if data["access_level"] == "full":
        for row in data["rows"]:
            assert row.get("issue_date", "9999") <= "2024-01-01"


def test_query_geojson_format(client):
    r = client.post("/query", json={
        "role": "admin",
        "department": "transit",
        "fmt": "geojson",
        "limit": 5,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["type"] == "FeatureCollection"
    assert "features" in data
    assert "access_level" in data


# ── /query/cross endpoint ────────────────────────────────────────────────────

def test_cross_query_returns_all_depts(client):
    r = client.post("/query/cross", json={"role": "admin", "limit": 10})
    assert r.status_code == 200
    data = r.json()
    assert "departments" in data
    for dept in ("planning", "engineering", "transit"):
        assert dept in data["departments"]


def test_cross_query_respects_role(client):
    r = client.post("/query/cross", json={"role": "planner", "limit": 10})
    assert r.status_code == 200
    depts = r.json()["departments"]
    # Planner gets full planning, aggregated engineering, read transit
    assert depts["planning"]["access_level"] == "full"
    assert depts["engineering"]["access_level"] in ("aggregated", "suppressed")
    assert depts["transit"]["access_level"] == "read"


# ── /download endpoint ────────────────────────────────────────────────────────

def test_download_csv(client):
    r = client.get("/download/planning?role=admin&fmt=csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]


def test_download_json(client):
    r = client.get("/download/planning?role=admin&fmt=json")
    assert r.status_code == 200
    data = r.json()
    assert "rows" in data
    assert "access_level" in data


def test_download_denied_for_no_access(client):
    # There's no role that has no access to all depts, but we can check suppressed path
    # Use a role that returns 'none' for a non-existent dept
    r = client.get("/download/nonexistent?role=admin")
    assert r.status_code in (400, 422, 404)


# ── Audit log ─────────────────────────────────────────────────────────────────

def test_audit_log_returns_entries(client):
    # Run a query first to ensure audit entries exist
    client.post("/query", json={"role": "admin", "department": "transit", "limit": 5})
    r = client.get("/audit?limit=10")
    assert r.status_code == 200
    data = r.json()
    assert "log" in data
    assert isinstance(data["log"], list)


def test_audit_log_has_expected_fields(client):
    client.post("/query", json={"role": "engineer", "department": "planning", "limit": 5})
    r = client.get("/audit?limit=5")
    assert r.status_code == 200
    log = r.json()["log"]
    if log:
        entry = log[0]
        for field in ("query_id", "timestamp", "requester_role", "department",
                      "access_level_applied", "record_count"):
            assert field in entry, f"Missing field: {field}"
