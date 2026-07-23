"""
core/hydrorash/snowmelt.py
Прогноз таяния снега — градусно-суточный метод (СП 33-101-2003 п.8.1, РД 52-26-2008)

Основные формулы:
- Степень таяния: M = A × T_air (мм/сутки)
- Снегозапас в начале таяния: W = H × ρ / 100
- Объём талых вод: W_t × F × α / (86400 × T_t)

Основные функции:
- snowmelt_degree_day — градусно-суточный метод
- snowmelt_balance — снеговой баланс бассейна
- melt_rate_by_zone — степень таяния по климатическим зонам
- snowmelt_peak_runoff — максимальный расход талых вод
- snow_water_equivalent — переход от высоты снега к запасу
- snowmelt_hydrograph — гидрограф таяния
"""

import numpy as np
from typing import Dict, List, Optional


# Степень таяния по климатическим зонам (мм/сутки при T=+10°С)
# A = M / T_air, где M — мм/сутки при среднесуточной T
MELT_COEFFICIENTS = {
    'zone_1': {'A': 2.5, 'name': 'Арктическая', 'snow_density': 250},
    'zone_2': {'A': 3.0, 'name': 'Западно-Сибирская', 'snow_density': 280},
    'zone_3': {'A': 3.5, 'name': 'Центральная', 'snow_density': 300},
    'zone_4': {'A': 4.0, 'name': 'Южная', 'snow_density': 320},
    'zone_5': {'A': 3.5, 'name': 'Предкавказская', 'snow_density': 300},
    'zone_6': {'A': 3.0, 'name': 'Закавказская', 'snow_density': 280},
    'zone_7': {'A': 2.8, 'name': 'Восточно-Сибирская', 'snow_density': 270},
    'zone_8': {'A': 3.2, 'name': 'Дальневосточная', 'snow_density': 290},
    'zone_9': {'A': 2.0, 'name': 'Среднеазиатская', 'snow_density': 260},
}


def snow_water_equivalent(
    H_snow: float,
    rho_snow: float = 300,
) -> float:
    """
    Запас воды в снеге (ЗВС) по высоте снега и плотности.

    W = H × ρ / 1000

    Parameters:
        H_snow: высота снега, см
        rho_snow: средняя плотность снега, кг/м³ (по умолчанию 300)

    Returns:
        Запас воды в снеге, мм
    """
    return float(H_snow * rho_snow / 1000)


def melt_rate_by_zone(
    zone: str = 'zone_3',
    T_air: float = 10.0,
) -> float:
    """
    Суточная степень таяния снега.

    M = A × T_air

    Parameters:
        zone: климатическая зона
        T_air: среднесуточная температура воздуха, °С

    Returns:
        Степень таяния, мм/сутки
    """
    if zone not in MELT_COEFFICIENTS:
        zone = 'zone_3'
    A = MELT_COEFFICIENTS[zone]['A']
    M = A * max(T_air, 0)
    return float(M)


def snowmelt_degree_day(
    W_initial: float,
    T_series: np.ndarray,
    A: float = 3.5,
    albedo: float = 0.3,
    net_coeff: float = 0.85,
    dt_days: float = 1.0,
) -> Dict:
    """
    Градусно-суточный метод расчёта таяния снега (СП 33 п.8.1).

    M_i = A × T_air,i × dt (при T_air > 0)

    Parameters:
        W_initial: начальный запас воды в снеге, мм
        T_series: среднесуточные температуры воздуха, °С
        A: коэффициент таяния (мм/сутки при T=+10°С)
        albedo: альбедо снега (0.2–0.4)
        net_coeff: коэффициент перехода к чистому снеготаянию
        dt_days: шаг времени, сутки

    Returns:
        Dict: melt_mm, remaining_snow_mm, daily_melt
    """
    W = W_initial
    daily_melt = []
    remaining = []
    total_melt = 0.0

    A_eff = A * net_coeff

    for T in T_series:
        if T > 0 and W > 0:
            melt = A_eff * T * dt_days
            melt = min(melt, W)
            W -= melt
            daily_melt.append(float(melt))
            total_melt += melt
        else:
            daily_melt.append(0.0)

        remaining.append(float(W))

    return {
        'daily_melt_mm': daily_melt,
        'remaining_snow_mm': remaining,
        'total_melt_mm': float(total_melt),
        'W_initial': float(W_initial),
        'W_final': float(W),
        'snow_free_day': next(
            (i for i, w in enumerate(remaining) if w <= 0),
            len(remaining)
        ),
    }


