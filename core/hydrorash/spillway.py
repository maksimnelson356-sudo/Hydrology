"""
core/hydrorash/spillway.py
Пропускная способность ППУ (водосброс) — СП 58.13330.2019 п.6

Основные функции:
- free_overfall — свободный перелив через тонкостенную плотину
- weir_flow — расход через лотковый водосброс
- orifice_flow — расход через отверстие (подпор)
- spillway_capacity_check — проверка пропускной способности
- emergency_flood_passage — пропуск ПФР (паводок разового вызова)
"""

import numpy as np
from typing import Dict, List, Optional


def free_overfall(
    H: float,
    L: float,
    Cd: float = 1.84,
    submergence: float = 1.0,
) -> float:
    """
    Свободный перелив через тонкостенную плотину (формула Томпсона).

    Q = Cd × L × H^1.5

    Parameters:
        H: напор над гребнем, м
        L: длина гребня, м
        Cd: коэффициент расхода (1.7–1.95)
        submergence: коэффициент затопления (1.0 = свободный сброс)

    Returns:
        Расход, м3/с
    """
    if H <= 0:
        return 0.0
    Q = Cd * L * (H ** 1.5) * submergence
    return float(Q)


def weir_flow(
    H: float,
    L: float,
    weir_type: str = 'sharp_crested',
    Cd: Optional[float] = None,
    submergence: float = 1.0,
) -> Dict:
    """
    Расход через лотковый водосброс.

    Parameters:
        H: напор, м
        L: длина гребня, м
        weir_type: 'sharp_crested', 'broad_crested', 'ogee'
        Cd: коэффициент расхода (если None — по типу)
        submergence: коэффициент затопления

    Returns:
        Dict: Q_m3_s, Cd, weir_type
    """
    if Cd is None:
        Cd_map = {
            'sharp_crested': 1.84,
            'broad_crested': 1.50,
            'ogee': 2.20,
        }
        Cd = Cd_map.get(weir_type, 1.84)

    Q = free_overfall(H, L, Cd, submergence)
    return {
        'Q_m3_s': round(Q, 2),
        'Cd': Cd,
        'weir_type': weir_type,
        'H_m': H,
        'L_m': L,
    }


def orifice_flow(
    H: float,
    A: float,
    Cd: float = 0.62,
    g: float = 9.81,
) -> float:
    """
    Расход через подводящее отверстие (труба, шахта).

    Q = Cd × A × sqrt(2 × g × H)

    Parameters:
        H: напор на ось отверстия, м
        A: площадь отверстия, м²
        Cd: коэффициент расхода (0.60–0.65)
        g: ускорение свободного падения, м/с²

    Returns:
        Расход, м3/с
    """
    if H <= 0:
        return 0.0
    Q = Cd * A * np.sqrt(2 * g * H)
    return float(Q)


def spillway_capacity_check(
    Q_design: float,
    H_max: float,
    L: float,
    weir_type: str = 'sharp_crested',
    Cd: Optional[float] = None,
    n_openings: int = 1,
    opening_width: float = 0,
    opening_height: float = 0,
    orifice_Cd: float = 0.62,
) -> Dict:
    """
    Проверка пропускной способности ППУ (СП 58 п.6).

    Сравнивает расчётный расход с пропускной способностью водосброса.

    Parameters:
        Q_design: расчётный расход паводка, м3/с
        H_max: максимальный напор (НПУ - УМЧ), м
        L: длина гребня водосброса, м
        weir_type: тип водосброса
        n_openings: количество отверстий (для шахтного водосброса)
        opening_width: ширина отверстия, м (для шахтного)
        opening_height: высота отверстия, м (для шахтного)

    Returns:
        Dict: Q_capacity, Q_design, margin, is_sufficient
    """
    if opening_width > 0 and opening_height > 0 and n_openings > 0:
        A = opening_width * opening_height * n_openings
        Q_capacity = orifice_flow(H_max, A, orifice_Cd)
    else:
        Q_capacity = free_overfall(H_max, L, Cd or 1.84)

    margin = (Q_capacity - Q_design) / Q_design * 100 if Q_design > 0 else 0
    is_sufficient = Q_capacity >= Q_design

    return {
        'Q_capacity_m3_s': round(Q_capacity, 2),
        'Q_design_m3_s': round(Q_design, 2),
        'margin_percent': round(float(margin), 1),
        'is_sufficient': is_sufficient,
        'H_max_m': H_max,
        'L_m': L,
    }


def emergency_flood_passage(
    Q_emergency: float,
    L: float,
    Cd: float = 1.84,
    max_H: float = 5.0,
) -> Dict:
    """
    Расчёт НПР (напора при пропуске ПФР) для определения высоты плотины.

    Нужно найти H при котором Q(H) = Q_emergency.

    Parameters:
        Q_emergency: расход ПФР, м3/с
        L: длина гребня, м
        Cd: коэффициент расхода
        max_H: максимальный искомый напор, м

    Returns:
        Dict: H_required, Q_capacity, is_safe
    """
    if Q_emergency <= 0:
        return {'H_required': 0, 'Q_capacity': 0, 'is_safe': True}

    H = np.linspace(0.01, max_H, 1000)
    Q = free_overfall(H, L, Cd)

    idx = np.searchsorted(Q, Q_emergency)

    if idx < len(H):
        H_req = float(H[idx])
    else:
        H_req = float(max_H)

    Q_at_H = free_overfall(H_req, L, Cd)

    return {
        'H_required_m': round(H_req, 2),
        'Q_capacity_at_H': round(Q_at_H, 2),
        'Q_emergency': round(Q_emergency, 2),
        'is_safe': Q_at_H >= Q_emergency * 1.05,
    }
