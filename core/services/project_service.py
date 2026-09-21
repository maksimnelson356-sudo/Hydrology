"""
core/services/project_service.py
Project file (.hsp) persistence for the HydroSphere P0 architecture.

The service is the single owner of the engineering project state: datasets,
parameters, the selected post, the path of the source data file, calculation
results and scenarios. The file format is documented in DOCS/hsp_schema.md.

Parsing is tolerant by design: missing sections fall back to defaults, unknown
keys are ignored and a schema version mismatch is reported as a warning - a
project must never be lost because of one unexpected key.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID

from core.domain.models import CalculationResult, Dataset, Project, Scenario
from core.domain.serialization import (
    calculation_result_from_dict,
    calculation_result_to_dict,
    dataset_from_dict,
    dataset_to_dict,
    project_from_dict,
    scenario_from_dict,
    scenario_to_dict,
    to_json_safe,
)

SCHEMA_VERSION = "1.0"
SUPPORTED_SCHEMA_VERSIONS = (SCHEMA_VERSION,)
PROJECT_EXTENSION = ".hsp"


class ProjectServiceError(Exception):
    """Raised when a project file cannot be read or written."""


class ProjectService:
    """In-memory engineering project with tolerant `.hsp` persistence."""

    def __init__(self, project: Project | None = None) -> None:
        self._project: Project = project or Project(name="Новый проект")
        self._datasets: list[Dataset] = []
        self._calculations: list[CalculationResult] = []
        self._scenarios: list[Scenario] = []
        self._reports: list[dict[str, Any]] = []
        self._parameters: dict[str, Any] = {}
        self._data_source: str = ""
        self._data_path: str = ""
        self._selected_post: str = ""
        self._region: str | None = None
        self._path: Path | None = None
        self._warnings: list[str] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def project(self) -> Project:
        """The domain project entity."""
        return self._project

    @property
    def path(self) -> Path | None:
        """Path of the project file, if it was saved or opened."""
        return self._path

    @property
    def warnings(self) -> list[str]:
        """Warnings collected while parsing a project file."""
        return list(self._warnings)

    @property
    def datasets(self) -> list[Dataset]:
        """Datasets stored in the project."""
        return list(self._datasets)

    @property
    def calculations(self) -> list[CalculationResult]:
        """Calculation results stored in the project."""
        return list(self._calculations)

    @property
    def scenarios(self) -> list[Scenario]:
        """Scenarios stored in the project."""
        return list(self._scenarios)

    @property
    def parameters(self) -> dict[str, Any]:
        """Project-level parameters (Qср, Cv, Cs, ...)."""
        return dict(self._parameters)

    @property
    def data_source(self) -> str:
        """Name of the source data file."""
        return self._data_source

    @property
    def data_path(self) -> str:
        """Path of the source data file."""
        return self._data_path

    @property
    def selected_post(self) -> str:
        """Post selected in the project."""
        return self._selected_post

    @property
    def region(self) -> str | None:
        """Region key (see core/hydrorash/regional_regressions.py)."""
        return self._region
    # ------------------------------------------------------------------
    # Creation and persistence
    # ------------------------------------------------------------------
    def create_project(
        self,
        name: str,
        description: str = "",
        path: str | Path | None = None,
    ) -> Project:
        """Start a new empty project, discarding the current state."""
        self._project = Project(name=name, description=description)
        self._datasets = []
        self._calculations = []
        self._scenarios = []
        self._reports = []
        self._parameters = {}
        self._data_source = ""
        self._data_path = ""
        self._selected_post = ""
        self._region = None
        self._warnings = []
        self._path = Path(path) if path is not None else None
        return self._project

    def open_project(self, path: str | Path) -> Project:
        """
        Load a project from a `.hsp` file into this service.

        Raises:
            ProjectServiceError: when the file is missing, unreadable or is not a
                JSON object.
        """
        resolved = Path(path)
        if not resolved.exists():
            raise ProjectServiceError(f"Файл проекта не найден: {resolved}")
        try:
            with resolved.open(encoding="utf-8") as handle:
                document = json.load(handle)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ProjectServiceError(f"Не удалось прочитать проект: {error}") from error
        if not isinstance(document, dict):
            raise ProjectServiceError("Файл проекта повреждён: ожидался JSON-объект")
        self.from_document(document)
        self._path = resolved
        return self._project

    def save_project(self, path: str | Path | None = None) -> Path:
        """
        Save the project to a `.hsp` file (written atomically via a temp file).

        Raises:
            ProjectServiceError: when no path is known or the file cannot be written.
        """
        target = Path(path) if path is not None else self._path
        if target is None:
            raise ProjectServiceError("Не задан путь для сохранения проекта")
        if not target.suffix:
            target = target.with_suffix(PROJECT_EXTENSION)

        self._project.touch()
        document = self.to_document()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_name(target.name + ".tmp")
            with temp.open("w", encoding="utf-8") as handle:
                json.dump(document, handle, ensure_ascii=False, indent=2)
            os.replace(temp, target)
        except OSError as error:
            raise ProjectServiceError(f"Не удалось сохранить проект: {error}") from error
        self._path = target
        return target

    @classmethod
    def from_file(cls, path: str | Path) -> ProjectService:
        """Open a project file and return a ready-to-use service instance."""
        service = cls()
        service.open_project(path)
        return service

    # ------------------------------------------------------------------
    # Document (schema 1.0)
    # ------------------------------------------------------------------
    def to_document(self) -> dict[str, Any]:
        """Build the JSON-compatible project document."""
        return {
            "schema_version": SCHEMA_VERSION,
            "title": self._project.name,
            "description": self._project.description,
            "status": self._project.status.value,
            "project_id": str(self._project.id),
            "created_at": self._project.created_at.isoformat(),
            "updated_at": self._project.updated_at.isoformat(),
            "data_source": self._data_source,
            "data_path": self._data_path,
            "selected_post": self._selected_post,
            "region": self._region,
            "parameters": to_json_safe(self._parameters),
            "metadata": to_json_safe(self._project.metadata),
            "datasets": [dataset_to_dict(item) for item in self._datasets],
            "calculations": [calculation_result_to_dict(item) for item in self._calculations],
            "scenarios": [scenario_to_dict(item) for item in self._scenarios],
            "reports": [to_json_safe(item) for item in self._reports],
        }
    def from_document(self, document: dict[str, Any]) -> Project:
        """
        Load state from a project document (tolerant; fills `self.warnings`).

        Raises:
            ProjectServiceError: when the document is not a mapping.
        """
        if not isinstance(document, dict):
            raise ProjectServiceError("Документ проекта должен быть объектом JSON")
        self._warnings = []

        version = document.get("schema_version")
        if version is None:
            self._warnings.append(
                f"В файле нет schema_version — принята версия {SCHEMA_VERSION}"
            )
        elif str(version) not in SUPPORTED_SCHEMA_VERSIONS:
            self._warnings.append(
                f"Версия схемы {version} не поддерживается (ожидается "
                f"{', '.join(SUPPORTED_SCHEMA_VERSIONS)}) — данные прочитаны как есть"
            )

        self._project = project_from_dict(
            {
                "id": document.get("project_id"),
                "name": document.get("title"),
                "description": document.get("description"),
                "status": document.get("status"),
                "created_at": document.get("created_at"),
                "updated_at": document.get("updated_at"),
                "metadata": document.get("metadata"),
            }
        )
        self._parameters = dict(document.get("parameters") or {})
        self._region = str(document["region"]) if document.get("region") else None
        self._data_source = str(document.get("data_source") or "")
        self._data_path = str(document.get("data_path") or "")
        self._selected_post = str(document.get("selected_post") or "")

        self._datasets = []
        for index, raw in enumerate(document.get("datasets") or []):
            try:
                self._datasets.append(dataset_from_dict(raw))
            except (ValueError, TypeError) as error:
                self._warnings.append(f"Набор данных #{index + 1} пропущен: {error}")

        self._calculations = []
        for index, raw in enumerate(document.get("calculations") or []):
            try:
                self._calculations.append(calculation_result_from_dict(raw))
            except (ValueError, TypeError) as error:
                self._warnings.append(f"Расчёт #{index + 1} пропущен: {error}")

        self._scenarios = []
        for index, raw in enumerate(document.get("scenarios") or []):
            try:
                self._scenarios.append(scenario_from_dict(raw, project_id=self._project.id))
            except (ValueError, TypeError) as error:
                self._warnings.append(f"Сценарий #{index + 1} пропущен: {error}")

        self._reports = [dict(item) for item in document.get("reports") or [] if isinstance(item, dict)]

        names = {item.name for item in self._datasets}
        if self._selected_post and names and self._selected_post not in names:
            self._warnings.append(
                f"Выбранный пост «{self._selected_post}» отсутствует среди наборов данных"
            )
        if self._data_path and not os.path.exists(self._data_path):
            self._warnings.append(f"Файл данных не найден: {self._data_path}")

        return self._project
    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def add_dataset(self, dataset: Dataset) -> Dataset:
        """Add a dataset; a dataset with the same name or id is replaced."""
        for index, existing in enumerate(self._datasets):
            if existing.name == dataset.name or existing.id == dataset.id:
                self._datasets[index] = dataset
                self._project.touch()
                return dataset
        self._datasets.append(dataset)
        self._project.touch()
        return dataset

    def get_dataset(self, reference: UUID | str) -> Dataset | None:
        """Find a dataset by id or by name; returns None when it is absent."""
        if isinstance(reference, UUID):
            return next((item for item in self._datasets if item.id == reference), None)
        return next((item for item in self._datasets if item.name == str(reference)), None)

    def remove_dataset(self, reference: UUID | str) -> bool:
        """Remove a dataset by id or name; returns True when something was removed."""
        dataset = self.get_dataset(reference)
        if dataset is None:
            return False
        self._datasets.remove(dataset)
        self._project.touch()
        return True

    def set_data_file(self, path: str | Path, source_name: str | None = None) -> None:
        """Remember the source data file of the project."""
        resolved = Path(path)
        self._data_path = str(resolved)
        self._data_source = source_name or resolved.name
        self._project.touch()

    def set_selected_post(self, post_name: str) -> None:
        """Remember the selected post."""
        self._selected_post = str(post_name or "")
        self._project.touch()

    def set_region(self, region: str | None) -> None:
        """Remember the region key."""
        self._region = str(region) if region else None
        self._project.touch()

    def set_parameters(self, parameters: dict[str, Any], merge: bool = True) -> None:
        """Set (or merge) project-level parameters such as Qср, Cv, Cs."""
        if merge:
            self._parameters.update(parameters)
        else:
            self._parameters = dict(parameters)
        self._project.touch()

    def add_calculation(self, result: CalculationResult) -> CalculationResult:
        """Store a calculation result in the project (used from stage 4 on)."""
        self._calculations.append(result)
        self._project.touch()
        return result

    def add_scenario(self, scenario: Scenario) -> Scenario:
        """Store a scenario in the project, replacing a scenario with the same id."""
        for index, existing in enumerate(self._scenarios):
            if existing.id == scenario.id:
                self._scenarios[index] = scenario
                self._project.touch()
                return scenario
        self._scenarios.append(scenario)
        self._project.touch()
        return scenario

    def remove_scenario(self, scenario_id: UUID) -> bool:
        """Remove a scenario by id; returns True when something was removed."""
        for index, existing in enumerate(self._scenarios):
            if existing.id == scenario_id:
                del self._scenarios[index]
                self._project.touch()
                return True
        return False

    def register_report(self, report: dict[str, Any]) -> dict[str, Any]:
        """Register a generated report (type/path pair, see DOCS/hsp_schema.md)."""
        entry = dict(report)
        self._reports.append(entry)
        self._project.touch()
        return entry

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def summary(self) -> dict[str, Any]:
        """Compact project description for the GUI panel and for logs."""
        years: list[int] = []
        for dataset in self._datasets:
            years.extend(dataset.years)
        return {
            "title": self._project.name,
            "description": self._project.description,
            "status": self._project.status.value,
            "path": str(self._path) if self._path else "",
            "schema_version": SCHEMA_VERSION,
            "data_source": self._data_source,
            "data_path": self._data_path,
            "selected_post": self._selected_post,
            "region": self._region,
            "dataset_count": len(self._datasets),
            "calculation_count": len(self._calculations),
            "scenario_count": len(self._scenarios),
            "report_count": len(self._reports),
            "year_from": min(years) if years else None,
            "year_to": max(years) if years else None,
            "created_at": self._project.created_at.isoformat(),
            "updated_at": self._project.updated_at.isoformat(),
            "warnings": self.warnings,
        }