def snowmelt_balance(
    W_initial: float,
    precipitation_mm: float,
    T_air: float,
    A: float = 3.5,
    days: int = 30,
) -> Dict:
    """
    Снеговой баланс бассейна за период таяния.

    W_end = W_init + P - M
    M = A × T_air × days

    Parameters:
        W_initial: начальный запас воды в снеге, мм
        precipitation_mm: осадки за период таяния, мм
        T_air: средняя температура, °С
        A: коэффициент таяния
        days: длительность периода, сутки

    Returns:
        Dict: melt_total, runoff_total, W_final
    """
    M = A * max(T_air, 0) * days
    M = min(M, W_initial)
    runoff = M - precipitation_mm * 0.3  # часть осадков уходит в сток
    runoff = max(runoff, 0)

    return {
        'melt_total_mm': round(float(M), 1),
        'runoff_total_mm': round(float(runoff), 1),
        'precipitation_mm': precipitation_mm,
        'W_final_mm': round(float(max(W_initial - M + precipitation_mm, 0)), 1),
        'days': days,
    }


def snowmelt_peak_runoff(
    F_km2: float,
    W_initial: float,
    A: float = 3.5,
    T_peak_temp: float = 10.0,
    concentration_time_h: float = 24.0,
    alpha: float = 0.7,
) -> Dict:
    """
    Максимальный расход талых вод (СП 33 п.8.1).

    Q_max = (M × F × α) / (3.6 × T_t)

    где M — интенсивность таяния, T_t — время концентрации

    Parameters:
        F_km2: площадь бассейна, км²
        W_initial: запас воды в снеге, мм
        A: коэффициент таяния
        T_peak_temp: температура в момент пика, °С
        concentration_time_h: время концентрации, ч
        alpha: коэффициент стока

    Returns:
        Dict: Q_peak, melt_intensity, W_initial
    """
    M = A * T_peak_temp
    W = W_initial

    if M * 10 > W:
        M = W / 10

    Q_peak = (M * F_km2 * alpha) / (3.6 * concentration_time_h)

    return {
        'Q_peak_m3_s': round(float(Q_peak), 2),
        'melt_intensity_mm_day': round(float(M), 1),
        'W_initial_mm': float(W_initial),
        'F_km2': F_km2,
        'alpha': alpha,
    }


def snowmelt_hydrograph(
    W_initial: float,
    T_series: np.ndarray,
    F_km2: float,
    A: float = 3.5,
    alpha: float = 0.7,
    concentration_time_h: float = 24.0,
    dt_days: float = 1.0,
) -> Dict:
    """
    Гидрограф таяния снега.

    Для каждого дня:
    M_i = A × T_i × dt
    Q_i = M_i × F × α / (3.6 × T_conc)

    Parameters:
        W_initial: начальный запас воды в снеге, мм
        T_series: температуры, °С
        F_km2: площадь, км²
        A: коэффициент таяния
        alpha: коэффициент стока
        concentration_time_h: время концентрации, ч

    Returns:
        Dict: t_days, Q_m3_s, daily_melt, W_remaining
    """
    W = W_initial
    t_days = list(range(len(T_series)))
    Q_series = []
    melt_series = []
    W_series = []

    for T in T_series:
        if T > 0 and W > 0:
            melt = A * T * dt_days
            melt = min(melt, W)
            Q = (melt * F_km2 * alpha) / (3.6 * concentration_time_h)
            W -= melt
        else:
            melt = 0
            Q = 0

        Q_series.append(round(float(Q), 2))
        melt_series.append(round(float(melt), 1))
        W_series.append(round(float(W), 1))

    return {
        't_days': t_days,
        'Q_m3_s': Q_series,
        'daily_melt_mm': melt_series,
        'W_remaining_mm': W_series,
        'W_initial': float(W_initial),
        'W_final': float(W),
        'total_runoff_m3_s_sum': round(sum(Q_series), 2),
    }


# Типичные запасы воды в снеге по зонам (значения H_050 для расчёта по формуле СП 33)
# H_050 — высота снега с обеспеченностью 50% в начале таяния
TYPICAL_SNOW_DEPTH = {
    'zone_1': {'H_050_cm': 60, 'rho': 250},
    'zone_2': {'H_050_cm': 70, 'rho': 280},
    'zone_3': {'H_050_cm': 50, 'rho': 300},
    'zone_4': {'H_050_cm': 20, 'rho': 320},
    'zone_5': {'H_050_cm': 30, 'rho': 300},
    'zone_6': {'H_050_cm': 25, 'rho': 280},
    'zone_7': {'H_050_cm': 40, 'rho': 270},
    'zone_8': {'H_050_cm': 55, 'rho': 290},
    'zone_9': {'H_050_cm': 15, 'rho': 260},
}
