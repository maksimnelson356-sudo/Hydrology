"""
Tests for ScenarioService.
"""
from unittest.mock import MagicMock

import pytest

from core.domain.models import Dataset, ScenarioStatus
from core.services.calculation_service import CalculationError, CalculationService
from core.services.scenario_service import ScenarioNotFoundError, ScenarioService


def make_dataset(name: str = "Test Dataset", data: dict[int, float] | None = None) -> Dataset:
    if data is None:
        data = {2000: 1.0, 2001: 2.0, 2002: 3.0}
    return Dataset(name=name, data=data)


def test_scenario_service_create_and_get():
    service = ScenarioService()
    scenario = service.create(
        name="Test Scenario",
        parameters={"param1": 10},
        description="A test scenario",
    )
    assert scenario.name == "Test Scenario"
    assert scenario.description == "A test scenario"
    assert scenario.parameters == {"param1": 10}
    # The default status for a newly created scenario is DRAFT
    assert scenario.status == ScenarioStatus.DRAFT

    retrieved = service.get(scenario.id)
    assert retrieved.id == scenario.id
    assert retrieved.name == scenario.name


def test_scenario_service_update():
    service = ScenarioService()
    scenario = service.create(name="Original", parameters={"a": 1})
    updated = service.update(scenario.id, name="Updated", parameters={"b": 2}, description="Desc")
    assert updated.name == "Updated"
    assert updated.description == "Desc"
    # parameters should be updated (merged)
    assert updated.parameters == {"a": 1, "b": 2}


def test_scenario_service_clone():
    service = ScenarioService()
    base = service.create(name="Base", parameters={"x": 1})
    clone = service.clone(base.id, name="Clone", parameters={"y": 2})
    assert clone.name == "Clone"
    assert clone.parameters == {"x": 1, "y": 2}
    assert clone.parent_scenario_id == base.id
    # Original unchanged
    assert service.get(base.id).parameters == {"x": 1}


def test_scenario_service_archive_and_activate():
    service = ScenarioService()
    scenario = service.create(name="ToArchive")
    archived = service.archive(scenario.id)
    assert archived.status == ScenarioStatus.ARCHIVED
    activated = service.activate(scenario.id)
    assert activated.status == ScenarioStatus.ACTIVE


def test_scenario_service_remove():
    service = ScenarioService()
    scenario = service.create(name="ToRemove")
    service.remove(scenario.id)
    assert not service.has(scenario.id)
    with pytest.raises(ScenarioNotFoundError):
        service.get(scenario.id)


def test_scenario_service_list_excludes_archived_by_default():
    service = ScenarioService()
    active = service.create(name="Active")
    archived = service.create(name="Archived")
    service.archive(archived.id)
    scenarios = service.list()
    assert len(scenarios) == 1
    assert scenarios[0].id == active.id
    # With include_archived=True
    all_scenarios = service.list(include_archived=True)
    assert len(all_scenarios) == 2


def test_scenario_service_dataset_override():
    service = ScenarioService()
    base_ds = make_dataset("Base")
    service.set_base_dataset(base_ds)
    scenario = service.create(name="Scenario with override")
    # No override yet -> should get base dataset
    assert service.get_dataset(scenario.id) == base_ds

    override_ds = make_dataset("Override", {2000: 9.0})
    service.set_dataset(scenario.id, override_ds)
    assert service.get_dataset(scenario.id) == override_ds


def test_scenario_service_run_success():
    # Mock calculation service
    mock_calc = MagicMock(spec=CalculationService)
    mock_result = MagicMock()
    mock_calc.execute.return_value = mock_result

    service = ScenarioService(calculation_service=mock_calc)
    base_ds = make_dataset()
    service.set_base_dataset(base_ds)
    scenario = service.create(name="RunMe", parameters={"p": 1})

    result = service.run(scenario.id, "some.methodology")
    assert result == mock_result
    mock_calc.execute.assert_called_once()
    # Check that the result is stored
    assert service.get_result(scenario.id) == mock_result


def test_scenario_service_run_no_calculation_service():
    service = ScenarioService()  # no calculation service
    base_ds = make_dataset()
    service.set_base_dataset(base_ds)
    scenario = service.create(name="RunMe")
    with pytest.raises(CalculationError, match="has no CalculationService"):
        service.run(scenario.id, "some.methodology")


def test_scenario_service_run_no_dataset():
    service = ScenarioService(calculation_service=CalculationService())
    # No base dataset set
    scenario = service.create(name="RunMe")
    with pytest.raises(CalculationError, match="No dataset bound"):
        service.run(scenario.id, "some.methodology")


def test_scenario_service_compare_parameters():
    service = ScenarioService()
    service.create(name="S1", parameters={"a": 1, "b": 2})
    service.create(name="S2", parameters={"a": 10, "c": 3})
    rows = service.compare()
    # Expect three rows: a, b, and c (c only in S2)
    assert len(rows) == 3
    # Find row for 'a'
    row_a = next(r for r in rows if r["parameter"] == "a")
    assert row_a["S1"] == 1
    assert row_a["S2"] == 10
    # Row for 'b'
    row_b = next(r for r in rows if r["parameter"] == "b")
    assert row_b["S1"] == 2
    assert row_b.get("S2") is None
    # Row for 'c'
    row_c = next(r for r in rows if r["parameter"] == "c")
    assert row_c["S2"] == 3
    assert row_c.get("S1") is None


def test_scenario_service_compare_results():
    mock_calc = MagicMock(spec=CalculationService)
    mock_result1 = MagicMock()
    mock_result1.metadata.status.value = "completed"
    mock_result1.output_data = {"Q": 100}
    mock_result2 = MagicMock()
    mock_result2.metadata.status.value = "failed"
    mock_result2.output_data = {}
    mock_calc.execute.side_effect = [mock_result1, mock_result2]

    service = ScenarioService(calculation_service=mock_calc)
    base_ds = make_dataset()
    service.set_base_dataset(base_ds)
    s1 = service.create(name="S1")
    s2 = service.create(name="S2")
    # Run scenarios
    service.run(s1.id, "m1")
    service.run(s2.id, "m2")

    rows = service.compare_results()
    assert len(rows) == 2
    # Find each
    row1 = next(r for r in rows if r["scenario"] == "S1")
    assert row1["status"] == "completed"
    assert row1["output"] == {"Q": 100}
    row2 = next(r for r in rows if r["scenario"] == "S2")
    assert row2["status"] == "failed"
    assert row2["output"] == {}
