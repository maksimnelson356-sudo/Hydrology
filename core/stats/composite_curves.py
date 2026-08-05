"""
core/stats/composite_curves.py
Составные кривые обеспеченности

Реализация методики А.В. Рождественского (ГГИ, СПб):
- Разделение ряда на генетически однородные категории (до 6)
- Индивидуальные кривые для каждой категории (Пирсон III / К-М)
- Составная кривая: осреднение вероятностей P(Q) по категориям

Алгоритм (СП 33-101-2003 п. 5.12, Рекомендации ГГИ [6]):
  P_сост(Q) = Σ ni × Pi(Q) / N

где:
  Pi(Q) — обеспеченность значения Q в i-й категории
  ni — число лет в i-й категории
  N = Σ ni — общее число лет

Ключевое отличие от взвешенного среднего Q:
  Рождественский осредняет ВЕРОЯТНОСТИ, а не квантили.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from scipy import stats

from core.stats.frequency import pearson3_ppf, kritsky_menkel_ppf


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def compute_category_stats(data: np.ndarray) -> Dict:
    """Расчёт параметров для одной категории."""
    data = np.asarray(data, dtype=float)
    data = data[~np.isnan(data)]
    n = len(data)

    if n < 3:
        return {'mean': 0, 'std': 0, 'cv': 0, 'cs': 0, 'n': n, 'valid': False}

    mean = float(np.mean(data))
    std = float(np.std(data, ddof=1))
    cv = std / mean if mean != 0 else 0
    cs = float(stats.skew(data, bias=False))

    return {
        'mean': round(mean, 4),
        'std': round(std, 4),
        'cv': round(cv, 4),
        'cs': round(cs, 4),
        'n': n,
        'valid': True,
    }


def _interpolate_probability(
    Q_target: float,
    Q_values: np.ndarray,
    P_values: np.ndarray,
) -> float:
    """
    Интерполяция обеспеченности P для заданного Q
    по табличным значениям (Q, P).
    """
    if Q_target <= Q_values[0]:
        return P_values[0]
    if Q_target >= Q_values[-1]:
        return P_values[-1]

    for i in range(len(Q_values) - 1):
        if Q_values[i] <= Q_target <= Q_values[i + 1]:
            frac = (Q_target - Q_values[i]) / (Q_values[i + 1] - Q_values[i])
            return P_values[i] + frac * (P_values[i + 1] - P_values[i])

    return P_values[-1]


# ============================================================
# МЕТОДИКА РОЖДЕСТВЕНСКОГО
# ============================================================

def compute_composite_curve_rodzhestvensky(
    categories: List[Dict],
    Q_grid: Optional[np.ndarray] = None,
    curve_type: str = 'pearson3',
    P_range: Optional[tuple] = None,
) -> Dict:
    """
    Построение составной кривой по методике Рождественского.

    Каждая категория = dict с ключами:
        'data': np.array — значения ряда для этой категории
        'name': str — название категории (опционально)

    Алгоритм:
    1. Для каждой категории строим индивидуальную кривую Pi(Q)
    2. Для каждого Q на сетке вычисляем:
       P_сост(Q) = Σ ni × Pi(Q) / N
    3. Результат — кривая P_сост(Q)

    Аргументы:
        categories — список dict с данными категорий
        Q_grid — сетка значений Q для расчёта (если None — автовыбор)
        curve_type — 'pearson3' или 'kritsky_menkel'
        P_range — (P_min, P_max) для фильтрации (опционально)

    Возвращает dict:
        curve_df — DataFrame с P_% и Q_составная
        category_curves — список кривых по категориям
        category_stats — параметры каждой категории
        total_years — общее число лет
    """
    if not categories or len(categories) < 2:
        return {'error': 'Нужно минимум 2 категории'}

    # Собираем статистику по каждой категории
    cat_stats = []
    cat_data = []
    for cat in categories:
        data = np.asarray(cat.get('data', []), dtype=float)
        data = data[~np.isnan(data)]
        stat = compute_category_stats(data)
        stat['name'] = cat.get('name', f'Категория {len(cat_stats)+1}')
        cat_stats.append(stat)
        cat_data.append(data)

    N = sum(s['n'] for s in cat_stats)
    if N < 5:
        return {'error': f'Недостаточно данных (N={N} < 5)'}

    # Определяем диапазон Q для расчёта
    all_data = np.concatenate([d for d in cat_data if len(d) > 0])
    if Q_grid is None:
        q_min = np.min(all_data) * 0.5
        q_max = np.max(all_data) * 1.5
        Q_grid = np.linspace(max(0, q_min), q_max, 200)

    # Для каждой категории строим кривую Pi(Q)
    cat_curves = []
    for i, (stat, data) in enumerate(zip(cat_stats, cat_data)):
        if not stat['valid'] or len(data) < 3:
            continue

        # Строим теоретическую кривую P(Q)
        # P(Q) = P(X >= Q) для данного распределения
        P_theoretical = np.array([0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4,
                                  0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99, 0.995, 0.999])

        if curve_type == 'kritsky_menkel':
            Q_theoretical = kritsky_menkel_ppf(P_theoretical, stat['mean'], stat['cv'], stat['cs'])
        else:
            Q_theoretical = pearson3_ppf(P_theoretical, stat['mean'], stat['cv'], stat['cs'])

        # Интерполяция P(Q) для сетки Q_grid
        # P(Q) убывает с ростом Q, поэтому инвертируем для интерполяции
        Q_sorted_idx = np.argsort(Q_theoretical)
        Q_sorted = Q_theoretical[Q_sorted_idx]
        P_sorted = P_theoretical[Q_sorted_idx]

        P_for_grid = np.interp(Q_grid, Q_sorted, P_sorted,
                               left=P_sorted[0], right=P_sorted[-1])
        P_for_grid = np.clip(P_for_grid, 0.0001, 0.9999)

        cat_curves.append({
            'name': stat['name'],
            'n': stat['n'],
            'P_values': P_for_grid,
            'stats': stat,
        })

    if not cat_curves:
        return {'error': 'Ни одна категория не содержит достаточно данных'}

    # Составная кривая: P_сост(Q) = Σ ni × Pi(Q) / N
    P_composite = np.zeros_like(Q_grid)
    for curve in cat_curves:
        weight = curve['n'] / N
        P_composite += weight * curve['P_values']

    P_composite = np.clip(P_composite, 0.0001, 0.9999)

    # Сортируем по убыванию Q (для красивого графика)
    sort_idx = np.argsort(Q_grid)[::-1]
    Q_sorted = Q_grid[sort_idx]
    P_sorted = P_composite[sort_idx]

    # Стандартные обеспеченностии для таблицы
    std_P = np.array([0.001, 0.01, 0.05, 0.1, 0.2, 0.3, 0.5,
                      0.7, 0.8, 0.9, 0.95, 0.99, 0.999])
    Q_at_std_P = np.interp(std_P, P_sorted, Q_sorted,
                            left=Q_sorted[0], right=Q_sorted[-1])

    curve_df = pd.DataFrame({
        'P_%': np.round(std_P * 100, 2),
        'Q_составная': np.round(Q_at_std_P, 2),
    })

    # Добавляем кривые по категориям
    for curve in cat_curves:
        P_cat = curve['P_values'][sort_idx]
        Q_at_P = np.interp(std_P, P_cat, Q_sorted,
                            left=Q_sorted[0], right=Q_sorted[-1])
        curve_df[f'Q_{curve["name"]}'] = np.round(Q_at_P, 2)

    return {
        'curve_df': curve_df,
        'category_curves': cat_curves,
        'category_stats': cat_stats,
        'total_years': N,
        'Q_grid': Q_grid,
        'P_composite': P_composite,
    }


# ============================================================
# ОБРАТНАЯ СОВМЕСТИМОСТЬ
# ============================================================

def find_change_point(values, years=None):
    """Обратная совместимость: поиск точки изменения (Pettitt)."""
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
    p_value = min(2 * np.exp(-6 * max_U**2 / (n**3 + n**2)), 1.0)

    change_year = int(years[change_idx]) if years is not None and change_idx < len(years) else None

    return {
        'change_year': change_year, 'change_index': change_idx,
        'p_value': round(p_value, 6), 'max_U': max_U,
        'significant': p_value < 0.05,
    }


def test_homogeneity_two_parts(part1, part2, alpha=0.05):
    """Обратная совместимость: тест Штрихова."""
    u_stat, u_p = stats.mannwhitneyu(part1, part2, alternative='two-sided')
    t_stat, t_p = stats.ttest_ind(part1, part2)
    ks_stat, ks_p = stats.ks_2samp(part1, part2)

    return {
        'u_stat': round(float(u_stat), 4), 'u_p': round(float(u_p), 6),
        't_stat': round(float(t_stat), 4), 't_p': round(float(t_p), 6),
        'ks_stat': round(float(ks_stat), 4), 'ks_p': round(float(ks_p), 6),
        'is_homogeneous': (u_p > alpha) and (t_p > alpha) and (ks_p > alpha),
        'alpha': alpha,
    }


def compute_part_stats(data, use_normative_Cs=True):
    """Обратная совместимость."""
    return compute_category_stats(data)


def split_series_by_year(values, years, break_year):
    """Обратная совместимость."""
    mask1 = years < break_year
    mask2 = years >= break_year
    return values[mask1], years[mask1], values[mask2], years[mask2]


def compute_composite_curve(values, years, break_year,
                            P_values=None, use_normative_Cs=True):
    """Обратная совместимость: старый интерфейс."""
    if P_values is None:
        P_values = [0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5,
                    0.7, 0.8, 0.9, 0.95, 0.98, 0.99, 0.995, 0.999]

    v1, y1, v2, y2 = split_series_by_year(values, years, break_year)

    stats1 = compute_part_stats(v1, use_normative_Cs)
    stats2 = compute_part_stats(v2, use_normative_Cs)

    P_arr = np.array(P_values)
    Q1 = pearson3_ppf(P_arr, stats1['mean'], stats1['cv'], stats1['cs'])
    Q2 = pearson3_ppf(P_arr, stats2['mean'], stats2['cv'], stats2['cs'])

    n1, n2 = len(v1), len(v2)
    n_total = n1 + n2
    Q_composite = (Q1 * n1 + Q2 * n2) / n_total

    curve_df = pd.DataFrame({
        'P_%': np.round(P_arr * 100, 3),
        'Q_часть1': np.round(Q1, 2),
        'Q_часть2': np.round(Q2, 2),
        'Q_составная': np.round(Q_composite, 2),
    })

    return {
        'curve_df': curve_df,
        'part1_stats': stats1,
        'part2_stats': stats2,
        'break_year': break_year,
        'n_part1': n1, 'n_part2': n2,
    }
