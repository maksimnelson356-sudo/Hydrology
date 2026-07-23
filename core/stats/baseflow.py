"""
core/stats/baseflow.py
Фильтрация базового стока (baseflow separation)

Основные функции:
- baseflow_straight_line — прямолинейное разделение
- baseflow_digital_filter — цифровой фильтр ( Boughton / Eckhardt)
- baseflow_lyne_hollick — фильтр Лайна-Холлика
- baseflow_statistics — статистика базового стока
"""

import numpy as np
from typing import Dict, Optional


def baseflow_straight_line(
    Q: np.ndarray,
    min_separation: int = 5,
) -> Dict:
    """
    Прямолинейное разделение стока на поверхностный и подземный.

    Простой метод: базовый сток = линия от начала паводка до точки
    пересечения с восходящей ветвью следующего паводка.

    Parameters:
        Q: суточные расходы, м3/с
        min_separation: минимальный интервал между пиками

    Returns:
        Dict: baseflow, surface_flow, ratio
    """
    Q = np.array(Q, dtype=float)
    n = len(Q)

    baseflow = np.zeros(n)

    peaks = []
    for i in range(1, n - 1):
        if Q[i] > Q[i - 1] and Q[i] > Q[i + 1]:
            peaks.append(i)

    if len(peaks) < 2:
        baseflow = Q * 0.3
        return {
            'baseflow': baseflow.tolist(),
            'surface_flow': (Q - baseflow).tolist(),
            'baseflow_ratio': 0.3,
        }

    for i in range(len(peaks) - 1):
        p1 = peaks[i]
        p2 = peaks[i + 1]
        if p2 - p1 > min_separation:
            slope = (Q[p2] - Q[p1]) / (p2 - p1)
            for j in range(p1, p2 + 1):
                baseflow[j] = Q[p1] + slope * (j - p1)
        else:
            baseflow[p1:p2 + 1] = min(Q[p1], Q[p2])

    baseflow = np.maximum(baseflow, 0)
    baseflow = np.minimum(baseflow, Q)

    surface = Q - baseflow
    ratio = float(np.mean(baseflow) / np.mean(Q)) if np.mean(Q) > 0 else 0

    return {
        'baseflow': baseflow.tolist(),
        'surface_flow': surface.tolist(),
        'baseflow_ratio': round(ratio, 3),
    }


def baseflow_digital_filter(
    Q: np.ndarray,
    alpha: float = 0.925,
    threshold: float = 0.9,
    passes: int = 3,
) -> Dict:
    """
    Цифровой фильтр базового стока ( Boughton, 1968; Eckhardt, 2005).

    q_b(t) = α × q_b(t-1) + (1-α) × Q(t)

    Parameters:
        Q: суточные расходы
        alpha: коэффициент фильтра (0.9–0.99)
        threshold: порог для определения пика
        passes: количество проходов (1–3)

    Returns:
        Dict: baseflow, surface_flow, ratio
    """
    Q = np.array(Q, dtype=float)
    n = len(Q)

    bf = np.zeros(n)
    bf[0] = Q[0] * 0.5

    for _ in range(passes):
        for i in range(1, n):
            if Q[i] < bf[i - 1]:
                bf[i] = alpha * bf[i - 1] + (1 - alpha) * Q[i]
            else:
                bf[i] = bf[i - 1] if Q[i] < bf[i - 1] * threshold else Q[i] * 0.5

    bf = np.maximum(bf, 0)
    bf = np.minimum(bf, Q)

    surface = Q - bf
    ratio = float(np.mean(bf) / np.mean(Q)) if np.mean(Q) > 0 else 0

    return {
        'baseflow': bf.tolist(),
        'surface_flow': surface.tolist(),
        'baseflow_ratio': round(ratio, 3),
    }


def baseflow_lyne_hollick(
    Q: np.ndarray,
    a: float = 0.97,
) -> Dict:
    """
    Фильтр Лайна-Холлика (1979) — быстрый цифровой фильтр.

    q_b(t) = a × q_b(t-1) + ((1-a)/2) × (Q(t) + Q(t-1))

    Parameters:
        Q: суточные расходы
        a: коэффициент фильтра (0.9–0.997)

    Returns:
        Dict: baseflow, surface_flow, ratio
    """
    Q = np.array(Q, dtype=float)
    n = len(Q)

    bf = np.zeros(n)
    bf[0] = Q[0] * 0.5

    for i in range(1, n):
        bf[i] = a * bf[i - 1] + ((1 - a) / 2) * (Q[i] + Q[i - 1])
        bf[i] = min(bf[i], Q[i])

    bf = np.maximum(bf, 0)

    surface = Q - bf
    ratio = float(np.mean(bf) / np.mean(Q)) if np.mean(Q) > 0 else 0

    return {
        'baseflow': bf.tolist(),
        'surface_flow': surface.tolist(),
        'baseflow_ratio': round(ratio, 3),
    }


def baseflow_statistics(
    Q: np.ndarray,
    baseflow: np.ndarray,
) -> Dict:
    """
    Статистика базового стока.

    Parameters:
        Q: расходы
        baseflow: базовый сток

    Returns:
        Dict: bf_mean, bf_min, bf_max, bf_ratio, reliability
    """
    Q = np.array(Q, dtype=float)
    bf = np.array(baseflow, dtype=float)

    bf_mean = float(np.mean(bf))
    bf_min = float(np.min(bf))
    bf_max = float(np.max(bf))
    bf_ratio = bf_mean / np.mean(Q) if np.mean(Q) > 0 else 0

    bf_stable_days = np.sum(np.abs(np.diff(bf)) < np.std(bf) * 0.1)
    reliability = bf_stable_days / len(bf) * 100 if len(bf) > 0 else 0

    return {
        'bf_mean_m3_s': round(bf_mean, 3),
        'bf_min_m3_s': round(bf_min, 3),
        'bf_max_m3_s': round(bf_max, 3),
        'bf_ratio': round(float(bf_ratio), 3),
        'reliability_percent': round(float(reliability), 1),
    }
