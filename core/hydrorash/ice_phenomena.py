"""
core/hydrorash/ice_phenomena.py
Модуль расчёта ледовых явлений (ледостав, ледоход, толщина льда, заторные паводки)

Реализация расчётов по нормативным документам:
- СП 33-101-2003, раздел 8.5 — ледовые явления
- СП 58.13330.2019, раздел 7 — ледовой режим рек
- РД 52-26-2008 — методика оценки ледовых явлений
- ГОСТ 19179-73 — ледовые наблюдения
- Методические указания РГГМУ по расчёту заторных паводков

Основные функции:
- compute_ice_cover_stats — статистика ледостава и ледохода
- estimate_max_ice_thickness — максимальная толщина льда
- ice_jam_rise — повышение уровня при заторном паводке
- ice_jam_flood_level — расчётный уровень при заторном паводке
- ice_cover_duration — длительность ледостава
- freeze_up_date_analysis — анализ дат ледостава
- ice_breakup_date_analysis — анализ дат ледохода
- get_ice_parameters_by_zone — параметры ледового режима по зоне
- estimate_ice_thickness_by_formula — расчёт толщины льда по формуле Кондратьева
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum


class ClimateZone(Enum):
    """Климатические зоны России (по карте СП 58.13330.2019, приложение Б)"""
    ARCTIC = "арктическая"
    SUBARCTIC = "субарктическая"
    COLD_HUMID = "холодная влажная"
    MODERATE = "умеренная"
    DRY = "сухая"
    SEMI_ARID = "полузасушливая"


# ─────────────────────────────────────────────────────────────────────
# Справочные таблицы
# ─────────────────────────────────────────────────────────────────────

# Таблица 7.1 СП 58.13330.2019: типичные параметры ледового режима
ICE_PARAMS_BY_ZONE: Dict[ClimateZone, Dict] = {
    ClimateZone.ARCTIC: {
        "max_thickness_range_m": (1.5, 3.0),
        "freeze_period_days": (200, 260),
        "typical_rise_m": (1.5, 3.0),
        "freeze_up_doy_range": (260, 310),
        "breakup_doy_range": (110, 160),
        "ice_duration_days": (200, 260),
        "zone_coefficient": 1.0,
        "snow_correction": 0.8,
        "description": "Северная зона с постоянным или многолетним льдом",
    },
    ClimateZone.SUBARCTIC: {
        "max_thickness_range_m": (1.0, 2.0),
        "freeze_period_days": (180, 230),
        "typical_rise_m": (1.0, 2.5),
        "freeze_up_doy_range": (270, 320),
        "breakup_doy_range": (100, 150),
        "ice_duration_days": (180, 230),
        "zone_coefficient": 0.85,
        "snow_correction": 0.85,
        "description": "Зона с длительным периодом со снежным покровом",
    },
    ClimateZone.COLD_HUMID: {
        "max_thickness_range_m": (0.8, 1.5),
        "freeze_period_days": (160, 200),
        "typical_rise_m": (0.8, 2.0),
        "freeze_up_doy_range": (290, 330),
        "breakup_doy_range": (90, 130),
        "ice_duration_days": (160, 200),
        "zone_coefficient": 0.70,
        "snow_correction": 0.90,
        "description": "Холодная влажная зона (Западная Сибирь)",
    },
    ClimateZone.MODERATE: {
        "max_thickness_range_m": (0.5, 1.2),
        "freeze_period_days": (120, 180),
        "typical_rise_m": (0.5, 1.5),
        "freeze_up_doy_range": (310, 350),
        "breakup_doy_range": (70, 120),
        "ice_duration_days": (120, 180),
        "zone_coefficient": 0.55,
        "snow_correction": 1.0,
        "description": "Умеренная зона (Центральная Россия)",
    },
    ClimateZone.DRY: {
        "max_thickness_range_m": (0.3, 0.8),
        "freeze_period_days": (90, 150),
        "typical_rise_m": (0.3, 1.0),
        "freeze_up_doy_range": (320, 355),
        "breakup_doy_range": (60, 100),
        "ice_duration_days": (90, 150),
        "zone_coefficient": 0.40,
        "snow_correction": 1.10,
        "description": "Сухая зона (юг Сибири, Приуралье)",
    },
    ClimateZone.SEMI_ARID: {
        "max_thickness_range_m": (0.2, 0.5),
        "freeze_period_days": (60, 120),
        "typical_rise_m": (0.2, 0.8),
        "freeze_up_doy_range": (330, 360),
        "breakup_doy_range": (50, 80),
        "ice_duration_days": (60, 120),
        "zone_coefficient": 0.30,
        "snow_correction": 1.20,
        "description": "Полузасушливая зона (юг России, Казахстан)",
    },
}

# Коэффициенты A для формулы d_max = A * sqrt(|T_jan|) по зонам
# РД 52-26-2008, таблица приложения
THICKNESS_COEFF_A: Dict[ClimateZone, float] = {
    ClimateZone.ARCTIC: 0.45,
    ClimateZone.SUBARCTIC: 0.40,
    ClimateZone.COLD_HUMID: 0.36,
    ClimateZone.MODERATE: 0.32,
    ClimateZone.DRY: 0.28,
    ClimateZone.SEMI_ARID: 0.22,
}

# Условия возникновения заторов (СП 33-101-2003, п. 8.5.3)
JAM_PROBABILITY_TABLE: Dict[float, float] = {
    # channel_width_m -> relative probability of jam formation (0..1)
    20: 0.85,
    50: 0.65,
    100: 0.45,
    150: 0.30,
    200: 0.20,
    300: 0.10,
    500: 0.05,
}


def _interpolate_table(
    table: Dict[float, float],
    x: float
) -> float:
    """Линейная интерполяция по таблице значений."""
    keys = sorted(table.keys())
    if x <= keys[0]:
        return table[keys[0]]
    if x >= keys[-1]:
        return table[keys[-1]]
    for i in range(len(keys) - 1):
        if keys[i] <= x <= keys[i + 1]:
            t = (x - keys[i]) / (keys[i + 1] - keys[i])
            return table[keys[i]] + t * (table[keys[i + 1]] - table[keys[i]])
    return table[keys[-1]]


# ─────────────────────────────────────────────────────────────────────
# 1. Статистика ледостава и ледохода
# ─────────────────────────────────────────────────────────────────────

def compute_ice_cover_stats(
    ice_start_dates: pd.Series,
    ice_end_dates: pd.Series
) -> Dict:
    """
    Статистика ледостава и ледохода.

    Рассчитывает средние, ранние и поздние даты начала и конца
    ледостава, а также длительность ледового покрова.

    Соответствие: СП 58.13330.2019, раздел 7.2; РД 52-26-2008.

    Parameters:
        ice_start_dates: Серия дат (день года) образования ледяного покрова
        ice_end_dates: Серия дат (день года) вскрытия реки от льда

    Returns:
        Словарь со статистикой ледостава и ледохода
    """
    if len(ice_start_dates) == 0 or len(ice_end_dates) == 0:
        raise ValueError("Ряды дат не должны быть пустыми")

    start = ice_start_dates.dropna().astype(float)
    end = ice_end_dates.dropna().astype(float)

    if len(start) == 0 or len(end) == 0:
        raise ValueError("После удаления пропусков ряды пусты")

    start_mean = float(start.mean())
    start_std = float(start.std(ddof=1)) if len(start) > 1 else 0.0
    end_mean = float(end.mean())
    end_std = float(end.std(ddof=1)) if len(end) > 1 else 0.0

    # Ранняя/поздняя дата = средняя ± СКО (по РД 52-26-2008)
    start_early = max(1.0, start_mean - start_std)
    start_late = min(366.0, start_mean + start_std)
    end_early = max(1.0, end_mean - end_std)
    end_late = min(366.0, end_mean + end_std)

    # Длительность ледостава по каждому году
    durations = []
    common_years = ice_start_dates.index.intersection(ice_end_dates.index)
    for year in common_years:
        s = ice_start_dates.get(year)
        e = ice_end_dates.get(year)
        if pd.notna(s) and pd.notna(e):
            dur = ice_cover_duration(int(s), int(e))
            durations.append(dur)

    durations = np.array(durations) if durations else np.array([0.0])
    dur_mean = float(np.mean(durations)) if len(durations) > 0 else 0.0
    dur_std = float(np.std(durations, ddof=1)) if len(durations) > 1 else 0.0

    return {
        "freeze_up": {
            "mean_day": round(start_mean, 1),
            "std_days": round(start_std, 1),
            "early_day": round(start_early, 1),
            "late_day": round(start_late, 1),
            "n_years": len(start),
            "min_day": round(float(start.min()), 1),
            "max_day": round(float(start.max()), 1),
        },
        "breakup": {
            "mean_day": round(end_mean, 1),
            "std_days": round(end_std, 1),
            "early_day": round(end_early, 1),
            "late_day": round(end_late, 1),
            "n_years": len(end),
            "min_day": round(float(end.min()), 1),
            "max_day": round(float(end.max()), 1),
        },
        "ice_cover_duration": {
            "mean_days": round(dur_mean, 1),
            "std_days": round(dur_std, 1),
            "min_days": int(np.min(durations)) if len(durations) > 0 else 0,
            "max_days": int(np.max(durations)) if len(durations) > 0 else 0,
            "n_years": len(durations),
        },
        "normative": "СП 58.13330.2019, РД 52-26-2008",
    }


# ─────────────────────────────────────────────────────────────────────
# 2. Максимальная толщина льда
# ─────────────────────────────────────────────────────────────────────

def estimate_max_ice_thickness(
    latitude: float,
    mean_jan_temp: float,
    zone: ClimateZone = ClimateZone.MODERATE
) -> Dict:
    """
    Оценка максимальной толщины льда на реках.

    Используются две методики:
    1. Эмпирическая формула d_max = A * sqrt(|T_jan|) (РД 52-26-2008)
    2. Табличные значения по климатической зоне (СП 58.13330.2019, таблица 7.1)

    Parameters:
        latitude: широта места, градусы
        mean_jan_temp: средняя температура января, °C (отрицательная)
        zone: климатическая зона

    Returns:
        Словарь с оценкой толщины льда, уверенностью и использованной формулой
    """
    mean_jan_temp = abs(mean_jan_temp)
    a = THICKNESS_COEFF_A.get(zone, 0.32)

    # Формула по РД 52-26-2008
    thickness_formula = a * np.sqrt(mean_jan_temp)

    # Табличная оценка по зоне
    params = ICE_PARAMS_BY_ZONE.get(zone, ICE_PARAMS_BY_ZONE[ClimateZone.MODERATE])
    t_min, t_max = params["max_thickness_range_m"]
    thickness_table = (t_min + t_max) / 2.0

    # Взвешенная оценка (60% формула, 40% таблица)
    thickness_weighted = 0.6 * thickness_formula + 0.4 * thickness_table

    # Корректировка по широте: на севере толще (СП 58.13330.2019, п. 7.3)
    lat_factor = 1.0 + 0.005 * max(0, latitude - 55.0)
    thickness_weighted *= lat_factor

    # Границы разброса
    thickness_low = thickness_weighted * 0.8
    thickness_high = thickness_weighted * 1.2

    # Уверенность
    if len(THICKNESS_COEFF_A) > 0 and zone in THICKNESS_COEFF_A:
        confidence = "средняя"
    else:
        confidence = "пониженная"

    return {
        "thickness_m": round(thickness_weighted, 3),
        "thickness_range_m": (round(thickness_low, 3), round(thickness_high, 3)),
        "formula_thickness_m": round(thickness_formula, 3),
        "table_thickness_m": round(thickness_table, 3),
        "lat_factor": round(lat_factor, 3),
        "zone": zone.value,
        "formula_used": f"d = {a:.2f} * sqrt(|T_jan|) = {thickness_formula:.3f} м",
        "confidence": confidence,
        "normative": "РД 52-26-2008; СП 58.13330.2019, таблица 7.1",
    }


def estimate_ice_thickness_by_formula(
    mean_winter_temp: float,
    water_depth: float,
    flow_velocity: float = 0.0,
    snow_depth: float = 0.3
) -> float:
    """
    Расчёт толщины льда по формуле Кондратьева (1968).

    Формула: d = K * sqrt(Sum(T_negative) / (1 + 0.04 * V^2))
    где:
        K — коэффициент снежного покрова (0.8 при нормальном снежном покрове,
            0.6 при отсутствии снега, 1.1 при толстом снежном покрове)
        Sum(T_negative) — сумма отрицательных среднесуточных температур
            за период ледостава (°C·сутки)
        V — средняя скорость течения в период образования льда, м/с

    Упрощённый вариант для умеренной зоны:
        d ≈ 0.8 * sqrt(-T_winter)

    Соответствие: СП 33-101-2003, п. 8.5.2; Кондратьев В.Г. (1968).

    Parameters:
        mean_winter_temp: сумма отрицательных температур за зиму, °C·сутки
            (передаётся как положительное число, т.е. |sum(T_neg)|)
        water_depth: глубина воды в период ледостава, м
        flow_velocity: скорость течения, м/с
        snow_depth: средняя глубина снежного покрова на льду, м

    Returns:
        Толщина льда, м
    """
    if mean_winter_temp <= 0:
        raise ValueError("Сумма отрицательных температур должна быть положительной (передать модуль)")

    # Коэффициент снежного покрова K (Кондратьев, 1968)
    # K = 1.1 при толстом снеге (>0.5м), 0.8 при нормальном (0.2-0.4м), 0.6 при отсутствии
    if snow_depth <= 0.05:
        k_snow = 0.60
    elif snow_depth <= 0.15:
        k_snow = 0.70
    elif snow_depth <= 0.30:
        k_snow = 0.80
    elif snow_depth <= 0.50:
        k_snow = 0.90
    else:
        k_snow = 1.00

    # Коэффициент влияния скорости течения
    velocity_factor = 1.0 + 0.04 * flow_velocity ** 2

    # Формула Кондратьева
    thickness = k_snow * np.sqrt(mean_winter_temp / velocity_factor)

    # Ограничение по глубине: толщина льда не может превышать глубину воды
    thickness = min(thickness, water_depth * 0.95)

    return round(float(thickness), 3)


# ─────────────────────────────────────────────────────────────────────
# 3. Повышение уровня воды при ледоходном заторе
# ─────────────────────────────────────────────────────────────────────

def ice_jam_rise(
    channel_width: float,
    ice_thickness: float,
    flow_velocity: float = 1.0
) -> Dict:
    """
    Расчёт повышения уровня воды при ледоходном заторе.

    Методика основана на следующих соотношениях (ГОСТ 19179-73,
    методические указания РГГМУ):

    Условия возникновения заторов (СП 33-101-2003, п. 8.5.3):
    - На узких руслах (B < 50 м) — значительное повышение (до 2-4 м)
    - На средних руслах (50 < B < 200 м) — умеренное (0.5-2 м)
    - На широких руслах (B > 200 м) — незначительное (< 0.5 м)

    Формула повышения по методу Саварена (упрощённая):
        ΔH = C * (d_лёд / B)^0.5 * (V / V_крит)^0.3
    где:
        C — коэффициент, зависящий от характера русла (1.5-3.0)
        d_лёд — толщина вскрывающегося льда
        B — ширина русла
        V — скорость потока
        V_крит — критическая скорость (принимается 0.5 м/с для весеннего ледохода)

    Parameters:
        channel_width: ширина русла, м
        ice_thickness: толщина вскрывающегося льда, м
        flow_velocity: средняя скорость потока, м/с

    Returns:
        Словарь с величиной повышения, вероятностью затора и формулой
    """
    if channel_width <= 0:
        raise ValueError("Ширина русла должна быть положительной")
    if ice_thickness <= 0:
        raise ValueError("Толщина льда должна быть положительной")

    # Вероятность формирования затора (по таблице)
    jam_prob = _interpolate_table(JAM_PROBABILITY_TABLE, channel_width)

    # Коэффициент характера русла (СП 33-101-2003, п. 8.5.3)
    # Для извилистых рек C выше
    if channel_width < 50:
        c_coeff = 2.8
    elif channel_width < 100:
        c_coeff = 2.2
    elif channel_width < 200:
        c_coeff = 1.7
    else:
        c_coeff = 1.2

    v_critical = 0.5  # м/с, критическая скорость для весеннего ледохода
    velocity_ratio = max(flow_velocity / v_critical, 0.1)

    # Формула повышения уровня (метод Саварена, упрощённая)
    delta_h = c_coeff * np.sqrt(ice_thickness / channel_width) * (velocity_ratio ** 0.3)

    # Дополнительная поправка на уклоны русла
    # Для пологих рек (B > 100 м) повышение меньше
    if channel_width > 150:
        delta_h *= 0.85

    delta_h = round(float(delta_h), 3)

    # Классификация по СП 33-101-2003
    if delta_h > 2.0:
        severity = "опасный"
    elif delta_h > 1.0:
        severity = "значительный"
    elif delta_h > 0.5:
        severity = "умеренный"
    else:
        severity = "незначительный"

    return {
        "rise_m": delta_h,
        "jam_probability": round(jam_prob, 2),
        "severity": severity,
        "channel_width_m": channel_width,
        "ice_thickness_m": ice_thickness,
        "formula_used": (
            f"ΔH = {c_coeff:.1f} * sqrt({ice_thickness:.2f}/{channel_width:.0f}) * "
            f"({velocity_ratio:.2f})^0.3 = {delta_h:.3f} м"
        ),
        "normative": "СП 33-101-2003, п. 8.5.3; ГОСТ 19179-73; методика РГГМУ",
    }


# ─────────────────────────────────────────────────────────────────────
# 4. Расчётный уровень при заторном паводке
# ─────────────────────────────────────────────────────────────────────

def ice_jam_flood_level(
    H_normal: float,
    channel_width: float,
    ice_thickness: float,
    flow_velocity: float = 1.0,
    return_period_years: int = 100
) -> Dict:
    """
    Расчётный уровень воды при заторном паводке.

    H_ice = H_безледный + ΔH_затор * k_P

    где:
        H_безледный — уровень паводка без льда (расчётная обеспеченность)
        ΔH_затор — дополнительное повышение уровня из-за затора
        k_P — коэффициент вероятности затора для данного периода возврата

    Коэффициенты k_P (СП 33-101-2003, п. 8.5.4):
        T = 2 года  -> k_P = 0.9
        T = 5 года  -> k_P = 0.8
        T = 10 года -> k_P = 0.7
        T = 25 года -> k_P = 0.6
        T = 50 года -> k_P = 0.5
        T = 100 года -> k_P = 0.4
        T = 500 года -> k_P = 0.3

    Это связано с тем, что вероятность одновременного совпадения паводка
    и затора уменьшается с ростом периода возврата.

    Parameters:
        H_normal: расчётный уровень без льда, м
        channel_width: ширина русла, м
        ice_thickness: толщина вскрывающегося льда, м
        flow_velocity: скорость потока, м/с
        return_period_years: период возврата, лет

    Returns:
        Словарь с расчётным уровнем, повышением и параметрами
    """
    if return_period_years <= 0:
        raise ValueError("Период возврата должен быть положительным")

    # Коэффициент вероятности затора k_P (СП 33-101-2003, п. 8.5.4)
    kp_table = {2: 0.9, 5: 0.8, 10: 0.7, 25: 0.6, 50: 0.5, 100: 0.4, 500: 0.3}
    k_periods = sorted(kp_table.keys())

    if return_period_years <= k_periods[0]:
        k_P = kp_table[k_periods[0]]
    elif return_period_years >= k_periods[-1]:
        k_P = kp_table[k_periods[-1]]
    else:
        for i in range(len(k_periods) - 1):
            if k_periods[i] <= return_period_years <= k_periods[i + 1]:
                t = (return_period_years - k_periods[i]) / (k_periods[i + 1] - k_periods[i])
                k_P = kp_table[k_periods[i]] + t * (kp_table[k_periods[i + 1]] - kp_table[k_periods[i]])
                break
        else:
            k_P = 0.4

    # Повышение уровня при заторе
    jam_result = ice_jam_rise(channel_width, ice_thickness, flow_velocity)
    delta_h_base = jam_result["rise_m"]

    # Итоговое повышение с учётом вероятности
    delta_h = delta_h_base * k_P
    delta_h = round(delta_h, 3)

    # Расчётный уровень
    H_ice = H_normal + delta_h

    return {
        "H_ice_m": round(H_ice, 3),
        "H_normal_m": H_normal,
        "rise_m": delta_h,
        "rise_base_m": delta_h_base,
        "k_P": round(k_P, 2),
        "return_period_years": return_period_years,
        "jam_probability": jam_result["jam_probability"],
        "severity": jam_result["severity"],
        "normative": "СП 33-101-2003, п. 8.5.4; методика РГГМУ",
    }


# ─────────────────────────────────────────────────────────────────────
# 5. Длительность ледостава
# ─────────────────────────────────────────────────────────────────────

def ice_cover_duration(
    freeze_day_of_year: int,
    break_day_of_year: int
) -> int:
    """
    Длительность периода ледостава (сутки).

    Учитывает переход через 1 января: ледостав в ноябре (DOY > 180),
    вскрытие в апреле (DOY < 180).

    Соответствие: СП 58.13330.2019, раздел 7.2.

    Parameters:
        freeze_day_of_year: день года начала ледостава (1-366)
        break_day_of_year: день года вскрытия (1-366)

    Returns:
        Длительность ледостава в сутках
    """
    if not (1 <= freeze_day_of_year <= 366):
        raise ValueError(f"freeze_day_of_year должен быть от 1 до 366, получено: {freeze_day_of_year}")
    if not (1 <= break_day_of_year <= 366):
        raise ValueError(f"break_day_of_year должен быть от 1 до 366, получено: {break_day_of_year}")

    if freeze_day_of_year <= break_day_of_year:
        # Ледостав и вскрытие в пределах одного календарного года (редко)
        duration = break_day_of_year - freeze_day_of_year
    else:
        # Нормальный случай: ледостав осенью, вскрытие весной
        duration = (366 - freeze_day_of_year) + break_day_of_year

    return max(0, int(round(duration)))


# ─────────────────────────────────────────────────────────────────────
# 6. Анализ дат ледостава
# ─────────────────────────────────────────────────────────────────────

def freeze_up_date_analysis(
    dates: pd.Series,
    period: str = "year"
) -> Dict:
    """
    Анализ дат ледостава (средняя, ранняя, поздняя).

    Соответствие: СП 58.13330.2019, раздел 7.2; РД 52-26-2008.

    Parameters:
        dates: Серия дат ледостава (datetime или день года, 1-366)
        period: период анализа ("year", "month", "decade")

    Returns:
        Словарь со статистическими характеристиками дат
    """
    if len(dates) == 0:
        raise ValueError("Ряд дат пуст")

    values = dates.dropna().astype(float)

    if len(values) == 0:
        raise ValueError("После удаления пропусков ряд пуст")

    mean_val = float(values.mean())
    std_val = float(values.std(ddof=1)) if len(values) > 1 else 0.0

    # Ранняя/поздняя = средняя ± СКО
    early = max(1.0, mean_val - std_val)
    late = min(366.0, mean_val + std_val)

    # Экстремальные значения
    min_val = float(values.min())
    max_val = float(values.max())

    # Мода (наиболее частый день года, ±5 дней)
    if len(values) >= 5:
        rounded = values.round(-1)  # округление до 10 дней для моды
        mode_bin = rounded.mode()
        mode_day = float(mode_bin.iloc[0]) if len(mode_bin) > 0 else mean_val
    else:
        mode_day = mean_val

    # Процентили
    p5 = float(values.quantile(0.05))
    p95 = float(values.quantile(0.95))

    return {
        "mean_day": round(mean_val, 1),
        "std_days": round(std_val, 1),
        "early_day": round(early, 1),
        "late_day": round(late, 1),
        "min_day": round(min_val, 1),
        "max_day": round(max_val, 1),
        "mode_day": round(mode_day, 1),
        "p5_day": round(p5, 1),
        "p95_day": round(p95, 1),
        "n_years": len(values),
        "period": period,
        "normative": "СП 58.13330.2019, РД 52-26-2008",
    }


# ─────────────────────────────────────────────────────────────────────
# 7. Анализ дат ледохода
# ─────────────────────────────────────────────────────────────────────

def ice_breakup_date_analysis(
    dates: pd.Series
) -> Dict:
    """
    Анализ дат ледохода (средняя, ранняя, поздняя).

    Соответствие: СП 58.13330.2019, раздел 7.2; РД 52-26-2008.

    Parameters:
        dates: Серия дат вскрытия реки от льда (datetime или день года, 1-366)

    Returns:
        Словарь со статистическими характеристиками дат вскрытия
    """
    if len(dates) == 0:
        raise ValueError("Ряд дат пуст")

    values = dates.dropna().astype(float)

    if len(values) == 0:
        raise ValueError("После удаления пропусков ряд пуст")

    mean_val = float(values.mean())
    std_val = float(values.std(ddof=1)) if len(values) > 1 else 0.0

    early = max(1.0, mean_val - std_val)
    late = min(366.0, mean_val + std_val)

    min_val = float(values.min())
    max_val = float(values.max())

    # Размах дат вскрытия — важная характеристика (РД 52-26-2008)
    range_days = max_val - min_val

    if len(values) >= 5:
        rounded = values.round(-1)
        mode_bin = rounded.mode()
        mode_day = float(mode_bin.iloc[0]) if len(mode_bin) > 0 else mean_val
    else:
        mode_day = mean_val

    p5 = float(values.quantile(0.05))
    p95 = float(values.quantile(0.95))

    # Классификация по ранности (РД 52-26-2008)
    if mean_val < 90:
        timing = "раннее вскрытие"
    elif mean_val > 120:
        timing = "позднее вскрытие"
    else:
        timing = "средние сроки"

    return {
        "mean_day": round(mean_val, 1),
        "std_days": round(std_val, 1),
        "early_day": round(early, 1),
        "late_day": round(late, 1),
        "min_day": round(min_val, 1),
        "max_day": round(max_val, 1),
        "range_days": round(range_days, 1),
        "mode_day": round(mode_day, 1),
        "p5_day": round(p5, 1),
        "p95_day": round(p95, 1),
        "timing": timing,
        "n_years": len(values),
        "normative": "СП 58.13330.2019, РД 52-26-2008",
    }


# ─────────────────────────────────────────────────────────────────────
# 8. Справочные параметры по климатической зоне
# ─────────────────────────────────────────────────────────────────────

def get_ice_parameters_by_zone(
    zone: ClimateZone
) -> Dict:
    """
    Справочные параметры ледового режима по климатической зоне.

    На основе СП 58.13330.2019, таблица 7.1 и приложение Б.

    Parameters:
        zone: климатическая зона

    Returns:
        Словарь с параметрами: максимальная толщина, период ледостава,
        типичное повышение при заторе и др.
    """
    params = ICE_PARAMS_BY_ZONE.get(zone)
    if params is None:
        raise ValueError(
            f"Неизвестная климатическая зона: {zone}. "
            f"Доступные: {[z.value for z in ClimateZone]}"
        )

    return {
        "zone": zone.value,
        "max_thickness_range_m": params["max_thickness_range_m"],
        "freeze_period_days": params["freeze_period_days"],
        "ice_duration_days": params["ice_duration_days"],
        "typical_rise_m": params["typical_rise_m"],
        "freeze_up_doy_range": params["freeze_up_doy_range"],
        "breakup_doy_range": params["breakup_doy_range"],
        "zone_coefficient": params["zone_coefficient"],
        "snow_correction": params["snow_correction"],
        "description": params["description"],
        "normative": "СП 58.13330.2019, таблица 7.1, приложение Б",
    }
