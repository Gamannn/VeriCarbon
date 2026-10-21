"""Entity resolution + duplicate-risk scoring tests."""
from __future__ import annotations

from shapely.geometry import Polygon

from pipeline.entity_resolution import (
    ProjectRecord,
    classify_risk,
    extract_features,
    find_duplicates,
    risk_score,
)


def _rec(pid: str, name: str, org: str, poly: Polygon, area_ha: float, desc: str = "") -> ProjectRecord:
    return ProjectRecord(
        project_id=pid,
        name=name,
        organization=org,
        description=desc,
        polygon=poly,
        area_ha=area_ha,
        registry="TEST",
        registry_ref=pid,
    )


POLY_A = Polygon([(0.0, 0.0), (0.02, 0.0), (0.02, 0.02), (0.0, 0.02), (0.0, 0.0)])
POLY_A_SHIFTED = Polygon(
    [(0.005, 0.005), (0.025, 0.005), (0.025, 0.025), (0.005, 0.025), (0.005, 0.005)]
)
POLY_FAR = Polygon([(10.0, 10.0), (10.02, 10.0), (10.02, 10.02), (10.0, 10.02), (10.0, 10.0)])


def test_identical_projects_yield_high_risk():
    a = _rec("a", "Amazonia Reforest Pilot", "GreenForest Inc", POLY_A, 500)
    b = _rec("b", "Amazonia Reforest Pilot", "GreenForest Inc", POLY_A, 500)
    feats = extract_features(a, b)
    score, _ = risk_score(feats)
    assert classify_risk(score) == "HIGH"
    assert score > 0.80


def test_overlapping_polygons_different_names_still_high_risk():
    """Core differentiator: cell overlap catches renamed duplicates."""
    a = _rec("a", "Amazonia Reforest Pilot", "GreenForest Inc", POLY_A, 500)
    b = _rec(
        "b",
        "Rio Verde Carbon Project",
        "EcoAlpha Foundation",
        POLY_A_SHIFTED,
        450,
    )
    feats = extract_features(a, b)
    assert feats.cell_overlap_ratio > 0.1
    assert feats.polygon_overlap_ratio > 0.1
    score, _ = risk_score(feats)
    assert classify_risk(score) in ("MEDIUM", "HIGH")


def test_distant_projects_low_risk():
    a = _rec("a", "Amazonia Reforest Pilot", "GreenForest Inc", POLY_A, 500)
    b = _rec("b", "Himalayan Restoration", "Mountain Trust", POLY_FAR, 500)
    feats = extract_features(a, b)
    score, _ = risk_score(feats)
    assert classify_risk(score) == "LOW"


def test_find_duplicates_blocks_by_distance():
    candidate = _rec("cand", "Amazonia Reforest Pilot", "GreenForest Inc", POLY_A, 500)
    corpus = [
        _rec("near", "Rio Verde", "EcoAlpha", POLY_A_SHIFTED, 450),
        _rec("far", "Himalayan Restoration", "Mountain Trust", POLY_FAR, 500),
    ]
    matches = find_duplicates(candidate, corpus, top_k=10)
    ids = {m.other_id for m in matches}
    assert "near" in ids
    assert "far" not in ids  # blocked by 50 km radius


def test_find_duplicates_returns_sorted_desc():
    candidate = _rec("cand", "Amazonia Reforest Pilot", "GreenForest Inc", POLY_A, 500)
    corpus = [
        _rec("exact", "Amazonia Reforest Pilot", "GreenForest Inc", POLY_A, 500),
        _rec("partial", "Rio Verde", "EcoAlpha", POLY_A_SHIFTED, 450),
    ]
    matches = find_duplicates(candidate, corpus, top_k=10)
    assert len(matches) == 2
    assert matches[0].risk_score >= matches[1].risk_score
    assert matches[0].other_id == "exact"
