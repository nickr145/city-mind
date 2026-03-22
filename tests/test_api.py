# tests/test_api.py
# Integration tests for the FastAPI gateway.
# Uses the `client` fixture from conftest.py (temp SQLite DBs, no live server needed).

import pytest


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def test_health_check(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# POST /query — RBAC enforcement
# ---------------------------------------------------------------------------

class TestQuery:
    def test_engineer_gets_full_engineering(self, client):
        r = client.post("/query", json={"role": "engineer", "department": "engineering"})
        assert r.status_code == 200
        data = r.json()
        assert data["access_level"] == "full"
        assert len(data["rows"]) == 6

    def test_planner_gets_aggregated_engineering(self, client):
        r = client.post("/query", json={"role": "planner", "department": "engineering"})
        assert r.status_code == 200
        data = r.json()
        assert data["access_level"] == "aggregated"

    def test_analyst_denied_health(self, client):
        r = client.post("/query", json={"role": "analyst", "department": "health"})
        assert r.status_code == 200
        data = r.json()
        assert data["access_level"] == "none"
        assert data["rows"] == []

    def test_admin_gets_full_health(self, client):
        r = client.post("/query", json={"role": "admin", "department": "health"})
        assert r.status_code == 200
        data = r.json()
        assert data["access_level"] == "full"
        assert len(data["rows"]) == 6

    def test_zone_filter(self, client):
        r = client.post("/query", json={"role": "engineer", "department": "engineering",
                                        "zone_id": "WR-ZONE-042"})
        assert r.status_code == 200
        data = r.json()
        assert len(data["rows"]) == 1
        assert data["rows"][0]["zone_id"] == "WR-ZONE-042"

    def test_invalid_department_returns_400(self, client):
        r = client.post("/query", json={"role": "analyst", "department": "finance"})
        assert r.status_code == 400

    def test_record_id_never_in_response(self, client):
        """record_id must never appear in any query response."""
        for dept in ("engineering", "planning", "health", "transit"):
            r = client.post("/query", json={"role": "admin", "department": dept})
            for row in r.json().get("rows", []):
                assert "record_id" not in row, f"record_id leaked in {dept} response"


# ---------------------------------------------------------------------------
# GET /audit — governance logging
# ---------------------------------------------------------------------------

class TestAudit:
    def test_every_query_is_logged(self, client):
        """Each POST /query must write one row to the audit log."""
        # Make two distinct queries
        client.post("/query", json={"role": "engineer", "department": "engineering"})
        client.post("/query", json={"role": "analyst", "department": "transit"})

        r = client.get("/audit?limit=10")
        assert r.status_code == 200
        log = r.json()["log"]
        roles = [e["requester_role"] for e in log]
        assert "engineer" in roles
        assert "analyst" in roles

    def test_suppressed_flag_logged(self, client):
        """A suppressed query (< 5 zones) must be flagged in the audit log."""
        # Query health as planner with a zone filter → 1 zone → aggregated suppressed
        client.post("/query", json={"role": "planner", "department": "health",
                                    "zone_id": "WR-ZONE-042"})
        r = client.get("/audit?limit=5")
        suppressed_entries = [e for e in r.json()["log"] if e["suppressed"]]
        assert len(suppressed_entries) >= 1

    def test_audit_log_fields(self, client):
        """Each audit entry must contain the required governance fields."""
        client.post("/query", json={"role": "planner", "department": "planning"})
        r = client.get("/audit?limit=1")
        entry = r.json()["log"][0]
        required = {"query_id", "timestamp", "requester_role", "department",
                    "zone_filter", "access_level_applied", "record_count", "suppressed"}
        assert required.issubset(entry.keys())


# ---------------------------------------------------------------------------
# GET /download/{dept} — CSV and JSON exports
# ---------------------------------------------------------------------------

class TestDownload:
    def test_csv_download_engineer(self, client):
        r = client.get("/download/engineering?role=engineer&fmt=csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        lines = r.text.strip().splitlines()
        assert len(lines) == 7  # 1 header + 6 data rows

    def test_json_download_engineer(self, client):
        r = client.get("/download/engineering?role=engineer&fmt=json")
        assert r.status_code == 200
        assert "application/json" in r.headers["content-type"]
        data = r.json()
        assert data["access_level"] == "full"
        assert len(data["rows"]) == 6

    def test_download_denied_for_analyst_health(self, client):
        """Analyst has no access to health — download must return 403."""
        r = client.get("/download/health?role=analyst&fmt=csv")
        assert r.status_code == 403

    def test_csv_has_no_record_id(self, client):
        r = client.get("/download/engineering?role=engineer&fmt=csv")
        header_line = r.text.strip().splitlines()[0]
        assert "record_id" not in header_line


# ---------------------------------------------------------------------------
# SDD §7 Demo Query Scenarios
# ---------------------------------------------------------------------------

class TestDemoScenarios:
    """
    The three demo queries from SDD §7 — these are the actual submission demos.
    Each validates the correct RBAC output for the described scenario.
    """

    def test_demo1_planner_infrastructure_readiness(self, client):
        """
        Demo 1 (SDD §7 Q01): role=planner querying infrastructure readiness.
        Engineering → aggregated (capacity bands, not raw %).
        Planning → full.
        Transit → full.
        """
        eng = client.post("/query", json={"role": "planner", "department": "engineering"})
        pln = client.post("/query", json={"role": "planner", "department": "planning"})
        trn = client.post("/query", json={"role": "planner", "department": "transit"})

        assert eng.json()["access_level"] == "aggregated"
        assert pln.json()["access_level"] == "full"
        assert trn.json()["access_level"] == "full"

        # Planners must NOT see raw capacity_pct float on engineering rows
        for row in eng.json()["rows"]:
            assert "capacity_pct" not in row, "Raw capacity_pct leaked to planner"

    def test_demo2_health_risk_zone042(self, client):
        """
        Demo 2 (SDD §7 Q02): role=health querying WR-ZONE-042.
        Health → full (1 zone record, no suppression on full access).
        Engineering → aggregated, zone-filtered to 1 zone → suppressed (< 5 zones).
        Planning → zone_summary.
        """
        hlt = client.post("/query", json={"role": "health", "department": "health",
                                          "zone_id": "WR-ZONE-042"})
        eng = client.post("/query", json={"role": "health", "department": "engineering",
                                          "zone_id": "WR-ZONE-042"})
        pln = client.post("/query", json={"role": "health", "department": "planning",
                                          "zone_id": "WR-ZONE-042"})

        assert hlt.json()["access_level"] == "full"
        assert hlt.json()["rows"][0]["zone_id"] == "WR-ZONE-042"

        # 1 zone filtered → aggregation produces 1 zone → suppressed
        assert eng.json()["access_level"] == "suppressed"

        assert pln.json()["access_level"] == "zone_summary"
        for row in pln.json()["rows"]:
            assert set(row.keys()) == {"zone_id", "department"}

    def test_demo3_analyst_cross_dept_overview(self, client):
        """
        Demo 3 (SDD §7 Q03): role=analyst, cross-department overview.
        Engineering → anonymized (zone_id + department only).
        Planning → anonymized.
        Health → none (analyst blocked by design).
        Transit → anonymized.
        """
        eng = client.post("/query", json={"role": "analyst", "department": "engineering"})
        pln = client.post("/query", json={"role": "analyst", "department": "planning"})
        hlt = client.post("/query", json={"role": "analyst", "department": "health"})
        trn = client.post("/query", json={"role": "analyst", "department": "transit"})

        assert eng.json()["access_level"] == "anonymized"
        assert pln.json()["access_level"] == "anonymized"
        assert hlt.json()["access_level"] == "none"
        assert trn.json()["access_level"] == "anonymized"

        # Anonymized rows contain only zone_id and department
        for row in eng.json()["rows"]:
            assert set(row.keys()) == {"zone_id", "department"}

        # Planning has 4 unique zones across 6 permits
        pln_zones = {r["zone_id"] for r in pln.json()["rows"]}
        assert pln_zones == {"WR-ZONE-001", "WR-ZONE-002", "WR-ZONE-042", "WR-ZONE-003"}
