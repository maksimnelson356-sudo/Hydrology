"""
core/hydrorash/water_balance.py
Модуль расчёта водного баланса бассейна и испарения с поверхности воды

Реализация расчётов водного баланса согласно российской гидрологической практике.
Ссылки: СП 33-101-2003, СП 529.1325800.2023, СП 32.13330.2018.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional


def water_balance(
    precipitation_mm: float,
    evaporation_mm: float,
    runoff_mm: float,
    groundwater_change_mm: float = 0.0,
    storage_change_mm: float = 0.0
) -> Dict:
    """
    Водный баланс бассейна: W = P - E - R ± ΔS ± G.

    Основное уравнение водного баланса (СП 33-101-2003, приложение 4).
    Все значения в мм за расчётный период.

    Parameters:
        precipitation_mm: осадки P (мм)
        evaporation_mm: испарение E (мм)
        runoff_mm: сток R (мм)
        groundwater_change_mm: изменение запасов грунтовых вод ±ΔG (мм)
        storage_change_mm: изменение запасов воды в водоёмах и снеге ±ΔS (мм)

    Returns:
        Словарь с уравнением баланса, невязкой и флагом сбалансированности
    """
    residual = precipitation_mm - evaporation_mm - runoff_mm - storage_change_mm - groundwater_change_mm

    balance_equation = (
        f"P({precipitation_mm:.1f}) = E({evaporation_mm:.1f}) + R({runoff_mm:.1f}) "
        f"+ ΔS({storage_change_mm:.1f}) + ΔG({groundwater_change_mm:.1f}) + W({residual:.1f})"
    )

    tolerance_pct = 5.0
    if precipitation_mm != 0:
        relative_residual = abs(residual / precipitation_mm * 100)
    else:
        relative_residual = 0.0

    is_balanced = relative_residual <= tolerance_pct

    return {
        "balance_equation": balance_equation,
        "residual_mm": round(residual, 2),
        "residual_pct": round(relative_residual, 2),
        "is_balanced": is_balanced,
        "tolerance_pct": tolerance_pct,
        "P": precipitation_mm,
        "E": evaporation_mm,
        "R": runoff_mm,
        "delta_S": storage_change_mm,
        "delta_G": groundwater_change_mm,
        "normative": "СП 33-101-2003, прил. 4"
    }


def annual_water_balance_series(
    P: pd.Series,
    E: pd.Series,
    Q: pd.Series,
    years: Optional[pd.Series] = None
) -> pd.DataFrame:
    """
    Годовой водный баланс для ряда лет.

    Рассчитывает невязку водного баланса для каждого года.
    Предполагается, что изменения запасов ΔS и ΔG равны нулю (для многолетнего
    периода или при отсутствии данных о снеге/грунтовых водах).

    Parameters:
        P: ряд годовых осадков (мм)
        E: ряд годового испарения (мм)
        Q: ряд годового стока (мм)
        years: необязательный ряд годов (если индексы P, E, Q не содержат годы)

    Returns:
        DataFrame с колонками: year, P, E, R, delta_S, balance, balance_pct
    """
    if not (len(P) == len(E) == len(Q)):
        raise ValueError("Ряды P, E и Q должны иметь одинаковую длину")

    if years is None:
        if hasattr(P.index, 'year'):
            years = pd.Series(P.index.year, index=P.index)
        else:
            years = pd.Series(range(len(P)), index=P.index)

    records = []
    for idx in range(len(P)):
        p_val = float(P.iloc[idx])
        e_val = float(E.iloc[idx])
        r_val = float(Q.iloc[idx])
        year_val = int(years.iloc[idx])

        balance = p_val - e_val - r_val
        balance_pct = abs(balance / p_val * 100) if p_val != 0 else 0.0

        records.append({
            "year": year_val,
            "P": round(p_val, 1),
            "E": round(e_val, 1),
            "R": round(r_val, 1),
            "delta_S": 0.0,
            "balance": round(balance, 1),
            "balance_pct": round(balance_pct, 1)
        })

    return pd.DataFrame(records)


def evaporation_dalton(
    water_temp: float,
    air_temp: float,
    wind_speed: float,
    A: float = 0.21
) -> float:
    """
    Испарение с поверхности воды по формуле Дальтона.

    E = A * (e_s - e_a) * (1 + 0.54 * U)

    где e_s — давление насыщенного пара при температуре воды,
    e_a — упругость водяного пара в воздухе при температуре воздуха,
    U — скорость ветра на высоте 2 м, м/с,
    A — коэффициент Дальтона (0.15–0.25 в зависимости от условий).

    Источник: СП 32.13330.2018, прил. Д; Лещенко В.П., Кboteev А.П.

    Parameters:
        water_temp: температура воды (°C)
        air_temp: температура воздуха (°C)
        wind_speed: скорость ветра на высоте 2 м (м/с)
        A: коэффициент Дальтона (по умолчанию 0.21)

    Returns:
        Испарение в мм/сутки
    """
    e_s = 6.11 * 10 ** (7.5 * water_temp / (237.3 + water_temp))
    e_a = 6.11 * 10 ** (7.5 * air_temp / (237.3 + air_temp)) * 1.0

    evap = A * (e_s - e_a) * (1 + 0.54 * wind_speed)

    return round(max(evap, 0.0), 2)


def evaporation_meschersky(
    air_temp: float,
    relative_humidity: float = 0.7,
    wind_speed: float = 2.0,
    month: int = 7
) -> float:
    """
    Формула Мещерского для расчёта испарения с водной поверхности.

    E = 0.0018 * (25 + t)^2 * (1 - a) * (1 + 0.72 * U)

    где t — температура воздуха (°C),
    a — относительная влажность (от 0 до 1),
    U — скорость ветра (м/с).

    Применяется для оценки испарения с малых водоёмов и озёр
    (Мещерский В.И., 1968).

    Parameters:
        air_temp: температура воздуха (°C)
        relative_humidity: относительная влажность (от 0 до 1)
        wind_speed: скорость ветра (м/с)
        month: номер месяца (1–12), влияет на корректировку

    Returns:
        Испарение в мм/мес (приблизительно для средних условий)
    """
    if not (0.0 <= relative_humidity <= 1.0):
        raise ValueError("Относительная влажность должна быть от 0 до 1")

    base_evap = 0.0018 * (25 + air_temp) ** 2 * (1 - relative_humidity) * (1 + 0.72 * wind_speed)

    days_in_month = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if 1 <= month <= 12:
        base_evap *= days_in_month[month]

    return round(max(base_evap, 0.0), 2)


def pan_evaporation_to_lake(
    pan_evaporation: float,
    coefficient: float = 0.68
) -> float:
    """
    Перевод испарения из испарителя в испарение с поверхности озера.

    Коэффициент зависит от размера водоёма (0.60–0.75 по данным
    ВНИИГМИ-МЦД и СП 32.13330.2018):
    - малые водоёмы (< 100 мкм): 0.60–0.65
    - средние водоёмы (100–10000 мкм): 0.65–0.70
    - крупные водоёмы (> 10000 мкм): 0.70–0.75

    Parameters:
        pan_evaporation: испарение из испарителя (мм)
        coefficient: коэффициент перевода (по умолчанию 0.68)

    Returns:
        Испарение с поверхности озера (мм)
    """
    if not (0.50 <= coefficient <= 0.85):
        raise ValueError("Коэффициент перевода должен быть от 0.50 до 0.85 (СП 32.13330.2018)")

    return round(pan_evaporation * coefficient, 2)


def runoff_coefficient(
    runoff_mm: float,
    precipitation_mm: float
) -> float:
    """
    Коэффициент стока: α = R / P.

    Показывает долю осадков, стекающую по поверхности в виде речного стока.
    Типичные значения по природным зонам (СП 33-101-2003):
    - Тундра: 0.5–0.8
    - Лесная зона: 0.3–0.5
    - Лесостепь: 0.15–0.3
    - Степь: 0.05–0.2
    - Полупустыня/пустыня: 0.0–0.05

    Parameters:
        runoff_mm: слой стока (мм)
        precipitation_mm: слой осадков (мм)

    Returns:
        Коэффициент стока (безразмерный)
    """
    if precipitation_mm == 0:
        return 0.0
    return round(runoff_mm / precipitation_mm, 4)


def infiltration_rate(
    precipitation_intensity: float,
    soil_permeability: float,
    antecedent_moisture: float = 0.5
) -> Dict:
    """
    Определение инфильтрации и поверхностного стока.

    Если интенсивность осадков < впитываемости почвы — вся вода инфильтруется
    (нет поверхностного стока). Иначе — частичная инфильтрация, остальное
    становится поверхностным стоком.

    Метод основан на принципах СП 32.13330.2018 (раздел 7) и теории Хортон-Филиппа.

    Parameters:
        precipitation_intensity: интенсивность осадков (мм/ч)
        soil_permeability: впитываемость почвы (мм/ч)
        antecedent_moisture: начальная влажность почвы (от 0 до 1)

    Returns:
        Словарь с инфильтрацией и поверхностным стоком (мм/ч)
    """
    if not (0.0 <= antecedent_moisture <= 1.0):
        raise ValueError("Начальная влажность почвы должна быть от 0 до 1")

    effective_permeability = soil_permeability * (1 - 0.8 * antecedent_moisture)
    effective_permeability = max(effective_permeability, 0.0)

    if precipitation_intensity <= effective_permeability:
        infiltration_mm = precipitation_intensity
        surface_runoff_mm = 0.0
    else:
        infiltration_mm = effective_permeability
        surface_runoff_mm = precipitation_intensity - effective_permeability

    return {
        "infiltration_mm": round(infiltration_mm, 2),
        "surface_runoff_mm": round(surface_runoff_mm, 2),
        "effective_permeability": round(effective_permeability, 2),
        "infiltration_ratio": round(infiltration_mm / precipitation_intensity, 3) if precipitation_intensity > 0 else 0.0
    }


def water_budget_coefficient(
    mean_precipitation: float,
    mean_runoff: float
) -> float:
    """
    Водоносный коэффициент: β = R / P (годовой).

    Характеризует увлажнённость территории. Нормативные значения
    по природно-климатическим зонам (СП 33-101-2003, СП 529.1325800.2023):
    - Тундра: 0.50–0.80
    - Подтайга/тайга: 0.35–0.55
    - Широколиственные леса: 0.25–0.45
    - Лесостепь: 0.15–0.30
    - Степь: 0.05–0.20
    - Полупустыня: 0.02–0.07
    - Пустыня: 0.00–0.03

    Parameters:
        mean_precipitation: среднемноголетние осадки (мм/год)
        mean_runoff: среднемноголетний сток (мм/год)

    Returns:
        Водоносный коэффициент (безразмерный)
    """
    if mean_precipitation == 0:
        return 0.0
    beta = round(mean_runoff / mean_precipitation, 4)

    if beta < 0.0 or beta > 1.0:
        raise ValueError(f"Водоносный коэффициент {beta} вне диапазона [0, 1]. Проверьте входные данные.")

    return beta
