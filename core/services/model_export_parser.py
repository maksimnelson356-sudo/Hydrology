"""Tolerant JSON parser for P3.5 engineering-model exchange files."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import assert_never

from core.services.backwater_profile_service import ReachSpec
from core.services.model_export_types import (
    MODEL_FORMAT,
    MODEL_VERSION,
    HydrographModel,
    ImportedModel,
    JsonValue,
    ModelExportError,
    ModelKind,
    ReachModel,
    WseProfileModel,
)


def import_json_model(path: Path) -> ImportedModel:
    """Parse one supported model document into a typed immutable model."""
    try:
        raw_text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as error:
        raise ModelExportError("не удалось прочитать JSON", path) from error
    try:
        raw_value = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise ModelExportError("некорректный JSON", path) from error
    root = _as_mapping(raw_value, "root", path)
    warnings = _metadata_warnings(root, path)
    kind = _model_kind(root.get("kind"), path)
    data = _as_mapping(root.get("data"), "data", path)

    match kind:
        case ModelKind.REACHES:
            return _parse_reaches(data, warnings, path)
        case ModelKind.HYDROGRAPH:
            return _parse_hydrograph(data, warnings, path)
        case ModelKind.WSE_PROFILE:
            return _parse_wse(data, warnings, path)
        case unreachable:
            assert_never(unreachable)


def _metadata_warnings(root: dict[str, JsonValue], path: Path) -> tuple[str, ...]:
    warnings: list[str] = []
    format_value = root.get("format")
    if format_value is None:
        warnings.append("missing optional format metadata")
    elif format_value != MODEL_FORMAT:
        raise ModelExportError(f"unsupported format {format_value!r}", path)
    version_value = root.get("version")
    if version_value is None:
        warnings.append("missing optional version metadata")
    elif version_value != MODEL_VERSION:
        warnings.append(f"unknown model version {version_value!r}; parsed as {MODEL_VERSION}")
    return tuple(warnings)


def _model_kind(value: JsonValue | None, path: Path) -> ModelKind:
    if not isinstance(value, str):
        raise ModelExportError("missing or invalid kind", path)
    try:
        return ModelKind(value)
    except ValueError as error:
        raise ModelExportError(f"unsupported kind {value!r}", path) from error


def _parse_reaches(
    data: dict[str, JsonValue],
    warnings: tuple[str, ...],
    path: Path,
) -> ReachModel:
    raw_reaches = _as_list(data.get("reaches"), "reaches", path)
    if not raw_reaches:
        raise ModelExportError("reaches must not be empty", path)
    reaches: list[ReachSpec] = []
    for index, raw_reach in enumerate(raw_reaches):
        item = _as_mapping(raw_reach, f"reaches[{index}]", path)
        reach = ReachSpec(
            name=_as_str(item.get("name"), f"reaches[{index}].name", path),
            B=_as_float(item.get("B"), f"reaches[{index}].B", path),
            m=_as_float(item.get("m"), f"reaches[{index}].m", path),
            n=_as_float(item.get("n"), f"reaches[{index}].n", path),
            slope=_as_float(item.get("slope"), f"reaches[{index}].slope", path),
            L=_as_float(item.get("L"), f"reaches[{index}].L", path),
        )
        try:
            reach.to_reach().validate()
        except ValueError as error:
            raise ModelExportError(f"invalid reach {index}: {error}", path) from error
        reaches.append(reach)
    return ReachModel(reaches=tuple(reaches), warnings=warnings)


def _parse_hydrograph(
    data: dict[str, JsonValue],
    warnings: tuple[str, ...],
    path: Path,
) -> HydrographModel:
    times = _as_float_list(data.get("times_hours"), "times_hours", path)
    inflow = _as_float_list(data.get("inflow"), "inflow", path)
    outflow = _as_float_list(data.get("outflow"), "outflow", path)
    _require_aligned(
        ("times_hours", times),
        ("inflow", inflow),
        ("outflow", outflow),
        path=path,
    )
    if any(current <= previous for previous, current in zip(times, times[1:], strict=False)):
        raise ModelExportError("times_hours must be strictly increasing", path)
    return HydrographModel(times_hours=times, inflow=inflow, outflow=outflow, warnings=warnings)


def _parse_wse(
    data: dict[str, JsonValue],
    warnings: tuple[str, ...],
    path: Path,
) -> WseProfileModel:
    distances = _as_float_list(data.get("distances_m"), "distances_m", path)
    elevations = _as_float_list(
        data.get("water_surface_elevation_m"),
        "water_surface_elevation_m",
        path,
    )
    _require_aligned(
        ("distances_m", distances),
        ("water_surface_elevation_m", elevations),
        path=path,
    )
    if any(current < previous for previous, current in zip(distances, distances[1:], strict=False)):
        raise ModelExportError("distances_m must be non-decreasing", path)
    return WseProfileModel(
        distances_m=distances,
        water_surface_elevation_m=elevations,
        warnings=warnings,
    )


def _as_mapping(value: JsonValue | None, field: str, path: Path) -> dict[str, JsonValue]:
    match value:
        case dict() if all(isinstance(key, str) for key in value):
            return value
        case dict() | list() | str() | float() | int() | bool() | None:
            raise ModelExportError(f"{field} must be an object", path)
        case unreachable:
            assert_never(unreachable)


def _as_list(value: JsonValue | None, field: str, path: Path) -> list[JsonValue]:
    match value:
        case list():
            return value
        case dict() | str() | float() | int() | bool() | None:
            raise ModelExportError(f"{field} must be an array", path)
        case unreachable:
            assert_never(unreachable)


def _as_str(value: JsonValue | None, field: str, path: Path) -> str:
    match value:
        case str() as text:
            return text
        case dict() | list() | float() | int() | bool() | None:
            raise ModelExportError(f"{field} must be a string", path)
        case unreachable:
            assert_never(unreachable)


def _as_float(value: JsonValue | None, field: str, path: Path) -> float:
    match value:
        case float() | int() if not isinstance(value, bool) and math.isfinite(float(value)):
            return float(value)
        case dict() | list() | str() | float() | int() | bool() | None:
            raise ModelExportError(f"{field} must be a finite number", path)
        case unreachable:
            assert_never(unreachable)


def _as_float_list(value: JsonValue | None, field: str, path: Path) -> tuple[float, ...]:
    values = _as_list(value, field, path)
    return tuple(_as_float(item, f"{field}[{index}]", path) for index, item in enumerate(values))


def _require_aligned(
    *series: tuple[str, tuple[float, ...]],
    path: Path,
) -> None:
    if not series:
        return
    expected_length = len(series[0][1])
    if any(len(values) != expected_length for _, values in series[1:]):
        names = ", ".join(name for name, _ in series)
        raise ModelExportError(f"{names} must have equal length", path)
    if expected_length == 0:
        names = ", ".join(name for name, _ in series)
        raise ModelExportError(f"{names} must not be empty", path)
