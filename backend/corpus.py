"""Load the (synthetic) registry corpus for duplicate detection."""
from __future__ import annotations

import json
from pathlib import Path

from shapely.geometry import shape

from pipeline.entity_resolution import ProjectRecord
from pipeline.geospatial import polygon_area_ha

from .config import get_settings


def load_corpus() -> list[ProjectRecord]:
    path = Path(get_settings().registry_corpus_path)
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    records: list[ProjectRecord] = []
    for p in data.get("projects", []):
        poly = shape(p["polygon"])
        records.append(
            ProjectRecord(
                project_id=p["project_id"],
                name=p.get("name", ""),
                organization=p.get("organization", ""),
                description=p.get("description", ""),
                polygon=poly,
                area_ha=float(p.get("area_ha") or polygon_area_ha(poly)),
                registry=p.get("registry", ""),
                registry_ref=p.get("registry_ref", ""),
            )
        )
    return records
