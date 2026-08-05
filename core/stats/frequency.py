"""
core/stats/frequency.py
Расчёт кривых обеспеченности:
- Пирсона III типа (точная функция распределения scipy)
- Крицкого-Менкеля (трёхпараметрическое гамма-распределение)
- Нормальное распределение
- Эмпирическая кривая
"""

import math
import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, Optional, Literal


CurveType = Literal[
    "pearson3",
    "kritsky_menkel",
    "normal",
    "empirical",
    "piecewise",
    "none"
]


def fit_pearson3(data: np.ndarray) -> Dict:
    from core.stats.parameters import calculate_statistical_parameters
    result = calculate_statistical_parameters(data)
    return {
        'mean': result['mean'],
        'std': result['std'],
        'cv': result['cv'],
        'skew': result['cs'],
        'n': result['n'],
        'r1': result['r1']
    }


def empirical_plotting_positions(data: np.ndarray) -> tuple:
    """
    Эмпирические точки кривой обеспеченности (формула Каннана).

    Ряд сортируется по убыванию (m=1 — максимальный член),
    обеспеченность каждого члена: P_m = (m - 0.3)/(n + 0.4) [0..1].

    Returns:
        (q_desc, p_exceed): отсортированный по убыванию ряд и его
        эмпирические обеспеченности (вероятности превышения).
    """
    data = np.asarray(data, dtype=float)
    q_desc = np.sort(data)[::-1]
    n = len(q_desc)
    p_exceed = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
    return q_desc, p_exceed


def pearson3_ppf(probabilities: np.ndarray, mean: float, cv: float, cs: float) -> np.ndarray:
    """
    Квантили распределения Пирсона III типа.

    X_p = X̄ + σ · z_p,  σ = X̄ · Cv

    где z_p — квантиль стандартизированного распределения Пирсона III
    (с нулевым средним, единичным СКО и заданной асимметрией Cs).
    Используется точная функция распределения scipy (в отличие от
    приближения Корниша-Фишера, которое не работает при больших Cs).

    Отрицательные квантили (нижний хвост при Cs < 0 и больших P)
    обрезаются до нуля, как это делает эталонная программа.
    """
    probabilities = np.asarray(probabilities, dtype=float)
    cv = max(abs(cv), 0.001)
    cs = float(cs)

    quantiles = stats.pearson3.ppf(
        1 - probabilities, skew=cs, loc=mean, scale=mean * cv
    )

    return np.maximum(quantiles, 0.0)


def kritsky_menkel_ppf(probabilities: np.ndarray, mean: float, cv: float, cs: float) -> np.ndarray:
    """
    Квантили распределения Крицкого-Менкеля.

    Основной метод — трёхпараметрическое гамма-распределение:
       α = 4/Cs²,  β = X̄·Cv·Cs/2,  A₀ = X̄·(1 - 2Cv/Cs)
       X_p = A₀ + Gamma(α, β)

    Совпадает с эталонной программой HydroStatCalc (таблицы KritkMenc.bin)
    в пределах погрешности таблиц. Отрицательные квантили обрезаются до нуля.
    """
    probabilities = np.asarray(probabilities, dtype=float)
    cv = max(abs(cv), 0.001)
    cs = float(cs)
    if abs(cs) < 0.001:
        cs = 0.001

    # --- Трёхпараметрическое гамма-распределение ---
    alpha = 4.0 / (cs ** 2)                          # параметр формы
    beta = mean * cv * abs(cs) / 2.0                  # параметр масштаба
    A0 = mean * (1.0 - 2.0 * cv / cs)               # начальная точка (сдвиг)

    try:
        quantiles = A0 + stats.gamma.ppf(1 - probabilities, a=alpha, scale=beta)
    except (ValueError, TypeError, RuntimeError):
        # Fallback на формулу Корниша-Фишера
        quantiles = pearson3_ppf(probabilities, mean, cv, cs)

    return np.maximum(quantiles, 0.0)


