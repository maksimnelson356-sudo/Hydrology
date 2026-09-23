"""
core/services/sensitivity_service.py
One-at-a-time (OAT) sensitivity analysis and tornado ranking (stage P2.2).

For each named input parameter the model is evaluated at ``baseline ± delta``
while all other inputs stay at their baseline values. Parameters are ranked by
the absolute output swing ``|f(high) − f(low)|`` (tornado order).

Works with any user callable — calibration parameters from P1.5 or an ad-hoc
model. No new runtime dependencies: only stdlib dataclasses + the domain
models for provenance.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from core.domain.models import CalculationMetadata, CalculationResult, Methodology

__all__ = [
    "DEFAULT_RELATIVE_DELTA",
    "ParameterInfluence",
    "SensitivityError",
    "SensitivityRequest",
    "SensitivityResult",
    "SensitivityService",
]

#: Default relative half-width of the OAT sweep (±10 % of |baseline|).
DEFAULT_RELATIVE_DELTA = 0.1

#: Floor for the absolute delta when |baseline| is ~0 (avoids a zero sweep).
_ZERO_BASELINE_SCALE = 1.0


class SensitivityError(Exception):
    """Invalid sensitivity request or failed model evaluation."""


@dataclass(frozen=True)
class ParameterInfluence:
    """OAT swing for one parameter (tornado bar)."""

    name: str
    baseline: float
    low: float
    high: float
    output_low: float
    output_high: float
    swing: float
    rank: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Flat dict for tables / provenance."""
        return {
            "name": self.name,
            "baseline": self.baseline,
            "low": self.low,
            "high": self.high,
            "output_low": self.output_low,
            "output_high": self.output_high,
            "swing": self.swing,
            "rank": self.rank,
        }


@dataclass(frozen=True)
class SensitivityRequest:
    """Baseline point and per-parameter half-widths for the OAT sweep."""

    baseline: Mapping[str, float]
    #: Absolute half-widths; a parameter missing here uses ``relative_delta``.
    deltas: Mapping[str, float] = field(default_factory=dict)
    relative_delta: float = DEFAULT_RELATIVE_DELTA

    def validate(self) -> None:
        """Raise SensitivityError if the baseline / deltas are invalid."""
        if not self.baseline:
            raise SensitivityError("Базовая точка пуста — нет параметров")
        for name, value in self.baseline.items():
            if not str(name).strip():
                raise SensitivityError("Имя параметра не может быть пустым")
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise SensitivityError(
                    f"Значение «{name}» должно быть числом (получено {type(value).__name__})"
                )
            if not float(value) == float(value):  # NaN check without math import
                raise SensitivityError(f"Значение «{name}» = NaN")
        if float(self.relative_delta) <= 0:
            raise SensitivityError(
                f"relative_delta должен быть > 0 (получено {self.relative_delta})"
            )
        for name, delta in self.deltas.items():
            if name not in self.baseline:
                raise SensitivityError(
                    f"delta задана для «{name}», которого нет в baseline"
                )
            if not isinstance(delta, (int, float)) or isinstance(delta, bool):
                raise SensitivityError(f"delta «{name}» должно быть числом")
            if float(delta) <= 0:
                raise SensitivityError(f"delta «{name}» должно быть > 0")

    def absolute_delta(self, name: str) -> float:
        """Resolved half-width for ``name`` (explicit delta or relative)."""
        if name in self.deltas:
            return float(self.deltas[name])
        base = abs(float(self.baseline[name]))
        scale = base if base > 0 else _ZERO_BASELINE_SCALE
        return float(self.relative_delta) * scale


@dataclass(frozen=True)
class SensitivityResult:
    """Ranked tornado bars plus the baseline output."""

    influences: tuple[ParameterInfluence, ...]
    baseline_output: float

    @property
    def order(self) -> list[str]:
        """Parameter names from most to least sensitive."""
        return [item.name for item in self.influences]

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe payload for CalculationResult.output_data."""
        return {
            "baseline_output": self.baseline_output,
            "order": self.order,
            "influences": [item.to_dict() for item in self.influences],
        }


class SensitivityService:
    """OAT sensitivity / tornado ranking over a user-supplied model."""

    @classmethod
    def analyze(
        cls,
        model: Callable[[Mapping[str, float]], float],
        request: SensitivityRequest,
    ) -> SensitivityResult:
        """Evaluate ``model`` at baseline ± delta for every parameter.

        Raises:
            SensitivityError: empty baseline, bad deltas, or non-finite output.
        """
        request.validate()
        baseline = {str(k): float(v) for k, v in request.baseline.items()}
        base_out = cls._evaluate(model, baseline, "baseline")

        influences: list[ParameterInfluence] = []
        for name in baseline:
            half = request.absolute_delta(name)
            low_point = dict(baseline)
            high_point = dict(baseline)
            low_point[name] = baseline[name] - half
            high_point[name] = baseline[name] + half
            out_low = cls._evaluate(model, low_point, f"low:{name}")
            out_high = cls._evaluate(model, high_point, f"high:{name}")
            swing = abs(out_high - out_low)
            influences.append(
                ParameterInfluence(
                    name=name,
                    baseline=baseline[name],
                    low=low_point[name],
                    high=high_point[name],
                    output_low=out_low,
                    output_high=out_high,
                    swing=swing,
                )
            )

        # Most sensitive first; stable tie-break by name for reproducibility.
        influences.sort(key=lambda item: (-item.swing, item.name))
        ranked = [
            ParameterInfluence(
                name=item.name,
                baseline=item.baseline,
                low=item.low,
                high=item.high,
                output_low=item.output_low,
                output_high=item.output_high,
                swing=item.swing,
                rank=index,
            )
            for index, item in enumerate(influences, start=1)
        ]
        return SensitivityResult(
            influences=tuple(ranked), baseline_output=base_out
        )

    @classmethod
    def run(
        cls,
        model: Callable[[Mapping[str, float]], float],
        request: SensitivityRequest,
    ) -> CalculationResult:
        """Same as :meth:`analyze` but wraps the outcome in ``CalculationResult``."""
        result = cls.analyze(model, request)
        payload = result.to_dict()
        metadata = CalculationMetadata(
            methodology=Methodology(
                name="sensitivity_oat",
                version="1.0",
                standard="OAT tornado",
                description=(
                    f"params={', '.join(payload['order'])}; "
                    f"relative_delta={request.relative_delta}"
                ),
            ),
            input_parameters={
                "baseline": {k: float(v) for k, v in request.baseline.items()},
                "deltas": {k: float(v) for k, v in request.deltas.items()},
                "relative_delta": float(request.relative_delta),
                "order": payload["order"],
            },
        )
        metadata.mark_running()
        metadata.mark_completed()
        return CalculationResult(metadata=metadata, output_data=payload)

    @staticmethod
    def _evaluate(
        model: Callable[[Mapping[str, float]], float],
        point: Mapping[str, float],
        label: str,
    ) -> float:
        try:
            value = float(model(point))
        except SensitivityError:
            raise
        except Exception as exc:  # noqa: BLE001 — user model may raise anything
            raise SensitivityError(f"Модель ({label}): {exc}") from exc
        if value != value or value in (float("inf"), float("-inf")):
            raise SensitivityError(f"Модель ({label}) вернула не-конечное значение")
        return value
