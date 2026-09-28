"""
core/hydrorash/ice_phenomena.py
Модуль расчёта ледовых явлений (ледостав, ледоход, заторные паводки)

ИСТОЧНИКИ И ИХ ФАКТИЧЕСКИЙ СТАТУС
Проверено 2026-09-28 по публичному полному тексту СП 33-101-2003
(https://files.stroyinf.ru/Data2/1/4294815/4294815038.htm). СП 33 состоит из
разделов 1-7; раздела 8 в стандарте НЕТ.

- СП 33-101-2003 п. 7.70, 7.71 - качественные указания по зажорам и заторам.
  Числовых коэффициентов не содержат; п. 7.70 прямо требует предварительных
  специальных (полевых) исследований. Формул толщины льда стандарт не содержит
  вовсе: слово "толщина" встречается один раз, в п. 7.71, как качественный фактор.
- СП 33-101-2003 п. 7.72, формула (7.51) - расчётный наивысший уровень при зажоре
  или заторе: h_з.р.% = (μ - 1) * ... , где μ - коэффициент зажорности/заторности,
  определяемый полевыми исследованиями либо по аналогии. ЭТА ФОРМУЛА ЗДЕСЬ НЕ
  РЕАЛИЗОВАНА. Структура формулы в публичной HTML-версии отдана растром и
  не извлекается; для реализации нужен печатный оригинал стандарта.
- РД 52-26-2008 - заявлен как источник, но НЕ НАЙДЕН (проверены все документы
  вида "РД 52.*" в коллекции meganorm, 1212 записей; отсутствует). Существование
  документа этим не опровергнуто.
- СП 58.13330.2019 (таблица 7.1, приложение Б) - атрибуции ОПРОВЕРГНУТЫ по полному
  тексту стандарта: таблицы 7.1 в СП 58 нет (раздел 7 - требования безопасности
  при реконструкции), а приложение Б - "Классы ответственности гидротехнических
  сооружений", а не климатические зоны. Совпадений "климатическая зона" - ноль.
- СП 38.13330.2018 "Нагрузки и воздействия на гидротехнические сооружения
  (волновые, ледовые и от судов)" - ПРОВЕРЕНЫ полный текст (168 771 символ,
  meganorm.ru, ред. от 15.12.2021). Это единственный найденный нормативный
  документ, где ледовая тема действительно регламентирована: раздел 7
  "Ледовые нагрузки на гидротехнические сооружения" (п. 7.1-7.3 и далее).
  ОДНАКО формулы толщины льда d_max = A*sqrt(|T_jan|) в нём НЕТ: совпадений
  "hл =" и "1,5*sqrt" - ноль. По п. 7.3 толщина льда - ВХОДНЫЕ ДАННЫЕ, которые
  "назначаются путем статистической обработки материалов натурных наблюдений".
  То есть эмпирическая формула модуля остаётся без нормативного источника.

СТАТУС: перечисленные ниже расчёты - ИНЖЕНЕРНЫЕ КОНСТРУКЦИИ. Числовые таблицы
JAM_PROBABILITY_TABLE, kp_table и THICKNESS_COEFF_A не имеют подтверждённого
нормативного источника. Ранее модуль приписывал их «СП 33-101-2003 раздел 8.5» и
п. 8.5.2-8.5.4 - этих пунктов в стандарте не существует.

Основные функции:
- compute_ice_cover_stats — статистика ледостава и ледохода
- estimate_max_ice_thickness — максимальная толщина льда (инженерная оценка)
- ice_jam_rise — повышение уровня при заторном паводке (инженерная оценка)
- ice_jam_flood_level — расчётный уровень при заторном паводке (инженерная оценка)
- ice_cover_duration — длительность ледостава
- freeze_up_date_analysis — анализ дат ледостава
- ice_breakup_date_analysis — анализ дат ледохода
- get_ice_parameters_by_zone — параметры ледового режима по зоне
- estimate_ice_thickness_by_formula — оценка толщины льда (инженерная формула)
"""

from enum import Enum

import numpy as np
import pandas as pd


class ClimateZone(Enum):
    """Климатические зоны России (карта не проверена)"""
    ARCTIC = "арктическая"
    SUBARCTIC = "субарктическая"
    COLD_HUMID = "холодная влажная"
    MODERATE = "умеренная"
    DRY = "сухая"
    SEMI_ARID = "полузасушливая"


# ─────────────────────────────────────────────────────────────────────
# Справочные таблицы
# ─────────────────────────────────────────────────────────────────────

