"""Geospatial module tests."""
from __future__ import annotations

from shapely.geometry import Polygon

from pipeline.geospatial import (
    centroid_distance_m,
    compute_overlap,
    h3_cells_to_uint64,
    polygon_area_ha,
    polygon_to_h3_cells,
)


# A ~0.01° square at the equator ≈ ~1.11 km × 1.11 km ≈ 123 ha
SMALL_SQ = Polygon([(0.0, 0.0), (0.01, 0.0), (0.01, 0.01), (0.0, 0.01), (0.0, 0.0)])
OFFSET_SQ = Polygon([(0.005, 0.0), (0.015, 0.0), (0.015, 0.01), (0.005, 0.01), (0.005, 0.0)])
FAR_SQ = Polygon([(10.0, 10.0), (10.01, 10.0), (10.01, 10.01), (10.0, 10.01), (10.0, 10.0)])


def test_polygon_to_h3_cells_nonempty():
    cells = polygon_to_h3_cells(SMALL_SQ, resolution=9)
    assert len(cells) > 0
    assert all(isinstance(c, str) for c in cells)


def test_h3_cells_fit_in_uint64():
    cells = polygon_to_h3_cells(SMALL_SQ, resolution=9)
    ints = h3_cells_to_uint64(cells)
    for i in ints:
        assert 0 <= i < 2**64


def test_polygon_area_ha_small_square():
    area = polygon_area_ha(SMALL_SQ)
    # within ±20% of 123 ha (Web Mercator distortion)
    assert 100 < area < 160


def test_overlap_detects_half_overlap():
    r = compute_overlap(SMALL_SQ, OFFSET_SQ, resolution=9)
    assert r.cell_overlap_count > 0
    assert 0.3 < r.cell_overlap_ratio < 0.8
    assert 0.3 < r.polygon_overlap_ratio < 0.7


def test_overlap_zero_for_far_polygons():
    r = compute_overlap(SMALL_SQ, FAR_SQ, resolution=9)
    assert r.cell_overlap_count == 0
    assert r.polygon_iou == 0.0
    assert r.centroid_distance_m > 1_000_000


def test_centroid_distance_is_haversine():
    d = centroid_distance_m(SMALL_SQ, SMALL_SQ)
    assert d < 1.0  # same polygon, same centroid
