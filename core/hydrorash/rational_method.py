"""
core/hydrorash/rational_method.py
Метод рациона и IDF-кривые (СП 33-101-2003 п.8.3)

Метод рациона: Q = q × F × α
  Q — расход паводка, м3/с
  q — интенсивность дождя, мм/мин
  F — площадь бассейна, км2
  α — коэффициент стока (0.3–0.95)

IDF-кривые: i = A × T^m / (t + B)^n
  T — обеспеченность, лет
  t — длительность, мин
  A, B, n, m — параметры по климатическим зонам РФ

Основные функции:
- rational_method — расчёт паводка методом рациона
- idf_curve — интенсивность осадков для заданной длительности и обеспечённости
- design_rainfall — расчётный дождь по СП 33
- rational_method_catchment — метод рациона для бассейна с неоднородным стоком
- check_rational_validity — проверка применимости метода
"""

import numpy as np
from typing import Dict, List, Optional, Tuple


# Параметры IDF по климатическим зонам РФ (СП 33, прил. 5; СН 4357-87)
# Формула: i = A * T^m / (t + B)^n
IDF_ZONES = {
    'zone_1': {  # Арктика, Таймыр
        'name': 'Арктическая',
        'A': 0.025, 'B': 5.0, 'n': 0.70, 'm': 0.10,
        'H_annual_mean': 250, 'H_max_daily': 35
    },
    'zone_2': {  # Западная Сибирь, Русская равнина
        'name': 'Западно-Сибирская / Восточно-Европейская',
        'A': 0.040, 'B': 8.0, 'n': 0.75, 'm': 0.12,
        'H_annual_mean': 550, 'H_max_daily': 55
    },
    'zone_3': {  # Центральная Россия
        'name': 'Центральная',
        'A': 0.050, 'B': 10.0, 'n': 0.78, 'm': 0.13,
        'H_annual_mean': 600, 'H_max_daily': 65
    },
    'zone_4': {  # Юг Европейской части
        'name': 'Южная',
        'A': 0.065, 'B': 12.0, 'n': 0.80, 'm': 0.15,
        'H_annual_mean': 450, 'H_max_daily': 80
    },
    'zone_5': {  # Предкавказье, Дагестан
        'name': 'Предкавказская',
        'A': 0.080, 'B': 15.0, 'n': 0.82, 'm': 0.17,
        'H_annual_mean': 700, 'H_max_daily': 120
    },
    'zone_6': {  # Закавказье
        'name': 'Закавказская',
        'A': 0.100, 'B': 18.0, 'n': 0.85, 'm': 0.18,
        'H_annual_mean': 1200, 'H_max_daily': 150
    },
    'zone_7': {  # Восточная Сибирь
        'name': 'Восточно-Сибирская',
        'A': 0.035, 'B': 6.0, 'n': 0.72, 'm': 0.11,
        'H_annual_mean': 400, 'H_max_daily': 45
    },
    'zone_8': {  # Дальний Восток
        'name': 'Дальневосточная',
        'A': 0.060, 'B': 10.0, 'n': 0.76, 'm': 0.14,
        'H_annual_mean': 800, 'H_max_daily': 95
    },
    'zone_9': {  # Средняя Азия
        'name': 'Среднеазиатская',
        'A': 0.055, 'B': 8.0, 'n': 0.74, 'm': 0.16,
        'H_annual_mean': 300, 'H_max_daily': 60
    },
}


def idf_intensity(
    t: float,
    T: float,
    zone: str = 'zone_3',
    A: Optional[float] = None,
    B: Optional[float] = None,
    n: Optional[float] = None,
    m: Optional[float] = None,
) -> float:
    """
    Интенсивность дождя по IDF-кривой.

    i = A × T^m / (t + B)^n

    Parameters:
        t: длительность дождя, мин
        T: обеспеченность, лет (период возврата)
        zone: климатическая зона (zone_1..zone_9)
        A, B, n, m: пользовательские параметры (перекрывают zone)

    Returns:
        Интенсивность, мм/мин
    """
    if zone in IDF_ZONES and A is None:
        params = IDF_ZONES[zone]
        A = params['A']
        B = params['B']
        n = params['n']
        m = params['m']

    if A is None or B is None or n is None or m is None:
        raise ValueError("Укажите зону или параметры A, B, n, m")

    t = max(t, 0.1)
    T = max(T, 1.0)

    i = A * (T ** m) / ((t + B) ** n)
    return float(i)


