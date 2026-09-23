"""
tests/test_extended_methodologies.py
P1.4 acceptance tests (DOCS/ROADMAP.md, stage P1.4): extended methodology registry.

Key criteria covered:
- N=10 new methodology ids are registered with both descriptor and handler;
- each runs through CalculationService.execute() and returns COMPLETED;
- results through the service are EQUAL to direct core calls (zero divergence);
- missing required parameters are rejected with a clear message.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.domain import CalculationStatus, Dataset, DatasetType
from core.services.bootstrap import build_container

# Same deterministic clean series as in tests/test_methodology_service.py
CLEAN_VALUES = [
    110.5, 117.8, 74.5, 98.6, 110.1, 113.5, 106.5, 115.0, 102.9, 105.5,
    101.8, 89.3, 91.5, 103.8, 94.2, 112.7, 112.9, 118.0, 99.7, 113.8,
    90.9, 91.8, 100.8, 102.8, 84.0, 82.7, 103.6, 91.4, 112.1, 103.9,
]

# P1.4: N=10 new methodology ids (решение 9.4)
P14_IDS = [
    "baseflow",
    "confidence_bands",
    "composite_curves",
    "drought_spi",
    "ecological_flow",
    "ice_phenomena",
    "intra_annual",
    "snowmelt",
    "spillway",
    "spectral_hurst",
]


def make_container():
    return build_container()


def make_dataset() -> Dataset:
    return Dataset(
        name="Тестовый пост",
        data={1990 + i: v for i, v in enumerate(CLEAN_VALUES)},
        dataset_type=DatasetType.OBSERVED,
    )


def execute(container, methodology_id: str, dataset: Dataset, parameters=None):
    descriptor = container.registry.get(methodology_id)
    return container.calculation.execute(
        descriptor.to_methodology(),
        dataset,
        parameters=parameters,
    )


def make_monthly_frame() -> pd.DataFrame:
    """Monthly precip/discharge-like frame for 10 water years (columns 1–12)."""
    rng = np.random.default_rng(11)
    rows = []
    for year in range(1990, 2000):
        row = {"year": year}
        for month in range(1, 13):
            row[month] = round(max(0.0, 50 + 30 * np.sin(month / 12 * 2 * np.pi) + rng.normal(0, 8)), 1)
        rows.append(row)
    return pd.DataFrame(rows).set_index("year")


def params_for(methodology_id: str) -> dict | None:
    """Default parameters for methodologies that require them."""
    table: dict[str, dict] = {
        "composite_curves": {"break_year": 2004},
        "intra_annual": {"monthly_df": make_monthly_frame()},
        "snowmelt": {"W_initial": 120.0, "precipitation_mm": 25.0, "T_air": 8.0},
        "spillway": {"Q_design": 250.0, "H_max": 3.5, "L": 40.0},
        "ecological_flow": {"Q_annual_mean": float(np.mean(CLEAN_VALUES))},
        "ice_phenomena": {"latitude": 56.0, "mean_jan_temp": -10.0},
        "confidence_bands": {"n_bootstrap": 50},  # keep tests fast
    }
    return table.get(methodology_id)


# ----------------------------------------------------------------------
# Registry wiring: N=10 new ids registered with handlers
# ----------------------------------------------------------------------
def test_p14_ids_are_registered():
    container = make_container()
    registered = set(container.registered_methodology_ids())

    for methodology_id in P14_IDS:
        assert methodology_id in registered, methodology_id
        descriptor = container.registry.get(methodology_id)
        assert descriptor.standard, methodology_id
        assert descriptor.scope, methodology_id
        assert descriptor.normative_reference != "не указана", methodology_id
        assert descriptor.qualified_name.endswith("@1.0"), methodology_id


def test_p14_grows_registered_list_by_ten():
    container = make_container()
    # P0 had 9 handlers; P1.4 adds 10; P1.7 adds storage_yield → 20 total
    # registered (descriptor + handler).
    assert len(container.registered_methodology_ids()) == 20
    assert "storage_yield" in container.registered_methodology_ids()
    assert len(P14_IDS) == 10


# ----------------------------------------------------------------------
# Execution through the service layer -> COMPLETED
# ----------------------------------------------------------------------
@pytest.mark.parametrize("methodology_id", P14_IDS)
def test_p14_methodologies_complete_through_service(methodology_id):
    container = make_container()

    result = execute(container, methodology_id, make_dataset(), parameters=params_for(methodology_id))

    assert result.is_successful is True
    assert result.metadata.status == CalculationStatus.COMPLETED
    assert result.output_data  # non-empty payload


# ----------------------------------------------------------------------
# Equivalence: service layer == direct core call (zero divergence)
# ----------------------------------------------------------------------
def test_spectral_hurst_equivalent_to_core():
    from core.stats.spectral import hurst_exponent

    dataset = make_dataset()
    container = make_container()

    result = execute(container, "spectral_hurst", dataset)
    direct = hurst_exponent(np.asarray(dataset.values, dtype=float))

    assert result.output_data["H"] == pytest.approx(direct["H"])
    assert result.output_data["R_over_S"] == pytest.approx(direct["R_over_S"])
    assert result.output_data["confidence"] == direct["confidence"]


def test_drought_spi_equivalent_to_core():
    from core.stats.drought import spi_index

    dataset = make_dataset()
    container = make_container()

    result = execute(container, "drought_spi", dataset, parameters={"scale": 12})
    direct = spi_index(np.asarray(dataset.values, dtype=float), scale=12)

    assert result.output_data["n_drought"] == direct["n_drought"]
    assert result.output_data["scale_months"] == direct["scale_months"]
    assert list(result.output_data["spi_values"]) == pytest.approx(
        list(direct["spi_values"])
    )


def test_baseflow_equivalent_to_core():
    from core.stats.baseflow import baseflow_straight_line

    dataset = make_dataset()
    container = make_container()

    result = execute(container, "baseflow", dataset)
    direct = baseflow_straight_line(np.asarray(dataset.values, dtype=float))

    assert result.output_data["baseflow_ratio"] == pytest.approx(direct["baseflow_ratio"])
    assert list(result.output_data["baseflow"]) == pytest.approx(list(direct["baseflow"]))
    assert list(result.output_data["surface_flow"]) == pytest.approx(
        list(direct["surface_flow"])
    )


def test_confidence_bands_equivalent_to_core():
    from core.stats.confidence_bands import pearson3_confidence_bands

    dataset = make_dataset()
    container = make_container()
    parameters = {"n_bootstrap": 50}

    result = execute(container, "confidence_bands", dataset, parameters=parameters)
    direct = pearson3_confidence_bands(
        np.asarray(dataset.values, dtype=float),
        n_bootstrap=50,
    )

    assert result.output_data["confidence"] == pytest.approx(direct["confidence"])
    assert list(result.output_data["Q_mean"]) == pytest.approx(list(direct["Q_mean"]))
    assert list(result.output_data["Q_lower"]) == pytest.approx(
        list(direct["Q_lower"]), abs=1e-6
    )
    assert list(result.output_data["Q_upper"]) == pytest.approx(
        list(direct["Q_upper"]), abs=1e-6
    )


def test_composite_curves_equivalent_to_core():
    from core.stats.composite_curves import compute_composite_curve

    dataset = make_dataset()
    container = make_container()
    parameters = {"break_year": 2004}

    result = execute(container, "composite_curves", dataset, parameters=parameters)
    direct = compute_composite_curve(
        np.asarray(dataset.values, dtype=float),
        np.asarray(dataset.years, dtype=float),
        2004,
    )

    assert result.output_data["break_year"] == direct["break_year"]
    assert result.output_data["n_part1"] == direct["n_part1"]
    assert result.output_data["n_part2"] == direct["n_part2"]
    # curve_df is serialized as {"columns": [...], "rows": [...]}
    assert result.output_data["curve_df"]["columns"] == [
        str(c) for c in direct["curve_df"].columns
    ]
    assert len(result.output_data["curve_df"]["rows"]) == len(direct["curve_df"])


def test_intra_annual_equivalent_to_core():
    from core.hydrorash.intra_annual import calculate_water_year_sums, compute_intra_annual_stats

    dataset = make_dataset()
    container = make_container()
    monthly_df = make_monthly_frame()
    parameters = {"monthly_df": monthly_df}

    result = execute(container, "intra_annual", dataset, parameters=parameters)
    sums = calculate_water_year_sums(monthly_df)
    direct_stats = compute_intra_annual_stats(sums)

    assert result.output_data["sums"]["columns"] == [str(c) for c in sums.columns]
    assert len(result.output_data["sums"]["rows"]) == len(sums)
    for column, expected in direct_stats.items():
        for key, value in expected.items():
            assert result.output_data["stats"][column][key] == pytest.approx(value)


def test_snowmelt_equivalent_to_core():
    from core.hydrorash.snowmelt import snowmelt_balance

    dataset = make_dataset()
    container = make_container()
    parameters = {"W_initial": 120.0, "precipitation_mm": 25.0, "T_air": 8.0}

    result = execute(container, "snowmelt", dataset, parameters=parameters)
    direct = snowmelt_balance(120.0, 25.0, 8.0)

    for key, expected in direct.items():
        assert result.output_data[key] == pytest.approx(expected)


def test_spillway_equivalent_to_core():
    from core.hydrorash.spillway import spillway_capacity_check

    dataset = make_dataset()
    container = make_container()
    parameters = {"Q_design": 250.0, "H_max": 3.5, "L": 40.0}

    result = execute(container, "spillway", dataset, parameters=parameters)
    direct = spillway_capacity_check(250.0, 3.5, 40.0)

    for key, expected in direct.items():
        assert result.output_data[key] == pytest.approx(expected)


def test_ecological_flow_equivalent_to_core():
    from core.hydrorash.ecological_flow import tessmann_seasonal

    dataset = make_dataset()
    container = make_container()
    q_mean = float(np.mean(CLEAN_VALUES))
    parameters = {"Q_annual_mean": q_mean}

    result = execute(container, "ecological_flow", dataset, parameters=parameters)
    direct = tessmann_seasonal(q_mean)

    assert result.output_data["Q_eco_annual_mean"] == pytest.approx(
        direct["Q_eco_annual_mean"]
    )
    assert result.output_data["eco_ratio_to_Qmean"] == pytest.approx(
        direct["eco_ratio_to_Qmean"]
    )
    assert list(result.output_data["Q_eco_monthly"]) == pytest.approx(
        list(direct["Q_eco_monthly"])
    )
    # monthly_table DataFrame → {"columns", "rows"}
    assert result.output_data["monthly_table"]["columns"] == [
        str(c) for c in direct["monthly_table"].columns
    ]


def test_ice_phenomena_equivalent_to_core():
    from core.hydrorash.ice_phenomena import estimate_max_ice_thickness

    dataset = make_dataset()
    container = make_container()
    parameters = {"latitude": 56.0, "mean_jan_temp": -10.0}

    result = execute(container, "ice_phenomena", dataset, parameters=parameters)
    direct = estimate_max_ice_thickness(56.0, -10.0)

    assert result.output_data["thickness_m"] == pytest.approx(direct["thickness_m"])
    # thickness_range_m tuple → list after serialization
    assert list(result.output_data["thickness_range_m"]) == pytest.approx(
        list(direct["thickness_range_m"])
    )
    assert result.output_data["zone"] == direct["zone"]
    assert result.output_data["confidence"] == direct["confidence"]


# ----------------------------------------------------------------------
# Missing required parameters are rejected
# ----------------------------------------------------------------------
def test_missing_required_parameters_for_p14():
    container = make_container()

    with pytest.raises(Exception) as exc_info:
        execute(container, "spillway", make_dataset())
    assert "Q_design" in str(exc_info.value) or "обязательные" in str(exc_info.value)

    with pytest.raises(Exception) as exc_info:
        execute(container, "snowmelt", make_dataset())
    assert "W_initial" in str(exc_info.value) or "обязательные" in str(exc_info.value)

    with pytest.raises(Exception) as exc_info:
        execute(container, "ecological_flow", make_dataset())
    assert "Q_annual_mean" in str(exc_info.value) or "обязательные" in str(
        exc_info.value
    )

    with pytest.raises(Exception) as exc_info:
        execute(container, "ice_phenomena", make_dataset())
    assert "latitude" in str(exc_info.value) or "обязательные" in str(exc_info.value)

    with pytest.raises(Exception) as exc_info:
        execute(container, "intra_annual", make_dataset())
    assert "monthly_df" in str(exc_info.value) or "обязательные" in str(
        exc_info.value
    )


def test_short_series_rejected_for_spectral_hurst():
    container = make_container()
    short = Dataset(
        name="Короткий ряд",
        data={1990 + k: 100.0 + 5.0 * k for k in range(5)},
        dataset_type=DatasetType.OBSERVED,
    )

    with pytest.raises(Exception) as exc_info:
        execute(container, "spectral_hurst", short)

    message = str(exc_info.value)
    assert "Хёрст" in message or "spectral" in message
    assert "20" in message
