"""
core/domain/models.py
Domain models for HydroSphere P0 architecture.

These models represent the core domain entities without any business logic.
They use standard library dataclasses and typing only.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class ProjectStatus(Enum):
    """Project lifecycle status."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    COMPLETED = "completed"


class DatasetType(Enum):
    """Type of hydrological dataset."""
    OBSERVED = "observed"           # Наблюдательный ряд
    CALCULATED = "calculated"       # Расчётный ряд
    SYNTHETIC = "synthetic"         # Синтетический ряд
    EXTENDED = "extended"           # Удлинённый ряд
    COMPOSITE = "composite"         # Составной ряд
    HISTORICAL = "historical"       # Исторические экстремумы


class CalculationStatus(Enum):
    """Calculation execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ValidationSeverity(Enum):
    """Validation issue severity."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ScenarioStatus(Enum):
    """Scenario status."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass
class Project:
    """
    Top-level project container.
    Aggregates datasets, scenarios, and calculations.
    """
    name: str
    description: str = ""
    status: ProjectStatus = ProjectStatus.DRAFT
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.name or not self.name.strip():
            raise ValueError("Project name cannot be empty")

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()


@dataclass
class Dataset:
    """
    Hydrological dataset with metadata.
    Represents a time series of hydrological observations or calculations.
    """
    name: str
    data: dict[int, float]  # year -> value mapping
    dataset_type: DatasetType = DatasetType.OBSERVED
    unit: str = "m³/s"
    location: str = ""
    catchment_area_km2: float | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.name or not self.name.strip():
            raise ValueError("Dataset name cannot be empty")
        if self.catchment_area_km2 is not None and self.catchment_area_km2 <= 0:
            raise ValueError("Catchment area must be positive")

    @property
    def years(self) -> list[int]:
        """Return sorted list of years."""
        return sorted(self.data.keys())

    @property
    def values(self) -> list[float]:
        """Return values sorted by year."""
        return [self.data[y] for y in self.years]

    @property
    def length(self) -> int:
        """Number of data points."""
        return len(self.data)

    @property
    def start_year(self) -> int | None:
        """First year in dataset."""
        return min(self.data.keys()) if self.data else None

    @property
    def end_year(self) -> int | None:
        """Last year in dataset."""
        return max(self.data.keys()) if self.data else None

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()

    def clone(self, name: str | None = None) -> Dataset:
        """Create a copy of this dataset with a new ID."""
        return Dataset(
            name=name or f"{self.name} (copy)",
            data=self.data.copy(),
            dataset_type=self.dataset_type,
            unit=self.unit,
            location=self.location,
            catchment_area_km2=self.catchment_area_km2,
            metadata=self.metadata.copy(),
        )


@dataclass
class Methodology:
    """
    Calculation methodology identification.
    Represents a specific calculation method with version.
    """
    name: str                    # e.g., "frequency_pearson3", "homogeneity_full"
    version: str                 # e.g., "1.0", "2024.1"
    standard: str | None = None  # e.g., "SP 33-101-2003", "GOST R 57205"
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self):
        if not self.name or not self.name.strip():
            raise ValueError("Methodology name cannot be empty")
        if not self.version or not self.version.strip():
            raise ValueError("Methodology version cannot be empty")

    @property
    def qualified_name(self) -> str:
        """Unique identifier combining name and version."""
        return f"{self.name}@{self.version}"

    def __hash__(self) -> int:
        return hash(self.qualified_name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Methodology):
            return NotImplemented
        return self.qualified_name == other.qualified_name


@dataclass
class CalculationMetadata:
    """
    Metadata for a calculation run.
    Tracks what was calculated, with what methodology, and when.
    """
    methodology: Methodology
    input_dataset_ids: list[UUID] = field(default_factory=list)
    input_parameters: dict[str, Any] = field(default_factory=dict)
    status: CalculationStatus = CalculationStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.now)

    def mark_running(self) -> None:
        """Mark calculation as running."""
        self.status = CalculationStatus.RUNNING
        self.started_at = datetime.now()

    def mark_completed(self) -> None:
        """Mark calculation as completed."""
        self.status = CalculationStatus.COMPLETED
        self.completed_at = datetime.now()

    def mark_failed(self, error: str) -> None:
        """Mark calculation as failed with error message."""
        self.status = CalculationStatus.FAILED
        self.completed_at = datetime.now()
        self.error_message = error

    @property
    def duration_seconds(self) -> float | None:
        """Calculation duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


