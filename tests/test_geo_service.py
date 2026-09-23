"""
tests/test_geo_service.py
P1.6 acceptance tests (DOCS/ROADMAP.md, stage P1.6, decision 9.3 = (b)).

Key criteria covered:
- square contour area matches the analytic reference within tolerance;
- perimeter and centroid of a known ring;
- GeoJSON Feature / FeatureCollection / bare Polygon all load;
- invalid JSON, wrong geometry type and missing files raise GeoServiceError;
- morphometry.to_metadata() is JSON-safe for Dataset.metadata;
- no new runtime dependencies (stdlib json + core.stats.geometry only).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from core.services.geo_service import (
    BasinMorphometry,
    GeoService,
    GeoServiceError,
)
from core.stats.geometry import polygon_area, polygon_centroid, polygon_perimeter

# 1 km × 1 km axis-aligned square in projected metres (not lon/lat).
SQUARE_M = [
    [0.0, 0.0],
    [1000.0, 0.0],
    [1000.0, 1000.0],
    [0.0, 1000.0],
    [0.0, 0.0],
]

# Same square expressed as a closed Feature.
FEATURE_SQUARE = {
    "type": "Feature",
    "properties": {"name": "Квадрат 1 км²"},
    "geometry": {"type": "Polygon", "coordinates": [SQUARE_M]},
}


def write_geojson(tmp_path: Path, document: dict, name: str = "basin.geojson") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


# ----------------------------------------------------------------------
# Geometry primitives (core.stats.geometry)
# ----------------------------------------------------------------------
def test_projected_square_area_and_perimeter():
    area = polygon_area(SQUARE_M)
    peri = polygon_perimeter(SQUARE_M)
    assert area == pytest.approx(1_000_000.0, rel=1e-9)
    assert peri == pytest.approx(4000.0, rel=1e-9)


def test_centroid_of_square_is_center():
    cx, cy = polygon_centroid(SQUARE_M)
    assert cx == pytest.approx(500.0)
    assert cy == pytest.approx(500.0)


def test_ring_without_closing_vertex_matches_closed():
    open_ring = SQUARE_M[:-1]
    assert polygon_area(open_ring) == pytest.approx(polygon_area(SQUARE_M))
    assert polygon_perimeter(open_ring) == pytest.approx(polygon_perimeter(SQUARE_M))


def test_too_short_ring_raises():
    with pytest.raises(ValueError):
        polygon_area([[0.0, 0.0], [1.0, 1.0]])


def test_spherical_square_near_equator_has_positive_area():
    # 1° × 1° near the equator ≈ 12 300 km² (order of magnitude check).
    ring = [
        [30.0, 55.0],
        [31.0, 55.0],
        [31.0, 56.0],
        [30.0, 56.0],
        [30.0, 55.0],
    ]
    area_m2 = polygon_area(ring)
    assert area_m2 > 0
    # ~7 000–8 000 km² for 1°×1° at 55°N.
    km2 = area_m2 / 1_000_000
    assert 5000.0 < km2 < 10_000.0
    peri_m = polygon_perimeter(ring)
    assert peri_m > 0


# ----------------------------------------------------------------------
# GeoService happy paths
# ----------------------------------------------------------------------
def test_load_feature_square(tmp_path: Path):
    path = write_geojson(tmp_path, FEATURE_SQUARE)
    service = GeoService()
    summary = service.load(path)

    assert isinstance(summary, BasinMorphometry)
    assert summary.name == "Квадрат 1 км²"
    assert summary.area_m2 == pytest.approx(1_000_000.0, rel=1e-9)
    assert summary.area_km2 == pytest.approx(1.0, rel=1e-9)
    assert summary.perimeter_m == pytest.approx(4000.0, rel=1e-9)
    assert summary.perimeter_km == pytest.approx(4.0, rel=1e-9)
    assert summary.centroid_lon == pytest.approx(500.0)
    assert summary.centroid_lat == pytest.approx(500.0)
    assert summary.vertex_count == 4
    assert summary.geometry_type == "Polygon"
    assert summary.source_path.endswith("basin.geojson")


def test_load_bare_polygon(tmp_path: Path):
    document = {"type": "Polygon", "coordinates": [SQUARE_M]}
    path = write_geojson(tmp_path, document, "bare.json")
    summary = GeoService().load(path)
    assert summary.area_km2 == pytest.approx(1.0, rel=1e-9)
    assert summary.name == "Бассейн"


def test_load_feature_collection_single_feature(tmp_path: Path):
    document = {
        "type": "FeatureCollection",
        "features": [FEATURE_SQUARE],
    }
    path = write_geojson(tmp_path, document)
    summary = GeoService().load(path)
    assert summary.area_km2 == pytest.approx(1.0, rel=1e-9)


def test_load_multi_polygon_sums_areas(tmp_path: Path):
    # Two disjoint 1 km² squares → 2 km² total.
    square2 = [[2000.0, 0.0], [3000.0, 0.0], [3000.0, 1000.0], [2000.0, 1000.0], [2000.0, 0.0]]
    document = {
        "type": "MultiPolygon",
        "coordinates": [[SQUARE_M], [square2]],
    }
    path = write_geojson(tmp_path, document, "multi.geojson")
    summary = GeoService().load(path)
    assert summary.area_km2 == pytest.approx(2.0, rel=1e-9)
    assert summary.geometry_type == "MultiPolygon"
    assert summary.vertex_count == 8


def test_to_metadata_is_json_safe(tmp_path: Path):
    path = write_geojson(tmp_path, FEATURE_SQUARE)
    summary = GeoService().load(path)
    meta = summary.to_metadata()
    # Round-trip through json proves no non-serialisable values.
    restored = json.loads(json.dumps(meta, ensure_ascii=False))
    assert restored["basin_area_km2"] == pytest.approx(1.0, rel=1e-6)
    assert restored["basin_perimeter_km"] == pytest.approx(4.0, rel=1e-6)
    assert restored["basin_vertex_count"] == 4
    assert restored["contour_name"] == "Квадрат 1 км²"


def test_loads_accepts_text_without_file(tmp_path: Path):
    text = json.dumps(FEATURE_SQUARE, ensure_ascii=False)
    summary = GeoService().loads(text, source_path="inline")
    assert summary.source_path == "inline"
    assert summary.area_km2 == pytest.approx(1.0, rel=1e-9)


# ----------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------
def test_missing_file_raises(tmp_path: Path):
    with pytest.raises(GeoServiceError, match="не найден"):
        GeoService().load(tmp_path / "nope.geojson")


def test_wrong_suffix_raises(tmp_path: Path):
    path = tmp_path / "basin.txt"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(GeoServiceError, match="geojson"):
        GeoService().load(path)


def test_invalid_json_raises(tmp_path: Path):
    path = tmp_path / "bad.geojson"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(GeoServiceError, match="JSON"):
        GeoService().load(path)


def test_unsupported_geometry_type_raises(tmp_path: Path):
    document = {"type": "Point", "coordinates": [30.0, 55.0]}
    path = write_geojson(tmp_path, document, "point.geojson")
    with pytest.raises(GeoServiceError, match="Polygon"):
        GeoService().load(path)


def test_empty_feature_collection_raises(tmp_path: Path):
    document = {"type": "FeatureCollection", "features": []}
    path = write_geojson(tmp_path, document, "empty.geojson")
    with pytest.raises(GeoServiceError, match="features"):
        GeoService().load(path)


def test_feature_without_geometry_raises(tmp_path: Path):
    document = {"type": "Feature", "properties": {}, "geometry": None}
    path = write_geojson(tmp_path, document, "nogeom.geojson")
    with pytest.raises(GeoServiceError):
        GeoService().load(path)


# ----------------------------------------------------------------------
# No new runtime dependencies (decision 9.3 = (b))
# ----------------------------------------------------------------------
def test_geo_service_uses_only_stdlib_and_core():
    """geo_service must not import rasterio / shapely / geopandas / fiona."""
    import ast

    import core.services.geo_service as geo_mod

    banned = {"rasterio", "shapely", "geopandas", "fiona", "osgeo", "pyproj"}
    source = Path(geo_mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    assert not (banned & imported_roots), f"forbidden import: {banned & imported_roots}"
    # Docstring may mention the decision; real check is AST above + geometry works.
    assert polygon_area is not None
    assert math.isclose(polygon_area(SQUARE_M), 1_000_000.0, rel_tol=1e-9)
    assert not (banned & set(vars(geo_mod)))
