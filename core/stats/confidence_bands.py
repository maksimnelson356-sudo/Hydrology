"""
core/stats/confidence_bands.py
Доверительные интервалы кривых обеспеченности (СП 482.1325800.2020)

Основные функции:
- pearson3_confidence_bands — доверительные полосы для кривой Пирсона III
- parametric_bootstrap_ci — бутстреп доверительные интервалы
- quantile_ci — доверительный интервал для квантиля
- epsilon_ci — доверительный интервал для ε
"""

import numpy as np
from typing import Dict, List, Optional
from scipy import stats


def pearson3_confidence_bands(
    data: np.ndarray,
    P_values: Optional[List[float]] = None,
    confidence: float = 0.95,
    n_bootstrap: int = 1000,
) -> Dict:
    """
    Доверительные полосы для кривой Пирсон III (бутстреп).

    Parameters:
        data: массив наблюдений
        P_values: обеспеченности (в долях), по умолчанию стандартные
        confidence: уровень доверия (0.90, 0.95, 0.99)
        n_bootstrap: количество бутстреп-выборок

    Returns:
        Dict: P_values, Q_mean, Q_lower, Q_upper, confidence
    """
    from core.stats.frequency import pearson3_ppf
    from core.stats.parameters import calculate_statistical_parameters

    data = np.array(data, dtype=float)
    data = data[~np.isnan(data)]
    n = len(data)

    if P_values is None:
        P_values = [0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5,
                    0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99, 0.995, 0.999]

    P_arr = np.array(P_values)

    params = calculate_statistical_parameters(data)
    Q_mean = pearson3_ppf(P_arr, params['mean'], params['corrected_cv'], params['corrected_cs'])

    Q_boot = np.zeros((n_bootstrap, len(P_arr)))
    rng = np.random.default_rng(42)

    for b in range(n_bootstrap):
        sample = rng.choice(data, size=n, replace=True)
        try:
            sp = calculate_statistical_parameters(sample)
            Q_boot[b] = pearson3_ppf(P_arr, sp['mean'], sp['corrected_cv'], sp['corrected_cs'])
        except (ValueError, TypeError, ZeroDivisionError):
            Q_boot[b] = Q_mean

    alpha = 1 - confidence
    Q_lower = np.percentile(Q_boot, 100 * alpha / 2, axis=0)
    Q_upper = np.percentile(Q_boot, 100 * (1 - alpha / 2), axis=0)

    return {
        'P_values': P_values,
        'P_percent': [p * 100 for p in P_values],
        'Q_mean': Q_mean.tolist(),
        'Q_lower': Q_lower.tolist(),
        'Q_upper': Q_upper.tolist(),
        'confidence': confidence,
        'n_bootstrap': n_bootstrap,
        'n': n,
    }


def parametric_bootstrap_ci(
    data: np.ndarray,
    P_target: float,
    confidence: float = 0.95,
    n_bootstrap: int = 1000,
) -> Dict:
    """
    Доверительный интервал для квантиля Q(P) методом бутстрепа.

    Parameters:
        data: наблюдения
        P_target: целевая обеспеченность (доля)
        confidence: уровень доверия
        n_bootstrap: число бутстреп-итераций

    Returns:
        Dict: Q_point, Q_lower, Q_upper, std_error
    """
    from core.stats.frequency import pearson3_ppf
    from core.stats.parameters import calculate_statistical_parameters

    data = np.array(data, dtype=float)
    data = data[~np.isnan(data)]
    n = len(data)

    params = calculate_statistical_parameters(data)
    Q_point = pearson3_ppf([P_target], params['mean'], params['corrected_cv'], params['corrected_cs'])[0]

    Q_boot = np.zeros(n_bootstrap)
    rng = np.random.default_rng(42)

    for b in range(n_bootstrap):
        sample = rng.choice(data, size=n, replace=True)
        try:
            sp = calculate_statistical_parameters(sample)
            Q_boot[b] = pearson3_ppf([P_target], sp['mean'], sp['corrected_cv'], sp['corrected_cs'])[0]
        except Exception:
            Q_boot[b] = Q_point

    alpha = 1 - confidence
    Q_lower = float(np.percentile(Q_boot, 100 * alpha / 2))
    Q_upper = float(np.percentile(Q_boot, 100 * (1 - alpha / 2)))
    std_error = float(np.std(Q_boot, ddof=1))

    return {
        'Q_point': round(float(Q_point), 3),
        'Q_lower': round(Q_lower, 3),
        'Q_upper': round(Q_upper, 3),
        'std_error': round(std_error, 3),
        'confidence': confidence,
        'P_target': P_target,
        'n_bootstrap': n_bootstrap,
    }


def quantile_ci_normal(
    data: np.ndarray,
    P_target: float,
    confidence: float = 0.95,
) -> Dict:
    """
    Доверительный интервал для квантиля (нормальное приближение).

    Используется когда n > 30.

    Parameters:
        data: наблюдения
        P_target: обеспеченность (доля)
        confidence: уровень доверия

    Returns:
        Dict: Q_point, Q_lower, Q_upper
    """
    from core.stats.frequency import pearson3_ppf
    from core.stats.parameters import calculate_statistical_parameters

    data = np.array(data, dtype=float)
    data = data[~np.isnan(data)]
    n = len(data)

    params = calculate_statistical_parameters(data)
    Q_point = pearson3_ppf([P_target], params['mean'], params['corrected_cv'], params['corrected_cs'])[0]

    se = params['mean'] * params['corrected_cv'] / np.sqrt(n) if n > 1 else 0

    z = stats.norm.ppf(1 - (1 - confidence) / 2)

    Q_lower = Q_point - z * se
    Q_upper = Q_point + z * se

    return {
        'Q_point': round(float(Q_point), 3),
        'Q_lower': round(float(Q_lower), 3),
        'Q_upper': round(float(Q_upper), 3),
        'std_error': round(float(se), 3),
        'confidence': confidence,
        'P_target': P_target,
        'n': n,
    }
