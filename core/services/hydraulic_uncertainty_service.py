"""Hydraulic uncertainty propagation across HydroSphere P3.1–P3.3."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, assert_never

from core.hydrorash.inundation import (
    InundationCalculationError,
    StageAreaPoint,
    inundation_from_stage_area,
)
from core.services.backwater_profile_service import (
    BackwaterProfileError,
    BackwaterProfileRequest,
    BackwaterProfileService,
    ReachSpec,
)
from core.services.inundation_service import InundationError
from core.services.monte_carlo_service import (
    MonteCarloError,
    MonteCarloRequest,
    MonteCarloService,
    ParameterSpec,
    SummaryStats,
)
from core.services.routing_service import RoutingError, RoutingRequest, RoutingService

__all__ = [
    "HYDRAULIC_UNCERTAINTY_PROVENANCE",
    "BackwaterMonteCarloBaseline",
    "HydraulicBaseline",
    "HydraulicUncertaintyError",
    "HydraulicUncertaintyRequest",
    "HydraulicUncertaintyResult",
    "HydraulicUncertaintyService",
    "RoutingMonteCarloBaseline",
]

HYDRAULIC_UNCERTAINTY_PROVENANCE: Final = "hydraulic_uncertainty@1.0"
_BACKWATER_PARAMETERS: Final = frozenset(
    {"Q", "H_downstream", "B_scale", "m_scale", "n_scale", "slope_scale"}
)
_ROUTING_PARAMETERS: Final = frozenset({"Q_scale", "K", "x", "dt"})

type JsonValue = str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]


class HydraulicUncertaintyError(Exception):
    """Invalid hydraulic uncertainty request or failed simulation."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True, slots=True)
class BackwaterMonteCarloBaseline:
    """Fixed P3.1 geometry and P3.3 S(H) curve with optional sampled overrides."""

    reaches: tuple[ReachSpec, ...]
    stage_area_points: tuple[StageAreaPoint, ...]
    Q: float
    H_downstream: float
    dx: float = 100.0


@dataclass(frozen=True, slots=True)
class RoutingMonteCarloBaseline:
    """Fixed P3.2 inflow and routing parameters with optional sampled overrides."""

    inflow: tuple[float, ...]
    K: float
    x: float
    dt: float
    outflow0: float | None = None


type HydraulicBaseline = BackwaterMonteCarloBaseline | RoutingMonteCarloBaseline


@dataclass(frozen=True, slots=True)
class HydraulicUncertaintyRequest:
    """Hydraulic baseline plus seedable uncertain parameters."""

    baseline: HydraulicBaseline
    parameters: tuple[ParameterSpec, ...]
    n_runs: int = 200
    seed: int | None = 42

    def monte_carlo_request(self) -> MonteCarloRequest:
        """Build the generic P2.1 request after hydraulic-name validation."""
        allowed = _allowed_parameters(self.baseline)
        unknown = sorted({spec.name for spec in self.parameters} - allowed)
        if unknown:
            raise HydraulicUncertaintyError(
                f"Неизвестные параметры для {self.engine}: {unknown}"
            )
        return MonteCarloRequest(
            parameters=self.parameters,
            n_runs=self.n_runs,
            seed=self.seed,
        )

    @property
    def engine(self) -> str:
        """Hydraulic engine selected by the baseline type."""
        match self.baseline:
            case BackwaterMonteCarloBaseline():
                return "backwater"
            case RoutingMonteCarloBaseline():
                return "routing"
            case unreachable:
                assert_never(unreachable)


@dataclass(frozen=True, slots=True)
class HydraulicUncertaintyResult:
    """Hydraulic metric samples and p5/p50/p95 summaries."""

    engine: str
    n_runs: int
    seed: int | None
    metrics: dict[str, SummaryStats]
    samples: dict[str, tuple[float, ...]]
    provenance: str

    def to_dict(self) -> dict[str, JsonValue]:
        """Serialize hydraulic uncertainty outputs."""
        return {
            "engine": self.engine,
            "n_runs": self.n_runs,
            "seed": self.seed,
            "metrics": {
                name: summary.to_dict() for name, summary in self.metrics.items()
            },
            "samples": {
                name: list(values) for name, values in self.samples.items()
            },
            "provenance": self.provenance,
        }


