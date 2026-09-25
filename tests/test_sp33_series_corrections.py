"""Regression tests for СП 33 error and variance-correction formulas."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.stats.series_extension import multi_analog_extension
from core.stats.sp33_variance_correction import apply_formula_6_9, apply_formula_6_10


def _multi_analog_case() -> tuple[pd.Index, pd.Series, pd.Series, pd.Series]:
    years = pd.Index(range(2000, 2013), name="year")
    analog_1 = pd.Series(np.arange(1.0, 14.0), index=years)
    analog_2 = pd.Series(
        [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0, 5.0, 3.0, 5.0, 8.0, 9.0],
        index=years,
    )
    target = 20.0 + 1.5 * analog_1 + 0.8 * analog_2
    target.loc[2000:2007] += pd.Series(
        [0.2, -0.1, 0.05, -0.15, 0.1, -0.05, 0.15, -0.1],
        index=years[0:8],
    )
    observed = target.copy()
    observed.loc[2008:] = np.nan
    return years, analog_1, analog_2, observed


def _regression_parts(
    years: pd.Index,
    analog_1: pd.Series,
    analog_2: pd.Series,
    observed: pd.Series,
) -> tuple[np.ndarray, np.ndarray, float, float, pd.Index, pd.Index]:
    common = years[0:8]
    missing = years[8:]
    design = np.column_stack(
        [np.ones(len(common)), analog_1.loc[common], analog_2.loc[common]]
    )
    observed_values = observed.loc[common].to_numpy()
    beta = np.linalg.lstsq(design, observed_values, rcond=None)[0]
    residuals = observed_values - design @ beta
    r_squared = 1.0 - np.sum(residuals**2) / np.sum(
        (observed_values - observed_values.mean()) ** 2
    )
    return design, beta, float(np.sqrt(r_squared)), float(observed_values.mean()), common, missing


def test_sp33_clause_6_17_formula_6_9_is_exact() -> None:
    corrected = apply_formula_6_9(
        np.array([8.0, 9.0, 10.0, 11.0, 12.0]),
        mean_n=10.0,
        correlation=0.8,
    )

    assert corrected == pytest.approx([7.5, 8.75, 10.0, 11.25, 12.5])


def test_sp33_clause_6_17_formula_6_10_is_exact() -> None:
    corrected = apply_formula_6_10(
        np.array([8.0, 9.0, 10.0]),
        correlation=0.8,
        sigma=2.0,
        phi=np.array([-1.0, 0.0, 1.0]),
    )

    assert corrected == pytest.approx([6.8, 9.0, 11.2])


def test_sp33_variance_corrections_reject_invalid_inputs() -> None:
    values = np.array([8.0, 9.0])

    with pytest.raises(ValueError, match="R"):
        apply_formula_6_9(values, mean_n=8.5, correlation=0.0)
    with pytest.raises(ValueError, match="φ"):
        apply_formula_6_10(
            values,
            correlation=0.8,
            sigma=2.0,
            phi=np.array([0.0]),
        )
    with pytest.raises(ValueError, match="σ"):
        apply_formula_6_10(
            values,
            correlation=0.8,
            sigma=0.0,
            phi=np.zeros(2),
        )


def test_multi_analog_extension_applies_formula_6_9_by_default() -> None:
    years, analog_1, analog_2, observed = _multi_analog_case()
    result = multi_analog_extension(
        observed,
        {"analog-1": analog_1, "analog-2": analog_2},
        n_min=8,
    )

    _, beta, correlation, observed_mean, _, missing = _regression_parts(
        years, analog_1, analog_2, observed
    )
    raw_missing = np.column_stack([
        np.ones(len(missing)), analog_1.loc[missing], analog_2.loc[missing]
    ]) @ beta
    expected = (raw_missing - observed_mean) / correlation + observed_mean

    assert result["variance_correction"] == "6.9"
    assert result["extended_series"].loc[missing].to_numpy() == pytest.approx(expected)


def test_multi_analog_extension_applies_formula_6_10() -> None:
    years, analog_1, analog_2, observed = _multi_analog_case()
    phi = pd.Series([-1.0, 0.0, 1.0, -0.5, 0.5], index=years[8:])
    result = multi_analog_extension(
        observed,
        {"analog-1": analog_1, "analog-2": analog_2},
        n_min=8,
        variance_correction="6.10",
        phi=phi,
    )

    _, beta, correlation, _, _, missing = _regression_parts(
        years, analog_1, analog_2, observed
    )
    raw_missing = np.column_stack([
        np.ones(len(missing)), analog_1.loc[missing], analog_2.loc[missing]
    ]) @ beta
    sigma = float(observed.loc[years[0:8]].std(ddof=1))
    expected = raw_missing + phi.to_numpy() * sigma * np.sqrt(1.0 - correlation**2)

    assert result["variance_correction"] == "6.10"
    assert result["extended_series"].loc[missing].to_numpy() == pytest.approx(expected)
    assert any("30" in warning for warning in result["warnings"])


def test_multi_analog_stochastic_correction_is_reproducible() -> None:
    _, analog_1, analog_2, observed = _multi_analog_case()
    kwargs = {
        "analogs": {"analog-1": analog_1, "analog-2": analog_2},
        "n_min": 8,
        "variance_correction": "6.10",
        "random_state": 42,
    }

    first = multi_analog_extension(observed, **kwargs)
    second = multi_analog_extension(observed, **kwargs)

    pd.testing.assert_series_equal(first["extended_series"], second["extended_series"])


def test_multi_analog_extension_rejects_unknown_variance_correction() -> None:
    _, analog_1, analog_2, observed = _multi_analog_case()

    with pytest.raises(ValueError, match="variance_correction"):
        multi_analog_extension(
            observed,
            {"analog-1": analog_1, "analog-2": analog_2},
            variance_correction="none",
        )
