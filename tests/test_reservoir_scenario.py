"""
tests/test_reservoir_scenario.py
P1.7 acceptance tests (DOCS/ROADMAP.md, stage P1.7): Reservoir Scenario Simulator.

Key criteria covered:
- numbers == core on the same inputs (zero divergence via CalculationService);
- two scenarios with different rules give distinguishable series;
- delta table shows Δ vs baseline for scalar metrics;
- scenario_type="reservoir" survives .hsp roundtrip;
- parameter validation rejects non-positive demand / guarantee / bad S0>V.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.domain import CalculationStatus, Dataset, DatasetType
from core.domain.serialization import scenario_from_dict, scenario_to_dict
from core.services.bootstrap import build_container
from core.services.project_service import ProjectService
from core.services.reservoir_scenario_service import (
    RESERVOIR_METHODOLOGY,
    RESERVOIR_SCENARIO_TYPE,
    ReservoirScenarioError,
    ReservoirScenarioService,
)
from core.services.scenario_service import ScenarioNotFoundError, ScenarioService

# Deterministic clean series (same as test_methodology_service.py)
CLEAN_VALUES = [
    110.5, 117.8, 74.5, 98.6, 110.1, 113.5, 106.5, 115.0, 102.9, 105.5,
    101.8, 89.3, 91.5, 103.8, 94.2, 112.7, 112.9, 118.0, 99.7, 113.8,
    90.9, 91.8, 100.8, 102.8, 84.0, 82.7, 103.6, 91.4, 112.1, 103.9,
]


def make_dataset() -> Dataset:
    return Dataset(
        name="Тестовый пост",
        data={1990 + i: v for i, v in enumerate(CLEAN_VALUES)},
        dataset_type=DatasetType.OBSERVED,
    )


def make_service(container=None) -> ReservoirScenarioService:
    container = container or build_container()
    scenarios = container.scenario
    scenarios.set_base_dataset(make_dataset())
    return ReservoirScenarioService(scenarios)


# ----------------------------------------------------------------------
# Creation / validation
# ----------------------------------------------------------------------
def test_create_reservoir_scenario_sets_type_and_parameters():
    service = make_service()
    scenario = service.create(
        name="Base",
        demand_m3_s=50.0,
        v_max_km3=1.0,
        target_guarantee=95.0,
        mode="guarantee_for_volume",
        year=2005,
    )
    assert scenario.scenario_type == RESERVOIR_SCENARIO_TYPE
    assert scenario.parameters["demand_m3_s"] == 50.0
    assert scenario.parameters["V_max_km3"] == 1.0
    assert scenario.parameters["target_guarantee"] == 95.0
    assert scenario.parameters["mode"] == "guarantee_for_volume"
    assert scenario.parameters["year"] == 2005
    assert service.list_reservoir() == [scenario]


def test_create_rejects_non_positive_demand():
    service = make_service()
    with pytest.raises(ReservoirScenarioError, match="demand_m3_s"):
        service.create(name="Bad", demand_m3_s=0)


def test_create_rejects_bad_guarantee():
    service = make_service()
    with pytest.raises(ReservoirScenarioError, match="target_guarantee"):
        service.create(name="Bad", demand_m3_s=10.0, target_guarantee=150.0)


def test_create_rejects_s0_exceeding_vmax():
    service = make_service()
    with pytest.raises(ReservoirScenarioError, match="S_0"):
        service.create(name="Bad", demand_m3_s=10.0, v_max_km3=1.0, s0_km3=2.0)


def test_create_rejects_empty_name():
    service = make_service()
    with pytest.raises(ReservoirScenarioError, match="name"):
        service.create(name="   ", demand_m3_s=10.0)


# ----------------------------------------------------------------------
# Equivalence: numbers == core multi_year_regulation on same inputs
# ----------------------------------------------------------------------
def test_run_equals_direct_core_multi_year_regulation():
    from core.hydrorash.reservoir_regulation import multi_year_regulation

    container = build_container()
    service = make_service(container)
    scenario = service.create(
        name="Eq",
        demand_m3_s=50.0,
        v_max_km3=2.0,
        target_guarantee=95.0,
        mode="guarantee_for_volume",
    )
    result = service.run(scenario.id)
    assert result.metadata.status == CalculationStatus.COMPLETED

    expected = multi_year_regulation(
        make_dataset().values,
        demand_m3_s=50.0,
        V_max_km3=2.0,
        target_guarantee=95.0,
        mode="guarantee_for_volume",
    )
    for key in ("guarantee_percent", "deficit_years", "required_volume_km3"):
        assert result.output_data[key] == pytest.approx(expected[key])


def test_run_storage_yield_equals_direct_core():
    from core.hydrorash.reservoir_regulation import storage_yield_curve

    container = build_container()
    descriptor = container.registry.get("storage_yield")
    dataset = make_dataset()
    parameters = {"V_range_km3": [0.5, 1.0, 2.0], "target_guarantee": 95.0}
    result = container.calculation.execute(
        descriptor.to_methodology(), dataset, parameters=parameters
    )
    assert result.metadata.status == CalculationStatus.COMPLETED

    frame = storage_yield_curve(
        dataset.values,
        V_range_km3=[0.5, 1.0, 2.0],
        target_guarantee=95.0,
    )
    expected_rows = frame.to_dict(orient="records")
    assert result.output_data["columns"] == [str(c) for c in frame.columns]
    assert len(result.output_data["rows"]) == len(expected_rows)


# ----------------------------------------------------------------------
# Distinguishable scenarios + delta table
# ----------------------------------------------------------------------
def test_two_scenarios_give_distinguishable_results_and_delta():
    service = make_service()
    base = service.create(
        name="Base",
        demand_m3_s=40.0,
        v_max_km3=2.0,
        mode="guarantee_for_volume",
    )
    scenario = service.create(
        name="Scenario",
        demand_m3_s=80.0,
        v_max_km3=2.0,
        mode="guarantee_for_volume",
    )
    base_result = service.run(base.id)
    scenario_result = service.run(scenario.id)

    # Distinguishable: higher demand → different guarantee / balance
    assert (
        base_result.output_data["guarantee_percent"]
        != scenario_result.output_data["guarantee_percent"]
        or base_result.output_data.get("balance_series_km3")
        != scenario_result.output_data.get("balance_series_km3")
    )

    rows = service.compare_delta([base.id, scenario.id], baseline_id=base.id)
    assert rows, "delta table must not be empty"
    guarantee_rows = [r for r in rows if r["metric"] == "guarantee_percent"]
    assert guarantee_rows
    row = guarantee_rows[0]
    assert row["baseline"] == "Base"
    assert "Scenario" in row
    assert "Δ Scenario" in row
    assert row["Δ Scenario"] == pytest.approx(
        row["Scenario"] - row["Base"]
    )


def test_series_for_returns_balance_series():
    service = make_service()
    scenario = service.create(
        name="Series",
        demand_m3_s=50.0,
        v_max_km3=2.0,
        mode="guarantee_for_volume",
    )
    service.run(scenario.id)
    series = service.series_for(scenario.id)
    assert len(series) == len(CLEAN_VALUES) + 1  # S_0 + one step per year
    assert all(isinstance(v, float) for v in series)


def test_run_rejects_non_reservoir_scenario():
    scenarios = ScenarioService()
    generic = scenarios.create(name="Generic", parameters={"demand_m3_s": 10.0})
    service = ReservoirScenarioService(scenarios)
    with pytest.raises(ReservoirScenarioError, match="not a reservoir"):
        service.run(generic.id)


def test_run_rejects_missing_demand():
    scenarios = ScenarioService()
    from core.domain.models import Scenario

    bad = Scenario(
        name="NoDemand",
        project_id=scenarios.project_id,
        scenario_type=RESERVOIR_SCENARIO_TYPE,
    )
    scenarios._scenarios[bad.id] = bad  # direct insert: missing parameters
    service = ReservoirScenarioService(scenarios)
    with pytest.raises(ReservoirScenarioError, match="demand_m3_s"):
        service.run(bad.id)


def test_get_unknown_scenario_raises_not_found():
    from uuid import uuid4

    service = make_service()
    with pytest.raises(ScenarioNotFoundError):
        service.get(uuid4())


# ----------------------------------------------------------------------
# Serialization / .hsp roundtrip
# ----------------------------------------------------------------------
def test_scenario_type_serialization_roundtrip():
    scenarios = ScenarioService()
    original = scenarios.create(
        name="Res",
        parameters={"demand_m3_s": 10.0},
        scenario_type=RESERVOIR_SCENARIO_TYPE,
    )
    restored = scenario_from_dict(scenario_to_dict(original))
    assert restored.scenario_type == RESERVOIR_SCENARIO_TYPE
    assert restored.parameters == original.parameters
    assert restored.id == original.id


def test_hsp_roundtrip_preserves_reservoir_type(tmp_path: Path):
    service = ProjectService()
    project = service.create_project("Reservoir project")
    scenarios = ScenarioService(project_id=project.id)
    reservoir = scenarios.create(
        name="Base Res",
        parameters={"demand_m3_s": 30.0, "V_max_km3": 1.5},
        scenario_type=RESERVOIR_SCENARIO_TYPE,
    )
    service.add_scenario(reservoir)
    path = service.save_project(tmp_path / "res.hsp")

    reopened = ProjectService.from_file(path)
    types = {s.name: s.scenario_type for s in reopened.scenarios}
    assert types["Base Res"] == RESERVOIR_SCENARIO_TYPE


def test_reservoir_methodology_is_registered():
    container = build_container()
    assert container.registry.has(RESERVOIR_METHODOLOGY)
    assert container.calculation.has_handler(
        container.registry.get(RESERVOIR_METHODOLOGY).qualified_name
    )
