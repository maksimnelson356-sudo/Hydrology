"""
core/domain/serialization.py
Serialization helpers for HydroSphere domain entities.

Every entity can be converted into a JSON-compatible structure and restored back.
UUIDs, datetimes and Enums are handled explicitly. Unknown keys are ignored and
missing keys fall back to model defaults, so an older project file never fails to
open (tolerant parsing, see DOCS/hsp_schema.md).

Used by `core.services.project_service` for storing the engineering project.
"""

from __future__ import annotations

import math
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from .models import (
    CalculationMetadata,
    CalculationResult,
    CalculationStatus,
    DataQualityReport,
    Dataset,
    DatasetType,
    Methodology,
    Project,
    ProjectStatus,
    Scenario,
    ScenarioStatus,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)


# ----------------------------------------------------------------------
# Scalar helpers
# ----------------------------------------------------------------------
def uuid_to_str(value: UUID | None) -> str | None:
    """Serialize a UUID to its string form."""
    return str(value) if value is not None else None


def parse_uuid(value: Any, default: UUID | None = None) -> UUID | None:
    """Parse a UUID from a string; return `default` when it cannot be parsed."""
    if value is None:
        return default
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return default


def datetime_to_iso(value: datetime | None) -> str | None:
    """Serialize a datetime to ISO 8601."""
    return value.isoformat() if value is not None else None


def parse_datetime(value: Any, default: datetime | None = None) -> datetime | None:
    """Parse an ISO 8601 datetime; return `default` when it cannot be parsed."""
    if value is None:
        return default
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return default


def parse_enum[E: Enum](enum_cls: type[E], value: Any, default: E) -> E:
    """Parse an enum member by its value; return `default` when it is unknown."""
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except (ValueError, TypeError):
        return default

def to_json_safe(value: Any) -> Any:
    """
    Convert an arbitrary value into something JSON can store.

    Lists, tuples, dicts, scalars, UUIDs, datetimes and Enums are converted
    recursively; non-finite floats become None (NaN is not valid JSON). Anything
    else is stored as its string representation - the project file must never fail
    to save because of one exotic object.
    """
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, int):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_json_safe(item) for item in value]
    if hasattr(value, "item"):  # numpy scalars
        try:
            return to_json_safe(value.item())
        except (ValueError, TypeError):
            pass
    if hasattr(value, "tolist"):  # numpy arrays, pandas objects
        try:
            return to_json_safe(value.tolist())
        except (ValueError, TypeError):
            pass
    return str(value)


def data_to_dict(data: dict[int, float]) -> dict[str, float]:
    """Serialize a year -> value mapping with string keys (JSON requirement)."""
    result: dict[str, float] = {}
    for year, value in data.items():
        try:
            result[str(int(year))] = float(value)
        except (ValueError, TypeError):
            continue
    return result


def data_from_dict(raw: Any) -> dict[int, float]:
    """Restore a year -> value mapping, skipping unusable entries."""
    result: dict[int, float] = {}
    if not isinstance(raw, dict):
        return result
    for year, value in raw.items():
        try:
            result[int(float(year))] = float(value)
        except (ValueError, TypeError):
            continue
    return result


# ----------------------------------------------------------------------
# Entities
# ----------------------------------------------------------------------
def project_to_dict(project: Project) -> dict[str, Any]:
    """Serialize a Project entity."""
    return {
        "id": uuid_to_str(project.id),
        "name": project.name,
        "description": project.description,
        "status": project.status.value,
        "created_at": datetime_to_iso(project.created_at),
        "updated_at": datetime_to_iso(project.updated_at),
        "metadata": to_json_safe(project.metadata),
    }


def project_from_dict(raw: Any, default_name: str = "Проект") -> Project:
    """Restore a Project entity from a dict (tolerant)."""
    data = raw if isinstance(raw, dict) else {}
    name = str(data.get("name") or default_name)
    project = Project(
        name=name,
        description=str(data.get("description") or ""),
        status=parse_enum(ProjectStatus, data.get("status"), ProjectStatus.DRAFT),
        metadata=dict(data.get("metadata") or {}),
    )
    parsed_id = parse_uuid(data.get("id"))
    if parsed_id is not None:
        project.id = parsed_id
    created = parse_datetime(data.get("created_at"))
    if created is not None:
        project.created_at = created
    updated = parse_datetime(data.get("updated_at"))
    if updated is not None:
        project.updated_at = updated
    return project

