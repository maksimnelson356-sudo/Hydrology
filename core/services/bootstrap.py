"""
core/services/bootstrap.py
Single assembly point for the service layer (stage 3 of DOCS/ROADMAP.md).

build_container() registers methodology descriptors, calculation handlers and
applicability validators in one place, so the GUI and tools never wire services
by hand: methodology -> handler -> validator -> CalculationService.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.domain.models import ValidationResult, ValidationSeverity
from core.services.calculation_service import CalculationContext, CalculationService
from core.services.data_quality_service import DataQualityService
from core.services.handlers import HANDLERS
from core.services.methodology_registry import (
    MethodologyRegistry,
    build_default_registry,
)
from core.services.quality_pipeline import QualityPipeline
from core.services.result_store import ResultStore
from core.services.scenario_service import ScenarioService

__all__ = ["ServiceContainer", "build_container"]


@dataclass
class ServiceContainer:
    """Wired service layer: registry + calculation + quality + result store + scenario service."""

    registry: MethodologyRegistry
    calculation: CalculationService
    quality: DataQualityService
    results: ResultStore
    scenario: ScenarioService
    quality_pipeline: QualityPipeline | None = None

    def registered_methodology_ids(self) -> list[str]:
        """Ids that have both a descriptor and a calculation handler."""
        return [
            descriptor.id
            for descriptor in self.registry
            if self.calculation.has_handler(descriptor.qualified_name)
        ]


def build_container() -> ServiceContainer:
    """Build and wire the full service container (stage 3)."""
    registry = build_default_registry()
    calculation = CalculationService()

    # 1. Handlers: methodology id -> handler (qualified name = id@version).
    for methodology_id, handler in HANDLERS.items():
        if not registry.has(methodology_id):
            continue  # descriptor missing: methodology is not exposed yet
        descriptor = registry.get(methodology_id)
        calculation.register_handler(descriptor.qualified_name, handler)

        # 2. Applicability validator from the registry requirements.
        calculation.register_validator(
            descriptor.qualified_name,
            _make_validator(registry, methodology_id),
        )

    quality = DataQualityService(registry=registry)
    results = ResultStore()
    scenario_service = ScenarioService(calculation_service=calculation)
    return ServiceContainer(
        registry=registry,
        calculation=calculation,
        quality=quality,
        results=results,
        scenario=scenario_service,
        quality_pipeline=QualityPipeline(quality=quality),
    )


def _make_validator(registry: MethodologyRegistry, methodology_id: str):
    """Build a pre-calculation validator bound to a methodology descriptor."""

    def validate(context: CalculationContext) -> ValidationResult:
        result = ValidationResult(is_valid=True)
        descriptor = registry.get(methodology_id)
        dataset = context.dataset

        # Minimum series length (with the normative reference).
        if descriptor.min_points and dataset.length < descriptor.min_points:
            result.add_issue(
                code="METHODOLOGY_MIN_POINTS",
                message=(
                    f"Методика «{descriptor.name}» требует ряд не короче "
                    f"{descriptor.min_points} лет (получено {dataset.length}); "
                    f"{descriptor.normative_reference}"
                ),
                severity=ValidationSeverity.ERROR,
                field="data",
                details={"required": descriptor.min_points, "actual": dataset.length},
            )

        # Required parameters.
        if descriptor.required_parameters:
            missing = [
                name for name in descriptor.required_parameters
                if name not in (context.parameters or {})
            ]
            if missing:
                result.add_issue(
                    code="MISSING_PARAMETER",
                    message=(
                        f"Не заданы обязательные параметры: {', '.join(missing)} "
                        f"(методика «{descriptor.name}»)"
                    ),
                    severity=ValidationSeverity.ERROR,
                    field="parameters",
                    details={"missing": missing},
                )

        return result

    return validate
