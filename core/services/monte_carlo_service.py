"""
core/services/monte_carlo_service.py
Monte Carlo uncertainty propagation (stage P2.1).

Samples named parameters from user-chosen distributions, runs a user model
N times and summarises the output (mean, std, p5/p50/p95, min/max).

Decisions:
- 10.1 (a): distributions are uniform / normal / triangular only.
- 10.2 (a): default N = 1000 (fast for GUI, seedable).

No new runtime dependencies: numpy + stdlib only. Mathematics lives here;
the GUI only configures the request and draws the summary.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from core.domain.models import CalculationMetadata, CalculationResult, Methodology

__all__ = [
    "DEFAULT_N_RUNS",
    "DISTRIBUTIONS",
    "MonteCarloError",
    "MonteCarloRequest",
    "MonteCarloService",
    "ParameterSpec",
    "SummaryStats",
]

#: Decision 10.2 (a): default number of runs.
DEFAULT_N_RUNS = 1000

#: Decision 10.1 (a): minimal distribution set for P2.1.
DISTRIBUTIONS: tuple[str, ...] = ("uniform", "normal", "triangular")


class MonteCarloError(Exception):
    """Invalid Monte Carlo request or failed model evaluation."""


@dataclass(frozen=True)
class ParameterSpec:
    """One input parameter and how it is sampled.

    Distribution-specific keys in ``params``:

    - ``uniform``: ``low``, ``high``
    - ``normal``: ``mean``, ``std``
    - ``triangular``: ``left``, ``mode``, ``right``
    """

    name: str
    distribution: str
    params: Mapping[str, float] = field(default_factory=dict)

    def validate(self) -> None:
        """Raise MonteCarloError if name / distribution / params are invalid."""
        if not self.name or not str(self.name).strip():
            raise MonteCarloError("Имя параметра не может быть пустым")
        dist = str(self.distribution).strip().lower()
        if dist not in DISTRIBUTIONS:
            raise MonteCarloError(
                f"Неизвестное распределение «{self.distribution}»; "
                f"доступны: {', '.join(DISTRIBUTIONS)}"
            )
        values = {str(k).strip().lower(): float(v) for k, v in self.params.items()}
        if dist == "uniform":
            self._require(values, ("low", "high"), dist, self.name)
            if values["low"] >= values["high"]:
                raise MonteCarloError(
                    f"uniform: low < high для «{self.name}» "
                    f"(low={values['low']}, high={values['high']})"
                )
        elif dist == "normal":
            self._require(values, ("mean", "std"), dist, self.name)
            if values["std"] < 0:
                raise MonteCarloError(f"normal: std >= 0 для «{self.name}»")
        else:  # triangular
            self._require(values, ("left", "mode", "right"), dist, self.name)
            left, mode, right = values["left"], values["mode"], values["right"]
            if left > mode or mode > right or left >= right:
                raise MonteCarloError(
                    f"triangular: left <= mode <= right и left < right для "
                    f"«{self.name}» (left={left}, mode={mode}, right={right})"
                )

    @staticmethod
    def _require(
        values: Mapping[str, float], keys: Sequence[str], dist: str, name: str
    ) -> None:
        missing = [k for k in keys if k not in values]
        if missing:
            raise MonteCarloError(f"{dist}: у «{name}» нет ключей {missing}")

    def sample(self, rng: np.random.Generator) -> float:
        """Draw one value from this parameter's distribution."""
        self.validate()
        dist = self.distribution.strip().lower()
        values = {str(k).strip().lower(): float(v) for k, v in self.params.items()}
        if dist == "uniform":
            return float(rng.uniform(values["low"], values["high"]))
        if dist == "normal":
            return float(rng.normal(values["mean"], values["std"]))
        return float(
            rng.triangular(values["left"], values["mode"], values["right"])
        )

    def to_metadata(self) -> dict[str, Any]:
        """Serializable description for provenance / tables."""
        return {
            "name": self.name,
            "distribution": self.distribution,
            "params": {str(k): float(v) for k, v in self.params.items()},
        }


