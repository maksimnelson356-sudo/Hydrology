"""
core/services/__init__.py
Service layer for the HydroSphere P0 architecture.

Services:
- CalculationService: Thin orchestration layer for calculations
- ValidationService: Unified validation interface
- MethodologyRegistry: Methodology identification, normative basis and applicability
- ScenarioService: Scenario management (CRUD, comparison, runs)
- ProjectService: Project persistence (.hsp) and the engineering project state
- ImportService: CSV/TSV/Excel time series import into Dataset (P1.1)
- CalibrationService: scipy.optimize parameter fitting with metrics (P1.5)
- ReservoirScenarioService: multi-year regulation as scenario runs (P1.7)
- GeoService: GeoJSON basin contour morphometry (P1.6, decision 9.3 = (b))
- MonteCarloService: uncertainty propagation with seedable sampling (P2.1)
- SensitivityService: one-at-a-time tornado ranking (P2.2)
- ClimateService: multiplicative/additive delta-change on series (P2.3)
- DecisionSupportService: P(exceed) + risk class on user Q_крит (P2.5, 10.3 (a))
- BackwaterProfileService: multi-reach chained backwater profiles (P3.1)
- RoutingService: Muskingum flood routing with peak metrics (P3.2)
- InundationService: water-level to flooded area/volume estimates (P3.3)

Services contain no mathematics: formulas stay in the calculation core
(`core.stats`, `core.hydrorash`).
"""

from .api_source import ApiSourceError, DataSource, FieldMap, HttpApiSource
from .backwater_profile_service import (
    BACKWATER_PROFILE_PROVENANCE,
    BackwaterProfileError,
    BackwaterProfileRequest,
    BackwaterProfileResult,
    BackwaterProfileService,
    ReachSpec,
)
from .bootstrap import ServiceContainer, build_container
from .calculation_service import CalculationContext, CalculationError, CalculationService
from .calibration_service import (
    AVAILABLE_METRICS,
    CalibrationError,
    CalibrationRequest,
    CalibrationService,
)
from .climate_service import (
    CLIMATE_MODES,
    ClimateError,
    ClimateScenario,
    ClimateService,
)
from .data_quality_service import RECOMMENDATIONS, DataQualityService
from .decision_support_service import (
    DEFAULT_RISK_CUTOFFS,
    RISK_CLASSES,
    DecisionSupportError,
    DecisionSupportRequest,
    DecisionSupportResult,
    DecisionSupportService,
    ThresholdAssessment,
)
from .geo_service import BasinMorphometry, GeoService, GeoServiceError
from .hydraulic_uncertainty_service import (
    HYDRAULIC_UNCERTAINTY_PROVENANCE,
    BackwaterMonteCarloBaseline,
    HydraulicBaseline,
    HydraulicUncertaintyError,
    HydraulicUncertaintyRequest,
    HydraulicUncertaintyResult,
    HydraulicUncertaintyService,
    RoutingMonteCarloBaseline,
)
from .import_service import ColumnMapping, ImportPreview, ImportService, ImportServiceError
from .inundation_service import (
    INUNDATION_PROVENANCE,
    GeoJsonSource,
    InundationError,
    InundationRequest,
    InundationResult,
    InundationService,
    StageAreaSource,
    TrapezoidSource,
)
from .methodology_registry import (
    DEFAULT_METHODOLOGIES,
    MethodologyDescriptor,
    MethodologyRegistry,
    build_default_registry,
)
from .monte_carlo_service import (
    DEFAULT_N_RUNS,
    DISTRIBUTIONS,
    MonteCarloError,
    MonteCarloRequest,
    MonteCarloService,
    ParameterSpec,
    SummaryStats,
)
from .project_service import (
    PROJECT_EXTENSION,
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    ProjectService,
    ProjectServiceError,
)
from .quality_pipeline import QualityGateDecision, QualityPipeline, QualityPipelineResult
from .report_service import Report, ReportSection, ReportService
from .reservoir_scenario_service import (
    RESERVOIR_METHODOLOGY,
    RESERVOIR_SCENARIO_TYPE,
    ReservoirScenarioError,
    ReservoirScenarioService,
)
from .result_store import ProvenanceStep, ResultStore, provenance_chain
from .routing_service import (
    ROUTING_PROVENANCE,
    RoutingError,
    RoutingRequest,
    RoutingResult,
    RoutingService,
)
from .scenario_service import ScenarioNotFoundError, ScenarioService
from .sensitivity_service import (
    DEFAULT_RELATIVE_DELTA,
    ParameterInfluence,
    SensitivityError,
    SensitivityRequest,
    SensitivityResult,
    SensitivityService,
)
from .validation_service import ValidationService

