"""
Sync Configuration

Defines data sources and dataset configurations for the sync process.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DataSourceConfig:
    """Configuration for an external data source."""
    source_id: str
    name: str
    base_url: str
    source_type: str  # 'arcgis_featureserver' | 'ckan'
    enabled: bool = True


@dataclass
class DatasetConfig:
    """Configuration for an individual dataset to sync."""
    dataset_id: str
    source_id: str
    service_name: str
    display_name: str
    service_url: str
    local_table: str
    primary_key: str
    field_mapping: dict = field(default_factory=dict)
    enabled: bool = True


# Data Sources
DATA_SOURCES = {
    "kitchener": DataSourceConfig(
        source_id="kitchener",
        name="City of Kitchener",
        base_url="https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services",
        source_type="arcgis_featureserver",
        enabled=True,
    ),
    "waterloo_region": DataSourceConfig(
        source_id="waterloo_region",
        name="Region of Waterloo",
        base_url="https://rowopendata-rmw.opendata.arcgis.com",
        source_type="arcgis_featureserver",
        enabled=False,  # Phase 2
    ),
    "waterloo_city": DataSourceConfig(
        source_id="waterloo_city",
        name="City of Waterloo",
        base_url="https://services.arcgis.com/ZpeBVw5o1kjit7LT/ArcGIS/rest/services",
        source_type="arcgis_featureserver",
        enabled=True,
    ),
}

# Dataset Configurations
DATASETS = {
    "kitchener_building_permits": DatasetConfig(
        dataset_id="kitchener_building_permits",
        source_id="kitchener",
        service_name="Building_Permits",
        display_name="Building Permits",
        service_url="https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services/Building_Permits/FeatureServer/0",
        local_table="building_permits",
        primary_key="PERMITNO",
        field_mapping={
            "PARCELID": "parcel_id",
            "PERMITNO": "permit_no",
            "FOLDERRSN": "folder_rsn",
            "PERMIT_TYPE": "permit_type",
            "PERMIT_TYPE_CODE": "permit_type_code",
            "ROLL_NO": "roll_no",
            "FOLDERNAME": "folder_name",
            "LEGAL_DESCRIPTION": "legal_description",
            "PERMIT_STATUS": "permit_status",
            "STATUS_CODE": "status_code",
            "APPLICATION_DATE": "application_date",
            "ISSUE_DATE": "issue_date",
            "FINAL_DATE": "final_date",
            "EXPIRY_DATE": "expiry_date",
            "ISSUE_YEAR": "issue_year",
            "ISSUED_BY": "issued_by",
            "SUB_WORK_TYPE": "sub_work_type",
            "WORK_TYPE": "work_type",
            "WORK_CODE": "work_code",
            "PERMIT_DESCRIPTION": "permit_description",
            "CONSTRUCTION_VALUE": "construction_value",
            "TOTAL_UNITS": "total_units",
            "UNITS_CREATED": "units_created",
            "UNITS_LOST": "units_lost",
            "UNITS_NET_CHANGE": "units_net_change",
            "REAR_YARD_RQRD": "rear_yard_rqrd",
            "LEFT_SIDE_YARD_RQRD": "left_side_yard_rqrd",
            "RIGHT_SIDE_YARD_RQRD": "right_side_yard_rqrd",
            "SPECIAL_CONDITIONS": "special_conditions",
            "OWNERS": "owners",
            "APPLICANT": "applicant",
            "CONTRACTOR": "contractor",
            "CONTRACTOR_CONTACT": "contractor_contact",
            "EXTRACTION_DATE": "extraction_date",
            "PERMIT_FEE": "permit_fee",
            "STATCANGROSSAREA_M2": "statcan_gross_area_m2",
            "EXISTING_GFA_M2": "existing_gfa_m2",
            "PROPOSED_GFA": "proposed_gfa",
            "TOTAL_GFA_M2": "total_gfa_m2",
            "OCCUPANCY_PERMITTED_DT": "occupancy_permitted_date",
            "ROWHOUSE_UNITS_CREATED": "rowhouse_units_created",
            "STOREYS_PROPOSED": "storeys_proposed",
            "GFA_GROUPC_CONSTR_SQFT": "gfa_groupc_constr_sqft",
            "NEW_FLOOR_AREA_SQFT": "new_floor_area_sqft",
        },
    ),
    "kitchener_water_mains": DatasetConfig(
        dataset_id="kitchener_water_mains",
        source_id="kitchener",
        service_name="Water_Mains",
        display_name="Water Mains",
        service_url="https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services/Water_Mains/FeatureServer/0",
        local_table="water_mains",
        primary_key="WATMAINID",
        field_mapping={
            "WATMAINID": "watmain_id",
            "STATUS": "status",
            "PRESSURE_ZONE": "pressure_zone",
            "PIPE_SIZE": "pipe_size",
            "MATERIAL": "material",
            "CRITICALITY": "criticality",
        },
    ),
    "kitchener_bus_stops": DatasetConfig(
        dataset_id="kitchener_bus_stops",
        source_id="kitchener",
        service_name="Bus_Stop",
        display_name="Bus Stops",
        service_url="https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services/Bus_Stop/FeatureServer/0",
        local_table="bus_stops",
        primary_key="STOP_ID",
        field_mapping={
            "STOP_ID": "stop_id",
            "STREET": "street",
            "CROSSSTREET": "crossstreet",
            "MUNICIPALITY": "municipality",
            "IXPRESS": "ixpress",
            "STATUS": "status",
        },
    ),
    # City of Waterloo datasets
    "waterloo_building_permits": DatasetConfig(
        dataset_id="waterloo_building_permits",
        source_id="waterloo_city",
        service_name="City_of_Waterloo_Building_Permits",
        display_name="Building Permits (Waterloo)",
        service_url="https://services.arcgis.com/ZpeBVw5o1kjit7LT/ArcGIS/rest/services/City_of_Waterloo_Building_Permits/FeatureServer/0",
        local_table="building_permits",
        primary_key="PERMIT_NUM",
        field_mapping={
            "PERMIT_NUM": "permit_no",
            "PERMIT_ID": "folder_rsn",
            "PERMITTYPE": "permit_type",
            "STATUS": "permit_status",
            "ISSUEDATE": "issue_date",
            "ISSUE_YEAR": "issue_year",
            "CONTRVALUE": "construction_value",
            "WORKCODE": "work_code",
            "WORKDESC": "work_type",
            "SUBDESC": "sub_work_type",
            "PERMITDESC": "permit_description",
            "ADDRESS": "folder_name",
            "UNITS": "total_units",
        },
    ),
    "waterloo_water_mains": DatasetConfig(
        dataset_id="waterloo_water_mains",
        source_id="waterloo_city",
        service_name="Water_Distribution_Mains",
        display_name="Water Mains (Waterloo)",
        service_url="https://services.arcgis.com/ZpeBVw5o1kjit7LT/ArcGIS/rest/services/Water_Distribution_Mains/FeatureServer/0",
        local_table="water_mains",
        primary_key="ASSET_ID",
        field_mapping={
            "ASSET_ID": "watmain_id",
            "LIFECYCLESTATUS": "status",
            "PRESSURE_ZONE": "pressure_zone",
            "DIAMETER": "pipe_size",
            "MATERIAL": "material",
        },
    ),
}


def get_enabled_datasets() -> list[DatasetConfig]:
    """Return list of enabled datasets."""
    return [ds for ds in DATASETS.values() if ds.enabled]


def get_dataset(dataset_id: str) -> Optional[DatasetConfig]:
    """Get a dataset configuration by ID."""
    return DATASETS.get(dataset_id)
