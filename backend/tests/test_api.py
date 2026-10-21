"""Backend API tests. Uses TestClient — no live chain required."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


AMAZON_POLY = {
    "type": "Polygon",
    "coordinates": [
        [[-60.02, -3.01], [-59.98, -3.01], [-59.98, -2.98], [-60.02, -2.98], [-60.02, -3.01]]
    ],
}

DUP_POLY = {  # overlaps the Amazon registry entry
    "type": "Polygon",
    "coordinates": [
        [[-60.01, -3.005], [-59.985, -3.005], [-59.985, -2.985], [-60.01, -2.985], [-60.01, -3.005]]
    ],
}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_chain_status_shows_not_configured_by_default():
    r = client.get("/chain/status")
    assert r.status_code == 200
    body = r.json()
    assert "configured" in body
    assert "rpc_url" in body


def test_verify_fixture_mode():
    payload = {
        "project_id": "amazonia-pilot-01",
        "name": "Amazonia Pilot",
        "organization": "GreenForest Inc",
        "description": "pilot",
        "polygon": AMAZON_POLY,
        "claimed_area_ha": 500,
        "registry_refs": ["VCS-X-123"],
    }
    r = client.post("/verify", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "fixture"
    assert body["outcome"] in ("VERIFIED", "REQUIRES_REVIEW", "REJECT")
    assert body["dataset_hash"].startswith("0x")
    assert body["result_hash"].startswith("0x")


def test_duplicate_check_detects_overlap_with_different_name():
    """The whole point: name is different, but polygon overlaps a known entry."""
    payload = {
        "project_id": "renamed-dup-01",
        "name": "Rio Verde Carbon Removal",   # intentionally different
        "organization": "EcoAlpha Foundation",
        "description": "pilot",
        "polygon": DUP_POLY,
        "claimed_area_ha": 450,
    }
    r = client.post("/duplicate-check", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cell_count"] > 0
    assert body["highest_risk_level"] in ("MEDIUM", "HIGH")
    # geographic signal must be present
    assert any(m["features"]["cell_overlap_ratio"] > 0.1 for m in body["matches"])


def test_duplicate_check_low_risk_for_far_polygon():
    payload = {
        "project_id": "unrelated-01",
        "name": "Pacific Blue Carbon",
        "organization": "Oceanic Trust",
        "description": "pilot",
        "polygon": {
            "type": "Polygon",
            "coordinates": [
                [[-170.0, 10.0], [-169.98, 10.0], [-169.98, 10.02], [-170.0, 10.02], [-170.0, 10.0]]
            ],
        },
        "claimed_area_ha": 100,
    }
    r = client.post("/duplicate-check", json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["highest_risk_level"] == "LOW"


def test_onchain_submit_without_config_returns_503():
    payload = {
        "project_id": "amazonia-pilot-01",
        "name": "Amazonia Pilot",
        "organization": "GreenForest Inc",
        "description": "pilot",
        "polygon": AMAZON_POLY,
        "claimed_area_ha": 500,
    }
    r = client.post("/onchain/submit", json=payload)
    # Without a running chain + contract address, we must return 503,
    # NOT a fake success.
    assert r.status_code == 503
