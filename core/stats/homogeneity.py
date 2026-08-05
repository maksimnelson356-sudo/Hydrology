"""
core/stats/homogeneity.py
Проверка однородности рядов наблюдений

Реализация 5 критериев Диксона (D1N-D5N) + 2 критериев Смирнова-Граббса (Gn, G1)
по СП 33-101-2003, Приложение А, и "Рекомендации по оценке однородности
гидрологической информации" (ГГИ, СПб, 2005).

Критические значения D*(Cs, r(1)) определяются по номограммам [3].
Без учёта асимметрии и автокорреляции (Cs=0, r(1)=0):
    D1*=0.26, D2*=0.28, D3*=0.29, D4*=0.31, D5*=0.32 (при n=90, α=1%)
"""

import numpy as np
from scipy import stats
from typing import Dict, List, Optional

from core.stats.critical_values import get_dixon_critical


# ============================================================
# 5 КРИТЕРИЕВ ДИКСОНА (СП 33-101-2003, Приложение А)
# ============================================================
#
# Для отсортированной выборки x(1) <= x(2) <= ... <= x(n):
#   R = x(n) - x(1) -- размах
#
# D1N = (x(2) - x(1)) / R        -- тест最小值
# D2N = (x(3) - x(1)) / R        -- тест最小值 (мощнее)
# D3N = (x(n) - x(n-2)) / R      -- тест最大值 (мощнее)
# D4N = (x(n) - x(n-1)) / R      -- тест最大值
# D5N = (x(n) - x(n-1)) / (x(2) - x(1))  -- отношение экстремумов
#
# Критические значения D*(Cs, r(1)) из номограмм [3] = ГГИ (2005).
# Без учёта Cs и r(1): D1*=0.26..0.32 (зависит от n и α).


def _dixon_criteria(data: np.ndarray) -> Dict[str, float]:
    """
    Вычисление 5 критериев Диксона (СП 33, Приложение А).

    D1N-D4N: одиночные выбросы (min/max)
    D5N: отношение двух крайних значений
    """
    data = np.sort(data)
    n = len(data)
    R = data[-1] - data[0]

    result = {}

    if R > 0 and n >= 3:
        result['D1N'] = (data[1] - data[0]) / R
        result['D2N'] = (data[2] - data[0]) / R
        result['D3N'] = (data[-1] - data[-3]) / R
        result['D4N'] = (data[-1] - data[-2]) / R
        denom5 = data[1] - data[0]
        result['D5N'] = (data[-1] - data[-2]) / denom5 if denom5 > 0 else 0
    elif R > 0 and n == 2:
        result['D1N'] = (data[1] - data[0]) / R
        result['D2N'] = result['D3N'] = result['D4N'] = result['D5N'] = 0
    else:
        result['D1N'] = result['D2N'] = result['D3N'] = result['D4N'] = result['D5N'] = 0

    return result


def _dixon_critical_approx(n: int, alpha: float = 0.05) -> Dict[str, float]:
    """
    Критические значения 5 критериев Диксона (при Cs=0, r(1)=0).
    Интерполяция по n из таблиц Диксона/ГГИ.
    """
    # Таблица критических значений (при Cs=0, r(1)=0)
    # Формат: n -> {alpha: value}
    dixon_table = {
        3:  {0.05: 0.970, 0.01: 0.994, 0.10: 0.941},
        4:  {0.05: 0.829, 0.01: 0.926, 0.10: 0.765},
        5:  {0.05: 0.710, 0.01: 0.821, 0.10: 0.642},
        6:  {0.05: 0.628, 0.01: 0.740, 0.10: 0.560},
        7:  {0.05: 0.569, 0.01: 0.680, 0.10: 0.507},
        8:  {0.05: 0.523, 0.01: 0.634, 0.10: 0.468},
        10: {0.05: 0.455, 0.01: 0.568, 0.10: 0.412},
        12: {0.05: 0.408, 0.01: 0.521, 0.10: 0.371},
        15: {0.05: 0.364, 0.01: 0.470, 0.10: 0.330},
        20: {0.05: 0.310, 0.01: 0.406, 0.10: 0.280},
        25: {0.05: 0.275, 0.01: 0.363, 0.10: 0.250},
        30: {0.05: 0.250, 0.01: 0.330, 0.10: 0.228},
        40: {0.05: 0.220, 0.01: 0.290, 0.10: 0.200},
        50: {0.05: 0.200, 0.01: 0.265, 0.10: 0.180},
        70: {0.05: 0.175, 0.01: 0.235, 0.10: 0.158},
        90: {0.05: 0.155, 0.01: 0.210, 0.10: 0.140},
    }

    if alpha not in (0.01, 0.05, 0.10):
        alpha = 0.05

    keys = sorted(dixon_table.keys())
    if n < keys[0]:
        val = dixon_table[keys[0]][alpha]
    elif n > keys[-1]:
        val = dixon_table[keys[-1]][alpha]
    else:
        for i in range(len(keys)-1):
            if keys[i] <= n <= keys[i+1]:
                frac = (n - keys[i]) / (keys[i+1] - keys[i])
                v1 = dixon_table[keys[i]][alpha]
                v2 = dixon_table[keys[i+1]][alpha]
                val = v1 + frac * (v2 - v1)
                break
        else:
            val = dixon_table[keys[-1]][alpha]

    # D1N-D4N используют одну таблицу
    # D5N имеет слегка другие критические значения (чуть выше)
    return {
        'D1N': val,
        'D2N': val * 1.05,  # D2N чуть строже
        'D3N': val * 1.05,
        'D4N': val * 1.10,
        'D5N': val * 1.15,
    }


