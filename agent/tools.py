# agent/tools.py
import os
import requests
from langchain.tools import tool

BASE = os.getenv("FASTAPI_URL", "http://localhost:8000")


@tool
def catalog_tool(query: str) -> str:
    """Search the municipal data catalog to discover what datasets exist,
    which departments own them, what fields are available, and what tags
    describe the data. Use this FIRST before any federated query.
    Input: a plain-text description of what data you are looking for."""
    tags = query.lower().split()[:4]  # simple keyword extraction
    resp = requests.post(f"{BASE}/catalog/search", json={"tags": tags}, timeout=10)
    data = resp.json()
    if not data["results"]:
        return f"No datasets found matching: {query}. Try broader terms."
    lines = []
    for d in data["results"]:
        lines.append(
            f"- [{d['department'].upper()}] {d['name']} (sensitivity: {d['sensitivity']})"
            f"\n  Fields: {', '.join(d['fields'])}"
            f"\n  Tags: {', '.join(d['tags'])}"
        )
    return "\n".join(lines)


@tool
def query_tool(department: str, role: str, zone_id: str = "") -> str:
    """Query a specific department's data with RBAC privacy enforcement applied.
    The privacy layer will automatically filter and anonymize results based on the role.

    Parameters:
      department: one of 'engineering', 'planning', 'health', 'transit'
      role: one of 'engineer', 'planner', 'health', 'analyst', 'admin'
      zone_id: optional zone filter e.g. 'WR-ZONE-042'. Leave empty for all zones.

    Returns role-filtered, anonymized data with access_level indicated."""
    payload = {"department": department, "role": role}
    if zone_id:
        payload["zone_id"] = zone_id
    resp = requests.post(f"{BASE}/query", json=payload, timeout=10)
    result = resp.json()
    access = result.get("access_level", "unknown")
    rows = result.get("rows", [])

    if access == "none":
        return f"ACCESS DENIED: {result.get('note', 'No access for this role.')}"
    if access == "suppressed":
        return f"SUPPRESSED: {result.get('note', 'Small-cell suppression applied.')}"

    summary = f"Access level: {access} | Records returned: {len(rows)}\n"
    for r in rows[:5]:  # show first 5 to agent
        summary += str(r) + "\n"
    if len(rows) > 5:
        summary += f"... and {len(rows) - 5} more records."
    return summary


@tool
def download_tool(department: str, role: str, zone_id: str = "", fmt: str = "csv") -> str:
    """Generate a download link and a browser webview link for department data with RBAC applied.
    Use this whenever the user asks to download, export, or view data directly.

    Parameters:
      department: one of 'engineering', 'planning', 'health', 'transit'
      role: one of 'engineer', 'planner', 'health', 'analyst', 'admin'
      zone_id: optional zone filter e.g. 'WR-ZONE-042'. Leave empty for all zones.
      fmt: file format for the download link — 'csv' (default) or 'json'

    Returns clickable URLs: one for a clean browser table view and one to download the file directly."""
    base = BASE
    params = f"role={role}"
    if zone_id:
        params += f"&zone_id={zone_id}"

    view_url = f"{base}/view/{department}?{params}"
    download_url = f"{base}/download/{department}?{params}&fmt={fmt}"

    # Verify the endpoint is reachable and check access level
    try:
        resp = requests.post(f"{base}/query", json={"department": department, "role": role, **({"zone_id": zone_id} if zone_id else {})}, timeout=10)
        result = resp.json()
        access = result.get("access_level", "unknown")
        count = len(result.get("rows", []))
        if access in ("none", "suppressed"):
            return f"Cannot generate download — access level is '{access}': {result.get('note', '')}"
        status = f"Access level: {access} | {count} records available"
    except Exception as e:
        status = f"(Could not pre-check access: {e})"

    zone_note = f" filtered to {zone_id}" if zone_id else ""
    return (
        f"{status}\n\n"
        f"**{department.title()} data{zone_note} — role: {role}**\n\n"
        f"- [Open in browser (table view)]({view_url})\n"
        f"- [Download {fmt.upper()}]({download_url})\n\n"
        f"These links open directly in a browser tab. The data is RBAC-filtered to your role."
    )


