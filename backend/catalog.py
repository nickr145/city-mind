# backend/catalog.py
# Catalog is stored in catalog.json — edit that file to add/update datasets.

import json
import pathlib

_CATALOG_PATH = pathlib.Path(__file__).parent / "catalog.json"


def _load() -> dict:
    with open(_CATALOG_PATH) as f:
        return json.load(f)


def _save(catalog: dict) -> None:
    with open(_CATALOG_PATH, "w") as f:
        json.dump(catalog, f, indent=2)


CATALOG = _load()
