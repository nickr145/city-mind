-- CityMind Open Data Replica Schema
-- Tiered read replica for aggregating open data from multiple ArcGIS portals

-- Data sources (kitchener, waterloo_region, waterloo_city)
CREATE TABLE IF NOT EXISTS data_sources (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    source_type TEXT NOT NULL,  -- 'arcgis_featureserver' | 'ckan'
    enabled INTEGER DEFAULT 1
);

-- Individual datasets within each source
CREATE TABLE IF NOT EXISTS datasets (
    dataset_id TEXT PRIMARY KEY,
    source_id TEXT REFERENCES data_sources(source_id),
    service_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    service_url TEXT NOT NULL,
    local_table TEXT NOT NULL,
    fields TEXT,  -- JSON array
    enabled INTEGER DEFAULT 1
);

-- Audit log of sync runs
CREATE TABLE IF NOT EXISTS sync_runs (
    run_id TEXT PRIMARY KEY,
    dataset_id TEXT REFERENCES datasets(dataset_id),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,  -- 'running' | 'completed' | 'failed'
    records_fetched INTEGER DEFAULT 0,
    error_message TEXT,
    triggered_by TEXT  -- 'manual' | 'cron'
);

-- Building permits from City of Kitchener (full dataset)
CREATE TABLE IF NOT EXISTS building_permits (
    permit_no TEXT PRIMARY KEY,
    parcel_id REAL,
    folder_rsn INTEGER,
    permit_type TEXT,
    permit_type_code TEXT,
    roll_no TEXT,
    folder_name TEXT,
    legal_description TEXT,
    permit_status TEXT,
    status_code TEXT,
    application_date TEXT,
    issue_date TEXT,
    final_date TEXT,
    expiry_date TEXT,
    issue_year REAL,
    issued_by TEXT,
    sub_work_type TEXT,
    work_type TEXT,
    work_code INTEGER,
    permit_description TEXT,
    construction_value REAL,
    total_units TEXT,
    units_created TEXT,
    units_lost TEXT,
    units_net_change REAL,
    rear_yard_rqrd TEXT,
    left_side_yard_rqrd TEXT,
    right_side_yard_rqrd TEXT,
    special_conditions TEXT,
    owners TEXT,
    applicant TEXT,
    contractor TEXT,
    contractor_contact TEXT,
    extraction_date TEXT,
    permit_fee REAL,
    statcan_gross_area_m2 TEXT,
    existing_gfa_m2 TEXT,
    proposed_gfa TEXT,
    total_gfa_m2 TEXT,
    occupancy_permitted_date TEXT,
    rowhouse_units_created TEXT,
    storeys_proposed TEXT,
    gfa_groupc_constr_sqft TEXT,
    new_floor_area_sqft TEXT,
    source_id TEXT DEFAULT 'kitchener',
    synced_at TEXT
);

-- Water mains from City of Kitchener
CREATE TABLE IF NOT EXISTS water_mains (
    watmain_id TEXT PRIMARY KEY,
    status TEXT,
    pressure_zone TEXT,
    pipe_size INTEGER,
    material TEXT,
    criticality INTEGER,
    source_id TEXT DEFAULT 'kitchener',
    synced_at TEXT
);

-- Bus stops from City of Kitchener / GRT
CREATE TABLE IF NOT EXISTS bus_stops (
    stop_id TEXT PRIMARY KEY,
    street TEXT,
    crossstreet TEXT,
    municipality TEXT,
    ixpress TEXT,
    status TEXT,
    source_id TEXT DEFAULT 'kitchener',
    synced_at TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_building_permits_type ON building_permits(permit_type);
CREATE INDEX IF NOT EXISTS idx_building_permits_status ON building_permits(permit_status);
CREATE INDEX IF NOT EXISTS idx_building_permits_issue_year ON building_permits(issue_year);
CREATE INDEX IF NOT EXISTS idx_building_permits_work_type ON building_permits(work_type);
CREATE INDEX IF NOT EXISTS idx_building_permits_application_date ON building_permits(application_date);
CREATE INDEX IF NOT EXISTS idx_water_mains_pressure_zone ON water_mains(pressure_zone);
CREATE INDEX IF NOT EXISTS idx_water_mains_material ON water_mains(material);
CREATE INDEX IF NOT EXISTS idx_bus_stops_municipality ON bus_stops(municipality);
CREATE INDEX IF NOT EXISTS idx_sync_runs_dataset ON sync_runs(dataset_id);
CREATE INDEX IF NOT EXISTS idx_sync_runs_status ON sync_runs(status);

-- Insert default data sources
INSERT OR IGNORE INTO data_sources (source_id, name, base_url, source_type, enabled)
VALUES
    ('kitchener', 'City of Kitchener', 'https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services', 'arcgis_featureserver', 1),
    ('waterloo_region', 'Region of Waterloo', 'https://rowopendata-rmw.opendata.arcgis.com', 'arcgis_featureserver', 0),
    ('waterloo_city', 'City of Waterloo', 'https://data.waterloo.ca', 'ckan', 0);

-- Insert default datasets
INSERT OR IGNORE INTO datasets (dataset_id, source_id, service_name, display_name, service_url, local_table, fields, enabled)
VALUES
    ('kitchener_building_permits', 'kitchener', 'Building_Permits', 'Building Permits',
     'https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services/Building_Permits/FeatureServer/0',
     'building_permits', '["PERMITNO","PERMITTYPE","PERMITSTATUS","APPLICATIONDATE","ISSUEDATE","CONSTRUCTIONVALUE","OWNERS","APPLICANT"]', 1),
    ('kitchener_water_mains', 'kitchener', 'Water_Mains', 'Water Mains',
     'https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services/Water_Mains/FeatureServer/0',
     'water_mains', '["WATMAINID","STATUS","PRESSUREZONE","PIPESIZE","MATERIAL","CRITICALITY","CONDITION_SCORE"]', 1),
    ('kitchener_bus_stops', 'kitchener', 'Bus_Stop', 'Bus Stops',
     'https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services/Bus_Stop/FeatureServer/0',
     'bus_stops', '["STOP_ID","STREET","CROSSSTREET","MUNICIPALITY","IXPRESS","STATUS"]', 1);
