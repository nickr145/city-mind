"""
FastAPI Router for Sync Endpoints

Provides REST API endpoints for triggering and monitoring data syncs.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks

from .config import DATASETS, DATA_SOURCES
from .models import (
    SyncTriggerRequest,
    SyncTriggerResponse,
    SyncStatusResponse,
    SyncRunsResponse,
    DatasetsResponse,
    DataSourceInfo,
    DatasetStatus,
    SyncRunInfo,
)
from .orchestrator import SyncOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])


def get_orchestrator() -> SyncOrchestrator:
    """Create and initialize a sync orchestrator."""
    orchestrator = SyncOrchestrator()
    orchestrator.init_database()
    return orchestrator


def run_sync_background(dataset_ids: Optional[list[str]], triggered_by: str):
    """Background task to run sync."""
    with SyncOrchestrator() as orchestrator:
        orchestrator.init_database()
        orchestrator.sync_all(dataset_ids=dataset_ids, triggered_by=triggered_by)


@router.post("/trigger", response_model=SyncTriggerResponse)
async def trigger_sync(
    request: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
):
    """
    Trigger a data sync operation.

    If no datasets are specified, syncs all enabled datasets.
    The sync runs in the background and returns immediately.
    """
    dataset_ids = request.datasets
    triggered_by = request.triggered_by

    # Validate dataset IDs if provided
    if dataset_ids:
        invalid = [ds for ds in dataset_ids if ds not in DATASETS]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown datasets: {invalid}. Valid: {list(DATASETS.keys())}",
            )
        queued = dataset_ids
    else:
        queued = [ds_id for ds_id, ds in DATASETS.items() if ds.enabled]

    if not queued:
        raise HTTPException(
            status_code=400,
            detail="No datasets to sync",
        )

    # Queue background sync
    background_tasks.add_task(run_sync_background, dataset_ids, triggered_by)

    import uuid
    run_id = str(uuid.uuid4())

    return SyncTriggerResponse(
        run_id=run_id,
        status="queued",
        datasets_queued=queued,
        message=f"Sync queued for {len(queued)} dataset(s)",
    )


@router.post("/trigger/sync", response_model=dict)
async def trigger_sync_synchronous(request: SyncTriggerRequest):
    """
    Trigger a data sync operation and wait for completion.

    Unlike POST /trigger, this endpoint blocks until the sync is complete.
    Useful for testing and cron jobs that need to know when sync finished.
    """
    dataset_ids = request.datasets
    triggered_by = request.triggered_by

    # Validate dataset IDs if provided
    if dataset_ids:
        invalid = [ds for ds in dataset_ids if ds not in DATASETS]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown datasets: {invalid}. Valid: {list(DATASETS.keys())}",
            )

    with SyncOrchestrator() as orchestrator:
        orchestrator.init_database()
        result = orchestrator.sync_all(
            dataset_ids=dataset_ids,
            triggered_by=triggered_by,
        )

    return result


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status():
    """
    Get the current sync status for all datasets.

    Returns record counts, last sync times, and sync status for each dataset.
    """
    with SyncOrchestrator() as orchestrator:
        orchestrator.init_database()
        status = orchestrator.get_status()

    return SyncStatusResponse(
        datasets=[DatasetStatus(**ds) for ds in status["datasets"]],
        total_records=status["total_records"],
        last_full_sync=status["last_full_sync"],
    )


@router.get("/runs", response_model=SyncRunsResponse)
async def get_sync_runs(limit: int = 20):
    """
    Get recent sync run history.

    Returns a list of recent sync runs with their status and record counts.
    """
    with SyncOrchestrator() as orchestrator:
        orchestrator.init_database()
        runs = orchestrator.get_runs(limit=limit)

    return SyncRunsResponse(
        runs=[SyncRunInfo(**run) for run in runs],
        count=len(runs),
    )


@router.get("/datasets", response_model=DatasetsResponse)
async def list_datasets():
    """
    List all configured data sources and their datasets.
    """
    sources = []

    for source_id, source in DATA_SOURCES.items():
        dataset_ids = [
            ds_id for ds_id, ds in DATASETS.items()
            if ds.source_id == source_id
        ]

        sources.append(DataSourceInfo(
            source_id=source.source_id,
            name=source.name,
            base_url=source.base_url,
            source_type=source.source_type,
            enabled=source.enabled,
            datasets=dataset_ids,
        ))

    total_datasets = len(DATASETS)

    return DatasetsResponse(
        sources=sources,
        total_datasets=total_datasets,
    )
