"""
tests/test_sensitivity_service.py
Stage P2.2 acceptance tests (DOCS/ROADMAP.md §6.2): OAT tornado ranking on a
linear model, symmetric-delta swing, validation errors, provenance shape and
an AST no-banned-dependencies guard.

No GUI: only core.domain, core.services, stdlib.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.services.sensitivity_service import (
    DEFAULT_RELATIVE_DELTA,
    ParameterInfluence,
    SensitivityError,
    SensitivityRequest,
    SensitivityResult,
    SensitivityService,
)

# ----------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------


def linear_y(params):
    """y = 3·x1 + 1·x2 — coefficient on x1 is larger (acceptance ranking)."""
    return 3.0 * float(params["x1"]) + 1.0 * float(params["x2"])


def monotonic_cube(params):
    """y = x³ — strictly increasing in x (sign of swing must be positive)."""
    return float(params["x"]) ** 3


BASE = {"x1": 1.0, "x2": 1.0}
ABS_DELTA = 0.1


def make_request(baseline=None, deltas=None, relative_delta=DEFAULT_RELATIVE_DELTA):
    return SensitivityRequest(
        baseline=baseline if baseline is not None else dict(BASE),
        deltas=deltas if deltas is not None else {},
        relative_delta=relative_delta,
    )


# ----------------------------------------------------------------------
# Acceptance: linear ranking [x1, x2] when a > b
# ----------------------------------------------------------------------


def test_linear_model_ranks_larger_coefficient_first():
    request = make_request(deltas={"x1": ABS_DELTA, "x2": ABS_DELTA})
    result = SensitivityService.analyze(linear_y, request)

    assert result.order == ["x1", "x2"]
    # swing = 2 · coefficient · delta  →  0.6 and 0.2
    by_name = {item.name: item for item in result.influences}
    assert by_name["x1"].swing == pytest.approx(2 * 3.0 * ABS_DELTA)
    assert by_name["x2"].swing == pytest.approx(2 * 1.0 * ABS_DELTA)
    assert by_name["x1"].rank == 1
    assert by_name["x2"].rank == 2


def test_baseline_output_recorded():
    request = make_request(deltas={"x1": ABS_DELTA, "x2": ABS_DELTA})
    result = SensitivityService.analyze(linear_y, request)
    assert result.baseline_output == pytest.approx(3.0 * 1.0 + 1.0 * 1.0)


# ----------------------------------------------------------------------
# Symmetric delta → expected swing (monotonic model)
# ----------------------------------------------------------------------


def test_symmetric_delta_linear_swing():
    delta = 0.25
    request = make_request(baseline={"x": 2.0}, deltas={"x": delta})
    result = SensitivityService.analyze(monotonic_cube, request)
    item = result.influences[0]
    # f(2+d) − f(2−d) for x³
    expected = (2.0 + delta) ** 3 - (2.0 - delta) ** 3
    assert item.swing == pytest.approx(abs(expected))
    assert item.output_high > item.output_low  # monotonic increasing


def test_equal_influence_tie_breaks_by_name():
    def symmetric(params):
        return float(params["a"]) + float(params["b"])

    request = make_request(
        baseline={"a": 1.0, "b": 1.0}, deltas={"a": 0.1, "b": 0.1}
    )
    result = SensitivityService.analyze(symmetric, request)
    # equal swings → alphabetical tie-break for reproducibility
    assert result.order == ["a", "b"]
    assert result.influences[0].swing == pytest.approx(result.influences[1].swing)


# ----------------------------------------------------------------------
# Relative delta fallback (zero baseline uses unit scale)
# ----------------------------------------------------------------------


def test_relative_delta_on_zero_baseline_uses_unit_scale():
    request = make_request(baseline={"z": 0.0}, deltas={}, relative_delta=0.1)
    assert request.absolute_delta("z") == pytest.approx(0.1 * 1.0)


def test_relative_delta_on_nonzero_baseline():
    request = make_request(baseline={"z": 10.0}, deltas={}, relative_delta=0.05)
    assert request.absolute_delta("z") == pytest.approx(0.5)


# ----------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------


def test_reject_empty_baseline():
    with pytest.raises(SensitivityError, match="Базовая точка пуста"):
        SensitivityRequest(baseline={}).validate()


def test_reject_non_numeric_baseline_value():
    with pytest.raises(SensitivityError, match="должно быть числом"):
        SensitivityRequest(baseline={"x": "oops"}).validate()  # type: ignore[dict-item]


def test_reject_unknown_delta_name():
    with pytest.raises(SensitivityError, match="нет в baseline"):
        make_request(deltas={"ghost": 0.1}).validate()


def test_reject_non_positive_delta():
    with pytest.raises(SensitivityError, match="delta"):
        make_request(deltas={"x1": 0.0}).validate()


def test_reject_non_positive_relative_delta():
    with pytest.raises(SensitivityError, match="relative_delta"):
        make_request(relative_delta=0.0).validate()


def test_reject_non_finite_model_output():
    def nan_model(_params):
        return float("nan")

    with pytest.raises(SensitivityError, match="не-конечное"):
        SensitivityService.analyze(
            nan_model, make_request(baseline={"x": 1.0}, deltas={"x": 0.1})
        )


def test_remodel_exception_wrapped():
    def boom(_params):
        raise RuntimeError("kaboom")

    with pytest.raises(SensitivityError, match="kaboom"):
        SensitivityService.analyze(
            boom, make_request(baseline={"x": 1.0}, deltas={"x": 0.1})
        )


# ----------------------------------------------------------------------
# CalculationResult / provenance
# ----------------------------------------------------------------------


def test_run_returns_successful_calculation_result():
    request = make_request(deltas={"x1": ABS_DELTA, "x2": ABS_DELTA})
    result = SensitivityService.run(linear_y, request)

    assert result.is_successful
    assert result.metadata.methodology.qualified_name == "sensitivity_oat@1.0"
    assert result.metadata.input_parameters["order"] == ["x1", "x2"]
    assert result.metadata.input_parameters["relative_delta"] == DEFAULT_RELATIVE_DELTA
    assert result.output_data["order"] == ["x1", "x2"]
    assert len(result.output_data["influences"]) == 2
    first = result.output_data["influences"][0]
    for key in ("name", "swing", "rank", "baseline", "low", "high"):
        assert key in first


def test_influence_to_dict_keys():
    item = ParameterInfluence(
        name="p",
        baseline=1.0,
        low=0.9,
        high=1.1,
        output_low=1.0,
        output_high=1.2,
        swing=0.2,
        rank=1,
    )
    data = item.to_dict()
    assert data["name"] == "p"
    assert data["rank"] == 1
    assert data["swing"] == pytest.approx(0.2)


def test_result_order_property():
    request = make_request(deltas={"x1": ABS_DELTA, "x2": ABS_DELTA})
    result = SensitivityService.analyze(linear_y, request)
    assert isinstance(result, SensitivityResult)
    assert result.order == ["x1", "x2"]


# ----------------------------------------------------------------------
# AST guard: no banned dependencies
# ----------------------------------------------------------------------

BANNED = {"rasterio", "shapely", "geopandas", "fiona", "osgeo", "pyproj", "sklearn", "emcee"}


def test_no_banned_dependencies_in_sensitivity_service():
    path = Path(__file__).resolve().parents[1] / "core" / "services" / "sensitivity_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    assert not (imported & BANNED), f"banned imports: {imported & BANNED}"


def test_only_allowed_top_level_imports():
    path = Path(__file__).resolve().parents[1] / "core" / "services" / "sensitivity_service.py"
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
