"""Typed defaults and request construction for the P3.4 panel."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, assert_never

from core.hydrorash.inundation import StageAreaPoint
from core.services.backwater_profile_service import ReachSpec
from core.services.hydraulic_uncertainty_service import (
    BackwaterMonteCarloBaseline,
    HydraulicBaseline,
    HydraulicUncertaintyError,
    HydraulicUncertaintyRequest,
    RoutingMonteCarloBaseline,
)
from core.services.monte_carlo_service import ParameterSpec

_DEFAULT_REACHES: Final = (
    ReachSpec(name="Нижний", B=20.0, m=2.0, n=0.035, slope=0.001, L=500.0),
    ReachSpec(name="Верхний", B=15.0, m=1.5, n=0.040, slope=0.002, L=500.0),
)
_DEFAULT_STAGE_AREA: Final = (
    StageAreaPoint(stage_m=0.0, area_m2=0.0),
    StageAreaPoint(stage_m=2.0, area_m2=20_000.0),
    StageAreaPoint(stage_m=4.0, area_m2=60_000.0),
    StageAreaPoint(stage_m=8.0, area_m2=160_000.0),
)
_DEFAULT_INFLOW: Final = (0.0, 20.0, 50.0, 100.0, 80.0, 50.0, 30.0, 15.0, 5.0)


class HydraulicEngine(StrEnum):
    """Hydraulic model families exposed by the P3.4 panel."""

    BACKWATER = "backwater"
    ROUTING = "routing"


@dataclass(frozen=True, slots=True)
class HydraulicParameterRow:
    """Raw editable row passed from the Qt table to the typed request builder."""

    name: str
    distribution: str
    low: str
    high: str


_DEFAULT_BACKWATER_ROWS: Final = (
    HydraulicParameterRow("Q", "uniform", "40", "60"),
    HydraulicParameterRow("H_downstream", "uniform", "4.5", "5.5"),
    HydraulicParameterRow("n_scale", "uniform", "0.9", "1.1"),
    HydraulicParameterRow("slope_scale", "uniform", "0.9", "1.1"),
)
_DEFAULT_ROUTING_ROWS: Final = (
    HydraulicParameterRow("Q_scale", "uniform", "0.8", "1.2"),
    HydraulicParameterRow("K", "uniform", "5.5", "6.5"),
    HydraulicParameterRow("x", "uniform", "0.15", "0.20"),
)


def parse_engine(value: str) -> HydraulicEngine:
    """Parse the combo-box value into a closed hydraulic engine type."""
    try:
        return HydraulicEngine(value)
    except ValueError as error:
        raise HydraulicUncertaintyError(f"Неизвестный гидравлический движок: {value}") from error


def default_parameter_rows(engine: HydraulicEngine) -> tuple[HydraulicParameterRow, ...]:
    """Return editable defaults for the selected hydraulic engine."""
    match engine:
        case HydraulicEngine.BACKWATER:
            return _DEFAULT_BACKWATER_ROWS
        case HydraulicEngine.ROUTING:
            return _DEFAULT_ROUTING_ROWS
        case unreachable:
            assert_never(unreachable)


def build_hydraulic_request(
    engine: HydraulicEngine,
    rows: Sequence[HydraulicParameterRow],
    n_runs: int,
    seed: int,
) -> HydraulicUncertaintyRequest:
    """Parse table rows and construct a validated hydraulic uncertainty request."""
    parameters = tuple(_parse_parameter_row(row, index) for index, row in enumerate(rows, 1))
    baseline: HydraulicBaseline
    match engine:
        case HydraulicEngine.BACKWATER:
            baseline = BackwaterMonteCarloBaseline(
                reaches=_DEFAULT_REACHES,
                stage_area_points=_DEFAULT_STAGE_AREA,
                Q=50.0,
                H_downstream=5.0,
            )
        case HydraulicEngine.ROUTING:
            baseline = RoutingMonteCarloBaseline(
                inflow=_DEFAULT_INFLOW,
                K=6.0,
                x=0.2,
                dt=3.0,
            )
        case unreachable:
            assert_never(unreachable)
    return HydraulicUncertaintyRequest(
        baseline=baseline,
        parameters=parameters,
        n_runs=n_runs,
        seed=seed,
    )


def _parse_parameter_row(row: HydraulicParameterRow, index: int) -> ParameterSpec:
    """Parse one UI row into the service-layer parameter type."""
    name = row.name.strip()
    distribution = row.distribution.strip().lower()
    if not name or distribution != "uniform":
        raise HydraulicUncertaintyError(
            f"Строка {index}: ожидается uniform-параметр с именем"
        )
    try:
        low = float(row.low.replace(",", "."))
        high = float(row.high.replace(",", "."))
    except ValueError as error:
        raise HydraulicUncertaintyError(
            f"Строка {index}: границы распределения должны быть числами"
        ) from error
    if low >= high:
        raise HydraulicUncertaintyError(f"Строка {index}: low должен быть меньше high")
    return ParameterSpec(
        name=name,
        distribution=distribution,
        params={"low": low, "high": high},
    )


__all__ = [
    "HydraulicEngine",
    "HydraulicParameterRow",
    "build_hydraulic_request",
    "default_parameter_rows",
    "parse_engine",
]
