"""
core/domain/__init__.py
Domain models for HydroSphere P0 architecture.

Entities:
- Project: Top-level project container
- Dataset: Hydrological dataset with metadata
- Methodology: Calculation methodology identification
- CalculationMetadata: Metadata for calculation runs
- CalculationResult: Results from calculations
- Scenario: Calculation scenario with parameters
- ValidationIssue / ValidationResult: Validation outcomes
- DataQualityReport: Data quality assessment

Enumerations:
- ProjectStatus, DatasetType, CalculationStatus, ValidationSeverity, ScenarioStatus
"""

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

__all__ = [
    "CalculationMetadata",
    "CalculationResult",
    "CalculationStatus",
    "DataQualityReport",
    "Dataset",
    "DatasetType",
    "Methodology",
    "Project",
    "ProjectStatus",
    "Scenario",
    "ScenarioStatus",
    "ValidationIssue",
    "ValidationResult",
    "ValidationSeverity",
]