def dataset_to_dict(dataset: Dataset) -> dict[str, Any]:
    """Serialize a Dataset entity (data as a year -> value mapping)."""
    return {
        "id": uuid_to_str(dataset.id),
        "name": dataset.name,
        "dataset_type": dataset.dataset_type.value,
        "unit": dataset.unit,
        "location": dataset.location,
        "catchment_area_km2": dataset.catchment_area_km2,
        "created_at": datetime_to_iso(dataset.created_at),
        "updated_at": datetime_to_iso(dataset.updated_at),
        "metadata": to_json_safe(dataset.metadata),
        "data": data_to_dict(dataset.data),
    }


def dataset_from_dict(raw: Any, default_name: str = "Набор данных") -> Dataset:
    """Restore a Dataset entity from a dict (tolerant)."""
    data = raw if isinstance(raw, dict) else {}

    area_value: float | None = None
    try:
        if data.get("catchment_area_km2") is not None:
            area_value = float(data["catchment_area_km2"])
    except (ValueError, TypeError):
        area_value = None
    if area_value is not None and area_value <= 0:
        area_value = None

    dataset = Dataset(
        name=str(data.get("name") or default_name),
        data=data_from_dict(data.get("data")),
        dataset_type=parse_enum(DatasetType, data.get("dataset_type"), DatasetType.OBSERVED),
        unit=str(data.get("unit") or "м³/с"),
        location=str(data.get("location") or ""),
        catchment_area_km2=area_value,
        metadata=dict(data.get("metadata") or {}),
    )
    parsed_id = parse_uuid(data.get("id"))
    if parsed_id is not None:
        dataset.id = parsed_id
    for field_name, attribute in (("created_at", "created_at"), ("updated_at", "updated_at")):
        parsed = parse_datetime(data.get(field_name))
        if parsed is not None:
            setattr(dataset, attribute, parsed)
    return dataset


def methodology_to_dict(methodology: Methodology) -> dict[str, Any]:
    """Serialize a Methodology entity."""
    return {
        "id": uuid_to_str(methodology.id),
        "name": methodology.name,
        "version": methodology.version,
        "standard": methodology.standard,
        "description": methodology.description,
        "parameters": to_json_safe(methodology.parameters),
    }


def methodology_from_dict(raw: Any) -> Methodology:
    """Restore a Methodology entity from a dict (tolerant)."""
    data = raw if isinstance(raw, dict) else {}
    methodology = Methodology(
        name=str(data.get("name") or "unknown_methodology"),
        version=str(data.get("version") or "1.0"),
        standard=str(data["standard"]) if data.get("standard") else None,
        description=str(data.get("description") or ""),
        parameters=dict(data.get("parameters") or {}),
    )
    parsed_id = parse_uuid(data.get("id"))
    if parsed_id is not None:
        methodology.id = parsed_id
    return methodology

def calculation_metadata_to_dict(metadata: CalculationMetadata) -> dict[str, Any]:
    """Serialize CalculationMetadata (methodology, inputs, status, timing)."""
    return {
        "id": uuid_to_str(metadata.id),
        "methodology": methodology_to_dict(metadata.methodology),
        "input_dataset_ids": [uuid_to_str(item) for item in metadata.input_dataset_ids],
        "input_parameters": to_json_safe(metadata.input_parameters),
        "status": metadata.status.value,
        "started_at": datetime_to_iso(metadata.started_at),
        "completed_at": datetime_to_iso(metadata.completed_at),
        "error_message": metadata.error_message,
        "created_at": datetime_to_iso(metadata.created_at),
    }


