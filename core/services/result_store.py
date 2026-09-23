"""
core/services/result_store.py
Storage and comparison of calculation results (stage 4 of DOCS/ROADMAP.md).

A CalculationResult is an object, not a number; the store keeps the history,
assigns a human-readable "Calculation #N" label, and provides provenance
(«откуда это число?») and diff for change messages like «результат изменился
с 1180 до 1240 м³/с на +5.1%».

This is an in-memory store; persistence is delegated to the project service
and the .hsp file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from core.domain.models import CalculationResult

try:
    from version import VERSION_FULL as ENGINE_VERSION
except Exception:  # pragma: no cover - very early bootstrap failures
    ENGINE_VERSION = "unknown"


@dataclass
class ProvenanceStep:
    """One step in the provenance chain of a calculation."""

    kind: str  # "calculation" | "methodology" | "dataset" | "quality" | "parameters" | "scenario" | "engine"
    title: str
    detail: str
    reference: str | None = None
    timestamp: datetime | None = None


def _to_plain(value: Any) -> Any:
    """Coerce a value to a JSON-friendly primitive for display."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (value != value):  # NaN
            return ""
        return value
    if isinstance(value, dict):
        if not value:
            return ""
        parts: list[str] = []
        for key in value:  # preserve insertion order (Python 3.7+)
            parts.append(f"{key}: {_to_plain(value[key])}")
        return "{" + ", ".join(parts) + "}"
    return str(value)


def provenance_chain(
    result: CalculationResult,
    *,
    engine_version: str = ENGINE_VERSION,
    quality_grade: str | None = None,
    quality_score: float | None = None,
    scenario_id: UUID | None = None,
    scenario_name: str | None = None,
    dataset_id: UUID | None = None,
    dataset_name: str | None = None,
    n_years: int | None = None,
    parameters: dict[str, Any] | None = None,
) -> list[ProvenanceStep]:
    """Build the provenance chain «откуда это число?».

    Order (most recent first, like a normal audit trail):
        calculation
        methodology (включая версию и норматив)
        dataset (число лет)
        quality (оценка качества данных)
        parameters (Cv, Cs, ...)
        scenario (если был)
        engine (версия движка)
    """
    metadata = result.metadata
    methodology = metadata.methodology
    steps: list[ProvenanceStep] = []

    steps.append(
        ProvenanceStep(
            kind="calculation",
            title=getattr(metadata, 'label', 'Расчёт'),
            detail=(
                f"{methodology.name}@{methodology.version} — "
                f"{metadata.status.value}; "
                f"{metadata.duration_seconds:.2f} с"
            )
            if metadata.duration_seconds
            else f"{methodology.name}@{methodology.version} — {metadata.status.value}",
            timestamp=metadata.completed_at or metadata.started_at,
        )
    )

    standard = methodology.standard or "не указан"
    steps.append(
        ProvenanceStep(
            kind="methodology",
            title=f"Методика: {methodology.name}",
            detail=f"{standard}; версия {methodology.version}",
            reference=standard,
        )
    )

    if dataset_name:
        parts = [f"пост «{dataset_name}»"]
        if n_years is not None:
            parts.append(f"{n_years} лет")
        steps.append(
            ProvenanceStep(
                kind="dataset",
                title="Входные данные",
                detail=", ".join(parts),
                reference=None,
            )
        )
    elif dataset_id is not None:
        steps.append(
            ProvenanceStep(
                kind="dataset",
                title="Входные данные",
                detail=f"dataset_id={dataset_id}",
                reference=None,
            )
        )

    if quality_grade is not None or quality_score is not None:
        quality_parts: list[str] = []
        if quality_grade:
            quality_parts.append(f"оценка {quality_grade}")
        if quality_score is not None:
            quality_parts.append(f"скор {quality_score:.2f}")
        steps.append(
            ProvenanceStep(
                kind="quality",
                title="Качество данных",
                detail=", ".join(quality_parts),
                reference=None,
            )
        )

    if parameters:
        steps.append(
            ProvenanceStep(
                kind="parameters",
                title="Параметры расчёта",
                detail=_to_plain(parameters),
                reference=None,
            )
        )

    if scenario_name or scenario_id is not None:
        steps.append(
            ProvenanceStep(
                kind="scenario",
                title="Сценарий",
                detail=scenario_name or f"scenario_id={scenario_id}",
                reference=None,
            )
        )

    steps.append(
        ProvenanceStep(
            kind="engine",
            title="Версия движка",
            detail=engine_version,
            reference=engine_version,
        )
    )

    return steps


