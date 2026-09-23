"""
tests/test_monte_carlo.py
Stage P2.1 acceptance tests (DOCS/ROADMAP.md §6.2): determinism with a fixed
seed, analytical quantiles on a normal sample, request validation errors,
provenance / CalculationResult shape, and a no-banned-dependencies AST guard.

No GUI: only core.domain, core.services, numpy, stdlib.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.services.monte_carlo_service import (
    DEFAULT_N_RUNS,
    DISTRIBUTIONS,
    MonteCarloError,
    MonteCarloRequest,
    MonteCarloService,
    ParameterSpec,
)

# ----------------------------------------------------------------------
# Fixtures / helpers
# ----------------------------------------------------------------------


def normal_spec(mean: float = 10.0, std: float = 2.0, name: str = "x") -> ParameterSpec:
    return ParameterSpec(name=name, distribution="normal", params={"mean": mean, "std": std})


def uniform_spec(low: float = 0.0, high: float = 1.0, name: str = "u") -> ParameterSpec:
    return ParameterSpec(name=name, distribution="uniform", params={"low": low, "high": high})


def triangular_spec(
    left: float = 0.0, mode: float = 0.5, right: float = 1.0, name: str = "t"
) -> ParameterSpec:
    return ParameterSpec(
        name=name, distribution="triangular", params={"left": left, "mode": mode, "right": right}
    )


def identity_model(params):
    """Return the single named parameter unchanged."""
    return float(next(iter(params.values())))


# ----------------------------------------------------------------------
# Decisions 10.1 / 10.2
# ----------------------------------------------------------------------


def test_decision_10_1_distributions_set():
    assert DISTRIBUTIONS == ("uniform", "normal", "triangular")


def test_decision_10_2_default_n_runs():
    request = MonteCarloRequest(parameters=(normal_spec(),))
    assert request.n_runs == DEFAULT_N_RUNS == 1000


# ----------------------------------------------------------------------
# Determinism (acceptance: bit-for-bit with fixed seed)
# ----------------------------------------------------------------------


def test_same_seed_gives_identical_samples():
    request = MonteCarloRequest(parameters=(normal_spec(),), n_runs=500, seed=42)
    first = MonteCarloService.sample_parameters(request)
    second = MonteCarloService.sample_parameters(request)
    assert first == second

    result_a = MonteCarloService.run(identity_model, request)
    result_b = MonteCarloService.run(identity_model, request)
    assert result_a.output_data["samples"] == result_b.output_data["samples"]
    assert result_a.output_data["summary"] == result_b.output_data["summary"]


def test_different_seeds_differ():
    a = MonteCarloService.sample_parameters(
        MonteCarloRequest(parameters=(normal_spec(),), n_runs=200, seed=1)
    )
    b = MonteCarloService.sample_parameters(
        MonteCarloRequest(parameters=(normal_spec(),), n_runs=200, seed=2)
    )
    assert a != b


# ----------------------------------------------------------------------
# Analytical quantiles (acceptance: p50 close to mu for N >= 10_000)
# ----------------------------------------------------------------------


def test_normal_p50_close_to_mu():
    mu, std = 10.0, 2.0
    request = MonteCarloRequest(
        parameters=(normal_spec(mean=mu, std=std),), n_runs=20_000, seed=7
    )
    result = MonteCarloService.run(identity_model, request)
    summary = result.output_data["summary"]
    assert summary["p50"] == pytest.approx(mu, abs=0.1)
    assert summary["mean"] == pytest.approx(mu, abs=0.1)
    # one-sided 5%/95% for normal: ±1.64485 sigma
    assert summary["p5"] == pytest.approx(mu - 1.64485 * std, abs=0.3)
    assert summary["p95"] == pytest.approx(mu + 1.64485 * std, abs=0.3)


def test_uniform_samples_stay_in_bounds():
    request = MonteCarloRequest(
        parameters=(uniform_spec(low=-1.0, high=3.0),), n_runs=1000, seed=3
    )
    draws = MonteCarloService.sample_parameters(request)
    values = [d["u"] for d in draws]
    assert min(values) >= -1.0
    assert max(values) <= 3.0


def test_triangular_samples_stay_in_bounds():
    request = MonteCarloRequest(
        parameters=(triangular_spec(left=0.0, mode=1.0, right=5.0),),
        n_runs=1000,
        seed=5,
    )
    draws = MonteCarloService.sample_parameters(request)
    values = [d["t"] for d in draws]
    assert min(values) >= 0.0
    assert max(values) <= 5.0


# ----------------------------------------------------------------------
# Errors (acceptance: N<1, unknown distribution, empty parameters)
# ----------------------------------------------------------------------


def test_reject_n_less_than_one():
    with pytest.raises(MonteCarloError, match="N должно быть"):
        MonteCarloService.run(
            identity_model,
            MonteCarloRequest(parameters=(normal_spec(),), n_runs=0),
        )


def test_reject_unknown_distribution():
    bad = ParameterSpec(name="x", distribution="beta", params={"a": 1.0, "b": 2.0})
    with pytest.raises(MonteCarloError, match="Неизвестное распределение"):
        bad.validate()


def test_reject_empty_parameters():
    with pytest.raises(MonteCarloError, match="Список параметров пуст"):
        MonteCarloService.run(identity_model, MonteCarloRequest(parameters=()))


def test_reject_duplicate_parameter_names():
    request = MonteCarloRequest(parameters=(normal_spec(name="x"), normal_spec(name="x")))
    with pytest.raises(MonteCarloError, match="уникальными"):
        request.validate()


def test_reject_inverted_uniform_bounds():
    bad = uniform_spec(low=5.0, high=1.0)
    with pytest.raises(MonteCarloError, match="low < high"):
        bad.validate()


def test_reject_negative_normal_std():
    bad = normal_spec(std=-1.0)
    with pytest.raises(MonteCarloError, match="std >= 0"):
        bad.validate()


def test_reject_bad_triangular_order():
    bad = triangular_spec(left=1.0, mode=0.0, right=2.0)
    with pytest.raises(MonteCarloError, match="triangular"):
        bad.validate()


def test_reject_model_returning_non_finite():
    def bad_model(_params):
        return float("nan")

    with pytest.raises(MonteCarloError, match="не-конечное"):
        MonteCarloService.run(
            bad_model,
            MonteCarloRequest(parameters=(normal_spec(),), n_runs=3, seed=1),
        )


# ----------------------------------------------------------------------
# CalculationResult shape / provenance
# ----------------------------------------------------------------------


def test_result_is_successful_with_provenance():
    request = MonteCarloRequest(parameters=(normal_spec(),), n_runs=50, seed=11)
    result = MonteCarloService.run(identity_model, request)

    assert result.is_successful
    assert result.metadata.methodology.qualified_name == "monte_carlo@1.0"
    assert result.metadata.input_parameters["n_runs"] == 50
    assert result.metadata.input_parameters["seed"] == 11
    assert len(result.metadata.input_parameters["parameters"]) == 1
    assert result.output_data["n_runs"] == 50
    assert len(result.output_data["samples"]) == 50
    summary = result.output_data["summary"]
    for key in ("mean", "std", "p5", "p50", "p95", "min", "max", "count"):
        assert key in summary
    assert summary["count"] == 50


def test_summarize_rejects_empty_and_nan():
    with pytest.raises(MonteCarloError, match="Пустая выборка"):
        MonteCarloService.summarize([])
    with pytest.raises(MonteCarloError, match="NaN/Inf"):
        MonteCarloService.summarize([1.0, float("nan")])


def test_multi_parameter_model_sum_of_params():
    request = MonteCarloRequest(
        parameters=(normal_spec(name="a"), uniform_spec(name="b")),
        n_runs=300,
        seed=9,
    )
    result = MonteCarloService.run(lambda p: p["a"] + p["b"], request)
    summary = result.output_data["summary"]
    # E[a]+E[b] = 10 + 0.5
    assert summary["mean"] == pytest.approx(10.5, abs=0.5)


# ----------------------------------------------------------------------
# AST guard: no banned dependencies (mirrors test_geo_service)
# ----------------------------------------------------------------------

BANNED = {"rasterio", "shapely", "geopandas", "fiona", "osgeo", "pyproj", "sklearn", "emcee"}


def test_no_banned_dependencies_in_monte_carlo_service():
    path = Path(__file__).resolve().parents[1] / "core" / "services" / "monte_carlo_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not (imported & BANNED), f"banned imports: {imported & BANNED}"


def test_only_numpy_and_stdlib_top_level():
    path = Path(__file__).resolve().parents[1] / "core" / "services" / "monte_carlo_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    allowed = {
        "__future__",
        "collections",
        "dataclasses",
        "typing",
        "numpy",
        "core",
        "math",
        "json",
        "pathlib",
        "enum",
        "uuid",
        "datetime",
    }
    top: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            top.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            top.add(node.module.split(".")[0])
    assert top <= allowed, f"unexpected top-level imports: {top - allowed}"
