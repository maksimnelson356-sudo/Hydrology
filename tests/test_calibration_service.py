"""
tests/test_calibration_service.py
Stage P1.5 acceptance tests (DOCS/ROADMAP.md): calibration on synthetic data,
metric before/after, invalid limits rejection, scenario apply/provenance.

No GUI: only core.domain, core.services, core.stats.metrics.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.domain.models import Dataset, ScenarioStatus
from core.services.calibration_service import (
    AVAILABLE_METRICS,
    CalibrationError,
    CalibrationRequest,
    CalibrationService,
)
from core.services.scenario_service import ScenarioService
from core.stats.metrics import mse, nse

# Synthetic linear series: y = 2.5 * t + 10  (true slope=2.5, intercept=10)
TRUE_SLOPE = 2.5
TRUE_INTERCEPT = 10.0
T = np.arange(40, dtype=float)
Y = TRUE_SLOPE * T + TRUE_INTERCEPT


def linear_predict(params):
    """y = slope * t + intercept — closed over the design matrix T."""
    return params["slope"] * T + params["intercept"]


def make_request(
    initial=None,
    bounds=None,
    metric="nse",
    method="L-BFGS-B",
    max_iterations=200,
) -> CalibrationRequest:
    return CalibrationRequest(
        initial=initial if initial is not None else {"slope": 1.0, "intercept": 0.0},
        bounds=bounds
        if bounds is not None
        else {"slope": (-10.0, 10.0), "intercept": (-50.0, 50.0)},
        metric=metric,
        method=method,
        max_iterations=max_iterations,
    )


# ----------------------------------------------------------------------
# Metrics (core.stats.metrics)
# ----------------------------------------------------------------------
def test_mse_and_nse_on_perfect_fit():
    assert mse(Y, Y) == pytest.approx(0.0, abs=1e-15)
    assert nse(Y, Y) == pytest.approx(1.0, abs=1e-12)


def test_mse_known_value():
    assert mse([1.0, 2.0, 3.0], [1.0, 2.0, 4.0]) == pytest.approx(1.0 / 3.0)


def test_nse_worse_than_perfect_is_below_one():
    value = nse(Y, Y + 5.0)
    assert value < 1.0


def test_available_metrics_decision_9_5():
    assert AVAILABLE_METRICS == ("mse", "nse")


# ----------------------------------------------------------------------
# Convergence on synthetic data (acceptance: closer than default)
# ----------------------------------------------------------------------
@pytest.mark.parametrize("metric", ["mse", "nse"])
def test_calibrated_parameter_closer_than_default(metric):
    service = CalibrationService()
    request = make_request(metric=metric)
    result = service.calibrate(Y, linear_predict, request)

    assert result.is_successful
    fitted = result.output_data["parameters_after"]
    default = result.output_data["parameters_before"]

    default_slope_err = abs(default["slope"] - TRUE_SLOPE)
    fitted_slope_err = abs(fitted["slope"] - TRUE_SLOPE)
    assert fitted_slope_err < default_slope_err
    assert fitted["slope"] == pytest.approx(TRUE_SLOPE, abs=0.05)
    assert fitted["intercept"] == pytest.approx(TRUE_INTERCEPT, abs=0.5)

    before = result.output_data["metric_before"]
    after = result.output_data["metric_after"]
    if metric == "mse":
        assert after < before
    else:
        assert after > before
    assert result.output_data["iterations"] >= 0
    assert result.output_data["metric"] == metric


def test_metric_before_after_recorded_in_provenance():
    service = CalibrationService()
    result = service.calibrate(Y, linear_predict, make_request(metric="nse"))
    params = result.metadata.input_parameters

    assert params["metric"] == "nse"
    assert params["calibrated_parameters"] == ["slope", "intercept"]
    assert params["iterations"] == result.output_data["iterations"]
    assert params["metric_before"] == result.output_data["metric_before"]
    assert params["metric_after"] == result.output_data["metric_after"]
    assert result.metadata.methodology.standard == "scipy.optimize"


def test_metric_value_unknown_raises():
    with pytest.raises(CalibrationError, match="Неизвестная метрика"):
        CalibrationService.metric_value(Y, Y, metric="rmse")


# ----------------------------------------------------------------------
# Invalid limits / request rejection
# ----------------------------------------------------------------------
def test_reject_inverted_bounds():
    service = CalibrationService()
    request = make_request(bounds={"slope": (5.0, -5.0), "intercept": (-50.0, 50.0)})
    with pytest.raises(CalibrationError, match="limits"):
        service.calibrate(Y, linear_predict, request)


def test_reject_initial_outside_bounds():
    service = CalibrationService()
    request = make_request(initial={"slope": 100.0, "intercept": 0.0})
    with pytest.raises(CalibrationError, match="вне limits"):
        service.calibrate(Y, linear_predict, request)


def test_reject_missing_bounds_entry():
    service = CalibrationService()
    request = make_request(bounds={"slope": (-10.0, 10.0)})  # intercept bounds missing
    with pytest.raises(CalibrationError, match="limits"):
        service.calibrate(Y, linear_predict, request)


def test_reject_empty_initial():
    service = CalibrationService()
    request = CalibrationRequest(initial={}, bounds={}, metric="nse")
    with pytest.raises(CalibrationError, match="начальные параметры"):
        service.calibrate(Y, linear_predict, request)


def test_reject_empty_observed():
    service = CalibrationService()
    with pytest.raises(CalibrationError, match="пустой"):
        service.calibrate([], linear_predict, make_request())


def test_reject_unknown_metric():
    service = CalibrationService()
    with pytest.raises(CalibrationError, match="метрика"):
        service.calibrate(Y, linear_predict, make_request(metric="mae"))


def test_reject_shape_mismatch_model():
    service = CalibrationService()

    def short_predict(params):
        return np.asarray(T[:5]) * params["slope"]

    with pytest.raises(CalibrationError, match="вернула"):
        service.calibrate(Y, short_predict, make_request())


# ----------------------------------------------------------------------
# Scenario apply (rollback = update with previous parameters)
# ----------------------------------------------------------------------
def test_apply_to_scenario_and_rollback():
    service = CalibrationService()
    scenarios = ScenarioService()
    scenario = scenarios.create(name="Base", parameters={"slope": 1.0, "other": 7})
    previous = dict(scenario.parameters)

    cal = service.calibrate(Y, linear_predict, make_request(metric="nse"))
    fitted = cal.output_data["parameters_after"]

    updated = service.apply_to_scenario(scenarios, scenario.id, fitted)
    assert updated.parameters["slope"] == pytest.approx(fitted["slope"])
    assert updated.parameters["other"] == 7  # untouched keys survive

    # Rollback: write the previous mapping back (user action / editor).
    scenarios.update(scenario.id, parameters=previous)
    assert scenarios.get(scenario.id).parameters["slope"] == previous["slope"]


def test_apply_to_scenario_empty_parameters_rejected():
    scenarios = ScenarioService()
    scenario = scenarios.create(name="S", parameters={})
    with pytest.raises(CalibrationError, match="пустой"):
        CalibrationService.apply_to_scenario(scenarios, scenario.id, {})


# ----------------------------------------------------------------------
# Dataset plumbing sanity (series comes from Dataset in the GUI path)
# ----------------------------------------------------------------------
def test_calibrate_from_dataset_values_roundtrip():
    data = {1980 + i: float(v) for i, v in enumerate(Y)}
    dataset = Dataset(name="Synthetic", data=data)
    observed = dataset.values

    service = CalibrationService()
    result = service.calibrate(observed, linear_predict, make_request(metric="mse"))
    fitted = result.output_data["parameters_after"]
    assert fitted["slope"] == pytest.approx(TRUE_SLOPE, abs=0.05)
    assert dataset.length == len(Y)
    assert ScenarioStatus.DRAFT is not None  # domain enum still importable
