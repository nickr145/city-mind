"""
Pydantic models for sync API requests and responses.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SyncTriggerRequest(BaseModel):
    """Request body for triggering a sync."""
    datasets: Optional[list[str]] = Field(
        default=None,
        description="List of dataset IDs to sync. If empty, syncs all enabled datasets."
    )
    triggered_by: str = Field(
        default="manual",
        description="Source of the trigger: 'manual' or 'cron'"
    )


class SyncTriggerResponse(BaseModel):
    """Response after triggering a sync."""
    run_id: str
    status: str
    datasets_queued: list[str]
    message: str


class DatasetStatus(BaseModel):
    """Status information for a single dataset."""
    dataset_id: str
    display_name: str
    source_id: str
    local_table: str
    record_count: int
    last_sync: Optional[str]
    last_sync_status: Optional[str]
    enabled: bool


class SyncStatusResponse(BaseModel):
    """Response for sync status endpoint."""
    datasets: list[DatasetStatus]
    total_records: int
    last_full_sync: Optional[str]


class SyncRunInfo(BaseModel):
    """Information about a single sync run."""
    run_id: str
    dataset_id: str
    started_at: str
    completed_at: Optional[str]
    status: str
    records_fetched: int
    error_message: Optional[str]
    triggered_by: str


class SyncRunsResponse(BaseModel):
    """Response for sync runs history endpoint."""
    runs: list[SyncRunInfo]
    count: int


class DataSourceInfo(BaseModel):
    """Information about a data source."""
    source_id: str
    name: str
    base_url: str
    source_type: str
    enabled: bool
    datasets: list[str]


class DatasetsResponse(BaseModel):
    """Response for datasets listing endpoint."""
    sources: list[DataSourceInfo]
    total_datasets: int
