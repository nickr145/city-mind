"""
Sync Orchestrator

Coordinates the sync process across multiple datasets.
"""

import logging
import uuid
from typing import Optional

from .config import DATASETS, DatasetConfig, get_enabled_datasets
from .fetcher import ArcGISFetcher
from .aggregator import DataAggregator

logger = logging.getLogger(__name__)


class SyncOrchestrator:
    """Orchestrates the sync process for multiple datasets."""

    def __init__(self):
        self.fetcher = ArcGISFetcher()
        self.aggregator = DataAggregator()

    def close(self):
        self.fetcher.close()
        self.aggregator.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def init_database(self):
        """Initialize the replica database."""
        self.aggregator.init_database()

    def sync_dataset(
        self,
        config: DatasetConfig,
        triggered_by: str = "manual",
    ) -> dict:
        """
        Sync a single dataset from source to replica.

        Args:
            config: Dataset configuration
            triggered_by: Source of the trigger ('manual' or 'cron')

        Returns:
            dict with sync run details
        """
        run_id = str(uuid.uuid4())
        logger.info(f"Starting sync run {run_id} for {config.dataset_id}")

        # Create sync run record
        self.aggregator.create_sync_run(
            run_id=run_id,
            dataset_id=config.dataset_id,
            triggered_by=triggered_by,
        )

        try:
            # Fetch all records with pagination
            records = self.fetcher.fetch_dataset(config)

            # Upsert into local database
            count = self.aggregator.upsert_records(config, records)

            # Mark as completed
            self.aggregator.complete_sync_run(
                run_id=run_id,
                status="completed",
                records_fetched=count,
            )

            logger.info(f"Completed sync run {run_id}: {count} records")
            return {
                "run_id": run_id,
                "dataset_id": config.dataset_id,
                "status": "completed",
                "records_fetched": count,
            }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Sync run {run_id} failed: {error_msg}")

            self.aggregator.complete_sync_run(
                run_id=run_id,
                status="failed",
                error_message=error_msg,
            )

            return {
                "run_id": run_id,
                "dataset_id": config.dataset_id,
                "status": "failed",
                "error_message": error_msg,
            }

    def sync_all(
        self,
        dataset_ids: Optional[list[str]] = None,
        triggered_by: str = "manual",
    ) -> dict:
        """
        Sync multiple datasets.

        Args:
            dataset_ids: List of dataset IDs to sync, or None for all enabled
            triggered_by: Source of the trigger

        Returns:
            dict with overall sync status and individual results
        """
        # Determine which datasets to sync
        if dataset_ids:
            configs = []
            for ds_id in dataset_ids:
                if ds_id in DATASETS:
                    configs.append(DATASETS[ds_id])
                else:
                    logger.warning(f"Unknown dataset: {ds_id}")
        else:
            configs = get_enabled_datasets()

        if not configs:
            return {
                "status": "no_datasets",
                "message": "No datasets to sync",
                "results": [],
            }

        # Generate a batch run ID
        batch_id = str(uuid.uuid4())
        logger.info(f"Starting batch sync {batch_id} for {len(configs)} datasets")

        results = []
        success_count = 0
        fail_count = 0

        for config in configs:
            result = self.sync_dataset(config, triggered_by=triggered_by)
            results.append(result)

            if result["status"] == "completed":
                success_count += 1
            else:
                fail_count += 1

        overall_status = "completed" if fail_count == 0 else "partial" if success_count > 0 else "failed"

        return {
            "batch_id": batch_id,
            "status": overall_status,
            "datasets_synced": success_count,
            "datasets_failed": fail_count,
            "results": results,
        }

    def get_status(self) -> dict:
        """Get current sync status for all datasets."""
        stats = self.aggregator.get_all_dataset_stats()
        total_records = sum(s["record_count"] for s in stats)

        # Find last full sync (all datasets completed)
        runs = self.aggregator.get_sync_runs(limit=100)
        last_full_sync = None

        # Simple heuristic: find most recent time all datasets were synced
        for stat in stats:
            if stat["last_sync"]:
                if last_full_sync is None or stat["last_sync"] < last_full_sync:
                    last_full_sync = stat["last_sync"]

        return {
            "datasets": stats,
            "total_records": total_records,
            "last_full_sync": last_full_sync,
        }

    def get_runs(self, limit: int = 20) -> list[dict]:
        """Get recent sync runs."""
        return self.aggregator.get_sync_runs(limit=limit)
