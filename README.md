# CityMind — City Data OS

**The Secure Data Nervous System for Waterloo Region**

> FCI × LangChain Hackathon · March 2026 · Problem Statement #2
> *Build the Blueprint for Municipal Data Infrastructure*

---

## What Is CityMind?

CityMind is a federated municipal data platform that lets different city departments share data while maintaining departmental autonomy and enforcing privacy at the query layer. Instead of forcing all departments into a single monolithic system, CityMind provides:

- A **unified data catalog** to discover what exists across departments
- A **privacy gateway** (RBAC) that enforces per-role, per-department access rules
- A **governance dashboard** with data quality scoring, audit logging, and a data dictionary
- A **real open data backend** synced from the City of Kitchener ArcGIS API
- A **citizen-facing portal** for public data access with plain-language labels

---

## Architecture

```
React + Vite (port 5173)
    │   8 pages: Dashboard · Dictionary · Audit Log · Explorer
    │             Cross Analysis · Citizen Portal · Map View · Sync Status
    │
    ▼ (proxied via Vite dev server)
FastAPI (port 8000)
    │
    ├── /catalog/*        → Dataset catalog (catalog.json)
    ├── /query            → RBAC-filtered department query
    ├── /query/cross      → Cross-departmental unified query
    ├── /download/*       → CSV / JSON / GeoJSON export
    ├── /audit            → Governance audit log
    ├── /geo/bus-stops    → Bus stop GeoJSON (from ArcGIS)
    ├── /sync/*           → Sync status + trigger (background)
    └── /health           → Health check
         │
         ▼
    privacy.py (apply_privacy)
         │  RBAC matrix: role × department → full | read | aggregated | anonymized | suppressed | none
         │  PII stripping · small-cell suppression (< 5 records)
         │
         ▼
    SQLite replica (db/opendata_replica.db)
         │  building_permits  — 74,565 rows (City of Kitchener)
         │  water_mains       — 16,163 rows (City of Kitchener)
         └─ bus_stops         —  1,178 rows (GRT / Region of Waterloo)

ArcGIS Sync (sync/)
    Kitchener open data portal → paginated fetch → upsert into replica
```

---

## Real Data

All data is sourced from the City of Kitchener open data portal (ArcGIS Feature Server):

| Dataset | Table | Records | Source URL |
|---|---|---|---|
| Building Permits | `building_permits` | 74,565 | `services1.arcgis.com/.../Building_Permits` |
| Water Mains | `water_mains` | 16,163 | `services1.arcgis.com/.../Water_Mains` |
| Bus Stops | `bus_stops` | 1,178 | `services1.arcgis.com/.../Bus_Stop` |

---

## RBAC Matrix

| Role | Engineering | Planning | Transit |
|---|---|---|---|
| **admin** | full | full | full |
| **engineer** | full | read | read |
| **planner** | aggregated | full | read |
| **health** | aggregated | read | read |
| **analyst** | anonymized | read | read |

Access levels:
- **full** — all fields, all rows (PII included for planning)
- **read** — all rows, PII fields stripped
- **aggregated** — grouped summary (no individual rows)
- **anonymized** — all rows, PII stripped (same as read but labelled)
- **suppressed** — result withheld (fewer than 5 records returned)
- **none** — access denied

Every query is logged to `db/audit.db` with role, department, access level, and row count.

---

## Setup

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Copy and configure environment variables
cp ../.env.example ../.env

# Run the ArcGIS sync to populate the local replica (first time only)
python -c "from sync.orchestrator import SyncOrchestrator; o = SyncOrchestrator(); o.init_database(); o.sync_all()"

# Start the API server
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

### Running Tests

```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check + version |
| GET | `/catalog` | List all datasets with metadata |
| GET | `/catalog/{dataset_id}` | Single dataset metadata |
| POST | `/catalog/search` | Search by query, tags, department |
| GET | `/catalog/quality` | Quality scores + field-level null % |
| GET | `/catalog/dictionary` | Shared field definitions |
| POST | `/catalog/datasets` | Add/update dataset (admin role) |
| POST | `/query` | RBAC-filtered department query |
| POST | `/query/cross` | Cross-departmental unified query |
| GET | `/audit` | Governance audit log |
| GET | `/download/{department}` | Export CSV / JSON / GeoJSON |
| GET | `/geo/bus-stops` | Bus stop GeoJSON from ArcGIS |
| GET | `/sync/status` | Replica DB stats + last sync times |
| GET | `/sync/runs` | Recent sync run history |
| POST | `/sync/trigger` | Trigger background sync |

All responses include the `X-CityMind-Version: 1.0` header.

---

## Frontend Pages

| Page | Route | Description |
|---|---|---|
| Data Quality | `/#/dashboard` | Quality scores, staleness, field completeness |
| Data Dictionary | `/#/dictionary` | Field definitions, privacy levels |
| Audit Log | `/#/audit` | All queries with role, access level, suppression |
| Dataset Explorer | `/#/explorer` | RBAC query tool with filters + download |
| Cross Analysis | `/#/cross-analysis` | All depts in one view, RBAC per dept |
| Citizen Portal | `/#/citizen` | Public-facing, plain-language, no PII |
| Map View | `/#/map` | Bus stop map (Leaflet + ArcGIS geometry) |
| Sync Status | `/#/sync-status` | Sync health, run history, trigger |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite 5 + React Router v6 |
| Map | Leaflet + react-leaflet |
| Backend | FastAPI (Python 3.11+) |
| Database | SQLite (local ArcGIS replica) |
| Sync | httpx + custom ArcGIS paginator |
| Tests | pytest + FastAPI TestClient |

---

## Privacy Design

- **RBAC enforced at the gateway** — privacy filtering runs before any data is returned
- **PII stripping** — owner names, applicants, contractors, legal descriptions stripped for non-full roles
- **Small-cell suppression** — results with fewer than 5 records are withheld entirely
- **Audit everything** — every query logged with role, department, access level, suppression flag
- **SQL injection prevention** — filter fields validated against a per-department whitelist before query execution
- **GeoJSON output** — spatial data returned with null geometry if local replica has no coordinates

---

## Key Design Decisions

- **Catalog as data** (`catalog.json`) — datasets are registered in a JSON file, not hardcoded Python. Add new departments by editing the file.
- **Federated by design** — each department can be backed by a separate DB; the `DB_MAP` in `main.py` is the only integration point.
- **Incremental sync** — ArcGIS data is pulled via paginated HTTP requests and upserted; re-running sync doesn't duplicate data.
- **Standards-based** — GeoJSON output, ISO 8601 dates, OpenStreetMap tiles (no proprietary dependencies).

---

## Ethical Considerations

CityMind is built with a privacy-first philosophy:
- No personal information is exposed to roles without explicit need
- All data access is logged and reviewable
- Suppression prevents re-identification from small result sets
- Public-facing portal only exposes sensitivity=public datasets
