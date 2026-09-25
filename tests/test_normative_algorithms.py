"""Regression tests for the СП 33-101-2003 algorithms used by HydroSphere."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy import optimize, stats

from core.services.methodology_registry import build_default_registry
from core.stats.composite_curves import compute_composite_curve
from core.stats.parameters import validate_series_length
from core.stats.series_extension import estimate_extension_error, regression_extension


def test_composite_curve_combines_probabilities_instead_of_discharges() -> None:
    values = np.array(
        [
            80.0,
            85.0,
            90.0,
            95.0,
            100.0,
            105.0,
            110.0,
            115.0,
            120.0,
            125.0,
            20.0,
            25.0,
            30.0,
            35.0,
            40.0,
            45.0,
            50.0,
            55.0,
            60.0,
            65.0,
        ]
    )
    years = np.arange(1990, 2010)

    result = compute_composite_curve(values, years, break_year=2000, P_values=[0.1])
    curve = result["curve_df"]
    actual = float(curve.loc[curve["P_%"] == 10.0, "Q_составная"].iloc[0])

    high = values[:10]
    low = values[10:]
    high_std = float(np.std(high, ddof=1))
    low_std = float(np.std(low, ddof=1))

    def combined_exceedance(discharge: float) -> float:
        return float(
            0.5 * stats.norm.sf((discharge - np.mean(high)) / high_std)
            + 0.5 * stats.norm.sf((discharge - np.mean(low)) / low_std)
        )

    expected = optimize.brentq(
        lambda discharge: combined_exceedance(discharge) - 0.1,
        -100.0,
        300.0,
    )

    assert actual == pytest.approx(expected, rel=2e-3)


def test_series_extension_rejects_five_common_years() -> None:
    index = pd.Index(range(2000, 2005), name="year")
    observed = pd.Series([10.0, 11.0, 12.0, 13.0, 14.0], index=index)
    analog = pd.Series([20.0, 22.0, 24.0, 26.0, 28.0], index=index)

    with pytest.raises(ValueError, match="6"):
        regression_extension(observed, analog)


def test_series_extension_rejects_correlation_below_sp33_threshold() -> None:
    index = pd.Index(range(2000, 2006), name="year")
    observed = pd.Series([1.0, 2.0, 1.0, 2.0, 1.0, 2.0], index=index)
    analog = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], index=index)

    with pytest.raises(ValueError, match="R"):
        regression_extension(observed, analog)


def test_series_extension_error_depends_on_regression_residuals() -> None:
    index = pd.Index(range(2000, 2020), name="year")
    analog = pd.Series(np.arange(20, dtype=float) + 1.0, index=index)
    exact = pd.Series(2.0 * analog + 5.0, index=index)
    alternating_residuals = np.array([3.0 if i % 2 == 0 else -3.0 for i in range(20)])
    noisy = exact + pd.Series(alternating_residuals, index=index)

    exact_result = regression_extension(exact, analog)
    noisy_result = regression_extension(noisy, analog)
    exact_error = estimate_extension_error(exact, analog, exact_result)
    noisy_error = estimate_extension_error(noisy, analog, noisy_result)

    assert exact_error["residual_std_error"] == pytest.approx(0.0, abs=1e-12)
    assert noisy_error["residual_std_error"] > 0.0
    assert exact_error["epsilon_extended"] < noisy_error["epsilon_extended"]


def test_series_length_warning_uses_sp33_error_threshold() -> None:
    assert validate_series_length(
        5,
        relative_rms_error=0.05,
        error_limit=0.10,
    ) == []

    warnings = validate_series_length(
        20,
        relative_rms_error=0.15,
        error_limit=0.10,
    )

    assert len(warnings) == 1
    assert "10" in warnings[0]
    assert "15" in warnings[0]


EXPECTED_NORMATIVE_METADATA = {
    "backwater": ("СП 33-101-2003", "п. 5.45, п. 7.69", True),
    "reservoir_regulation": ("Метод Риппла (инженерный метод)", None, False),
    "spillway": ("СП 290.1325800.2016", None, False),
    "storage_yield": ("Метод Риппла (инженерный метод)", None, False),
    "ecological_flow": ("Метод Тессмана (инженерный метод)", None, False),
    "flood_hydrograph": ("СП 33-101-2003", "п. 5.32", True),
    "ice_phenomena": ("СП 33-101-2003", "п. 5.44, п. 7.70–7.71, прил. А.14", False),
    "intra_annual": ("HydroRash", None, False),
    "max_runoff": ("СП 33-101-2003", "п. 5.26–5.31", True),
    "min_runoff": ("СП 33-101-2003", "п. 5.41–5.43", True),
    "snowmelt": ("РД 52-26-2008", None, False),
    "baseflow": ("Boughton (1968), Eckhardt (2005), Lyne & Hollick (1979)", None, False),
    "composite_curves": ("СП 33-101-2003", "п. 5.12, формулы 5.21–5.25", True),
    "confidence_bands": ("Bootstrap-метод (инженерная оценка)", None, False),
    "drought_spi": ("McKee et al. (1993) / WMO SPI", None, False),
    "flow_duration": ("Инженерный метод FDC", None, False),
    "frequency_kritsky_menkel": ("СП 33-101-2003", "п. 5.1–5.6", True),
    "frequency_pearson3": ("СП 33-101-2003", "п. 5.1–5.3", True),
    "homogeneity_full": ("СП 33-101-2003", "п. 4.7, прил. А.1–А.3", True),
    "series_extension": ("СП 33-101-2003", "п. 6.2–6.7, п. 6.17", False),
    "spectral_hurst": ("Метод R/S (экспонента Хёрста)", None, False),
    "stats_parameters": ("СП 33-101-2003", "п. 5.1, п. 5.4–5.15", True),
    "trends_full": ("Манн—Кендалл / Сен / Pettitt", None, False),
}


def test_methodology_metadata_matches_verified_sources() -> None:
    registry = build_default_registry()

    assert set(registry.ids()) == set(EXPECTED_NORMATIVE_METADATA)
    for methodology_id, expected in EXPECTED_NORMATIVE_METADATA.items():
        descriptor = registry.get(methodology_id)
        assert (
            descriptor.standard,
            descriptor.clause,
            descriptor.is_normative,
        ) == expected, methodology_id


def test_registry_does_not_apply_false_fixed_year_minimum() -> None:
    registry = build_default_registry()

    assert registry.get("stats_parameters").min_points == 0
    assert registry.get("max_runoff").required_parameters == ("daily_df",)
    assert registry.get("min_runoff").required_parameters == ("daily_df",)
