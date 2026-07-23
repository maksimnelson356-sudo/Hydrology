"""
core/hydrorash/backwater.py
Кривые подпора (ГВП) — СП 33-101-2003

Основные функции:
- backwater_curve_step — расчёт ГВП методом последовательных сечений
- normal_depth — нормальная глубина (Маннинг)
- critical_depth — критическая глубина
- backwater_from_reservoir — линия подпора от водохранилища
"""

import numpy as np
from typing import Dict, List, Optional, Tuple


def normal_depth(
    Q: float,
    B: float,
    m: float,
    n: float,
    I: float,
) -> float:
    """
    Нормальная глубина (Маннинг).

    Q = (1/n) × ω × R^(2/3) × sqrt(I)

    Итеративно решаем уравнение для h_н.

    Parameters:
        Q: расход, м3/с
        B: ширина русла, м
        m: откос (1:m, b=1 — трапеция)
        n: коэффициент шероховатости Маннинга
        I: уклон, м/м

    Returns:
        Нормальная глубина, м
    """
    def manning_Q(h):
        if h <= 0:
            return 0
        omega = B * h + m * h ** 2
        P = B + 2 * h * np.sqrt(1 + m ** 2)
        R = omega / P if P > 0 else 0
        return (1 / n) * omega * (R ** (2 / 3)) * np.sqrt(I)

    h = 0.1
    for _ in range(100):
        Q_h = manning_Q(h)
        if abs(Q_h - Q) < 0.01:
            return float(h)
        if Q_h < Q:
            h *= 1.1
        else:
            h *= 0.9

    return float(h)


def critical_depth(
    Q: float,
    B: float,
    m: float,
    g: float = 9.81,
) -> float:
    """
    Критическая глубина для трапецеидального русла.

    Q²/g = ω³/B_где

    Parameters:
        Q: расход, м3/с
        B: ширина дна, м
        m: откос бортов

    Returns:
        Критическая глубина, м
    """
    def discharge_number(h):
        if h <= 0:
            return 0
        omega = B * h + m * h ** 2
        B_top = B + 2 * m * h
        return (Q ** 2 / g) - (omega ** 3 / B_top)

    h = 0.1
    for _ in range(200):
        f = discharge_number(h)
        if abs(f) < 0.001:
            return float(h)
        df = discharge_number(h + 0.001) - f
        if abs(df) > 1e-10:
            h -= f / df * 0.5
        else:
            h *= 1.1
        h = max(h, 0.01)

    return float(h)


def backwater_curve_step(
    Q: float,
    B: float,
    m: float,
    n: float,
    I: float,
    L_total: float,
    dx: float = 100.0,
    H_downstream: float = 0,
) -> Dict:
    """
    Расчёт кривой подпора методом последовательных сечений (direct step).

    Параметрическое уравнение:
    dx = (E₂ - E₁) / (I - S̄f)

    Где E = h + V²/(2g) — энергетический напор
    Sf = Q²n²/(ω²R^(4/3)) — трение по Маннингу

    Parameters:
        Q: расход, м3/с
        B: ширина дна, м
        m: откос бортов
        n: коэффициент Маннинга
        I: уклон, м/м
        L_total: длина участка расчёта, м
        dx: шаг по длине, м
        H_downstream: глубина на нижнем конце (напор от водохранилища), м

    Returns:
        Dict: distances, depths, velocities, energy_heads
    """
    g = 9.81
    h_n = normal_depth(Q, B, m, n, I)

    h = max(H_downstream, h_n * 1.1)
    distances = [0.0]
    depths = [h]
    velocities = []
    energy_heads = []

    n_steps = int(L_total / dx)

    for i in range(n_steps):
        x = (i + 1) * dx

        omega = B * h + m * h ** 2
        P = B + 2 * h * np.sqrt(1 + m ** 2)
        R = omega / P if P > 0 else 0.01
        V = Q / omega if omega > 0 else 0
        E = h + V ** 2 / (2 * g)
        Sf = (Q * n) ** 2 / (omega ** 2 * R ** (4 / 3)) if R > 0 else 0

        h_next = h
        for _ in range(50):
            omega2 = B * h_next + m * h_next ** 2
            P2 = B + 2 * h_next * np.sqrt(1 + m ** 2)
            R2 = omega2 / P2 if P2 > 0 else 0.01
            V2 = Q / omega2 if omega2 > 0 else 0
            E2 = h_next + V2 ** 2 / (2 * g)
            Sf2 = (Q * n) ** 2 / (omega2 ** 2 * R2 ** (4 / 3)) if R2 > 0 else 0
            Sf_avg = (Sf + Sf2) / 2
            dx_calc = (E2 - E) / (I - Sf_avg) if abs(I - Sf_avg) > 1e-10 else 0
            if abs(dx_calc - dx) < 0.1:
                break
            h_next += (dx - dx_calc) * 0.01

        h_next = max(h_next, 0.01)
        h = h_next
        distances.append(x)
        depths.append(round(float(h), 3))

    return {
        'distances_m': distances,
        'depths_m': depths,
        'normal_depth': round(float(h_n), 3),
        'L_total': L_total,
        'dx': dx,
    }


def backwater_from_reservoir(
    Q: float,
    B: float,
    m: float,
    n: float,
    I: float,
    H_reservoir: float,
    L_max: float = 10000,
    dx: float = 200,
) -> Dict:
    """
    Линия подпора от водохранилища (СП 33 п.8.4).

    Показывает, на каком расстоянии от плотины уровень снижается до нормальной глубины.

    Parameters:
        Q: средний расход в реке, м3/с
        B, m, n, I: параметры русла
        H_reservoir: уровень воды в водохранилище (НПУ), м
        L_max: максимальная длина расчёта, м

    Returns:
        Dict: result (distances, depths), normal_depth, L_backwater
    """
    h_n = normal_depth(Q, B, m, n, I)
    L_backwater = L_max

    result = backwater_curve_step(Q, B, m, n, I, L_max, dx, H_reservoir)

    for i, d in enumerate(result['depths']):
        if abs(d - h_n) < 0.05:
            L_backwater = result['distances_m'][i]
            break

    return {
        'result': result,
        'normal_depth': round(float(h_n), 3),
        'H_reservoir': H_reservoir,
        'L_backwater_m': round(float(L_backwater), 0),
        'L_backwater_km': round(float(L_backwater) / 1000, 2),
    }
