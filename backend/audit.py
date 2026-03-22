# backend/audit.py
import sqlite3
from datetime import datetime


def _conn():
    c = sqlite3.connect("db/audit.db")
    c.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        query_id TEXT PRIMARY KEY,
        timestamp TEXT,
        requester_role TEXT,
        department TEXT,
        zone_filter TEXT,
        access_level_applied TEXT,
        record_count INTEGER,
        suppressed INTEGER
    )""")
    c.commit()
    return c


def log_query(entry: dict):
    c = _conn()
    c.execute(
        "INSERT INTO audit_log VALUES (?,?,?,?,?,?,?,?)",
        (
            entry["query_id"],
            datetime.now().isoformat(),
            entry["requester_role"],
            entry["department"],
            entry["zone_filter"],
            entry["access_level_applied"],
            entry["record_count"],
            int(entry["suppressed"]),
        ),
    )
    c.commit()
    c.close()
