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
        base_url="https://data.waterloo.ca",
        source_type="ckan",
        enabled=False,  # Phase 2
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
            "PERMITNO": "permit_no",
            "PERMIT_TYPE": "permit_type",
            "PERMIT_STATUS": "permit_status",
            "APPLICATION_DATE": "application_date",
            "ISSUE_DATE": "issue_date",
            "CONSTRUCTION_VALUE": "construction_value",
            "OWNERS": "owners",
            "APPLICANT": "applicant",
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
}


def get_enabled_datasets() -> list[DatasetConfig]:
    """Return list of enabled datasets."""
    return [ds for ds in DATASETS.values() if ds.enabled]


def get_dataset(dataset_id: str) -> Optional[DatasetConfig]:
    """Get a dataset configuration by ID."""
    return DATASETS.get(dataset_id)