def fit_theoretical_distributions(Q: np.ndarray, p_prob: np.ndarray) -> dict:
    """
    Подгоняет несколько теоретических распределений к данным.

    Parameters:
        Q: массив расходов
        p_prob: массив вероятностей (0–1) для квантилей

    Returns:
        dict: {название: массив_квантилей или None}
    """
    probabilities = np.asarray(p_prob, dtype=float)

    # Pearson III (скью-нормальное)
    try:
        params = stats.pearson3.fit(Q)
        p3 = stats.pearson3.ppf(1 - probabilities, *params)
    except (ValueError, TypeError):
        p3 = None

    # Gamma
    try:
        params = stats.gamma.fit(Q, floc=0)
        g = stats.gamma.ppf(1 - probabilities, *params)
    except (ValueError, TypeError):
        g = None

    # Lognormal
    try:
        params = stats.lognorm.fit(Q, floc=0)
        ln = stats.lognorm.ppf(1 - probabilities, *params)
    except (ValueError, TypeError):
        ln = None

    # Normal
    try:
        params = stats.norm.fit(Q)
        n = stats.norm.ppf(1 - probabilities, *params)
    except (ValueError, TypeError):
        n = None

    return {
        "pearson3": p3,
        "gamma": g,
        "lognormal": ln,
        "normal": n
    }


def calculate_frequency_curve(
    data: np.ndarray,
    probabilities: Optional[np.ndarray] = None,
    curve_type: CurveType = "pearson3",
    use_corrected: bool = True
) -> pd.DataFrame:
    """
    Построение кривой обеспеченности разных типов.
    """
    if probabilities is None:
        probabilities = np.array([0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 0.99])

    from core.stats.parameters import calculate_statistical_parameters
    params = calculate_statistical_parameters(data)

    mean = params['mean']
    cv = params['corrected_cv'] if use_corrected else params['cv']
    cs = params['corrected_cs'] if use_corrected else params['cs']

    if curve_type == "normal":
        std = params['std']
        quantiles = stats.norm.ppf(1 - probabilities, loc=mean, scale=std)

    elif curve_type == "pearson3":
        # Распределение Пирсона III типа — формула Корниша-Фишера
        quantiles = pearson3_ppf(probabilities, mean, cv, cs)

    elif curve_type == "kritsky_menkel":
        # Распределение Крицкого-Менкеля — табличный метод / трёхпараметрическое гамма
        quantiles = kritsky_menkel_ppf(probabilities, mean, cv, cs)

    elif curve_type == "empirical":
        # Ряд сортируется по убыванию: m=1 — максимальный член ряда,
        # эмпирическая обеспеченность P_m = (m - 0.3)/(n + 0.4).
        q_desc = np.sort(data)[::-1]
        n = len(q_desc)
        emp_probs = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
        quantiles = np.interp(probabilities, emp_probs, q_desc,
                              left=q_desc[0], right=q_desc[-1])

    elif curve_type == "piecewise":
        # Интерполяция ломаной линией (ГГИ):
        # Точки эмпирической кривой последовательно соединяются отрезками
        # прямых. Расчётные квантили — по координатам этих отрезков.
        q_desc = np.sort(data)[::-1]
        n = len(q_desc)
        emp_probs = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
        # Линейная интерполяция между эмпирическими точками
        quantiles = np.interp(probabilities, emp_probs, q_desc,
                              left=q_desc[0], right=q_desc[-1])

    elif curve_type == "none":
        quantiles = np.full_like(probabilities, np.nan)
    else:
        std = params['std']
        quantiles = stats.norm.ppf(1 - probabilities, loc=mean, scale=std)

    return pd.DataFrame({
        'P_%': np.round(probabilities * 100, 2),
        'Q': np.round(quantiles, 2)
    })


# ============================================================
# ПОДБОР Cs/Cv АВТОМАТОМ (ГГИ: «Подбор Cs/Cv»)
# ============================================================
#
# МинимизацияΣ(Yэмп.i - Yтеор.i)² по Cs/Cv
# с точностью до 0.05 (как в оригинальной программе ГГИ)
#
# Диапазон P: «весь» или «указанный» (P% > и P% <)


