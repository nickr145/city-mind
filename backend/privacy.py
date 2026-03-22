# backend/privacy.py
import sqlite3

ROLE_ACCESS = {
    "engineer": {
        "engineering": "full",
        "planning": "read",
        "health": "none",
        "transit": "read",
    },
    "planner": {
        "engineering": "aggregated",
        "planning": "full",
        "health": "aggregated",
        "transit": "full",
    },
    "health": {
        "engineering": "aggregated",
        "planning": "zone_summary",
        "health": "full",
        "transit": "aggregated",
    },
    "analyst": {
        "engineering": "anonymized",
        "planning": "anonymized",
        "health": "none",
        "transit": "anonymized",
    },
    "admin": {
        "engineering": "full",
        "planning": "full",
        "health": "full",
        "transit": "full",
    },
}

STRIP_ALWAYS = ["record_id"]  # never return internal IDs

CAPACITY_BANDS = {
    "engineering": {
        "capacity_pct": lambda v: (
            "Low (<75%)" if v < 0.75 else
            "Medium (75-90%)" if v < 0.90 else
            "High (90-95%)" if v < 0.95 else
            "Critical (95%+)"
        )
    }
}


def apply_privacy(rows: list, dept: str, role: str) -> dict:
    access = ROLE_ACCESS.get(role, {}).get(dept, "none")

    if access == "none":
        return {
            "rows": [],
            "access_level": "none",
            "note": f"Role '{role}' has no access to {dept} data.",
        }

    # Strip universal sensitive fields
    cleaned = [{k: v for k, v in r.items() if k not in STRIP_ALWAYS} for r in rows]

    # Apply capacity banding for non-engineer roles on engineering data
    if dept == "engineering" and role != "engineer":
        bands = CAPACITY_BANDS.get("engineering", {})
        for row in cleaned:
            for field, fn in bands.items():
                if field in row:
                    row[field] = fn(row[field])

    if access in ("full", "read"):
        return {"rows": cleaned, "access_level": access}

    if access == "aggregated":
        summary = {}
        for r in cleaned:
            z = r.get("zone_id", "unknown")
            if z not in summary:
                summary[z] = {"zone_id": z, "department": dept, "record_count": 0}
            summary[z]["record_count"] += 1
            for k, v in r.items():
                if isinstance(v, float) and k != "zone_id":
                    prev_avg = summary[z].get(f"avg_{k}", 0)
                    n = summary[z]["record_count"]
                    summary[z][f"avg_{k}"] = round((prev_avg * (n - 1) + v) / n, 3)
        result = list(summary.values())
        if len(result) < 5:
            return {
                "rows": [],
                "access_level": "suppressed",
                "note": "Small-cell suppression applied: fewer than 5 zones returned.",
            }
        return {"rows": result, "access_level": "aggregated"}

    if access in ("zone_summary", "anonymized"):
        zones = list({r.get("zone_id") for r in cleaned})
        return {
            "rows": [{"zone_id": z, "department": dept} for z in zones],
            "access_level": access,
        }

    return {"rows": [], "access_level": "denied"}
