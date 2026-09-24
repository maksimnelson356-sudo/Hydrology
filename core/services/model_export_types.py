"""Typed data contracts for HydroSphere engineering-model exchange files."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

from core.services.backwater_profile_service import ReachSpec

MODEL_FORMAT: Final = "hydrosphere-engineering-model"
MODEL_VERSION: Final = "1.0"

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]


class ModelKind(StrEnum):
    """Supported engineering-model exchange kinds."""

    REACHES = "reaches"
    HYDROGRAPH = "hydrograph"
    WSE_PROFILE = "wse_profile"


class ModelExportError(Exception):
    """Typed failure raised at the model import/export boundary."""

    def __init__(self, message: str, path: Path | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.path = path

    def __str__(self) -> str:
        if self.path is None:
            return self.message
        return f"{self.message}: {self.path}"


@dataclass(frozen=True, slots=True)
class ReachExportRequest:
    """Reach chain and destination JSON path."""

    reaches: tuple[ReachSpec, ...]
    target: Path


@dataclass(frozen=True, slots=True)
class HydrographExportRequest:
    """Aligned routing time series and destination JSON path."""

    times_hours: tuple[float, ...]
    inflow: tuple[float, ...]
    outflow: tuple[float, ...]
    target: Path


@dataclass(frozen=True, slots=True)
class WseProfileExportRequest:
    """Aligned WSE profile and destination JSON path."""

    distances_m: tuple[float, ...]
    water_surface_elevation_m: tuple[float, ...]
    target: Path


@dataclass(frozen=True, slots=True)
class ModelExportResult:
    """Paths written by one export operation."""

    kind: ModelKind
    json_path: Path
    csv_path: Path


@dataclass(frozen=True, slots=True)
class ReachModel:
    """Imported reach-chain model."""

    reaches: tuple[ReachSpec, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HydrographModel:
    """Imported routed hydrograph model."""

    times_hours: tuple[float, ...]
    inflow: tuple[float, ...]
    outflow: tuple[float, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class WseProfileModel:
    """Imported water-surface-elevation profile."""

    distances_m: tuple[float, ...]
    water_surface_elevation_m: tuple[float, ...]
    warnings: tuple[str, ...] = ()


type ImportedModel = ReachModel | HydrographModel | WseProfileModel
