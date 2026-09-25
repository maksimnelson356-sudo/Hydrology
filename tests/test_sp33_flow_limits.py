"""Regression tests for СП 33 flow-statistics error limits."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.hydrorash.max_runoff import compute_max_runoff_stats
from core.hydrorash.min_runoff_extended import compute_min_runoff_stats
from core.stats.parameters import calculate_statistical_parameters


def test_stats_parameters_use_sp33_formula_5_27_and_10_percent_limit() -> None:
    series = np.array([10.0, 11.0, 13.0, 12.0, 15.0, 14.0, 17.0, 16.0])

    with pytest.warns(UserWarning, match=r"15\.4%"):
        result = calculate_statistical_parameters(series)

    assert result["r1"] == pytest.approx(0.6722, abs=0.0001)
    assert len(result["length_warnings"]) == 1
    assert "10" in result["length_warnings"][0]
    assert "15.4%" in result["length_warnings"][0]


def test_max_runoff_uses_sp33_20_percent_error_limit() -> None:
    series = pd.Series(
        [100.0, 200.0, 200.0, 50.0, 200.0, 0.0, 100.0, 150.0,
         150.0, 0.0, 50.0, 150.0, 100.0, 0.0, 50.0]
    )

    result = compute_max_runoff_stats(series)

    assert 10.0 < result["epsilon"] < 20.0
    assert result["warnings"] == []
    assert result["reliability_class"] == "Надёжная"
    assert result["relative_rms_error_limit"] == pytest.approx(0.20)


def test_min_runoff_uses_sp33_20_percent_error_limit() -> None:
    series = pd.Series(
        [100.0, 200.0, 200.0, 50.0, 200.0, 20.0, 100.0, 150.0,
         150.0, 20.0, 50.0, 150.0, 100.0, 20.0, 50.0]
    )

    result = compute_min_runoff_stats(series)

    assert 10.0 < result["epsilon"] < 20.0
    assert result["warnings"] == []
    assert result["reliability_class"] == "Надёжная"
    assert result["relative_rms_error_limit"] == pytest.approx(0.20)


def test_max_and_min_runoff_warn_above_sp33_20_percent_limit() -> None:
    max_result = compute_max_runoff_stats(
        pd.Series([50.0, 200.0, 0.0, 150.0, 50.0, 0.0])
    )
    min_result = compute_min_runoff_stats(
        pd.Series([5.0, 20.0, 0.0, 15.0, 5.0, 0.0])
    )

    assert max_result["epsilon"] > 20.0
    assert min_result["epsilon"] > 20.0
    assert any("20" in warning for warning in max_result["warnings"])
    assert any("20" in warning for warning in min_result["warnings"])


def test_max_runoff_uses_sp33_formula_5_27_for_high_autocorrelation() -> None:
    series = pd.Series([10.0, 11.0, 13.0, 12.0, 15.0, 14.0, 17.0, 16.0])
    result = compute_max_runoff_stats(series)

    n = len(series)
    r1 = float(np.corrcoef(series[:-1], series[1:])[0, 1])
    geometric_sum = (1.0 - r1**n) / (1.0 - r1)
    numerator = 1.0 + 2.0 * r1 / (n * (1.0 - r1)) * (n - geometric_sum)
    denominator = 1.0 - 2.0 * r1 / (
        n * (n - 1) * (1.0 - r1)
    ) * (n - geometric_sum)
    expected = (
        float(series.std(ddof=1) / series.mean() / np.sqrt(n))
        * np.sqrt(numerator / denominator)
        * 100.0
    )

    assert r1 >= 0.5
    assert result["epsilon"] == pytest.approx(expected, abs=0.01)
