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
    """Тест Манна-Кендалла"""
    n = len(values)
    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            s += np.sign(values[j] - values[i])
    
    unique, counts = np.unique(values, return_counts=True)
    ties = np.sum(counts * (counts - 1) * (2 * counts + 5))
    var_s = (n * (n - 1) * (2 * n + 5) - ties) / 18
    
    if s > 0:
        z = (s - 1) / np.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / np.sqrt(var_s)
    else:
        z = 0
    
    p_value = 2 * (1 - norm.cdf(abs(z)))
    
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
    """Наклон Сена"""
    n = len(values)
    slopes = []
    for i in range(n):
        for j in range(i + 1, n):
            if years[j] != years[i]:
                slopes.append((values[j] - values[i]) / (years[j] - years[i]))
    
    slope = np.median(slopes) if slopes else 0
    intercept = np.median(values) - slope * np.median(years)
    return {'slope': slope, 'intercept': intercept}


def pettitt_test(values):
    """
    Тест Петтитта (Pettitt test) — поиск точки изменения
    """
    n = len(values)
    U_t = []
    
    for t in range(1, n):
        left = values[:t]
        right = values[t:]
        u = sum(np.sign(x - y) for x in right for y in left)
        U_t.append(abs(u))
    
    if not U_t:
        return None
    
    max_U = max(U_t)
    change_idx = U_t.index(max_U)
    change_year = None  # будет заполнено позже
    
    # Примерная оценка значимости
    p_value = 2 * np.exp(-6 * max_U**2 / (n**3 + n**2))
    
    return {
        'change_index': change_idx,
        'max_U': max_U,
        'p_value': min(p_value, 1.0),
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