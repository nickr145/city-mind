# backend/arcgis_client.py
"""
Client for fetching data from Region of Waterloo and Kitchener ArcGIS Open Data portals.

Data Sources:
- Region of Waterloo: https://rowopendata-rmw.opendata.arcgis.com/
- City of Kitchener: https://open-kitchenergis.opendata.arcgis.com/
"""

import requests
from typing import Optional
from functools import lru_cache

# Base URLs for ArcGIS Feature Services
ARCGIS_BASE = "https://services1.arcgis.com/qAo1OsXi67t7XgmS/arcgis/rest/services"

# Dataset endpoints
DATASETS = {
    "building_permits": {
        "url": f"{ARCGIS_BASE}/Building_Permits/FeatureServer/0",
        "name": "Building Permits",
        "source": "City of Kitchener",
        "description": "Building permits issued by the City of Kitchener",
        "fields": ["PERMITNO", "PERMIT_TYPE", "PERMIT_STATUS", "APPLICATION_DATE",
                   "ISSUE_DATE", "CONSTRUCTION_VALUE", "OWNERS", "APPLICANT"],
    },
    "water_mains": {
        "url": f"{ARCGIS_BASE}/Water_Mains/FeatureServer/0",
        "name": "Water Mains",
        "source": "City of Kitchener",
        "description": "Water main infrastructure including pipe size, material, and condition",
        "fields": ["WATMAINID", "STATUS", "PRESSURE_ZONE", "PIPE_SIZE", "MATERIAL",
                   "INSTALLATION_DATE", "OWNERSHIP", "CRITICALITY", "CONDITION_SCORE"],
    },
    "bus_stops": {
        "url": f"{ARCGIS_BASE}/Bus_Stop/FeatureServer/0",
        "name": "GRT Bus Stops",
        "source": "Region of Waterloo / GRT",
        "description": "Grand River Transit bus stop locations",
        "fields": ["STOP_ID", "STREET", "CROSSSTREET", "MUNICIPALITY", "IXPRESS", "STATUS"],
    },
}


