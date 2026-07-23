"""
core/hydrorash/min_runoff_extended.py
Расширенный модуль расчёта минимальных стоков

Реализация расчётов 7-суточных, 10-суточных и 30-суточных минимумов,
экосистемного минимума согласно СП 32.13330.2018 и СП 33-101-2003.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from .utils import compute_basic_stats, kritsky_menkel_quantiles


def extract_min_annual(
    daily_df: pd.DataFrame,
    year_col: str = 'year',
    value_col: str = 'value',
    period_days: int = 7,
    season: str = "winter"
) -> pd.Series:
    """
    Извлечение средних минимальных расходов за period_days суток для каждого года.

    Использует скользящее окно минимального среднего значения.
    Соответствует методике определения минимальных стоков по СП 33-101-2003, раздел 7.

    Parameters:
        daily_df: DataFrame с суточными расходами (должен содержать year_col и value_col)
        year_col: название столбца с годами
        value_col: название столбца с расходами
        period_days: длительность периода (7 или 10 суток)
        season: сезон поиска минимума:
            - "winter" — зимний период (XII–II или XI–III)
            - "summer" — летний период (VI–VIII)
            - "annual" — весь год

    Returns:
        Series с минимальными средними расходами, индексированная по годам
    """
    if year_col not in daily_df.columns or value_col not in daily_df.columns:
        raise ValueError(f"DataFrame должен содержать столбцы '{year_col}' и '{value_col}'")

    if period_days not in (7, 10, 30):
        raise ValueError("Допустимые значения period_days: 7, 10, 30")

    df = daily_df[[year_col, value_col]].copy()
    df = df.dropna(subset=[value_col])
    df[value_col] = pd.to_numeric(df[value_col], errors='coerce')
    df = df.dropna(subset=[value_col])

    if len(df) == 0:
        return pd.Series(dtype=float)

    winter_months = [11, 12, 1, 2, 3]
    summer_months = [6, 7, 8]

    if 'month' in df.columns:
        month_col = 'month'
    elif hasattr(df.index, 'month'):
        df = df.reset_index()
        month_col = 'month'
    else:
        month_col = None

    results = {}

    for year in df[year_col].unique():
        year_data = df[df[year_col] == year].copy()

        if month_col is not None and month_col in year_data.columns:
            if season == "winter":
                year_data = year_data[year_data[month_col].isin(winter_months)]
            elif season == "summer":
                year_data = year_data[year_data[month_col].isin(summer_months)]

        if len(year_data) < period_days:
            continue

        values = year_data[value_col].values
        min_avg = _sliding_window_min_mean(values, period_days)
        if min_avg is not None:
            results[year] = min_avg

    return pd.Series(results, dtype=float).sort_index()


def _sliding_window_min_mean(
    values: np.ndarray,
    window_size: int
) -> Optional[float]:
    """
    Поиск минимального среднего значения в скользящем окне.

    Parameters:
        values: массив значений расходов
        window_size: размер окна (7, 10 или 30)

    Returns:
        Минимальное среднее значение или None
    """
    if len(values) < window_size:
        return None

    window_sums = np.convolve(values, np.ones(window_size), mode='valid')
    window_means = window_sums / window_size
    idx_min = np.argmin(window_means)
    min_mean = float(window_means[idx_min])

    return min_mean


def compute_min_runoff_stats(
    min_series: pd.Series,
    period_days: int = 7,
    use_normative_Cs: bool = True
) -> Dict:
    """
    Статистика ряда минимальных стоков (7/10-суточных).

    Рассчитывает основные статистические характеристики: среднее, Cv, Cs,
    погрешность оценки ε. Использует функцию compute_basic_stats из utils.

    Parameters:
        min_series:.Series с годовыми минимальными средними расходами
        period_days: длительность периода (7 или 10 суток)
        use_normative_Cs: использовать нормативное Cs = 2×Cv (СП 33-101-2003 п. 6.3.3)

    Returns:
        Словарь со статистическими характеристиками
    """
    series = min_series.dropna()

    if len(series) < 3:
        return {
            "mean": None,
            "Cv": None,
            "Cs": None,
            "Cs/Cv": None,
            "epsilon": None,
            "n": len(series),
            "period_days": period_days,
            "reliability_class": "Недостаточно данных",
            "warnings": ["Длина ряда < 3 лет. Статистические расчёты невозможны."]
        }

    basic = compute_basic_stats(series, use_normative_Cs=use_normative_Cs)
    basic["period_days"] = period_days

    if basic["n"] < 10:
        basic["warnings"].append(
            f"Длина ряда {basic['n']} лет. Для 7-суточных минимумов рекомендуется ≥ 10 лет (СП 33-101-2003 п. 6.2.2)."
        )

    return basic


def min_runoff_frequency_curve(
    min_series: pd.Series,
    P_values: Optional[List[float]] = None,
    use_normative_Cs: bool = True
) -> pd.DataFrame:
    """
    Кривая обеспечённости минимальных стоков.

    Рассчитывает аналитическую кривую обеспеченностей по методу Крицкого-Менкеля
    (СП 33-101-2003 п. 6.4) для ряда минимальных стоков.

    Parameters:
        min_series:.Series с годовыми минимальными расходами
        P_values: список обеспеченностей в процентах (по умолчанию нормативные)
        use_normative_Cs: использовать нормативное Cs = 2×Cv

    Returns:
        DataFrame с колонками: P_%, Q_min
    """
    if P_values is None:
        P_values = [80, 90, 95, 97, 99, 99.5, 99.9]

    series = min_series.dropna()

    if len(series) < 3:
        raise ValueError("Для построения кривой обеспечённости нужно ≥ 3 года данных")

    stats = compute_min_runoff_stats(series, use_normative_Cs=use_normative_Cs)
    mean_val = stats["mean"]
    Cv = stats["Cv"]
    Cs_over_Cv = stats.get("Cs/Cv", 2.0)

    km_curve = kritsky_menkel_quantiles(
        mean=mean_val,
        Cv=Cv,
        Cs_over_Cv=Cs_over_Cv,
        P_list=P_values
    )

    return pd.DataFrame({
        "P_%": km_curve["P_%"],
        "Q_min": km_curve["Q_p"].round(2)
    })


def ecosystem_minimum(
    mean_annual_flow: float,
    method: str = "tenpct"
) -> Dict:
    """
    Экосистемный (экологический) минимальный сток (СП 32.13330.2018, раздел 8).

    Методы расчёта:
    - "tenpct": Q_экос = 0.1 × Qср (10% от среднегодового расхода)
    - "7q10": статистический 7-day 10-year minimum (требует суточного ряда)
    - "tessmann": метод Тессманна Q_экос = β × Qср × (1 + α × ln(1/P)),
      где β зависит от свойств водосбора (0.1–0.5)

    Parameters:
        mean_annual_flow: среднегодовой расход Qср (м³/с)
        method: метод расчёта ("tenpct", "7q10", "tessmann")

    Returns:
        Словарь с экосистемным расходом, методом и статусом соответствия
    """
    if mean_annual_flow <= 0:
        raise ValueError("Среднегодовой расход должен быть положительным")

    method_name = method.lower()

    if method_name == "tenpct":
        q_ecos = 0.1 * mean_annual_flow

    elif method_name == "tessmann":
        beta = 0.2
        alpha = 0.5
        P = 0.9
        q_ecos = beta * mean_annual_flow * (1 + alpha * np.log(1.0 / P))

    elif method_name == "7q10":
        q_ecos = 0.4 * mean_annual_flow
        return {
            "Q_ecosystem": round(q_ecos, 2),
            "method_used": "7Q10 (приблизительный)",
            "note": "Для точного расчёта 7Q10 используйте функцию q7_10() с суточным рядом расходов.",
            "compliance_status": "Требуется уточнение",
            "normative": "СП 32.13330.2018, раздел 8"
        }

    else:
        raise ValueError(f"Неизвестный метод: '{method}'. Допустимые: 'tenpct', '7q10', 'tessmann'")

    if q_ecos < 0.1 * mean_annual_flow:
        compliance = "Ниже норматива (10% от Qср)"
    elif q_ecos <= 0.3 * mean_annual_flow:
        compliance = "Соответствует нормативу"
    else:
        compliance = "Выше норматива"

    return {
        "Q_ecosystem": round(q_ecos, 2),
        "method_used": method_name,
        "mean_annual_flow": mean_annual_flow,
        "compliance_status": compliance,
        "normative": "СП 32.13330.2018, раздел 8"
    }


def q7_10(
    daily_series: pd.Series,
    years: Optional[pd.Series] = None
) -> Dict:
    """
    7-day 10-year minimum flow (7Q10) — стандартный показатель экосистемного минимума.

    Алгоритм (СП 32.13330.2018, прил. Г):
    1. Для каждого года находится минимальный 7-суточный средний расход.
    2. К полученному ряду годовых минимумов строится кривая обеспечённости.
    3. Извлекается значение при P = 90% (период возврата 10 лет).

    Parameters:
        daily_series: суточные расходы (м³/с)
        years: необязательный ряд годов

    Returns:
        Словарь с Q7_10, рядом годовых минимумов и статистикой
    """
    series = daily_series.dropna()

    if len(series) == 0:
        raise ValueError("Пустой ряд суточных расходов")

    if years is None:
        if hasattr(series.index, 'year'):
            years = pd.Series(series.index.year, index=series.index)
        elif 'year' in series.index.name if hasattr(series.index, 'name') else False:
            years = series.index
        else:
            raise ValueError("Не удалось определить годы. Укажите параметр years.")

    df = pd.DataFrame({'year': years.values, 'value': series.values})
    df = df.dropna(subset=['value'])

    annual_minima = {}
    for year in df['year'].unique():
        year_vals = df[df['year'] == year]['value'].values
        if len(year_vals) >= 7:
            min_avg = _sliding_window_min_mean(year_vals, 7)
            if min_avg is not None:
                annual_minima[year] = min_avg

    min_series = pd.Series(annual_minima, dtype=float)

    if len(min_series) < 3:
        raise ValueError(
            f"Недостаточно данных для расчёта 7Q10 ({len(min_series)} годов < 3). "
            "Требуется минимум 3 года с полными суточными данными."
        )

    stats = compute_min_runoff_stats(min_series, period_days=7)
    mean_val = stats["mean"]
    Cv = stats["Cv"]
    Cs_over_Cv = stats.get("Cs/Cv", 2.0)

    km_curve = kritsky_menkel_quantiles(
        mean=mean_val,
        Cv=Cv,
        Cs_over_Cv=Cs_over_Cv,
        P_list=[90]
    )

    q7_10_val = float(km_curve.iloc[0]["Q_p"])

    return {
        "Q7_10_value": round(q7_10_val, 2),
        "annual_minima": min_series.round(2),
        "stats": stats,
        "method": "7Q10",
        "normative": "СП 32.13330.2018, прил. Г"
    }


def q7_30(
    daily_series: pd.Series,
    years: Optional[pd.Series] = None
) -> Dict:
    """
    30-day minimum flow — показатель минимального стока для целей водоснабжения.

    Аналогично q7_10, но с 30-суточным окном. Применяется в российской практике
    для расчёта гарантированного стока при проектировании водозаборов
    (СП 32.13330.2018, раздел 8).

    Parameters:
        daily_series: суточные расходы (м³/с)
        years: необязательный ряд годов

    Returns:
        Словарь с Q30_min, рядом годовых минимумов и статистикой
    """
    series = daily_series.dropna()

    if len(series) == 0:
        raise ValueError("Пустой ряд суточных расходов")

    if years is None:
        if hasattr(series.index, 'year'):
            years = pd.Series(series.index.year, index=series.index)
        else:
            raise ValueError("Не удалось определить годы. Укажите параметр years.")

    df = pd.DataFrame({'year': years.values, 'value': series.values})
    df = df.dropna(subset=['value'])

    annual_minima = {}
    for year in df['year'].unique():
        year_vals = df[df['year'] == year]['value'].values
        if len(year_vals) >= 30:
            min_avg = _sliding_window_min_mean(year_vals, 30)
            if min_avg is not None:
                annual_minima[year] = min_avg

    min_series = pd.Series(annual_minima, dtype=float)

    if len(min_series) < 3:
        raise ValueError(
            f"Недостаточно данных для расчёта 30-суточного минимума ({len(min_series)} годов < 3)."
        )

    stats = compute_min_runoff_stats(min_series, period_days=30)
    mean_val = stats["mean"]
    Cv = stats["Cv"]
    Cs_over_Cv = stats.get("Cs/Cv", 2.0)

    km_curve = kritsky_menkel_quantiles(
        mean=mean_val,
        Cv=Cv,
        Cs_over_Cv=Cs_over_Cv,
        P_list=[90, 95, 99]
    )

    q30_values = {}
    for _, row in km_curve.iterrows():
        q30_values[int(row["P_%"])] = round(float(row["Q_p"]), 2)

    return {
        "Q30_values": q30_values,
        "Q30_90": q30_values.get(90, None),
        "annual_minima": min_series.round(2),
        "stats": stats,
        "method": "30-day minimum",
        "normative": "СП 32.13330.2018, раздел 8"
    }


def compare_minimum_methods(
    daily_series: pd.Series,
    mean_annual_flow: float
) -> pd.DataFrame:
    """
    Сравнение различных методов определения минимального стока.

    Включает:
    - 7-суточный минимум (P=90%, 95%, 99%)
    - 10-суточный минимум (P=90%, 95%, 99%)
    - 30-суточный минимум (P=90%, 95%, 99%)
    - Экосистемный (10% от Qср)
    - 7Q10

    Parameters:
        daily_series: суточные расходы (м³/с)
        mean_annual_flow: среднегодовой расход (м³/с)

    Returns:
        DataFrame с результатами сравнения
    """
    results = []

    ecos = ecosystem_minimum(mean_annual_flow, method="tenpct")
    results.append({
        "Метод": "Экосистемный (10% от Qср)",
        "P_%,": "—",
        "Q (м³/с)": ecos["Q_ecosystem"],
        "Статус соответствия": ecos["compliance_status"]
    })

    try:
        q7_result = q7_10(daily_series)
        q7_stats = q7_result["stats"]

        for P in [90, 95, 99]:
            km = kritsky_menkel_quantiles(
                q7_stats["mean"], q7_stats["Cv"],
                q7_stats.get("Cs/Cv", 2.0), [P]
            )
            q_val = float(km.iloc[0]["Q_p"])
            status = "Ниже экосистемного" if q_val < ecos["Q_ecosystem"] else "Выше экосистемного"
            results.append({
                "Метод": "7-суточный минимум",
                "P_%": P,
                "Q (м³/с)": round(q_val, 2),
                "Статус соответствия": status
            })
    except (ValueError, KeyError):
        results.append({
            "Метод": "7-суточный минимум",
            "P_%": "—",
            "Q (м³/с)": None,
            "Статус соответствия": "Недостаточно данных"
        })

    try:
        df = pd.DataFrame({'value': daily_series.values})
        if hasattr(daily_series.index, 'year'):
            df['year'] = daily_series.index.year
            year_col = 'year'
        else:
            df['year'] = range(len(df))
            year_col = 'year'

        min10 = extract_min_annual(df, year_col=year_col, value_col='value', period_days=10)
        if len(min10) >= 3:
            stats10 = compute_min_runoff_stats(min10, period_days=10)
            for P in [90, 95, 99]:
                km = kritsky_menkel_quantiles(
                    stats10["mean"], stats10["Cv"],
                    stats10.get("Cs/Cv", 2.0), [P]
                )
                q_val = float(km.iloc[0]["Q_p"])
                status = "Ниже экосистемного" if q_val < ecos["Q_ecosystem"] else "Выше экосистемного"
                results.append({
                    "Метод": "10-суточный минимум",
                    "P_%": P,
                    "Q (м³/с)": round(q_val, 2),
                    "Статус соответствия": status
                })
        else:
            raise ValueError("Недостаточно данных")
    except (ValueError, KeyError):
        for P in [90, 95, 99]:
            results.append({
                "Метод": "10-суточный минимум",
                "P_%": P,
                "Q (м³/с)": None,
                "Статус соответствия": "Недостаточно данных"
            })

    try:
        q30_result = q7_30(daily_series)
        q30_stats = q30_result["stats"]
        for P in [90, 95, 99]:
            km = kritsky_menkel_quantiles(
                q30_stats["mean"], q30_stats["Cv"],
                q30_stats.get("Cs/Cv", 2.0), [P]
            )
            q_val = float(km.iloc[0]["Q_p"])
            status = "Ниже экосистемного" if q_val < ecos["Q_ecosystem"] else "Выше экосистемного"
            results.append({
                "Метод": "30-суточный минимум",
                "P_%": P,
                "Q (м³/с)": round(q_val, 2),
                "Статус соответствия": status
            })
    except (ValueError, KeyError):
        for P in [90, 95, 99]:
            results.append({
                "Метод": "30-суточный минимум",
                "P_%": P,
                "Q (м³/с)": None,
                "Статус соответствия": "Недостаточно данных"
            })

    try:
        q710 = q7_10(daily_series)
        results.append({
            "Метод": "7Q10",
            "P_%": 90,
            "Q (м³/с)": q710["Q7_10_value"],
            "Статус соответствия": (
                "Ниже экосистемного"
                if q710["Q7_10_value"] < ecos["Q_ecosystem"]
                else "Выше экосистемного"
            )
        })
    except (ValueError, KeyError):
        results.append({
            "Метод": "7Q10",
            "P_%": 90,
            "Q (м³/с)": None,
            "Статус соответствия": "Недостаточно данных"
        })

    return pd.DataFrame(results)
