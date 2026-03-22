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
def list_catalog() -> dict:
    return {"datasets": list(CATALOG.values()), "count": len(CATALOG)}


@app.get("/catalog/quality")
def catalog_quality() -> dict:
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
def catalog_dictionary() -> dict:
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
def get_dataset(dataset_id: str) -> dict:
    if dataset_id not in CATALOG:
        raise HTTPException(404, "Dataset not found")
    return CATALOG[dataset_id]


@app.post("/catalog/search")
def search_catalog(body: dict) -> dict:
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
def federated_query(body: dict) -> dict:
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
def get_audit(limit: int = 20) -> dict:
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

def _fetch_rbac_rows(department: str, role: str, zone_id: str) -> dict:
    """Shared helper: fetch and privacy-filter rows for a department."""
    if department not in DB_MAP:
        raise HTTPException(400, f"Unknown department: {department}. Valid: {list(DB_MAP.keys())}")
    db_path, table = DB_MAP[department]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    if zone_id:
        rows = conn.execute(f"SELECT * FROM {table} WHERE zone_id = ?", (zone_id,)).fetchall()
    else:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    conn.close()
    raw = [dict(r) for r in rows]
    return apply_privacy(raw, department, role)


@app.get("/download/{department}")
def download_data(department: str, role: str = "analyst", zone_id: str = "", fmt: str = "csv"):
    """Return RBAC-filtered department data as a downloadable CSV or JSON file."""
    result = _fetch_rbac_rows(department, role, zone_id)
    access = result["access_level"]

    if access in ("none", "suppressed"):
        raise HTTPException(403, result.get("note", f"Access {access} for role '{role}'."))

    rows = result["rows"]
    zone_label = f"_{zone_id}" if zone_id else ""
    filename = f"citymind_{department}{zone_label}_{role}.{fmt}"

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
def view_data(department: str, role: str = "analyst", zone_id: str = "") -> HTMLResponse:
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
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "service": "CityMind Data Gateway"}
