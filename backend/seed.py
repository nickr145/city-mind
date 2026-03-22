import sqlite3
from datetime import datetime

NOW = datetime.now().isoformat()


def seed_engineering():
    c = sqlite3.connect("db/engineering.db")
    c.execute("""CREATE TABLE IF NOT EXISTS water_capacity (
        record_id TEXT PRIMARY KEY, zone_id TEXT, department TEXT,
        asset_type TEXT, capacity_pct REAL, condition_score INTEGER,
        upgrade_year INTEGER, last_inspected TEXT,
        sensitivity_level TEXT, timestamp TEXT)""")
    rows = [
        ("ENG-001", "WR-ZONE-001", "engineering", "water_main", 0.86, 3, 2027, "2024-03-15", "internal", NOW),
        ("ENG-002", "WR-ZONE-002", "engineering", "water_main", 0.91, 2, 2025, "2024-01-10", "internal", NOW),
        ("ENG-003", "WR-ZONE-003", "engineering", "pump_station", 0.74, 4, 2029, "2024-06-01", "internal", NOW),
        ("ENG-004", "WR-ZONE-042", "engineering", "water_main", 0.97, 2, 2024, "2023-11-20", "internal", NOW),
        ("ENG-005", "WR-ZONE-005", "engineering", "reservoir", 0.62, 5, 2031, "2024-08-12", "internal", NOW),
        ("ENG-006", "WR-ZONE-006", "engineering", "water_main", 0.78, 3, 2028, "2024-05-30", "internal", NOW),
    ]
    c.executemany("INSERT OR REPLACE INTO water_capacity VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    c.commit()
    c.close()


def seed_planning():
    c = sqlite3.connect("db/planning.db")
    c.execute("""CREATE TABLE IF NOT EXISTS permits (
        record_id TEXT PRIMARY KEY, zone_id TEXT, department TEXT,
        permit_type TEXT, zoning_class TEXT, unit_count INTEGER,
        status TEXT, density_approved REAL,
        sensitivity_level TEXT, timestamp TEXT)""")
    rows = [
        ("PLN-001", "WR-ZONE-001", "planning", "infill", "R4", 42, "approved", 85.0, "public", NOW),
        ("PLN-002", "WR-ZONE-001", "planning", "infill", "R4", 18, "pending", 85.0, "public", NOW),
        ("PLN-003", "WR-ZONE-002", "planning", "subdivision", "R2", 120, "approved", 35.0, "public", NOW),
        ("PLN-004", "WR-ZONE-042", "planning", "infill", "MU-2", 65, "approved", 120.0, "public", NOW),
        ("PLN-005", "WR-ZONE-042", "planning", "infill", "MU-2", 38, "pending", 120.0, "public", NOW),
        ("PLN-006", "WR-ZONE-003", "planning", "commercial", "C1", 0, "approved", 0.0, "public", NOW),
    ]
    c.executemany("INSERT OR REPLACE INTO permits VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    c.commit()
    c.close()


def seed_health():
    c = sqlite3.connect("db/health.db")
    c.execute("""CREATE TABLE IF NOT EXISTS zone_health (
        record_id TEXT PRIMARY KEY, zone_id TEXT, department TEXT,
        er_utilization_pct REAL, clinic_count INTEGER,
        vulnerability_index INTEGER, gp_ratio REAL,
        sensitivity_level TEXT, timestamp TEXT)""")
    rows = [
        ("HLT-001", "WR-ZONE-001", "health", 0.87, 2, 58, 0.9, "confidential", NOW),
        ("HLT-002", "WR-ZONE-002", "health", 0.72, 3, 42, 1.1, "confidential", NOW),
        ("HLT-003", "WR-ZONE-042", "health", 0.93, 1, 71, 0.7, "confidential", NOW),
        ("HLT-004", "WR-ZONE-005", "health", 0.61, 4, 31, 1.4, "confidential", NOW),
        ("HLT-005", "WR-ZONE-003", "health", 0.79, 2, 49, 1.0, "confidential", NOW),
        ("HLT-006", "WR-ZONE-006", "health", 0.68, 3, 38, 1.2, "confidential", NOW),
    ]
    c.executemany("INSERT OR REPLACE INTO zone_health VALUES (?,?,?,?,?,?,?,?,?)", rows)
    c.commit()
    c.close()


def seed_transit():
    c = sqlite3.connect("db/transit.db")
    c.execute("""CREATE TABLE IF NOT EXISTS routes (
        record_id TEXT PRIMARY KEY, zone_id TEXT, department TEXT,
        route_id TEXT, corridor TEXT, frequency_min INTEGER,
        avg_ridership INTEGER, service_level TEXT,
        sensitivity_level TEXT, timestamp TEXT)""")
    rows = [
        ("TRN-001", "WR-ZONE-001", "transit", "RT-7", "Uptown Waterloo King St", 12, 3200, "high", "public", NOW),
        ("TRN-002", "WR-ZONE-002", "transit", "RT-200", "Fairway Station", 20, 1850, "medium", "public", NOW),
        ("TRN-003", "WR-ZONE-042", "transit", "RT-7", "King/Victoria Kitchener", 12, 2900, "high", "public", NOW),
        ("TRN-004", "WR-ZONE-005", "transit", "RT-29", "Columbia/Fischer-Hallman", 25, 980, "low", "public", NOW),
        ("TRN-005", "WR-ZONE-003", "transit", "RT-12", "University Ave", 15, 2100, "high", "public", NOW),
        ("TRN-006", "WR-ZONE-006", "transit", "RT-22", "Ottawa St S", 30, 720, "low", "public", NOW),
    ]
    c.executemany("INSERT OR REPLACE INTO routes VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    c.commit()
    c.close()


if __name__ == "__main__":
    import os
    os.makedirs("db", exist_ok=True)
    seed_engineering()
    seed_planning()
    seed_health()
    seed_transit()
    print("All 4 department databases seeded.")