# Атрибуция «Таблица 7.1 СП 58.13330.2019» ОПРОВЕРГНУТА: такой таблицы нет.
# Значения ниже - инженерная оценка, нормативного источника не установлено.
ICE_PARAMS_BY_ZONE: dict[ClimateZone, dict] = {
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

# Коэффициенты A для формулы d_max = A * sqrt(|T_jan|) по зонам.
# ИНЖЕНЕРНЫЕ КОЭФФИЦИЕНТЫ. Ранее приписывались «РД 52-26-2008, таблица приложения» —
# источник не проверен по тексту, подтверждения значениям нет.
THICKNESS_COEFF_A: dict[ClimateZone, float] = {
    ClimateZone.ARCTIC: 0.45,
    ClimateZone.SUBARCTIC: 0.40,
    ClimateZone.COLD_HUMID: 0.36,
    ClimateZone.MODERATE: 0.32,
    ClimateZone.DRY: 0.28,
    ClimateZone.SEMI_ARID: 0.22,
}

# ИНЖЕНЕРНАЯ ТАБЛИЦА. Ранее комментировалась как «Условия возникновения заторов
# (СП 33-101-2003, п. 8.5.3)» - такого пункта в СП 33-101-2003 не существует.
# СП 33 п. 7.70/7.71 дают только качественные признаки и требуют полевых
# исследований; числовой вероятности затора по ширине русла стандарт не задаёт.
JAM_PROBABILITY_TABLE: dict[float, float] = {
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
    table: dict[float, float],
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
) -> dict:
    """
    Статистика ледостава и ледохода.

    Рассчитывает средние, ранние и поздние даты начала и конца
    ледостава, а также длительность ледового покрова.

    Соответствие: (источник НЕ проверен — см. docstring модуля).

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

    # Ранняя/поздняя дата = средняя ± СКО. Первоисточник не подтверждён:
    # прежняя ссылка «по РД 52-26-2008» удалена как недоказуемая.
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
        "normative": (
            "инженерная оценка; РД 52-26-2008 не найден, атрибуции СП 58 "
            "(табл. 7.1, прил. Б) ОПРОВЕРГНУТЫ "
            "по тексту (доступ платный)"
        ),
    }


# ─────────────────────────────────────────────────────────────────────
# 2. Максимальная толщина льда
# ─────────────────────────────────────────────────────────────────────

def estimate_max_ice_thickness(
    latitude: float,
    mean_jan_temp: float,
    zone: ClimateZone = ClimateZone.MODERATE
) -> dict:
    """
    Оценка максимальной толщины льда на реках.

    Используются две методики:
    1. Эмпирическая формула d_max = A * sqrt(|T_jan|)  (источник НЕ проверен — см. docstring модуля)
    2. Табличные значения по климатической зоне  (атрибуция «табл. 7.1 СП 58» ОПРОВЕРГНУТА)

    Parameters:
        latitude: широта места, градусы
        mean_jan_temp: средняя температура января, °C (отрицательная)
        zone: климатическая зона

    Returns:
        Словарь с оценкой толщины льда, уверенностью и использованной формулой
    """
    mean_jan_temp = abs(mean_jan_temp)
    a = THICKNESS_COEFF_A.get(zone, 0.32)

    # Инженерная оценка: a = f(зона), толщина = a·√|T_янв|. Первоисточник
    # не подтверждён — прежняя ссылка «по РД 52-26-2008» удалена.
    thickness_formula = a * np.sqrt(mean_jan_temp)

    # Табличная оценка по зоне
    params = ICE_PARAMS_BY_ZONE.get(zone, ICE_PARAMS_BY_ZONE[ClimateZone.MODERATE])
    t_min, t_max = params["max_thickness_range_m"]
    thickness_table = (t_min + t_max) / 2.0

    # Взвешенная оценка (60% формула, 40% таблица)
    thickness_weighted = 0.6 * thickness_formula + 0.4 * thickness_table

    # Корректировка по широте: на севере толще  (п. 7.3 СП 58 ОПРОВЕРГНУТ: это
    # требования безопасности при реконструкции, поправка оттуда не следует)
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
        "normative": (
            "инженерная оценка; «таблица 7.1» СП 58 и РД 52-26-2008 ОПРОВЕРГНУТЫ "
            "по полному тексту СП 58"
        ),
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

    Соответствие: ИНЖЕНЕРНАЯ ФОРМУЛА, нормативного источника в СП 33-101-2003 нет.
    Ранее указывалось «СП 33-101-2003, п. 8.5.2» - такого пункта не существует.
    Формулы толщины льда стандарт не содержит вовсе. Атрибуция Кондратьеву В.Г. (1968)
    здесь не подтверждена и требует первоисточника.

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

# ─────────────────────────────────────────────────────────────────────
# 4. Расчётный наивысший уровень при заторе — СП 33-101-2003, п. 7.72
# ─────────────────────────────────────────────────────────────────────

# Таблица 7.5 СП 33-101-2003 «Значения коэффициента μ» — перенесена из
# полного печатного экземпляра стандарта.
#
# Проверка 2026-09-28: третья строка таблицы равна среднему арифметическому
# первых двух во всех шести столбцах, что подтверждает перенос:
#   (27,1+17,3)/2=22,2  (22,2+14,2)/2=18,2  (18,2+11,6)/2=14,9
#   (14,9+9,5)/2=12,2   (12,2+7,8)/2=10,0   (10,0+6,4)/2=8,2
#
# Ключ — отношение приращения ширины реки ΔB/B в пределах подъёма уровня
# от H_о до H_з.р.%. Значения — коэффициент зажорности/заторности μ.
ICE_JAM_MU_TABLE: dict[str, dict[float, float]] = {
    "зажор": {
        0.0: 27.1, 0.2: 22.2, 0.4: 18.2, 0.6: 14.9, 0.8: 12.2, 1.0: 10.0,
    },
    "затор": {
        0.0: 17.3, 0.2: 14.2, 0.4: 11.6, 0.6: 9.5, 0.8: 7.8, 1.0: 6.4,
    },
    "зажор+затор": {
        0.0: 22.2, 0.2: 18.2, 0.4: 14.9, 0.6: 12.2, 0.8: 10.0, 1.0: 8.2,
    },
}

ICE_JAM_FORMATIONS = tuple(ICE_JAM_MU_TABLE)

# Псевдонимы вида ледяного образования. Явная карта вместо преобразования строки:
# вариант «зажор и затор» при наивной замене пробелов и «и» давал «зажор++затор».
_FORMATION_ALIASES: dict[str, str] = {
    "зажор": "зажор",
    "затор": "затор",
    "зажор+затор": "зажор+затор",
    "зажор и затор": "зажор+затор",
    "зажор+затора": "зажор+затор",
    "затор+зажор": "зажор+затор",
    "жор": "зажор",
    "тор": "затор",
}


def ice_jam_coefficient_mu(formation: str, delta_b_over_b: float) -> float:
    """Коэффициент зажорности/заторности μ по таблице 7.5 СП 33-101-2003, п. 7.72.

    Пункт 7.72 предписывает определять μ полевыми исследованиями на временном
    посту с учащёнными наблюдениями за ледовыми явлениями и уровнем, а при их
    отсутствии — по аналогии с реками-аналогами (перечислительные условия
    аналогии приведены в стандарте). Таблица 7.5 даёт ОРИЕНТИРОВОЧНЫЕ значения
    в зависимости от вида ледяного образования и ΔB/B; именно этой оговоркой
    стандарт и сопровождает таблицу.

    Args:
        formation: вид ледяного образования — «зажор», «затор» или «зажор+затор».
        delta_b_over_b: отношение приращения ширины реки ΔB/B, 0…1.

    Returns:
        Коэффициент μ с линейной интерполяцией по таблице 7.5.
    """
    key = _FORMATION_ALIASES.get(formation.strip().lower())
    if key is None:
        raise ValueError(
            f"Вид ледяного образования {formation!r} не найден; "
            f"допустимо: {ICE_JAM_FORMATIONS}"
        )
    if delta_b_over_b < 0:
        raise ValueError("Отношение ΔB/B не может быть отрицательным")
    return _interpolate_table(ICE_JAM_MU_TABLE[key], float(delta_b_over_b))


def ice_jam_level_772(
    slope_per_mille: float,
    mean_depth: float,
    normal_level: float,
    formation: str = "зажор+затор",
    delta_b_over_b: float = 0.4,
    mu: float | None = None,
) -> dict:
    """Расчётный наивысший уровень по формуле (7.51) п. 7.72 СП 33-101-2003.

    Стандарт предписывает:

        H_з.р.% = (μ · I^0,3 − 1) · h + H_з.р.%

    где μ — коэффициент зажорности/заторности, I — уклон водной поверхности,
    h — средняя глубина реки, м, H_з.р.% — уровень воды в расчётном створе, м.
    Все три величины I, h и H берутся при одном и том же расходе Q_з.р.% и на
    свободном от льда русле: индекс Q_з.р.% — условие отбора, а не множитель,
    отдельного расходного члена в формуле нет.

    ИСПРАВЛЕНИЕ 2026-09-28. Ранее формула читалась как (μ/(3,0·I) − 1)·h + ΔH:
    текстовый слой PDF утратил дробную черту, и 3,0 было принято за знаменатель.
    На деле 3,0 — показатель степени, а сама формула иная: без множителя
    Q_з.р.%/Q_и и с другим последним членом. Прежний выбор обосновывался
    правдоподобностью величины, но вел к отбору между двумя вариантами чтения
    дробной черты, а не между двумя разными формулами.

    НЕОДНОЗНАЧНОСТЬ ЕДИНИЦ. Стандарт подписывает I как ‰, и код принимает
    значение именно в промилле. При I = 1 ‰ и μ = 14,9 это даёт повышение
    27,8 м — величина неправдоподобная для затора. Если же I понимать как
    безразмерный уклон (0,001 для 1 ‰), то μ·I^0,3 = 1 достигается при
    μ ≈ 7,9, что попадает внутрь диапазона таблицы 7,5 (6,4…27,1), и повышение
    составляет около 1,8 м. Калибровка таблицы 7,5 согласуется именно с
    безразмерным уклоном, поэтому чтение ‰ может требовать перевода I в
    безразмерную величину. Вопрос открыт: зафиксирована структура формулы,
    но не единицы I. До его решения результат нельзя использовать для
    проектных решений.

    Args:
        slope_per_mille: уклон водной поверхности I, ‰ (см. оговорку выше).
        mean_depth: средняя глубина реки h, м.
        normal_level: уровень воды в расчётном створе H_з.р.% при расходе
            Q_з.р.% и свободном от льда русле, м.
        formation: вид ледяного образования для μ по таблице 7.5.
        delta_b_over_b: отношение приращения ширины ΔB/B, 0…1.
        mu: коэффициент μ, если он определён полевыми исследованиями. При
            None берётся из таблицы 7.5.

    Returns:
        Словарь с расчётным уровнем, повышением, μ и использованной формулой.
    """
    if slope_per_mille <= 0:
        raise ValueError(
            "Уклон I должен быть положительным: в формуле (7.51) он входит "
            "в степень 0,3"
        )
    if mean_depth <= 0:
        raise ValueError("Средняя глубина h должна быть положительной")
    # Флаг фиксируется ДО присваивания: после подстановки из таблицы проверка
    # mu is not None всегда истинна, и табличный путь помечался бы как
    # полевое исследование.
    mu_is_measured = mu is not None
    if mu is None:
        mu = ice_jam_coefficient_mu(formation, delta_b_over_b)
    elif mu <= 0:
        raise ValueError("Коэффициент μ должен быть положительным")

    rise = (mu * slope_per_mille ** 0.3 - 1.0) * mean_depth
    if rise < 0.0:
        raise ValueError(
            f"μ·I^0,3 = {mu * slope_per_mille ** 0.3:.3f} < 1, повышение "
            f"отрицательно ({rise:.3f} м). Затор не может опустить уровень ниже "
            f"исходного: проверьте μ ({mu}) и уклон I ({slope_per_mille} ‰)."
        )
    level = normal_level + rise

    mu_source = (
        "полевое исследование"
        if mu_is_measured
        else f"таблица 7.5, «{formation}», ΔB/B={delta_b_over_b}"
    )

    return {
        "level_m": round(float(level), 3),
        "rise_m": round(float(rise), 3),
        "mu": round(float(mu), 2),
        "mu_source": mu_source,
        "slope_per_mille": slope_per_mille,
        "mean_depth_m": mean_depth,
        "normal_level_m": normal_level,
        "formation": formation,
        "delta_b_over_b": delta_b_over_b,
        "formula": "H = (μ·I^0,3 − 1)·h + H, формула (7.51) п. 7.72",
        "normative": (
            "СП 33-101-2003 п. 7.72, формула (7.51). Коэффициент μ по таблице 7.5 "
            "ориентировочный; стандарт требует определять его полевыми "
            "исследованиями. Структура формулы уточнена 2026-09-28 по печатной "
            "формуле: 3,0 — показатель степени, а не знаменатель дробной черты. "
            "Открытым остаётся единица уклона I — ‰ или безразмерная величина; "
            "результат нельзя применять для проектных решений до её фиксации."
        ),
    }


def ice_jam_rise(
    channel_width: float,
    ice_thickness: float,
    flow_velocity: float = 1.0
) -> dict:
    """
    Расчёт повышения уровня воды при ледоходном заторе.

    ИНЖЕНЕРНАЯ ОЦЕНКА. Нормативного источника в СП 33-101-2003 нет:
    - п. 8.5.3, на который ранее ссылался модуль, в стандарте не существует;
    - п. 7.70/7.71 дают только качественные признаки и требуют полевых исследований;
    - предписанная формула (7.51) из п. 7.72 здесь НЕ реализована.

    Принятые в модуле соображения (инженерные, не нормативные):
    - На узких руслах (B < 50 м) — значительное повышение (до 2-4 м)
    - На средних руслах (50 < B < 200 м) — умеренное (0.5-2 м)
    - На широких руслах (B > 200 м) — незначительное (< 0.5 м)

    Формула повышения, обозначаемая в коде как «метод Саварена (упрощённый)».
    Атрибуция первоисточнику здесь НЕ подтверждена:
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

    # Коэффициент характера русла. ИНЖЕНЕРНЫЙ; ранее приписывался «п. 8.5.3»,
    # которого в СП 33-101-2003 не существует.
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
        "normative": "инженерная оценка; в СП 33-101-2003 п. 8.5.3 не существует",
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
) -> dict:
    """
    Расчётный уровень воды при заторном паводке.

    H_ice = H_безледный + ΔH_затор * k_P

    где:
        H_безледный — уровень паводка без льда (расчётная обеспеченность)
        ΔH_затор — дополнительное повышение уровня из-за затора
        k_P — коэффициент вероятности затора для данного периода возврата

    Коэффициенты k_P. Ранее приписывались «СП 33-101-2003, п. 8.5.4» - такого
    пункта в стандарте нет. Это инженерная таблица без подтверждённого источника.
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

    # Коэффициент вероятности затора k_P. ИНЖЕНЕРНЫЙ; ранее приписывался «п. 8.5.4»,
    # которого в СП 33-101-2003 не существует.
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
        "normative": "инженерная оценка; в СП 33-101-2003 п. 8.5.4 не существует",
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

    Соответствие: (источник НЕ проверен — см. docstring модуля).

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
) -> dict:
    """
    Анализ дат ледостава (средняя, ранняя, поздняя).

    Соответствие: (источник НЕ проверен — см. docstring модуля).

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
        "normative": (
            "инженерная оценка; РД 52-26-2008 не найден, атрибуции СП 58 "
            "(табл. 7.1, прил. Б) ОПРОВЕРГНУТЫ "
            "по тексту (доступ платный)"
        ),
    }


