"""Cross-registry entity resolution and duplicate-risk scoring.

Given a candidate project and a corpus of existing registry records, produce an
explainable duplicate-risk score. The score combines name/organization fuzzy
similarity, project description similarity, area ratio, centroid distance, and
H3 cell / polygon overlap.

Blocking: only compare the candidate against records within a configurable
centroid-radius (default 50 km). Features: engineered scalars in [0, 1]. Model:
a logistic regression baseline is provided for optional calibration; the raw
weighted score is also usable as an explainable fallback.

Risk thresholds (from the blueprint):
    LOW     < 0.40
    MEDIUM  0.40 ≤ risk < 0.75
    HIGH    ≥ 0.75
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Iterable, Sequence

import numpy as np
from rapidfuzz import fuzz
from shapely.geometry import Polygon

from .geospatial import (
    OverlapResult,
    area_ratio,
    centroid_distance_m,
    compute_overlap,
    polygon_area_ha,
)


BLOCKING_RADIUS_M = 50_000.0  # 50 km


@dataclass
class ProjectRecord:
    project_id: str
    name: str
    organization: str
    description: str
    polygon: Polygon
    area_ha: float
    registry: str = ""
    registry_ref: str = ""


@dataclass
class SimilarityFeatures:
    name_similarity: float
    org_similarity: float
    description_similarity: float
    area_similarity: float
    centroid_distance_m: float
    polygon_iou: float
    polygon_overlap_ratio: float
    cell_overlap_ratio: float

    def as_vector(self) -> np.ndarray:
        return np.array(
            [
                self.name_similarity,
                self.org_similarity,
                self.description_similarity,
                self.area_similarity,
                1.0 - min(self.centroid_distance_m / BLOCKING_RADIUS_M, 1.0),
                self.polygon_iou,
                self.polygon_overlap_ratio,
                self.cell_overlap_ratio,
            ],
            dtype=np.float64,
        )


@dataclass
class DuplicateMatch:
    candidate_id: str
    other_id: str
    other_registry: str
    other_registry_ref: str
    features: SimilarityFeatures
    risk_score: float
    risk_level: str
    explanation: list[str]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["features"] = asdict(self.features)
        return d


# ──────────────────────────────────────────────────────────────────────────────
# Feature extraction
# ──────────────────────────────────────────────────────────────────────────────
def _norm(text: str) -> str:
    return (text or "").strip().lower()


def extract_features(a: ProjectRecord, b: ProjectRecord) -> SimilarityFeatures:
    name_sim = fuzz.token_set_ratio(_norm(a.name), _norm(b.name)) / 100.0
    org_sim = fuzz.token_set_ratio(_norm(a.organization), _norm(b.organization)) / 100.0
    desc_sim = (
        fuzz.token_set_ratio(_norm(a.description), _norm(b.description)) / 100.0
        if a.description and b.description
        else 0.0
    )
    overlap = compute_overlap(a.polygon, b.polygon)
    return SimilarityFeatures(
        name_similarity=name_sim,
        org_similarity=org_sim,
        description_similarity=desc_sim,
        area_similarity=area_ratio(a.area_ha, b.area_ha),
        centroid_distance_m=overlap.centroid_distance_m,
        polygon_iou=overlap.polygon_iou,
        polygon_overlap_ratio=overlap.polygon_overlap_ratio,
        cell_overlap_ratio=overlap.cell_overlap_ratio,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Risk score (explainable weighted combo + optional classifier calibration)
# ──────────────────────────────────────────────────────────────────────────────
# Blueprint weights, tuned so geographic overlap dominates — that's the signal
# the smart contract actually enforces, and metadata is easily spoofed.
WEIGHTS = {
    "entity": 0.35,  # avg of name / org / description
    "geo": 0.40,
    "area": 0.10,
    "org": 0.15,
}


def risk_score(features: SimilarityFeatures) -> tuple[float, list[str]]:
    """Return (risk_in_[0,1], human-readable explanation)."""
    entity_sim = np.mean(
        [features.name_similarity, features.org_similarity, features.description_similarity]
    )
    # geo signal combines polygon overlap (direct) and cell overlap (on-chain)
    geo_sim = max(features.polygon_overlap_ratio, features.cell_overlap_ratio)
    score = (
        WEIGHTS["entity"] * entity_sim
        + WEIGHTS["geo"] * geo_sim
        + WEIGHTS["area"] * features.area_similarity
        + WEIGHTS["org"] * features.org_similarity
    )
    score = float(np.clip(score, 0.0, 1.0))

    reasons = []
    if features.cell_overlap_ratio > 0.0:
        reasons.append(
            f"H3 cell overlap: {features.cell_overlap_ratio:.0%} of the smaller polygon"
        )
    if features.polygon_overlap_ratio > 0.1:
        reasons.append(f"polygon overlap: {features.polygon_overlap_ratio:.0%}")
    if features.name_similarity > 0.75:
        reasons.append(f"project name similarity: {features.name_similarity:.0%}")
    if features.org_similarity > 0.75:
        reasons.append(f"organization similarity: {features.org_similarity:.0%}")
    if features.area_similarity > 0.90:
        reasons.append(f"area ratio within {features.area_similarity:.0%}")
    if features.centroid_distance_m < 1_000:
        reasons.append(
            f"centroids within {features.centroid_distance_m:.0f} m"
        )
    if not reasons:
        reasons.append("no strong individual signal")
    return score, reasons


def classify_risk(score: float) -> str:
    if score >= 0.75:
        return "HIGH"
    if score >= 0.40:
        return "MEDIUM"
    return "LOW"


# ──────────────────────────────────────────────────────────────────────────────
# Top-level: score a candidate against a corpus
# ──────────────────────────────────────────────────────────────────────────────
def find_duplicates(
    candidate: ProjectRecord,
    corpus: Sequence[ProjectRecord],
    *,
    blocking_radius_m: float = BLOCKING_RADIUS_M,
    top_k: int | None = 5,
) -> list[DuplicateMatch]:
    """Compare `candidate` to each record in `corpus` within a blocking radius.

    Returns matches sorted by risk score descending. If `top_k` is given, only
    the top-k matches are returned (always includes every HIGH-risk match).
    """
    matches: list[DuplicateMatch] = []
    for other in corpus:
        if other.project_id == candidate.project_id:
            continue
        dist = centroid_distance_m(candidate.polygon, other.polygon)
        if dist > blocking_radius_m:
            continue
        feats = extract_features(candidate, other)
        score, reasons = risk_score(feats)
        matches.append(
            DuplicateMatch(
                candidate_id=candidate.project_id,
                other_id=other.project_id,
                other_registry=other.registry,
                other_registry_ref=other.registry_ref,
                features=feats,
                risk_score=score,
                risk_level=classify_risk(score),
                explanation=reasons,
            )
        )

    matches.sort(key=lambda m: m.risk_score, reverse=True)
    if top_k is None:
        return matches
    high = [m for m in matches if m.risk_level == "HIGH"]
    rest = [m for m in matches if m.risk_level != "HIGH"][: max(0, top_k - len(high))]
    return high + rest


# ──────────────────────────────────────────────────────────────────────────────
# Optional classifier (logistic regression) for calibration against labels
# ──────────────────────────────────────────────────────────────────────────────
def train_classifier(features: Iterable[SimilarityFeatures], labels: Iterable[int]):
    """Train a logistic regression on labeled pairs. Returns a fitted sklearn model."""
    from sklearn.linear_model import LogisticRegression

    X = np.vstack([f.as_vector() for f in features])
    y = np.array(list(labels))
    clf = LogisticRegression(max_iter=1000, class_weight="balanced")
    clf.fit(X, y)
    return clf


def evaluate_classifier(clf, features: Iterable[SimilarityFeatures], labels: Iterable[int]) -> dict:
    """Return precision, recall, F1, and confusion matrix on a held-out set."""
    from sklearn.metrics import (
        confusion_matrix,
        precision_recall_fscore_support,
    )

    X = np.vstack([f.as_vector() for f in features])
    y = np.array(list(labels))
    y_pred = clf.predict(X)
    p, r, f1, _ = precision_recall_fscore_support(
        y, y_pred, average="binary", zero_division=0
    )
    cm = confusion_matrix(y, y_pred, labels=[0, 1]).tolist()
    return {
        "precision": float(p),
        "recall": float(r),
        "f1": float(f1),
        "confusion_matrix": cm,
        "support": int(len(y)),
    }