def calculation_metadata_from_dict(raw: Any) -> CalculationMetadata:
    """Restore CalculationMetadata from a dict (tolerant)."""
    data = raw if isinstance(raw, dict) else {}
    metadata = CalculationMetadata(
        methodology=methodology_from_dict(data.get("methodology")),
        input_dataset_ids=[
            parsed
            for parsed in (parse_uuid(item) for item in data.get("input_dataset_ids") or [])
            if parsed is not None
        ],
        input_parameters=dict(data.get("input_parameters") or {}),
        status=parse_enum(CalculationStatus, data.get("status"), CalculationStatus.PENDING),
        started_at=parse_datetime(data.get("started_at")),
        completed_at=parse_datetime(data.get("completed_at")),
        error_message=str(data["error_message"]) if data.get("error_message") else None,
    )
    parsed_id = parse_uuid(data.get("id"))
    if parsed_id is not None:
        metadata.id = parsed_id
    created = parse_datetime(data.get("created_at"))
    if created is not None:
        metadata.created_at = created
    return metadata


def calculation_result_to_dict(result: CalculationResult) -> dict[str, Any]:
    """Serialize a CalculationResult (metadata + output values)."""
    return {
        "id": uuid_to_str(result.id),
        "metadata": calculation_metadata_to_dict(result.metadata),
        "output_data": to_json_safe(result.output_data),
        "warnings": [str(item) for item in result.warnings],
        "created_at": datetime_to_iso(result.created_at),
    }


def calculation_result_from_dict(raw: Any) -> CalculationResult:
    """Restore a CalculationResult from a dict (tolerant)."""
    data = raw if isinstance(raw, dict) else {}
    result = CalculationResult(
        metadata=calculation_metadata_from_dict(data.get("metadata")),
        output_data=dict(data.get("output_data") or {}),
        warnings=[str(item) for item in data.get("warnings") or []],
    )
    parsed_id = parse_uuid(data.get("id"))
    if parsed_id is not None:
        result.id = parsed_id
    created = parse_datetime(data.get("created_at"))
    if created is not None:
        result.created_at = created
    return result

