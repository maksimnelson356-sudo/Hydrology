"""
core/hydrorash/flood_hydrograph.py
Форма паводочной кривой (гидрограф паводка) — СП 33-101-2003 п.8.3

Основные функции:
- triangular_hydrograph — треугольный гидрограф (асимметричный)
- gamma_hydrograph — гидрограф по распределению Гамма (СП 33)
- unit_hydrograph — единичный гидрограф (гидрограф слоя 1 мм стока)
- flood_volume — объём паводка
- hydrograph_from_peak — восстановление гидрографа по Qpeak и Tbase
"""

import numpy as np
from typing import Dict, Optional


def triangular_hydrograph(
    Q_peak: float,
    T_peak: float,
    T_base: float,
    asymmetry: float = 0.3,
    dt: float = 1.0,
) -> Dict:
    """
    Асимметричный треугольный гидрограф паводка.

    Нарастание: 0 → Qpeak за T_peak
    Спад: Qpeak → 0 за T_base - T_peak

    Parameters:
        Q_peak: пиковый расход, м3/с
        T_peak: время нарастания, ч
        T_base: общая длительность паводка, ч
        asymmetry: отношение времени нарастания к общему (0.2–0.4)
        dt: шаг времени, ч

    Returns:
        Dict: t (часы), Q (м3/с), volume_m3, volume_km3
    """
    if T_peak is None or T_peak <= 0:
        T_peak = T_base * asymmetry

    T_rise = T_peak
    T_fall = T_base - T_rise

    t = np.arange(0, T_base + dt, dt)
    Q = np.zeros_like(t)

    for i, ti in enumerate(t):
        if ti <= T_rise:
            Q[i] = Q_peak * (ti / T_rise) if T_rise > 0 else Q_peak
        else:
            Q[i] = Q_peak * (1 - (ti - T_rise) / T_fall) if T_fall > 0 else 0

    Q = np.maximum(Q, 0)

    volume_m3 = float(np.trapz(Q, t) * 3600)
    volume_km3 = volume_m3 / 1e9

    return {
        't_hours': t.tolist(),
        'Q_m3_s': Q.tolist(),
        'Q_peak': float(Q_peak),
        'T_peak': float(T_rise),
        'T_base': float(T_base),
        'volume_m3': volume_m3,
        'volume_km3': volume_km3,
    }


def gamma_hydrograph(
    Q_peak: float,
    T_peak: float,
    T_base: float,
    shape: float = 3.5,
    dt: float = 1.0,
) -> Dict:
    """
    Гидрограф паводка по распределению Гамма (СП 33, рекомендуемая форма).

    Q(t) = Q_peak × (t/T_peak)^α × exp(α × (1 - t/T_peak))

    где α — параметр формы (2.5–4.0, типично 3.5)

    Parameters:
        Q_peak: пиковый расход, м3/с
        T_peak: время нарастания, ч
        T_base: общая длительность (для определения границ), ч
        shape: параметр формы α
        dt: шаг времени, ч

    Returns:
        Dict: t, Q, volume
    """
    t = np.arange(0, T_base + dt, dt)
    Q = np.zeros_like(t)

    alpha = shape

    for i, ti in enumerate(t):
        if ti <= 0:
            Q[i] = 0
        elif ti <= T_peak:
            Q[i] = Q_peak * (ti / T_peak) ** alpha
        else:
            tau = (ti - T_peak) / T_peak
            Q[i] = Q_peak * np.exp(-alpha * tau)

    Q = np.maximum(Q, 0)

    volume_m3 = float(np.trapz(Q, t) * 3600)
    volume_km3 = volume_m3 / 1e9

    return {
        't_hours': t.tolist(),
        'Q_m3_s': Q.tolist(),
        'Q_peak': float(Q_peak),
        'T_peak': float(T_peak),
        'T_base': float(T_base),
        'shape_alpha': alpha,
        'volume_m3': volume_m3,
        'volume_km3': volume_km3,
    }


