# backend/privacy.py

ROLE_ACCESS = {
    "engineer": {
        "engineering": "full",
        "planning": "read",
        "transit": "read",
    },
    "planner": {
        "engineering": "aggregated",
        "planning": "full",
        "transit": "read",
    },
    "health": {
        "engineering": "aggregated",
        "planning": "read",
        "transit": "read",
    },
    "analyst": {
        "engineering": "anonymized",
        "planning": "read",
        "transit": "read",
    },
    "admin": {
        "engineering": "full",
        "planning": "full",
        "transit": "full",
    },
}

# Fields to always strip regardless of role
STRIP_ALWAYS = ["source_id", "synced_at"]

# PII fields stripped for non-full access levels
PII_FIELDS = {
    "planning": {"owners", "applicant", "contractor", "contractor_contact",
                 "roll_no", "legal_description", "parcel_id", "folder_rsn"},
    "engineering": set(),
    "transit": set(),
}

# Field to group by when aggregating
AGGREGATE_KEY = {
    "planning": "permit_type",
    "engineering": "pressure_zone",
    "transit": "municipality",
}

# Numeric fields to average when aggregating
NUMERIC_FIELDS = {
    "planning": ["construction_value"],
    "engineering": ["pipe_size", "criticality"],
    "transit": [],
}

# Minimum records before suppression kicks in
SUPPRESSION_THRESHOLD = 5


def apply_privacy(rows: list, dept: str, role: str) -> dict:
    access = ROLE_ACCESS.get(role, {}).get(dept, "none")

    if access == "none":
        return {
            "rows": [],
            "access_level": "none",
            "note": f"Role '{role}' has no access to {dept} data.",
        }

    # Strip universal internal fields
    cleaned = [{k: v for k, v in r.items() if k not in STRIP_ALWAYS} for r in rows]

    pii = PII_FIELDS.get(dept, set())

    if access == "full":
        return {"rows": cleaned, "access_level": "full"}

    if access == "read":
        stripped = [{k: v for k, v in r.items() if k not in pii} for r in cleaned]
        return {"rows": stripped, "access_level": "read"}

    if access == "aggregated":
        group_key = AGGREGATE_KEY.get(dept, "status")
        numeric = NUMERIC_FIELDS.get(dept, [])
        summary = {}
        for r in cleaned:
            key_val = r.get(group_key, "unknown") or "unknown"
            if key_val not in summary:
                summary[key_val] = {group_key: key_val, "record_count": 0}
                for f in numeric:
                    summary[key_val][f"avg_{f}"] = 0.0
            summary[key_val]["record_count"] += 1
            for f in numeric:
                v = r.get(f)
                if isinstance(v, (int, float)) and v is not None:
                    n = summary[key_val]["record_count"]
                    prev = summary[key_val][f"avg_{f}"]
                    summary[key_val][f"avg_{f}"] = round((prev * (n - 1) + v) / n, 2)
        rows_out = list(summary.values())
        if len(rows_out) < SUPPRESSION_THRESHOLD:
            return {
                "rows": [],
                "access_level": "suppressed",
                "note": f"Result suppressed: fewer than {SUPPRESSION_THRESHOLD} aggregation groups returned.",
            }
        return {"rows": rows_out, "access_level": "aggregated"}

    if access == "anonymized":
        stripped = [{k: v for k, v in r.items() if k not in pii} for r in cleaned]
        if len(stripped) < SUPPRESSION_THRESHOLD:
            return {
                "rows": [],
                "access_level": "suppressed",
                "note": f"Result suppressed: fewer than {SUPPRESSION_THRESHOLD} records returned.",
            }
        return {"rows": stripped, "access_level": "anonymized"}

    return {"rows": [], "access_level": "denied"}
