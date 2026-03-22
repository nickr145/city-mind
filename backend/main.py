# backend/main.py
import sqlite3
import uuid

from fastapi import FastAPI, HTTPException

from audit import _conn, log_query
from catalog import CATALOG
from privacy import apply_privacy

app = FastAPI(title="CityMind Data Gateway")

DB_MAP = {
    "engineering": ("db/engineering.db", "water_capacity"),
    "planning": ("db/planning.db", "permits"),
    "health": ("db/health.db", "zone_health"),
    "transit": ("db/transit.db", "routes"),
}

# ---------------------------------------------------------------------------
# Catalog endpoints
# ---------------------------------------------------------------------------

@app.get("/catalog")
def list_catalog():
    return {"datasets": list(CATALOG.values()), "count": len(CATALOG)}


@app.get("/catalog/quality")
def catalog_quality():
    """Flag datasets that are stale (not updated in 90+ days)."""
    from datetime import datetime, timedelta
    threshold = datetime.now() - timedelta(days=90)
    stale = []
    for ds in CATALOG.values():
        updated = ds.get("last_updated", "")
        try:
            if datetime.fromisoformat(updated) < threshold:
                stale.append({"dataset_id": ds["dataset_id"], "last_updated": updated})
        except ValueError:
            stale.append({"dataset_id": ds["dataset_id"], "last_updated": "unknown"})
    return {"stale_datasets": stale, "count": len(stale)}


@app.get("/catalog/dictionary")
def catalog_dictionary():
    """Return shared field definitions (data dictionary)."""
    return {
        "shared_fields": {
            "zone_id": {"type": "string", "description": "Anonymized area code (e.g. WR-ZONE-042)", "privacy": "aggregated"},
            "department": {"type": "string", "description": "Owning department name", "privacy": "public"},
            "sensitivity_level": {"type": "enum", "values": ["public", "internal", "confidential", "restricted"], "privacy": "public"},
            "timestamp": {"type": "ISO 8601", "description": "Record creation or last update time", "privacy": "public"},
            "record_id": {"type": "UUID", "description": "Internal unique key — NEVER returned outside admin role", "privacy": "internal"},
        },
        "departments": {ds["department"]: {"fields": ds["fields"], "sensitivity": ds["sensitivity"]} for ds in CATALOG.values()},
    }


@app.get("/catalog/{dataset_id}")
def get_dataset(dataset_id: str):
    if dataset_id not in CATALOG:
        raise HTTPException(404, "Dataset not found")
    return CATALOG[dataset_id]


@app.post("/catalog/search")
def search_catalog(body: dict):
    tags = body.get("tags", [])
    dept = body.get("department")
    results = [
        d for d in CATALOG.values()
        if (not tags or any(t in d["tags"] for t in tags))
        and (not dept or d["department"] == dept)
    ]
    return {"results": results, "count": len(results)}


# ---------------------------------------------------------------------------
# Federated query endpoint (RBAC + privacy layer)
# ---------------------------------------------------------------------------

@app.post("/query")
def federated_query(body: dict):
    role = body.get("role", "analyst")
    department = body.get("department")
    zone_filter = body.get("zone_id")

    if department not in DB_MAP:
        raise HTTPException(400, f"Unknown department: {department}. Valid: {list(DB_MAP.keys())}")

    db_path, table = DB_MAP[department]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    if zone_filter:
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE zone_id = ?", (zone_filter,)
        ).fetchall()
    else:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    conn.close()

    raw = [dict(r) for r in rows]
    result = apply_privacy(raw, department, role)

    # Log every query to audit table
    log_query({
        "query_id": str(uuid.uuid4()),
        "requester_role": role,
        "department": department,
        "zone_filter": zone_filter or "all",
        "access_level_applied": result["access_level"],
        "record_count": len(result["rows"]),
        "suppressed": result["access_level"] == "suppressed",
    })

    return result


# ---------------------------------------------------------------------------
# Audit log endpoint (governance)
# ---------------------------------------------------------------------------

@app.get("/audit")
def get_audit(limit: int = 20):
    c = _conn()
    rows = c.execute(
        "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    c.close()
    cols = [
        "query_id", "timestamp", "requester_role", "department",
        "zone_filter", "access_level_applied", "record_count", "suppressed",
    ]
    return {"log": [dict(zip(cols, r)) for r in rows], "count": len(rows)}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "CityMind Data Gateway"}