class HydraulicUncertaintyService:
    """Propagate Monte Carlo parameters through P3.1/P3.2/P3.3 services."""

    @staticmethod
    def run(request: HydraulicUncertaintyRequest) -> HydraulicUncertaintyResult:
        """Run a seedable hydraulic uncertainty analysis."""
        try:
            mc_request = request.monte_carlo_request()
            draws = MonteCarloService.sample_parameters(mc_request)
            match request.baseline:
                case BackwaterMonteCarloBaseline() as baseline:
                    samples = _run_backwater(baseline, draws)
                case RoutingMonteCarloBaseline() as baseline:
                    samples = _run_routing(baseline, draws)
                case unreachable:
                    assert_never(unreachable)
        except HydraulicUncertaintyError:
            raise
        except MonteCarloError as error:
            raise HydraulicUncertaintyError(str(error)) from error

        frozen_samples = {name: tuple(values) for name, values in samples.items()}
        metrics = {
            name: MonteCarloService.summarize(values)
            for name, values in frozen_samples.items()
        }
        return HydraulicUncertaintyResult(
            engine=request.engine,
            n_runs=request.n_runs,
            seed=request.seed,
            metrics=metrics,
            samples=frozen_samples,
            provenance=HYDRAULIC_UNCERTAINTY_PROVENANCE,
        )


def _allowed_parameters(baseline: HydraulicBaseline) -> frozenset[str]:
    match baseline:
        case BackwaterMonteCarloBaseline():
            return _BACKWATER_PARAMETERS
        case RoutingMonteCarloBaseline():
            return _ROUTING_PARAMETERS
        case unreachable:
            assert_never(unreachable)


def _run_backwater(
    baseline: BackwaterMonteCarloBaseline,
    draws: list[dict[str, float]],
) -> dict[str, list[float]]:
    samples = _empty_samples("max_depth_m", "flooded_area_m2", "flooded_volume_m3")
    for index, draw in enumerate(draws, start=1):
        try:
            reaches = tuple(
                ReachSpec(
                    name=reach.name,
                    B=reach.B * draw.get("B_scale", 1.0),
                    m=reach.m * draw.get("m_scale", 1.0),
                    n=reach.n * draw.get("n_scale", 1.0),
                    slope=reach.slope * draw.get("slope_scale", 1.0),
                    L=reach.L,
                )
                for reach in baseline.reaches
            )
            result = BackwaterProfileService.run(
                BackwaterProfileRequest(
                    reaches=list(reaches),
                    Q=draw.get("Q", baseline.Q),
                    H_downstream=draw.get("H_downstream", baseline.H_downstream),
                    dx=baseline.dx,
                )
            )
            max_depth = max(result.depths_m)
            inundation = inundation_from_stage_area(
                max(max_depth, result.H_downstream),
                baseline.stage_area_points,
            )
        except (BackwaterProfileError, InundationError, InundationCalculationError) as error:
            raise HydraulicUncertaintyError(f"Прогон {index}: {error}") from error
        samples["max_depth_m"].append(max_depth)
        samples["flooded_area_m2"].append(inundation.area_m2)
        samples["flooded_volume_m3"].append(inundation.volume_m3)
    return samples


def _run_routing(
    baseline: RoutingMonteCarloBaseline,
    draws: list[dict[str, float]],
) -> dict[str, list[float]]:
    samples = _empty_samples(
        "peak_in_m3s", "peak_out_m3s", "peak_attenuation_m3s", "peak_lag_steps"
    )
    for index, draw in enumerate(draws, start=1):
        try:
            q_scale = draw.get("Q_scale", 1.0)
            result = RoutingService.run(
                RoutingRequest(
                    inflow=[value * q_scale for value in baseline.inflow],
                    k=draw.get("K", baseline.K),
                    x=draw.get("x", baseline.x),
                    dt=draw.get("dt", baseline.dt),
                    outflow0=baseline.outflow0,
                )
            )
        except RoutingError as error:
            raise HydraulicUncertaintyError(f"Прогон {index}: {error}") from error
        samples["peak_in_m3s"].append(result.peak_in_m3s)
        samples["peak_out_m3s"].append(result.peak_out_m3s)
        samples["peak_attenuation_m3s"].append(result.peak_attenuation_m3s)
        samples["peak_lag_steps"].append(float(result.peak_lag_steps))
    return samples


def _empty_samples(*names: str) -> dict[str, list[float]]:
    return {name: [] for name in names}