def _as_int(value: Any, default: int = 0) -> int:
    """Convert a value to int, returning `default` when it is unusable."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    """Convert a value to float, returning `default` when it is unusable."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _as_bool(value: Any, default: bool = False) -> bool:
    """Convert a value to bool, returning `default` for anything unrecognised."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "да"}
    return default


def scenario_to_dict(scenario: Scenario) -> dict[str, Any]:
    """Serialize a Scenario entity."""
    return {
        "id": uuid_to_str(scenario.id),
        "name": scenario.name,
        "project_id": uuid_to_str(scenario.project_id),
        "base_dataset_id": uuid_to_str(scenario.base_dataset_id),
        "parent_scenario_id": uuid_to_str(scenario.parent_scenario_id),
        "parameters": to_json_safe(scenario.parameters),
        "description": scenario.description,
        "status": scenario.status.value,
        "scenario_type": scenario.scenario_type,
        "created_at": datetime_to_iso(scenario.created_at),
        "updated_at": datetime_to_iso(scenario.updated_at),
    }


def scenario_from_dict(raw: Any, project_id: UUID | None = None) -> Scenario:
    """
    Restore a Scenario entity from a dict (tolerant).

    Raises:
        ValueError: when neither the dict nor the caller provides a project id.
    """
    data = raw if isinstance(raw, dict) else {}
    resolved_project = parse_uuid(data.get("project_id"), project_id)
    if resolved_project is None:
        raise ValueError("Scenario project_id is required")

    scenario = Scenario(
        name=str(data.get("name") or "Сценарий"),
        project_id=resolved_project,
        base_dataset_id=parse_uuid(data.get("base_dataset_id")),
        parameters=dict(data.get("parameters") or {}),
        description=str(data.get("description") or ""),
        status=parse_enum(ScenarioStatus, data.get("status"), ScenarioStatus.DRAFT),
        scenario_type=str(data.get("scenario_type") or "generic"),
        parent_scenario_id=parse_uuid(data.get("parent_scenario_id")),
    )
    parsed_id = parse_uuid(data.get("id"))
    if parsed_id is not None:
        scenario.id = parsed_id
    for key, attribute in (("created_at", "created_at"), ("updated_at", "updated_at")):
        parsed = parse_datetime(data.get(key))
        if parsed is not None:
            setattr(scenario, attribute, parsed)
    return scenario

def validation_issue_to_dict(issue: ValidationIssue) -> dict[str, Any]:
    """Serialize a single ValidationIssue."""
    return {
        "code": issue.code,
        "message": issue.message,
        "severity": issue.severity.value,
        "field": issue.field,
        "details": to_json_safe(issue.details),
    }


def validation_issue_from_dict(raw: Any) -> ValidationIssue:
    """Restore a ValidationIssue from a dict (tolerant)."""
    data = raw if isinstance(raw, dict) else {}
    return ValidationIssue(
        code=str(data.get("code") or "UNKNOWN"),
        message=str(data.get("message") or ""),
        severity=parse_enum(ValidationSeverity, data.get("severity"), ValidationSeverity.INFO),
        field=str(data["field"]) if data.get("field") else None,
        details=dict(data.get("details") or {}),
    )


def validation_result_to_dict(result: ValidationResult) -> dict[str, Any]:
    """Serialize a ValidationResult."""
    return {
        "is_valid": result.is_valid,
        "issues": [validation_issue_to_dict(item) for item in result.issues],
        "validated_at": datetime_to_iso(result.validated_at),
        "metadata": to_json_safe(result.metadata),
    }


def validation_result_from_dict(raw: Any) -> ValidationResult:
    """Restore a ValidationResult from a dict (tolerant)."""
    data = raw if isinstance(raw, dict) else {}
    result = ValidationResult(
        is_valid=_as_bool(data.get("is_valid"), True),
        issues=[validation_issue_from_dict(item) for item in data.get("issues") or []],
        metadata=dict(data.get("metadata") or {}),
    )
    validated = parse_datetime(data.get("validated_at"))
    if validated is not None:
        result.validated_at = validated
    return result


def data_quality_report_to_dict(report: DataQualityReport) -> dict[str, Any]:
    """Serialize a DataQualityReport (reuses the to_dict() defined on the model)."""
    return report.to_dict()


def data_quality_report_from_dict(raw: Any) -> DataQualityReport:
    """Restore a DataQualityReport from a dict (tolerant)."""
    data = raw if isinstance(raw, dict) else {}
    report = DataQualityReport(
        dataset_id=parse_uuid(data.get("dataset_id")) or uuid4(),
        dataset_name=str(data.get("dataset_name") or ""),
        n_points=_as_int(data.get("n_points")),
        n_missing=_as_int(data.get("n_missing")),
        n_outliers=_as_int(data.get("n_outliers")),
        homogeneity_passed=_as_bool(data.get("homogeneity_passed"), True),
        stationarity_passed=_as_bool(data.get("stationarity_passed"), True),
        completeness_ratio=_as_float(data.get("completeness_ratio")),
        quality_score=_as_float(data.get("quality_score")),
        issues=[validation_issue_from_dict(item) for item in data.get("issues") or []],
        statistics=dict(data.get("statistics") or {}),
    )
    created = parse_datetime(data.get("created_at"))
    if created is not None:
        report.created_at = created
    return report


__all__ = [
    "calculation_metadata_from_dict",
    "calculation_metadata_to_dict",
    "calculation_result_from_dict",
    "calculation_result_to_dict",
    "data_from_dict",
    "data_quality_report_from_dict",
    "data_quality_report_to_dict",
    "data_to_dict",
    "dataset_from_dict",
    "dataset_to_dict",
    "datetime_to_iso",
    "methodology_from_dict",
    "methodology_to_dict",
    "parse_datetime",
    "parse_enum",
    "parse_uuid",
    "project_from_dict",
    "project_to_dict",
    "scenario_from_dict",
    "scenario_to_dict",
    "to_json_safe",
    "uuid_to_str",
    "validation_issue_from_dict",
    "validation_issue_to_dict",
    "validation_result_from_dict",
    "validation_result_to_dict",
]
