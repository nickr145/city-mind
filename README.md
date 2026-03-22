# CityMind — City Data OS

**The Secure Data Nervous System for Waterloo Region**

> FCI × LangChain Hackathon · March 2026 · Problem Statement #2
> *Build the Blueprint for Municipal Data Infrastructure*

---

## What Is CityMind?

CityMind is a **federated municipal data infrastructure prototype** — the secure data nervous system that lets planning, transit, engineering, and health finally think as one city.

Departments keep their existing systems. CityMind adds the missing layer:

- **Federated Data Catalog** — shared schema registry, discoverability, data stewardship
- **RBAC Privacy Gateway** — role-based field filtering, anonymization, small-cell suppression, PII stripping on every query
- **Governance Audit Log** — every query logged: requester role, datasets touched, fields returned, anonymization applied
- **AI Query Interface** — DeepAgents + Claude translates natural-language planning questions into governed, cross-departmental answers

### Real-World Anchor

The Region paused housing development due to untracked water capacity — because engineering and planning data were never connected. CityMind makes that connection safe, governed, and queryable.

---

## Architecture

```
LangGraph Studio (browser UI — AI query interface + live agent trace)
        |
        v
DeepAgents AI Layer  (create_deep_agent · Claude claude-sonnet-4-20250514)
  |-- catalog_tool   "What data exists? Which departments have capacity data?"
  |-- query_tool     "Query engineering + planning for zone WR-ZONE-042, role=planner"
  |-- audit_tool     "Show me the last 10 data accesses"
        |
        v
FastAPI Privacy & Catalog Gateway  (localhost:8000)
  POST /query    -- RBAC filter + anonymize + log every access
  GET  /catalog  -- list registered datasets + schemas
  GET  /audit    -- governance dashboard: who accessed what
        |
   RBAC Privacy Layer
   role=engineer -> engineering:full  | planning:read    | health:NONE    | transit:read
   role=planner  -> engineering:agg   | planning:full    | health:zone_agg | transit:full
   role=health   -> engineering:agg   | planning:summary | health:full    | transit:agg
   role=analyst  -> engineering:anon  | planning:anon    | health:NONE    | transit:anon
        |
        v
Department SQLite Databases  (simulated Waterloo Region zone data)
  engineering.db -- water_capacity: zone_id, capacity_pct, condition_score, upgrade_year
  planning.db    -- permits: zone_id, permit_type, unit_count, density_approved, status
  health.db      -- zone_health: zone_id, er_utilization_pct, vulnerability_index, clinic_count
  transit.db     -- routes: zone_id, route_id, corridor, frequency_min, avg_ridership
```

**Key design:** Federated by design — no department's data is copied into a central warehouse. The catalog knows what exists. The privacy layer controls what is returned. Sensitive data never leaves departmental control.

---

## Setup

### Prerequisites

