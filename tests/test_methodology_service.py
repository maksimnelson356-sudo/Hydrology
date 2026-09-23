"""
tests/test_methodology_service.py
Stage 3 acceptance tests (DOCS/ROADMAP.md, stage 3): methodology registry +
calculation through the service layer.

Key criteria covered:
- every P0 methodology runs through CalculationService.execute() and returns
  a CalculationResult with status COMPLETED;
- results through the service are EQUAL to direct core calls (zero divergence);
- an inapplicable methodology (too short series) does not run and produces a
  clear error containing the normative reference.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.domain import CalculationStatus, Dataset, DatasetType
from core.services.bootstrap import build_container

# Deterministic clean series (numpy default_rng(6), mean=100, std=10):
# verified homogeneous, stationary, no gaps, all positive.
CLEAN_VALUES = [
    110.5, 117.8, 74.5, 98.6, 110.1, 113.5, 106.5, 115.0, 102.9, 105.5,
    101.8, 89.3, 91.5, 103.8, 94.2, 112.7, 112.9, 118.0, 99.7, 113.8,
    90.9, 91.8, 100.8, 102.8, 84.0, 82.7, 103.6, 91.4, 112.1, 103.9,
]


def make_container():
    return build_container()


def make_dataset() -> Dataset:
    return Dataset(
        name="Тестовый пост",
        data={1990 + i: v for i, v in enumerate(CLEAN_VALUES)},
        dataset_type=DatasetType.OBSERVED,
    )


def make_daily_frame() -> pd.DataFrame:
    """Synthetic daily series for 3 years (max/min runoff methodologies)."""
    rng = np.random.default_rng(7)
    rows = []
    for year in (2021, 2022, 2023):
        for day in range(365):
            seasonal = 60 + 40 * np.sin(day / 365 * 2 * np.pi)
            rows.append((year, day, round(max(1.0, seasonal + rng.normal(0, 8)), 2)))
    return pd.DataFrame(rows, columns=["year", "day", "value"])


def execute(container, methodology_id: str, dataset: Dataset, parameters=None):
    descriptor = container.registry.get(methodology_id)
    return container.calculation.execute(
        descriptor.to_methodology(),
        dataset,
        parameters=parameters,
    )


# ----------------------------------------------------------------------
# Registry wiring
# ----------------------------------------------------------------------
def test_container_registers_all_p0_handlers():
    container = make_container()

    assert sorted(container.registered_methodology_ids()) == [
        "baseflow",
        "composite_curves",
        "confidence_bands",
        "drought_spi",
        "ecological_flow",
        "flow_duration",
        "frequency_kritsky_menkel",
        "frequency_pearson3",
        "homogeneity_full",
        "ice_phenomena",
        "intra_annual",
        "max_runoff",
        "min_runoff",
        "reservoir_regulation",
        "snowmelt",
        "spectral_hurst",
        "spillway",
        "stats_parameters",
        "storage_yield",
        "trends_full",
    ]


# ----------------------------------------------------------------------
# Execution through the service layer -> COMPLETED
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "methodology_id",
    [
        "stats_parameters",
        "frequency_pearson3",
        "frequency_kritsky_menkel",
        "homogeneity_full",
        "trends_full",
        "flow_duration",
    ],
)
def test_p0_methodologies_complete_through_service(methodology_id):
    container = make_container()

    result = execute(container, methodology_id, make_dataset())

    assert result.is_successful is True
    assert result.metadata.status == CalculationStatus.COMPLETED
    assert result.output_data  # non-empty payload


def test_max_runoff_completes_through_service():
    container = make_container()

    result = execute(
        container,
        "max_runoff",
        make_dataset(),
        parameters={"daily_df": make_daily_frame()},
    )

    assert result.is_successful is True
    assert result.metadata.status == CalculationStatus.COMPLETED


def test_min_runoff_completes_through_service():
    container = make_container()

    result = execute(
        container,
        "min_runoff",
        make_dataset(),
        parameters={"daily_df": make_daily_frame()},
    )

    assert result.is_successful is True
    assert result.metadata.status == CalculationStatus.COMPLETED


def test_reservoir_regulation_completes_through_service():
    container = make_container()

    result = execute(
        container,
        "reservoir_regulation",
        make_dataset(),
        parameters={"demand_m3_s": 80.0},
    )

    assert result.is_successful is True
    assert result.metadata.status == CalculationStatus.COMPLETED


# ----------------------------------------------------------------------
# Equivalence: service layer == direct core call (zero divergence)
# ----------------------------------------------------------------------
def test_stats_parameters_equivalent_to_core():
    from core.stats.parameters import calculate_statistical_parameters

    dataset = make_dataset()
    container = make_container()

    result = execute(container, "stats_parameters", dataset)
    direct = calculate_statistical_parameters(
        np.asarray(dataset.values, dtype=float), show_warnings=False
    )

    for key, expected in direct.items():
        assert result.output_data[key] == pytest.approx(expected)


def test_frequency_pearson3_equivalent_to_core():
    from core.stats.frequency import calculate_frequency_curve

    dataset = make_dataset()
    container = make_container()

    result = execute(container, "frequency_pearson3", dataset)
    frame = calculate_frequency_curve(
        np.asarray(dataset.values, dtype=float), curve_type="pearson3"
    )

    expected = result.output_data
    assert expected["columns"] == [str(c) for c in frame.columns]
    assert len(expected["rows"]) == len(frame)
    for row, record in zip(expected["rows"], frame.to_dict(orient="records"), strict=True):
        for cell, column in zip(row, expected["columns"], strict=True):
            assert cell == pytest.approx(float(record[column]))


def test_homogeneity_equivalent_to_core():
    from core.stats.homogeneity import check_homogeneity_full

    dataset = make_dataset()
    container = make_container()

    result = execute(container, "homogeneity_full", dataset)
    direct = check_homogeneity_full(np.asarray(dataset.values, dtype=float))

    assert result.output_data["is_homogeneous"] == direct["is_homogeneous"]


def test_flow_duration_equivalent_to_core():
    from core.stats.flow_duration import flow_duration_curve

    dataset = make_dataset()
    container = make_container()

    result = execute(container, "flow_duration", dataset)
    direct = flow_duration_curve(np.asarray(dataset.values, dtype=float))

    for key, expected in direct.items():
        actual = result.output_data[key]
        if isinstance(expected, pd.DataFrame):
            # Service serializes a DataFrame into {"columns": [...], "rows": [...]}.
            assert actual["columns"] == [str(c) for c in expected.columns]
            flat_expected = [float(v) for v in expected.values.ravel()]
            flat_actual = [float(v) for row in actual["rows"] for v in row]
            assert flat_actual == pytest.approx(flat_expected)
        elif isinstance(expected, dict):
            for sub_key, sub_expected in expected.items():
                assert actual[sub_key] == pytest.approx(sub_expected)
        elif isinstance(expected, (list, tuple)):
            assert list(actual) == pytest.approx(list(expected))
        else:
            assert actual == pytest.approx(expected)


# ----------------------------------------------------------------------
# Inapplicable methodology: clear error with the normative reference
# ----------------------------------------------------------------------
def test_short_series_is_rejected_with_normative_reference():
    container = make_container()
    # stats_parameters requires >= 25 points (СП 482 п. 8.2 / СП 33-101-2003)
    short = Dataset(
        name="Короткий ряд",
        data={1990 + k: 100.0 + 5.0 * k for k in range(5)},
        dataset_type=DatasetType.OBSERVED,
    )

    with pytest.raises(Exception) as exc_info:
        execute(container, "stats_parameters", short)

    message = str(exc_info.value)
    assert "Статистические параметры" in message  # methodology name
    assert "не короче 25 лет" in message  # requirement
    assert "5" in message  # actual length reported
    assert "СП 33-101-2003" in message  # normative reference present


def test_missing_required_parameter_is_rejected():
    container = make_container()

    with pytest.raises(Exception) as exc_info:
        execute(container, "reservoir_regulation", make_dataset())

    message = str(exc_info.value)
    assert "demand" in message


def test_missing_daily_df_is_rejected_for_max_runoff():
    container = make_container()

    with pytest.raises(Exception) as exc_info:
        execute(container, "max_runoff", make_dataset())

    assert "daily_df" in str(exc_info.value)


def test_unknown_methodology_raises_key_error():
    container = make_container()

    with pytest.raises(KeyError):
        container.registry.get("no_such_methodology")


def test_descriptor_catalogue_is_complete_for_p0():
    container = make_container()

    for methodology_id in container.registered_methodology_ids():
        descriptor = container.registry.get(methodology_id)
        assert descriptor.standard, methodology_id
        assert descriptor.scope, methodology_id
        assert descriptor.normative_reference != "не указана", methodology_id
        assert descriptor.qualified_name.endswith("@1.0"), methodology_id
