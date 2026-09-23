"""
tests/test_result_store.py
Stage 4 acceptance tests (DOCS/ROADMAP.md, stage 4): result history,
numbering, provenance («откуда это число?») and comparison.

Covered:
- storing/finding results (by id, methodology, dataset, scenario);
- correct sequential numbering ("Расчёт #N");
- provenance chain contains the engine version and the data quality grade;
- compare() on a changed parameter yields the expected difference.
"""

from __future__ import annotations

from uuid import uuid4

from core.domain import (
    CalculationMetadata,
    CalculationResult,
    Methodology,
)
from core.services.bootstrap import build_container
from core.services.result_store import (
    ENGINE_VERSION,
    ProvenanceStep,
    ResultStore,
    provenance_chain,
)


def make_result(
    output: dict | None = None,
    *,
    methodology_name: str = "echo",
    dataset_id=None,
    parameters: dict | None = None,
    failed: bool = False,
):
    """A completed CalculationResult with metadata (no store involved)."""
    metadata = CalculationMetadata(
        methodology=Methodology(name=methodology_name, version="1.0"),
        input_dataset_ids=[dataset_id] if dataset_id is not None else [],
        input_parameters=parameters or {},
    )
    if failed:
        metadata.mark_failed("boom")
    else:
        metadata.mark_completed()
    return CalculationResult(metadata=metadata, output_data=output or {})


def make_store(results: int = 0) -> ResultStore:
    store = ResultStore()
    for index in range(results):
        store.attach(make_result({"value": 100.0 + index}))
    return store


# ----------------------------------------------------------------------
# Storing and numbering
# ----------------------------------------------------------------------
def test_store_assigns_sequential_labels():
    store = make_store(3)

    assert store.count() == 3
    labels = [getattr(item.metadata, "label", "") for item in store.list_results()]
    assert labels == ["Расчёт #1", "Расчёт #2", "Расчёт #3"]


def test_store_register_returns_same_result():
    store = ResultStore()
    result = make_result()

    assert store.register(result) is result
    assert store.count() == 1


def test_store_find_by_id_methodology_dataset_scenario():
    dataset_id = uuid4()
    scenario_id = uuid4()
    store = ResultStore()
    first = make_result({"value": 1.0}, methodology_name="echo", dataset_id=dataset_id)
    second = make_result({"value": 2.0}, methodology_name="other")
    store.attach(first)
    store.attach(second)
    # scenario_id is service-layer metadata attached after creation
    second.metadata.scenario_id = scenario_id

    assert store.get_by_id(first.id) is first
    assert store.get_by_id(uuid4()) is None
    assert store.find_by_methodology("echo@1.0") == [first]
    assert store.find_by_dataset(dataset_id) == [first]
    assert store.find_by_scenario(scenario_id) == [second]
    assert store.latest(1) == [second]
    assert store.latest(2) == [first, second]


def test_container_builds_result_store():
    container = build_container()

    assert isinstance(container.results, ResultStore)
    assert container.results.count() == 0


# ----------------------------------------------------------------------
# Provenance («откуда это число?»)
# ----------------------------------------------------------------------
def test_provenance_chain_contains_all_steps_in_order():
    methodology = Methodology(
        name="frequency_pearson3", version="1.0", standard="СП 33-101-2003"
    )
    metadata = CalculationMetadata(methodology=methodology, input_parameters={"Cv": 0.2})
    metadata.mark_completed()
    result = CalculationResult(metadata=metadata, output_data={"Q_p95": 1240.0})

    steps = provenance_chain(
        result,
        quality_grade="B",
        quality_score=0.8,
        scenario_name="Маловодный год",
        dataset_name="Пост 1",
        n_years=30,
        parameters={"Cv": 0.2, "Cs": 0.5},
    )

    kinds = [step.kind for step in steps]
    assert kinds == [
        "calculation",
        "methodology",
        "dataset",
        "quality",
        "parameters",
        "scenario",
        "engine",
    ]
    by_kind = {step.kind: step for step in steps}
    assert by_kind["methodology"].reference == "СП 33-101-2003"
    assert "версия 1.0" in by_kind["methodology"].detail
    assert "Пост 1" in by_kind["dataset"].detail
    assert "30 лет" in by_kind["dataset"].detail
    assert "оценка B" in by_kind["quality"].detail
    assert by_kind["parameters"].detail == "{Cv: 0.2, Cs: 0.5}"
    assert by_kind["scenario"].detail == "Маловодный год"


def test_provenance_chain_contains_engine_version():
    metadata = CalculationMetadata(methodology=Methodology(name="echo", version="1.0"))
    metadata.mark_completed()
    result = CalculationResult(metadata=metadata)

    steps = provenance_chain(result)
    engine = steps[-1]

    assert engine.kind == "engine"
    assert engine.detail == ENGINE_VERSION
    assert ENGINE_VERSION and ENGINE_VERSION != "unknown"


def test_provenance_survives_unregistered_result_without_label():
    # CalculationMetadata has no `label`/`scenario_id` fields: the store attaches
    # them dynamically. provenance must not crash on a bare result.
    result = make_result({"value": 1.0})

    steps = provenance_chain(result)

    assert [step.kind for step in steps] == ["calculation", "methodology", "engine"]
    assert isinstance(steps[0], ProvenanceStep)


def test_provenance_shows_store_label_in_calculation_step():
    store = ResultStore()
    result = store.register(make_result({"value": 1.0}))

    steps = provenance_chain(result)

    assert steps[0].kind == "calculation"
    assert steps[0].title == "Расчёт #1"


# ----------------------------------------------------------------------
# compare («было / стало»)
# ----------------------------------------------------------------------
def test_compare_detects_changed_value_with_percent():
    store = ResultStore()
    old = make_result({"Q_p95": 1180.0})
    new = make_result({"Q_p95": 1240.0})

    diff = store.compare(old, new)

    assert len(diff["changes"]) == 1
    change = diff["changes"][0]
    assert change["path"] == "Q_p95"
    assert change["old"] == 1180.0
    assert change["new"] == 1240.0
    assert change["percent"] == "+5.1%"
    assert change["note"] == "изменение +5.1%"
    assert diff["status_changed"] is False


def test_compare_reports_no_changes_for_identical_results():
    store = ResultStore()
    result = make_result({"Q_p95": 1180.0})

    diff = store.compare(result, make_result({"Q_p95": 1180.0}))

    assert diff["changes"] == []
    assert diff["status_changed"] is False


def test_compare_reports_status_change():
    store = ResultStore()

    diff = store.compare(make_result(failed=True), make_result())

    assert diff["status_changed"] is True
