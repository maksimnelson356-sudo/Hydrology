"""
tests/test_project_service.py
Project (.hsp) persistence tests - stage 1 of DOCS/ROADMAP.md.

No GUI is required: only core.domain and core.services are touched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.domain import (
    CalculationResult,
    Dataset,
    DatasetType,
    Methodology,
    Scenario,
    ScenarioStatus,
)
from core.services import CalculationService
from core.services.project_service import (
    SCHEMA_VERSION,
    ProjectService,
    ProjectServiceError,
)

SAMPLE_PROJECT = Path(__file__).resolve().parents[1] / "sample_project.hsp"


def make_dataset(name: str = "Пост 1", start: int = 1990, count: int = 5) -> Dataset:
    return Dataset(
        name=name,
        data={start + index: 100.0 + index * 2.0 for index in range(count)},
        dataset_type=DatasetType.OBSERVED,
    )


def make_result(dataset: Dataset | None = None) -> CalculationResult:
    calculation = CalculationService()
    calculation.register_handler(
        "demo@1.0", lambda context: {"Q": 1240.0, "n": context.dataset.length}
    )
    return calculation.execute(
        Methodology(name="demo", version="1.0"), dataset or make_dataset()
    )


def test_create_project_resets_state():
    service = ProjectService()
    service.add_dataset(make_dataset())
    service.set_parameters({"Cv": 0.3})

    project = service.create_project("Река X — расчёт максимального стока")

    assert project.name == "Река X — расчёт максимального стока"
    assert service.datasets == []
    assert service.parameters == {}
    assert service.path is None


def test_project_requires_name():
    with pytest.raises(ValueError):
        ProjectService().create_project("   ")


def test_save_requires_path():
    with pytest.raises(ProjectServiceError):
        ProjectService().save_project()

def test_save_and_open_roundtrip(tmp_path: Path):
    data_file = tmp_path / "data.xlsx"
    data_file.write_text("dummy", encoding="utf-8")

    service = ProjectService()
    service.create_project("Проект A", description="описание проекта")
    dataset = service.add_dataset(make_dataset())
    service.set_data_file(data_file)
    service.set_selected_post("Пост 1")
    service.set_region("central_russia")
    service.set_parameters({"Q_mean": 150.2, "Cv": 0.25, "Cs": 0.5})
    service.add_calculation(make_result(dataset))

    path = service.save_project(tmp_path / "project")

    assert path.suffix == ".hsp"
    assert path.exists()

    restored = ProjectService()
    restored.open_project(path)

    assert restored.project.name == "Проект A"
    assert restored.project.description == "описание проекта"
    assert restored.project.id == service.project.id
    assert restored.data_source == "data.xlsx"
    assert restored.data_path == str(data_file)
    assert restored.selected_post == "Пост 1"
    assert restored.region == "central_russia"
    assert restored.parameters == {"Q_mean": 150.2, "Cv": 0.25, "Cs": 0.5}
    assert len(restored.datasets) == 1
    assert restored.datasets[0].data == dataset.data
    assert len(restored.calculations) == 1
    assert restored.calculations[0].output_data["Q"] == 1240.0
    assert restored.calculations[0].methodology_name == "demo@1.0"
    assert restored.warnings == []


def test_saved_file_is_valid_json_without_temp_leftovers(tmp_path: Path):
    service = ProjectService()
    service.create_project("Проект B")
    path = service.save_project(tmp_path / "b.hsp")

    document = json.loads(path.read_text(encoding="utf-8"))

    assert document["schema_version"] == SCHEMA_VERSION
    assert document["title"] == "Проект B"
    assert document["datasets"] == []
    assert not (tmp_path / "b.hsp.tmp").exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_save_as_changes_project_path(tmp_path: Path):
    service = ProjectService()
    service.create_project("Проект C")

    first = service.save_project(tmp_path / "first")
    second = service.save_project(tmp_path / "second.hsp")

    assert first.name == "first.hsp"
    assert second.name == "second.hsp"
    assert service.path == second
    assert first.exists() and second.exists()


def test_open_missing_file_raises(tmp_path: Path):
    with pytest.raises(ProjectServiceError):
        ProjectService().open_project(tmp_path / "absent.hsp")


def test_open_invalid_json_raises(tmp_path: Path):
    broken = tmp_path / "broken.hsp"
    broken.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ProjectServiceError):
        ProjectService().open_project(broken)

    not_object = tmp_path / "list.hsp"
    not_object.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ProjectServiceError):
        ProjectService().open_project(not_object)

def test_minimal_file_is_opened_with_warning(tmp_path: Path):
    path = tmp_path / "minimal.hsp"
    path.write_text(json.dumps({"title": "Мини-проект"}, ensure_ascii=False), encoding="utf-8")

    service = ProjectService()
    project = service.open_project(path)

    assert project.name == "Мини-проект"
    assert service.datasets == []
    assert any("schema_version" in item for item in service.warnings)


def test_unsupported_schema_version_warns_but_loads(tmp_path: Path):
    path = tmp_path / "future.hsp"
    path.write_text(
        json.dumps({"schema_version": "9.9", "title": "Из будущего"}, ensure_ascii=False),
        encoding="utf-8",
    )

    service = ProjectService()
    service.open_project(path)

    assert service.project.name == "Из будущего"
    assert any("9.9" in item for item in service.warnings)


def test_unknown_sections_and_broken_entries_are_ignored(tmp_path: Path):
    document = {
        "schema_version": SCHEMA_VERSION,
        "title": "Странный проект",
        "unknown_section": {"a": 1},
        "datasets": [
            {"name": "Пост 1", "data": {"1990": 10.0, "1991": "нет"}},
            "не объект",
        ],
        "calculations": ["не объект"],
        "scenarios": ["не объект"],
        "reports": [{"type": "txt", "path": "out/report.txt"}, "не объект"],
    }
    path = tmp_path / "odd.hsp"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

    service = ProjectService()
    service.open_project(path)

    assert service.project.name == "Странный проект"
    assert len(service.datasets) == 2
    assert service.datasets[0].data == {1990: 10.0}
    assert service.datasets[1].name == "Набор данных"
    assert service.datasets[1].data == {}
    assert len(service.calculations) == 1
    assert len(service.scenarios) == 1
    assert len(service.to_document()["reports"]) == 1


def test_missing_data_file_and_post_produce_warnings(tmp_path: Path):
    path = tmp_path / "proj.hsp"
    path.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "title": "Проект с потерей файла",
                "data_path": str(tmp_path / "gone.xlsx"),
                "selected_post": "Пост 9",
                "datasets": [{"name": "Пост 1", "data": {"1990": 10.0}}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    service = ProjectService()
    service.open_project(path)

    assert any("Файл данных не найден" in item for item in service.warnings)
    assert any("Пост 9" in item for item in service.warnings)

def test_dataset_add_replace_and_remove():
    service = ProjectService()
    service.create_project("Проект D")
    service.add_dataset(make_dataset("Пост 1"))
    updated = make_dataset("Пост 1", start=1980, count=3)
    service.add_dataset(updated)

    assert len(service.datasets) == 1
    assert service.datasets[0].data == updated.data
    assert service.get_dataset("Пост 1").data == updated.data
    assert service.get_dataset(updated.id).name == "Пост 1"
    assert service.get_dataset("нет такого") is None

    assert service.remove_dataset("Пост 1") is True
    assert service.remove_dataset("Пост 1") is False
    assert service.datasets == []


def test_parameters_merge_and_replace():
    service = ProjectService()
    service.create_project("Проект E")

    service.set_parameters({"Cv": 0.25, "Cs": 0.5})
    service.set_parameters({"Q_mean": 150.2})

    assert service.parameters == {"Cv": 0.25, "Cs": 0.5, "Q_mean": 150.2}

    service.set_parameters({"Cv": 0.3}, merge=False)

    assert service.parameters == {"Cv": 0.3}


def test_scenarios_roundtrip(tmp_path: Path):
    service = ProjectService()
    service.create_project("Проект F")
    service.add_scenario(
        Scenario(
            name="Маловодный год",
            project_id=service.project.id,
            parameters={"demand": 350.0, "inflow": 420.0},
            description="сценарий засухи",
        )
    )

    path = service.save_project(tmp_path / "f.hsp")
    restored = ProjectService()
    restored.open_project(path)

    assert len(restored.scenarios) == 1
    loaded = restored.scenarios[0]
    assert loaded.name == "Маловодный год"
    assert loaded.parameters == {"demand": 350.0, "inflow": 420.0}
    assert loaded.project_id == service.project.id
    assert loaded.status is ScenarioStatus.DRAFT

    assert restored.remove_scenario(loaded.id) is True
    assert restored.remove_scenario(loaded.id) is False


def test_summary_contains_counts_and_years():
    service = ProjectService()
    service.create_project("Проект G")
    service.add_dataset(make_dataset("Пост 1", start=1990, count=5))
    service.add_dataset(make_dataset("Пост 2", start=1993, count=4))

    summary = service.summary()

    assert summary["title"] == "Проект G"
    assert summary["schema_version"] == SCHEMA_VERSION
    assert summary["dataset_count"] == 2
    assert summary["year_from"] == 1990
    assert summary["year_to"] == 1996
    assert summary["path"] == ""


def test_sample_project_file_opens():
    assert SAMPLE_PROJECT.exists(), "sample_project.hsp должен лежать в корне репозитория"

    service = ProjectService()
    service.open_project(SAMPLE_PROJECT)

    assert service.project.name == "Sample River Basin Analysis"
    assert service.data_source == "sample_data.xlsx"
    assert service.parameters["Q_mean"] == 150.2
    assert any("schema_version" in item for item in service.warnings)
