"""Sequential multi-analog extension workflow for long-term reconstruction."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd

from core.stats.series_extension import multi_analog_extension


@dataclass(frozen=True)
class AnalogExtensionStage:
    """One regression stage applied to an explicit set of target years."""

    name: str
    analogs: dict[str, pd.Series]
    target_years: tuple[int, ...]
    fit_years: tuple[int, ...] | None = None
    n_min: int = 6
    ro_cr: float = 0.7
    ro_over_sigma: float = 2.0
    k_over_sigma: float = 2.0
    y_over_sigma: float = 0.2
    variance_correction: str = "6.9"
    phi: pd.Series | None = None
    random_state: int | None = None


def staged_multi_analog_extension(
    q_calc: pd.Series,
    stages: Sequence[AnalogExtensionStage],
    exclude_negative: bool = True,
) -> dict[str, Any]:
    """Apply sequential regression stages without overwriting observations.

    Each stage fits only on its declared observed ``fit_years`` and writes only
    its declared ``target_years``. This mirrors the staged use of analogs in
    СП 33-101-2003 Appendix A.8 without claiming that the published example is
    reproduced when its raw analog observations are unavailable.
    """
    if not q_calc.index.is_unique:
        raise ValueError("q_calc index должен быть уникальным")
    if not stages:
        raise ValueError("Не задано ни одного этапа восстановления")

    observed = q_calc.astype(float).dropna()
    if observed.empty:
        raise ValueError("q_calc не содержит наблюдённых значений")

    all_years = set(observed.index)
    stage_names: set[str] = set()
    for stage in stages:
        if not stage.name.strip():
            raise ValueError("Название этапа не может быть пустым")
        if stage.name in stage_names:
            raise ValueError(f"Название этапа повторяется: {stage.name}")
        stage_names.add(stage.name)
        if not stage.analogs:
            raise ValueError(f"Этап {stage.name}: не заданы аналоги")
        if not stage.target_years:
            raise ValueError(f"Этап {stage.name}: не заданы годы восстановления")
        all_years.update(stage.target_years)

    try:
        ordered_years = sorted(all_years)
    except TypeError as error:
        raise ValueError("Все годы должны иметь сравнимый тип") from error

    extended = q_calc.astype(float).reindex(ordered_years)
    warnings: list[str] = []
    stage_results: list[dict[str, Any]] = []

    for stage in stages:
        fit = observed if stage.fit_years is None else observed.reindex(stage.fit_years)
        fit = fit.dropna()
        stage_input = fit.reindex(sorted(set(fit.index) | set(stage.target_years)))
        result = multi_analog_extension(
            stage_input,
            stage.analogs,
            n_min=stage.n_min,
            ro_cr=stage.ro_cr,
            ro_over_sigma=stage.ro_over_sigma,
            k_over_sigma=stage.k_over_sigma,
            y_over_sigma=stage.y_over_sigma,
            exclude_negative=exclude_negative,
            variance_correction=stage.variance_correction,
            phi=stage.phi,
            random_state=stage.random_state,
        )
        predictions = result["extended_series"]
        applied: dict[int, float] = {}

        for year in stage.target_years:
            if year not in predictions.index:
                raise ValueError(
                    f"Этап {stage.name}: analog data do not contain year {year}"
                )
            if year in observed.index:
                continue
            value = float(predictions.loc[year])
            if pd.isna(value):
                raise ValueError(
                    f"Этап {stage.name}: analog data do not contain year {year}"
                )
            if exclude_negative and value < 0.0:
                warnings.append(
                    f"Этап {stage.name}: отрицательное значение {year} исключено"
                )
                continue
            extended.loc[year] = value
            applied[year] = value

        stage_results.append(
            {
                "name": stage.name,
                "fit_years": list(fit.index),
                "target_years": list(stage.target_years),
                "applied_years": applied,
                "R": result["R"],
                "coefficients": result["coeffs"],
                "variance_correction": result["variance_correction"],
            }
        )

    unresolved = extended.index[extended.isna()].tolist()
    return {
        "success": not unresolved,
        "observed_years": list(observed.index),
        "extended_series": extended,
        "stages": stage_results,
        "unresolved_years": unresolved,
        "warnings": warnings,
    }


__all__ = ["AnalogExtensionStage", "staged_multi_analog_extension"]
