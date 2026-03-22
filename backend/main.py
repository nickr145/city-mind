# backend/main.py
import csv
import io
import json as _json
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

from audit import _conn, log_query
from catalog import CATALOG, _load, _save
from privacy import apply_privacy

app = FastAPI(title="CityMind Data Gateway", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_version_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-CityMind-Version"] = "1.0"
    return response


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

# Date field used for as_of filtering per department
DATE_FIELD = {
    "planning": "issue_date",
    "engineering": "synced_at",
    "transit": "synced_at",
}

# Key fields for completeness checks (exclude STRIP_ALWAYS fields)
KEY_FIELDS = {
    "building_permits": ["permit_no", "permit_type", "permit_status", "issue_date", "construction_value"],
    "water_mains":      ["watmain_id", "status", "pressure_zone", "material"],
    "bus_stops":        ["stop_id", "street", "municipality", "status"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db_conn(db_path: str = REAL_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _compute_field_nulls(conn: sqlite3.Connection, table: str) -> dict:
    """Return % null per key field for a given table."""
    fields = KEY_FIELDS.get(table, [])
    if not fields:
        return {}
    total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    if total == 0:
        return {f: 0.0 for f in fields}
    result = {}
    for field in fields:
        null_count = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {field} IS NULL OR CAST({field} AS TEXT) = ''"
        ).fetchone()[0]
        result[field] = round(null_count / total * 100, 1)
    return result


def _quality_score(null_rates: dict, is_stale: bool) -> int:
    """Compute 0–100 quality score: 60% completeness + 40% freshness."""
    avg_null = sum(null_rates.values()) / len(null_rates) if null_rates else 0
    completeness = max(0, 100 - avg_null)
    freshness = 0 if is_stale else 100
    return round(completeness * 0.6 + freshness * 0.4)


def _fetch_rbac_rows(department: str, role: str, filters: dict = None,
                     limit: int = 500, as_of: str = None) -> dict:
    """Shared helper: fetch and privacy-filter rows for a department."""
    if department not in DB_MAP:
        raise HTTPException(400, f"Unknown department: {department}. Valid: {list(DB_MAP.keys())}")
    db_path, table = DB_MAP[department]
    conn = _db_conn(db_path)
    allowed = ALLOWED_FILTERS.get(department, set())
    clauses, params = [], []
    for field, value in (filters or {}).items():
        if field in allowed and value not in (None, ""):
            clauses.append(f"{field} = ?")
            params.append(value)
    if as_of and department in DATE_FIELD:
        clauses.append(f"{DATE_FIELD[department]} <= ?")
        params.append(as_of)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(f"SELECT * FROM {table} {where} LIMIT ?", params + [limit]).fetchall()
    conn.close()
    raw = [dict(r) for r in rows]
    return apply_privacy(raw, department, role)


def _rows_to_geojson(rows: list) -> dict:
    """Convert a list of row dicts to a GeoJSON FeatureCollection (geometry=null)."""
    features = [
        {"type": "Feature", "geometry": None, "properties": row}
        for row in rows
    ]
    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# Catalog endpoints
# ---------------------------------------------------------------------------

@app.get("/catalog")
def list_catalog():
    catalog = _load()
    return {"datasets": list(catalog.values()), "count": len(catalog)}


@app.get("/catalog/quality")
def catalog_quality():
    """Enhanced quality: staleness + per-field null % + quality score per dataset."""
    catalog = _load()
    threshold = datetime.now() - timedelta(days=90)
    conn = _db_conn()

    result = []
    for ds in catalog.values():
        updated = ds.get("last_updated", "")
        try:
            is_stale = datetime.fromisoformat(updated) < threshold
        except ValueError:
            is_stale = True

        dept = ds.get("department")
        _, table = DB_MAP.get(dept, (None, None)) if dept in DB_MAP else (None, None)
        null_rates = _compute_field_nulls(conn, table) if table else {}
        score = _quality_score(null_rates, is_stale)

        result.append({
            "dataset_id": ds["dataset_id"],
            "name": ds.get("name"),
            "department": dept,
            "last_updated": updated,
            "is_stale": is_stale,
            "quality_score": score,
            "field_null_pct": null_rates,
            "record_count": ds.get("record_count", 0),
        })

    conn.close()
    stale = [r for r in result if r["is_stale"]]
    return {
        "datasets": result,
        "stale_datasets": stale,
        "stale_count": len(stale),
    }


@app.get("/catalog/dictionary")
def catalog_dictionary():
    """Return shared field definitions (data dictionary)."""
    catalog = _load()
    return {
        "shared_fields": {
            "permit_no":  {"type": "string",   "description": "Unique permit number (e.g. 24-100432)", "privacy": "public"},
            "watmain_id": {"type": "string",   "description": "Unique water main asset ID",            "privacy": "internal"},
            "stop_id":    {"type": "string",   "description": "Unique GRT bus stop ID",                "privacy": "public"},
            "source_id":  {"type": "string",   "description": "Origin data source (e.g. kitchener)",   "privacy": "internal"},
            "synced_at":  {"type": "ISO 8601", "description": "Timestamp when record was last synced from ArcGIS", "privacy": "internal"},
        },
        "departments": {
            ds["department"]: {"fields": ds["fields"], "sensitivity": ds["sensitivity"]}
            for ds in catalog.values()
        },
    }


@app.get("/catalog/{dataset_id}")
def get_dataset(dataset_id: str):
    catalog = _load()
    if dataset_id not in catalog:
        raise HTTPException(404, "Dataset not found")
    return catalog[dataset_id]


@app.post("/catalog/search")
def search_catalog(body: dict):
    catalog = _load()
    tags = body.get("tags", [])
    dept = body.get("department")
    query = body.get("query", "").lower()
    results = [
        d for d in catalog.values()
        if (not tags or any(t in d.get("tags", []) for t in tags))
        and (not dept or d["department"] == dept)
        and (not query or query in d["name"].lower() or query in d.get("description", "").lower()
             or any(query in t for t in d.get("tags", [])))
    ]
    return {"results": results, "count": len(results)}


@app.post("/catalog/datasets")
def upsert_dataset(body: dict):
    """Admin-only: add or update a dataset entry in the catalog."""
    if body.get("role") != "admin":
        raise HTTPException(403, "Admin role required to modify the catalog.")
    dataset = body.get("dataset")
    if not dataset:
        raise HTTPException(400, "Missing 'dataset' field in request body.")
    required = {"dataset_id", "department", "name", "sensitivity", "fields"}
    missing = required - set(dataset.keys())
    if missing:
        raise HTTPException(400, f"Missing required dataset fields: {sorted(missing)}")
    catalog = _load()
    catalog[dataset["dataset_id"]] = dataset
    _save(catalog)
    return {"status": "ok", "dataset_id": dataset["dataset_id"]}


# ---------------------------------------------------------------------------
# Federated query endpoint (RBAC + privacy layer)
# ---------------------------------------------------------------------------

@app.post("/query")
def federated_query(body: dict):
    role = body.get("role", "analyst")
    department = body.get("department")
    filters = body.get("filters", {})
    limit = min(int(body.get("limit", 200)), 2000)
    as_of = body.get("as_of")  # ISO date string, e.g. "2024-12-31"
    fmt = body.get("fmt", "json")

    if department not in DB_MAP:
        raise HTTPException(400, f"Unknown department: {department}. Valid: {list(DB_MAP.keys())}")

    db_path, table = DB_MAP[department]
    conn = _db_conn(db_path)

    allowed = ALLOWED_FILTERS.get(department, set())
    clauses, params = [], []
    for field, value in filters.items():
        if field in allowed and value not in (None, ""):
            clauses.append(f"{field} = ?")
            params.append(value)
    if as_of and department in DATE_FIELD:
        clauses.append(f"{DATE_FIELD[department]} <= ?")
        params.append(as_of)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(f"SELECT * FROM {table} {where} LIMIT ?", params + [limit]).fetchall()
    conn.close()

    raw = [dict(r) for r in rows]
    result = apply_privacy(raw, department, role)

    filter_desc = ", ".join(f"{k}={v}" for k, v in filters.items() if v) or "all"
    if as_of:
        filter_desc += f", as_of={as_of}"
    log_query({
        "query_id": str(uuid.uuid4()),
        "requester_role": role,
        "department": department,
        "zone_filter": filter_desc,
        "access_level_applied": result["access_level"],
        "record_count": len(result["rows"]),
        "suppressed": result["access_level"] in ("suppressed", "none"),
    })

    if fmt == "geojson":
        geo = _rows_to_geojson(result["rows"])
        geo["access_level"] = result["access_level"]
        if "note" in result:
            geo["note"] = result["note"]
        return JSONResponse(content=geo, headers={"Content-Type": "application/geo+json"})

    return result


# ---------------------------------------------------------------------------
# Cross-departmental query endpoint
# ---------------------------------------------------------------------------

@app.post("/query/cross")
def cross_query(body: dict):
    """
    Query all departments simultaneously with RBAC applied per-dept.
    Returns per-dept results + a unified summary for cross-departmental analysis.
    """
    role = body.get("role", "analyst")
    limit = min(int(body.get("limit", 200)), 1000)

    dept_results = {}
    for dept in DB_MAP:
        try:
            r = _fetch_rbac_rows(dept, role, limit=limit)
        except HTTPException:
            r = {"rows": [], "access_level": "error"}
        dept_results[dept] = r

    # Build summary statistics per department
    summary = {}
    for dept, r in dept_results.items():
        rows = r.get("rows", [])
        entry = {
            "access_level": r.get("access_level"),
            "record_count": len(rows),
        }
        if rows and r.get("access_level") in ("full", "read", "anonymized"):
            # Compute a few cross-dept stats where possible
            if dept == "planning":
                types = {}
                for row in rows:
                    t = row.get("permit_type", "Unknown") or "Unknown"
                    types[t] = types.get(t, 0) + 1
                top = sorted(types.items(), key=lambda x: -x[1])[:5]
                entry["top_permit_types"] = [{"type": k, "count": v} for k, v in top]
            elif dept == "engineering":
                zones = {}
                for row in rows:
                    z = row.get("pressure_zone", "Unknown") or "Unknown"
                    zones[z] = zones.get(z, 0) + 1
                entry["pressure_zones"] = len(zones)
            elif dept == "transit":
                munis = {}
                for row in rows:
                    m = row.get("municipality", "Unknown") or "Unknown"
                    munis[m] = munis.get(m, 0) + 1
                entry["by_municipality"] = munis
        elif r.get("access_level") == "aggregated":
            entry["aggregated_groups"] = rows
        summary[dept] = entry

    log_query({
        "query_id": str(uuid.uuid4()),
        "requester_role": role,
        "department": "cross",
        "zone_filter": "all",
        "access_level_applied": "multi",
        "record_count": sum(len(r.get("rows", [])) for r in dept_results.values()),
        "suppressed": False,
    })

    return {
        "role": role,
        "departments": summary,
        "note": "Cross-departmental view. RBAC enforced independently per department.",
    }


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
# Download endpoint — RBAC-filtered CSV, JSON, or GeoJSON
# ---------------------------------------------------------------------------

@app.get("/download/{department}")
def download_data(department: str, role: str = "analyst", fmt: str = "csv"):
    """Return RBAC-filtered department data as a downloadable file."""
    result = _fetch_rbac_rows(department, role)
    access = result["access_level"]

    if access in ("none", "suppressed"):
        raise HTTPException(403, result.get("note", f"Access {access} for role '{role}'."))

    rows = result["rows"]
    filename = f"citymind_{department}_{role}"

    if fmt == "geojson":
        geo = _rows_to_geojson(rows)
        geo["access_level"] = access
        content = _json.dumps(geo, indent=2)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/geo+json",
            headers={"Content-Disposition": f'attachment; filename="{filename}.geojson"'},
        )

    if fmt == "json":
        content = _json.dumps({"access_level": access, "rows": rows}, indent=2)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
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
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )


# ---------------------------------------------------------------------------
# Geo endpoint — bus stops with real ArcGIS geometry
# ---------------------------------------------------------------------------

@app.get("/geo/bus-stops")
def geo_bus_stops(limit: int = 500):
    """
    Return bus stop locations as GeoJSON, fetching geometry from ArcGIS.
    Falls back to geometry=null if ArcGIS is unavailable.
    """
    import httpx

    BUS_STOP_URL = (
        "https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services"
        "/Bus_Stop/FeatureServer/0/query"
    )
    params = {
        "f": "geojson",
        "where": "1=1",
        "outFields": "STOP_ID,STREET,CROSSSTREET,MUNICIPALITY,IXPRESS,STATUS",
        "returnGeometry": "true",
        "outSR": "4326",
        "resultRecordCount": min(limit, 2000),
    }
    try:
        resp = httpx.get(BUS_STOP_URL, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        # Normalize field names to lowercase
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            feature["properties"] = {k.lower(): v for k, v in props.items()}
        return JSONResponse(content=data)
    except Exception as e:
        # Fallback: return local replica data with null geometry
        conn = _db_conn()
        rows = conn.execute(f"SELECT * FROM bus_stops LIMIT {limit}").fetchall()
        conn.close()
        raw = [dict(r) for r in rows]
        result = apply_privacy(raw, "transit", "analyst")
        return JSONResponse(content=_rows_to_geojson(result["rows"]))


# ---------------------------------------------------------------------------
# Webview endpoint — RBAC-filtered HTML table (legacy, deprecated)
# ---------------------------------------------------------------------------

@app.get("/view/{department}", response_class=HTMLResponse, deprecated=True)
def view_data(department: str, role: str = "analyst", zone_id: str = ""):
    """
    [Deprecated] HTML table view. Use the React frontend at port 5173 instead.
    """
    result = _fetch_rbac_rows(department, role)
    access = result["access_level"]
    rows = result["rows"]

    if access in ("none", "suppressed"):
        note = result.get("note", f"Access {access} for role '{role}'.")
        return HTMLResponse(f"<h2>Access Denied</h2><p>{note}</p>")

    if not rows:
        return HTMLResponse("<h2>No Data</h2><p>No records returned.</p>")

    headers = list(rows[0].keys())
    header_html = "".join(f"<th>{h}</th>" for h in headers)
    rows_html = "".join(
        "<tr>" + "".join(f"<td>{r.get(h, '')}</td>" for h in headers) + "</tr>"
        for r in rows
    )
    return HTMLResponse(f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>CityMind — {department}</title></head><body>
<p><em>Deprecated: use the React frontend instead.</em></p>
<table border='1'><thead><tr>{header_html}</tr></thead>
<tbody>{rows_html}</tbody></table></body></html>""")


# ---------------------------------------------------------------------------
# ArcGIS Open Data endpoints (deprecated — use /query with RBAC instead)
# ---------------------------------------------------------------------------

from arcgis_client import get_client, DATASETS as ARCGIS_DATASETS
from sync import sync_router

app.include_router(sync_router)


@app.get("/opendata/datasets", deprecated=True)
def list_opendata_datasets():
    """[Deprecated] Use GET /catalog instead."""
    return {
        "datasets": [
            {"id": k, "name": v["name"], "source": v["source"],
             "description": v["description"], "fields": v["fields"]}
            for k, v in ARCGIS_DATASETS.items()
        ],
        "count": len(ARCGIS_DATASETS),
    }


@app.post("/opendata/query", deprecated=True)
def query_opendata(body: dict):
    """[Deprecated] Use POST /query instead."""
    dataset = body.get("dataset")
    if not dataset:
        raise HTTPException(400, "Missing 'dataset' parameter")
    client = get_client()
    try:
        return client.query(
            dataset=dataset,
            where=body.get("where", "1=1"),
            out_fields=body.get("fields"),
            result_record_count=min(body.get("limit", 100), 2000),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"ArcGIS query failed: {e}")


@app.get("/opendata/permits", deprecated=True)
def get_permits(permit_type: str = None, status: str = None,
                min_value: float = None, limit: int = 100):
    """[Deprecated] Use POST /query with department=planning instead."""
    client = get_client()
    return client.get_building_permits(permit_type=permit_type, status=status,
                                       min_value=min_value, limit=limit)


@app.get("/opendata/water-mains", deprecated=True)
def get_water_mains(pressure_zone: str = None, material: str = None,
                    min_criticality: int = None, limit: int = 100):
    """[Deprecated] Use POST /query with department=engineering instead."""
    client = get_client()
    return client.get_water_mains(pressure_zone=pressure_zone, material=material,
                                  min_criticality=min_criticality, limit=limit)


@app.get("/opendata/transit-stops", deprecated=True)
def get_transit_stops(municipality: str = None, ixpress_only: bool = False, limit: int = 100):
    """[Deprecated] Use POST /query with department=transit instead."""
    client = get_client()
    return client.get_bus_stops(municipality=municipality, ixpress_only=ixpress_only, limit=limit)


@app.get("/opendata/infrastructure-summary", deprecated=True)
def get_infrastructure_summary(zone: str = None):
    """[Deprecated] Use POST /query/cross instead."""
    client = get_client()
    return client.get_infrastructure_summary(zone=zone)


# ---------------------------------------------------------------------------
# Local Replica endpoints (deprecated — use /query with RBAC instead)
# ---------------------------------------------------------------------------

REPLICA_DB = Path(__file__).parent / "db" / "opendata_replica.db"


def _get_replica_conn():
    conn = sqlite3.connect(str(REPLICA_DB))
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/replica/permits", deprecated=True)
def get_replica_permits(permit_no: str = None, permit_type: str = None,
                        status: str = None, min_value: float = None,
                        issued_by: str = None, issue_year: int = None, limit: int = 100):
    """[Deprecated] Use POST /query with department=planning instead."""
    conn = _get_replica_conn()
    clauses, params = [], []
    if permit_no:
        clauses.append("permit_no = ?"); params.append(permit_no)
    if permit_type:
        clauses.append("permit_type LIKE ?"); params.append(f"%{permit_type}%")
    if status:
        clauses.append("permit_status LIKE ?"); params.append(f"%{status}%")
    if min_value:
        clauses.append("construction_value >= ?"); params.append(min_value)
    if issued_by:
        clauses.append("issued_by LIKE ?"); params.append(f"%{issued_by}%")
    if issue_year:
        clauses.append("issue_year = ?"); params.append(float(issue_year))
    where = " AND ".join(clauses) if clauses else "1=1"
    rows = conn.execute(f"SELECT * FROM building_permits WHERE {where} LIMIT ?",
                        params + [limit]).fetchall()
    conn.close()
    return {"source": "Local Replica", "record_count": len(rows),
            "features": [dict(r) for r in rows]}


@app.get("/replica/permits/download", deprecated=True)
def download_replica_permits(permit_type: str = None, status: str = None,
                             min_value: float = None, issued_by: str = None,
                             issue_year: int = None, fmt: str = "csv"):
    """[Deprecated] Use GET /download/planning instead."""
    conn = _get_replica_conn()
    clauses, params = [], []
    if permit_type:
        clauses.append("permit_type LIKE ?"); params.append(f"%{permit_type}%")
    if status:
        clauses.append("permit_status LIKE ?"); params.append(f"%{status}%")
    if min_value:
        clauses.append("construction_value >= ?"); params.append(min_value)
    if issued_by:
        clauses.append("issued_by LIKE ?"); params.append(f"%{issued_by}%")
    if issue_year:
        clauses.append("issue_year = ?"); params.append(float(issue_year))
    where = " AND ".join(clauses) if clauses else "1=1"
    rows = conn.execute(f"SELECT * FROM building_permits WHERE {where}", params).fetchall()
    conn.close()
    if not rows:
        raise HTTPException(404, "No permits found")
    records = [dict(r) for r in rows]
    if fmt == "json":
        content = _json.dumps({"record_count": len(records), "permits": records}, indent=2)
        return StreamingResponse(io.BytesIO(content.encode()), media_type="application/json",
                                 headers={"Content-Disposition": 'attachment; filename="permits.json"'})
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=records[0].keys())
    writer.writeheader(); writer.writerows(records); output.seek(0)
    return StreamingResponse(io.BytesIO(output.getvalue().encode()), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="permits.csv"'})


@app.get("/replica/permits/{permit_no}", deprecated=True)
def get_replica_permit_by_id(permit_no: str):
    """[Deprecated] Use POST /query with department=planning instead."""
    conn = _get_replica_conn()
    row = conn.execute("SELECT * FROM building_permits WHERE permit_no = ?",
                       (permit_no,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, f"Permit {permit_no} not found")
    return {"source": "Local Replica", "permit": dict(row)}


@app.get("/replica/water-mains", deprecated=True)
def get_replica_water_mains(pressure_zone: str = None, material: str = None,
                            min_criticality: int = None, status: str = None, limit: int = 100):
    """[Deprecated] Use POST /query with department=engineering instead."""
    conn = _get_replica_conn()
    clauses, params = [], []
    if pressure_zone:
        clauses.append("pressure_zone LIKE ?"); params.append(f"%{pressure_zone}%")
    if material:
        clauses.append("material = ?"); params.append(material)
    if min_criticality:
        clauses.append("criticality >= ?"); params.append(min_criticality)
    if status:
        clauses.append("status = ?"); params.append(status)
    where = " AND ".join(clauses) if clauses else "1=1"
    rows = conn.execute(f"SELECT * FROM water_mains WHERE {where} LIMIT ?",
                        params + [limit]).fetchall()
    conn.close()
    return {"source": "Local Replica", "record_count": len(rows),
            "features": [dict(r) for r in rows]}


@app.get("/replica/water-mains/download", deprecated=True)
def download_replica_water_mains(pressure_zone: str = None, material: str = None,
                                  min_criticality: int = None, fmt: str = "csv"):
    """[Deprecated] Use GET /download/engineering instead."""
    conn = _get_replica_conn()
    clauses, params = [], []
    if pressure_zone:
        clauses.append("pressure_zone LIKE ?"); params.append(f"%{pressure_zone}%")
    if material:
        clauses.append("material = ?"); params.append(material)
    if min_criticality:
        clauses.append("criticality >= ?"); params.append(min_criticality)
    where = " AND ".join(clauses) if clauses else "1=1"
    rows = conn.execute(f"SELECT * FROM water_mains WHERE {where}", params).fetchall()
    conn.close()
    if not rows:
        raise HTTPException(404, "No water mains found")
    records = [dict(r) for r in rows]
    if fmt == "json":
        content = _json.dumps({"record_count": len(records), "water_mains": records}, indent=2)
        return StreamingResponse(io.BytesIO(content.encode()), media_type="application/json",
                                 headers={"Content-Disposition": 'attachment; filename="water_mains.json"'})
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=records[0].keys())
    writer.writeheader(); writer.writerows(records); output.seek(0)
    return StreamingResponse(io.BytesIO(output.getvalue().encode()), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="water_mains.csv"'})


@app.get("/replica/bus-stops", deprecated=True)
def get_replica_bus_stops(municipality: str = None, ixpress_only: bool = False, limit: int = 100):
    """[Deprecated] Use POST /query with department=transit instead."""
    conn = _get_replica_conn()
    clauses, params = [], []
    if municipality:
        clauses.append("municipality = ?"); params.append(municipality)
    if ixpress_only:
        clauses.append("ixpress = 'Y'")
    where = " AND ".join(clauses) if clauses else "1=1"
    rows = conn.execute(f"SELECT * FROM bus_stops WHERE {where} LIMIT ?",
                        params + [limit]).fetchall()
    conn.close()
    return {"source": "Local Replica", "record_count": len(rows),
            "features": [dict(r) for r in rows]}


@app.get("/replica/bus-stops/download", deprecated=True)
def download_replica_bus_stops(municipality: str = None, ixpress_only: bool = False, fmt: str = "csv"):
    """[Deprecated] Use GET /download/transit instead."""
    conn = _get_replica_conn()
    clauses, params = [], []
    if municipality:
        clauses.append("municipality = ?"); params.append(municipality)
    if ixpress_only:
        clauses.append("ixpress = 'Y'")
    where = " AND ".join(clauses) if clauses else "1=1"
    rows = conn.execute(f"SELECT * FROM bus_stops WHERE {where}", params).fetchall()
    conn.close()
    if not rows:
        raise HTTPException(404, "No bus stops found")
    records = [dict(r) for r in rows]
    if fmt == "json":
        content = _json.dumps({"record_count": len(records), "bus_stops": records}, indent=2)
        return StreamingResponse(io.BytesIO(content.encode()), media_type="application/json",
                                 headers={"Content-Disposition": 'attachment; filename="bus_stops.json"'})
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=records[0].keys())
    writer.writeheader(); writer.writerows(records); output.seek(0)
    return StreamingResponse(io.BytesIO(output.getvalue().encode()), media_type="text/csv",
                             headers={"Content-Disposition": 'attachment; filename="bus_stops.csv"'})


@app.get("/replica/stats", deprecated=True)
def get_replica_stats():
    """[Deprecated] Use GET /sync/status instead."""
    conn = _get_replica_conn()
    stats = {}
    for table in ["building_permits", "water_mains", "bus_stops"]:
        try:
            stats[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except Exception:
            stats[table] = 0
    last_sync = conn.execute(
        "SELECT MAX(completed_at) FROM sync_runs WHERE status = 'completed'"
    ).fetchone()[0]
    conn.close()
    return {"tables": stats, "total_records": sum(stats.values()), "last_sync": last_sync}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "CityMind Data Gateway", "version": "1.0"}
