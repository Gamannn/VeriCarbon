"""Satellite + environmental verification pipeline.

Given a project polygon and a claimed restoration area, this module produces a
verification result containing:

* The list of Sentinel-2 scene identifiers (STAC item IDs) considered.
* An NDVI-based estimate of the vegetated area inside the polygon.
* A verification confidence derived from scene coverage, cloud fraction, and
  the ratio of estimated-area to claimed-area.
* Three deterministic hashes: dataset (scene list + windows), model (code +
  parameters), result (output dict). These are the commitments posted on-chain.
* An outcome: VERIFIED, REQUIRES_REVIEW, or REJECT.

Three execution modes:

* **live** (requires network access): queries a public Sentinel-2 L2A STAC
  endpoint (``PC_STAC_URL``, default: Microsoft Planetary Computer) and runs
  the real NDVI pipeline. Not run by default — it needs rasterio + a token.
* **fixture** (used in tests): reads a JSON observation fixture from
  ``pipeline/data/fixtures/<project_id>.json`` and produces the same output
  schema. Results are clearly labeled with ``mode: "fixture"``.
* **synthetic** (demo fallback for arbitrary user submissions): generates a
  deterministic verification result from the polygon alone — a fixed
  pseudo-random NDVI drawn from a seed derived from the polygon's centroid.
  Clearly labeled ``mode: "synthetic"`` with an explicit disclosure that this
  is a demo stand-in and should never be used in production.

All three modes produce the same ``VerificationResult`` schema and the same
three provenance hashes, so the smart-contract interaction is identical.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, asdict, field
from datetime import date
from pathlib import Path
from typing import Any, Literal

from shapely.geometry import Polygon

from .geospatial import polygon_area_ha, polygon_to_geojson

Mode = Literal["live", "fixture", "synthetic"]
Outcome = Literal["VERIFIED", "REQUIRES_REVIEW", "REJECT"]

FIXTURE_DIR = Path(__file__).parent / "data" / "fixtures"

MODEL_VERSION = "vericarbon-ndvi-v0.1"
CODE_HASH_SOURCE_FILES = ["satellite.py", "geospatial.py"]

# Verification thresholds (documented, tunable, evaluated against test cases)
NDVI_FOREST_THRESHOLD = 0.55          # NDVI above this is considered forested
MIN_SCENE_COUNT = 2                   # need at least this many usable scenes
MAX_CLOUD_FRACTION = 0.30             # drop scenes above this
VERIFIED_AREA_RATIO = 0.80            # est ≥ 80% of claimed → VERIFIED
REVIEW_AREA_RATIO = 0.50              # 50-80% → REQUIRES_REVIEW; <50% → REJECT


@dataclass
class SceneRef:
    item_id: str
    datetime: str
    cloud_fraction: float
    source: str = "sentinel-2-l2a"


@dataclass
class VerificationResult:
    project_id: str
    mode: Mode
    outcome: Outcome
    claimed_area_ha: float
    estimated_vegetated_area_ha: float
    confidence_bps: int                       # 0–10000
    ndvi_mean: float
    ndvi_forest_fraction: float               # fraction of pixels with NDVI ≥ threshold
    scenes: list[SceneRef]
    dataset_hash: str                         # commit to the scene set + polygon
    model_hash: str                           # commit to code + parameters
    result_hash: str                          # commit to this dict's canonical form
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["scenes"] = [asdict(s) for s in self.scenes]
        return d


# ──────────────────────────────────────────────────────────────────────────────
# Hashing helpers (deterministic, canonical JSON)
# ──────────────────────────────────────────────────────────────────────────────
def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_hex(s: str) -> str:
    return "0x" + hashlib.sha256(s.encode("utf-8")).hexdigest()


def _code_hash() -> str:
    """Hash the current source of this pipeline for model-provenance."""
    h = hashlib.sha256()
    base = Path(__file__).parent
    for name in CODE_HASH_SOURCE_FILES:
        p = base / name
        if p.exists():
            h.update(p.read_bytes())
    h.update(MODEL_VERSION.encode("utf-8"))
    h.update(
        _canonical(
            {
                "ndvi_forest_threshold": NDVI_FOREST_THRESHOLD,
                "min_scene_count": MIN_SCENE_COUNT,
                "max_cloud_fraction": MAX_CLOUD_FRACTION,
                "verified_area_ratio": VERIFIED_AREA_RATIO,
                "review_area_ratio": REVIEW_AREA_RATIO,
            }
        ).encode("utf-8")
    )
    return "0x" + h.hexdigest()


def _dataset_hash(scenes: list[SceneRef], polygon: Polygon) -> str:
    return _sha256_hex(
        _canonical(
            {
                "scenes": [asdict(s) for s in scenes],
                "polygon": polygon_to_geojson(polygon),
            }
        )
    )


def _result_hash(payload: dict) -> str:
    scrubbed = {k: v for k, v in payload.items() if k != "result_hash"}
    return _sha256_hex(_canonical(scrubbed))


# ──────────────────────────────────────────────────────────────────────────────
# Core verification logic
# ──────────────────────────────────────────────────────────────────────────────
def _decide_outcome(claimed_ha: float, estimated_ha: float, usable_scenes: int) -> Outcome:
    if usable_scenes < MIN_SCENE_COUNT:
        return "REQUIRES_REVIEW"
    if claimed_ha <= 0:
        return "REJECT"
    ratio = estimated_ha / claimed_ha
    if ratio >= VERIFIED_AREA_RATIO:
        return "VERIFIED"
    if ratio >= REVIEW_AREA_RATIO:
        return "REQUIRES_REVIEW"
    return "REJECT"


def _confidence_bps(
    *,
    estimated_ha: float,
    claimed_ha: float,
    usable_scenes: int,
    avg_cloud_fraction: float,
    ndvi_forest_fraction: float,
) -> int:
    """Return a confidence in basis points. Explicit, interpretable formula."""
    area_term = min(estimated_ha / claimed_ha, 1.0) if claimed_ha > 0 else 0.0
    scene_term = min(usable_scenes / 5.0, 1.0)
    cloud_term = max(1.0 - avg_cloud_fraction / MAX_CLOUD_FRACTION, 0.0)
    ndvi_term = ndvi_forest_fraction
    conf = 0.45 * area_term + 0.20 * scene_term + 0.15 * cloud_term + 0.20 * ndvi_term
    return max(0, min(10000, int(round(conf * 10000))))


# ──────────────────────────────────────────────────────────────────────────────
# Fixture mode (synthetic, labeled, deterministic)
# ──────────────────────────────────────────────────────────────────────────────
def verify_from_fixture(
    project_id: str,
    polygon: Polygon,
    claimed_area_ha: float,
    fixture_dir: Path = FIXTURE_DIR,
) -> VerificationResult:
    """Produce a VerificationResult from a fixture JSON file. Clearly labeled fixture.

    The fixture JSON must contain:
      - "scenes": list of {"item_id","datetime","cloud_fraction"}
      - "ndvi_mean": float
      - "ndvi_forest_fraction": float in [0,1]
      - "estimated_vegetated_area_ha": float
    """
    fx_path = fixture_dir / f"{project_id}.json"
    if not fx_path.exists():
        raise FileNotFoundError(f"No fixture for project {project_id} at {fx_path}")
    fx = json.loads(fx_path.read_text())

    scenes = [SceneRef(**s) for s in fx["scenes"]]
    usable = [s for s in scenes if s.cloud_fraction <= MAX_CLOUD_FRACTION]
    avg_cloud = (
        sum(s.cloud_fraction for s in usable) / len(usable) if usable else 1.0
    )

    estimated_ha = float(fx["estimated_vegetated_area_ha"])
    ndvi_mean = float(fx["ndvi_mean"])
    ndvi_forest_fraction = float(fx["ndvi_forest_fraction"])

    outcome = _decide_outcome(claimed_area_ha, estimated_ha, len(usable))
    conf = _confidence_bps(
        estimated_ha=estimated_ha,
        claimed_ha=claimed_area_ha,
        usable_scenes=len(usable),
        avg_cloud_fraction=avg_cloud,
        ndvi_forest_fraction=ndvi_forest_fraction,
    )

    dataset_hash = _dataset_hash(scenes, polygon)
    model_hash = _code_hash()

    payload = dict(
        project_id=project_id,
        mode="fixture",
        outcome=outcome,
        claimed_area_ha=claimed_area_ha,
        estimated_vegetated_area_ha=estimated_ha,
        confidence_bps=conf,
        ndvi_mean=ndvi_mean,
        ndvi_forest_fraction=ndvi_forest_fraction,
        scenes=[asdict(s) for s in scenes],
        dataset_hash=dataset_hash,
        model_hash=model_hash,
        notes=[
            "Fixture mode: NDVI values and scene list are deterministic test "
            "inputs, not derived from current satellite observations. Do not "
            "treat as a real environmental measurement.",
        ],
    )
    result_hash = _result_hash(payload)

    return VerificationResult(
        project_id=project_id,
        mode="fixture",
        outcome=outcome,
        claimed_area_ha=claimed_area_ha,
        estimated_vegetated_area_ha=estimated_ha,
        confidence_bps=conf,
        ndvi_mean=ndvi_mean,
        ndvi_forest_fraction=ndvi_forest_fraction,
        scenes=scenes,
        dataset_hash=dataset_hash,
        model_hash=model_hash,
        result_hash=result_hash,
        notes=payload["notes"],
    )


# ──────────────────────────────────────────────────────────────────────────────
# Live mode (optional, requires rasterio + STAC credentials)
# ──────────────────────────────────────────────────────────────────────────────
def verify_live(
    project_id: str,
    polygon: Polygon,
    claimed_area_ha: float,
    start_date: date,
    end_date: date,
) -> VerificationResult:
    """Query Sentinel-2 L2A via STAC, compute NDVI inside the polygon, score the project.

    Requires rasterio, pystac-client, and (optionally) planetary-computer. Raises
    RuntimeError when those optional deps are missing — callers should fall back
    to :func:`verify_from_fixture` with a clearly labeled fixture.
    """
    try:
        import numpy as np
        import rasterio
        from rasterio.features import geometry_mask
        from pystac_client import Client
        import planetary_computer as pc  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "Live satellite mode requires rasterio, pystac-client, and "
            "planetary-computer. Install the full requirements.txt or use "
            "verify_from_fixture() instead."
        ) from e

    stac_url = os.environ.get(
        "PC_STAC_URL", "https://planetarycomputer.microsoft.com/api/stac/v1"
    )
    catalog = Client.open(stac_url, modifier=pc.sign_inplace)
    search = catalog.search(
        collections=["sentinel-2-l2a"],
        intersects=polygon_to_geojson(polygon),
        datetime=f"{start_date.isoformat()}/{end_date.isoformat()}",
        query={"eo:cloud_cover": {"lt": int(MAX_CLOUD_FRACTION * 100)}},
    )
    items = list(search.items())
    if not items:
        raise RuntimeError("No Sentinel-2 scenes found for polygon and date range")

    scenes: list[SceneRef] = []
    ndvi_pixels: list[np.ndarray] = []

    for item in items[:10]:  # cap to keep the demo tractable
        cloud = float(item.properties.get("eo:cloud_cover", 0.0)) / 100.0
        scenes.append(
            SceneRef(
                item_id=item.id,
                datetime=item.datetime.isoformat() if item.datetime else "",
                cloud_fraction=cloud,
            )
        )
        try:
            red_href = item.assets["B04"].href
            nir_href = item.assets["B08"].href
            with rasterio.open(red_href) as red, rasterio.open(nir_href) as nir:
                mask = geometry_mask(
                    [polygon_to_geojson(polygon)],
                    transform=red.transform,
                    invert=True,
                    out_shape=red.shape,
                )
                red_band = red.read(1).astype("float32")
                nir_band = nir.read(1).astype("float32")
                denom = (nir_band + red_band)
                ndvi = np.where(denom == 0, 0, (nir_band - red_band) / denom)
                ndvi_pixels.append(ndvi[mask])
        except Exception:  # pragma: no cover
            continue

    if not ndvi_pixels:
        raise RuntimeError("Could not read any usable NDVI pixels")

    all_ndvi = np.concatenate(ndvi_pixels)
    ndvi_mean = float(all_ndvi.mean())
    ndvi_forest_fraction = float((all_ndvi >= NDVI_FOREST_THRESHOLD).mean())

    poly_area = polygon_area_ha(polygon)
    estimated_ha = poly_area * ndvi_forest_fraction

    usable = [s for s in scenes if s.cloud_fraction <= MAX_CLOUD_FRACTION]
    avg_cloud = sum(s.cloud_fraction for s in usable) / max(len(usable), 1)
    outcome = _decide_outcome(claimed_area_ha, estimated_ha, len(usable))
    conf = _confidence_bps(
        estimated_ha=estimated_ha,
        claimed_ha=claimed_area_ha,
        usable_scenes=len(usable),
        avg_cloud_fraction=avg_cloud,
        ndvi_forest_fraction=ndvi_forest_fraction,
    )
    dataset_hash = _dataset_hash(scenes, polygon)
    model_hash = _code_hash()

    payload = dict(
        project_id=project_id,
        mode="live",
        outcome=outcome,
        claimed_area_ha=claimed_area_ha,
        estimated_vegetated_area_ha=estimated_ha,
        confidence_bps=conf,
        ndvi_mean=ndvi_mean,
        ndvi_forest_fraction=ndvi_forest_fraction,
        scenes=[asdict(s) for s in scenes],
        dataset_hash=dataset_hash,
        model_hash=model_hash,
        notes=[
            "Live mode: NDVI derived from Sentinel-2 L2A bands B04 (red) and "
            "B08 (NIR) via the Microsoft Planetary Computer STAC endpoint. "
            "Vegetation increase is not equivalent to carbon removal — "
            "additionality, permanence, and leakage are out of scope for "
            "this metric.",
        ],
    )
    result_hash = _result_hash(payload)
    return VerificationResult(
        project_id=project_id,
        mode="live",
        outcome=outcome,
        claimed_area_ha=claimed_area_ha,
        estimated_vegetated_area_ha=estimated_ha,
        confidence_bps=conf,
        ndvi_mean=ndvi_mean,
        ndvi_forest_fraction=ndvi_forest_fraction,
        scenes=scenes,
        dataset_hash=dataset_hash,
        model_hash=model_hash,
        result_hash=result_hash,
        notes=payload["notes"],
    )


# ──────────────────────────────────────────────────────────────────────────────
# Synthetic mode (demo fallback for arbitrary user submissions)
# ──────────────────────────────────────────────────────────────────────────────
def verify_synthetic(
    project_id: str,
    polygon: Polygon,
    claimed_area_ha: float,
) -> VerificationResult:
    """Produce a deterministic demo verification for any polygon.

    This is for the live dashboard — a user who draws a polygon on the map
    should get a plausible verification response, not an error about missing
    fixtures. The NDVI mean and forest fraction are derived from a stable
    hash of the polygon centroid, so repeat submissions return identical
    numbers (deterministic — important because the on-chain attestation
    commits to the result hash).

    Every result is labeled ``mode: "synthetic"`` with a prominent note that
    this is a demo stand-in, not a real satellite observation.
    """
    from .geospatial import polygon_area_ha as _area_ha

    centroid = polygon.centroid
    seed_bytes = hashlib.sha256(
        f"{centroid.x:.6f},{centroid.y:.6f},{project_id}".encode("utf-8")
    ).digest()
    # Reproducible pseudo-random floats in [0, 1) from the seed
    r1 = int.from_bytes(seed_bytes[:4], "big") / 0xFFFFFFFF
    r2 = int.from_bytes(seed_bytes[4:8], "big") / 0xFFFFFFFF
    r3 = int.from_bytes(seed_bytes[8:12], "big") / 0xFFFFFFFF

    # Realistic ranges: NDVI mean 0.35 – 0.80 for forested land
    ndvi_mean = 0.35 + 0.45 * r1
    # Forest fraction correlates with NDVI mean
    ndvi_forest_fraction = max(0.0, min(1.0, (ndvi_mean - 0.25) / 0.55 + 0.1 * (r2 - 0.5)))

    polygon_area = _area_ha(polygon)
    estimated_ha = polygon_area * ndvi_forest_fraction

    # Synthesize two plausible scene refs so provenance hashing is non-trivial
    scenes = [
        SceneRef(
            item_id=f"SYNTH_{seed_bytes[:4].hex()}_T{int(10 + 20 * r3):02d}",
            datetime="2025-08-15T00:00:00Z",
            cloud_fraction=0.05 + 0.15 * r3,
            source="synthetic-stand-in",
        ),
        SceneRef(
            item_id=f"SYNTH_{seed_bytes[4:8].hex()}_T{int(10 + 20 * r1):02d}",
            datetime="2025-09-05T00:00:00Z",
            cloud_fraction=0.05 + 0.20 * r1,
            source="synthetic-stand-in",
        ),
    ]
    usable = [s for s in scenes if s.cloud_fraction <= MAX_CLOUD_FRACTION]
    avg_cloud = sum(s.cloud_fraction for s in usable) / max(len(usable), 1)

    outcome = _decide_outcome(claimed_area_ha, estimated_ha, len(usable))
    conf = _confidence_bps(
        estimated_ha=estimated_ha,
        claimed_ha=claimed_area_ha,
        usable_scenes=len(usable),
        avg_cloud_fraction=avg_cloud,
        ndvi_forest_fraction=ndvi_forest_fraction,
    )

    dataset_hash = _dataset_hash(scenes, polygon)
    model_hash = _code_hash()

    payload = dict(
        project_id=project_id,
        mode="synthetic",
        outcome=outcome,
        claimed_area_ha=claimed_area_ha,
        estimated_vegetated_area_ha=estimated_ha,
        confidence_bps=conf,
        ndvi_mean=ndvi_mean,
        ndvi_forest_fraction=ndvi_forest_fraction,
        scenes=[asdict(s) for s in scenes],
        dataset_hash=dataset_hash,
        model_hash=model_hash,
        notes=[
            "SYNTHETIC MODE — NDVI values are deterministically derived from "
            "the polygon centroid, not from any satellite observation. This "
            "mode exists so the live dashboard can accept any user-drawn "
            "polygon and still produce a plausible, repeatable verification "
            "response. For production, use mode=live against the real "
            "Sentinel-2 STAC endpoint.",
        ],
    )
    result_hash = _result_hash(payload)
    return VerificationResult(
        project_id=project_id,
        mode="synthetic",
        outcome=outcome,
        claimed_area_ha=claimed_area_ha,
        estimated_vegetated_area_ha=estimated_ha,
        confidence_bps=conf,
        ndvi_mean=ndvi_mean,
        ndvi_forest_fraction=ndvi_forest_fraction,
        scenes=scenes,
        dataset_hash=dataset_hash,
        model_hash=model_hash,
        result_hash=result_hash,
        notes=payload["notes"],
    )
