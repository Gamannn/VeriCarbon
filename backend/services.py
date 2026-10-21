"""Service layer: orchestrates pipeline modules and the chain client.

The HTTP layer calls these functions and converts their results to Pydantic
responses. Each service exposes real pipeline output; none of them fabricate
success when a dependency is missing.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import date

from shapely.geometry import shape

from pipeline.entity_resolution import (
    DuplicateMatch,
    ProjectRecord,
    classify_risk,
    find_duplicates,
)
from pipeline.geospatial import (
    h3_cells_to_uint64,
    polygon_area_ha,
    polygon_to_h3_cells,
)
from pipeline.satellite import (
    FIXTURE_DIR,
    VerificationResult,
    verify_from_fixture,
    verify_live,
    verify_synthetic,
)

from .config import get_settings
from .corpus import load_corpus


# ──────────────────────────────────────────────────────────────────────────────
# Project ID → 32-byte key
# ──────────────────────────────────────────────────────────────────────────────
def project_id_bytes(project_id: str) -> bytes:
    return hashlib.sha256(project_id.encode("utf-8")).digest()


def registry_refs_hash(refs: list[str]) -> bytes:
    payload = json.dumps(sorted(refs), separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).digest()


def _hex_to_bytes32(hex_str: str) -> bytes:
    h = hex_str[2:] if hex_str.startswith("0x") else hex_str
    return bytes.fromhex(h)


# ──────────────────────────────────────────────────────────────────────────────
# Satellite verification
# ──────────────────────────────────────────────────────────────────────────────
def run_verification(
    project_id: str,
    polygon_geojson: dict,
    claimed_area_ha: float,
) -> VerificationResult:
    """Dispatch to live / fixture / synthetic mode.

    Resolution order:
      1. If settings.satellite_mode == "live", use live.
      2. If a fixture exists for the given project_id, use it (preserves
         deterministic hashes for the demo scenarios A and B).
      3. Otherwise fall back to synthetic mode so any user-drawn polygon
         still produces a usable verification response.
    """
    poly = shape(polygon_geojson)
    mode = get_settings().satellite_mode
    if mode == "live":
        return verify_live(
            project_id,
            poly,
            claimed_area_ha,
            start_date=date(2025, 6, 1),
            end_date=date(2025, 9, 30),
        )
    if (FIXTURE_DIR / f"{project_id}.json").exists():
        return verify_from_fixture(project_id, poly, claimed_area_ha)
    return verify_synthetic(project_id, poly, claimed_area_ha)


# ──────────────────────────────────────────────────────────────────────────────
# Duplicate check
# ──────────────────────────────────────────────────────────────────────────────
def run_duplicate_check(
    project_id: str,
    name: str,
    organization: str,
    description: str,
    polygon_geojson: dict,
) -> tuple[list[DuplicateMatch], str, int]:
    poly = shape(polygon_geojson)
    candidate = ProjectRecord(
        project_id=project_id,
        name=name,
        organization=organization,
        description=description,
        polygon=poly,
        area_ha=polygon_area_ha(poly),
    )
    matches = find_duplicates(candidate, load_corpus(), top_k=5)
    highest = "LOW"
    for m in matches:
        if m.risk_level == "HIGH":
            highest = "HIGH"
            break
        if m.risk_level == "MEDIUM":
            highest = "MEDIUM"
    cell_count = len(polygon_to_h3_cells(poly))
    return matches, highest, cell_count


# ──────────────────────────────────────────────────────────────────────────────
# Cells for on-chain claim
# ──────────────────────────────────────────────────────────────────────────────
def polygon_to_cells_uint64(polygon_geojson: dict) -> list[int]:
    poly = shape(polygon_geojson)
    return h3_cells_to_uint64(polygon_to_h3_cells(poly))


# ──────────────────────────────────────────────────────────────────────────────
# Helpers for building the on-chain submission args
# ──────────────────────────────────────────────────────────────────────────────
def build_submission_args(
    project_id: str,
    polygon_geojson: dict,
    claimed_area_ha: float,
    registry_refs: list[str],
) -> dict:
    cells = polygon_to_cells_uint64(polygon_geojson)
    return {
        "project_id_bytes": project_id_bytes(project_id),
        "cells_uint64": cells,
        "claimed_area_ha": int(round(claimed_area_ha)),
        "registry_refs_hash": registry_refs_hash(registry_refs),
    }


def build_attestation_args(result: VerificationResult) -> dict:
    return {
        "project_id_bytes": project_id_bytes(result.project_id),
        "dataset_hash": _hex_to_bytes32(result.dataset_hash),
        "model_hash": _hex_to_bytes32(result.model_hash),
        "result_hash": _hex_to_bytes32(result.result_hash),
        "verified_area_ha": int(round(result.estimated_vegetated_area_ha)),
        "confidence_bps": int(result.confidence_bps),
    }