class ArcGISClient:
    """Client for querying ArcGIS Feature Services."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()

    def query(
        self,
        dataset: str,
        where: str = "1=1",
        out_fields: Optional[list[str]] = None,
        return_geometry: bool = False,
        result_record_count: int = 100,
        result_offset: int = 0,
    ) -> dict:
        """
        Query an ArcGIS Feature Service.

        Args:
            dataset: Key from DATASETS dict (e.g., 'building_permits')
            where: SQL WHERE clause for filtering
            out_fields: List of fields to return (None = all)
            return_geometry: Whether to include geometry in response
            result_record_count: Max records to return (max 2000)
            result_offset: Offset for pagination

        Returns:
            Dict with 'features' list and metadata
        """
        if dataset not in DATASETS:
            raise ValueError(f"Unknown dataset: {dataset}. Available: {list(DATASETS.keys())}")

        ds = DATASETS[dataset]
        url = f"{ds['url']}/query"

        params = {
            "where": where,
            "outFields": ",".join(out_fields) if out_fields else "*",
            "returnGeometry": str(return_geometry).lower(),
            "resultRecordCount": min(result_record_count, 2000),
            "resultOffset": result_offset,
            "f": "json",
        }

        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            raise Exception(f"ArcGIS API error: {data['error']}")

        return {
            "dataset": dataset,
            "source": ds["source"],
            "record_count": len(data.get("features", [])),
            "features": [f["attributes"] for f in data.get("features", [])],
            "exceeded_limit": data.get("exceededTransferLimit", False),
        }

    def get_building_permits(
        self,
        permit_type: Optional[str] = None,
        status: Optional[str] = None,
        min_value: Optional[float] = None,
        limit: int = 100,
    ) -> dict:
        """Query building permits with common filters."""
        clauses = ["1=1"]

        if permit_type:
            clauses.append(f"PERMIT_TYPE LIKE '%{permit_type}%'")
        if status:
            clauses.append(f"PERMIT_STATUS = '{status}'")
        if min_value:
            clauses.append(f"CONSTRUCTION_VALUE >= {min_value}")

        return self.query(
            "building_permits",
            where=" AND ".join(clauses),
            result_record_count=limit,
        )

    def get_water_mains(
        self,
        pressure_zone: Optional[str] = None,
        material: Optional[str] = None,
        min_criticality: Optional[int] = None,
        status: str = "ACTIVE",
        limit: int = 100,
    ) -> dict:
        """Query water mains with common filters."""
        clauses = [f"STATUS = '{status}'"]

        if pressure_zone:
            clauses.append(f"PRESSURE_ZONE = '{pressure_zone}'")
        if material:
            clauses.append(f"MATERIAL = '{material}'")
        if min_criticality is not None:
            clauses.append(f"CRITICALITY >= {min_criticality}")

        return self.query(
            "water_mains",
            where=" AND ".join(clauses),
            result_record_count=limit,
        )

    def get_bus_stops(
        self,
        municipality: Optional[str] = None,
        ixpress_only: bool = False,
        limit: int = 100,
    ) -> dict:
        """Query GRT bus stops with common filters."""
        clauses = ["STATUS = 'ACTIVE'"]

        if municipality:
            clauses.append(f"MUNICIPALITY = '{municipality}'")
        if ixpress_only:
            clauses.append("IXPRESS = 'Y'")

        return self.query(
            "bus_stops",
            where=" AND ".join(clauses),
            result_record_count=limit,
        )

    def get_infrastructure_summary(self, zone: Optional[str] = None) -> dict:
        """Get a cross-dataset infrastructure summary."""
        summary = {
            "water_mains": {"total": 0, "by_material": {}, "avg_criticality": 0},
            "permits": {"total": 0, "by_status": {}, "total_value": 0},
            "transit": {"total_stops": 0, "ixpress_stops": 0},
        }

        # Water mains
        where = "STATUS = 'ACTIVE'"
        if zone:
            where += f" AND PRESSURE_ZONE LIKE '%{zone}%'"
        mains = self.query("water_mains", where=where, result_record_count=2000)
        summary["water_mains"]["total"] = mains["record_count"]

        for f in mains["features"]:
            mat = f.get("MATERIAL", "UNKNOWN")
            summary["water_mains"]["by_material"][mat] = \
                summary["water_mains"]["by_material"].get(mat, 0) + 1

        criticalities = [f.get("CRITICALITY", 0) for f in mains["features"]
                        if f.get("CRITICALITY") is not None]
        if criticalities:
            summary["water_mains"]["avg_criticality"] = sum(criticalities) / len(criticalities)

        # Building permits (recent)
        permits = self.query("building_permits", where="1=1", result_record_count=500)
        summary["permits"]["total"] = permits["record_count"]

        for f in permits["features"]:
            status = f.get("PERMIT_STATUS", "UNKNOWN")
            summary["permits"]["by_status"][status] = \
                summary["permits"]["by_status"].get(status, 0) + 1
            summary["permits"]["total_value"] += f.get("CONSTRUCTION_VALUE") or 0

        # Bus stops
        stops = self.query("bus_stops", where="STATUS = 'ACTIVE'", result_record_count=2000)
        summary["transit"]["total_stops"] = stops["record_count"]
        summary["transit"]["ixpress_stops"] = sum(
            1 for f in stops["features"] if f.get("IXPRESS") == "Y"
        )

        return summary


# Singleton client instance
_client: Optional[ArcGISClient] = None


def get_client() -> ArcGISClient:
    """Get or create the ArcGIS client singleton."""
    global _client
    if _client is None:
        _client = ArcGISClient()
    return _client


if __name__ == "__main__":
    # Test the client
    client = get_client()

    print("=== Building Permits ===")
    permits = client.get_building_permits(limit=5)
    print(f"Found {permits['record_count']} permits")
    for p in permits["features"][:3]:
        print(f"  - {p.get('PERMITNO')}: {p.get('PERMIT_TYPE')} ({p.get('PERMIT_STATUS')})")

    print("\n=== Water Mains ===")
    mains = client.get_water_mains(limit=5)
    print(f"Found {mains['record_count']} water mains")
    for m in mains["features"][:3]:
        print(f"  - Size: {m.get('PIPE_SIZE')}mm, Material: {m.get('MATERIAL')}, "
              f"Criticality: {m.get('CRITICALITY')}")

    print("\n=== Bus Stops ===")
    stops = client.get_bus_stops(municipality="KITCHENER", limit=5)
    print(f"Found {stops['record_count']} bus stops")
    for s in stops["features"][:3]:
        print(f"  - Stop {s.get('STOP_ID')}: {s.get('STREET')} @ {s.get('CROSSSTREET')}")

    print("\n=== Infrastructure Summary ===")
    summary = client.get_infrastructure_summary()
    print(f"Water mains: {summary['water_mains']['total']} "
          f"(avg criticality: {summary['water_mains']['avg_criticality']:.2f})")
    print(f"Permits: {summary['permits']['total']} "
          f"(total value: ${summary['permits']['total_value']:,.0f})")
    print(f"Transit stops: {summary['transit']['total_stops']} "
          f"({summary['transit']['ixpress_stops']} iXpress)")
