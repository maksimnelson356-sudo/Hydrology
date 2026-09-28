"""Tests for the sequential multi-analog extension workflow."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.stats.staged_series_extension import (
    AnalogExtensionStage,
    staged_multi_analog_extension,
)


def _case() -> tuple[pd.Series, dict[str, pd.Series], dict[str, pd.Series]]:
    years = pd.Index(range(2000, 2015), name="year")
    analog_1 = pd.Series(np.arange(1.0, 16.0), index=years)
    analog_2 = pd.Series(
        [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0, 5.0, 3.0, 5.0, 8.0, 9.0, 4.0, 7.0],
        index=years,
    )
    analog_3 = 2.0 * analog_1 + 0.3 * analog_2
    analog_4 = 0.5 * analog_1 - 0.2 * analog_2 + 4.0
    target = 20.0 + 1.5 * analog_1 + 0.8 * analog_2
    observed = target.copy()
    observed.loc[2010:] = np.nan
    analogs_1 = {"a1": analog_1, "a2": analog_2}
    analogs_2 = {"a3": analog_3, "a4": analog_4}
    return observed, analogs_1, analogs_2


def test_staged_workflow_fills_only_declared_target_years() -> None:
    observed, analogs_1, analogs_2 = _case()
    stages = [
        AnalogExtensionStage(
            name="recent",
            analogs=analogs_1,
            target_years=(2010, 2011, 2012),
            fit_years=tuple(range(2000, 2010)),
        ),
        AnalogExtensionStage(
            name="historical",
            analogs=analogs_2,
            target_years=(2013, 2014),
            fit_years=tuple(range(2000, 2010)),
            ro_cr=0.6,
        ),
    ]

    result = staged_multi_analog_extension(observed, stages)

    assert result["success"] is True
    assert result["unresolved_years"] == []
    assert list(result["stages"][0]["applied_years"]) == [2010, 2011, 2012]
    assert list(result["stages"][1]["applied_years"]) == [2013, 2014]
    assert result["extended_series"].loc[2010:2014].notna().all()


def test_staged_workflow_does_not_overwrite_observed_years() -> None:
    observed, analogs_1, _ = _case()
    original = float(observed.loc[2005])
    stages = [
        AnalogExtensionStage(
            name="safe",
            analogs=analogs_1,
            target_years=(2005, 2010),
            fit_years=tuple(range(2000, 2010)),
        )
    ]

    result = staged_multi_analog_extension(observed, stages)

    assert result["extended_series"].loc[2005] == pytest.approx(original)
    assert list(result["stages"][0]["applied_years"]) == [2010]


def test_staged_workflow_ignores_analog_only_years() -> None:
    observed, analogs, _ = _case()
    analogs_with_extra_year = {
        name: pd.concat([series, pd.Series({2015: float(series.iloc[-1])})])
        for name, series in analogs.items()
    }
    stage = AnalogExtensionStage(
        name="bounded",
        analogs=analogs_with_extra_year,
        target_years=(2010,),
        fit_years=tuple(range(2000, 2010)),
    )

    result = staged_multi_analog_extension(observed, [stage])

    assert result["success"] is True
    assert 2015 not in result["extended_series"].index
    assert result["unresolved_years"] == []


def test_staged_workflow_reports_target_year_without_analog_data() -> None:
    observed, analogs_1, _ = _case()
    stage = AnalogExtensionStage(
        name="missing",
        analogs=analogs_1,
        target_years=(2015,),
        fit_years=tuple(range(2000, 2010)),
    )

    with pytest.raises(ValueError, match="2015"):
        staged_multi_analog_extension(observed, [stage])
