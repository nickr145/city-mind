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
