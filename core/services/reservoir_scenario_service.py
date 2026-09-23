"""
core/services/reservoir_scenario_service.py
Reservoir Scenario Simulator (P1.7 of DOCS/ROADMAP.md).

Thin orchestration over ScenarioService + CalculationService: creates
`scenario_type="reservoir"` scenarios (demand, V useful, S0, guarantee, mode,
entry year), runs them through the existing `reservoir_regulation` methodology
handler (which delegates to core.hydrorash.reservoir_regulation), and builds
numeric delta tables between two reservoir scenarios.

No mathematics: formulas stay in `core.hydrorash.reservoir_regulation`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from core.domain.models import CalculationResult, Dataset, Scenario
from core.services.scenario_service import ScenarioNotFoundError, ScenarioService

RESERVOIR_SCENARIO_TYPE = "reservoir"
RESERVOIR_METHODOLOGY = "reservoir_regulation"

# Parameters understood by multi_year_regulation / handle_reservoir_regulation.
RESERVOIR_PARAMETERS: frozenset[str] = frozenset(
    {
        "demand_m3_s",
        "V_max_km3",
        "S_0_km3",
        "target_guarantee",
        "mode",
        "year",
    }
)


class ReservoirScenarioError(ValueError):
    """Raised when reservoir scenario parameters or state are invalid."""


class ReservoirScenarioService:
    """Create / run / compare reservoir scenarios on top of ScenarioService."""

    def __init__(self, scenario_service: ScenarioService) -> None:
        self._scenarios = scenario_service

    @property
    def scenario_service(self) -> ScenarioService:
        """Underlying ScenarioService (shared state with the scenario tab)."""
        return self._scenarios

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------
    def create(
        self,
        name: str,
        demand_m3_s: float,
        v_max_km3: float | None = None,
        s0_km3: float | None = None,
        target_guarantee: float = 95.0,
        mode: str = "guarantee_for_volume",
        year: int | None = None,
        description: str = "",
        dataset: Dataset | None = None,
    ) -> Scenario:
        """
        Create a scenario typed as `reservoir` with regulation parameters.

        Raises:
            ReservoirScenarioError: on non-positive demand, empty name or
                non-positive target_guarantee.
        """
        if not name or not name.strip():
            raise ReservoirScenarioError("Reservoir scenario name cannot be empty")
        try:
            demand = float(demand_m3_s)
        except (TypeError, ValueError) as error:
            raise ReservoirScenarioError(
                f"demand_m3_s must be a number: {demand_m3_s!r}"
            ) from error
        if demand <= 0:
            raise ReservoirScenarioError("demand_m3_s must be positive")
        try:
            guarantee = float(target_guarantee)
        except (TypeError, ValueError) as error:
            raise ReservoirScenarioError(
                f"target_guarantee must be a number: {target_guarantee!r}"
            ) from error
        if not (0 < guarantee <= 100):
            raise ReservoirScenarioError("target_guarantee must be in (0, 100]")
        if v_max_km3 is not None and float(v_max_km3) <= 0:
            raise ReservoirScenarioError("V_max_km3 must be positive when provided")
        if s0_km3 is not None and float(s0_km3) < 0:
            raise ReservoirScenarioError("S_0_km3 must be non-negative when provided")
        if v_max_km3 is not None and s0_km3 is not None and float(s0_km3) > float(v_max_km3):
            raise ReservoirScenarioError("S_0_km3 cannot exceed V_max_km3")

        parameters: dict[str, Any] = {
            "demand_m3_s": demand,
            "target_guarantee": guarantee,
            "mode": str(mode),
        }
        if v_max_km3 is not None:
            parameters["V_max_km3"] = float(v_max_km3)
        if s0_km3 is not None:
            parameters["S_0_km3"] = float(s0_km3)
        if year is not None:
            parameters["year"] = int(year)

        return self._scenarios.create(
            name=name.strip(),
            parameters=parameters,
            description=description,
            dataset=dataset,
            scenario_type=RESERVOIR_SCENARIO_TYPE,
        )

    def list_reservoir(self) -> list[Scenario]:
        """Return only scenarios with scenario_type == \"reservoir\"."""
        return [s for s in self._scenarios.list() if s.scenario_type == RESERVOIR_SCENARIO_TYPE]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def run(self, scenario_id: UUID) -> CalculationResult:
        """
        Run a reservoir scenario through the shared ScenarioService.run.

        Raises:
            ScenarioNotFoundError: unknown scenario id.
            ReservoirScenarioError: scenario is not of type `reservoir` or
                lacks required demand_m3_s.
            CalculationError: calculation service / dataset missing or failed.
        """
        scenario = self._scenarios.get(scenario_id)
        if scenario.scenario_type != RESERVOIR_SCENARIO_TYPE:
            raise ReservoirScenarioError(
                f"Scenario '{scenario.name}' is not a reservoir scenario "
                f"(type={scenario.scenario_type})"
            )
        if "demand_m3_s" not in scenario.parameters:
            raise ReservoirScenarioError(
                f"Reservoir scenario '{scenario.name}' is missing demand_m3_s"
            )
        return self._scenarios.run(scenario_id, RESERVOIR_METHODOLOGY)

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------
    def compare_delta(
        self,
        scenario_ids: Sequence[UUID] | None = None,
        baseline_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        """
        Numeric delta table for stored reservoir results (or all scenarios).

        Baseline defaults to the first scenario; other columns include
        `Δ <name>` = value - baseline for each scalar metric.
        """
        return self._scenarios.compare_numeric_results(scenario_ids, baseline_id=baseline_id)

    def series_for(self, scenario_id: UUID) -> list[float]:
        """
        Return the balance_series_km3 output of a run reservoir scenario.

        Raises:
            ScenarioNotFoundError: unknown scenario id.
            ReservoirScenarioError: no result yet or output lacks balance series
                (e.g. natural_supply mode which does not produce it).
        """
        self._scenarios.get(scenario_id)  # raises ScenarioNotFoundError
        result = self._scenarios.get_result(scenario_id)
        if result is None:
            raise ReservoirScenarioError("Scenario has no calculation result yet; run it first")
        series = result.output_data.get("balance_series_km3")
        if series is None:
            raise ReservoirScenarioError(
                "Result has no balance_series_km3 (run mode=guarantee_for_volume)"
            )
        if not isinstance(series, list):
            raise ReservoirScenarioError("balance_series_km3 is not a list")
        return [float(v) for v in series]

    def get(self, scenario_id: UUID) -> Scenario:
        """Delegate to ScenarioService.get (raises ScenarioNotFoundError)."""
        return self._scenarios.get(scenario_id)


__all__ = [
    "RESERVOIR_METHODOLOGY",
    "RESERVOIR_PARAMETERS",
    "RESERVOIR_SCENARIO_TYPE",
    "ReservoirScenarioError",
    "ReservoirScenarioService",
    "ScenarioNotFoundError",
]
