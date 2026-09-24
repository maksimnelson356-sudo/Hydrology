"""
core/services/routing_service.py
Thin service adapter for Muskingum flood routing (stage P3.2, decision 11.1 = (a)).

Validation and JSON-safe packaging live here; routing math stays in
``core.hydrorash.routing`` (no math in services).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.hydrorash.routing import MuskingumError, muskingum_route

__all__ = [
    "ROUTING_PROVENANCE",
    "RoutingError",
    "RoutingRequest",
    "RoutingResult",
    "RoutingService",
]

ROUTING_PROVENANCE = "muskingum@1.0"


class RoutingError(Exception):
    """Invalid Muskingum routing request."""


@dataclass(frozen=True, slots=True)
class RoutingRequest:
    """Inflow hydrograph + Muskingum parameters (consistent time units)."""

    inflow: list[float] = field(default_factory=list)
    dt: float = 1.0
    k: float = 0.0
    x: float = 0.0
    outflow0: float | None = None

    def validate(self) -> None:
        """Raise RoutingError on empty/invalid inputs."""
        if not self.inflow:
            raise RoutingError("Входной гидрограф пуст")
        if len(self.inflow) < 2:
            raise RoutingError(
                f"Гидрограф должен содержать минимум 2 точки (получено {len(self.inflow)})"
            )
        if self.dt <= 0:
            raise RoutingError(f"dt должен быть > 0 (получено {self.dt})")
        if self.k < self.dt:
            raise RoutingError(
                f"K должен быть >= dt (K={self.k}, dt={self.dt})"
            )
        if not (0.0 <= self.x <= 0.5):
            raise RoutingError(f"x должен быть в [0, 0.5] (получено {self.x})")
        for i, v in enumerate(self.inflow):
            if v != v or v in (float("inf"), float("-inf")):
                raise RoutingError(f"inflow[{i}] не является конечным числом")
            if v < 0:
                raise RoutingError(f"inflow[{i}] должен быть >= 0 (получено {v})")
        if self.outflow0 is not None and self.outflow0 < 0:
            raise RoutingError(f"outflow0 должен быть >= 0 (получено {self.outflow0})")


@dataclass(frozen=True, slots=True)
class RoutingResult:
    """JSON-safe Muskingum routing result with peak metrics."""

    outflow: list[float]
    coefficients: dict[str, float]
    peak_in_m3s: float
    peak_out_m3s: float
    peak_attenuation_m3s: float
    peak_lag_steps: int
    n_steps: int
    dt: float
    k: float
    x: float
    provenance: str

    def to_dict(self) -> dict[str, Any]:
        """Flat dict for tables / provenance chains."""
        return {
            "outflow": self.outflow,
            "coefficients": self.coefficients,
            "peak_in_m3s": self.peak_in_m3s,
            "peak_out_m3s": self.peak_out_m3s,
            "peak_attenuation_m3s": self.peak_attenuation_m3s,
            "peak_lag_steps": self.peak_lag_steps,
            "n_steps": self.n_steps,
            "dt": self.dt,
            "k": self.k,
            "x": self.x,
            "provenance": self.provenance,
        }


class RoutingService:
    """Orchestrates Muskingum routing without owning math."""

    @staticmethod
    def run(request: RoutingRequest) -> RoutingResult:
        """Validate and evaluate a Muskingum routing request."""
        request.validate()
        try:
            raw = muskingum_route(
                inflow=request.inflow,
                dt=request.dt,
                k=request.k,
                x=request.x,
                outflow0=request.outflow0,
            )
        except MuskingumError as error:
            raise RoutingError(str(error)) from error
        return RoutingResult(
            outflow=raw["outflow"],
            coefficients=raw["coefficients"],
            peak_in_m3s=raw["peak_in_m3s"],
            peak_out_m3s=raw["peak_out_m3s"],
            peak_attenuation_m3s=raw["peak_attenuation_m3s"],
            peak_lag_steps=raw["peak_lag_steps"],
            n_steps=len(request.inflow),
            dt=request.dt,
            k=request.k,
            x=request.x,
            provenance=ROUTING_PROVENANCE,
        )
