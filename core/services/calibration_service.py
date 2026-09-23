"""
core/services/calibration_service.py
Parameter calibration via numerical optimization (stage P1.5).

Thin adapter only: builds an objective from the user model + metric, then
calls ``scipy.optimize.minimize`` (already in the stack). Limits, metric and
method are user settings. The service does not invent formulas — metrics live
in ``core.stats.metrics``.

Results are returned as ``CalculationResult`` with provenance in
``output_data`` / ``input_parameters`` (what was fitted, metric, iterations)
and can be applied to an existing scenario through ``ScenarioService``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import numpy as np
from scipy.optimize import minimize

from core.domain.models import CalculationMetadata, CalculationResult, Methodology
from core.services.scenario_service import ScenarioService
from core.stats.metrics import AVAILABLE_METRICS, mse, nse

__all__ = [
    "AVAILABLE_METRICS",
    "CalibrationError",
    "CalibrationRequest",
    "CalibrationService",
]

_METRIC_FUNCS: dict[str, Callable[[Any, Any], float]] = {"mse": mse, "nse": nse}
#: For metrics where lower is better the optimizer minimises f; higher-is-better
#: metrics are turned into ``-f`` inside the objective only.
_MINIMIZE_DIRECTLY = frozenset({"mse"})

MetricName = str
ParamName = str
PredictFn = Callable[[Mapping[ParamName, float]], Sequence[float]]


class CalibrationError(Exception):
    """Invalid calibration request or numerical failure."""


@dataclass(frozen=True)
class CalibrationRequest:
    """User-facing calibration settings (objective, limits, method)."""

    initial: Mapping[ParamName, float]
    bounds: Mapping[ParamName, tuple[float | None, float | None]]
    metric: MetricName = "nse"
    method: str = "L-BFGS-B"
    max_iterations: int = 500


class CalibrationService:
    """Fit named parameters of a user model to an observed series."""

    # ------------------------------------------------------------------
    # Metrics (delegates to core.stats.metrics)
    # ------------------------------------------------------------------
    @staticmethod
    def metric_value(
        observed: Sequence[float],
        predicted: Sequence[float],
        metric: MetricName = "nse",
    ) -> float:
        """Evaluate a registered metric (user-facing name)."""
        fn = _METRIC_FUNCS.get(metric)
        if fn is None:
            raise CalibrationError(
                f"Неизвестная метрика «{metric}»; доступны: {', '.join(AVAILABLE_METRICS)}"
            )
        return float(fn(list(observed), list(predicted)))

    # ------------------------------------------------------------------
    # Calibration
    # ------------------------------------------------------------------
    def calibrate(
        self,
        observed: Sequence[float],
        predict: PredictFn,
        request: CalibrationRequest,
    ) -> CalculationResult:
        """
        Fit ``request.initial`` so that ``predict(params)`` matches ``observed``.

        Raises:
            CalibrationError: invalid limits, unknown metric, shape mismatch,
                empty series, or optimizer failure without a usable solution.
        """
        obs = np.asarray(list(observed), dtype=float).ravel()
        if obs.size == 0:
            raise CalibrationError("Калибровка: пустой наблюдаемый ряд")
        if not np.all(np.isfinite(obs)):
            raise CalibrationError("Калибровка: в наблюдениях есть NaN/Inf")

        names = list(request.initial.keys())
        if not names:
            raise CalibrationError("Калибровка: не заданы начальные параметры")

        metric = request.metric
        if metric not in _METRIC_FUNCS:
            raise CalibrationError(
                f"Неизвестная метрика «{metric}»; доступны: {', '.join(AVAILABLE_METRICS)}"
            )

        x0, lower, upper = self._validate_limits(names, request)

        # Probe the model once at the initial point (shape + metric «before»).
        sim0 = self._predict_array(predict, dict(request.initial), obs.size)
        metric_before = self.metric_value(obs, sim0, metric)

        def objective(x: np.ndarray) -> float:
            params = {name: float(value) for name, value in zip(names, x, strict=True)}
            try:
                sim = self._predict_array(predict, params, obs.size)
                value = self.metric_value(obs, sim, metric)
            except (CalibrationError, ValueError, TypeError, ZeroDivisionError):
                # Keep the optimizer inside the feasible region on user-model errors.
                return 1e30
            return value if metric in _MINIMIZE_DIRECTLY else -value

        try:
            result = minimize(
                objective,
                x0,
                method=request.method,
                bounds=list(zip(lower, upper, strict=True)),
                options={"maxiter": int(request.max_iterations)},
            )
        except Exception as exc:  # scipy raises various types for bad methods
            raise CalibrationError(f"Оптимизация не выполнена: {exc}") from exc

        fitted = {name: float(value) for name, value in zip(names, result.x, strict=True)}
        sim_fit = self._predict_array(predict, fitted, obs.size)
        metric_after = self.metric_value(obs, sim_fit, metric)

        iterations = int(getattr(result, "nit", 0) or 0)
        n_fev = int(getattr(result, "nfev", 0) or 0)
        message = str(getattr(result, "msg", "") or "")

        if not np.all(np.isfinite(result.x)):
            raise CalibrationError(f"Оптимизация не сошлась: {message or 'non-finite solution'}")

        output: dict[str, Any] = {
            "metric": metric,
            "metric_before": metric_before,
            "metric_after": metric_after,
            "parameters_before": {k: float(v) for k, v in request.initial.items()},
            "parameters_after": fitted,
            "bounds": {k: [lo, hi] for k, (lo, hi) in request.bounds.items()},
            "method": request.method,
            "iterations": iterations,
            "function_evaluations": n_fev,
            "success": bool(result.success),
            "message": message,
            "n_points": int(obs.size),
        }

        metadata = CalculationMetadata(
            methodology=Methodology(
                name="calibration",
                version="1.0",
                standard="scipy.optimize",
                description=f"metric={metric}; method={request.method}",
            ),
            input_parameters={
                "calibrated_parameters": list(names),
                "metric": metric,
                "method": request.method,
                "iterations": iterations,
                "metric_before": metric_before,
                "metric_after": metric_after,
                "initial": {k: float(v) for k, v in request.initial.items()},
            },
        )
        metadata.mark_running()
        metadata.mark_completed()
        return CalculationResult(metadata=metadata, output_data=output)

    # ------------------------------------------------------------------
    # Scenario integration
    # ------------------------------------------------------------------
    @staticmethod
    def apply_to_scenario(
        scenarios: ScenarioService,
        scenario_id: UUID,
        parameters: Mapping[str, float],
    ) -> Any:
        """
        Write calibrated parameters into an existing scenario.

        Rollback is the scenario editor's job: store the previous mapping and
        call ``ScenarioService.update`` again with the old values (or reset
        parameters by creating a clone without the fitted keys).
        """
        if not parameters:
            raise CalibrationError("Нечего применять: пустой набор параметров")
        return scenarios.update(scenario_id, parameters=dict(parameters))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_limits(
        names: list[str],
        request: CalibrationRequest,
    ) -> tuple[np.ndarray, list[float], list[float]]:
        """Validate bounds against initial values; return x0 and flat limit lists."""
        missing = [name for name in names if name not in request.bounds]
        if missing:
            raise CalibrationError(
                f"Не заданы limits для параметров: {', '.join(missing)}"
            )

        x0: list[float] = []
        lower: list[float] = []
        upper: list[float] = []
        for name in names:
            lo_raw, hi_raw = request.bounds[name]
            lo = float(lo_raw) if lo_raw is not None else float("-inf")
            hi = float(hi_raw) if hi_raw is not None else float("inf")
            if not np.isfinite(lo) and lo_raw is not None:
                lo = float("-inf")
            if not np.isfinite(hi) and hi_raw is not None:
                hi = float("inf")
            if lo > hi:
                raise CalibrationError(
                    f"Некорректные limits «{name}»: lower ({lo}) > upper ({hi})"
                )
            value = float(request.initial[name])
            if value < lo or value > hi:
                raise CalibrationError(
                    f"Начальное значение «{name}»={value} вне limits [{lo}, {hi}]"
                )
            x0.append(value)
            lower.append(lo)
            upper.append(hi)
        return np.asarray(x0, dtype=float), lower, upper

    @staticmethod
    def _predict_array(
        predict: PredictFn,
        params: Mapping[str, float],
        expected_size: int,
    ) -> np.ndarray:
        """Run the user model and enforce a finite series of the expected length."""
        try:
            raw = predict(params)
        except CalibrationError:
            raise
        except Exception as exc:
            raise CalibrationError(f"Модель не смогла предсказать: {exc}") from exc
        sim = np.asarray(list(raw), dtype=float).ravel()
        if sim.size != expected_size:
            raise CalibrationError(
                f"Модель вернула {sim.size} значений, ожидалось {expected_size}"
            )
        if not np.all(np.isfinite(sim)):
            raise CalibrationError("Модель вернула NaN/Inf")
        return sim