- Python 3.11+
- `ANTHROPIC_API_KEY` (from [console.anthropic.com](https://console.anthropic.com))
- `LANGSMITH_API_KEY` (optional — for LangGraph Studio tracing)

### Install

```bash
git clone <repo-url>
cd city-mind

python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY (and optionally LANGSMITH_API_KEY)
```

### Seed databases

```bash
cd backend
python seed.py
# Output: All 4 department databases seeded.
cd ..
```

### Run

You need **two terminals** running simultaneously:

**Terminal 1 — FastAPI backend:**
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Terminal 2 — DeepAgents + LangGraph Studio:**
```bash
source venv/bin/activate
langgraph dev
# Open: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

---

## Demo Queries

Run these in LangGraph Studio (or via `fallback_demo.py`):

### Query 1 — Coordinated Infrastructure Planning (role=planner)
```
What is the water infrastructure readiness for the Uptown Waterloo corridor?
I am a city planner reviewing development permit applications.
```
**What to expect:** Agent queries catalog → queries engineering (gets capacity *bands*, not raw %) → queries planning (full permit data) → queries transit (full) → shows audit log. Demonstrates RBAC in action.

### Query 2 — Public Health Surveillance (role=health)
```
What are the environmental and infrastructure risk factors in zone WR-ZONE-042?
I am a public health official investigating a potential disease cluster.
```
**What to expect:** Health official gets full health data, aggregated engineering, zone-summary planning. No PII exposed. Small-cell suppression check runs. Audit trail logged.

### Query 3 — Housing Affordability Analysis (role=analyst)
```
Which zones have both high development pressure from permits and high
infrastructure strain? Give me a cross-department overview.
```
**What to expect:** All data anonymized/aggregated. Health data blocked (analyst role). Suppression check on all zones. Cross-department pattern analysis with full governance trail.

---

## RBAC Role Matrix

| Role | Engineering | Planning | Health | Transit |
|------|-------------|----------|--------|---------|
| engineer | Full | Read-only | No access | Read-only |
| planner | Aggregated (bands) | Full | Zone aggregates | Full |
| health | Aggregated | Zone summary | Full | Aggregated |
| analyst | Anonymized | Anonymized | No access | Anonymized |
| admin | Full + audit log | Full + audit log | Full + audit log | Full + audit log |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/catalog` | List all registered datasets |
| GET | `/catalog/{id}` | Get dataset metadata |
| POST | `/catalog/search` | Search by tags or department |
| GET | `/catalog/dictionary` | Shared field definitions |
| GET | `/catalog/quality` | Flag stale datasets |
| POST | `/query` | Federated query with RBAC enforcement |
| GET | `/audit` | Governance audit log |
| GET | `/health` | Health check |

### Example `/query` request

```bash
# Planner querying engineering (gets capacity bands, not raw %)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"role":"planner","department":"engineering","zone_id":"WR-ZONE-042"}'

# Engineer querying own dept (gets full data)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"role":"engineer","department":"engineering","zone_id":"WR-ZONE-042"}'

# Analyst querying health (ACCESS DENIED by design)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"role":"analyst","department":"health"}'
```

---

## Fallback Demo (no LangGraph Studio)

```bash
python fallback_demo.py
```

Runs all 3 demo queries directly from the terminal — use this if LangGraph Studio is unavailable.

---

## PS#2 Requirement Checklist

| PS#2 Requirement | CityMind Component | Status |
|---|---|---|
| Unified data architecture | Federated Data Catalog (FastAPI) — shared schemas, dept connectors, common `zone_id` key | ✅ MVP |
| Privacy and confidentiality by design | RBAC Privacy Gateway — role-based field filtering, anonymization, small-cell suppression | ✅ MVP |
| Interoperability standards | Common base schema across all 4 dept SQLite databases — shared fields: `zone_id`, `department`, `sensitivity_level`, `timestamp` | ✅ MVP |
| Data governance framework | Audit Log — every query logged: requester role, datasets touched, fields returned, anonymization applied | ✅ MVP |
| Incremental implementation pathway | Pilot: Engineering + Planning. Scale: Health + Transit. Architecture supports N departments. | ✅ MVP |

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| Agent Harness | deepagents — `create_deep_agent()` built on LangGraph |
| LLM | Anthropic Claude API — `claude-sonnet-4-20250514` |
| API Gateway | FastAPI + Uvicorn |
| Department Data | SQLite — 4 simulated dept databases |
| Privacy Layer | Python FastAPI middleware — RBAC, field filtering, anonymization, small-cell suppression |
| Agent Runtime | LangGraph — `langgraph-cli[inmem]` · UI: LangGraph Studio |
| Observability | LangSmith (agent tracing) + SQLite audit table (governance log) |

---

## Ethical Considerations

- **Privacy is structural, not procedural:** anonymization and RBAC are enforced at the API gateway. The AI agent cannot retrieve PII even if it attempts to.
- **Small-cell suppression:** any query returning fewer than 5 records in a zone is automatically suppressed and flagged.
- **Audit accountability:** every data access is permanently logged. Data stewards can review all access to their department's data at any time.
- **Federated not centralised:** sensitive data never leaves departmental control. No central data warehouse is created.
- **Synthetic data only:** all department databases contain realistic but entirely synthetic Waterloo Region zone data.

---

*CityMind · FCI × LangChain Hackathon · March 2026 · Problem Statement #2*