# ─────────────────────────────────────────────────────────────────────
# 7. Анализ дат ледохода
# ─────────────────────────────────────────────────────────────────────

def ice_breakup_date_analysis(
    dates: pd.Series
) -> dict:
    """
    Анализ дат ледохода (средняя, ранняя, поздняя).

    Соответствие: (источник НЕ проверен — см. docstring модуля).

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

    # Размах дат вскрытия — важная характеристика  (источник НЕ проверен — см. docstring модуля)
    range_days = max_val - min_val

    if len(values) >= 5:
        rounded = values.round(-1)
        mode_bin = rounded.mode()
        mode_day = float(mode_bin.iloc[0]) if len(mode_bin) > 0 else mean_val
    else:
        mode_day = mean_val

    p5 = float(values.quantile(0.05))
    p95 = float(values.quantile(0.95))

    # Классификация по ранности  (источник НЕ проверен — см. docstring модуля)
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
        "normative": (
            "инженерная оценка; РД 52-26-2008 не найден, атрибуции СП 58 "
            "(табл. 7.1, прил. Б) ОПРОВЕРГНУТЫ "
            "по тексту (доступ платный)"
        ),
    }


# ─────────────────────────────────────────────────────────────────────
# 8. Справочные параметры по климатической зоне
# ─────────────────────────────────────────────────────────────────────

def get_ice_parameters_by_zone(
    zone: ClimateZone
) -> dict:
    """
    Справочные параметры ледового режима по климатической зоне.

    Атрибуции «таблица 7.1» и «приложение Б» СП 58.13330.2019 ОПРОВЕРГНУТЫ по
    полному тексту стандарта (таблицы 7.1 нет; приложение Б — классы ответственности).

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
        "normative": (
            "инженерная оценка; «таблица 7.1» и «приложение Б» СП 58.13330.2019 "
            "ОПРОВЕРГНУТЫ по полному тексту СП 58"
        ),
    }