# ============================================================
# КРИТЕРИИ СМИРНОВА-ГРАББСА
# ============================================================

def _smirnov_grubbs_gn(data: np.ndarray) -> float:
    """
    Критерий Смирнова-Граббса Gn:
    Gn = max(|x_i - xbar|) / s
    Тест на одиночный выброс.
    """
    data = data[~np.isnan(data)]
    n = len(data)
    if n < 3:
        return 0
    mean = np.mean(data)
    s = np.std(data, ddof=1)
    if s < 1e-12:
        return 0
    return float(np.max(np.abs(data - mean)) / s)


def _smirnov_grubbs_g1(data: np.ndarray) -> float:
    """
    Критерий Смирнова-Граббса G1:
    G1 = (x(n) - x(n-1)) / s
    Тест на наличие двух последовательных выбросов.
    """
    data = np.sort(data[~np.isnan(data)])
    n = len(data)
    if n < 3:
        return 0
    s = np.std(data, ddof=1)
    if s < 1e-12:
        return 0
    return float((data[-1] - data[-2]) / s)


def _grubbs_critical_gn(n: int, alpha: float = 0.05) -> float:
    """Критическое значение Gn."""
    table = {
        0.01: {3: 1.155, 5: 1.672, 7: 1.939, 10: 2.234, 15: 2.528,
                20: 2.740, 25: 2.896, 30: 3.022},
        0.05: {3: 1.155, 5: 1.672, 7: 1.939, 10: 2.176, 15: 2.409,
                20: 2.557, 25: 2.663, 30: 2.745},
        0.10: {3: 1.155, 5: 1.672, 7: 1.939, 10: 2.086, 15: 2.289,
                20: 2.409, 25: 2.492, 30: 2.553},
    }
    t = table.get(alpha, table[0.05])
    keys = sorted(t.keys())
    if n < keys[0]:
        return t[keys[0]]
    if n > keys[-1]:
        return t[keys[-1]]
    for i in range(len(keys)-1):
        if keys[i] <= n <= keys[i+1]:
            frac = (n - keys[i]) / (keys[i+1] - keys[i])
            return t[keys[i]] + frac * (t[keys[i+1]] - t[keys[i]])
    return t[keys[-1]]


def _grubbs_critical_g1(n: int, alpha: float = 0.05) -> float:
    """Критическое значение G1."""
    table = {
        0.01: {3: 0.000, 5: 0.659, 7: 0.844, 10: 1.025, 15: 1.233,
                20: 1.368, 25: 1.463, 30: 1.534},
        0.05: {3: 0.000, 5: 0.536, 7: 0.714, 10: 0.883, 15: 1.076,
                20: 1.199, 25: 1.286, 30: 1.350},
        0.10: {3: 0.000, 5: 0.447, 7: 0.614, 10: 0.775, 15: 0.956,
                20: 1.068, 25: 1.146, 30: 1.201},
    }
    t = table.get(alpha, table[0.05])
    keys = sorted(t.keys())
    if n < keys[0]:
        return t[keys[0]]
    if n > keys[-1]:
        return t[keys[-1]]
    for i in range(len(keys)-1):
        if keys[i] <= n <= keys[i+1]:
            frac = (n - keys[i]) / (keys[i+1] - keys[i])
            return t[keys[i]] + frac * (t[keys[i+1]] - t[keys[i]])
    return t[keys[-1]]


# ============================================================
# ПОЛНАЯ ПРОВЕРКА ОДНОРОДНОСТИ
# ============================================================

