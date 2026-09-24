"""Service boundary for HydroSphere P3.3 inundation calculations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Final, assert_never

from core.hydrorash.inundation import (
    InundationCalculationError,
    InundationEstimate,
    StageAreaPoint,
    inundation_from_stage_area,
    inundation_from_trapezoid,
)
from core.services.geo_service import GeoService, GeoServiceError

__all__ = [
    "INUNDATION_PROVENANCE",
    "GeoJsonSource",
    "InundationError",
    "InundationRequest",
    "InundationResult",
    "InundationService",
    "InundationSource",
    "StageAreaSource",
    "TrapezoidSource",
]

INUNDATION_PROVENANCE: Final = "inundation@1.0"

type JsonValue = str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
type InundationSource = StageAreaSource | TrapezoidSource | GeoJsonSource


@dataclass(frozen=True, slots=True)
class InundationError(ValueError):
    """Invalid inundation request or source data."""

    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True, slots=True)
class StageAreaSource:
    """Explicit stage-area curve from a table or ``MorphoProfile.build_curves``."""

    points: tuple[StageAreaPoint, ...]


@dataclass(frozen=True, slots=True)
class TrapezoidSource:
    """Analytical trapezoidal cross-section."""

    bottom_width_m: float
    side_slope: float = 0.0


@dataclass(frozen=True, slots=True)
class GeoJsonSource:
    """GeoJSON contour features carrying elevation metadata."""

    geojson_text: str


@dataclass(frozen=True, slots=True)
class InundationRequest:
    """Water level plus one typed inundation source."""

    stage_m: float
    source: InundationSource


@dataclass(frozen=True, slots=True)
class InundationResult:
    """JSON-safe inundation estimate with provenance."""

    requested_stage_m: float
    effective_stage_m: float
    area_m2: float
    volume_m3: float
    source: str
    curve: tuple[StageAreaPoint, ...]
    warnings: tuple[str, ...]
    provenance: str

    @property
    def area_km2(self) -> float:
        """Flooded area in square kilometres."""
        return self.area_m2 / 1_000_000.0

    @property
    def volume_mln_m3(self) -> float:
        """Flooded volume in million cubic metres."""
        return self.volume_m3 / 1_000_000.0

    @property
    def volume_km3(self) -> float:
        """Flooded volume in cubic kilometres."""
        return self.volume_m3 / 1_000_000_000.0

    def to_dict(self) -> dict[str, JsonValue]:
        """Serialize the result for tables, reports, and project metadata."""
        return {
            "requested_stage_m": self.requested_stage_m,
            "effective_stage_m": self.effective_stage_m,
            "area_m2": self.area_m2,
            "area_km2": self.area_km2,
            "volume_m3": self.volume_m3,
            "volume_mln_m3": self.volume_mln_m3,
            "volume_km3": self.volume_km3,
            "source": self.source,
            "curve": [
                {"stage_m": point.stage_m, "area_m2": point.area_m2}
                for point in self.curve
            ],
            "warnings": list(self.warnings),
            "provenance": self.provenance,
        }


class InundationService:
    """Dispatch typed inundation sources to the pure core calculations."""

    @staticmethod
    def run(request: InundationRequest) -> InundationResult:
        """Evaluate one inundation request and attach provenance."""
        try:
            match request.source:
                case StageAreaSource(points=points):
                    estimate = inundation_from_stage_area(request.stage_m, points)
                    source_name = "stage_area"
                case TrapezoidSource(
                    bottom_width_m=bottom_width_m,
                    side_slope=side_slope,
                ):
                    estimate = inundation_from_trapezoid(
                        request.stage_m,
                        bottom_width_m,
                        side_slope,
                    )
                    source_name = "trapezoid"
                case GeoJsonSource(geojson_text=geojson_text):
                    points = _stage_area_from_geojson(geojson_text)
                    estimate = inundation_from_stage_area(request.stage_m, points)
                    source_name = "geojson"
                case unreachable:
                    assert_never(unreachable)
        except InundationCalculationError as error:
            raise InundationError(str(error)) from error
        except GeoServiceError as error:
            raise InundationError(str(error)) from error
        return _result_from_estimate(estimate, source_name)


def _result_from_estimate(estimate: InundationEstimate, source: str) -> InundationResult:
    return InundationResult(
        requested_stage_m=estimate.requested_stage_m,
        effective_stage_m=estimate.effective_stage_m,
        area_m2=estimate.area_m2,
        volume_m3=estimate.volume_m3,
        source=source,
        curve=estimate.curve,
        warnings=estimate.warnings,
        provenance=INUNDATION_PROVENANCE,
    )


def _stage_area_from_geojson(text: str) -> tuple[StageAreaPoint, ...]:
    try:
        document: JsonValue = json.loads(text)
    except json.JSONDecodeError as error:
        raise InundationError(f"Некорректный JSON: {error}") from error

    match document:  # noqa: MATCH_OK
        case {"type": "FeatureCollection", "features": list(features)}:
            if not features:
                raise InundationError("GeoJSON FeatureCollection не содержит контуров")
        case {"type": "Feature"}:
            features = [document]
        case _:
            raise InundationError("Ожидался GeoJSON Feature или FeatureCollection")

    service = GeoService()
    points: list[StageAreaPoint] = []
    for feature in features:
        elevation = _feature_elevation(feature)
        summary = service.from_document(feature)
        points.append(StageAreaPoint(stage_m=elevation, area_m2=summary.area_m2))
    return tuple(points)


def _feature_elevation(feature: JsonValue) -> float:
    match feature:  # noqa: MATCH_OK
        case {"properties": {"elevation": value}}:
            return _elevation_value(value)
        case {"properties": {"elevation_m": value}}:
            return _elevation_value(value)
        case _:
            raise InundationError("В свойствах контура отсутствует числовая отметка")


def _elevation_value(value: JsonValue) -> float:
    match value:  # noqa: MATCH_OK
        case bool():
            raise InundationError("Отметка контура должна быть числовой")
        case int() | float() as elevation:
            return float(elevation)
        case _:
            raise InundationError("Отметка контура должна быть числовой")
