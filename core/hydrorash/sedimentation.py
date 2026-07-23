"""
core/hydrorash/sedimentation.py
Накопление наносов в водохранилищах — СП 58.13330.2019

Основные функции:
- trap_efficiency — степень задержания наносов (формула Брая)
- sediment_yield — годовой приход наносов
- reservoir_lifetime — срок службы водохранилища
- sediment_deposition — объём отложений
"""

import numpy as np
from typing import Dict


def trap_efficiency(
    V_km3: float,
    Q_mean_m3_s: float,
) -> float:
    """
    Степень задержания наносов (формула Брая, 1972).

    E = 1 - 0.057 * V^(0.58) / Q^(0.14)

    Parameters:
        V_km3: объём водохранилища, км³
        Q_mean_m3_s: средний расход в реке, м³/с

    Returns:
        Степень задержания (0–1)
    """
    if V_km3 <= 0 or Q_mean_m3_s <= 0:
        return 0
    E = 1 - 0.057 * (V_km3 ** 0.58) / (Q_mean_m3_s ** 0.14)
    return float(np.clip(E, 0, 1))


def sediment_yield(
    F_km2: float,
    runoff_mm: float = 300,
    soil_type: str = 'moderate',
) -> float:
    """
    Годовой приход взвешенных наносов.

    Грубая оценка: G = C × Q × F / 1000

    Parameters:
        F_km2: площадь бассейна, км²
        runoff_mm: годовой сток, мм
        soil_type: тип почв ('weak', 'moderate', 'strong')

    Returns:
        Годовой приход наносов, тыс. тонн/год
    """
    erosion_factors = {
        'weak': 0.05,
        'moderate': 0.15,
        'strong': 0.40,
    }
    C = erosion_factors.get(soil_type, 0.15)
    G = C * runoff_mm * F_km2 / 1000
    return float(G)


def reservoir_lifetime(
    V_useful_km3: float,
    sediment_rate_mln_t_per_year: float,
    sediment_density: float = 1.3,
) -> Dict:
    """
    Срок службы водохранилища (СП 58).

    T = V / (G × η / ρ)

    Parameters:
        V_useful_km3: полезный объём, км³
        sediment_rate_mln_t_per_year: годовой приход наносов, млн тонн
        sediment_density: плотность отложений, т/м³

    Returns:
        Dict: lifetime_years, is_sufficient
    """
    if sediment_rate_mln_t_per_year <= 0:
        return {'lifetime_years': float('inf'), 'is_sufficient': True}

    V_m3 = V_useful_km3 * 1e9
    G_m3_per_year = sediment_rate_mln_t_per_year * 1e6 / sediment_density

    T = V_m3 / G_m3_per_year

    is_sufficient = T > 100

    return {
        'lifetime_years': round(float(T), 0),
        'is_sufficient': is_sufficient,
        'V_useful_km3': V_useful_km3,
        'sediment_rate': sediment_rate_mln_t_per_year,
    }


def sediment_deposition_profile(
    V_total_km3: float,
    Q_mean: float,
    n_layers: int = 10,
) -> Dict:
    """
    Профиль отложений (упрощённая модель).

    Parameters:
        V_total_km3: общий объём водохранилища
        Q_mean: средний расход
        n_layers: количество слоёв для расчёта

    Returns:
        Dict: layers, years_to_fill
    """
    E = trap_efficiency(V_total_km3, Q_mean)
    V_m3 = V_total_km3 * 1e9

    layer_volume = V_m3 / n_layers
    Q_annual_m3 = Q_mean * 31.536e6
    sediment_fraction = 0.001

    annual_deposition = Q_annual_m3 * sediment_fraction * E

    if annual_deposition > 0:
        years_per_layer = layer_volume / annual_deposition
    else:
        years_per_layer = float('inf')

    layers = []
    for i in range(n_layers):
        layers.append({
            'layer': i + 1,
            'volume_km3': round(layer_volume / 1e9, 4),
            'years_to_fill': round(years_per_layer, 0),
            'cumulative_years': round(years_per_layer * (i + 1), 0),
        })

    return {
        'layers': layers,
        'years_to_fill_total': round(years_per_layer * n_layers, 0),
        'trap_efficiency': round(E, 3),
        'annual_deposition_m3': round(annual_deposition, 0),
    }