def idf_curve(
    T: float,
    durations: Optional[List[float]] = None,
    zone: str = 'zone_3',
    **kwargs,
) -> Dict:
    """
    Построение IDF-кривой для заданной обеспеченности.

    Parameters:
        T: обеспеченность, лет
        durations: список длительностей, мин (по умолчанию 5..1440)
        zone: климатическая зона

    Returns:
        Dict: durations, intensities (мм/ч), cumulative_depths (мм)
    """
    if durations is None:
        durations = [5, 10, 15, 30, 60, 90, 120, 180, 360, 720, 1440]

    intensities = [idf_intensity(t, T, zone, **kwargs) * 60 for t in durations]  # мм/ч
    depths = [i * t / 60 for i, t in zip(intensities, durations)]  # мм

    return {
        'durations_min': durations,
        'intensities_mm_h': intensities,
        'cumulative_depths_mm': depths,
        'T_years': T,
        'zone': zone,
    }


def design_rainfall(
    T: float,
    t: float,
    zone: str = 'zone_3',
    **kwargs,
) -> Dict:
    """
    Расчётный дождь (СП 33 п.8.3).

    H_T = i × t

    Parameters:
        T: обеспеченность, лет
        t: длительность, мин
        zone: климатическая зона

    Returns:
        Dict: intensity_mm_h, depth_mm, duration_min, T_years
    """
    i_mm_min = idf_intensity(t, T, zone, **kwargs)
    i_mm_h = i_mm_min * 60
    depth_mm = i_mm_min * t

    return {
        'intensity_mm_h': round(i_mm_h, 2),
        'depth_mm': round(depth_mm, 2),
        'duration_min': t,
        'T_years': T,
    }


def rational_method(
    F: float,
    T: float,
    t: float,
    alpha: float = 0.7,
    zone: str = 'zone_3',
    **kwargs,
) -> Dict:
    """
    Метод рациона (СП 33 п.8.3).

    Q = q × F × α / 3.6

    где q — интенсивность мм/ч, F — км², α — коэффициент стока

    Parameters:
        F: площадь бассейна, км²
        T: обеспеченность, лет
        t: время концентрации, мин (= длительность расчётного дождя)
        alpha: коэффициент стока (0.3–0.95)
        zone: климатическая зона

    Returns:
        Dict: Q, intensity, depth, alpha, F, T, t
    """
    i_mm_h = idf_intensity(t, T, zone, **kwargs) * 60
    Q = i_mm_h * F * alpha / 3.6

    return {
        'Q_m3_s': round(Q, 3),
        'intensity_mm_h': round(i_mm_h, 2),
        'depth_mm': round(idf_intensity(t, T, zone, **kwargs) * t, 2),
        'alpha': alpha,
        'F_km2': F,
        'T_years': T,
        't_min': t,
    }


def time_of_concentration(
    L: float,
    I: float,
    method: str = 'kirpich',
) -> float:
    """
    Время концентрации (время собирания) по формуле Кирпича.

    t_c = 0.0195 × L^0.77 × I^(-0.385)

    Parameters:
        L: длина русла, км
        I: уклон русла, м/м

    Returns:
        Время концентрации, мин
    """
    if method == 'kirpich':
        t_c = 0.0195 * (L ** 0.77) * (I ** (-0.385))
    elif method == 'babuškin':
        t_c = 0.93 * (L ** 0.57) * (I ** (-0.33))
    else:
        t_c = 0.0195 * (L ** 0.77) * (I ** (-0.385))

    return float(t_c)


