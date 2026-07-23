"""
core/hydrorash/minimal_runoff.py
Модуль расчёта минимального стока (Работа 3)

Перенесено из HydroRash с адаптацией под hydrolib.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from .utils import compute_basic_stats, kritsky_menkel_quantiles


def prepare_minimal_series(
    winter_minimals: pd.Series,
    summer_minimals: pd.Series
) -> Dict[str, pd.Series]:
    """Подготовка рядов минимальных расходов (зима/лето)."""
    return {
        "зима": winter_minimals.dropna(),
        "лето": summer_minimals.dropna()
    }


def compute_minimal_stats(
    minimal_series: Dict[str, pd.Series]
) -> Dict[str, Dict[str, float]]:
    """Расчёт характеристик минимальных расходов (отдельно зима/лето)."""
    stats = {}

    for season, series in minimal_series.items():
        if len(series) < 3:
            stats[season] = {
                "mean": None, "Cv": None, "Cs": None,
                "Cs/Cv": None, "epsilon": None, "n": len(series),
                "reliability_class": "Недостаточно данных"
            }
            continue

        basic = compute_basic_stats(series)
        stats[season] = {
            "mean": basic["mean"],
            "Cv": basic["Cv"],
            "Cs": basic["Cs"],
            "Cs/Cv": basic["Cs/Cv"],
            "epsilon": basic["epsilon"],
            "n": basic["n"],
            "reliability_class": basic["reliability_class"],
            "warnings": basic["warnings"]
        }

    return stats


def calculate_probability_curves(
    stats: Dict[str, Dict[str, float]],
    P_values: Optional[List[float]] = None
) -> Dict[str, pd.DataFrame]:
    """
    Расчёт аналитических кривых обеспеченностей минимальных расходов
    по методу Крицкого-Менкеля (СП 33-101-2003, раздел 7).

    Расчётные обеспеченности: 75%, 80%, 90%, 95%, 97%, 99%
    """
    if P_values is None:
        P_values = [75, 80, 90, 95, 97, 99]

    curves = {}

    for season, s in stats.items():
        if s["mean"] is None or s["Cv"] is None:
            continue

        Cs_over_Cv = s.get("Cs/Cv", 2.0)
        df = kritsky_menkel_quantiles(
            mean=s["mean"],
            Cv=s["Cv"],
            Cs_over_Cv=Cs_over_Cv,
            P_list=P_values
        )
        curves[season] = df

    return curves


def proportional_method(
    short_series: pd.Series,
    analog_series: pd.Series,
    analog_stats: Dict[str, float],
    P_values: Optional[List[float]] = None
) -> pd.DataFrame:
    """
    Метод пропорций для коротких рядов (n < 6).
    Q_p% = (Q_i / Q_i,analog) * Q_p%,analog
    """
    if P_values is None:
        P_values = [75, 80, 90, 95, 97]

    if len(short_series) == 0 or len(analog_series) == 0:
        raise ValueError("Пустые ряды")

    common_idx = short_series.index.intersection(analog_series.index)
    if len(common_idx) == 0:
        raise ValueError("Нет общих лет для расчёта пропорций")

    ratios = short_series.loc[common_idx] / analog_series.loc[common_idx]
    ratios = ratios.replace([np.inf, -np.inf], np.nan).dropna()
    if len(ratios) == 0:
        raise ValueError("Все пропорции оказались бесконечными (деление на ноль в ряде аналога)")
    k_mean = ratios.mean()

    results = []
    for P in P_values:
        km_row = kritsky_menkel_quantiles(
            analog_stats["mean"], analog_stats["Cv"],
            analog_stats.get("Cs/Cv", 2.0), [P]
        )
        Q_analog_p = km_row.iloc[0]["Q_p"]
        Q_p = k_mean * Q_analog_p
        results.append({
            "P_%": P,
            "Q_p (пропорции)": round(Q_p, 2),
            "k_mean": round(k_mean, 3)
        })

    return pd.DataFrame(results)


def compare_methods(
    statistical_q: Dict[float, float],
    proportional_q: pd.DataFrame
) -> pd.DataFrame:
    """Сравнение статистического и пропорционального методов."""
    comparison = []

    for P in proportional_q["P_%"]:
        stat_val = statistical_q.get(P, None)
        prop_val = proportional_q[proportional_q["P_%"] == P]["Q_p (пропорции)"].values[0]

        diff = None
        if stat_val is not None:
            diff = round((prop_val - stat_val) / stat_val * 100, 1)

        comparison.append({
            "P_%": P,
            "Статистический метод": stat_val,
            "Метод пропорций": prop_val,
            "Разница, %": diff
        })

    return pd.DataFrame(comparison)
