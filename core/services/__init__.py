"""
core/services/__init__.py
Service layer for the HydroSphere P0 architecture.

Services:
- CalculationService: Thin orchestration layer for calculations
- ValidationService: Unified validation interface
- MethodologyRegistry: Methodology identification, normative basis and applicability
- ScenarioService: Scenario management (CRUD, comparison, runs)
- ProjectService: Project persistence (.hsp) and the engineering project state

Services contain no mathematics: formulas stay in the calculation core
(`core.stats`, `core.hydrorash`).
"""

from .calculation_service import CalculationContext, CalculationError, CalculationService
from .methodology_registry import (
    DEFAULT_METHODOLOGIES,
    MethodologyDescriptor,
    MethodologyRegistry,
    build_default_registry,
)
from .project_service import (
    PROJECT_EXTENSION,
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    ProjectService,
    ProjectServiceError,
)
from .scenario_service import ScenarioNotFoundError, ScenarioService
from .validation_service import ValidationService

__all__ = [
    "DEFAULT_METHODOLOGIES",
    "PROJECT_EXTENSION",
    "SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "CalculationContext",
    "CalculationError",
    "CalculationService",
    "MethodologyDescriptor",
    "MethodologyRegistry",
    "ProjectService",
    "ProjectServiceError",
    "ScenarioNotFoundError",
    "ScenarioService",
    "ValidationService",
    "build_default_registry",
]