def check_rational_validity(
    F: float,
    t: float,
    zone: str = 'zone_3',
) -> Dict:
    """
    Проверка применимости метода рациона (СП 33 п.8.3).

    Метод рациона применим при:
    - F < 50–200 км² (в зависимости от зоны)
    - t > 5 мин
    - Не适用于 больших бассейнов

    Returns:
        Dict: is_valid, warnings, F_max_recommended
    """
    warnings = []
    F_max = 50

    if zone in IDF_ZONES:
        zone_name = IDF_ZONES[zone]['name']
        if 'Закавказ' in zone_name or 'Предкавказ' in zone_name:
            F_max = 100
        elif 'Южная' in zone_name:
            F_max = 80
        elif 'Дальн' in zone_name:
            F_max = 75

    is_valid = True

    if F > F_max:
        warnings.append(f"Площадь F={F} км² > рекомендуемой ({F_max} км²). Используйте регрессионные уравнения.")
        is_valid = False

    if t < 5:
        warnings.append(f"Время концентрации t={t} мин < 5 мин. IDF-кривые ненадёжны для малых t.")
        is_valid = False

    if F > 200:
        warnings.append("Для бассейнов > 200 км² метод рациона НЕ применим.")

    return {
        'is_valid': is_valid,
        'F_max_recommended': F_max,
        'warnings': warnings,
    }


def rational_method_catchment(
    subcatchments: List[Dict],
    T: float,
    zone: str = 'zone_3',
) -> Dict:
    """
    Метод рациона для неоднородного бассейна (суммирование по подбассейнам).

    Q_total = Σ(q_i × F_i × α_i) / 3.6

    Parameters:
        subcatchments: список словарей:
            [{'F_km2': float, 'alpha': float, 'L_km': float, 'I': float}, ...]
        T: обеспеченность, лет
        zone: климатическая зона

    Returns:
        Dict: Q_total, breakdown per subcatchment
    """
    total_Q = 0.0
    breakdown = []

    for sc in subcatchments:
        F = sc['F_km2']
        alpha = sc.get('alpha', 0.7)
        L = sc.get('L_km', 10.0)
        I = sc.get('I', 0.005)

        t_c = time_of_concentration(L, I)
        result = rational_method(F, T, t_c, alpha, zone)

        total_Q += result['Q_m3_s']
        breakdown.append({
            'F_km2': F,
            'alpha': alpha,
            't_c_min': round(t_c, 1),
            'Q_m3_s': result['Q_m3_s'],
        })

    return {
        'Q_total_m3_s': round(total_Q, 3),
        'n_subcatchments': len(subcatchments),
        'breakdown': breakdown,
        'T_years': T,
    }


# Коэффициенты стока α для различных типов поверхности (СП 33, прил. 7)
RUNOFF_COEFFICIENTS = {
    'dense_urban': 0.70,
    'residential': 0.50,
    'park': 0.25,
    'farmland_clay': 0.40,
    'farmland_sand': 0.20,
    'forest_clay': 0.30,
    'forest_sand': 0.15,
    'grassland_clay': 0.35,
    'grassland_sand': 0.15,
    'marsh': 0.10,
    'rock': 0.75,
    'asphalt': 0.90,
    'roof': 0.95,
}

# Средние коэффициенты стока по природным зонам (для предварительных расчётов)
ZONE_RUNOFF_COEFFICIENTS = {
    'zone_1': 0.45,  # Арктика
    'zone_2': 0.35,  # Зап. Сибирь
    'zone_3': 0.30,  # Центральная
    'zone_4': 0.25,  # Юг
    'zone_5': 0.35,  # Предкавказье
    'zone_6': 0.45,  # Закавказье
    'zone_7': 0.40,  # Вост. Сибирь
    'zone_8': 0.40,  # Дальний Восток
    'zone_9': 0.20,  # Средняя Азия
}
