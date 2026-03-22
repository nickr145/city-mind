"""
Data Aggregator

Handles SQLite upsert operations for synced data.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from .config import DatasetConfig

logger = logging.getLogger(__name__)

# Path to the replica database
DB_PATH = Path(__file__).parent.parent / "db" / "opendata_replica.db"
SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


class DataAggregator:
    """Aggregates data into the local SQLite replica database."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def init_database(self):
        """Initialize the database schema if it doesn't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        if SCHEMA_PATH.exists():
            logger.info(f"Initializing database from {SCHEMA_PATH}")
            with open(SCHEMA_PATH) as f:
                schema_sql = f.read()
            self.conn.executescript(schema_sql)
            self.conn.commit()
        else:
            logger.warning(f"Schema file not found: {SCHEMA_PATH}")

    def upsert_records(
        self,
        config: DatasetConfig,
        records: Iterator[dict],
        batch_size: int = 500,
    ) -> int:
        """
        Upsert records into the local table using INSERT OR REPLACE.

        Args:
            config: Dataset configuration with field mapping
            records: Iterator of record dicts (ArcGIS attributes)
            batch_size: Number of records to commit per batch

        Returns:
            int: Total number of records upserted
        """
        table = config.local_table
        field_mapping = config.field_mapping
        source_id = config.source_id
        synced_at = datetime.now(timezone.utc).isoformat()

        # Build column lists
        local_columns = list(field_mapping.values()) + ["source_id", "synced_at"]
        placeholders = ", ".join(["?"] * len(local_columns))
        columns_str = ", ".join(local_columns)

        sql = f"INSERT OR REPLACE INTO {table} ({columns_str}) VALUES ({placeholders})"

        total_count = 0
        batch = []

        for record in records:
            # Map ArcGIS field names to local column names
            values = []
            for arcgis_field, local_field in field_mapping.items():
                value = record.get(arcgis_field)
                # Handle timestamp fields (ArcGIS uses milliseconds since epoch)
                if value is not None and "date" in local_field.lower():
                    try:
                        if isinstance(value, (int, float)) and value > 0:
                            # Convert milliseconds to ISO format
                            value = datetime.fromtimestamp(
                                value / 1000, tz=timezone.utc
                            ).isoformat()
                    except (ValueError, OSError):
                        pass  # Keep original value
                values.append(value)

            # Add metadata columns
            values.extend([source_id, synced_at])
            batch.append(tuple(values))

            if len(batch) >= batch_size:
                self.conn.executemany(sql, batch)
                self.conn.commit()
                total_count += len(batch)
                logger.debug(f"Committed batch: {total_count} total records")
                batch = []

        # Commit remaining records
        if batch:
            self.conn.executemany(sql, batch)
            self.conn.commit()
            total_count += len(batch)

        logger.info(f"Upserted {total_count} records into {table}")
        return total_count

    def get_record_count(self, table: str) -> int:
        """Get the current record count for a table."""
        cursor = self.conn.execute(f"SELECT COUNT(*) FROM {table}")
        return cursor.fetchone()[0]

    def get_last_sync(self, dataset_id: str) -> Optional[dict]:
        """Get the most recent sync run for a dataset."""
        cursor = self.conn.execute(
            """
            SELECT run_id, started_at, completed_at, status, records_fetched, error_message
            FROM sync_runs
            WHERE dataset_id = ?
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (dataset_id,),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def create_sync_run(
        self,
        run_id: str,
        dataset_id: str,
        triggered_by: str = "manual",
    ) -> None:
        """Create a new sync run record."""
        started_at = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """
            INSERT INTO sync_runs (run_id, dataset_id, started_at, status, triggered_by)
            VALUES (?, ?, ?, 'running', ?)
            """,
            (run_id, dataset_id, started_at, triggered_by),
        )
        self.conn.commit()

    def complete_sync_run(
        self,
        run_id: str,
        status: str,
        records_fetched: int = 0,
        error_message: Optional[str] = None,
    ) -> None:
        """Mark a sync run as completed."""
        completed_at = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """
            UPDATE sync_runs
            SET completed_at = ?, status = ?, records_fetched = ?, error_message = ?
            WHERE run_id = ?
            """,
            (completed_at, status, records_fetched, error_message, run_id),
        )
        self.conn.commit()

    def get_sync_runs(self, limit: int = 20) -> list[dict]:
        """Get recent sync runs."""
        cursor = self.conn.execute(
            """
            SELECT run_id, dataset_id, started_at, completed_at, status,
                   records_fetched, error_message, triggered_by
            FROM sync_runs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_all_dataset_stats(self) -> list[dict]:
        """Get statistics for all datasets."""
        stats = []

        # Get enabled datasets from config
        from .config import DATASETS

        for dataset_id, config in DATASETS.items():
            try:
                count = self.get_record_count(config.local_table)
            except sqlite3.OperationalError:
                count = 0

            last_sync = self.get_last_sync(dataset_id)

            stats.append({
                "dataset_id": dataset_id,
                "display_name": config.display_name,
                "source_id": config.source_id,
                "local_table": config.local_table,
                "record_count": count,
                "last_sync": last_sync.get("completed_at") if last_sync else None,
                "last_sync_status": last_sync.get("status") if last_sync else None,
                "enabled": config.enabled,
            })

        return stats
