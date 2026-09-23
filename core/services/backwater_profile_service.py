"""
core/services/backwater_profile_service.py
Thin service adapter for multi-reach backwater profiles (stage P3.1).

Validation and JSON-safe packaging live here; all hydraulics stay in
``core.hydraulics_profile`` → ``core.hydrorash.backwater`` (no math in services).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.hydraulics_profile import Reach, route_backwater_profile

__all__ = [
    "BACKWATER_PROFILE_PROVENANCE",
    "BackwaterProfileError",
    "BackwaterProfileRequest",
    "BackwaterProfileResult",
    "BackwaterProfileService",
    "ReachSpec",
]

BACKWATER_PROFILE_PROVENANCE = "backwater_profile@1.0"


class BackwaterProfileError(Exception):
    """Invalid multi-reach backwater request."""


@dataclass(frozen=True)
class ReachSpec:
    """Plain-data reach description (serializable, no core types in the API)."""

    name: str
    B: float
    m: float
    n: float
    #: Bed slope (core param ``I``); named ``slope`` for lint.
    slope: float
    L: float

    def to_reach(self) -> Reach:
        """Convert to the core Reach dataclass."""
        return Reach(
            name=self.name,
            B=self.B,
            m=self.m,
            n=self.n,
            slope=self.slope,
            L=self.L,
        )


@dataclass(frozen=True)
class BackwaterProfileRequest:
    """Downstream control + ordered reach chain (downstream → upstream)."""

    reaches: list[ReachSpec] = field(default_factory=list)
    Q: float = 0.0
    H_downstream: float = 0.0
    dx: float = 100.0

    def validate(self) -> None:
        """Raise BackwaterProfileError on empty/invalid inputs."""
        if not self.reaches:
            raise BackwaterProfileError("Список пролётов пуст")
        if self.Q <= 0:
            raise BackwaterProfileError(f"Q должен быть > 0 (получено {self.Q})")
        if self.H_downstream < 0:
            raise BackwaterProfileError(
                f"H_downstream должен быть >= 0 (получено {self.H_downstream})"
            )
        if self.dx <= 0:
            raise BackwaterProfileError(f"dx должен быть > 0 (получено {self.dx})")
        names = [r.name for r in self.reaches]
        if any(not name for name in names):
            raise BackwaterProfileError("Каждый пролёт должен иметь имя")
        if len(set(names)) != len(names):
            raise BackwaterProfileError("Имена пролётов должны быть уникальны")
        for spec in self.reaches:
            try:
                spec.to_reach().validate()
            except ValueError as error:
                raise BackwaterProfileError(str(error)) from error
        # (geometry errors surface as BackwaterProfileError above)


@dataclass(frozen=True)
class BackwaterProfileResult:
    """JSON-safe multi-reach profile result."""

    reaches: list[dict[str, Any]]
    distances_m: list[float]
    depths_m: list[float]
    L_total_m: float
    Q: float
    H_downstream: float
    provenance: str

    def to_dict(self) -> dict[str, Any]:
        """Flat dict for tables / provenance chains."""
        return {
            "reaches": self.reaches,
            "distances_m": self.distances_m,
            "depths_m": self.depths_m,
            "L_total_m": self.L_total_m,
            "Q": self.Q,
            "H_downstream": self.H_downstream,
            "provenance": self.provenance,
        }


class BackwaterProfileService:
    """Orchestrates multi-reach backwater routing without owning math."""

    @staticmethod
    def run(request: BackwaterProfileRequest) -> BackwaterProfileResult:
        """Validate and evaluate a multi-reach profile request."""
        request.validate()
        core_reaches = [spec.to_reach() for spec in request.reaches]
        try:
            raw = route_backwater_profile(
                reaches=core_reaches,
                q=request.Q,
                h_downstream=request.H_downstream,
                dx=request.dx,
            )
        except ValueError as error:
            raise BackwaterProfileError(str(error)) from error
        return BackwaterProfileResult(
            reaches=raw["reaches"],
            distances_m=raw["distances_m"],
            depths_m=raw["depths_m"],
            L_total_m=raw["L_total_m"],
            Q=raw["Q"],
            H_downstream=raw["H_downstream"],
            provenance=BACKWATER_PROFILE_PROVENANCE,
        )
