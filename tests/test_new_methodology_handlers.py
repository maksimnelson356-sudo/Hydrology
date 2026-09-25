"""Service-layer acceptance tests for the newly wired methodologies."""

from __future__ import annotations

import pandas as pd
import pytest

from core.domain import CalculationStatus, Dataset, DatasetType
from core.services.bootstrap import build_container


def _execute(methodology_id: str, dataset: Dataset, parameters: dict):
    container = build_container()
    descriptor = container.registry.get(methodology_id)
    return container.calculation.execute(
        descriptor.to_methodology(),
        dataset,
        parameters=parameters,
    )


def _short_series() -> Dataset:
    return Dataset(
        name="Короткий ряд",
        data={2000 + i: 10.0 + 2.0 * i for i in range(10)},
        dataset_type=DatasetType.OBSERVED,
    )


def _analog_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "year": list(range(2000, 2020)),
            "value": [10.0 + 2.0 * i for i in range(20)],
        }
    )


def _empty_dataset() -> Dataset:
    return Dataset(
        name="Пустой контекст",
        data={2000: 1.0},
        dataset_type=DatasetType.OBSERVED,
    )


def test_series_extension_completes_through_service() -> None:
    result = _execute(
        "series_extension",
        _short_series(),
        {"analog_df": _analog_frame(), "method": "regression"},
    )

    assert result.is_successful is True
    assert result.metadata.status == CalculationStatus.COMPLETED
    assert result.output_data["method"] == "regression"
    assert len(result.output_data["extended_series"]) == 20


def test_series_extension_proportional_completes_through_service() -> None:
    result = _execute(
        "series_extension",
        _short_series(),
        {"analog_df": _analog_frame(), "method": "proportional"},
    )

    assert result.is_successful is True
    assert result.output_data["method"] == "proportional"
    assert len(result.output_data["extended_series"]) == 20


def test_flood_hydrograph_completes_through_service() -> None:
    result = _execute(
        "flood_hydrograph",
        _empty_dataset(),
        {
            "Q_peak": 100.0,
            "T_peak": 5.0,
            "T_base": 20.0,
            "method": "triangle",
            "asymmetry": 0.3,
            "dt": 1.0,
        },
    )

    assert result.is_successful is True
    assert result.output_data["Q_peak"] == pytest.approx(100.0)
    assert len(result.output_data["t_hours"]) == 21


def test_backwater_completes_through_service() -> None:
    result = _execute(
        "backwater",
        _empty_dataset(),
        {
            "Q": 50.0,
            "B": 10.0,
            "m": 1.0,
            "n": 0.03,
            "I": 0.001,
            "H_reservoir": 2.0,
            "L_max": 1000.0,
            "dx": 100.0,
        },
    )

    assert result.is_successful is True
    assert result.output_data["normal_depth"] > 0.0
    assert result.output_data["L_backwater_m"] > 0.0


def test_new_methodologies_declare_required_parameters() -> None:
    registry = build_container().registry

    assert registry.get("series_extension").required_parameters == ("analog_df",)
    assert registry.get("flood_hydrograph").required_parameters == (
        "Q_peak",
        "T_peak",
        "T_base",
    )
    assert registry.get("backwater").required_parameters[:5] == (
        "Q",
        "B",
        "m",
        "n",
        "I",
    )


def test_missing_series_extension_input_is_rejected() -> None:
    with pytest.raises(Exception, match="analog_df"):
        _execute("series_extension", _short_series(), {})
