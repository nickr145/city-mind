"""
CityMind Sync Module

Tiered read replica pattern for aggregating open data from multiple ArcGIS portals.
"""

from .config import DATASETS, DATA_SOURCES, DatasetConfig, DataSourceConfig
from .fetcher import ArcGISFetcher
from .aggregator import DataAggregator
from .orchestrator import SyncOrchestrator
from .endpoints import router as sync_router

__all__ = [
    "DATASETS",
    "DATA_SOURCES",
    "DatasetConfig",
    "DataSourceConfig",
    "ArcGISFetcher",
    "DataAggregator",
    "SyncOrchestrator",
    "sync_router",
]