def auto_select_cs_cv(
    data: np.ndarray,
    curve_type: str = 'pearson3',
    p_range: Optional[tuple] = None,
    precision: float = 0.05,
    cs_cv_min: float = -2.0,
    cs_cv_max: float = 6.0,
) -> Dict:
    """
    Автоматический подбор отношения Cs/Cv для кривой обеспеченности.

    Алгоритм (ГГИ):
    1. Вычислить эмпирические обеспеченности по формуле Крицкого-Менкеля
       P = (m - 0.3) / (n + 0.4)
    2. Перебрать Cs/Cv от cs_cv_min до cs_cv_max с шагом precision
    3. Для каждого Cs/Cv: построить теоретическую кривую (Пирсон III или К-М)
    4. ВычислитьΣ(Yэмп - Yтеор)² по точкам в заданном диапазоне P
    5. Выбрать Cs/Cv с минимальной суммой

    Аргументы:
        data — исходные данные
        curve_type — 'pearson3' или 'kritsky_menkel'
        p_range — (P_min, P_max) в долях (0-1), None = весь диапазон
        precision — шаг перебора Cs/Cv (default 0.05)
        cs_cv_min — нижняя граница Cs/Cv
        cs_cv_max — верхняя граница Cs/Cv

    Возвращает dict:
        cs_cv_optimal — оптимальное Cs/Cv
        ss_min — минимальная сумма квадратов
        all_results — список {cs_cv, ss} для всех перебранных значений
        quantiles — теоретические квантили при оптимальном Cs/Cv
        empirical — эмпирические точки
        cv — Cv исходных данных
    """
    data = np.asarray(data, dtype=float)
    data = data[~np.isnan(data)]
    n = len(data)

    if n < 5:
        return {
            'cs_cv_optimal': None,
            'ss_min': float('inf'),
            'message': f'Недостаточно данных (n={n} < 5)',
        }

    # Базовые параметры
    mean_val = np.mean(data)
    cv = np.std(data, ddof=1) / mean_val if mean_val > 0 else 0

    # Эмпирические обеспеченности (формула Крицкого-Менкеля)
    sorted_data = np.sort(data)[::-1]  # по убыванию
    emp_probs = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
    emp_quantiles = sorted_data

    # Стандартные обеспеченностии
    std_probs = np.array([0.001, 0.01, 0.05, 0.1, 0.2, 0.3, 0.5,
                          0.7, 0.8, 0.9, 0.95, 0.97, 0.99, 0.999])
    std_probs_pct = std_probs * 100

    # Фильтрация по диапазону P
    if p_range is not None:
        p_min, p_max = p_range
        mask = (emp_probs >= p_min) & (emp_probs <= p_max)
        eval_probs = emp_probs[mask]
        eval_emp = emp_quantiles[mask]
    else:
        eval_probs = emp_probs
        eval_emp = emp_quantiles

    if len(eval_probs) < 3:
        return {
            'cs_cv_optimal': None,
            'ss_min': float('inf'),
            'message': 'Недостаточно точек в заданном диапазоне P',
        }

    # Перебор Cs/Cv
    cs_cv_values = np.arange(cs_cv_min, cs_cv_max + precision, precision)
    results = []

    best_cs_cv = None
    best_ss = float('inf')

    for cs_cv in cs_cv_values:
        cs = cs_cv * cv  # Cs = (Cs/Cv) × Cv

        if abs(cs) < 1e-6:
            # Cs ≈ 0: нормальное распределение
            theo = stats.norm.ppf(1 - eval_probs, loc=mean_val,
                                  scale=cv * mean_val)
        elif curve_type == 'pearson3':
            try:
                theo = pearson3_ppf(eval_probs, mean_val, cv, cs)
            except Exception:
                continue
        else:  # kritsky_menkel
            try:
                theo = kritsky_menkel_ppf(eval_probs, mean_val, cv, cs)
            except Exception:
                continue

        # Σ(Yэмп - Yтеор)²
        ss = np.sum((eval_emp - theo) ** 2)
        results.append({'cs_cv': round(cs_cv, 3), 'ss': round(ss, 4)})

        if ss < best_ss:
            best_ss = ss
            best_cs_cv = cs_cv

    if best_cs_cv is None:
        return {
            'cs_cv_optimal': None,
            'ss_min': float('inf'),
            'message': 'Не удалось подобрать Cs/Cv',
        }

    # Построение теоретической кривой при оптимальном Cs/Cv
    cs_opt = best_cs_cv * cv
    if abs(cs_opt) < 1e-6:
        theo_opt = stats.norm.ppf(1 - std_probs, loc=mean_val,
                                  scale=cv * mean_val)
    elif curve_type == 'pearson3':
        theo_opt = pearson3_ppf(std_probs, mean_val, cv, cs_opt)
    else:
        theo_opt = kritsky_menkel_ppf(std_probs, mean_val, cv, cs_opt)

    # Эмпирические точки на стандартных обеспеченностях
    emp_on_std = np.interp(std_probs, emp_probs, sorted_data,
                           left=sorted_data[0], right=sorted_data[-1])

    return {
        'cs_cv_optimal': round(best_cs_cv, 2),
        'cs_optimal': round(cs_opt, 4),
        'ss_min': round(best_ss, 4),
        'cv': round(cv, 4),
        'mean': round(mean_val, 4),
        'all_results': results,
        'quantiles': pd.DataFrame({
            'P_%': np.round(std_probs * 100, 2),
            'Q_theory': np.round(theo_opt, 2),
            'Q_empirical': np.round(emp_on_std, 2),
        }),
        'empirical': pd.DataFrame({
            'P_%': np.round(emp_probs * 100, 2),
            'Q': np.round(sorted_data, 2),
        }),
    }