__all__ = [
    "AVAILABLE_METRICS",
    "BACKWATER_PROFILE_PROVENANCE",
    "CLIMATE_MODES",
    "DEFAULT_N_RUNS",
    "DEFAULT_RELATIVE_DELTA",
    "DEFAULT_RISK_CUTOFFS",
    "DISTRIBUTIONS",
    "HYDRAULIC_UNCERTAINTY_PROVENANCE",
    "INUNDATION_PROVENANCE",
    "RISK_CLASSES",
    "ROUTING_PROVENANCE",
    "BackwaterProfileError",
    "BackwaterProfileRequest",
    "BackwaterProfileResult",
    "BackwaterProfileService",
    "BackwaterMonteCarloBaseline",
    "BasinMorphometry",
    "ClimateError",
    "ClimateScenario",
    "ClimateService",
    "DecisionSupportError",
    "DecisionSupportRequest",
    "DecisionSupportResult",
    "DecisionSupportService",
    "ThresholdAssessment",
    "DEFAULT_METHODOLOGIES",
    "GeoJsonSource",
    "GeoService",
    "GeoServiceError",
    "InundationError",
    "InundationRequest",
    "InundationResult",
    "InundationService",
    "HydraulicBaseline",
    "HydraulicUncertaintyError",
    "HydraulicUncertaintyRequest",
    "HydraulicUncertaintyResult",
    "HydraulicUncertaintyService",
    "MonteCarloError",
    "MonteCarloRequest",
    "MonteCarloService",
    "ParameterInfluence",
    "ParameterSpec",
    "ReachSpec",
    "SensitivityError",
    "SensitivityRequest",
    "SensitivityResult",
    "SensitivityService",
    "StageAreaSource",
    "SummaryStats",
    "TrapezoidSource",
    "PROJECT_EXTENSION",
    "RECOMMENDATIONS",
    "Report",
    "ReportSection",
    "ReportService",
    "SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSIONS",
    "CalculationContext",
    "CalculationError",
    "CalculationService",
    "CalibrationError",
    "CalibrationRequest",
    "CalibrationService",
    "ColumnMapping",
    "DataQualityService",
    "DataSource",
    "ApiSourceError",
    "FieldMap",
    "HttpApiSource",
    "ImportPreview",
    "ImportService",
    "ImportServiceError",
    "MethodologyDescriptor",
    "MethodologyRegistry",
    "ProjectService",
    "ProjectServiceError",
    "ProvenanceStep",
    "QualityGateDecision",
    "QualityPipeline",
    "QualityPipelineResult",
    "RESERVOIR_METHODOLOGY",
    "RESERVOIR_SCENARIO_TYPE",
    "ResultStore",
    "RoutingError",
    "RoutingRequest",
    "RoutingResult",
    "RoutingService",
    "RoutingMonteCarloBaseline",
    "ReservoirScenarioError",
    "ReservoirScenarioService",
    "ScenarioNotFoundError",
    "ScenarioService",
    "ServiceContainer",
    "ValidationService",
    "build_container",
    "build_default_registry",
    "provenance_chain",
]
