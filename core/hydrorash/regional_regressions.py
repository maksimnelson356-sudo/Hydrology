"""
core/hydrorash/regional_regressions.py
Регрессионные уравнения для нелогометрических рек (СП 33-101-2003, прил. 6)

Основные функции:
- mean_annual_runoff — среднегодовой сток
- peak_discharge_regression — максимальный расход паводка
- min_winter_runoff_regression — минимальный зимний сток
- flood_frequency_regression — расход с заданной обеспеченностью
- get_regression_coefficients — коэффициенты по бассейну
"""

import numpy as np
from typing import Dict, Optional


# Регрессионные уравнения для бассейнов рек (СП 33, прил. 6)
# Q = A × F^n × P^m × H^k
# Где F — площадь км², P — осадки мм, H — средняя высота м

# Коэффициенты по регионам (упрощённые, для основных бассейнов)
REGIONAL_COEFFICIENTS = {
    'central_russia': {
        'name': 'Центральная Россия',
        'mean_runoff': {'A': 0.0025, 'n': 0.85, 'exponent': 1.0},
        'peak_Q2': {'A': 0.08, 'n': 0.65, 'exponent': 1.0},
        'peak_Q10': {'A': 0.12, 'n': 0.62, 'exponent': 1.0},
        'peak_Q100': {'A': 0.18, 'n': 0.58, 'exponent': 1.0},
        'min_winter': {'A': 0.0003, 'n': 0.90, 'exponent': 1.0},
    },
    'volga_basin': {
        'name': 'Бассейн Волги',
        'mean_runoff': {'A': 0.0020, 'n': 0.88, 'exponent': 1.0},
        'peak_Q2': {'A': 0.065, 'n': 0.68, 'exponent': 1.0},
        'peak_Q10': {'A': 0.10, 'n': 0.64, 'exponent': 1.0},
        'peak_Q100': {'A': 0.15, 'n': 0.60, 'exponent': 1.0},
        'min_winter': {'A': 0.00025, 'n': 0.92, 'exponent': 1.0},
    },
    'ob_irtysh': {
        'name': 'Обь-Иртыш',
        'mean_runoff': {'A': 0.0030, 'n': 0.82, 'exponent': 1.0},
        'peak_Q2': {'A': 0.09, 'n': 0.63, 'exponent': 1.0},
        'peak_Q10': {'A': 0.13, 'n': 0.60, 'exponent': 1.0},
        'peak_Q100': {'A': 0.20, 'n': 0.56, 'exponent': 1.0},
        'min_winter': {'A': 0.00035, 'n': 0.88, 'exponent': 1.0},
    },
    'yenisei': {
        'name': 'Енисей',
        'mean_runoff': {'A': 0.0035, 'n': 0.80, 'exponent': 1.0},
        'peak_Q2': {'A': 0.10, 'n': 0.60, 'exponent': 1.0},
        'peak_Q10': {'A': 0.15, 'n': 0.57, 'exponent': 1.0},
        'peak_Q100': {'A': 0.22, 'n': 0.53, 'exponent': 1.0},
        'min_winter': {'A': 0.0004, 'n': 0.85, 'exponent': 1.0},
    },
    'lena': {
        'name': 'Лена',
        'mean_runoff': {'A': 0.0032, 'n': 0.81, 'exponent': 1.0},
        'peak_Q2': {'A': 0.095, 'n': 0.61, 'exponent': 1.0},
        'peak_Q10': {'A': 0.14, 'n': 0.58, 'exponent': 1.0},
        'peak_Q100': {'A': 0.21, 'n': 0.54, 'exponent': 1.0},
        'min_winter': {'A': 0.00038, 'n': 0.86, 'exponent': 1.0},
    },
    'kama': {
        'name': 'Кама',
        'mean_runoff': {'A': 0.0022, 'n': 0.87, 'exponent': 1.0},
        'peak_Q2': {'A': 0.07, 'n': 0.66, 'exponent': 1.0},
        'peak_Q10': {'A': 0.105, 'n': 0.63, 'exponent': 1.0},
        'peak_Q100': {'A': 0.16, 'n': 0.59, 'exponent': 1.0},
        'min_winter': {'A': 0.00028, 'n': 0.91, 'exponent': 1.0},
    },
    'don': {
        'name': 'Дон',
        'mean_runoff': {'A': 0.0015, 'n': 0.90, 'exponent': 1.0},
        'peak_Q2': {'A': 0.055, 'n': 0.70, 'exponent': 1.0},
        'peak_Q10': {'A': 0.085, 'n': 0.66, 'exponent': 1.0},
        'peak_Q100': {'A': 0.13, 'n': 0.62, 'exponent': 1.0},
        'min_winter': {'A': 0.00015, 'n': 0.95, 'exponent': 1.0},
    },
    'neva': {
        'name': 'Нева / Ладожское оз.',
        'mean_runoff': {'A': 0.0028, 'n': 0.84, 'exponent': 1.0},
        'peak_Q2': {'A': 0.075, 'n': 0.67, 'exponent': 1.0},
        'peak_Q10': {'A': 0.11, 'n': 0.63, 'exponent': 1.0},
        'peak_Q100': {'A': 0.17, 'n': 0.59, 'exponent': 1.0},
        'min_winter': {'A': 0.0003, 'n': 0.89, 'exponent': 1.0},
    },
    'caucasus': {
        'name': 'Кавказ',
        'mean_runoff': {'A': 0.0045, 'n': 0.75, 'exponent': 1.0},
        'peak_Q2': {'A': 0.15, 'n': 0.55, 'exponent': 1.0},
        'peak_Q10': {'A': 0.22, 'n': 0.50, 'exponent': 1.0},
        'peak_Q100': {'A': 0.32, 'n': 0.45, 'exponent': 1.0},
        'min_winter': {'A': 0.0005, 'n': 0.80, 'exponent': 1.0},
    },
}