# ============================================================
# ИСТОРИЧЕСКИЕ ЭКСТРЕМУМЫ (ГГИ: «Выдающиеся значения»)
# ============================================================
#
# Данные об исторических максимумах/минимумах:
# - Год, значение, период непревышения T
# - Обеспеченность: P = 1 / (T + 0.5)
#
# Учёт в расчёте параметров:
# - Поправка к среднему: ΔQ = (Q_hist - Q̄) / (N + 1)
# - Поправка к Cv: учитывает更多信息 о хвосте распределения


class HistoricalExtreme:
    """Исторический экстремум (год, значение, период)."""

    def __init__(self, year: int, value: float, period: int):
        self.year = year
        self.value = value
        self.period = period
        self.exceedance_prob = 1.0 / (period + 0.5)

    def __repr__(self):
        return (f"HistoricalExtreme(year={self.year}, value={self.value}, "
                f"T={self.period}, P={self.exceedance_prob:.6f})")


def compute_params_with_extremes(
    data: np.ndarray,
    extremes: list,
    is_max: bool = True,
) -> Dict:
    """
    Расчёт параметров распределения с учётом исторических экстремумов.

    Метод (ГГИ):
    1. Для каждого экстремума вычислить обеспеченность P = 1/(T+0.5)
    2. Добавить экстремум к наблюдаемому ряду с весом 1/(N+1)
    3. Пересчитать среднее и Cv с учётом экстремумов

    Аргументы:
        data — наблюдаемые значения
        extremes — список HistoricalExtreme
        is_max — True для максимумов, False для минимумов

    Возвращает dict:
        mean_raw, cv_raw — исходные параметры
        mean_corrected, cv_corrected — скорректированные
        corrections — поправки
        extremes_with_probs — экстремумы с обеспеченностями
    """
    data = np.asarray(data, dtype=float)
    data = data[~np.isnan(data)]
    n = len(data)

    if n < 3:
        return {
            'mean_raw': np.mean(data) if n > 0 else 0,
            'cv_raw': 0,
            'mean_corrected': np.mean(data) if n > 0 else 0,
            'cv_corrected': 0,
            'corrections': {'delta_mean': 0, 'delta_cv': 0},
            'extremes_with_probs': [],
        }

    mean_raw = np.mean(data)
    std_raw = np.std(data, ddof=1)
    cv_raw = std_raw / mean_raw if mean_raw > 0 else 0

    if not extremes:
        return {
            'mean_raw': round(mean_raw, 4),
            'cv_raw': round(cv_raw, 4),
            'mean_corrected': round(mean_raw, 4),
            'cv_corrected': round(cv_raw, 4),
            'corrections': {'delta_mean': 0, 'delta_cv': 0},
            'extremes_with_probs': [],
        }

    # Вычисляем обеспеченности экстремумов
    extremes_info = []
    for ext in extremes:
        prob = ext.exceedance_prob
        extremes_info.append({
            'year': ext.year,
            'value': ext.value,
            'period': ext.period,
            'exceedance_prob': round(prob, 6),
            'exceedance_pct': round(prob * 100, 4),
        })

    # Поправка к среднему:
    # Если экстремум за пределами периода наблюдений:
    # ΔQ = (Q_hist - Q̄) / (N + 1)
    N = n
    delta_mean = 0
    for ext in extremes:
        if ext.value > mean_raw and is_max:
            delta_mean += (ext.value - mean_raw) / (N + 1)
        elif ext.value < mean_raw and not is_max:
            delta_mean += (mean_raw - ext.value) / (N + 1)

    mean_corrected = mean_raw + delta_mean

    # Поправка к Cv:
    # Учитывает дисперсию экстремумов
    delta_cv = 0
    for ext in extremes:
        weight = 1.0 / (N + 1)
        contrib = weight * ((ext.value - mean_corrected) / mean_corrected) ** 2
        delta_cv += contrib

    cv_corrected = np.sqrt(cv_raw ** 2 + delta_cv) if cv_raw > 0 else np.sqrt(delta_cv)

    return {
        'mean_raw': round(mean_raw, 4),
        'cv_raw': round(cv_raw, 4),
        'mean_corrected': round(mean_corrected, 4),
        'cv_corrected': round(cv_corrected, 4),
        'corrections': {
            'delta_mean': round(delta_mean, 4),
            'delta_cv': round(cv_corrected - cv_raw, 4),
        },
        'extremes_with_probs': extremes_info,
    }