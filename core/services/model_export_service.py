"""P3.5 JSON/CSV engineering-model exchange service."""

from __future__ import annotations

import csv
import io
import json
import math
from collections.abc import Sequence
from pathlib import Path

from core.services.backwater_profile_service import ReachSpec
from core.services.model_export_parser import import_json_model
from core.services.model_export_types import (
    MODEL_FORMAT,
    MODEL_VERSION,
    HydrographExportRequest,
    HydrographModel,
    ImportedModel,
    JsonValue,
    ModelExportError,
    ModelExportResult,
    ModelKind,
    ReachExportRequest,
    ReachModel,
    WseProfileExportRequest,
    WseProfileModel,
)

CsvCell = str | float


def export_reaches(request: ReachExportRequest) -> ModelExportResult:
    """Export a validated reach chain to UTF-8-SIG JSON and CSV."""
    _validate_reaches(request.reaches, request.target)
    data: dict[str, JsonValue] = {
        "reaches": [
            {
                "name": reach.name,
                "B": reach.B,
                "m": reach.m,
                "n": reach.n,
                "slope": reach.slope,
                "L": reach.L,
            }
            for reach in request.reaches
        ]
    }
    headers = ("name", "B_m", "m", "n", "slope", "L_m")
    rows: list[list[CsvCell]] = [
        [reach.name, reach.B, reach.m, reach.n, reach.slope, reach.L]
        for reach in request.reaches
    ]
    return _write_pair(request.target, ModelKind.REACHES, data, headers, rows)


def export_hydrograph(request: HydrographExportRequest) -> ModelExportResult:
    """Export aligned inflow/outflow hydrograph arrays to JSON and CSV."""
    _validate_series(
        ("times_hours", request.times_hours),
        ("inflow", request.inflow),
        ("outflow", request.outflow),
        target=request.target,
    )
    data: dict[str, JsonValue] = {
        "times_hours": list(request.times_hours),
        "inflow": list(request.inflow),
        "outflow": list(request.outflow),
    }
    headers = ("time_h", "inflow_m3s", "outflow_m3s")
    rows: list[list[CsvCell]] = [
        [time, inflow, outflow]
        for time, inflow, outflow in zip(
            request.times_hours,
            request.inflow,
            request.outflow,
            strict=True,
        )
    ]
    return _write_pair(request.target, ModelKind.HYDROGRAPH, data, headers, rows)


def export_wse_profile(request: WseProfileExportRequest) -> ModelExportResult:
    """Export aligned distance/WSE samples to JSON and CSV."""
    _validate_series(
        ("distances_m", request.distances_m),
        ("water_surface_elevation_m", request.water_surface_elevation_m),
        target=request.target,
    )
    if any(
        current < previous
        for previous, current in zip(request.distances_m, request.distances_m[1:], strict=False)
    ):
        raise ModelExportError("distances_m must be non-decreasing", request.target)
    data: dict[str, JsonValue] = {
        "distances_m": list(request.distances_m),
        "water_surface_elevation_m": list(request.water_surface_elevation_m),
    }
    headers = ("distance_m", "wse_m")
    rows: list[list[CsvCell]] = [
        [distance, elevation]
        for distance, elevation in zip(
            request.distances_m,
            request.water_surface_elevation_m,
            strict=True,
        )
    ]
    return _write_pair(request.target, ModelKind.WSE_PROFILE, data, headers, rows)


def _validate_reaches(reaches: tuple[ReachSpec, ...], target: Path) -> None:
    if not reaches:
        raise ModelExportError("reaches must not be empty", target)
    for reach in reaches:
        try:
            reach.to_reach().validate()
        except ValueError as error:
            raise ModelExportError(str(error), target) from error


def _validate_series(*series: tuple[str, tuple[float, ...]], target: Path) -> None:
    if not series:
        raise ModelExportError("no data series", target)
    expected_length = len(series[0][1])
    if expected_length == 0:
        raise ModelExportError(f"{series[0][0]} must not be empty", target)
    for _, values in series[1:]:
        if len(values) != expected_length:
            raise ModelExportError("time, inflow and outflow must have equal length", target)
    for name, values in series:
        if any(not math.isfinite(value) for value in values):
            raise ModelExportError(f"{name} must contain finite values", target)


def _write_pair(
    target: Path,
    kind: ModelKind,
    data: dict[str, JsonValue],
    headers: Sequence[str],
    rows: Sequence[Sequence[CsvCell]],
) -> ModelExportResult:
    json_path = target.with_suffix(".json")
    csv_path = target.with_suffix(".csv")
    payload: dict[str, JsonValue] = {
        "format": MODEL_FORMAT,
        "version": MODEL_VERSION,
        "kind": kind.value,
        "data": data,
    }
    json_text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    csv_buffer = io.StringIO(newline="")
    writer = csv.writer(csv_buffer, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    _atomic_write(json_path, json_text)
    _atomic_write(csv_path, csv_buffer.getvalue())
    return ModelExportResult(kind=kind, json_path=json_path, csv_path=csv_path)


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(content, encoding="utf-8-sig", newline="")
        temporary.replace(path)
    except (OSError, UnicodeError) as error:
        raise ModelExportError("could not write model file", path) from error
    finally:
        if temporary.exists():
            temporary.unlink()


__all__ = [
    "HydrographExportRequest",
    "HydrographModel",
    "ImportedModel",
    "ModelExportError",
    "ModelExportResult",
    "ModelKind",
    "ReachExportRequest",
    "ReachModel",
    "WseProfileExportRequest",
    "WseProfileModel",
    "export_hydrograph",
    "export_reaches",
    "export_wse_profile",
    "import_json_model",
]
