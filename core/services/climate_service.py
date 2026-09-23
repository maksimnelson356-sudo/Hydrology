"""
core/services/climate_service.py
Climate delta-change scenarios (stage P2.3).

Applies a multiplicative or additive climate factor to a year→value series
without external APIs and without a new stack (stdlib only).

Modes
-----
- ``multiplicative``: ``y' = y * (1 + delta)``  (e.g. Q × 1.1)
- ``additive``:       ``y' = y + delta``         (absolute units)

The output is the same type as the input (``dict[int, float]`` or a
``Dataset`` clone) so it stays compatible with ``Dataset`` /
``CalculationService``. Scenario parameters are JSON-safe and stored in
``Dataset.metadata["climate"]`` for ``.hsp`` round-trip.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.domain.models import Dataset

__all__ = [
    "CLIMATE_MODES",
    "CLIMATE_METADATA_KEY",
    "ClimateError",
    "ClimateScenario",
    "ClimateService",
]

#: Supported delta-change modes (ROADMAP §6.2 P2.3).
CLIMATE_MODES: tuple[str, ...] = ("multiplicative", "additive")

#: Key under ``Dataset.metadata`` for the last applied scenario (JSON-safe).
CLIMATE_METADATA_KEY = "climate"


class ClimateError(Exception):
    """Invalid climate scenario or failed series transform."""


@dataclass(frozen=True)
class ClimateScenario:
    """Delta-change parameters for one climate factor.

    Attributes:
        name: Human label (shown in GUI / provenance).
        delta: Relative fraction for multiplicative mode (0.1 → ×1.1)
            or absolute increment for additive mode.
        mode: ``multiplicative`` or ``additive``.
    """

    name: str = "baseline"
    delta: float = 0.0
    mode: str = "multiplicative"

    def validate(self) -> None:
        """Raise ClimateError if name / delta / mode are invalid."""
        if not str(self.name).strip():
            raise ClimateError("Имя климат-сценария не может быть пустым")
        mode = str(self.mode).strip().lower()
        if mode not in CLIMATE_MODES:
            raise ClimateError(
                f"Неизвестный режим «{self.mode}»; доступны: {', '.join(CLIMATE_MODES)}"
            )
        if not isinstance(self.delta, (int, float)) or isinstance(self.delta, bool):
            raise ClimateError(
                f"delta должен быть числом (получено {type(self.delta).__name__})"
            )
        if self.delta != self.delta:  # NaN
            raise ClimateError("delta = NaN")

    def apply_value(self, value: float) -> float:
        """Transform a single scalar under this scenario."""
        if str(self.mode).strip().lower() == "additive":
            return float(value) + float(self.delta)
        return float(value) * (1.0 + float(self.delta))

    def to_metadata(self) -> dict[str, Any]:
        """JSON-safe payload for ``Dataset.metadata[CLIMATE_METADATA_KEY]``."""
        return {
            "name": str(self.name),
            "delta": float(self.delta),
            "mode": str(self.mode).strip().lower(),
            "method": "delta_change@1.0",
        }

    @classmethod
    def from_metadata(cls, raw: Any) -> ClimateScenario | None:
        """Restore a scenario from metadata; ``None`` if unusable."""
        if not isinstance(raw, dict):
            return None
        try:
            return cls(
                name=str(raw.get("name") or "scenario"),
                delta=float(raw.get("delta", 0.0)),
                mode=str(raw.get("mode") or "multiplicative"),
            )
        except (TypeError, ValueError):
            return None


class ClimateService:
    """Apply climate delta-change factors to hydrological series."""

    @classmethod
    def apply_series(
        cls,
        data: Mapping[int, float],
        scenario: ClimateScenario,
    ) -> dict[int, float]:
        """Return a new year→value mapping with the factor applied.

        Raises:
            ClimateError: empty series or non-finite input/output.
        """
        scenario.validate()
        if not data:
            raise ClimateError("Пустой ряд — применять климат-фактор не к чему")
        out: dict[int, float] = {}
        for year, value in data.items():
            try:
                year_i = int(year)
                raw = float(value)
            except (TypeError, ValueError) as exc:
                raise ClimateError(f"Нечисловое значение в году {year}: {value!r}") from exc
            if raw != raw or raw in (float("inf"), float("-inf")):
                raise ClimateError(f"Неконечное значение в году {year}")
            transformed = scenario.apply_value(raw)
            if transformed != transformed or transformed in (
                float("inf"),
                float("-inf"),
            ):
                raise ClimateError(f"Результат неконечен в году {year}")
            out[year_i] = transformed
        return out

    @classmethod
    def apply_dataset(
        cls,
        dataset: Dataset,
        scenario: ClimateScenario,
        name_suffix: str | None = None,
    ) -> Dataset:
        """Clone ``dataset`` with the factor applied and climate metadata.

        The input dataset is not mutated (program never edits data silently).
        """
        scenario.validate()
        if not dataset.data:
            raise ClimateError("Пустой набор данных — применять климат-фактор не к чему")
        new_data = cls.apply_series(dataset.data, scenario)
        suffix = name_suffix if name_suffix is not None else f" [{scenario.name}]"
        clone = dataset.clone(name=f"{dataset.name}{suffix}")
        clone.data = new_data
        clone.metadata = dict(dataset.metadata)
        clone.metadata[CLIMATE_METADATA_KEY] = scenario.to_metadata()
        clone.touch()
        return clone

    @classmethod
    def identity(cls, data: Mapping[int, float]) -> dict[int, float]:
        """Return an independent copy (δ=0 reference for before/after)."""
        return {int(y): float(v) for y, v in data.items()}