@dataclass(frozen=True)
class MonteCarloRequest:
    """User-facing Monte Carlo settings (parameters, N, seed)."""

    parameters: tuple[ParameterSpec, ...]
    n_runs: int = DEFAULT_N_RUNS
    seed: int | None = None

    def validate(self) -> None:
        """Raise MonteCarloError if N / parameters are invalid."""
        if int(self.n_runs) < 1:
            raise MonteCarloError(f"N должно быть >= 1 (получено {self.n_runs})")
        if not self.parameters:
            raise MonteCarloError("Список параметров пуст")
        names = [p.name for p in self.parameters]
        if len(names) != len(set(names)):
            raise MonteCarloError("Имена параметров должны быть уникальными")
        for spec in self.parameters:
            spec.validate()


@dataclass(frozen=True)
class SummaryStats:
    """Summary of one output sample (stage P2.1)."""

    mean: float
    std: float
    p5: float
    p50: float
    p95: float
    min: float
    max: float
    count: int

    def to_dict(self) -> dict[str, float | int]:
        """Flat dict for tables / provenance."""
        return {
            "mean": self.mean,
            "std": self.std,
            "p5": self.p5,
            "p50": self.p50,
            "p95": self.p95,
            "min": self.min,
            "max": self.max,
            "count": self.count,
        }


class MonteCarloService:
    """Run Monte Carlo uncertainty propagation over a user-supplied model."""

    @staticmethod
    def sample_parameters(
        request: MonteCarloRequest,
        rng: np.random.Generator | None = None,
    ) -> list[dict[str, float]]:
        """Draw ``request.n_runs`` parameter dicts (one per run)."""
        request.validate()
        generator = rng if rng is not None else np.random.default_rng(request.seed)
        draws: list[dict[str, float]] = []
        for _ in range(int(request.n_runs)):
            draw = {spec.name: spec.sample(generator) for spec in request.parameters}
            draws.append(draw)
        return draws

    @staticmethod
    def summarize(values: Sequence[float] | np.ndarray) -> SummaryStats:
        """Compute mean/std/p5/p50/p95/min/max of a sample."""
        array = np.asarray(list(values), dtype=float).ravel()
        if array.size == 0:
            raise MonteCarloError("Пустая выборка — нечего обобщать")
        if not np.all(np.isfinite(array)):
            raise MonteCarloError("В выборке есть NaN/Inf")
        p5, p50, p95 = np.percentile(array, [5.0, 50.0, 95.0])
        return SummaryStats(
            mean=float(np.mean(array)),
            std=float(np.std(array, ddof=1)) if array.size > 1 else 0.0,
            p5=float(p5),
            p50=float(p50),
            p95=float(p95),
            min=float(np.min(array)),
            max=float(np.max(array)),
            count=int(array.size),
        )

    @classmethod
    def run(
        cls,
        model: Callable[[Mapping[str, float]], float],
        request: MonteCarloRequest,
    ) -> CalculationResult:
        """Evaluate ``model`` on ``request.n_runs`` sampled parameter sets.

        The model must return a finite scalar. Failures and invalid requests
        raise ``MonteCarloError``.
        """
        request.validate()
        generator = np.random.default_rng(request.seed)

        outputs = np.empty(int(request.n_runs), dtype=float)
        for i in range(int(request.n_runs)):
            draw = {
                spec.name: spec.sample(generator) for spec in request.parameters
            }
            try:
                value = float(model(draw))
            except MonteCarloError:
                raise
            except Exception as exc:  # user model may raise anything
                raise MonteCarloError(
                    f"Модель вернула ошибку на прогоне {i + 1}: {exc}"
                ) from exc
            if not np.isfinite(value):
                raise MonteCarloError(
                    f"Модель вернула не-конечное значение на прогоне {i + 1}"
                )
            outputs[i] = value

        summary = cls.summarize(outputs)
        distributions = [spec.to_metadata() for spec in request.parameters]
        output: dict[str, Any] = {
            "summary": summary.to_dict(),
            "samples": outputs.tolist(),
            "n_runs": int(request.n_runs),
            "seed": request.seed,
            "distributions": distributions,
        }

        metadata = CalculationMetadata(
            methodology=Methodology(
                name="monte_carlo",
                version="1.0",
                standard="numpy.random",
                description=(
                    f"N={request.n_runs}; seed={request.seed}; "
                    f"params={', '.join(p.name for p in request.parameters)}"
                ),
            ),
            input_parameters={
                "n_runs": int(request.n_runs),
                "seed": request.seed,
                "parameters": distributions,
            },
        )
        metadata.mark_running()
        metadata.mark_completed()
        return CalculationResult(metadata=metadata, output_data=output)
