"""Geospatial utilities: polygon → H3 cells, overlap, centroid distance.

Resolution 9 is used because its average hexagon edge length (~174 m) and area
(~0.1 km²) make it suitable for forest-restoration projects of a few hundred
hectares: a 500-ha project maps to roughly 50 cells, which is small enough for
on-chain storage yet granular enough to detect partial overlaps.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import h3
from shapely.geometry import Polygon, mapping, shape
from shapely.ops import transform
from pyproj import Transformer

DEFAULT_RESOLUTION = 9  # see module docstring


# ──────────────────────────────────────────────────────────────────────────────
# Polygon → H3 cells
# ──────────────────────────────────────────────────────────────────────────────
def polygon_to_h3_cells(polygon: Polygon, resolution: int = DEFAULT_RESOLUTION) -> list[str]:
    """Return the H3 cells (as string indexes) covering a shapely polygon.

    Uses h3-py v4 ``geo_to_cells`` with LatLngPoly input.
    """
    if polygon.is_empty:
        return []
    exterior = [(y, x) for x, y in polygon.exterior.coords]  # H3 uses (lat, lng)
    holes = [[(y, x) for x, y in interior.coords] for interior in polygon.interiors]
    poly = h3.LatLngPoly(exterior, *holes)
    return list(h3.polygon_to_cells(poly, resolution))


def h3_cells_to_uint64(cells: Iterable[str]) -> list[int]:
    """Convert H3 string cell ids to uint64 integers for on-chain storage."""
    return [int(c, 16) for c in cells]


def uint64_to_h3_cell(cell_int: int) -> str:
    """Convert a uint64 back to an H3 string cell id."""
    return format(cell_int, "x")


# ──────────────────────────────────────────────────────────────────────────────
# Area + distance
# ──────────────────────────────────────────────────────────────────────────────
_WGS84_TO_WEB_MERCATOR = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True).transform


def polygon_area_ha(polygon: Polygon) -> float:
    """Approximate the polygon area in hectares using Web Mercator reprojection.

    Suitable for small projects at mid-latitudes; for high accuracy at the poles
    an equal-area projection should be preferred.
    """
    projected = transform(_WGS84_TO_WEB_MERCATOR, polygon)
    return projected.area / 10_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 points, in meters."""
    r = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def centroid_distance_m(p1: Polygon, p2: Polygon) -> float:
    """Distance between the centroids of two WGS84 polygons, in meters."""
    c1, c2 = p1.centroid, p2.centroid
    return haversine_m(c1.y, c1.x, c2.y, c2.x)


# ──────────────────────────────────────────────────────────────────────────────
# Overlap metrics
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class OverlapResult:
    cell_overlap_count: int
    cell_overlap_ratio: float  # cells in intersection / cells in smaller set
    polygon_iou: float  # intersection-over-union of the raw polygons
    polygon_overlap_ratio: float  # intersection / smaller polygon
    centroid_distance_m: float


def compute_overlap(
    poly_a: Polygon,
    poly_b: Polygon,
    resolution: int = DEFAULT_RESOLUTION,
) -> OverlapResult:
    """Return cell-level and polygon-level overlap metrics between two project polygons."""
    cells_a = set(polygon_to_h3_cells(poly_a, resolution))
    cells_b = set(polygon_to_h3_cells(poly_b, resolution))
    overlap_cells = cells_a & cells_b
    smaller = min(len(cells_a), len(cells_b)) or 1
    cell_ratio = len(overlap_cells) / smaller

    if poly_a.is_empty or poly_b.is_empty:
        iou = 0.0
        poly_ratio = 0.0
    else:
        inter = poly_a.intersection(poly_b).area
        union = poly_a.union(poly_b).area or 1.0
        iou = inter / union
        smaller_area = min(poly_a.area, poly_b.area) or 1.0
        poly_ratio = inter / smaller_area

    return OverlapResult(
        cell_overlap_count=len(overlap_cells),
        cell_overlap_ratio=cell_ratio,
        polygon_iou=iou,
        polygon_overlap_ratio=poly_ratio,
        centroid_distance_m=centroid_distance_m(poly_a, poly_b),
    )


def area_ratio(area_a_ha: float, area_b_ha: float) -> float:
    """Return min/max of two areas, bounded in [0, 1]."""
    if area_a_ha <= 0 or area_b_ha <= 0:
        return 0.0
    return min(area_a_ha, area_b_ha) / max(area_a_ha, area_b_ha)


# ──────────────────────────────────────────────────────────────────────────────
# GeoJSON helpers
# ──────────────────────────────────────────────────────────────────────────────
def polygon_from_geojson(geojson: dict) -> Polygon:
    """Build a shapely polygon from a GeoJSON Polygon feature or geometry."""
    geom = geojson.get("geometry", geojson)
    p = shape(geom)
    if not isinstance(p, Polygon):
        raise ValueError("Only Polygon geometry is supported")
    return p


def polygon_to_geojson(polygon: Polygon) -> dict:
    return mapping(polygon)
