"""
core/services/geo_service.py
Basin morphometry from GeoJSON contours (stage P1.6, decision 9.3 = (b)).

Parses a Feature / FeatureCollection / bare Polygon|MultiPolygon with the
stdlib `json` module and computes area, perimeter and centroid via
`core.stats.geometry`. No rasterio, no QtGIS, no new runtime dependencies.

Services contain no mathematics: geometry stays in `core.stats.geometry`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.stats.geometry import polygon_area, polygon_centroid, polygon_perimeter

__all__ = [
    "BasinMorphometry",
    "GeoService",
    "GeoServiceError",
]

SUPPORTED_SUFFIXES = {".geojson", ".json"}


class GeoServiceError(ValueError):
    """Raised when a GeoJSON file cannot be turned into basin morphometry."""


@dataclass(frozen=True)
class BasinMorphometry:
    """Summary of a basin contour ready for Dataset.metadata / UI."""

    name: str
    area_m2: float
    perimeter_m: float
    centroid_lon: float
    centroid_lat: float
    vertex_count: int
    geometry_type: str
    source_path: str = ""
    properties: dict[str, Any] = field(default_factory=dict)

    @property
    def area_km2(self) -> float:
        """Area in square kilometres."""
        return self.area_m2 / 1_000_000.0

    @property
    def perimeter_km(self) -> float:
        """Perimeter in kilometres."""
        return self.perimeter_m / 1_000.0

    def to_metadata(self) -> dict[str, Any]:
        """Flat dict suitable for Dataset.metadata / project parameters."""
        return {
            "contour_name": self.name,
            "basin_area_km2": round(self.area_km2, 6),
            "basin_perimeter_km": round(self.perimeter_km, 6),
            "basin_centroid_lon": round(self.centroid_lon, 8),
            "basin_centroid_lat": round(self.centroid_lat, 8),
            "basin_vertex_count": self.vertex_count,
            "basin_geometry_type": self.geometry_type,
            "basin_source_path": self.source_path,
        }


class GeoService:
    """Import GeoJSON basin contours and compute morphometry summaries."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load(self, path: str | Path) -> BasinMorphometry:
        """
        Read a GeoJSON file and return basin morphometry.

        Raises:
            GeoServiceError: missing file, bad suffix, invalid JSON or
                geometry that is not Polygon / MultiPolygon.
        """
        resolved = Path(path)
        if not resolved.exists():
            raise GeoServiceError(f"Файл контура не найден: {resolved}")
        if resolved.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise GeoServiceError(
                f"Ожидался .geojson или .json, получено: {resolved.suffix or '(нет)'}"
            )
        try:
            text = resolved.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as error:
            raise GeoServiceError(f"Не удалось прочитать контур: {error}") from error
        return self.loads(text, source_path=str(resolved))

    def loads(self, text: str, *, source_path: str = "", name: str = "") -> BasinMorphometry:
        """Parse GeoJSON text into morphometry (see `load`)."""
        try:
            document = json.loads(text)
        except json.JSONDecodeError as error:
            raise GeoServiceError(f"Некорректный JSON: {error}") from error
        return self.from_document(document, source_path=source_path, name=name)

    def from_document(
        self,
        document: Any,
        *,
        source_path: str = "",
        name: str = "",
    ) -> BasinMorphometry:
        """
        Build morphometry from an already-parsed GeoJSON object.

        Accepts Feature, FeatureCollection, Geometry, or a bare geometry
        mapping with a `type` field. Only Polygon / MultiPolygon are used.
        """
        if not isinstance(document, dict):
            raise GeoServiceError("GeoJSON должен быть объектом (dict)")

        geo_type = document.get("type")
        if geo_type == "FeatureCollection":
            return self._from_feature_collection(document, source_path, name)
        if geo_type == "Feature":
            return self._from_feature(document, source_path, name)
        if geo_type in {"Polygon", "MultiPolygon"}:
            return self._from_geometry(document, source_path, name)
        raise GeoServiceError(
            f"Неподдерживаемый GeoJSON type={geo_type!r}: "
            "нужен Feature, FeatureCollection, Polygon или MultiPolygon"
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _from_feature_collection(
        self,
        document: dict[str, Any],
        source_path: str,
        name: str,
    ) -> BasinMorphometry:
        features = document.get("features")
        if not isinstance(features, list) or not features:
            raise GeoServiceError("FeatureCollection не содержит features")
        # Single-feature collections are the common export shape.
        if len(features) == 1 and isinstance(features[0], dict):
            return self._from_feature(features[0], source_path, name)
        # Multi-feature: merge all polygon rings into one summary.
        polygons: list[Any] = []
        props: dict[str, Any] = {}
        for feature in features:
            if not isinstance(feature, dict):
                raise GeoServiceError("Feature в коллекции должен быть объектом")
            geometry = feature.get("geometry")
            if not isinstance(geometry, dict):
                continue
            gtype = geometry.get("type")
            if gtype == "Polygon":
                polygons.append(geometry.get("coordinates"))
            elif gtype == "MultiPolygon":
                polys = geometry.get("coordinates")
                if isinstance(polys, list):
                    polygons.extend(polys)
            if feature.get("properties") and not props:
                props = dict(feature["properties"])
        if not polygons:
            raise GeoServiceError("В FeatureCollection нет Polygon/MultiPolygon")
        return self._summary_from_polygons(
            polygons,
            source_path=source_path,
            name=name or str(props.get("name") or "Бассейн"),
            geometry_type="MultiPolygon" if len(polygons) > 1 else "Polygon",
            properties=props,
        )

    def _from_feature(
        self,
        feature: dict[str, Any],
        source_path: str,
        name: str,
    ) -> BasinMorphometry:
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            raise GeoServiceError("Feature без geometry")
        props = feature.get("properties")
        properties = dict(props) if isinstance(props, dict) else {}
        feature_name = name or str(properties.get("name") or "")
        return self._from_geometry(
            geometry,
            source_path,
            feature_name,
            properties=properties,
        )

    def _from_geometry(
        self,
        geometry: dict[str, Any],
        source_path: str,
        name: str,
        *,
        properties: dict[str, Any] | None = None,
    ) -> BasinMorphometry:
        gtype = geometry.get("type")
        coords = geometry.get("coordinates")
        if gtype == "Polygon":
            polygons: list[Any] = [coords]
            effective_type = "Polygon"
        elif gtype == "MultiPolygon":
            if not isinstance(coords, list):
                raise GeoServiceError("MultiPolygon coordinates must be a list")
            polygons = coords
            effective_type = "MultiPolygon"
        else:
            raise GeoServiceError(
                f"Ожидался Polygon/MultiPolygon, получено: {gtype!r}"
            )
        return self._summary_from_polygons(
            polygons,
            source_path=source_path,
            name=name or "Бассейн",
            geometry_type=effective_type,
            properties=properties or {},
        )

    def _summary_from_polygons(
        self,
        polygons: Iterable[Any],
        *,
        source_path: str,
        name: str,
        geometry_type: str,
        properties: dict[str, Any],
    ) -> BasinMorphometry:
        rings_outer: list[Sequence[Sequence[float]]] = []
        for poly in polygons:
            if not isinstance(poly, list) or not poly:
                raise GeoServiceError("Polygon coordinates: expected non-empty ring list")
            outer = poly[0]
            if not isinstance(outer, list) or len(outer) < 3:
                raise GeoServiceError("Внешнее кольцо должно содержать минимум 3 вершины")
            rings_outer.append(outer)

        area_m2 = 0.0
        perimeter_m = 0.0
        vertex_count = 0
        lon_sum = 0.0
        lat_sum = 0.0
        n_vertices = 0
        for ring in rings_outer:
            area_m2 += polygon_area(ring)
            perimeter_m += polygon_perimeter(ring)
            cx, cy = polygon_centroid(ring)
            lon_sum += cx
            lat_sum += cy
            # Count distinct vertices (drop closing duplicate if present).
            pairs = [
                (float(p[0]), float(p[1]))
                for p in ring
                if len(p) >= 2
            ]
            if len(pairs) >= 2 and pairs[0] == pairs[-1]:
                pairs = pairs[:-1]
            vertex_count += len(pairs)
            n_vertices += len(pairs)

        if n_vertices == 0:
            raise GeoServiceError("Контур не содержит вершин")

        return BasinMorphometry(
            name=name,
            area_m2=area_m2,
            perimeter_m=perimeter_m,
            centroid_lon=lon_sum / len(rings_outer),
            centroid_lat=lat_sum / len(rings_outer),
            vertex_count=vertex_count,
            geometry_type=geometry_type,
            source_path=source_path,
            properties=properties,
        )
