"""
core/stats/series_extension.py
Удлинение рядов наблюдений

Реализация методов удлинения согласно СП 33-101-2003 раздел 6.2:
- Регрессионный метод (линейная регрессия Qрасчёт = a × Qаналог + b)
- Метод пропорций (Qрасчёт = k × Qаналог)
- Проверка значимости связи (R > Ro крит)
- Оценка погрешности удлинённого ряда

Основные функции:
- validate_correlation — проверка значимости корреляции
- regression_extension — регрессионный метод удлинения
- proportional_extension — метод пропорций
- estimate_extension_error — оценка погрешности
- full_extension_workflow — полный цикл удлинения
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from scipy import stats


# Табличные значения Ro крит (СП 33-101-2003, Таблица 3)
# Ключ: (n_common, alpha=0.05)
RO_CRITICAL = {
    5: 0.878, 6: 0.811, 7: 0.754, 8: 0.707, 9: 0.666, 10: 0.632,
    11: 0.602, 12: 0.576, 13: 0.553, 14: 0.532, 15: 0.514,
    16: 0.497, 17: 0.482, 18: 0.468, 19: 0.456, 20: 0.444,
    25: 0.396, 30: 0.361, 35: 0.335, 40: 0.314, 50: 0.282,
    60: 0.259, 80: 0.226, 100: 0.203, 150: 0.166, 200: 0.143
}


def get_ro_critical(n: int, alpha: float = 0.05) -> float:
    """
    Получить табличное значение Ro крит для n общих лет.

    Если точное n нет в таблице — интерполяция.
    """
    keys = sorted(RO_CRITICAL.keys())
    if n < keys[0]:
        return 1.0
    if n > keys[-1]:
        return RO_CRITICAL[keys[-1]]

    for i in range(len(keys) - 1):
        if keys[i] <= n <= keys[i + 1]:
            frac = (n - keys[i]) / (keys[i + 1] - keys[i])
            return RO_CRITICAL[keys[i]] + frac * (RO_CRITICAL[keys[i + 1]] - RO_CRITICAL[keys[i]])

    return RO_CRITICAL[keys[-1]]


def validate_correlation(
    Q_calc: pd.Series,
    Q_analog: pd.Series,
    alpha: float = 0.05
) -> Dict:
    """
    Проверка статистической значимости корреляционной связи.

    СП 33-101-2003 п. 6.2.3: связь признаётся значимой при R > Ro(α, n).

    Parameters:
        Q_calc: ряд расчётной реки
        Q_analog: ряд реки-аналога
        alpha: уровень значимости

    Returns:
        Dict: R, Ro_crit, n_common, is_significant, quality_class
    """
    common_idx = Q_calc.index.intersection(Q_analog.index)
    n = len(common_idx)

    if n < 5:
        return {
            'R': 0, 'Ro_crit': 1.0, 'n_common': n,
            'is_significant': False,
            'quality_class': 'Нет связи (n < 5)'
        }

    Qc = Q_calc.loc[common_idx].values
    Qa = Q_analog.loc[common_idx].values

    R, p_value = stats.pearsonr(Qa, Qc)
    Ro = get_ro_critical(n, alpha)

    R2 = R ** 2

    if R > 0.95:
        quality = 'Отличная (R² > 0.90)'
    elif R > 0.90:
        quality = 'Хорошая (R² > 0.81)'
    elif R > 0.80:
        quality = 'Удовлетворительная (R² > 0.64)'
    elif R > 0.70:
        quality = 'Слабая (R² > 0.49)'
    else:
        quality = 'Неудовлетворительная (R² < 0.49)'

    return {
        'R': round(float(R), 4),
        'R2': round(float(R2), 4),
        'Ro_crit': round(Ro, 4),
        'n_common': n,
        'is_significant': float(R) > float(Ro),
        'p_value': round(float(p_value), 6),
        'quality_class': quality
    }


def regression_extension(
    Q_calc: pd.Series,
    Q_analog: pd.Series
) -> Dict:
    """
    Регрессионный метод продления ряда.

    Qрасчёт = a × Qаналог + b

    Parameters:
        Q_calc: ряд расчётной реки (короткий)
        Q_analog: ряд реки-аналога (длинный)

    Returns:
        Dict: a, b, R, n_common, validation, extended_series
    """
    validation = validate_correlation(Q_calc, Q_analog)
    if not validation['is_significant']:
        pass  # предупреждаем, но не блокируем

    common_idx = Q_calc.index.intersection(Q_analog.index)
    if len(common_idx) < 2:
        raise ValueError("Недостаточно общих лет для регрессии (нужно ≥ 2)")

    Qc = Q_calc.loc[common_idx]
    Qa = Q_analog.loc[common_idx]
    result = stats.linregress(Qa.values, Qc.values)
    a = float(result.slope)
    b = float(result.intercept)

    Q_ext = Q_analog.copy().astype(float)

    missing = Q_analog.index.difference(Q_calc.index)
    if len(missing) > 0:
        Q_ext.loc[missing] = a * Q_analog.loc[missing] + b

    common = Q_calc.index.intersection(Q_analog.index)
    Q_ext.loc[common] = Q_calc.loc[common]

    return {
        'a': round(a, 6),
        'b': round(b, 4),
        'R': validation['R'],
        'R2': validation['R2'],
        'Ro_crit': validation['Ro_crit'],
        'n_common': validation['n_common'],
        'is_significant': validation['is_significant'],
        'quality_class': validation['quality_class'],
        'extended_series': Q_ext,
        'warning': None if validation['is_significant'] else
                   f"R={validation['R']:.3f} < Ro={validation['Ro_crit']:.3f}. Связь статистически незначима!"
    }


def proportional_extension(
    Q_calc: pd.Series,
    Q_analog: pd.Series
) -> Dict:
    """
    Метод пропорций для продления ряда.

    Qрасчёт = k × Qаналог, где k = Qср_расчёт / Qср_аналог

    Parameters:
        Q_calc: ряд расчётной реки (короткий)
        Q_analog: ряд реки-аналога (длинный)

    Returns:
        Dict: k, Q_mean_calc, Q_mean_analog, extended_series
    """
    common_idx = Q_calc.index.intersection(Q_analog.index)
    if len(common_idx) < 2:
        raise ValueError("Недостаточно общих лет")

    Qc_mean = float(Q_calc.loc[common_idx].mean())
    Qa_mean = float(Q_analog.loc[common_idx].mean())

    k = Qc_mean / Qa_mean if Qa_mean != 0 else 1.0

    Q_ext = Q_analog.copy().astype(float) * k

    common = Q_calc.index.intersection(Q_analog.index)
    Q_ext.loc[common] = Q_calc.loc[common]

    return {
        'k': round(k, 6),
        'Q_mean_calc': round(Qc_mean, 4),
        'Q_mean_analog': round(Qa_mean, 4),
        'extended_series': Q_ext
    }


def estimate_extension_error(
    Q_calc: pd.Series,
    Q_analog: pd.Series,
    regression_result: Dict
) -> Dict:
    """
    Оценка погрешности продлённого ряда.

    СП 33-101-2003 п. 6.2.4:
    ε = (Cv / sqrt(n)) × Kr × 100%

    Для продлённого ряда:
    ε_продл = ε_исх × sqrt(n_исх / n_продл)

    Parameters:
        Q_calc: исходный (короткий) ряд
        Q_analog: ряд-аналог (длинный)
        regression_result: результат regression_extension

    Returns:
        Dict: epsilon_original, epsilon_extended, n_original, n_extended, reliability
    """
    n_orig = len(Q_calc.dropna())
    n_ext = len(Q_analog.dropna())

    Cv_orig = float(Q_calc.std() / Q_calc.mean()) if Q_calc.mean() != 0 else 0

    R = regression_result.get('R', 0.8)
    r = 0.5
    K_r = np.sqrt((1 + r) / (1 - r)) if r < 1 else 1.0

    eps_orig = (Cv_orig / np.sqrt(n_orig)) * K_r * 100
    eps_ext = (Cv_orig / np.sqrt(n_ext)) * K_r * 100

    if eps_ext <= 10:
        reliability = 'Надёжная'
    elif eps_ext <= 15:
        reliability = 'Пониженная надёжность'
    else:
        reliability = 'Ненадёжная'

    return {
        'epsilon_original': round(eps_orig, 2),
        'epsilon_extended': round(eps_ext, 2),
        'n_original': n_orig,
        'n_extended': n_ext,
        'Cv': round(Cv_orig, 4),
        'reliability': reliability,
        'improvement_pct': round((eps_orig - eps_ext) / eps_orig * 100, 1) if eps_orig > 0 else 0
    }


def full_extension_workflow(
    Q_calc: pd.Series,
    Q_analog: pd.Series,
    method: str = 'regression'
) -> Dict:
    """
    Полный цикл удлинения ряда с валидацией.

    Parameters:
        Q_calc: расчётный (короткий) ряд
        Q_analog: ряд-аналог (длинный)
        method: 'regression' или 'proportional'

    Returns:
        Dict: validation, extension_result, error_estimate, warnings
    """
    warnings = []

    validation = validate_correlation(Q_calc, Q_analog)

    if not validation['is_significant']:
        warnings.append(
            f"КРИТИЧНО: R={validation['R']:.3f} < Ro({validation['n_common']})={validation['Ro_crit']:.3f}. "
            f"Корреляция статистически незначима! Результаты могут быть недостоверными."
        )

    if validation['n_common'] < 10:
        warnings.append(
            f"Мало общих лет ({validation['n_common']}). Рекомендуется ≥ 10."
        )

    if method == 'regression':
        ext_result = regression_extension(Q_calc, Q_analog)
    else:
        ext_result = proportional_extension(Q_calc, Q_analog)

    error_est = estimate_extension_error(Q_calc, Q_analog, ext_result)

    if error_est['epsilon_extended'] > 15:
        warnings.append(
            f"ε после продления = {error_est['epsilon_extended']:.1f}% > 15%. "
            f"Ряд остаётся ненадёжным."
        )

    return {
        'validation': validation,
        'extension_result': ext_result,
        'error_estimate': error_est,
        'warnings': warnings,
        'extended_series': ext_result.get('extended_series'),
        'method': method
    }
