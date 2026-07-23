"""
core/hydraulics.py
Расчёт расхода по формуле Маннинга с разделением на отсеки.

Формула Маннинга (СП 33-101-2003):
    Q = (1/n) · ω · R^(2/3) · √I

где:
    n — коэффициент шероховатости Маннинга
    ω — площадь живого сечения, м²
    R = ω/χ — гидравлический радиус, м
    χ — смоченный периметр, м
    I — уклон的能量水线 (в данной реализации — уклон дна)
"""

import math
from typing import Dict
from core.profile import MorphoProfile


def calculate_q_manning(omega: float, chi: float, n: float, i: float) -> float:
    """
    Расход по формуле Маннинга (стандартная формула без поправок).

    Q = (1/n) · ω · (ω/χ)^(2/3) · √I
    """
    if omega <= 0 or chi <= 0 or n <= 0 or i <= 0:
        return 0.0
    R = omega / chi
    q = (1.0 / n) * omega * (R ** (2.0 / 3.0)) * math.sqrt(i)
    return round(q, 3)


def calculate_composite_q(profile: MorphoProfile, h: float) -> Dict[str, float]:
    """
    Расчёт расхода с разделением на отсеки.
    Согласно СП 33-101-2003 п. 7.4 раздельно считаем русло и поймы.
    """
    compartments = profile.get_geometry_by_compartments(h)

    # Левая пойма
    left = compartments['left_poyma']
    q_left = 0.0
    if left['omega'] > 0 and left['chi'] > 0:
        q_left = calculate_q_manning(left['omega'], left['chi'],
                                     profile.n_left, profile.slope_i)

    # Русловая часть
    ruslo = compartments['ruslo']
    q_ruslo = 0.0
    if ruslo['omega'] > 0 and ruslo['chi'] > 0:
        q_ruslo = calculate_q_manning(ruslo['omega'], ruslo['chi'],
                                      profile.n_ruslo, profile.slope_i)

    # Правая пойма
    right = compartments['right_poyma']
    q_right = 0.0
    if right['omega'] > 0 and right['chi'] > 0:
        q_right = calculate_q_manning(right['omega'], right['chi'],
                                      profile.n_right, profile.slope_i)

    # Суммарный расход
    q_total = q_left + q_ruslo + q_right

    # Средневзвешенный коэффициент шероховатости (для справки)
    total_omega = compartments['total']['omega_total']
    if total_omega > 0:
        n_weighted = (left['omega'] * profile.n_left +
                     ruslo['omega'] * profile.n_ruslo +
                     right['omega'] * profile.n_right) / total_omega
    else:
        n_weighted = profile.n_ruslo

    return {
        'H': round(h, 2),
        'Q_total': round(q_total, 3),
        'Q_left_poyma': round(q_left, 3),
        'Q_ruslo': round(q_ruslo, 3),
        'Q_right_poyma': round(q_right, 3),
        'omega_total': compartments['total']['omega_total'],
        'omega_left': left['omega'],
        'omega_ruslo': ruslo['omega'],
        'omega_right': right['omega'],
        'n_weighted': round(n_weighted, 4),
    }