@dataclass
class CalculationResult:
    """
    Results from a calculation.
    Contains the output data and reference to metadata.
    """
    metadata: CalculationMetadata
    output_data: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def is_successful(self) -> bool:
        """Check if calculation completed successfully."""
        return self.metadata.status == CalculationStatus.COMPLETED

    @property
    def methodology_name(self) -> str:
        """Get methodology qualified name."""
        return self.metadata.methodology.qualified_name


@dataclass
class Scenario:
    """
    Calculation scenario with parameters.
    Allows creating variations of calculations without modifying originals.
    """
    name: str
    project_id: UUID
    base_dataset_id: UUID | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    status: ScenarioStatus = ScenarioStatus.DRAFT
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    parent_scenario_id: UUID | None = None  # For cloning tracking

    def __post_init__(self):
        if not self.name or not self.name.strip():
            raise ValueError("Scenario name cannot be empty")

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()

    def with_parameters(self, **kwargs: Any) -> Scenario:
        """
        Create a new scenario with modified parameters.
        Does not modify the original scenario.
        """
        new_params = self.parameters.copy()
        new_params.update(kwargs)
        return Scenario(
            name=f"{self.name} (modified)",
            project_id=self.project_id,
            base_dataset_id=self.base_dataset_id,
            parameters=new_params,
            description=self.description,
            parent_scenario_id=self.id,
        )

    def clone(self, name: str | None = None) -> Scenario:
        """Create a copy of this scenario with a new ID."""
        return Scenario(
            name=name or f"{self.name} (copy)",
            project_id=self.project_id,
            base_dataset_id=self.base_dataset_id,
            parameters=self.parameters.copy(),
            description=self.description,
            status=ScenarioStatus.DRAFT,
        )


@dataclass
class ValidationIssue:
    """Single validation issue."""
    code: str
    message: str
    severity: ValidationSeverity
    field: str | None = None
    # NOTE: the attribute `field` above shadows `dataclasses.field` inside this class
    # body, so the fully qualified name must be used here.
    details: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclass
class ValidationResult:
    """
    Validation outcome for a calculation or dataset.
    """
    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    validated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def errors(self) -> list[ValidationIssue]:
        """Get all error-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Get all warning-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    @property
    def critical_issues(self) -> list[ValidationIssue]:
        """Get all critical issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.CRITICAL]

    def add_issue(self, code: str, message: str, severity: ValidationSeverity,
                  field: str | None = None, **details: Any) -> None:
        """Add a validation issue."""
        self.issues.append(ValidationIssue(
            code=code,
            message=message,
            severity=severity,
            field=field,
            details=details,
        ))
        if severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL):
            self.is_valid = False

    def merge(self, other: ValidationResult) -> ValidationResult:
        """Merge another validation result into this one."""
        merged = ValidationResult(
            is_valid=self.is_valid and other.is_valid,
            issues=self.issues + other.issues,
            metadata={**self.metadata, **other.metadata},
        )
        return merged


@dataclass
class DataQualityReport:
    """
    Data quality assessment report for a dataset.
    """
    dataset_id: UUID
    dataset_name: str
    n_points: int
    n_missing: int
    n_outliers: int
    homogeneity_passed: bool
    stationarity_passed: bool
    completeness_ratio: float  # 0.0 - 1.0
    quality_score: float       # 0.0 - 1.0
    issues: list[ValidationIssue] = field(default_factory=list)
    statistics: dict[str, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def quality_grade(self) -> str:
        """Letter grade for quality score."""
        if self.quality_score >= 0.9:
            return "A"
        elif self.quality_score >= 0.8:
            return "B"
        elif self.quality_score >= 0.7:
            return "C"
        elif self.quality_score >= 0.6:
            return "D"
        else:
            return "F"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "dataset_id": str(self.dataset_id),
            "dataset_name": self.dataset_name,
            "n_points": self.n_points,
            "n_missing": self.n_missing,
            "n_outliers": self.n_outliers,
            "homogeneity_passed": self.homogeneity_passed,
            "stationarity_passed": self.stationarity_passed,
            "completeness_ratio": round(self.completeness_ratio, 3),
            "quality_score": round(self.quality_score, 3),
            "quality_grade": self.quality_grade,
            "issues": [
                {
                    "code": i.code,
                    "message": i.message,
                    "severity": i.severity.value,
                    "field": i.field,
                    "details": i.details,
                }
                for i in self.issues
            ],
            "statistics": self.statistics,
            "created_at": self.created_at.isoformat(),
        }