def unit_hydrograph(
    T_peak: float,
    T_base: float,
    F_km2: float,
    shape: float = 3.5,
    dt: float = 1.0,
) -> Dict:
    """
    Единичный гидрограф (гидрограф слоя приведённого стока 1 мм).

    Используется для свёртки с осадками.

    Parameters:
        T_peak: время нарастания единичного гидрографа, ч
        T_base: общая длительность, ч
        F_km2: площадь бассейна, км²
        shape: параметр формы
        dt: шаг времени, ч

    Returns:
        Dict: t_hours, Q_m3_s (расход при слое 1 мм), volume_m3
    """
    Q_peak_unit = F_km2 / (3.6 * T_peak) if T_peak > 0 else 0

    gamma = gamma_hydrograph(Q_peak_unit, T_peak, T_base, shape, dt)

    return {
        't_hours': gamma['t_hours'],
        'Q_m3_s': gamma['Q_m3_s'],
        'Q_peak_unit': float(Q_peak_unit),
        'T_peak': T_peak,
        'T_base': T_base,
        'F_km2': F_km2,
        'volume_m3': gamma['volume_m3'],
    }


def hydrograph_convolution(
    unit_hydro: np.ndarray,
    excess_rainfall_mm: np.ndarray,
    dt: float = 1.0,
) -> np.ndarray:
    """
    Свёртка единичного гидрографа с избыточными осадками.

    Q(t) = Σ U(t - τ) × i(τ) × F / 3.6

    Parameters:
        unit_hydro: единичный гидрограф (м3/с при слое 1 мм)
        excess_rainfall_mm: избыточная осадка по интервалам, мм
        dt: шаг времени, ч

    Returns:
        Суммарный гидрограф паводка, м3/с
    """
    n = len(unit_hydro) + len(excess_rainfall_mm) - 1
    result = np.zeros(n)

    for j, rain in enumerate(excess_rainfall_mm):
        result[j:j + len(unit_hydro)] += unit_hydro * rain

    return result


def flood_volume(
    Q: np.ndarray,
    dt: float = 1.0,
) -> Dict:
    """
    Объём паводка по гидрографу.

    W = ∫ Q(t) dt

    Parameters:
        Q: расходы, м3/с
        dt: шаг времени, ч

    Returns:
        Dict: volume_m3, volume_km3, volume_mln_m3
    """
    volume_m3 = float(np.trapz(Q, dt * np.ones_like(Q)) * 3600)

    return {
        'volume_m3': volume_m3,
        'volume_km3': volume_m3 / 1e9,
        'volume_mln_m3': volume_m3 / 1e6,
    }


def hydrograph_from_peak(
    Q_peak: float,
    T_peak: float,
    T_base: float,
    method: str = 'gamma',
    shape: float = 3.5,
    dt: float = 1.0,
) -> Dict:
    """
    Построение гидрографа по Qpeak, Tpeak, Tbase.

    Parameters:
        Q_peak: пиковый расход
        T_peak: время нарастания
        T_base: общая длительность
        method: 'gamma' или 'triangle'
        shape: параметр формы (для gamma)
        dt: шаг

    Returns:
        Dict: t_hours, Q_m3_s, volume
    """
    if method == 'triangle':
        return triangular_hydrograph(Q_peak, T_peak, T_base, dt=dt)
    else:
        return gamma_hydrograph(Q_peak, T_peak, T_base, shape, dt)


def design_hydrograph_params(
    F_km2: float,
    Q_peak: float,
    zone: str = 'zone_3',
) -> Dict:
    """
    Оценка параметров расчётного гидрографа по площади бассейна.

    Эмпирические зависимости для российских условий:
    - T_peak ≈ 0.3 × F^0.3 (ч)
    - T_base ≈ 2.5 × T_peak (ч)

    Parameters:
        F_km2: площадь бассейна, км²
        Q_peak: пиковый расход, м³/с
        zone: климатическая зона

    Returns:
        Dict: T_peak, T_base, Q_peak
    """
    T_peak = 0.3 * (F_km2 ** 0.3)
    T_base = 2.5 * T_peak

    if zone in ('zone_5', 'zone_6'):
        T_peak *= 0.7
        T_base *= 0.8

    if F_km2 > 500:
        T_peak *= 1.3
        T_base *= 1.2

    return {
        'T_peak': round(float(T_peak), 1),
        'T_base': round(float(T_base), 1),
        'Q_peak': float(Q_peak),
        'F_km2': F_km2,
    }
