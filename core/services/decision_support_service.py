"""
core/services/decision_support_service.py
Decision Support: exceedance probability and risk class (stage P2.5).

Decision 10.3 (a): thresholds are user-supplied ``Q_крит`` values; the service
never invents a threshold from percentiles. For each threshold it computes

    P(exceed) = count(samples > Q_крит) / N

and maps that probability to a risk class (низкий / средний / высокий) via
explicit, configurable cut-offs. Optional recommendation text for the report.

No new runtime dependencies: stdlib only. Mathematics lives here; the GUI only
collects the threshold and draws the result.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from core.domain.models import CalculationMetadata, CalculationResult, Methodology

__all__ = [
    "DEFAULT_RISK_CUTOFFS",
    "RISK_CLASSES",
    "DecisionSupportError",
    "DecisionSupportRequest",
    "DecisionSupportResult",
    "DecisionSupportService",
    "ThresholdAssessment",
]

#: Risk classes ordered from least to most severe (ROADMAP §6.2 P2.5).
RISK_CLASSES: tuple[str, ...] = ("низкий", "средний", "высокий")

#: P(exceed) cut-offs: < low → «низкий»; < medium → «средний»; else «высокий».
DEFAULT_RISK_CUTOFFS: Mapping[str, float] = {"low": 0.05, "medium": 0.20}


class DecisionSupportError(Exception):
    """Invalid decision-support request or empty sample."""


@dataclass(frozen=True)
class ThresholdAssessment:
    """Exceedance stats for one user threshold (Q_крит)."""

    name: str
    threshold: float
    n_samples: int
    n_exceed: int
    p_exceed: float
    risk_class: str

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe payload for tables / report lines."""
        return {
            "name": self.name,
            "threshold": float(self.threshold),
            "n_samples": int(self.n_samples),
            "n_exceed": int(self.n_exceed),
            "p_exceed": float(self.p_exceed),
            "risk_class": str(self.risk_class),
        }


@dataclass(frozen=True)
class DecisionSupportRequest:
    """Samples plus one or more user thresholds (decision 10.3 (a))."""

    samples: Sequence[float]
    #: name → Q_крит (must be non-empty; thresholds are explicit).
    thresholds: Mapping[str, float]
    risk_cutoffs: Mapping[str, float] = field(
        default_factory=lambda: dict(DEFAULT_RISK_CUTOFFS)
    )

    def validate(self) -> None:
        """Raise DecisionSupportError if samples / thresholds are unusable."""
        if not self.samples:
            raise DecisionSupportError("Пустая выборка — нечего оценивать")
        for value in self.samples:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise DecisionSupportError(
                    f"Выборка должна содержать числа (получено {type(value).__name__})"
                )
            if float(value) != float(value):  # NaN
                raise DecisionSupportError("Выборка содержит NaN")
        if not self.thresholds:
            raise DecisionSupportError(
                "Нет порогов Q_крит — задайте хотя бы один (решение 10.3 (а))"
            )
        for name, value in self.thresholds.items():
            if not str(name).strip():
                raise DecisionSupportError("Имя порога не может быть пустым")
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise DecisionSupportError(
                    f"Порог «{name}» должен быть числом (получено {type(value).__name__})"
                )
            if float(value) != float(value):
                raise DecisionSupportError(f"Порог «{name}» = NaN")
        low = float(self.risk_cutoffs.get("low", DEFAULT_RISK_CUTOFFS["low"]))
        medium = float(self.risk_cutoffs.get("medium", DEFAULT_RISK_CUTOFFS["medium"]))
        if not (0.0 <= low < medium <= 1.0):
            raise DecisionSupportError(
                f"Пороги риска: 0 ≤ low < medium ≤ 1 (low={low}, medium={medium})"
            )


@dataclass(frozen=True)
class DecisionSupportResult:
    """Ranked-by-threshold assessments plus overall sample summary."""

    assessments: tuple[ThresholdAssessment, ...]
    n_samples: int
    sample_mean: float
    sample_max: float

    @property
    def worst_class(self) -> str:
        """Most severe risk class among assessments («низкий» < … < «высокий»)."""
        if not self.assessments:
            return RISK_CLASSES[0]
        order = {name: index for index, name in enumerate(RISK_CLASSES)}
        return max(
            (item.risk_class for item in self.assessments),
            key=lambda cls: order.get(cls, 0),
        )

    @property
    def recommendation(self) -> str:
        """Short human recommendation for the engineering report."""
        worst = self.worst_class
        if worst == "высокий":
            return "Риск высокий: требуется проверить пороги и меры снижения."
        if worst == "средний":
            return "Риск средний: рекомендуется дополнительная проверка расчёта."
        return "Риск низкий при заданных порогах Q_крит."

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe payload for CalculationResult.output_data."""
        return {
            "n_samples": self.n_samples,
            "sample_mean": self.sample_mean,
            "sample_max": self.sample_max,
            "worst_class": self.worst_class,
            "recommendation": self.recommendation,
            "assessments": [item.to_dict() for item in self.assessments],
        }


class DecisionSupportService:
    """Exceedance probability and risk class for user Q_крит (10.3 (a))."""

    @classmethod
    def assess(
        cls,
        request: DecisionSupportRequest,
    ) -> DecisionSupportResult:
        """Evaluate every threshold against the sample.

        Raises:
            DecisionSupportError: empty sample, empty thresholds, bad cutoffs.
        """
        request.validate()
        values = [float(v) for v in request.samples]
        n = len(values)
        sample_mean = sum(values) / n
        sample_max = max(values)
        low = float(request.risk_cutoffs.get("low", DEFAULT_RISK_CUTOFFS["low"]))
        medium = float(
            request.risk_cutoffs.get("medium", DEFAULT_RISK_CUTOFFS["medium"])
        )

        assessments: list[ThresholdAssessment] = []
        # Stable order: insertion order of thresholds mapping.
        for name, threshold in request.thresholds.items():
            q = float(threshold)
            n_exceed = sum(1 for v in values if v > q)
            p = n_exceed / n
            if p < low:
                risk = RISK_CLASSES[0]
            elif p < medium:
                risk = RISK_CLASSES[1]
            else:
                risk = RISK_CLASSES[2]
            assessments.append(
                ThresholdAssessment(
                    name=str(name),
                    threshold=q,
                    n_samples=n,
                    n_exceed=n_exceed,
                    p_exceed=p,
                    risk_class=risk,
                )
            )
        return DecisionSupportResult(
            assessments=tuple(assessments),
            n_samples=n,
            sample_mean=sample_mean,
            sample_max=sample_max,
        )

    @classmethod
    def run(cls, request: DecisionSupportRequest) -> CalculationResult:
        """Same as :meth:`assess` but wraps the outcome in ``CalculationResult``."""
        result = cls.assess(request)
        payload = result.to_dict()
        metadata = CalculationMetadata(
            methodology=Methodology(
                name="decision_support",
                version="1.0",
                standard="P(exceed), risk class",
                description=(
                    f"thresholds={list(request.thresholds)}; "
                    f"decision=10.3(a) user Q_крит; N={result.n_samples}"
                ),
            ),
            input_parameters={
                "thresholds": {
                    str(k): float(v) for k, v in request.thresholds.items()
                },
                "risk_cutoffs": {
                    str(k): float(v) for k, v in request.risk_cutoffs.items()
                },
                "n_samples": result.n_samples,
            },
        )
        metadata.mark_running()
        metadata.mark_completed()
        return CalculationResult(metadata=metadata, output_data=payload)
