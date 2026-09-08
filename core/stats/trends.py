"""
core/stats/trends.py
Улучшенный анализ трендов + Pettitt test
"""

import numpy as np
from scipy import stats
from scipy.stats import norm


def linear_trend(years, values):
    """Линейный тренд с доверительным интервалом"""
    slope, intercept, r_value, p_value, std_err = stats.linregress(years, values)

    # Доверительный интервал для наклона (95%)
    n = len(years)
    t_val = stats.t.ppf(0.975, n - 2)
    slope_ci = t_val * std_err

    return {
        'slope': slope,
        'intercept': intercept,
        'r_squared': r_value ** 2,
        'p_value': p_value,
        'std_err': std_err,
        'slope_ci_lower': slope - slope_ci,
        'slope_ci_upper': slope + slope_ci,
        'significant': p_value < 0.05
    }


def mann_kendall_test(values):
    """Тест Манна-Кендалла (векторизованная реализация)."""
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n < 4:
        return {'statistic': 0, 'z': 0, 'p_value': 1.0,
                'trend': 'Тренд отсутствует', 'significant': False}

    # Векторизованный расчёт S: только пары i < j.
    # (Полная матрица all-pairs взаимно уничтожает знаки: sign(x_j-x_i) = -sign(x_i-x_j))
    i_idx, j_idx = np.triu_indices(n, k=1)
    diffs = values[j_idx] - values[i_idx]
    s = float(np.sum(np.sign(diffs)))

    unique, counts = np.unique(values, return_counts=True)
    ties = np.sum(counts * (counts - 1) * (2 * counts + 5))
    var_s = (n * (n - 1) * (2 * n + 5) - ties) / 18.0
    var_s = max(var_s, 1e-10)

    if s > 0:
        z = (s - 1) / np.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / np.sqrt(var_s)
    else:
        z = 0

    p_value = float(2 * (1 - norm.cdf(abs(z))))

    if s > 0:
        trend = "Рост"
    elif s < 0:
        trend = "Снижение"
    else:
        trend = "Тренд отсутствует"

    return {
        'statistic': s,
        'z': z,
        'p_value': p_value,
        'trend': trend,
        'significant': p_value < 0.05
    }


def sens_slope(years, values):
    """
    Наклон Сена (векторизованная реализация).

    Медиана попарных наклонов (Yj - Yi) / (Xj - Xi) для всех i < j.
    O(n²) по памяти, но векторные операции NumPy дают ускорение ~100x.
    """
    years = np.asarray(years, dtype=float)
    values = np.asarray(values, dtype=float)

    n = len(values)
    if n < 2:
        return {'slope': 0.0, 'intercept': 0.0}

    if len(years) != n:
        raise ValueError("years и values должны быть одинаковой длины")

    # Создаём i < j через broadcasting
    i_idx, j_idx = np.triu_indices(n, k=1)
    dy = values[j_idx] - values[i_idx]
    dx = years[j_idx] - years[i_idx]
    valid = dx != 0
    slopes = dy[valid] / dx[valid]

    if slopes.size == 0:
        return {'slope': 0.0, 'intercept': float(np.median(values))}

    slope = float(np.median(slopes))
    intercept = float(np.median(values) - slope * np.median(years))
    return {'slope': slope, 'intercept': intercept}


def pettitt_test(values):
    """
    Тест Петтитта (Pettitt test) — поиск точки изменения.
    Векторизованная реализация.
    """
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n < 4:
        return {'change_index': 0, 'max_U': 0, 'p_value': 1.0, 'significant': False}

    # Векторизованный расчёт U_t
    sign_diff = np.sign(values[None, :] - values[:, None])
    U_t_clean = []
    for t in range(1, n):
        u = float(np.sum(sign_diff[t:, :t]))
        U_t_clean.append(abs(u))

    if not U_t_clean:
        return {'change_index': 0, 'max_U': 0, 'p_value': 1.0, 'significant': False}

    U_arr = np.array(U_t_clean)
    max_U = float(np.max(U_arr))
    change_idx = int(np.argmax(U_arr))

    p_value = float(2 * np.exp(-6 * max_U**2 / (n**3 + n**2)))
    p_value = min(max(p_value, 0.0), 1.0)

    return {
        'change_index': change_idx,
        'max_U': max_U,
        'p_value': p_value,
        'significant': p_value < 0.05
    }


def full_trend_analysis(df):
    """Полный анализ тренда"""
    years = df['year'].values.astype(float)
    values = df['value'].values

    linear = linear_trend(years, values)
    mk = mann_kendall_test(values)
    sen = sens_slope(years, values)
    pettitt = pettitt_test(values)

    if pettitt:
        pettitt['change_year'] = int(years[pettitt['change_index']])

    # Интерпретация
    if mk['significant']:
        interp = f"Обнаружен значимый {mk['trend'].lower()} (p={mk['p_value']:.4f})"
    else:
        interp = f"Статистически значимый тренд не обнаружен (направление: {mk['trend'].lower()}, p={mk['p_value']:.4f})"

    if pettitt and pettitt['significant']:
        interp += f" | Возможная точка изменения: ~{pettitt['change_year']} г."

    return {
        'linear': linear,
        'mann_kendall': mk,
        'sen_slope': sen,
        'pettitt': pettitt,
        'interpretation': interp,
        'years': years,
        'values': values
    }
