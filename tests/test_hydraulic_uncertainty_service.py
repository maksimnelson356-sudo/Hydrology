"""P3.4 acceptance tests for hydraulic uncertainty propagation."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from core.hydrorash.inundation import StageAreaPoint
from core.services.backwater_profile_service import ReachSpec
from core.services.hydraulic_uncertainty_service import (
    HYDRAULIC_UNCERTAINTY_PROVENANCE,
    BackwaterMonteCarloBaseline,
    HydraulicUncertaintyError,
    HydraulicUncertaintyRequest,
    HydraulicUncertaintyService,
    RoutingMonteCarloBaseline,
)
from core.services.monte_carlo_service import ParameterSpec

_REACHES = (
    ReachSpec(name="Нижний", B=20.0, m=2.0, n=0.035, slope=0.001, L=500.0),
    ReachSpec(name="Верхний", B=15.0, m=1.5, n=0.040, slope=0.002, L=500.0),
)
_STAGE_AREA = (
    StageAreaPoint(stage_m=0.0, area_m2=0.0),
    StageAreaPoint(stage_m=2.0, area_m2=20_000.0),
    StageAreaPoint(stage_m=4.0, area_m2=60_000.0),
    StageAreaPoint(stage_m=8.0, area_m2=160_000.0),
)
_INFLOW = (0.0, 20.0, 50.0, 100.0, 80.0, 50.0, 30.0, 15.0, 5.0)


def _uniform(name: str, low: float, high: float) -> ParameterSpec:
    return ParameterSpec(name=name, distribution="uniform", params={"low": low, "high": high})


def _backwater_request(seed: int = 42) -> HydraulicUncertaintyRequest:
    return HydraulicUncertaintyRequest(
        baseline=BackwaterMonteCarloBaseline(
            reaches=_REACHES,
            stage_area_points=_STAGE_AREA,
            Q=50.0,
            H_downstream=5.0,
        ),
        parameters=(
            _uniform("Q", 40.0, 60.0),
            _uniform("H_downstream", 4.5, 5.5),
            _uniform("n_scale", 0.9, 1.1),
            _uniform("slope_scale", 0.9, 1.1),
        ),
        n_runs=30,
        seed=seed,
    )


def _routing_request(seed: int = 42) -> HydraulicUncertaintyRequest:
    return HydraulicUncertaintyRequest(
        baseline=RoutingMonteCarloBaseline(
            inflow=_INFLOW,
            K=6.0,
            x=0.2,
            dt=3.0,
        ),
        parameters=(
            _uniform("Q_scale", 0.8, 1.2),
            _uniform("K", 5.5, 6.5),
            _uniform("x", 0.15, 0.20),
        ),
        n_runs=30,
        seed=seed,
    )


def test_backwater_runner_is_deterministic_for_same_seed():
    # Given: the same seedable P3.1 request.
    request = _backwater_request()
    # When: the hydraulic uncertainty is evaluated twice.
    first = HydraulicUncertaintyService.run(request)
    second = HydraulicUncertaintyService.run(request)
    # Then: every sampled metric is bit-for-bit reproducible.
    assert first.engine == "backwater"
    assert first.samples == second.samples
    assert {name: summary.to_dict() for name, summary in first.metrics.items()} == {
        name: summary.to_dict() for name, summary in second.metrics.items()
    }


def test_backwater_runner_reports_depth_area_volume_quantiles():
    # Given: an uncertain multi-reach backwater model.
    request = _backwater_request()
    # When: the P3.4 runner propagates uncertainty.
    result = HydraulicUncertaintyService.run(request)
    # Then: depth, area, and volume expose ordered p5/p50/p95 statistics.
    assert set(result.metrics) == {"max_depth_m", "flooded_area_m2", "flooded_volume_m3"}
    for summary in result.metrics.values():
        assert summary.p5 <= summary.p50 <= summary.p95
        assert summary.count == request.n_runs
        assert summary.p50 > 0.0


def test_backwater_different_seeds_produce_different_samples():
    # Given: identical models with different random seeds.
    first = HydraulicUncertaintyService.run(_backwater_request(seed=1))
    second = HydraulicUncertaintyService.run(_backwater_request(seed=2))
    # When/Then: at least one hydraulic metric changes.
    assert first.samples != second.samples


def test_routing_runner_reports_peak_quantiles():
    # Given: an uncertain Muskingum model.
    request = _routing_request()
    # When: the P3.4 runner propagates uncertainty.
    result = HydraulicUncertaintyService.run(request)
    # Then: inflow/outflow peaks, attenuation, and lag are summarized.
    assert result.engine == "routing"
    assert set(result.metrics) == {
        "peak_in_m3s",
        "peak_out_m3s",
        "peak_attenuation_m3s",
        "peak_lag_steps",
    }
    for summary in result.metrics.values():
        assert summary.p5 <= summary.p50 <= summary.p95
        assert summary.count == request.n_runs
    assert result.metrics["peak_out_m3s"].p50 <= result.metrics["peak_in_m3s"].p50


def test_routing_runner_is_deterministic():
    # Given: the same routing request.
    request = _routing_request()
    # When: it is evaluated twice.
    first = HydraulicUncertaintyService.run(request)
    second = HydraulicUncertaintyService.run(request)
    # Then: all routing samples match exactly.
    assert first.samples == second.samples


def test_result_json_round_trip_and_provenance():
    # Given: a completed hydraulic uncertainty result.
    result = HydraulicUncertaintyService.run(_routing_request())
    # When: the result is serialized.
    payload = result.to_dict()
    restored = json.loads(json.dumps(payload, ensure_ascii=False))
    # Then: JSON preserves provenance, engine, seed, and metric quantiles.
    assert restored["provenance"] == HYDRAULIC_UNCERTAINTY_PROVENANCE
    assert restored["engine"] == "routing"
    assert restored["seed"] == 42
    assert set(restored["metrics"]) == set(result.metrics)


def test_unknown_parameter_is_rejected():
    # Given: a parameter name unsupported by the selected hydraulic engine.
    request = HydraulicUncertaintyRequest(
        baseline=RoutingMonteCarloBaseline(inflow=_INFLOW, K=6.0, x=0.2, dt=3.0),
        parameters=(_uniform("unknown", 0.0, 1.0),),
        n_runs=3,
        seed=1,
    )
    # When/Then: the request is rejected before model evaluation.
    with pytest.raises(HydraulicUncertaintyError, match="unknown"):
        HydraulicUncertaintyService.run(request)


def test_invalid_routing_draw_is_wrapped():
    # Given: x values that violate the Muskingum service contract.
    request = HydraulicUncertaintyRequest(
        baseline=RoutingMonteCarloBaseline(inflow=_INFLOW, K=6.0, x=0.2, dt=3.0),
        parameters=(_uniform("x", 0.6, 0.7),),
        n_runs=2,
        seed=1,
    )
    # When: the runner evaluates an invalid draw.
    with pytest.raises(HydraulicUncertaintyError, match="Прогон 1"):
        # Then: the domain error identifies the failed simulation.
        HydraulicUncertaintyService.run(request)


def test_hydraulic_service_ast_has_no_gui_or_gis_dependencies():
    # Given: the hydraulic uncertainty service source.
    path = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "services"
        / "hydraulic_uncertainty_service.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    # When/Then: orchestration stays independent from GUI/GIS stacks.
    banned = {"PyQt6", "matplotlib", "rasterio", "shapely", "geopandas", "fiona"}
    assert not (imported & banned)
