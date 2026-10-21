"""Pydantic request/response schemas for the FastAPI service."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class GeoJSONPolygon(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[list[float]]]


class ProjectSubmission(BaseModel):
    project_id: str = Field(min_length=1, max_length=64)
    name: str
    organization: str
    description: str = ""
    polygon: GeoJSONPolygon
    claimed_area_ha: float = Field(gt=0, le=1_000_000)
    registry_refs: list[str] = []


class SceneRefOut(BaseModel):
    item_id: str
    datetime: str
    cloud_fraction: float
    source: str = "sentinel-2-l2a"


class VerificationOut(BaseModel):
    project_id: str
    mode: str
    outcome: str
    claimed_area_ha: float
    estimated_vegetated_area_ha: float
    confidence_bps: int
    ndvi_mean: float
    ndvi_forest_fraction: float
    scenes: list[SceneRefOut]
    dataset_hash: str
    model_hash: str
    result_hash: str
    notes: list[str]


class SimilarityFeaturesOut(BaseModel):
    name_similarity: float
    org_similarity: float
    description_similarity: float
    area_similarity: float
    centroid_distance_m: float
    polygon_iou: float
    polygon_overlap_ratio: float
    cell_overlap_ratio: float


class DuplicateMatchOut(BaseModel):
    candidate_id: str
    other_id: str
    other_registry: str
    other_registry_ref: str
    risk_score: float
    risk_level: str
    explanation: list[str]
    features: SimilarityFeaturesOut


class DuplicateCheckOut(BaseModel):
    project_id: str
    cell_count: int
    highest_risk_level: str
    matches: list[DuplicateMatchOut]


class TxReceiptOut(BaseModel):
    tx_hash: str
    block_number: int
    gas_used: int
    status: int


class SubmitOnchainOut(BaseModel):
    project_id: str
    cell_count: int
    tx: Optional[TxReceiptOut] = None
    error: Optional[str] = None


class ChainStatusOut(BaseModel):
    rpc_url: str
    contract_address: str
    connected: bool
    configured: bool
    signer: str
    chain_id: int
