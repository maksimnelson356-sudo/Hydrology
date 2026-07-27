"""
core/stats/composite_curves.py
Составные кривые обеспеченности

Реализация методики СП 33-101-2003 п. 4.4:
- Статистическое определение границы неоднородности (Пettitt)
- Тест Штрихова (Манн-Уитни) для проверки различий двух половин
- Пересчёт Cv и Cs для каждой части ряда
- Построение составной кривой

Основные функции:
- find_change_point — поиск точки изменения (Пettitt)
- test_homogeneity_two_parts — тест Штрихова (U-критерий Манна-Уитни)
- split_series_by_year — разделение ряда по году
- compute_composite_curve — расчёт составной кривой
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from scipy import stats


def find_change_point(
    values: np.ndarray,
    years: Optional[np.ndarray] = None
) -> Dict:
    """
    Поиск точки изменения ряда тестом Пettitt.

    Пettitt test — непараметрический тест для определения
    момента изменения среднего уровня ряда.

    Parameters:
        values: массив значений
        years: массив лет (если None — используются индексы)

    Returns:
        Dict: change_year, change_index, p_value, max_U, significant
    """
    n = len(values)
    if n < 10:
        return {'change_year': None, 'change_index': None,
                'p_value': 1.0, 'max_U': 0, 'significant': False}

    U_t = []
    for t in range(1, n):
        left = values[:t]
        right = values[t:]
        u = sum(np.sign(x - y) for x in right for y in left)
        U_t.append(abs(u))

    max_U = max(U_t)
    change_idx = U_t.index(max_U)

    p_value = 2 * np.exp(-6 * max_U**2 / (n**3 + n**2))
    p_value = min(p_value, 1.0)

    if years is not None and change_idx < len(years):
        change_year = int(years[change_idx])
    else:
        change_year = None

    return {
        'change_year': change_year,
        'change_index': change_idx,
        'p_value': round(p_value, 6),
        'max_U': max_U,
        'significant': p_value < 0.05
    }


def test_homogeneity_two_parts(
    part1: np.ndarray,
    part2: np.ndarray,
    alpha: float = 0.05
) -> Dict:
    """
    Тест Штрихова (Манн-Уитни) для двух частей ряда.

    Нулевая гипотеза: части принадлежат одному распределению.
    Если p > alpha → различий нет → ряд однороден.

    Также проводятся:
    - t-тест Стьюдента (средние)
    - F-тест Фишера (дисперсии)
    - KS-тест Колмогорова-Смирнова

    Parameters:
        part1: первая часть ряда
        part2: вторая часть ряда
        alpha: уровень значимости

    Returns:
        Dict: u_stat, u_p, t_stat, t_p, f_stat, f_p, ks_stat, ks_p, is_homogeneous
    """
    u_stat, u_p = stats.mannwhitneyu(part1, part2, alternative='two-sided')
    t_stat, t_p = stats.ttest_ind(part1, part2)
    ks_stat, ks_p = stats.ks_2samp(part1, part2)

    var1 = np.var(part1, ddof=1)
    var2 = np.var(part2, ddof=1)
    f_stat = var1 / var2 if var2 > 0 else 1.0
    f_p = 1 - stats.f.cdf(f_stat, len(part1)-1, len(part2)-1)

    is_homogeneous = (u_p > alpha) and (t_p > alpha) and (ks_p > alpha)

    return {
        'u_stat': round(float(u_stat), 4),
        'u_p': round(float(u_p), 6),
        't_stat': round(float(t_stat), 4),
        't_p': round(float(t_p), 6),
        'f_stat': round(float(f_stat), 4),
        'f_p': round(float(f_p), 6),
        'ks_stat': round(float(ks_stat), 4),
        'ks_p': round(float(ks_p), 6),
        'is_homogeneous': is_homogeneous,
        'alpha': alpha
    }


def split_series_by_year(
    values: np.ndarray,
    years: np.ndarray,
    break_year: int
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Разделение ряда на две части по году разрыва.

    Returns:
        (values1, years1, values2, years2)
    """
    mask1 = years < break_year
    mask2 = years >= break_year
    return values[mask1], years[mask1], values[mask2], years[mask2]


def compute_part_stats(
    data: np.ndarray,
    use_normative_Cs: bool = True
) -> Dict:
    """
    Расчёт Cv и Cs для части ряда.
    """
    n = len(data)
    if n < 3:
        return {'mean': 0, 'std': 0, 'cv': 0, 'cs': 0, 'n': n}

    mean = float(np.mean(data))
    std = float(np.std(data, ddof=1))
    cv = std / mean if mean != 0 else 0.0
    cs = float(pd.Series(data).skew())

    if use_normative_Cs:
        cs = 2.0 * cv

    return {
        'mean': round(mean, 4),
        'std': round(std, 4),
        'cv': round(cv, 4),
        'cs': round(cs, 4),
        'n': n
    }


def compute_composite_curve(
    values: np.ndarray,
    years: np.ndarray,
    break_year: int,
    P_values: Optional[List[float]] = None,
    use_normative_Cs: bool = True
) -> Dict:
    """
    Полный расчёт составной кривой обеспеченности.

    Алгоритм (СП 33-101-2003 п. 4.4):
    1. Разделить ряд по году разрыва
    2. Проверить однородность тестом Штрихова
    3. Рассчитать Cv и Cs для каждой части
    4. Построить кривую для каждой части
    5. Определить пересечение кривых (точка переключения)
    6. Составная кривая: до точки переключения — первая часть, после — вторая

    Parameters:
        values: массив расходов
        years: массив лет
        break_year: год разрыва
        P_values: обеспеченности (в долях)
        use_normative_Cs: нормативное Cs = 2×Cv

    Returns:
        Dict: curve_df, part1_stats, part2_stats, homogeneity_test, change_point
    """
    if P_values is None:
        P_values = [0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5,
                    0.7, 0.8, 0.9, 0.95, 0.98, 0.99, 0.995, 0.999]

    v1, y1, v2, y2 = split_series_by_year(values, years, break_year)

    stats1 = compute_part_stats(v1, use_normative_Cs)
    stats2 = compute_part_stats(v2, use_normative_Cs)

    homo = test_homogeneity_two_parts(v1, v2) if len(v1) >= 5 and len(v2) >= 5 else {'is_homogeneous': True}

    change_point = find_change_point(values, years)

    from core.stats.frequency import pearson3_ppf
    P_arr = np.array(P_values)
    Q1 = pearson3_ppf(P_arr, stats1['mean'], stats1['cv'], stats1['cs'])
    Q2 = pearson3_ppf(P_arr, stats2['mean'], stats2['cv'], stats2['cs'])

    n1, n2 = len(v1), len(v2)
    n_total = n1 + n2
    Q_composite = (Q1 * n1 + Q2 * n2) / n_total if n_total > 0 else np.minimum(Q1, Q2)

    curve_df = pd.DataFrame({
        'P_%': np.round(P_arr * 100, 3),
        'Q_часть1': np.round(Q1, 2),
        'Q_часть2': np.round(Q2, 2),
        'Q_составная': np.round(Q_composite, 2)
    })

    return {
        'curve_df': curve_df,
        'part1_stats': stats1,
        'part2_stats': stats2,
        'homogeneity_test': homo,
        'change_point': change_point,
        'break_year': break_year,
        'n_part1': len(v1),
        'n_part2': len(v2)
    }
