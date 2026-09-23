"""
core/services/scenario_service.py
Scenario management for the HydroSphere P0 architecture.

A scenario is a variation of the base case: it overrides calculation parameters
and/or the input dataset, and can be recalculated at any time without touching
the base data. Scenarios form a lineage (Base -> Scenario A -> Scenario B) via
`Scenario.parent_scenario_id`.

The service contains no mathematics: calculations are delegated to
`CalculationService` (which in turn calls the calculation core).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID, uuid4

from core.domain.models import (
    CalculationResult,
    Dataset,
    Scenario,
    ScenarioStatus,
)
from core.services.calculation_service import CalculationError, CalculationService


class ScenarioNotFoundError(KeyError):
    """Raised when a scenario id is not present in the service."""


class ScenarioService:
    """In-memory scenario management bound to a single project."""

    def __init__(
        self,
        project_id: UUID | None = None,
        calculation_service: CalculationService | None = None,
        base_dataset: Dataset | None = None,
    ) -> None:
        self.project_id: UUID = project_id or uuid4()
        self._calculation_service = calculation_service
        self._base_dataset = base_dataset
        self._scenarios: dict[UUID, Scenario] = {}
        self._datasets: dict[UUID, Dataset] = {}
        self._results: dict[UUID, CalculationResult] = {}

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def create(
        self,
        name: str,
        parameters: dict[str, Any] | None = None,
        base_dataset_id: UUID | None = None,
        description: str = "",
        dataset: Dataset | None = None,
        parent: Scenario | None = None,
        project_id: UUID | None = None,
    ) -> Scenario:
        """Create a new scenario in the project."""
        scenario = Scenario(
            name=name,
            project_id=project_id or self.project_id,
            base_dataset_id=base_dataset_id or (self._base_dataset.id if self._base_dataset else None),
            parameters=dict(parameters or {}),
            description=description,
            parent_scenario_id=parent.id if parent is not None else None,
        )
        self._scenarios[scenario.id] = scenario
        if dataset is not None:
            self._datasets[scenario.id] = dataset
        return scenario

    def get(self, scenario_id: UUID) -> Scenario:
        """Return a scenario by id. Raises ScenarioNotFoundError for an unknown id."""
        try:
            return self._scenarios[scenario_id]
        except KeyError:
            raise ScenarioNotFoundError(f"Unknown scenario id: {scenario_id}") from None

    def get_optional(self, scenario_id: UUID) -> Scenario | None:
        """Return a scenario by id or None when it is not registered."""
        return self._scenarios.get(scenario_id)

    def has(self, scenario_id: UUID) -> bool:
        """Check whether a scenario id is registered."""
        return scenario_id in self._scenarios

    def update(
        self,
        scenario_id: UUID,
        parameters: dict[str, Any] | None = None,
        name: str | None = None,
        description: str | None = None,
    ) -> Scenario:
        """Update scenario parameters in place and return it."""
        scenario = self.get(scenario_id)
        if name is not None:
            if not name.strip():
                raise ValueError("Scenario name cannot be empty")
            scenario.name = name
        if description is not None:
            scenario.description = description
        if parameters:
            scenario.parameters.update(parameters)
        scenario.touch()
        return scenario

    def clone(
        self,
        scenario_id: UUID,
        name: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> Scenario:
        """Clone a scenario; the original is never modified."""
        source = self.get(scenario_id)
        copy = source.clone(name=name)
        copy.parent_scenario_id = source.id
        if parameters:
            copy.parameters.update(parameters)
        self._scenarios[copy.id] = copy
        source_dataset = self._datasets.get(source.id)
        if source_dataset is not None:
            self._datasets[copy.id] = source_dataset.clone(name=f"{source_dataset.name} (scenario copy)")
        return copy

    def archive(self, scenario_id: UUID) -> Scenario:
        """Mark a scenario as archived."""
        scenario = self.get(scenario_id)
        scenario.status = ScenarioStatus.ARCHIVED
        scenario.touch()
        return scenario

    def activate(self, scenario_id: UUID) -> Scenario:
        """Mark a scenario as active."""
        scenario = self.get(scenario_id)
        scenario.status = ScenarioStatus.ACTIVE
        scenario.touch()
        return scenario

    def remove(self, scenario_id: UUID) -> None:
        """Delete a scenario and everything bound to it."""
        self.get(scenario_id)
        del self._scenarios[scenario_id]
        self._datasets.pop(scenario_id, None)
        self._results.pop(scenario_id, None)

    def list(self, include_archived: bool = False) -> list[Scenario]:
        """List scenarios sorted by creation time."""
        items = list(self._scenarios.values())
        if not include_archived:
            items = [item for item in items if item.status is not ScenarioStatus.ARCHIVED]
        return sorted(items, key=lambda item: item.created_at)

    # ------------------------------------------------------------------
    # Datasets
    # ------------------------------------------------------------------
    def set_base_dataset(self, dataset: Dataset) -> None:
        """Set the dataset used when a scenario has no override."""
        self._base_dataset = dataset

    @property
    def base_dataset(self) -> Dataset | None:
        """The dataset used for scenarios without an override."""
        return self._base_dataset

    def set_dataset(self, scenario_id: UUID, dataset: Dataset) -> None:
        """Bind a dataset override to a scenario."""
        self.get(scenario_id)
        self._datasets[scenario_id] = dataset

    def get_dataset(self, scenario_id: UUID) -> Dataset | None:
        """Return the dataset of a scenario: its override or the base dataset."""
        self.get(scenario_id)
        return self._datasets.get(scenario_id) or self._base_dataset

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------
    def compare(self, scenario_ids: Sequence[UUID] | None = None) -> list[dict[str, Any]]:
        """
        Build a parameter comparison table: one row per parameter, one column per scenario.

        Example: [{"parameter": "demand", "Базовый": 300, "Маловодный": 350}, ...]
        """
        scenarios = self.list() if scenario_ids is None else [self.get(sid) for sid in scenario_ids]
        if not scenarios:
            return []

        keys: list[str] = []
        for scenario in scenarios:
            for key in scenario.parameters:
                if key not in keys:
                    keys.append(key)

        rows: list[dict[str, Any]] = []
        for key in keys:
            row: dict[str, Any] = {"parameter": key}
            for scenario in scenarios:
                row[scenario.name] = scenario.parameters.get(key)
            rows.append(row)
        return rows

    def compare_results(self, scenario_ids: Sequence[UUID] | None = None) -> list[dict[str, Any]]:
        """Compare stored calculation results of scenarios."""
        scenarios = self.list() if scenario_ids is None else [self.get(sid) for sid in scenario_ids]
        rows: list[dict[str, Any]] = []
        for scenario in scenarios:
            result = self._results.get(scenario.id)
            rows.append(
                {
                    "scenario": scenario.name,
                    "status": result.metadata.status.value if result is not None else None,
                    "output": dict(result.output_data) if result is not None else {},
                }
            )
        return rows

    # ------------------------------------------------------------------
    # Calculation
    # ------------------------------------------------------------------
    def set_calculation_service(self, service: CalculationService) -> None:
        """Attach (or replace) the calculation service used to run scenarios."""
        self._calculation_service = service

    def run(
        self,
        scenario_id: UUID,
        methodology_qualified_name: str,
        dataset: Dataset | None = None,
    ) -> CalculationResult:
        """
        Run a scenario through `CalculationService` and remember the result.

        Raises:
            CalculationError: when no calculation service or no dataset is available.
        """
        scenario = self.get(scenario_id)
        if self._calculation_service is None:
            raise CalculationError(
                "ScenarioService has no CalculationService attached",
                methodology_qualified_name,
            )
        data = dataset or self.get_dataset(scenario_id)
        if data is None:
            raise CalculationError(
                f"No dataset bound to scenario '{scenario.name}' and no base dataset set",
                methodology_qualified_name,
            )
        result = self._calculation_service.execute(
            methodology=methodology_qualified_name,
            dataset=data,
            parameters=scenario.parameters,
            input_dataset_ids=[data.id],
        )
        self._results[scenario.id] = result
        return result

    def get_result(self, scenario_id: UUID) -> CalculationResult | None:
        """Return the last calculation result of a scenario, if any."""
        self.get(scenario_id)
        return self._results.get(scenario_id)

    # ------------------------------------------------------------------
    # Container protocol
    # ------------------------------------------------------------------
    def __len__(self) -> int:
        return len(self._scenarios)

    def __contains__(self, scenario_id: object) -> bool:
        return isinstance(scenario_id, UUID) and scenario_id in self._scenarios

