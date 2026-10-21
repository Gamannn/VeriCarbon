"""Satellite verification tests (fixture mode only — no network required)."""
from __future__ import annotations

from shapely.geometry import Polygon

from pipeline.satellite import verify_from_fixture, VerificationResult


POLY = Polygon(
    [(-60.0, -3.0), (-59.99, -3.0), (-59.99, -2.99), (-60.0, -2.99), (-60.0, -3.0)]
)


def test_fixture_mode_labels_results_as_fixture():
    r = verify_from_fixture("amazonia-pilot-01", POLY, claimed_area_ha=500.0)
    assert isinstance(r, VerificationResult)
    assert r.mode == "fixture"
    assert any("fixture" in n.lower() for n in r.notes)


def test_fixture_mode_verifies_well_supported_project():
    r = verify_from_fixture("amazonia-pilot-01", POLY, claimed_area_ha=500.0)
    assert r.outcome == "VERIFIED"
    assert r.confidence_bps >= 7000
    assert r.estimated_vegetated_area_ha > 400


def test_fixture_mode_requires_review_for_partial_evidence():
    r = verify_from_fixture("kalimantan-pilot-02", POLY, claimed_area_ha=250.0)
    assert r.outcome == "REQUIRES_REVIEW"
    assert 2500 < r.confidence_bps < 8000


def test_fixture_mode_rejects_overclaim():
    r = verify_from_fixture("congo-pilot-03", POLY, claimed_area_ha=1000.0)
    assert r.outcome == "REJECT"


def test_hashes_are_deterministic():
    r1 = verify_from_fixture("amazonia-pilot-01", POLY, claimed_area_ha=500.0)
    r2 = verify_from_fixture("amazonia-pilot-01", POLY, claimed_area_ha=500.0)
    assert r1.dataset_hash == r2.dataset_hash
    assert r1.model_hash == r2.model_hash
    assert r1.result_hash == r2.result_hash


def test_different_polygon_changes_dataset_hash():
    other = Polygon(
        [(10.0, 10.0), (10.01, 10.0), (10.01, 10.01), (10.0, 10.01), (10.0, 10.0)]
    )
    r1 = verify_from_fixture("amazonia-pilot-01", POLY, claimed_area_ha=500.0)
    r2 = verify_from_fixture("amazonia-pilot-01", other, claimed_area_ha=500.0)
    assert r1.dataset_hash != r2.dataset_hash


# ──────────────────────────────────────────────────────────────────────────────
# Synthetic mode — the fallback used by the live dashboard
# ──────────────────────────────────────────────────────────────────────────────
from pipeline.satellite import verify_synthetic


def test_synthetic_mode_labels_results_as_synthetic():
    r = verify_synthetic("user-pilot-xyz", POLY, claimed_area_ha=400.0)
    assert r.mode == "synthetic"
    assert any("SYNTHETIC" in n or "synthetic" in n for n in r.notes)


def test_synthetic_mode_is_deterministic():
    r1 = verify_synthetic("user-pilot-xyz", POLY, claimed_area_ha=400.0)
    r2 = verify_synthetic("user-pilot-xyz", POLY, claimed_area_ha=400.0)
    assert r1.dataset_hash == r2.dataset_hash
    assert r1.result_hash == r2.result_hash
    assert r1.ndvi_mean == r2.ndvi_mean


def test_synthetic_mode_different_project_different_result():
    r1 = verify_synthetic("project-A", POLY, claimed_area_ha=400.0)
    r2 = verify_synthetic("project-B", POLY, claimed_area_ha=400.0)
    assert r1.result_hash != r2.result_hash  # project id must enter the hash


def test_synthetic_mode_produces_plausible_ranges():
    r = verify_synthetic("whatever", POLY, claimed_area_ha=400.0)
    assert 0.3 < r.ndvi_mean < 0.85
    assert 0.0 <= r.ndvi_forest_fraction <= 1.0
    assert r.estimated_vegetated_area_ha >= 0
    assert r.outcome in ("VERIFIED", "REQUIRES_REVIEW", "REJECT")
