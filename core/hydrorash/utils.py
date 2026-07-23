"""
core/hydrorash/utils.py
Общие утилиты для гидрологических расчётов

Перенесено из HydroRash с адаптацией под hydrolib.
Основные функции:
- compute_basic_stats — статистические характеристики ряда
- linear_regression_reduction — приведение ряда по аналогу
- extend_series — продление ряда
- empirical_probability — эмпирическая кривая обеспеченностей
- kritsky_menkel_quantiles — аналитическая кривая Крицкого-Менкеля
- module_layer — расчёт модуля, объёма и слоя стока
"""

import numpy as np
import pandas as pd
from scipy.stats import pearson3, linregress
from typing import Dict, List, Optional, Tuple


def compute_basic_stats(
    Q: pd.Series,
    r: Optional[float] = None,
    ddof: int = 1,
    use_normative_Cs: bool = True
) -> Dict:
    """
    Расчёт основных статистических характеристик ряда годового стока
    согласно СП 33-101-2003 и СП 529.1325800.2023.

    Parameters:
        Q: ряд расходов
        r: коэффициент автокорреляции (если None — рассчитывается)
        ddof: степени свободы для СКО
        use_normative_Cs: использовать нормативное Cs = 2×Cv (СП 33-101-2003 п. 6.3.3)

    Returns:
        Словарь со статистическими характеристиками
    """
    n = len(Q)
    mean = float(Q.mean())
    std = float(Q.std(ddof=ddof))
    Cv = std / mean if mean != 0 else 0.0
    Cs_empirical = float(pd.Series(Q).skew())

    # СП 33-101-2003 п. 6.3.3: для годового стока рекомендуется Cs = 2×Cv
    if use_normative_Cs:
        Cs = 2.0 * Cv
    else:
        Cs = Cs_empirical

    # Автокорреляция
    if r is None and len(Q) > 2:
        r = float(np.corrcoef(Q.iloc[1:], Q.shift(1).dropna())[0, 1])
    elif r is None:
        r = 0.0

    K_r = np.sqrt((1 + r) / (1 - r)) if 0 <= r < 1 else 1.0
    epsilon = (Cv / np.sqrt(n)) * K_r * 100.0

    # Проверки по СП 33-101-2003 п. 6.2.2 и 6.2.4
    warnings = []
    reliability_class = "Надёжная"

    if n < 10:
        warnings.append("⚠️ КРИТИЧНО: Длина ряда < 10 лет. Расчёты ненадёжны (СП 33-101-2003 п. 6.2.2)")
        reliability_class = "Ненадёжная"
    elif n < 15:
        warnings.append("⚠️ ВНИМАНИЕ: Длина ряда < 15 лет. Рекомендуется удлинение (СП 33-101-2003 п. 6.2.2)")
        reliability_class = "Пониженная надёжность"

    if epsilon > 15:
        warnings.append(f"⚠️ εQ = {epsilon:.1f}% > 15%. Требуется удлинение ряда (СП 33-101-2003 п. 6.2.4)")
        reliability_class = "Ненадёжная"
    elif epsilon > 10:
        warnings.append(f"⚠️ εQ = {epsilon:.1f}% > 10%. Желательно удлинение ряда (СП 33-101-2003 п. 6.2.4)")
        if reliability_class == "Надёжная":
            reliability_class = "Пониженная надёжность"

    return {
        "n": n,
        "mean": mean,
        "std": std,
        "Cv": Cv,
        "Cs": Cs,
        "Cs_empirical": Cs_empirical,
        "Cs/Cv": Cs / Cv if Cv != 0 else 0.0,
        "r": r,
        "epsilon": epsilon,
        "warnings": warnings,
        "reliability_class": reliability_class,
        "normative": "СП 33-101-2003, СП 529.1325800.2023"
    }


def linear_regression_reduction(
    Q_calc: pd.Series,
    Q_analog: pd.Series
) -> Dict[str, float]:
    """
    Линейная регрессия для приведения ряда к многолетнему периоду.

    Parameters:
        Q_calc: ряд расчётной реки
        Q_analog: ряд реки-аналога

    Returns:
        {'a': slope, 'b': intercept, 'R': corr, 'n_common': int}
    """
    common_idx = Q_calc.index.intersection(Q_analog.index)
    if len(common_idx) < 2:
        raise ValueError("Недостаточно общих лет для регрессии (нужно ≥ 2)")

    Qc = Q_calc.loc[common_idx]
    Qa = Q_analog.loc[common_idx]
    result = linregress(Qa.values, Qc.values)

    return {
        "a": result.slope,
        "b": result.intercept,
        "R": result.rvalue,
        "n_common": len(common_idx)
    }


def extend_series(Q_calc: pd.Series, Q_analog: pd.Series, reg: Dict) -> pd.Series:
    """
    Продление ряда расчётной реки по данным аналога.

    Parameters:
        Q_calc: ряд расчётной реки (короткий)
        Q_analog: ряд реки-аналога (длинный)
        reg: результат linear_regression_reduction

    Returns:
        Продлённый ряд
    """
    Q_ext = Q_analog.astype(float).copy()
    common = Q_calc.index.intersection(Q_analog.index)
    Q_ext.loc[common] = Q_calc.loc[common]

    missing = Q_analog.index.difference(Q_calc.index)
    if len(missing) > 0:
        Q_ext.loc[missing] = reg["a"] * Q_analog.loc[missing] + reg["b"]

    return Q_ext


def empirical_probability(Q: pd.Series) -> pd.DataFrame:
    """
    Эмпирическая кривая обеспеченностей.

    Returns:
        DataFrame с колонками Q, P_%
    """
    Q_sorted = Q.sort_values(ascending=False).reset_index(drop=True)
    P = np.arange(1, len(Q_sorted) + 1) / len(Q_sorted) * 100
    return pd.DataFrame({"Q": Q_sorted, "P_%": P})


def kritsky_menkel_quantiles(
    mean: float,
    Cv: float,
    Cs_over_Cv: float,
    P_list: Optional[List[float]] = None
) -> pd.DataFrame:
    """
    Аналитическая кривая обеспеченностей по методу Крицкого-Менкеля
    (СП 33-101-2003 п. 6.4).

    Parameters:
        mean: среднее многолетнее
        Cv: коэффициент вариации
        Cs_over_Cv: отношение Cs/Cv
        P_list: список обеспеченностей (по умолчанию — нормативные точки)

    Returns:
        DataFrame: P_%, Φp, kp, Q_p
    """
    if P_list is None:
        P_list = [0.1, 1, 3, 5, 10, 25, 50, 75, 90, 95, 97, 99, 99.9]

    Cs = Cv * Cs_over_Cv
    results = []

    for P in P_list:
        try:
            t = pearson3.ppf(1 - P / 100, skew=Cs, loc=0, scale=1)
        except Exception:
            t = 0.0
        kp = 1 + Cv * t
        results.append({"P_%": P, "Φp": t, "kp": kp, "Q_p": mean * kp})

    return pd.DataFrame(results)


def module_layer(Qmean: float, F: float) -> Dict[str, float]:
    """
    Расчёт модуля, объёма и слоя стока.

    Parameters:
        Qmean: средний расход, м³/с
        F: площадь водосбора, км²

    Returns:
        {'q': модуль (л/с·км²), 'W': объём (км³), 'h': слой (мм)}
    """
    if F <= 0:
        return {"q": 0.0, "W": 0.0, "h": 0.0}
    return {
        "q": Qmean * 1000 / F,
        "W": Qmean * 31.536 / 1000,
        "h": Qmean * 31536 / F
    }
