"""
core/services/quality_pipeline.py
Mandatory quality gates for import and calculation (stage P1.3).

Pipeline stages:
- after_import: analyze only — report for the user, never mutates the series;
- before_calculation: analyze + gate — CRITICAL/ERROR issues block the run
  until the user explicitly confirms; WARNING/INFO only warn.

Reactive rules (configurable): year gaps already come from DataQualityService;
this module adds jump/spike detection between consecutive years.

Services contain no mathematics beyond simple threshold checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.domain.models import (
    DataQualityReport,
    Dataset,
    ValidationIssue,
    ValidationSeverity,
)
from core.services.data_quality_service import DataQualityService

__all__ = [
    "QualityGateDecision",
    "QualityPipeline",
    "QualityPipelineResult",
]

# Severities that block calculation without explicit user confirmation.
BLOCKING_SEVERITIES = frozenset(
    {ValidationSeverity.ERROR, ValidationSeverity.CRITICAL}
)

# Default spike rule: |ΔQ| / max(|Q_prev|, eps) above ratio flags a jump.
DEFAULT_SPIKE_RATIO = 8.0
DEFAULT_SPIKE_EPS = 1e-9


@dataclass(frozen=True)
class QualityGateDecision:
    """Outcome of a quality gate for a single stage."""

    stage: str  # "after_import" | "before_calculation"
    allowed: bool
    needs_confirmation: bool
    blocking: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if self.needs_confirmation:
            return (
                f"{self.stage}: обнаружено {len(self.blocking)} "
                f"блокирующ(ая/их) проблем(ы) — требуется подтверждение"
            )
        if not self.allowed:
            return f"{self.stage}: расчёт заблокирован по качеству данных"
        if self.warnings:
            return f"{self.stage}: предупреждений {len(self.warnings)}"
        return f"{self.stage}: качество в норме"


@dataclass
class QualityPipelineResult:
    """Report + gate decision for a pipeline stage."""

    report: DataQualityReport
    decision: QualityGateDecision
    extra_issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.decision.allowed

    @property
    def needs_confirmation(self) -> bool:
        return self.decision.needs_confirmation


class QualityPipeline:
    """Import/calculation quality gates built on DataQualityService."""

    def __init__(
        self,
        quality: DataQualityService | None = None,
        *,
        spike_ratio: float = DEFAULT_SPIKE_RATIO,
    ) -> None:
        self._quality = quality or DataQualityService()
        self.spike_ratio = float(spike_ratio)

    # ------------------------------------------------------------------
    # Stages
    # ------------------------------------------------------------------
    def after_import(
        self,
        dataset: Dataset,
        *,
        methodology_id: str | None = None,
    ) -> QualityPipelineResult:
        """Analyze after import: report only, never block UI import.

        Decision is informational: ``allowed`` is True unless the series is
        empty; ``needs_confirmation`` is True when blocking issues exist so
        the UI can warn before calculations.
        """
        report, extra = self._analyze(dataset, methodology_id)
        blocking, warnings = self._split(report, extra)
        decision = QualityGateDecision(
            stage="after_import",
            allowed=dataset.length > 0,
            needs_confirmation=bool(blocking) and dataset.length > 0,
            blocking=blocking,
            warnings=warnings,
        )
        return QualityPipelineResult(report=report, decision=decision, extra_issues=extra)

    def before_calculation(
        self,
        dataset: Dataset,
        *,
        confirmed: bool = False,
        methodology_id: str | None = None,
    ) -> QualityPipelineResult:
        """Gate before a calculation run.

        CRITICAL/ERROR issues (including reactive spikes) block until
        ``confirmed`` is True. The dataset is never modified.
        """
        report, extra = self._analyze(dataset, methodology_id)
        blocking, warnings = self._split(report, extra)

        if not blocking or confirmed:
            allowed = True
            needs_confirmation = False
        else:
            allowed = False
            needs_confirmation = True

        # Empty series can never be calculated, confirmation or not.
        if dataset.length == 0:
            allowed = False
            needs_confirmation = False

        decision = QualityGateDecision(
            stage="before_calculation",
            allowed=allowed,
            needs_confirmation=needs_confirmation,
            blocking=blocking,
            warnings=warnings,
        )
        return QualityPipelineResult(report=report, decision=decision, extra_issues=extra)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _analyze(
        self, dataset: Dataset, methodology_id: str | None
    ) -> tuple[DataQualityReport, list[ValidationIssue]]:
        snapshot = dict(dataset.data)
        report = self._quality.analyze(dataset, methodology_id=methodology_id)
        # Hard guarantee: analysis never mutates the series (product rule).
        if dataset.data != snapshot:
            dataset.data.clear()
            dataset.data.update(snapshot)
        extra = self._spike_issues(dataset)
        return report, extra

    def _spike_issues(self, dataset: Dataset) -> list[ValidationIssue]:
        """Flag abrupt year-to-year jumps beyond ``spike_ratio``.

        Ratio is max(|Q_prev|, |Q_now|) / min(|Q_prev|, |Q_now|) for
        same-sign pairs (1.5× jump → ratio 1.5); sign flips and
        transitions through near-zero are treated as infinite jumps.
        """
        if dataset.length < 2:
            return []
        issues: list[ValidationIssue] = []
        years = dataset.years
        for prev_year, year in zip(years, years[1:], strict=False):
            prev = dataset.data[prev_year]
            curr = dataset.data[year]
            ratio = self._jump_ratio(prev, curr)
            if ratio is not None and ratio >= self.spike_ratio:
                ratio_desc = "inf" if ratio == float("inf") else f"×{ratio:.1f}"
                issues.append(
                    ValidationIssue(
                        code="DATA_SPIKE",
                        message=(
                            f"Резкий скачок {prev_year}→{year}: "
                            f"{prev:.3g} → {curr:.3g} ({ratio_desc})"
                        ),
                        severity=ValidationSeverity.WARNING,
                        field="data",
                        details={
                            "why_it_matters": (
                                "Внезапный выброс/обрыв ряда искажает параметры "
                                "распределения и экстремальные оценки."
                            ),
                            "recommended_actions": [
                                {
                                    "code": "spike_review",
                                    "description": (
                                        "Проверить измерения и журнал постов "
                                        "за указанные годы"
                                    ),
                                }
                            ],
                            "from_year": prev_year,
                            "to_year": year,
                            "ratio": (
                                "inf" if ratio == float("inf") else round(ratio, 3)
                            ),
                            "threshold": self.spike_ratio,
                        },
                    )
                )
        return issues

    @staticmethod
    def _jump_ratio(prev: float, curr: float) -> float | None:
        a, b = abs(prev), abs(curr)
        if a < DEFAULT_SPIKE_EPS and b < DEFAULT_SPIKE_EPS:
            return None
        if a < DEFAULT_SPIKE_EPS or b < DEFAULT_SPIKE_EPS:
            return float("inf")
        if prev * curr < 0:
            return (a + b) / min(a, b)
        return max(a, b) / min(a, b)

    @staticmethod
    def _split(
        report: DataQualityReport, extra: list[ValidationIssue]
    ) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
        all_issues = list(report.issues) + list(extra)
        blocking = [i for i in all_issues if i.severity in BLOCKING_SEVERITIES]
        warnings = [i for i in all_issues if i.severity not in BLOCKING_SEVERITIES]
        return blocking, warnings

    def gate_payload(self, result: QualityPipelineResult) -> dict[str, Any]:
        """JSON-safe payload for logs / provenance attachments."""
        decision = result.decision
        return {
            "stage": decision.stage,
            "allowed": decision.allowed,
            "needs_confirmation": decision.needs_confirmation,
            "quality_score": round(result.report.quality_score, 3),
            "quality_grade": result.report.quality_grade,
            "blocking": [
                {"code": i.code, "severity": i.severity.value, "message": i.message}
                for i in decision.blocking
            ],
            "warnings": [
                {"code": i.code, "severity": i.severity.value, "message": i.message}
                for i in decision.warnings
            ],
        }
