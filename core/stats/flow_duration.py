"""
core/stats/flow_duration.py
Кривая длительностей (Flow Duration Curve, FDC) — СП 32.13330.2018

Основные функции:
- flow_duration_curve — построение FDC
- fdc_percentiles — перцентили FDC (Q10, Q50, Q90 и т.д.)
- fdc_slope指数 — показатели формы FDC (n-value, Q90/Q10)
- flow_regime_classification — классификация режима по FDC
- exceedance_probability — вероятность превышения расхода
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from scipy import stats


def flow_duration_curve(
    Q: np.ndarray,
    exceedance_probs: Optional[List[float]] = None,
) -> Dict:
    """
    Построение кривой длительностей (FDC).

    Показывает % времени, когда расход Q ≥ заданного.

    Parameters:
        Q: массив среднегодовых (суточных/месячных) расходов, м3/с
        exceedance_probs: обеспеченности (в долях), по умолчанию 1-99%

    Returns:
        Dict: Q_values, P_values, dataframe
    """
    Q = np.array(Q, dtype=float)
    Q = Q[~np.isnan(Q)]
    Q = np.sort(Q)[::-1]

    n = len(Q)

    if exceedance_probs is None:
        exceedance_probs = [0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5,
                            0.6, 0.7, 0.8, 0.9, 0.95, 0.99]

    Q_interp = np.interp(exceedance_probs,
                         np.linspace(0, 1, n), Q)

    df = pd.DataFrame({
        'P_exceedance': exceedance_probs,
        'P_percent': [p * 100 for p in exceedance_probs],
        'Q_m3_s': np.round(Q_interp, 3),
    })

    return {
        'P_values': exceedance_probs,
        'Q_values': Q_interp.tolist(),
        'dataframe': df,
        'n': n,
        'Q_min': float(np.min(Q)),
        'Q_max': float(np.max(Q)),
        'Q_mean': float(np.mean(Q)),
    }


def fdc_percentiles(
    Q: np.ndarray,
    percentiles: Optional[List[float]] = None,
) -> Dict:
    """
    Перцентили кривой длительностей.

    Parameters:
        Q: массив расходов
        percentiles: список перцентилей (по умолчанию 5, 10, 25, 50, 75, 90, 95)

    Returns:
        Dict: {P5: Q_value, P10: Q_value, ...}
    """
    if percentiles is None:
        percentiles = [5, 10, 25, 50, 75, 90, 95]

    Q = np.array(Q, dtype=float)
    Q = Q[~np.isnan(Q)]

    result = {}
    for p in percentiles:
        q = np.percentile(Q, 100 - p)
        result[f'Q{p}'] = round(float(q), 3)

    return result


def fdc_slope_index(
    Q: np.ndarray,
) -> Dict:
    """
    Показатели формы FDC.

    n-value (параметр формы FDC):
    n = (log(Q2) - log(Q98)) / (log(t98) - log(t2))

    Q90/Q10 — отношение показателей (характеристика стабильности стока)

    Parameters:
        Q: массив расходов

    Returns:
        Dict: n_value, Q90_Q10_ratio, Q50_Q90_ratio, variability
    """
    Q = np.array(Q, dtype=float)
    Q = Q[~np.isnan(Q)]

    Q10 = np.percentile(Q, 90)
    Q50 = np.percentile(Q, 50)
    Q90 = np.percentile(Q, 10)

    if Q90 > 0:
        ratio_90_10 = Q10 / Q90
    else:
        ratio_90_10 = float('inf')

    if Q90 > 0:
        ratio_50_90 = Q50 / Q90
    else:
        ratio_50_90 = float('inf')

    Q2 = np.percentile(Q, 98)
    Q98 = np.percentile(Q, 2)

    if Q98 > 0 and Q2 > 0:
        n_value = (np.log(Q2) - np.log(Q98)) / (np.log(0.98) - np.log(0.02))
    else:
        n_value = 0

    cv = float(np.std(Q, ddof=1) / np.mean(Q)) if np.mean(Q) > 0 else 0

    return {
        'n_value': round(float(n_value), 4),
        'Q90_Q10_ratio': round(float(ratio_90_10), 2),
        'Q50_Q90_ratio': round(float(ratio_50_90), 2),
        'Q10': round(float(Q10), 3),
        'Q50': round(float(Q50), 3),
        'Q90': round(float(Q90), 3),
        'Cv': round(cv, 3),
    }


def flow_regime_classification(
    Q: np.ndarray,
) -> Dict:
    """
    Классификация режима реки по форме FDC (методинг РГГМУ).

    По показателю n и Cv определяется тип режима:
    - Высокий сток (нестабильный): n > 1.5, Cv > 0.5
    - Средний сток: 0.5 < n < 1.5
    - Низкий сток (стабильный): n < 0.5, Cv < 0.3

    Parameters:
        Q: суточные расходы за несколько лет

    Returns:
        Dict: regime_type, n_value, Cv, Q10, Q50, Q90, description
    """
    slope = fdc_slope_index(Q)

    n = slope['n_value']
    cv = slope['Cv']
    ratio = slope['Q90_Q10_ratio']

    if cv > 0.6 or n > 1.5:
        regime = 'highly_variable'
        desc = 'Нестабильный режим (высокие паводки, низкая межень)'
    elif cv > 0.4 or n > 0.8:
        regime = 'moderate'
        desc = 'Умеренно стабильный режим'
    else:
        regime = 'stable'
        desc = 'Стабильный режим (хорошая грунтовая подпитка)'

    if ratio > 10:
        desc += ' | Сильная меженная подпитка'
    elif ratio < 3:
        desc += ' | Слабая меженная подпитка'

    return {
        'regime_type': regime,
        'description': desc,
        'n_value': slope['n_value'],
        'Cv': slope['Cv'],
        'Q90_Q10_ratio': slope['Q90_Q10_ratio'],
        'Q10': slope['Q10'],
        'Q50': slope['Q50'],
        'Q90': slope['Q90'],
    }


def exceedance_probability(
    Q: float,
    Q_series: np.ndarray,
) -> float:
    """
    Вероятность превышения заданного расхода.

    Parameters:
        Q: расход, м3/с
        Q_series: ряд наблюдений

    Returns:
        Вероятность превышения (0–1)
    """
    Q_series = np.array(Q_series, dtype=float)
    Q_series = Q_series[~np.isnan(Q_series)]

    return float(np.mean(Q_series >= Q))


def fdc_from_monthly(
    monthly_df: pd.DataFrame,
    q_col: str = 'value',
) -> Dict:
    """
    FDC из месячных данных (для водного баланса и экологии).

    Parameters:
        monthly_df: DataFrame с месячными расходами
        q_col: имя колонки расходов

    Returns:
        Dict: FDC результат
    """
    Q = monthly_df[q_col].dropna().values
    return flow_duration_curve(Q)