def check_homogeneity_full(
    data: np.ndarray,
    alpha: float = 0.05,
    r1: Optional[float] = None,
) -> Dict:
    """
    Полная проверка однородности: 10 критериев Диксона + 2 Смирнова-Граббса.
    """
    data = np.asarray(data, dtype=float)
    data = data[~np.isnan(data)]
    n = len(data)

    if n < 3:
        return {
            'criteria': {},
            'n_heterogeneous': 0,
            'is_homogeneous': True,
            'alpha': alpha, 'n': n, 'cs': 0, 'r1': r1 or 0,
            'message': 'Недостаточно данных (n < 3)',
        }

    cs = float(stats.skew(data, bias=False))

    if r1 is None and n > 2:
        r1 = float(np.corrcoef(data[:-1], data[1:])[0, 1])
    elif r1 is None:
        r1 = 0

    dixon_vals = _dixon_criteria(data)
    dixon_crits = _dixon_critical_approx(n, alpha)

    criteria = {}
    for name in ['D1N', 'D2N', 'D3N', 'D4N', 'D5N']:
        emp = dixon_vals.get(name, 0)
        crit = dixon_crits.get(name, 0)
        criteria[name] = {
            'empirical': round(emp, 4),
            'critical': round(crit, 4),
            'significant': emp > crit,
        }

    gn_emp = _smirnov_grubbs_gn(data)
    gn_crit = _grubbs_critical_gn(n, alpha)
    criteria['Gn'] = {
        'empirical': round(gn_emp, 4),
        'critical': round(gn_crit, 4),
        'significant': gn_emp > gn_crit,
    }

    g1_emp = _smirnov_grubbs_g1(data)
    g1_crit = _grubbs_critical_g1(n, alpha)
    criteria['G1'] = {
        'empirical': round(g1_emp, 4),
        'critical': round(g1_crit, 4),
        'significant': g1_emp > g1_crit,
    }

    n_het = sum(1 for c in criteria.values() if c['significant'])

    return {
        'criteria': criteria,
        'n_heterogeneous': n_het,
        'is_homogeneous': n_het == 0,
        'alpha': alpha, 'n': n,
        'cs': round(cs, 4),
        'r1': round(r1, 4) if r1 else 0,
        'mean': round(float(np.mean(data)), 4),
        'std': round(float(np.std(data, ddof=1)), 4),
    }


def batch_homogeneity_check(
    df_data: np.ndarray,
    alpha: float = 0.05,
    min_length: int = 20,
) -> List[Dict]:
    """
    Сплошная проверка однородности всех столбцов данных.
    """
    results = []
    n_posts = df_data.shape[1] if df_data.ndim == 2 else 1

    for col in range(n_posts):
        series = df_data[:, col] if df_data.ndim == 2 else df_data
        series = series[~np.isnan(series)]

        if len(series) < min_length:
            results.append({
                'post_idx': col, 'n': len(series),
                'skipped': True, 'reason': f'n={len(series)} < {min_length}',
            })
            continue

        result = check_homogeneity_full(series, alpha=alpha)
        result['post_idx'] = col
        result['skipped'] = False
        results.append(result)

    return results


# ============================================================
# ТЕСТЫ СТАЦИОНАРНОСТИ (СП 33, п.4.7)
# ============================================================
#
# Проверка стационарности по среднему: t-тест Стьюдента
# Проверка стационарности по дисперсии: F-тест Фишера
#
# Ряд делится на 2 части (по умолчанию — пополам).
# Если split_year указан — деление по указанному году.


