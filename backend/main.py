# backend/main.py
import csv
import io
import sqlite3
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse

from audit import _conn, log_query
from catalog import CATALOG
from privacy import apply_privacy

app = FastAPI(title="CityMind Data Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

REAL_DB = "db/opendata_replica.db"

DB_MAP = {
    "planning":    (REAL_DB, "building_permits"),
    "engineering": (REAL_DB, "water_mains"),
    "transit":     (REAL_DB, "bus_stops"),
}

# Whitelisted filter fields per department (prevents SQL injection)
ALLOWED_FILTERS = {
    "planning":    {"permit_type", "permit_status", "work_type", "issue_year", "sub_work_type"},
    "engineering": {"pressure_zone", "material", "status"},
    "transit":     {"municipality", "status", "ixpress"},
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
            "permit_no": {"type": "string", "description": "Unique permit number (e.g. 24-100432)", "privacy": "public"},
            "watmain_id": {"type": "string", "description": "Unique water main asset ID", "privacy": "internal"},
            "stop_id": {"type": "string", "description": "Unique GRT bus stop ID", "privacy": "public"},
            "source_id": {"type": "string", "description": "Origin data source (e.g. kitchener)", "privacy": "internal"},
            "synced_at": {"type": "ISO 8601", "description": "Timestamp when record was last synced from ArcGIS", "privacy": "internal"},
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
    filters = body.get("filters", {})
    limit = min(int(body.get("limit", 200)), 2000)

    if department not in DB_MAP:
        raise HTTPException(400, f"Unknown department: {department}. Valid: {list(DB_MAP.keys())}")

    db_path, table = DB_MAP[department]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Build WHERE clause from whitelisted filters only
    allowed = ALLOWED_FILTERS.get(department, set())
    clauses, params = [], []
    for field, value in filters.items():
        if field in allowed and value not in (None, ""):
            clauses.append(f"{field} = ?")
            params.append(value)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(f"SELECT * FROM {table} {where} LIMIT ?", params + [limit]).fetchall()
    conn.close()

    raw = [dict(r) for r in rows]
    result = apply_privacy(raw, department, role)

    filter_desc = ", ".join(f"{k}={v}" for k, v in filters.items() if v) or "all"
    log_query({
        "query_id": str(uuid.uuid4()),
        "requester_role": role,
        "department": department,
        "zone_filter": filter_desc,
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
# Download endpoint — RBAC-filtered CSV or JSON
# ---------------------------------------------------------------------------

def _fetch_rbac_rows(department: str, role: str, filters: dict = None, limit: int = 500):
    """Shared helper: fetch and privacy-filter rows for a department."""
    if department not in DB_MAP:
        raise HTTPException(400, f"Unknown department: {department}. Valid: {list(DB_MAP.keys())}")
    db_path, table = DB_MAP[department]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    allowed = ALLOWED_FILTERS.get(department, set())
    clauses, params = [], []
    for field, value in (filters or {}).items():
        if field in allowed and value not in (None, ""):
            clauses.append(f"{field} = ?")
            params.append(value)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(f"SELECT * FROM {table} {where} LIMIT ?", params + [limit]).fetchall()
    conn.close()
    raw = [dict(r) for r in rows]
    return apply_privacy(raw, department, role)


@app.get("/download/{department}")
def download_data(department: str, role: str = "analyst", fmt: str = "csv"):
    """Return RBAC-filtered department data as a downloadable CSV or JSON file."""
    result = _fetch_rbac_rows(department, role)
    access = result["access_level"]

    if access in ("none", "suppressed"):
        raise HTTPException(403, result.get("note", f"Access {access} for role '{role}'."))

    rows = result["rows"]
    filename = f"citymind_{department}_{role}.{fmt}"

    if fmt == "json":
        import json as _json
        content = _json.dumps({"access_level": access, "rows": rows}, indent=2)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # Default: CSV
    if not rows:
        raise HTTPException(404, "No records returned for this query.")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Webview endpoint — RBAC-filtered HTML table
# ---------------------------------------------------------------------------

@app.get("/view/{department}", response_class=HTMLResponse)
def view_data(department: str, role: str = "analyst", zone_id: str = ""):
    """Return an HTML table of RBAC-filtered department data, viewable in a browser."""
    result = _fetch_rbac_rows(department, role, zone_id)
    access = result["access_level"]
    rows = result["rows"]

    zone_label = f" — {zone_id}" if zone_id else ""
    dept_title = department.title()
    access_color = {"full": "#2e7d32", "read": "#1565c0", "aggregated": "#e65100", "anonymized": "#6a1b9a"}.get(access, "#555")

    if access in ("none", "suppressed"):
        note = result.get("note", f"Access {access} for role '{role}'.")
        return HTMLResponse(f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>CityMind — Access Denied</title>
<style>body{{font-family:system-ui,sans-serif;padding:2rem;background:#fafafa;color:#333}}</style>
</head><body><h2>CityMind Data Gateway</h2>
<p style="color:#c62828;font-weight:bold">⛔ {access.upper()}: {note}</p></body></html>""")

    if not rows:
        return HTMLResponse(f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>CityMind — No Data</title>
<style>body{{font-family:system-ui,sans-serif;padding:2rem;background:#fafafa;color:#333}}</style>
</head><body><h2>CityMind Data Gateway</h2><p>No records returned.</p></body></html>""")

    headers = list(rows[0].keys())
    header_html = "".join(f"<th>{h}</th>" for h in headers)
    rows_html = ""
    for row in rows:
        cells = "".join(f"<td>{row.get(h, '')}</td>" for h in headers)
        rows_html += f"<tr>{cells}</tr>"

    zone_filter_display = zone_id if zone_id else "all zones"
    csv_href = f"/download/{department}?role={role}&zone_id={zone_id}&fmt=csv"
    json_href = f"/download/{department}?role={role}&zone_id={zone_id}&fmt=json"

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CityMind — {dept_title}{zone_label}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ font-family: system-ui, -apple-system, sans-serif; margin: 0; background: #f5f6fa; color: #1a1a2e; }}
    header {{ background: #1a1a2e; color: #fff; padding: 1rem 2rem; display: flex; align-items: center; gap: 1rem; }}
    header h1 {{ margin: 0; font-size: 1.25rem; }}
    header .badge {{ background: {access_color}; color: #fff; font-size: 0.75rem; padding: 0.2rem 0.6rem; border-radius: 999px; font-weight: 600; text-transform: uppercase; }}
    main {{ padding: 1.5rem 2rem; }}
    .meta {{ display: flex; gap: 1.5rem; margin-bottom: 1rem; font-size: 0.875rem; color: #555; flex-wrap: wrap; }}
    .meta span {{ background: #fff; border: 1px solid #ddd; border-radius: 6px; padding: 0.25rem 0.75rem; }}
    .actions {{ display: flex; gap: 0.75rem; margin-bottom: 1.25rem; }}
    .btn {{ display: inline-block; padding: 0.45rem 1rem; border-radius: 6px; font-size: 0.875rem; font-weight: 600; text-decoration: none; cursor: pointer; }}
    .btn-csv {{ background: #2e7d32; color: #fff; }}
    .btn-json {{ background: #1565c0; color: #fff; }}
    .btn:hover {{ opacity: 0.85; }}
    .table-wrap {{ overflow-x: auto; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; font-size: 0.875rem; }}
    th {{ background: #1a1a2e; color: #fff; padding: 0.65rem 1rem; text-align: left; font-weight: 600; white-space: nowrap; }}
    td {{ padding: 0.55rem 1rem; border-bottom: 1px solid #eee; white-space: nowrap; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:nth-child(even) {{ background: #f9f9f9; }}
    tr:hover {{ background: #eef2ff; }}
    footer {{ padding: 1rem 2rem; font-size: 0.75rem; color: #aaa; }}
  </style>
</head>
<body>
  <header>
    <h1>CityMind &mdash; {dept_title} Data{zone_label}</h1>
    <span class="badge">{access}</span>
  </header>
  <main>
    <div class="meta">
      <span>Role: <strong>{role}</strong></span>
      <span>Zone: <strong>{zone_filter_display}</strong></span>
      <span>Records: <strong>{len(rows)}</strong></span>
      <span>Access level: <strong style="color:{access_color}">{access}</strong></span>
    </div>
    <div class="actions">
      <a class="btn btn-csv" href="{csv_href}" download>&#8595; Download CSV</a>
      <a class="btn btn-json" href="{json_href}" download>&#8595; Download JSON</a>
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr>{header_html}</tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
  </main>
  <footer>CityMind Data Gateway &mdash; RBAC-enforced &mdash; All queries are audited.</footer>
</body>
</html>""")


# ---------------------------------------------------------------------------
# ArcGIS Open Data endpoints (Real data from Region of Waterloo / Kitchener)
# ---------------------------------------------------------------------------

from arcgis_client import get_client, DATASETS as ARCGIS_DATASETS
from sync import sync_router

# Include sync router for tiered read replica pattern
app.include_router(sync_router)


@app.get("/opendata/datasets")
def list_opendata_datasets():
    """List available open data datasets from ArcGIS."""
    return {
        "datasets": [
            {
                "id": k,
                "name": v["name"],
                "source": v["source"],
                "description": v["description"],
                "fields": v["fields"],
            }
            for k, v in ARCGIS_DATASETS.items()
        ],
        "count": len(ARCGIS_DATASETS),
    }


@app.post("/opendata/query")
def query_opendata(body: dict):
    """
    Query open data from ArcGIS.

    Body params:
        dataset: 'building_permits', 'water_mains', or 'bus_stops'
        where: Optional SQL WHERE clause (default: '1=1')
        fields: Optional list of fields to return
        limit: Max records (default: 100, max: 2000)
    """
    dataset = body.get("dataset")
    if not dataset:
        raise HTTPException(400, "Missing 'dataset' parameter")

    client = get_client()
    try:
        result = client.query(
            dataset=dataset,
            where=body.get("where", "1=1"),
            out_fields=body.get("fields"),
            result_record_count=min(body.get("limit", 100), 2000),
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"ArcGIS query failed: {e}")


@app.get("/opendata/permits")
def get_permits(
    permit_type: str = None,
    status: str = None,
    min_value: float = None,
    limit: int = 100,
):
    """Query building permits from City of Kitchener."""
    client = get_client()
    return client.get_building_permits(
        permit_type=permit_type,
        status=status,
        min_value=min_value,
        limit=limit,
    )


@app.get("/opendata/water-mains")
def get_water_mains(
    pressure_zone: str = None,
    material: str = None,
    min_criticality: int = None,
    limit: int = 100,
):
    """Query water main infrastructure from City of Kitchener."""
    client = get_client()
    return client.get_water_mains(
        pressure_zone=pressure_zone,
        material=material,
        min_criticality=min_criticality,
        limit=limit,
    )


@app.get("/opendata/transit-stops")
def get_transit_stops(
    municipality: str = None,
    ixpress_only: bool = False,
    limit: int = 100,
):
    """Query GRT bus stops."""
    client = get_client()
    return client.get_bus_stops(
        municipality=municipality,
        ixpress_only=ixpress_only,
        limit=limit,
    )


@app.get("/opendata/infrastructure-summary")
def get_infrastructure_summary(zone: str = None):
    """Get cross-dataset infrastructure summary."""
    client = get_client()
    return client.get_infrastructure_summary(zone=zone)


# ---------------------------------------------------------------------------
# Local Replica endpoints (query aggregated data from SQLite)
# ---------------------------------------------------------------------------

from pathlib import Path

REPLICA_DB = Path(__file__).parent / "db" / "opendata_replica.db"


def _get_replica_conn():
    """Get a connection to the replica database."""
    conn = sqlite3.connect(str(REPLICA_DB))
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/replica/permits")
def get_replica_permits(
    permit_no: str = None,
    permit_type: str = None,
    status: str = None,
    min_value: float = None,
    issued_by: str = None,
    issue_year: int = None,
    limit: int = 100,
):
    """Query building permits from local replica (all 46 fields available)."""
    conn = _get_replica_conn()

    clauses = []
    params = []

    if permit_no:
        clauses.append("permit_no = ?")
        params.append(permit_no)
    if permit_type:
        clauses.append("permit_type LIKE ?")
        params.append(f"%{permit_type}%")
    if status:
        clauses.append("permit_status LIKE ?")
        params.append(f"%{status}%")
    if min_value:
        clauses.append("construction_value >= ?")
        params.append(min_value)
    if issued_by:
        clauses.append("issued_by LIKE ?")
        params.append(f"%{issued_by}%")
    if issue_year:
        clauses.append("issue_year = ?")
        params.append(float(issue_year))

    where = " AND ".join(clauses) if clauses else "1=1"
    query = f"SELECT * FROM building_permits WHERE {where} LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    return {
        "source": "Local Replica (City of Kitchener)",
        "record_count": len(rows),
        "features": [dict(row) for row in rows],
    }


@app.get("/replica/permits/download")
def download_replica_permits(
    permit_type: str = None,
    status: str = None,
    min_value: float = None,
    issued_by: str = None,
    issue_year: int = None,
    fmt: str = "csv",
):
    """Download building permits from local replica as CSV or JSON."""
    conn = _get_replica_conn()

    clauses = []
    params = []

    if permit_type:
        clauses.append("permit_type LIKE ?")
        params.append(f"%{permit_type}%")
    if status:
        clauses.append("permit_status LIKE ?")
        params.append(f"%{status}%")
    if min_value:
        clauses.append("construction_value >= ?")
        params.append(min_value)
    if issued_by:
        clauses.append("issued_by LIKE ?")
        params.append(f"%{issued_by}%")
    if issue_year:
        clauses.append("issue_year = ?")
        params.append(float(issue_year))

    where = " AND ".join(clauses) if clauses else "1=1"
    query = f"SELECT * FROM building_permits WHERE {where}"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        raise HTTPException(404, "No permits found matching criteria")

    records = [dict(row) for row in rows]
    filename = "building_permits"
    if issue_year:
        filename += f"_{issue_year}"
    if permit_type:
        filename += f"_{permit_type.replace(' ', '_')}"

    if fmt == "json":
        import json as _json
        content = _json.dumps({"record_count": len(records), "permits": records}, indent=2)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
        )

    # Default: CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=records[0].keys())
    writer.writeheader()
    writer.writerows(records)
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )


@app.get("/replica/permits/{permit_no}")
def get_replica_permit_by_id(permit_no: str):
    """Get a single building permit by permit number from local replica."""
    conn = _get_replica_conn()
    row = conn.execute(
        "SELECT * FROM building_permits WHERE permit_no = ?", (permit_no,)
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(404, f"Permit {permit_no} not found")

    return {
        "source": "Local Replica (City of Kitchener)",
        "permit": dict(row),
    }


@app.get("/replica/water-mains")
def get_replica_water_mains(
    pressure_zone: str = None,
    material: str = None,
    min_criticality: int = None,
    status: str = None,
    limit: int = 100,
):
    """Query water mains from local replica."""
    conn = _get_replica_conn()

    clauses = []
    params = []

    if pressure_zone:
        clauses.append("pressure_zone LIKE ?")
        params.append(f"%{pressure_zone}%")
    if material:
        clauses.append("material = ?")
        params.append(material)
    if min_criticality:
        clauses.append("criticality >= ?")
        params.append(min_criticality)
    if status:
        clauses.append("status = ?")
        params.append(status)

    where = " AND ".join(clauses) if clauses else "1=1"
    query = f"SELECT * FROM water_mains WHERE {where} LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    return {
        "source": "Local Replica (City of Kitchener)",
        "record_count": len(rows),
        "features": [dict(row) for row in rows],
    }


@app.get("/replica/water-mains/download")
def download_replica_water_mains(
    pressure_zone: str = None,
    material: str = None,
    min_criticality: int = None,
    fmt: str = "csv",
):
    """Download water mains from local replica as CSV or JSON."""
    conn = _get_replica_conn()

    clauses = []
    params = []

    if pressure_zone:
        clauses.append("pressure_zone LIKE ?")
        params.append(f"%{pressure_zone}%")
    if material:
        clauses.append("material = ?")
        params.append(material)
    if min_criticality:
        clauses.append("criticality >= ?")
        params.append(min_criticality)

    where = " AND ".join(clauses) if clauses else "1=1"
    query = f"SELECT * FROM water_mains WHERE {where}"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        raise HTTPException(404, "No water mains found matching criteria")

    records = [dict(row) for row in rows]
    filename = "water_mains"

    if fmt == "json":
        import json as _json
        content = _json.dumps({"record_count": len(records), "water_mains": records}, indent=2)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
        )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=records[0].keys())
    writer.writeheader()
    writer.writerows(records)
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )


@app.get("/replica/bus-stops")
def get_replica_bus_stops(
    municipality: str = None,
    ixpress_only: bool = False,
    limit: int = 100,
):
    """Query bus stops from local replica."""
    conn = _get_replica_conn()

    clauses = []
    params = []

    if municipality:
        clauses.append("municipality = ?")
        params.append(municipality)
    if ixpress_only:
        clauses.append("ixpress = 'Y'")

    where = " AND ".join(clauses) if clauses else "1=1"
    query = f"SELECT * FROM bus_stops WHERE {where} LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    return {
        "source": "Local Replica (GRT / Region of Waterloo)",
        "record_count": len(rows),
        "features": [dict(row) for row in rows],
    }


@app.get("/replica/bus-stops/download")
def download_replica_bus_stops(
    municipality: str = None,
    ixpress_only: bool = False,
    fmt: str = "csv",
):
    """Download bus stops from local replica as CSV or JSON."""
    conn = _get_replica_conn()

    clauses = []
    params = []

    if municipality:
        clauses.append("municipality = ?")
        params.append(municipality)
    if ixpress_only:
        clauses.append("ixpress = 'Y'")

    where = " AND ".join(clauses) if clauses else "1=1"
    query = f"SELECT * FROM bus_stops WHERE {where}"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        raise HTTPException(404, "No bus stops found matching criteria")

    records = [dict(row) for row in rows]
    filename = "bus_stops"
    if municipality:
        filename += f"_{municipality}"

    if fmt == "json":
        import json as _json
        content = _json.dumps({"record_count": len(records), "bus_stops": records}, indent=2)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
        )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=records[0].keys())
    writer.writeheader()
    writer.writerows(records)
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )


@app.get("/replica/stats")
def get_replica_stats():
    """Get statistics about the local replica database."""
    conn = _get_replica_conn()

    stats = {}
    for table in ["building_permits", "water_mains", "bus_stops"]:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            stats[table] = count
        except Exception:
            stats[table] = 0

    # Get last sync time
    last_sync = conn.execute(
        "SELECT MAX(completed_at) FROM sync_runs WHERE status = 'completed'"
    ).fetchone()[0]

    conn.close()

    return {
        "tables": stats,
        "total_records": sum(stats.values()),
        "last_sync": last_sync,
    }


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "CityMind Data Gateway"}
