"""
Paginated ArcGIS Feature Server Fetcher

Handles pagination for ArcGIS services that limit results to 2000 records per request.
"""

import logging
from typing import Generator, Optional
import httpx

from .config import DatasetConfig

logger = logging.getLogger(__name__)

# ArcGIS typically limits to 2000 records per request
DEFAULT_PAGE_SIZE = 2000
REQUEST_TIMEOUT = 60.0


class ArcGISFetcher:
    """Fetches data from ArcGIS Feature Servers with automatic pagination."""

    def __init__(self, timeout: float = REQUEST_TIMEOUT):
        self.timeout = timeout
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def close(self):
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def fetch_page(
        self,
        service_url: str,
        out_fields: str = "*",
        where: str = "1=1",
        result_offset: int = 0,
        result_record_count: int = DEFAULT_PAGE_SIZE,
    ) -> dict:
        """
        Fetch a single page of results from an ArcGIS Feature Server.

        Args:
            service_url: Base URL of the feature service layer
            out_fields: Comma-separated field names or "*" for all
            where: SQL WHERE clause for filtering
            result_offset: Number of records to skip
            result_record_count: Maximum records to return

        Returns:
            dict with 'features' list and metadata
        """
        params = {
            "f": "json",
            "where": where,
            "outFields": out_fields,
            "resultOffset": result_offset,
            "resultRecordCount": result_record_count,
            "returnGeometry": "false",
        }

        query_url = f"{service_url}/query"
        logger.debug(f"Fetching page: offset={result_offset}, url={query_url}")

        response = self.client.get(query_url, params=params)
        response.raise_for_status()

        data = response.json()

        if "error" in data:
            error = data["error"]
            raise RuntimeError(
                f"ArcGIS error {error.get('code')}: {error.get('message')}"
            )

        return data

    def fetch_all(
        self,
        service_url: str,
        out_fields: str = "*",
        where: str = "1=1",
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> Generator[dict, None, None]:
        """
        Fetch all records from an ArcGIS Feature Server, handling pagination.

        Yields individual feature records (the 'attributes' dict from each feature).

        Args:
            service_url: Base URL of the feature service layer
            out_fields: Comma-separated field names or "*" for all
            where: SQL WHERE clause for filtering
            page_size: Number of records per page

        Yields:
            dict: Feature attributes for each record
        """
        offset = 0
        total_fetched = 0

        while True:
            data = self.fetch_page(
                service_url=service_url,
                out_fields=out_fields,
                where=where,
                result_offset=offset,
                result_record_count=page_size,
            )

            features = data.get("features", [])
            if not features:
                logger.info(f"No more features at offset {offset}")
                break

            for feature in features:
                yield feature.get("attributes", {})
                total_fetched += 1

            # Check if there are more records
            exceeded_limit = data.get("exceededTransferLimit", False)
            if not exceeded_limit:
                logger.info(f"Completed fetch: {total_fetched} total records")
                break

            offset += page_size
            logger.debug(f"Pagination: fetched {total_fetched}, next offset {offset}")

    def fetch_dataset(self, config: DatasetConfig) -> Generator[dict, None, None]:
        """
        Fetch all records for a configured dataset.

        Args:
            config: Dataset configuration

        Yields:
            dict: Feature attributes for each record
        """
        out_fields = ",".join(config.field_mapping.keys()) if config.field_mapping else "*"

        logger.info(f"Starting fetch for dataset: {config.dataset_id}")
        yield from self.fetch_all(
            service_url=config.service_url,
            out_fields=out_fields,
        )

    def get_record_count(self, service_url: str, where: str = "1=1") -> int:
        """
        Get the total record count for a service without fetching all data.

        Args:
            service_url: Base URL of the feature service layer
            where: SQL WHERE clause for filtering

        Returns:
            int: Total record count
        """
        params = {
            "f": "json",
            "where": where,
            "returnCountOnly": "true",
        }

        query_url = f"{service_url}/query"
        response = self.client.get(query_url, params=params)
        response.raise_for_status()

        data = response.json()
        return data.get("count", 0)
