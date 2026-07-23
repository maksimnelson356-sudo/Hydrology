"""
core/stats/frequency.py
Расчёт кривых обеспеченности:
- Пирсона III типа (формула Корниша-Фишера)
- Крицкого-Менкеля (табличный метод + трёхпараметрическое гамма)
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


def pearson3_ppf(probabilities: np.ndarray, mean: float, cv: float, cs: float) -> np.ndarray:
    """
    Квантили распределения Пирсона III типа (Крицкий-Менкель)
    через формулу Корниша-Фишера.

    X_p = X̄ · (1 + Cv · Φ_mod)

    где Φ_mod — модифицированный нормальный квантиль с учётом Cs:
    Φ_mod = Φ + (Cs/6)·(Φ²-1) + (Cs²/36)·(2Φ³-5Φ) - (Cs³/216)·(Φ⁴-17Φ²+16)
    """
    probabilities = np.asarray(probabilities, dtype=float)
    cv = max(abs(cv), 0.001)
    cs = float(cs)

    # Квантили нормального распределения (1 - P для перевода из обеспеченности)
    phi = stats.norm.ppf(1 - probabilities)

    # Формула Корниша-Фишера (расширение до 4-го порядка)
    phi_mod = (phi
               + (cs / 6.0) * (phi ** 2 - 1.0)
               + (cs ** 2 / 36.0) * (2.0 * phi ** 3 - 5.0 * phi)
               - (cs ** 3 / 216.0) * (2.0 * phi ** 4 - 17.0 * phi ** 2 + 16.0))

    return mean * (1.0 + cv * phi_mod)


def kritsky_menkel_ppf(probabilities: np.ndarray, mean: float, cv: float, cs: float) -> np.ndarray:
    """
    Квантили распределения Крицкого-Менкеля.

    1) Если Cs/Cv ∈ поддерживаемым таблицам — используем табличный метод
       (интерполяция из kritsky_tables.py, наиболее точный).
    2) Иначе — трёхпараметрическое гамма-распределение:
       α = 4/Cs²,  β = X̄·Cv·Cs/2,  A₀ = X̄·(1 - 2Cv/Cs)
       X_p = A₀ + Gamma(α, β)
    """
    probabilities = np.asarray(probabilities, dtype=float)
    cv = max(abs(cv), 0.001)
    cs = float(cs)
    if abs(cs) < 0.001:
        cs = 0.001

    # --- Попытка табличного метода ---
    cs_cv = abs(cs / cv) if cv > 0 else 2.0
    try:
        from core.stats.kritsky_tables import get_ordinates, PROBS
        ordinates = get_ordinates(cs_cv, cv)
        # Интерполяция по обеспеченностям
        quantiles = mean * np.interp(probabilities, PROBS, ordinates)
        # Проверяем разумность (все квантили > 0 для расходов)
        if np.all(quantiles > 0):
            return quantiles
    except Exception:
        pass

    # --- Трёхпараметрическое гамма-распределение ---
    alpha = 4.0 / (cs ** 2)                          # параметр формы
    beta = mean * cv * abs(cs) / 2.0                  # параметр масштаба
    A0 = mean * (1.0 - 2.0 * cv / cs)               # начальная точка (сдвиг)

    try:
        quantiles = A0 + stats.gamma.ppf(1 - probabilities, a=alpha, scale=beta)
    except Exception:
        # Fallback на формулу Корниша-Фишера
        quantiles = pearson3_ppf(probabilities, mean, cv, cs)

    return quantiles


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
    except Exception:
        p3 = None

    # Gamma
    try:
        params = stats.gamma.fit(Q, floc=0)
        g = stats.gamma.ppf(1 - probabilities, *params)
    except Exception:
        g = None

    # Lognormal
    try:
        params = stats.lognorm.fit(Q, floc=0)
        ln = stats.lognorm.ppf(1 - probabilities, *params)
    except Exception:
        ln = None

    # Normal
    try:
        params = stats.norm.fit(Q)
        n = stats.norm.ppf(1 - probabilities, *params)
    except Exception:
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
        sorted_data = np.sort(data)
        n = len(sorted_data)
        emp_probs = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
        quantiles = np.interp(probabilities, emp_probs, sorted_data)

    elif curve_type == "none":
        quantiles = np.full_like(probabilities, np.nan)
    else:
        std = params['std']
        quantiles = stats.norm.ppf(1 - probabilities, loc=mean, scale=std)

    return pd.DataFrame({
        'P_%': np.round(probabilities * 100, 2),
        'Q': np.round(quantiles, 2)
    })