@tool
def audit_tool(limit: int = 10) -> str:
    """Retrieve the governance audit log showing recent data access history.
    Use this to demonstrate data governance — who accessed what, with what role,
    and what privacy level was applied. Call this at the end of each analysis."""
    resp = requests.get(f"{BASE}/audit?limit={limit}", timeout=10)
    log = resp.json().get("log", [])
    if not log:
        return "Audit log is empty."
    lines = ["Recent data access log:"]
    for entry in log:
        suppressed = " [SUPPRESSED]" if entry["suppressed"] else ""
        lines.append(
            f"  {entry['timestamp'][:19]} | role={entry['requester_role']} | "
            f"dept={entry['department']} | zone={entry['zone_filter']} | "
            f"access={entry['access_level_applied']} | "
            f"records={entry['record_count']}{suppressed}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Real Open Data Tools (ArcGIS - Region of Waterloo / City of Kitchener)
# ---------------------------------------------------------------------------

@tool
def opendata_catalog() -> str:
    """List available real open data datasets from Region of Waterloo and
    City of Kitchener ArcGIS portals. Use this to discover what real
    municipal data is available."""
    resp = requests.get(f"{BASE}/opendata/datasets", timeout=10)
    data = resp.json()
    lines = ["Available Open Data from Region of Waterloo / Kitchener:"]
    for ds in data["datasets"]:
        lines.append(
            f"\n- {ds['name']} (id: {ds['id']})"
            f"\n  Source: {ds['source']}"
            f"\n  Description: {ds['description']}"
            f"\n  Fields: {', '.join(ds['fields'][:6])}..."
        )
    return "\n".join(lines)


@tool
def query_building_permits(
    permit_no: str = "",
    permit_type: str = "",
    status: str = "",
    min_value: float = 0,
    issued_by: str = "",
    issue_year: int = 0,
    limit: int = 20
) -> str:
    """Query building permits from the local replica database (City of Kitchener).
    This queries the aggregated local database which has ALL 46 fields including
    issued_by, contractor, permit_fee, work_type, etc.

    Parameters:
      permit_no: Exact permit number to look up (e.g., '99100011')
      permit_type: Filter by type (e.g., 'Residential', 'Commercial', 'Alteration')
      status: Filter by status (e.g., 'Issued', 'Closed', 'In Review')
      min_value: Minimum construction value in dollars
      issued_by: Filter by issuing officer name
      issue_year: Filter by year issued (e.g., 2024)
      limit: Max records to return (default 20)

    Returns permit data including ALL fields: permit_no, permit_type, permit_status,
    issued_by, construction_value, contractor, applicant, work_type, and more."""
    params = {"limit": limit}
    if permit_no:
        params["permit_no"] = permit_no
    if permit_type:
        params["permit_type"] = permit_type
    if status:
        params["status"] = status
    if min_value > 0:
        params["min_value"] = min_value
    if issued_by:
        params["issued_by"] = issued_by
    if issue_year > 0:
        params["issue_year"] = issue_year

    resp = requests.get(f"{BASE}/replica/permits", params=params, timeout=30)
    data = resp.json()

    if data["record_count"] == 0:
        return "No permits found matching the criteria."

    lines = [f"Building Permits from {data['source']} ({data['record_count']} records):"]
    for p in data["features"][:10]:
        value = p.get("construction_value")
        value_str = f"${value:,.0f}" if value else "N/A"
        issued_by_str = p.get("issued_by") or "N/A"
        lines.append(
            f"  - Permit {p.get('permit_no')}: {p.get('permit_type')}"
            f"\n    Status: {p.get('permit_status')} | Value: {value_str}"
            f"\n    Issued by: {issued_by_str} | Year: {p.get('issue_year')}"
            f"\n    Applicant: {p.get('applicant') or 'N/A'}"
            f"\n    Contractor: {p.get('contractor') or 'N/A'}"
            f"\n    Work Type: {p.get('work_type') or 'N/A'}"
        )
    if data["record_count"] > 10:
        lines.append(f"  ... and {data['record_count'] - 10} more permits")
    return "\n".join(lines)


@tool
def download_permits(
    permit_type: str = "",
    status: str = "",
    min_value: float = 0,
    issued_by: str = "",
    issue_year: int = 0,
    fmt: str = "csv"
) -> str:
    """Generate a download link for building permits from the local replica.
    Use this when the user wants to download, export, or get a CSV/JSON of permits.

    Parameters:
      permit_type: Filter by type (e.g., 'Residential', 'Commercial')
      status: Filter by status (e.g., 'Issued', 'Closed')
      min_value: Minimum construction value in dollars
      issued_by: Filter by issuing officer name
      issue_year: Filter by year issued (e.g., 2024)
      fmt: 'csv' or 'json' (default: csv)

    Returns a download link that the user can click to get the file."""
    params = []
    if permit_type:
        params.append(f"permit_type={permit_type}")
    if status:
        params.append(f"status={status}")
    if min_value > 0:
        params.append(f"min_value={min_value}")
    if issued_by:
        params.append(f"issued_by={issued_by}")
    if issue_year > 0:
        params.append(f"issue_year={issue_year}")
    params.append(f"fmt={fmt}")

    query_string = "&".join(params)
    download_url = f"{BASE}/replica/permits/download?{query_string}"

    # Get count from the search endpoint
    search_params = {"limit": 1}
    if permit_type:
        search_params["permit_type"] = permit_type
    if status:
        search_params["status"] = status
    if min_value > 0:
        search_params["min_value"] = min_value
    if issued_by:
        search_params["issued_by"] = issued_by
    if issue_year > 0:
        search_params["issue_year"] = issue_year

    try:
        # Get stats to show record count
        resp = requests.get(f"{BASE}/replica/stats", timeout=10)
        stats = resp.json()
        total = stats["tables"].get("building_permits", 0)
    except Exception:
        total = "unknown"

    filters = []
    if permit_type:
        filters.append(f"type={permit_type}")
    if status:
        filters.append(f"status={status}")
    if issue_year > 0:
        filters.append(f"year={issue_year}")
    if issued_by:
        filters.append(f"issued_by={issued_by}")
    filter_str = ", ".join(filters) if filters else "no filters (all permits)"

    return (
        f"**Building Permits Download**\n\n"
        f"Filters: {filter_str}\n"
        f"Total permits in database: {total:,}\n"
        f"Format: {fmt.upper()}\n\n"
        f"[Download {fmt.upper()} File]({download_url})\n\n"
        f"Click the link above to download the file directly."
    )


@tool
def download_water_mains(
    pressure_zone: str = "",
    material: str = "",
    min_criticality: int = 0,
    fmt: str = "csv"
) -> str:
    """Generate a download link for water mains data from the local replica.

    Parameters:
      pressure_zone: Filter by pressure zone
      material: Filter by pipe material (e.g., 'DI', 'PVC', 'CI')
      min_criticality: Minimum criticality score (0-10)
      fmt: 'csv' or 'json' (default: csv)

    Returns a download link for the water mains data."""
    params = []
    if pressure_zone:
        params.append(f"pressure_zone={pressure_zone}")
    if material:
        params.append(f"material={material}")
    if min_criticality > 0:
        params.append(f"min_criticality={min_criticality}")
    params.append(f"fmt={fmt}")

    query_string = "&".join(params)
    download_url = f"{BASE}/replica/water-mains/download?{query_string}"

    try:
        resp = requests.get(f"{BASE}/replica/stats", timeout=10)
        stats = resp.json()
        total = stats["tables"].get("water_mains", 0)
    except Exception:
        total = "unknown"

    filters = []
    if pressure_zone:
        filters.append(f"zone={pressure_zone}")
    if material:
        filters.append(f"material={material}")
    if min_criticality > 0:
        filters.append(f"criticality>={min_criticality}")
    filter_str = ", ".join(filters) if filters else "no filters (all water mains)"

    return (
        f"**Water Mains Download**\n\n"
        f"Filters: {filter_str}\n"
        f"Total water mains in database: {total:,}\n"
        f"Format: {fmt.upper()}\n\n"
        f"[Download {fmt.upper()} File]({download_url})\n\n"
        f"Click the link above to download the file directly."
    )


@tool
def download_bus_stops(
    municipality: str = "",
    ixpress_only: bool = False,
    fmt: str = "csv"
) -> str:
    """Generate a download link for bus stops data from the local replica.

    Parameters:
      municipality: Filter by city (e.g., 'KITCHENER', 'WATERLOO')
      ixpress_only: If true, only include iXpress stops
      fmt: 'csv' or 'json' (default: csv)

    Returns a download link for the bus stops data."""
    params = []
    if municipality:
        params.append(f"municipality={municipality}")
    if ixpress_only:
        params.append("ixpress_only=true")
    params.append(f"fmt={fmt}")

    query_string = "&".join(params)
    download_url = f"{BASE}/replica/bus-stops/download?{query_string}"

    try:
        resp = requests.get(f"{BASE}/replica/stats", timeout=10)
        stats = resp.json()
        total = stats["tables"].get("bus_stops", 0)
    except Exception:
        total = "unknown"

    filters = []
    if municipality:
        filters.append(f"municipality={municipality}")
    if ixpress_only:
        filters.append("iXpress only")
    filter_str = ", ".join(filters) if filters else "no filters (all stops)"

    return (
        f"**Bus Stops Download**\n\n"
        f"Filters: {filter_str}\n"
        f"Total bus stops in database: {total:,}\n"
        f"Format: {fmt.upper()}\n\n"
        f"[Download {fmt.upper()} File]({download_url})\n\n"
        f"Click the link above to download the file directly."
    )


@tool
def lookup_permit(permit_no: str) -> str:
    """Look up a specific building permit by its permit number.
    Returns ALL available fields for that permit including issued_by,
    contractor, applicant, construction_value, work_type, etc.

    Parameters:
      permit_no: The permit number to look up (e.g., '99100011')

    Returns complete permit details with all 46 fields."""
    resp = requests.get(f"{BASE}/replica/permits/{permit_no}", timeout=30)

    if resp.status_code == 404:
        return f"Permit {permit_no} not found in the database."

    data = resp.json()
    p = data["permit"]

    lines = [f"=== Permit {permit_no} Details ==="]
    lines.append(f"Source: {data['source']}")
    lines.append("")

    # Core info
    lines.append(f"Type: {p.get('permit_type') or 'N/A'}")
    lines.append(f"Status: {p.get('permit_status') or 'N/A'}")
    lines.append(f"Work Type: {p.get('work_type') or 'N/A'}")
    lines.append(f"Sub Work Type: {p.get('sub_work_type') or 'N/A'}")
    lines.append(f"Description: {p.get('permit_description') or 'N/A'}")
    lines.append("")

    # Value and fees
    value = p.get('construction_value')
    fee = p.get('permit_fee')
    lines.append(f"Construction Value: ${value:,.0f}" if value else "Construction Value: N/A")
    lines.append(f"Permit Fee: ${fee:,.0f}" if fee else "Permit Fee: N/A")
    lines.append("")

    # Dates
    lines.append(f"Application Date: {p.get('application_date') or 'N/A'}")
    lines.append(f"Issue Date: {p.get('issue_date') or 'N/A'}")
    lines.append(f"Issue Year: {int(p.get('issue_year')) if p.get('issue_year') else 'N/A'}")
    lines.append(f"Final Date: {p.get('final_date') or 'N/A'}")
    lines.append(f"Expiry Date: {p.get('expiry_date') or 'N/A'}")
    lines.append("")

    # People
    lines.append(f"Issued By: {p.get('issued_by') or 'N/A'}")
    lines.append(f"Applicant: {p.get('applicant') or 'N/A'}")
    lines.append(f"Owners: {p.get('owners') or 'N/A'}")
    lines.append(f"Contractor: {p.get('contractor') or 'N/A'}")
    lines.append(f"Contractor Contact: {p.get('contractor_contact') or 'N/A'}")
    lines.append("")

    # Location
    lines.append(f"Folder Name: {p.get('folder_name') or 'N/A'}")
    lines.append(f"Legal Description: {p.get('legal_description') or 'N/A'}")
    lines.append(f"Roll No: {p.get('roll_no') or 'N/A'}")
    lines.append("")

    # Units
    lines.append(f"Total Units: {p.get('total_units') or 'N/A'}")
    lines.append(f"Units Created: {p.get('units_created') or 'N/A'}")
    lines.append(f"Units Lost: {p.get('units_lost') or 'N/A'}")
    lines.append(f"Units Net Change: {p.get('units_net_change') or 'N/A'}")

    return "\n".join(lines)


@tool
def query_water_infrastructure(
    pressure_zone: str = "",
    material: str = "",
    min_criticality: int = 0,
    limit: int = 20
) -> str:
    """Query real water main infrastructure from City of Kitchener open data.

    Parameters:
      pressure_zone: Filter by pressure zone (e.g., 'KIT 2E', 'MANNHEIM')
      material: Filter by pipe material (e.g., 'DI', 'PVC', 'CI', 'AC')
      min_criticality: Minimum criticality score (0-10, higher = more critical)
      limit: Max records to return (default 20)

    Returns actual water main data including pipe size, material, and condition."""
    params = {"limit": limit}
    if pressure_zone:
        params["pressure_zone"] = pressure_zone
    if material:
        params["material"] = material
    if min_criticality > 0:
        params["min_criticality"] = min_criticality

    resp = requests.get(f"{BASE}/opendata/water-mains", params=params, timeout=30)
    data = resp.json()

    lines = [f"Water Mains from {data['source']} ({data['record_count']} records):"]

    # Summarize by material
    materials = {}
    criticalities = []
    for m in data["features"]:
        mat = m.get("MATERIAL", "UNKNOWN")
        materials[mat] = materials.get(mat, 0) + 1
        if m.get("CRITICALITY") is not None:
            criticalities.append(m["CRITICALITY"])

    lines.append(f"  Materials: {materials}")
    if criticalities:
        avg_crit = sum(criticalities) / len(criticalities)
        lines.append(f"  Avg Criticality: {avg_crit:.2f} (scale 0-10)")

    # Show sample records
    lines.append("\n  Sample records:")
    for m in data["features"][:5]:
        lines.append(
            f"    - Size: {m.get('PIPE_SIZE')}mm | Material: {m.get('MATERIAL')} | "
            f"Zone: {m.get('PRESSURE_ZONE')} | Criticality: {m.get('CRITICALITY')}"
        )
    return "\n".join(lines)


@tool
def query_transit_stops(
    municipality: str = "",
    ixpress_only: bool = False,
    limit: int = 50
) -> str:
    """Query real GRT bus stop locations from Region of Waterloo open data.

    Parameters:
      municipality: Filter by city (e.g., 'KITCHENER', 'WATERLOO', 'CAMBRIDGE')
      ixpress_only: If true, only return iXpress rapid transit stops
      limit: Max records to return (default 50)

    Returns actual bus stop data including location and route info."""
    params = {"limit": limit}
    if municipality:
        params["municipality"] = municipality
    if ixpress_only:
        params["ixpress_only"] = "true"

    resp = requests.get(f"{BASE}/opendata/transit-stops", params=params, timeout=30)
    data = resp.json()

    lines = [f"GRT Bus Stops from {data['source']} ({data['record_count']} records):"]

    # Count by municipality
    munis = {}
    ixpress_count = 0
    for s in data["features"]:
        muni = s.get("MUNICIPALITY", "UNKNOWN")
        munis[muni] = munis.get(muni, 0) + 1
        if s.get("IXPRESS") == "Y":
            ixpress_count += 1

    lines.append(f"  By Municipality: {munis}")
    lines.append(f"  iXpress Stops: {ixpress_count}")

    # Show sample stops
    lines.append("\n  Sample stops:")
    for s in data["features"][:8]:
        ixpress = " [iXpress]" if s.get("IXPRESS") == "Y" else ""
        lines.append(
            f"    - Stop {s.get('STOP_ID')}: {s.get('STREET')} @ {s.get('CROSSSTREET')}{ixpress}"
        )
    return "\n".join(lines)


@tool
def infrastructure_summary(zone: str = "") -> str:
    """Get a cross-dataset infrastructure summary combining water, permits, and transit.

    Parameters:
      zone: Optional pressure zone filter for water mains

    Returns aggregated statistics across all open data sources."""
    params = {}
    if zone:
        params["zone"] = zone

    resp = requests.get(f"{BASE}/opendata/infrastructure-summary", params=params, timeout=60)
    data = resp.json()

    lines = ["=== Infrastructure Summary (Real Open Data) ==="]

    # Water mains
    wm = data["water_mains"]
    lines.append(f"\nWATER INFRASTRUCTURE:")
    lines.append(f"  Total mains: {wm['total']}")
    lines.append(f"  Avg criticality: {wm['avg_criticality']:.2f}")
    lines.append(f"  By material: {wm['by_material']}")

    # Permits
    pm = data["permits"]
    lines.append(f"\nBUILDING PERMITS:")
    lines.append(f"  Total permits: {pm['total']}")
    lines.append(f"  Total construction value: ${pm['total_value']:,.0f}")
    lines.append(f"  By status: {pm['by_status']}")

    # Transit
    tr = data["transit"]
    lines.append(f"\nTRANSIT:")
    lines.append(f"  Total bus stops: {tr['total_stops']}")
    lines.append(f"  iXpress stops: {tr['ixpress_stops']}")

    return "\n".join(lines)
