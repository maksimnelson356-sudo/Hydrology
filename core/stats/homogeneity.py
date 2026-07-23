"""
core/stats/homogeneity.py
Проверка однородности с использованием расширенных таблиц
"""

import numpy as np
from scipy import stats
from typing import Dict

from core.stats.critical_values import get_dixon_critical, get_grubbs_critical


def grubbs_test(data: np.ndarray, alpha: float = 0.05) -> Dict:
    data = np.asarray(data)
    data = data[~np.isnan(data)]
    n = len(data)
    if n < 3:
        return {'significant': False}

    cs = stats.skew(data, bias=False)
    mean = np.mean(data)
    std = np.std(data, ddof=1)

    G = np.max(np.abs(data - mean)) / std
    G_crit = get_grubbs_critical(n, alpha, cs)

    return {
        'significant': G > G_crit,
        'G': round(G, 4),
        'G_critical': round(G_crit, 4),
        'alpha': alpha,
        'cs': round(cs, 3)
    }


def dixon_q_test(data: np.ndarray, alpha: float = 0.05) -> Dict:
    data = np.asarray(data)
    data = data[~np.isnan(data)]
    n = len(data)
    if n < 3:
        return {'significant': False}

    cs = stats.skew(data, bias=False)
    sorted_data = np.sort(data)
    range_val = sorted_data[-1] - sorted_data[0]
    if range_val == 0:
        return {'significant': False, 'Q': 0.0, 'Q_critical': 0.0, 'alpha': alpha, 'cs': round(cs, 3)}
    Q = max(
        (sorted_data[1] - sorted_data[0]) / range_val,
        (sorted_data[-1] - sorted_data[-2]) / range_val
    )

    Q_crit = get_dixon_critical(n, alpha, cs) or 0.22

    return {
        'significant': Q > Q_crit,
        'Q': round(Q, 4),
        'Q_critical': round(Q_crit, 4),
        'alpha': alpha,
        'cs': round(cs, 3)
    }


def check_homogeneity(data: np.ndarray, alpha: float = 0.05) -> Dict:
    grubbs = grubbs_test(data, alpha)
    dixon = dixon_q_test(data, alpha)

    return {
        'grubbs': grubbs,
        'dixon': dixon,
        'is_homogeneous': not (grubbs['significant'] or dixon['significant']),
        'alpha': alpha
    }