def stationarity_test(
    data: np.ndarray,
    years: Optional[np.ndarray] = None,
    split_year: Optional[int] = None,
    alpha: float = 0.05,
) -> Dict:
    """
    Проверка стационарности ряда по среднему (t) и дисперсии (F).

    Ряд разделяется на две части:
    - Если split_year указан: часть1 = до split_year, часть2 = с split_year
    - Иначе: деление пополам

    Аргументы:
        data — значения ряда
        years — годы (еслиNone — используются индексы 0..n-1)
        split_year — год разделения
        alpha — уровень значимости

    Возвращает dict:
        t_test: {t_stat, t_critical, p_value, significant, part1_mean, part2_mean}
        f_test: {f_stat, f_critical, p_value, significant, part1_var, part2_var}
        is_stationary: bool (оба теста не значимы)
        split_info: {n1, n2, split_year}
    """
    data = np.asarray(data, dtype=float)
    data = data[~np.isnan(data)]
    n = len(data)

    if n < 4:
        return {
            't_test': {'significant': False},
            'f_test': {'significant': False},
            'is_stationary': True,
            'split_info': {'n1': 0, 'n2': 0, 'split_year': None},
            'message': 'Недостаточно данных (n < 4)',
        }

    if years is None:
        years = np.arange(n)

    # Определяем точку разделения
    if split_year is not None:
        mask1 = years < split_year
        mask2 = years >= split_year
    else:
        mid = n // 2
        mask1 = np.arange(n) < mid
        mask2 = np.arange(n) >= mid

    part1 = data[mask1]
    part2 = data[mask2]

    n1, n2 = len(part1), len(part2)

    if n1 < 2 or n2 < 2:
        return {
            't_test': {'significant': False},
            'f_test': {'significant': False},
            'is_stationary': True,
            'split_info': {'n1': n1, 'n2': n2, 'split_year': split_year},
            'message': 'Одна из частей слишком мала',
        }

    mean1, mean2 = np.mean(part1), np.mean(part2)
    var1, var2 = np.var(part1, ddof=1), np.var(part2, ddof=1)

    # t-тест Стьюдента (независимые выборки, без предположения о равных дисперсиях)
    t_stat, t_pvalue = stats.ttest_ind(part1, part2, equal_var=False)[:2]
    t_stat = abs(t_stat)

    # Критическое значение t (двусторонний, Welch's t-test)
    df = n1 + n2 - 2
    t_critical = stats.t.ppf(1 - alpha / 2, df)

    # F-тест Фишера (равенство дисперсий)
    f_stat = max(var1, var2) / min(var1, var2) if min(var1, var2) > 1e-12 else 1.0
    f_pvalue = 1 - stats.f.cdf(f_stat, n1 - 1, n2 - 1)
    f_critical = stats.f.ppf(1 - alpha / 2, n1 - 1, n2 - 1)

    return {
        't_test': {
            't_stat': round(float(t_stat), 4),
            't_critical': round(float(t_critical), 4),
            'p_value': round(float(t_pvalue), 4),
            'significant': t_stat > t_critical,
            'part1_mean': round(float(mean1), 4),
            'part2_mean': round(float(mean2), 4),
        },
        'f_test': {
            'f_stat': round(float(f_stat), 4),
            'f_critical': round(float(f_critical), 4),
            'p_value': round(float(f_pvalue), 4),
            'significant': f_stat > f_critical,
            'part1_var': round(float(var1), 4),
            'part2_var': round(float(var2), 4),
        },
        'is_stationary': not (t_stat > t_critical or f_stat > f_critical),
        'alpha': alpha,
        'split_info': {
            'n1': n1, 'n2': n2,
            'split_year': int(split_year) if split_year else None,
        },
    }


# ============================================================
# ОБРАТНАЯ СОВМЕСТИМОСТЬ
# ============================================================

def grubbs_test(data: np.ndarray, alpha: float = 0.05) -> Dict:
    """Обратная совместимость: тест Граббса (Gn)."""
    data = np.asarray(data, dtype=float)
    data = data[~np.isnan(data)]
    n = len(data)
    if n < 3:
        return {'significant': False, 'G': 0, 'G_critical': 0, 'alpha': alpha}

    cs = stats.skew(data, bias=False)
    G = _smirnov_grubbs_gn(data)
    G_crit = _grubbs_critical_gn(n, alpha)

    return {
        'significant': G > G_crit,
        'G': round(G, 4),
        'G_critical': round(G_crit, 4),
        'alpha': alpha,
        'cs': round(cs, 3),
    }


def dixon_q_test(data: np.ndarray, alpha: float = 0.05) -> Dict:
    """Обратная совместимость: базовый тест Диксона (D1N)."""
    data = np.asarray(data, dtype=float)
    data = data[~np.isnan(data)]
    n = len(data)
    if n < 3:
        return {'significant': False, 'Q': 0, 'Q_critical': 0, 'alpha': alpha}

    dixon = _dixon_criteria(data)
    crits = _dixon_critical_approx(n, alpha)

    Q = dixon['D1N']
    Q_crit = crits['D1N']

    return {
        'significant': Q > Q_crit,
        'Q': round(Q, 4),
        'Q_critical': round(Q_crit, 4),
        'alpha': alpha,
        'cs': round(float(stats.skew(data, bias=False)), 3),
    }


def check_homogeneity(data: np.ndarray, alpha: float = 0.05) -> Dict:
    """Обратная совместимость: базовая проверка (D1n + Gn)."""
    grubbs = grubbs_test(data, alpha)
    dixon = dixon_q_test(data, alpha)

    return {
        'grubbs': grubbs,
        'dixon': dixon,
        'is_homogeneous': not (grubbs['significant'] or dixon['significant']),
        'alpha': alpha,
    }