@dataclass
class ResultStore:
    """In-memory history of calculation results for a single context (e.g. project)."""

    _results: list[CalculationResult] = field(default_factory=list, repr=False)
    _next_number: int = 1

    def attach(self, result: CalculationResult) -> None:
        """Register a completed/failed result and assign the sequence label."""
        metadata = result.metadata
        label = f"Расчёт #{self._next_number}"
        metadata.label = label
        result.metadata = metadata
        self._results.append(result)
        self._next_number += 1

    def register(self, result: CalculationResult) -> CalculationResult:
        """Register and return the same result (convenience for fluent usage)."""
        self.attach(result)
        return result

    def list_results(self) -> list[CalculationResult]:
        return list(self._results)

    def get_by_id(self, result_id: UUID) -> CalculationResult | None:
        for item in self._results:
            if item.id == result_id:
                return item
        return None

    def find_by_methodology(self, qualified_name: str) -> list[CalculationResult]:
        return [
            item
            for item in self._results
            if item.metadata.methodology.qualified_name == qualified_name
        ]

    def find_by_dataset(self, dataset_id: UUID) -> list[CalculationResult]:
        return [
            item
            for item in self._results
            if item.metadata.input_dataset_ids and dataset_id in item.metadata.input_dataset_ids
        ]

    def find_by_scenario(self, scenario_id: UUID) -> list[CalculationResult]:
        return [
            item
            for item in self._results
            if getattr(item.metadata, "scenario_id", None) == scenario_id
        ]

    def latest(self, n: int = 1) -> list[CalculationResult]:
        return self._results[-n:]

    def count(self) -> int:
        return len(self._results)

    def load_results(self, results: list[CalculationResult]) -> None:
        """Replace the internal list with the given results and adjust the next number."""
        self._results = list(results)
        self._next_number = len(self._results) + 1
        # Ensure each result has a label (should already have from serialization)
        for idx, result in enumerate(self._results, start=1):
            if not getattr(result.metadata, 'label', None):
                result.metadata.label = f"Расчёт #{idx}"
                result.metadata = result.metadata  # trigger reassignment if needed

    def set_next_number(self, number: int) -> None:
        """Set the next label number."""
        self._next_number = max(number, 1)

    # ------------------------------------------------------------------
    # Diff for change messages («было / стало»)
    # ------------------------------------------------------------------

    def compare(
        self,
        old: CalculationResult,
        new: CalculationResult,
    ) -> dict[str, Any]:
        """Compare two CalculationResults and describe the observed change.

        Returns a dict with keys:
            - old_values: dict describing old output_data (plain values)
            - new_values: dict describing new output_data (plain values)
            - changes: list[dict] with keys {path, old, new, value, percent, note}
            - status_changed: bool
        """
        old_data = dict(old.output_data)
        new_data = dict(new.output_data)

        changes: list[dict[str, Any]] = []
        all_keys = sorted(old_data.keys())
        for key in all_keys:
            old_val = old_data.get(key)
            new_val = new_data.get(key)
            if old_val == new_val:
                continue
            try:
                old_num = float(old_val) if old_val is not None else None
                new_num = float(new_val) if new_val is not None else None
            except (TypeError, ValueError):
                old_num = None
                new_num = None

            if old_num is not None and new_num is not None and old_num != 0.0:
                percent = (new_num - old_num) / abs(old_num) * 100.0
                percent_text = f"{percent:+.1f}%"
            else:
                percent = None
                percent_text = ""

            human_old = _to_plain(old_val)
            human_new = _to_plain(new_val)
            note = ""
            if percent is not None:
                note = f"изменение {percent_text}"
            changes.append(
                {
                    "path": key,
                    "old": human_old,
                    "new": human_new,
                    "value": new_num if new_num is not None else new_val,
                    "percent": percent_text,
                    "note": note,
                }
            )

        return {
            "old_values": {k: _to_plain(v) for k, v in old_data.items()},
            "new_values": {k: _to_plain(v) for k, v in new_data.items()},
            "changes": changes,
            "status_changed": old.metadata.status != new.metadata.status,
        }


def compare(
    store: ResultStore,
    old: CalculationResult,
    new: CalculationResult,
) -> dict[str, Any]:
    """Compare two CalculationResults through the given store.

    Convenience wrapper around ResultStore.compare when you already have a store.
    """
    return store.compare(old, new)


__all__ = [
    "ProvenanceStep",
    "ResultStore",
    "compare",
    "provenance_chain",
    "ENGINE_VERSION",
]

