"""
tests/test_domain_services.py
Smoke tests for the P0 domain and service layer (stage 0 of DOCS/ROADMAP.md).

These tests run without GUI: only `core.domain` and `core.services` are touched.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from core.domain import (
    CalculationStatus,
    Dataset,
    DatasetType,
    Methodology,
    Project,
    ProjectStatus,
    Scenario,
    ScenarioStatus,
    ValidationResult,
    ValidationSeverity,
)
from core.services import (
    CalculationError,
    CalculationService,
    MethodologyDescriptor,
    MethodologyRegistry,
    ScenarioNotFoundError,
    ScenarioService,
    ValidationService,
    build_default_registry,
)


def make_series(overrides: dict[int, float] | None = None) -> Dataset:
    """Yearly series 1990..2009 with a simple non-degenerate pattern."""
    data = {1990 + index: 100.0 + index * 2.0 for index in range(20)}
    data.update(overrides or {})
    return Dataset(name="Тестовый пост", data=data, dataset_type=DatasetType.OBSERVED)


# ----------------------------------------------------------------------
# Domain models
# ----------------------------------------------------------------------
def test_domain_enums_are_exported():
    assert ProjectStatus.DRAFT.value == "draft"
    assert DatasetType.OBSERVED.value == "observed"
    assert CalculationStatus.COMPLETED.value == "completed"
    assert ValidationSeverity.WARNING.value == "warning"
    assert ScenarioStatus.ARCHIVED.value == "archived"


def test_project_requires_non_empty_name():
    with pytest.raises(ValueError):
        Project(name="   ")


def test_project_touch_updates_timestamp():
    project = Project(name="Река X — расчёт максимального стока")
    before = project.updated_at

    project.touch()

    assert project.updated_at >= before


def test_dataset_properties():
    dataset = Dataset(name="Пост 1", data={1991: 11.0, 1990: 10.0, 1992: 12.0})

    assert dataset.years == [1990, 1991, 1992]
    assert dataset.values == [10.0, 11.0, 12.0]
    assert dataset.length == 3
    assert dataset.start_year == 1990
    assert dataset.end_year == 1992


def test_dataset_clone_is_independent():
    dataset = make_series()
    clone = dataset.clone()

    assert clone.id != dataset.id
    assert clone.name.endswith("(copy)")
    assert clone.data == dataset.data

    clone.data[1990] = 0.0

    assert dataset.data[1990] == 100.0


def test_dataset_rejects_non_positive_catchment_area():
    with pytest.raises(ValueError):
        Dataset(name="Пост 1", data={1990: 10.0}, catchment_area_km2=0.0)


def test_methodology_identity_by_qualified_name():
    first = Methodology(name="frequency_pearson3", version="1.0")
    second = Methodology(name="frequency_pearson3", version="1.0")
    other_version = Methodology(name="frequency_pearson3", version="1.1")

    assert first.qualified_name == "frequency_pearson3@1.0"
    assert first == second
    assert hash(first) == hash(second)
    assert len({first, second}) == 1
    assert first != other_version


def test_methodology_requires_version():
    with pytest.raises(ValueError):
        Methodology(name="frequency_pearson3", version="  ")


# ----------------------------------------------------------------------
# ValidationService
# ----------------------------------------------------------------------
def issue_codes(result) -> set[str]:
    return {issue.code for issue in result.issues}


def test_validation_service_flags_gap_negative_and_zero():
    dataset = make_series({1999: -5.0, 2001: 0.0})
    del dataset.data[1995]  # разрыв временного ряда

    result = ValidationService().validate_dataset(dataset, min_points=10)

    codes = issue_codes(result)
    assert "DATA_GAPS" in codes
    assert "NEGATIVE_VALUES" in codes
    assert "ZERO_VALUES" in codes
    assert result.is_valid is True  # предупреждения не блокируют расчёт


def test_validation_service_reports_insufficient_data():
    dataset = Dataset(name="Короткий ряд", data={1990: 10.0, 1991: 12.0, 1992: 11.0})

    result = ValidationService().validate_dataset(dataset, min_points=10)

    assert "INSUFFICIENT_DATA" in issue_codes(result)
    assert result.is_valid is False
    assert result.errors


def test_validation_service_handles_empty_dataset():
    result = ValidationService().validate_dataset(Dataset(name="Пусто", data={}))

    assert "EMPTY_DATASET" in issue_codes(result)
    assert result.is_valid is False


def test_validation_service_quality_report():
    report = ValidationService().generate_quality_report(make_series())

    assert report.n_points == 20
    assert 0.0 <= report.quality_score <= 1.0
    assert report.quality_grade in {"A", "B", "C", "D", "F"}
    assert report.to_dict()["dataset_name"] == "Тестовый пост"


# ----------------------------------------------------------------------
# Scenario model and ScenarioService
# ----------------------------------------------------------------------
def test_scenario_with_parameters_keeps_original():
    base = Scenario(name="Базовый", project_id=uuid4(), parameters={"demand": 300.0})

    modified = base.with_parameters(demand=350.0)

    assert base.parameters["demand"] == 300.0
    assert modified.parameters["demand"] == 350.0
    assert modified.parent_scenario_id == base.id
    assert modified.id != base.id


def test_scenario_requires_name():
    with pytest.raises(ValueError):
        Scenario(name="", project_id=uuid4())


def test_scenario_service_crud_and_lineage():
    service = ScenarioService()
    base = service.create("Базовый", {"demand": 300.0})

    assert len(service) == 1
    assert service.has(base.id)
    assert base.id in service

    service.update(base.id, {"demand": 320.0})
    assert service.get(base.id).parameters["demand"] == 320.0

    clone = service.clone(base.id, name="Маловодный год", parameters={"inflow": 350.0})

    assert clone.parent_scenario_id == base.id
    assert clone.status is ScenarioStatus.DRAFT
    assert clone.parameters["demand"] == 320.0
    assert clone.parameters["inflow"] == 350.0
    assert base.parameters == {"demand": 320.0}
    assert len(service) == 2


def test_scenario_service_unknown_id_raises():
    service = ScenarioService()

    with pytest.raises(ScenarioNotFoundError):
        service.get(uuid4())


def test_scenario_service_archive_hides_scenario():
    service = ScenarioService()
    base = service.create("Базовый", {"demand": 300.0})

    service.archive(base.id)

    assert service.list() == []
    assert service.list(include_archived=True) == [base]


def test_scenario_service_compare_parameters():
    service = ScenarioService()
    service.create("Базовый", {"demand": 300.0})
    service.create("Засушливый", {"demand": 250.0, "inflow": 350.0})

    rows = service.compare()
    by_parameter = {row["parameter"]: row for row in rows}

    assert set(by_parameter) == {"demand", "inflow"}
    assert by_parameter["demand"]["Базовый"] == 300.0
    assert by_parameter["demand"]["Засушливый"] == 250.0
    assert by_parameter["inflow"]["Базовый"] is None


def test_scenario_service_run_requires_service_and_dataset():
    service = ScenarioService()
    scenario = service.create("Базовый", {"demand": 300.0})
    methodology = Methodology(name="echo", version="1.0")

    with pytest.raises(CalculationError):
        service.run(scenario.id, methodology)  # нет CalculationService

    service.set_calculation_service(CalculationService())

    with pytest.raises(CalculationError):
        service.run(scenario.id, methodology)  # нет датасета


def test_scenario_service_run_passes_parameters_and_stores_result():
    seen: dict = {}

    def echo_handler(context):
        seen["parameters"] = dict(context.parameters)
        return {"echo": True}

    calculation = CalculationService()
    calculation.register_handler("echo@1.0", echo_handler)
    service = ScenarioService(calculation_service=calculation, base_dataset=make_series())
    scenario = service.create("Базовый", {"demand": 300.0})

    result = service.run(scenario.id, Methodology(name="echo", version="1.0"))

    assert result.is_successful is True
    assert result.output_data == {"echo": True}
    assert seen["parameters"] == {"demand": 300.0}
    assert service.get_result(scenario.id) is result


# ----------------------------------------------------------------------
# MethodologyRegistry
# ----------------------------------------------------------------------
def test_default_registry_catalogue_is_complete():
    registry = build_default_registry()

    assert len(registry) >= 10
    assert "homogeneity_full" in registry
    assert "statistics" in registry.categories()
    assert registry.ids() == sorted(registry.ids())
    assert registry.by_standard("СП 33-101-2003")
    assert all(item.standard for item in registry)
    assert all(item.name.strip() for item in registry)

    descriptor = registry.get("homogeneity_full")
    assert descriptor.normative_reference == "СП 33-101-2003, Приложение А"
    assert descriptor.scope


def test_registry_rejects_duplicates_and_unknown_ids():
    registry = MethodologyRegistry()
    descriptor = MethodologyDescriptor(id="demo", name="Демонстрационная методика")
    registry.register(descriptor)

    with pytest.raises(ValueError):
        registry.register(descriptor)
    with pytest.raises(KeyError):
        registry.get("missing")
    assert registry.get_optional("missing") is None

    registry.unregister("demo")
    assert len(registry) == 0


def test_registry_applicability_checks():
    registry = MethodologyRegistry()
    registry.register(
        MethodologyDescriptor(
            id="needs_30_years",
            name="Требует 30 лет наблюдений",
            standard="СП 33-101-2003",
            min_points=30,
            required_parameters=("Cs",),
        )
    )
    short_series = make_series()  # 20 лет

    short_result = registry.check_applicability("needs_30_years", short_series)

    assert "INSUFFICIENT_DATA" in issue_codes(short_result)
    assert short_result.is_valid is False

    no_param_result = registry.check_applicability(
        "needs_30_years", short_series, parameters={"Cv": 0.3}
    )
    assert "MISSING_PARAMETER" in issue_codes(no_param_result)

    long_series = Dataset(
        name="Длинный ряд", data={1990 + i: 100.0 + i for i in range(40)}
    )
    ok_result = registry.check_applicability(
        "needs_30_years", long_series, parameters={"Cs": 0.6}
    )
    assert ok_result.is_valid is True
    assert issue_codes(ok_result) == set()


def test_descriptor_converts_to_methodology():
    descriptor = MethodologyDescriptor(
        id="frequency_pearson3",
        name="Кривая обеспеченности (Пирсон III)",
        standard="СП 33-101-2003",
    )

    methodology = descriptor.to_methodology()

    assert methodology.qualified_name == "frequency_pearson3@1.0"
    assert methodology.standard == "СП 33-101-2003"
    assert methodology.description == descriptor.name


def test_descriptor_validates_input():
    with pytest.raises(ValueError):
        MethodologyDescriptor(id="", name="Имя")
    with pytest.raises(ValueError):
        MethodologyDescriptor(id="demo", name="")
    with pytest.raises(ValueError):
        MethodologyDescriptor(id="demo", name="Имя", min_points=-1)


# ----------------------------------------------------------------------
# CalculationService
# ----------------------------------------------------------------------
def test_calculation_service_requires_registered_handler():
    service = CalculationService()
    methodology = Methodology(name="unknown_method", version="1.0")

    with pytest.raises(CalculationError):
        service.execute(methodology, make_series())

    assert service.get_registered_methodologies() == []
    assert service.has_handler(methodology.qualified_name) is False


def test_calculation_service_runs_handler_and_records_metadata():
    service = CalculationService()

    def handler(context):
        return {"values": context.dataset.values, "n": context.dataset.length}

    service.register_handler("demo@1.0", handler)

    result = service.execute(Methodology(name="demo", version="1.0"), make_series())

    assert result.is_successful is True
    assert result.metadata.status is CalculationStatus.COMPLETED
    assert result.methodology_name == "demo@1.0"
    assert result.output_data["n"] == 20
    assert result.metadata.duration_seconds is not None


def test_calculation_service_validator_can_block_execution():
    service = CalculationService()

    def validator(context):
        blocked = ValidationResult(is_valid=False)
        blocked.add_issue(
            code="BLOCKED",
            message="Ряд непригоден для расчёта",
            severity=ValidationSeverity.ERROR,
        )
        return blocked

    service.register_handler("demo@1.0", lambda context: {"ok": True})
    service.register_validator("demo@1.0", validator)

    with pytest.raises(CalculationError):
        service.execute(Methodology(name="demo", version="1.0"), make_series())



