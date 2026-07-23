"""
core/hydrorash/reservoir_regulation.py
Многолетнее регулирование стока — СП 32.13330.2018

Основные функции:
- multi_year_regulation — расчёт полезного объёма для многолетнего регулирования
- storage_yield_curve — кривая «объём — обеспеченность водоснабжения»
- reservoir_storage_calculation — расчёт объёма водохранилища
- annual_regulation_table — таблица годового регулирования
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional


def multi_year_regulation(
    Q_annual: np.ndarray,
    demand_m3_s: float,
) -> Dict:
    """
    Многолетнее регулирование стока (метод Риппла / Монте-Карло).

    Определяет необходимый объём водохранилища для обеспечения заданного
    забора воды с заданной обеспеченностью.

    Метод Риппла:
    V = max Σ(Q_i - Q_забор) за худший период

    Parameters:
        Q_annual: среднегодовые расходы за ряд лет, м3/с
        demand_m3_s: среднегодовой забор (потребление), м3/с

    Returns:
        Dict: required_volume_km3, guarantee_percent, ripple_volume
    """
    Q = np.array(Q_annual, dtype=float)
    Q = Q[~np.isnan(Q)]
    n = len(Q)

    Q_mean = float(np.mean(Q))
    Q_min = float(np.min(Q))

    if demand_m3_s > Q_mean:
        guarantee = max(0, (Q >= demand_m3_s).mean() * 100)
        return {
            'required_volume_km3': float('inf'),
            'guarantee_percent': round(guarantee, 1),
            'Q_mean': round(Q_mean, 2),
            'Q_demand': round(demand_m3_s, 2),
            'warning': 'Забор > среднего стока! Нужно много летнее регулирование.',
        }

    # Метод Риппла — суммарный дефицит худшего периода
    cumulative = np.cumsum(Q - demand_m3_s)
    max_deficit = float(-np.min(cumulative))
    V_ripple_m3 = max_deficit * 365.25 * 86400
    V_ripple_km3 = V_ripple_m3 / 1e9

    # Гарантия водоснабжения
    Q_surplus = Q - demand_m3_s
    months_surplus = 0
    total_months = 0
    running_balance = 0
    balance_series = []
    for q in Q_surplus:
        running_balance += q
        balance_series.append(running_balance)
        total_months += 12
        if running_balance >= 0:
            months_surplus += 12

    guarantee = months_surplus / total_months * 100 if total_months > 0 else 0

    return {
        'required_volume_km3': round(V_ripple_km3, 3),
        'required_volume_mln_m3': round(V_ripple_m3 / 1e6, 1),
        'guarantee_percent': round(guarantee, 1),
        'Q_mean': round(Q_mean, 2),
        'Q_demand': round(demand_m3_s, 2),
        'deficit_fraction': round(float(max_deficit / Q_mean), 3) if Q_mean > 0 else 0,
        'balance_cumulative': balance_series,
    }


def storage_yield_curve(
    Q_annual: np.ndarray,
    V_range_km3: Optional[List[float]] = None,
) -> pd.DataFrame:
    """
    Кривая «объём водохранилища — обеспеченность водоснабжения».

    Для каждого объёма V определяем максимальный Q_забор при котором
    guarantee ≥ заданного уровня.

    Parameters:
        Q_annual: среднегодовые расходы
        V_range_km3: список объёмов для расчёта, км³

    Returns:
        DataFrame: V_km3, Q_demand, guarantee_percent
    """
    if V_range_km3 is None:
        V_range_km3 = [0.1, 0.5, 1, 2, 3, 5, 8, 10, 15, 20]

    Q = np.array(Q_annual, dtype=float)
    Q = Q[~np.isnan(Q)]
    Q_mean = float(np.mean(Q))

    rows = []
    for V_km3 in V_range_km3:
        V_m3 = V_km3 * 1e9
        V_per_year = V_m3 / (365.25 * 86400)

        max_demand = Q_mean
        result = multi_year_regulation(Q, max_demand)

        rows.append({
            'V_km3': V_km3,
            'V_per_year_m3_s': round(V_per_year, 2),
            'Q_max_demand': round(max_demand, 2),
            'guarantee_%': result['guarantee_percent'],
        })

    return pd.DataFrame(rows)


def reservoir_storage_calculation(
    H_list: List[float],
    A_list: List[float],
    method: str = 'trapezoid',
) -> Dict:
    """
    Объём водохранилища по данных нивелировки (кривая «уровень-площадь-объём»).

    Метод трапеций: V_i = (A_i + A_{i+1})/2 × (H_{i+1} - H_i)

    Parameters:
        H_list: уровни, м (по возрастанию)
        A_list: площади зеркала, км²

    Returns:
        Dict: cumulative_volumes, table_df
    """
    H = np.array(H_list)
    A = np.array(A_list)

    V_cumulative = [0.0]
    for i in range(1, len(H)):
        dV = (A[i - 1] + A[i]) / 2 * (H[i] - H[i - 1])
        V_cumulative.append(V_cumulative[-1] + dV)

    df = pd.DataFrame({
        'H_m': H,
        'A_km2': A,
        'V_cumulative_km3': [round(v, 4) for v in V_cumulative],
    })

    return {
        'table': df,
        'V_total_km3': round(float(V_cumulative[-1]), 4),
    }


def annual_regulation_table(
    Q_monthly: np.ndarray,
    demand_m3_s: float,
    V_useful_km3: float = 1.0,
) -> pd.DataFrame:
    """
    Таблица годового регулирования (месячный баланс).

    Parameters:
        Q_monthly: 12 средних месячных расходов, м3/с
        demand_m3_s: средний забор, м3/с
        V_useful_km3: полезный объём, км³

    Returns:
        DataFrame с месячным балансом
    """
    months = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
              'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']

    days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

    rows = []
    V_balance = 0
    for i, (m, d) in enumerate(zip(months, days)):
        Q_in = Q_monthly[i] if i < len(Q_monthly) else 0
        Q_out = demand_m3_s
        dV = (Q_in - Q_out) * d * 86400 / 1e9
        V_balance += dV

        rows.append({
            'Месяц': m,
            'Q_приток': round(Q_in, 2),
            'Q_забор': round(Q_out, 2),
            'dV_km3': round(dV, 4),
            'V_баланс_km3': round(V_balance, 4),
            'Заполнен_%': round(V_balance / V_useful_km3 * 100, 1) if V_useful_km3 > 0 else 0,
        })

    return pd.DataFrame(rows)