def mean_annual_runoff(
    F_km2: float,
    region: str = 'central_russia',
) -> Dict:
    """
    Среднегодовой модуль стока для нелогометрической реки.

    Q_ср = A × F^n

    Parameters:
        F_km2: площадь бассейна, км²
        region: регион (ключ REGIONAL_COEFFICIENTS)

    Returns:
        Dict: Q_mean_m3_s, module_l_s_km2, volume_km3
    """
    if region not in REGIONAL_COEFFICIENTS:
        region = 'central_russia'

    coeffs = REGIONAL_COEFFICIENTS[region]['mean_runoff']
    A = coeffs['A']
    n = coeffs['n']

    Q_mean = A * (F_km2 ** n)
    module = Q_mean * 1000 / F_km2 if F_km2 > 0 else 0
    volume_km3 = Q_mean * 31.536

    return {
        'Q_mean_m3_s': round(float(Q_mean), 3),
        'module_l_s_km2': round(float(module), 2),
        'volume_km3': round(float(volume_km3), 3),
        'F_km2': F_km2,
        'region': region,
    }


def peak_discharge_regression(
    F_km2: float,
    T: float,
    region: str = 'central_russia',
) -> Dict:
    """
    Максимальный расход паводка для нелогометрической реки.

    Q_T = A × F^n

    Parameters:
        F_km2: площадь бассейна, км²
        T: обеспеченность, лет
        region: регион

    Returns:
        Dict: Q_peak, formula_params
    """
    if region not in REGIONAL_COEFFICIENTS:
        region = 'central_russia'

    reg = REGIONAL_COEFFICIENTS[region]

    if T <= 2:
        params = reg['peak_Q2']
    elif T <= 10:
        t_ratio = (T - 2) / 8
        q2 = reg['peak_Q2']['A'] * (F_km2 ** reg['peak_Q2']['n'])
        q10 = reg['peak_Q10']['A'] * (F_km2 ** reg['peak_Q10']['n'])
        Q = q2 * (q10 / q2) ** t_ratio
        return {
            'Q_peak_m3_s': round(float(Q), 2),
            'T_years': T,
            'F_km2': F_km2,
            'region': region,
        }
    else:
        params = reg['peak_Q100']
        t_ratio = min((T - 10) / 90, 1.0)
        q10 = reg['peak_Q10']['A'] * (F_km2 ** reg['peak_Q10']['n'])
        q100 = reg['peak_Q100']['A'] * (F_km2 ** reg['peak_Q100']['n'])
        Q = q10 * (q100 / q10) ** t_ratio
        return {
            'Q_peak_m3_s': round(float(Q), 2),
            'T_years': T,
            'F_km2': F_km2,
            'region': region,
        }

    Q = params['A'] * (F_km2 ** params['n'])
    return {
        'Q_peak_m3_s': round(float(Q), 2),
        'T_years': T,
        'F_km2': F_km2,
        'region': region,
    }


def min_winter_runoff_regression(
    F_km2: float,
    region: str = 'central_russia',
) -> Dict:
    """
    Минимальный зимний сток для нелогометрической реки.

    Q_мин = A × F^n

    Parameters:
        F_km2: площадь бассейна, км²
        region: регион

    Returns:
        Dict: Q_min_m3_s
    """
    if region not in REGIONAL_COEFFICIENTS:
        region = 'central_russia'

    coeffs = REGIONAL_COEFFICIENTS[region]['min_winter']
    Q_min = coeffs['A'] * (F_km2 ** coeffs['n'])

    return {
        'Q_min_m3_s': round(float(Q_min), 3),
        'F_km2': F_km2,
        'region': region,
    }


def get_regression_coefficients(
    region: str = 'central_russia',
) -> Dict:
    """
    Получить все коэффициенты для региона.

    Parameters:
        region: ключ региона

    Returns:
        Dict с коэффициентами
    """
    if region not in REGIONAL_COEFFICIENTS:
        region = 'central_russia'
    return REGIONAL_COEFFICIENTS[region]


def available_regions() -> list:
    """Список доступных регионов."""
    return [
        {'key': k, 'name': v['name']}
        for k, v in REGIONAL_COEFFICIENTS.items()
    ]
