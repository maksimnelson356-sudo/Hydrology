"""
core/stats/frequency.py
Расчёт кривых обеспеченности:
- Пирсона III типа (точная функция распределения scipy)
- Крицкого-Менкеля (трёхпараметрическое гамма-распределение)
- Нормальное распределение
- Эмпирическая кривая
"""

import math
import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, Optional, Literal


CurveType = Literal[
    "pearson3",
    "kritsky_menkel",
    "normal",
    "empirical",
    "none"
]


def fit_pearson3(data: np.ndarray) -> Dict:
    from core.stats.parameters import calculate_statistical_parameters
    result = calculate_statistical_parameters(data)
    return {
        'mean': result['mean'],
        'std': result['std'],
        'cv': result['cv'],
        'skew': result['cs'],
        'n': result['n'],
        'r1': result['r1']
    }


def empirical_plotting_positions(data: np.ndarray) -> tuple:
    """
    Эмпирические точки кривой обеспеченности (формула Каннана).

    Ряд сортируется по убыванию (m=1 — максимальный член),
    обеспеченность каждого члена: P_m = (m - 0.3)/(n + 0.4) [0..1].

    Returns:
        (q_desc, p_exceed): отсортированный по убыванию ряд и его
        эмпирические обеспеченности (вероятности превышения).
    """
    data = np.asarray(data, dtype=float)
    q_desc = np.sort(data)[::-1]
    n = len(q_desc)
    p_exceed = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
    return q_desc, p_exceed


def pearson3_ppf(probabilities: np.ndarray, mean: float, cv: float, cs: float) -> np.ndarray:
    """
    Квантили распределения Пирсона III типа.

    X_p = X̄ + σ · z_p,  σ = X̄ · Cv

    где z_p — квантиль стандартизированного распределения Пирсона III
    (с нулевым средним, единичным СКО и заданной асимметрией Cs).
    Используется точная функция распределения scipy (в отличие от
    приближения Корниша-Фишера, которое не работает при больших Cs).

    Отрицательные квантили (нижний хвост при Cs < 0 и больших P)
    обрезаются до нуля, как это делает эталонная программа.
    """
    probabilities = np.asarray(probabilities, dtype=float)
    cv = max(abs(cv), 0.001)
    cs = float(cs)

    quantiles = stats.pearson3.ppf(
        1 - probabilities, skew=cs, loc=mean, scale=mean * cv
    )

    return np.maximum(quantiles, 0.0)


def kritsky_menkel_ppf(probabilities: np.ndarray, mean: float, cv: float, cs: float) -> np.ndarray:
    """
    Квантили распределения Крицкого-Менкеля.

    Основной метод — трёхпараметрическое гамма-распределение:
       α = 4/Cs²,  β = X̄·Cv·Cs/2,  A₀ = X̄·(1 - 2Cv/Cs)
       X_p = A₀ + Gamma(α, β)

    Совпадает с эталонной программой HydroStatCalc (таблицы KritkMenc.bin)
    в пределах погрешности таблиц. Отрицательные квантили обрезаются до нуля.
    """
    probabilities = np.asarray(probabilities, dtype=float)
    cv = max(abs(cv), 0.001)
    cs = float(cs)
    if abs(cs) < 0.001:
        cs = 0.001

    # --- Трёхпараметрическое гамма-распределение ---
    alpha = 4.0 / (cs ** 2)                          # параметр формы
    beta = mean * cv * abs(cs) / 2.0                  # параметр масштаба
    A0 = mean * (1.0 - 2.0 * cv / cs)               # начальная точка (сдвиг)

    try:
        quantiles = A0 + stats.gamma.ppf(1 - probabilities, a=alpha, scale=beta)
    except (ValueError, TypeError, RuntimeError):
        # Fallback на формулу Корниша-Фишера
        quantiles = pearson3_ppf(probabilities, mean, cv, cs)

    return np.maximum(quantiles, 0.0)


def fit_theoretical_distributions(Q: np.ndarray, p_prob: np.ndarray) -> dict:
    """
    Подгоняет несколько теоретических распределений к данным.

    Parameters:
        Q: массив расходов
        p_prob: массив вероятностей (0–1) для квантилей

    Returns:
        dict: {название: массив_квантилей или None}
    """
    probabilities = np.asarray(p_prob, dtype=float)

    # Pearson III (скью-нормальное)
    try:
        params = stats.pearson3.fit(Q)
        p3 = stats.pearson3.ppf(1 - probabilities, *params)
    except (ValueError, TypeError):
        p3 = None

    # Gamma
    try:
        params = stats.gamma.fit(Q, floc=0)
        g = stats.gamma.ppf(1 - probabilities, *params)
    except (ValueError, TypeError):
        g = None

    # Lognormal
    try:
        params = stats.lognorm.fit(Q, floc=0)
        ln = stats.lognorm.ppf(1 - probabilities, *params)
    except (ValueError, TypeError):
        ln = None

    # Normal
    try:
        params = stats.norm.fit(Q)
        n = stats.norm.ppf(1 - probabilities, *params)
    except (ValueError, TypeError):
        n = None

    return {
        "pearson3": p3,
        "gamma": g,
        "lognormal": ln,
        "normal": n
    }


def calculate_frequency_curve(
    data: np.ndarray,
    probabilities: Optional[np.ndarray] = None,
    curve_type: CurveType = "pearson3",
    use_corrected: bool = True
) -> pd.DataFrame:
    """
    Построение кривой обеспеченности разных типов.
    """
    if probabilities is None:
        probabilities = np.array([0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 0.99])

    from core.stats.parameters import calculate_statistical_parameters
    params = calculate_statistical_parameters(data)

    mean = params['mean']
    cv = params['corrected_cv'] if use_corrected else params['cv']
    cs = params['corrected_cs'] if use_corrected else params['cs']

    if curve_type == "normal":
        std = params['std']
        quantiles = stats.norm.ppf(1 - probabilities, loc=mean, scale=std)

    elif curve_type == "pearson3":
        # Распределение Пирсона III типа — формула Корниша-Фишера
        quantiles = pearson3_ppf(probabilities, mean, cv, cs)

    elif curve_type == "kritsky_menkel":
        # Распределение Крицкого-Менкеля — табличный метод / трёхпараметрическое гамма
        quantiles = kritsky_menkel_ppf(probabilities, mean, cv, cs)

    elif curve_type == "empirical":
        # Ряд сортируется по убыванию: m=1 — максимальный член ряда,
        # эмпирическая обеспеченность P_m = (m - 0.3)/(n + 0.4).
        q_desc = np.sort(data)[::-1]
        n = len(q_desc)
        emp_probs = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
        quantiles = np.interp(probabilities, emp_probs, q_desc,
                              left=q_desc[0], right=q_desc[-1])

    elif curve_type == "none":
        quantiles = np.full_like(probabilities, np.nan)
    else:
        std = params['std']
        quantiles = stats.norm.ppf(1 - probabilities, loc=mean, scale=std)

    return pd.DataFrame({
        'P_%': np.round(probabilities * 100, 2),
        'Q': np.round(quantiles, 2)
    })