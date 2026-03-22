## Cole — Database & Backend (already assigned)                                                       
                                                                                                            
  ### Database Layer                                                                                        
  - [ ] Add indexes on `zone_id` in all department tables for faster filtering                              
  - [ ] Add index on `timestamp` in `audit_log` for time-range queries                                      
  - [ ] Replace per-request SQLite connections with a connection pool (e.g. `sqlite3` connection reuse or   
  SQLAlchemy pool)                                                                                          
  - [ ] Add a `migrations/` pattern so schema changes don't require re-seeding                              
  - [ ] Seed more realistic zone data (expand beyond 6 zones, vary ranges more)                             
                                                                                                            
  ### Backend API Hardening                                                                                 
  - [ ] Add Pydantic request/response models to replace raw `dict` type hints throughout `main.py`          
  - [ ] Add query timeout enforcement (kill queries exceeding N seconds)                                    
  - [ ] Add rate limiting on `/query` and `/download` endpoints (e.g. slowapi)                              
  - [ ] Add structured error logging (replace bare `HTTPException` with logged errors)                      
  - [ ] Make `/catalog/quality` return live freshness checks instead of hardcoded logic                     
  - [ ] Fix module import paths so `backend/` can be run from any working directory                         
                                                                                                            
  ---                                                                                                       
                                                                                                            
  ## Nicholas — Frontend / User Interface                                                                   
  
  ### Interactive Query Portal                                                                              
  - [ ] Scaffold a frontend (React or plain HTML+JS) served at a `/ui` route or as a separate app
  - [ ] Build a role selector (dropdown: engineer, planner, health, analyst, admin)                         
  - [ ] Build a natural-language query input box that calls the agent or `/query` directly                  
  - [ ] Display query results in a sortable, filterable table                                               
  - [ ] Show the access level badge (full / aggregated / anonymized / none) per department result           
  - [ ] Add a zone filter input (zone_id selector or multi-select)                                          
                                                                                                            
  ### Results & Export UI                                                                                   
  - [ ] Show download buttons (CSV / JSON) wired to `/download/{dept}` for each result block                
  - [ ] Add a "View full table" button linking to `/view/{dept}` HTML webview                               
  - [ ] Style the existing `/view/{dept}` HTML webview (improve table, header, access badge)                
  - [ ] Add a "copy link" button for sharing a filtered webview URL                                         
                                                                                                            
  ### Governance Visibility                                                                                 
  - [ ] Build an audit log viewer page pulling from `GET /audit`                                            
  - [ ] Show each audit entry: timestamp, role, dept queried, access level applied, suppressed flag         
  - [ ] Add a simple data catalog browser page (pulls from `GET /catalog`) with search by tag/dept          
                                                                                                            
  ---                                                                                                       
                                                                                                            
  ## Stephen — Testing, Agent & Code Quality                                                               
   
  ### Test Suite                                                                                            
  - [ ] Set up `pytest` with a `tests/` directory and `conftest.py`
  - [ ] Write unit tests for every access level in `privacy.py` (engineer, planner, health, analyst, admin ×
   each dept)                                                                                               
  - [ ] Write tests for small-cell suppression (<5 zones returns suppressed)                                
  - [ ] Write tests for capacity banding (non-engineers never see raw %)                                    
  - [ ] Write integration tests for `POST /query` hitting a test SQLite db                                  
  - [ ] Write integration tests for `GET /download/{dept}` (CSV and JSON formats)                           
  - [ ] Write tests for `GET /audit` to confirm every query is logged                                       
                                                                                                            
  ### Agent Improvements                                                                                    
  - [ ] Add a `health_check_tool` so the agent can verify FastAPI is reachable before querying              
  - [ ] Improve agent system prompt: add explicit handling for "unknown role" cases                         
  - [ ] Add role constants to a shared `constants.py` so `agent.py`, `tools.py`, and `privacy.py` all pull  
  from one source of truth (currently strings are repeated across files)                                    
  - [ ] Add retry logic to all tool HTTP calls (currently fail silently on connection error)                
  - [ ] Test and document the `fallback_demo.py` flow end-to-end                                            
                                                                                                            
  ### Code Quality                                                                                          
  - [ ] Add type hints to all functions in `backend/main.py`, `privacy.py`, `audit.py`                      
  - [ ] Add `__all__` exports to `backend/__init__.py` and `agent/__init__.py`                              
  - [ ] Add a `Makefile` or `justfile` with targets: `seed`, `serve`, `test`, `lint`                        
  - [ ] Add a `.env.example` validation check on startup (warn if required keys are missing)                
  - [ ] Set up `ruff` or `flake8` for linting + `black` for formatting