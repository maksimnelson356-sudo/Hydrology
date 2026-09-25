"""
core/stats/series_extension.py
Удлинение рядов наблюдений

Реализация методов удлинения согласно СП 33-101-2003, п. 6.2–6.7:
- Регрессионный метод (линейная регрессия Qрасчёт = a × Qаналог + b)
- Метод пропорций (Qрасчёт = k × Qаналог)
- Проверка числа совместных наблюдений, корреляции и погрешности коэффициентов
- Оценка неопределённости по остаткам регрессии

Основные функции:
- validate_correlation — проверка значимости корреляции
- regression_extension — регрессионный метод удлинения
- proportional_extension — метод пропорций
- estimate_extension_error — оценка погрешности
- full_extension_workflow — полный цикл удлинения
"""


import numpy as np
import pandas as pd
from scipy import stats

from core.stats.sp33_variance_correction import apply_formula_6_9, apply_formula_6_10

MIN_COMMON_YEARS = 6
MIN_CORRELATION = 0.7
MIN_CORRELATION_SIGMA_RATIO = 2.0
MIN_SLOPE_SIGMA_RATIO = 2.0

# Legacy table retained for callers of get_ro_critical(). The normative
# regression gate follows СП 33-101-2003 п. 6.7 and uses MIN_CORRELATION.
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
) -> dict:
    """Проверить применимость регрессии по критериям СП 33-101-2003 п. 6.7."""
    common_idx = Q_calc.index.intersection(Q_analog.index)
    n = len(common_idx)

    if n < MIN_COMMON_YEARS:
        return {
            'R': 0.0,
            'R2': 0.0,
            'Ro_crit': MIN_CORRELATION,
            'R_critical': MIN_CORRELATION,
            'sigma_R': float('inf'),
            'R_over_sigma_R': 0.0,
            'n_common': n,
            'is_significant': False,
            'p_value': 1.0,
            'quality_class': f'Недостаточно совместных наблюдений (n < {MIN_COMMON_YEARS})',
        }

    Qc = Q_calc.loc[common_idx].values
    Qa = Q_analog.loc[common_idx].values
    R, p_value = stats.pearsonr(Qa, Qc)
    sigma_R = max((1.0 - float(R) ** 2) / np.sqrt(n), 1e-12)
    R_over_sigma_R = float(R) / sigma_R
    is_significant = (
        float(R) >= MIN_CORRELATION
        and R_over_sigma_R >= MIN_CORRELATION_SIGMA_RATIO
    )

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
        'R2': round(float(R) ** 2, 4),
        'Ro_crit': MIN_CORRELATION,
        'R_critical': MIN_CORRELATION,
        'sigma_R': round(sigma_R, 6),
        'R_over_sigma_R': round(R_over_sigma_R, 4),
        'n_common': n,
        'is_significant': is_significant,
        'p_value': round(float(p_value), 6),
        'quality_class': quality,
    }


def regression_extension(
    Q_calc: pd.Series,
    Q_analog: pd.Series
) -> dict:
    """
    Регрессионный метод продления ряда.

    Qрасчёт = a × Qаналог + b

    Parameters:
        Q_calc: ряд расчётной реки (короткий)
        Q_analog: ряд реки-аналога (длинный)

    Returns:
        Dict: a, b, R, n_common, validation, extended_series
    """
    common_idx = Q_calc.index.intersection(Q_analog.index)
    n_common = len(common_idx)
    if n_common < MIN_COMMON_YEARS:
        raise ValueError(
            f"Для регрессии по СП 33-101-2003 п. 6.7 нужно ≥ {MIN_COMMON_YEARS} "
            f"совместных лет; получено {n_common}"
        )

    validation = validate_correlation(Q_calc, Q_analog)
    Qc = Q_calc.loc[common_idx]
    Qa = Q_analog.loc[common_idx]
    result = stats.linregress(Qa.values, Qc.values)
    a = float(result.slope)
    b = float(result.intercept)

    if not validation['is_significant']:
        raise ValueError(
            f"Корреляция R={validation['R']:.3f} не соответствует СП 33-101-2003 п. 6.7: "
            f"R ≥ {MIN_CORRELATION}, R/σR ≥ {MIN_CORRELATION_SIGMA_RATIO}"
        )

    slope_std_error = float(result.stderr)
    slope_over_sigma = (
        float('inf') if slope_std_error == 0.0 else abs(a) / slope_std_error
    )
    if a <= 0.0:
        raise ValueError("Коэффициент регрессии должен быть положительным")
    if slope_over_sigma < MIN_SLOPE_SIGMA_RATIO:
        raise ValueError(
            f"Коэффициент регрессии не подтверждён критерием СП 33-101-2003 п. 6.7: "
            f"k/σk={slope_over_sigma:.3f} < {MIN_SLOPE_SIGMA_RATIO}"
        )

    Q_ext = Q_analog.copy().astype(float)

    missing = Q_analog.index.difference(Q_calc.index)
    if len(missing) > 0:
        Q_ext.loc[missing] = a * Q_analog.loc[missing] + b

    common = Q_calc.index.intersection(Q_analog.index)
    Q_ext.loc[common] = Q_calc.loc[common]

    # === Проверка остатков (СП 33-101-2003 п. 6.2.4) ===
    # Остатки = наблюдаемые - предсказанные. Должны:
    # 1) Не иметь систематического смещения (mean ~ 0)
    # 2) Быть гомоскедастичными (σ постоянна)
    # 3) Не содержать выбросов (|residual| > 3·σ — подозрительные)
    residuals = Q_calc.loc[common_idx] - (a * Q_analog.loc[common_idx] + b)
    resid_mean = float(residuals.mean())
    resid_std = float(residuals.std())
    outlier_mask = (residuals - resid_mean).abs() > 3 * resid_std
    n_outliers = int(outlier_mask.sum())

    # Тест на гетероскедастичность (ранговый по подвыборкам)
    half = len(residuals) // 2
    resid_var_1 = float(residuals.iloc[:half].var()) if half > 1 else 0.0
    resid_var_2 = float(residuals.iloc[half:].var()) if half > 1 else 0.0
    heteroscedasticity = (min(resid_var_1, resid_var_2) > 0 and
                         max(resid_var_1, resid_var_2) / min(resid_var_1, resid_var_2) > 4.0)

    residual_diagnostics = {
        'resid_mean': round(resid_mean, 4),
        'resid_std': round(resid_std, 4),
        'n_outliers_3sigma': n_outliers,
        'has_outliers': n_outliers > 0,
        'var_first_half': round(resid_var_1, 4),
        'var_second_half': round(resid_var_2, 4),
        'heteroscedastic': heteroscedasticity,
    }

    warnings = []
    if n_outliers > 0:
        warnings.append(
            f"Обнаружено {n_outliers} выбросов в остатках (>3σ). "
            f"Проверьте исходные данные — возможны аномальные годы."
        )
    if heteroscedasticity:
        warnings.append(
            f"Гетероскедастичность остатков: дисперсия меняется в {max(resid_var_1, resid_var_2) / max(min(resid_var_1, resid_var_2), 1e-10):.1f} раз. "
            f"Регрессия может давать смещённые интервалы."
        )
    if abs(resid_mean) > 0.5 * resid_std:
        warnings.append(
            f"Систематическое смещение в остатках: mean={resid_mean:.3f}, std={resid_std:.3f}."
        )

    return {
        'a': round(a, 6),
        'b': round(b, 4),
        'R': validation['R'],
        'R2': validation['R2'],
        'Ro_crit': validation['Ro_crit'],
        'sigma_R': validation['sigma_R'],
        'R_over_sigma_R': validation['R_over_sigma_R'],
        'slope_std_error': round(slope_std_error, 6),
        'slope_over_sigma': round(slope_over_sigma, 4),
        'n_common': validation['n_common'],
        'is_significant': validation['is_significant'],
        'quality_class': validation['quality_class'],
        'extended_series': Q_ext,
        'residual_diagnostics': residual_diagnostics,
        'warnings': warnings,
        'warning': None,
    }


def proportional_extension(
    Q_calc: pd.Series,
    Q_analog: pd.Series
) -> dict:
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
    regression_result: dict
) -> dict:
    """Оценить неопределённость по остаткам линейной регрессии.

    Это инженерная оценка ошибки прогноза: фиксированный коэффициент r=0.5
    удалён, а неопределённость вычисляется из остатков и разброса аналога.
    """
    common_idx = Q_calc.index.intersection(Q_analog.index)
    n_orig = len(common_idx)
    n_ext = len(Q_analog.dropna())
    if n_orig < 3:
        raise ValueError("Для оценки погрешности нужно ≥ 3 совместных наблюдений")

    if 'a' in regression_result:
        a = float(regression_result['a'])
        b = float(regression_result.get('b', 0.0))
        parameter_count = 2 if 'b' in regression_result else 1
    elif 'k' in regression_result:
        a = float(regression_result['k'])
        b = 0.0
        parameter_count = 1
    else:
        raise ValueError("Результат удлинения не содержит коэффициент регрессии")
    x_common = Q_analog.loc[common_idx].astype(float)
    y_common = Q_calc.loc[common_idx].astype(float)
    predicted_common = a * x_common + b
    residuals = y_common - predicted_common
    degrees_of_freedom = n_orig - parameter_count
    if degrees_of_freedom <= 0:
        raise ValueError("Недостаточно степеней свободы для оценки погрешности")

    residual_std_error = float(np.sqrt(np.sum(residuals ** 2) / degrees_of_freedom))
    x_mean = float(x_common.mean())
    sxx = float(np.sum((x_common - x_mean) ** 2))
    if sxx == 0.0:
        raise ValueError("Ряд-аналог не имеет дисперсии")

    def prediction_std_error(values: pd.Series) -> np.ndarray:
        leverage = 1.0 / n_orig + (values - x_mean) ** 2 / sxx
        return residual_std_error * np.sqrt(leverage)

    common_error = prediction_std_error(x_common)
    missing_idx = Q_analog.index.difference(Q_calc.index)
    extended_x = Q_analog.loc[missing_idx].astype(float)
    if extended_x.empty:
        extended_x = x_common
    extended_error = prediction_std_error(extended_x)
    extended_prediction = a * extended_x + b

    eps_orig = float(np.mean(common_error / np.maximum(np.abs(predicted_common), 1e-12)) * 100)
    eps_ext = float(np.mean(extended_error / np.maximum(np.abs(extended_prediction), 1e-12)) * 100)

    if eps_ext <= 10:
        reliability = 'Надёжная'
    elif eps_ext <= 15:
        reliability = 'Пониженная надёжность'
    else:
        reliability = 'Ненадёжная'

    return {
        'epsilon_original': round(eps_orig, 2),
        'epsilon_extended': round(eps_ext, 2),
        'residual_std_error': round(residual_std_error, 6),
        'prediction_std_error_mean': round(float(np.mean(extended_error)), 6),
        'n_original': n_orig,
        'n_extended': n_ext,
        'reliability': reliability,
        'improvement_pct': round((eps_orig - eps_ext) / eps_orig * 100, 1) if eps_orig > 0 else 0,
    }


def full_extension_workflow(
    Q_calc: pd.Series,
    Q_analog: pd.Series,
    method: str = 'regression'
) -> dict:
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


def multi_analog_extension(
    Q_calc: pd.Series,
    analogs: dict[str, pd.Series],
    n_min: int = 6,
    ro_cr: float = 0.7,
    ro_over_sigma: float = 2.0,
    k_over_sigma: float = 2.0,
    y_over_sigma: float = 0.2,
    max_analogs: int = 3,
    exclude_negative: bool = True,
    variance_correction: str = "6.9",
    phi: pd.Series | np.ndarray | None = None,
    random_state: int | None = None,
) -> dict:
    """Удлинить ряд множественной регрессией по СП 33 п. 6.5 и 6.17.

    ``variance_correction="6.9"`` применяет детерминированную поправку
    систематически заниженной дисперсии. Вариант ``"6.10"`` добавляет
    нормально распределённую случайную составляющую; ``phi`` можно передать
    явно либо задать воспроизводимый ``random_state``.
    """
    if not analogs:
        raise ValueError("Не задан ни один ряд-аналог")
    if variance_correction not in {"6.9", "6.10"}:
        raise ValueError("variance_correction должен быть '6.9' или '6.10'")
    if phi is not None and random_state is not None:
        raise ValueError("Передавайте либо phi, либо random_state, но не оба")

    analog_names = list(analogs.keys())[:max_analogs]

    common = Q_calc.dropna().index
    for name in analog_names:
        common = common.intersection(analogs[name].dropna().index)

    n_common = len(common)
    if n_common < n_min:
        return {
            'success': False,
            'n_common': n_common,
            'n_min': n_min,
            'reason': f'Мало общих лет ({n_common} < {n_min})'
        }

    y = Q_calc.loc[common].values.astype(float)
    X = np.column_stack([
        np.ones(n_common),
        *[analogs[name].loc[common].values.astype(float) for name in analog_names]
    ])

    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    k0 = beta[0]
    k = beta[1:]

    y_pred = X @ beta
    residuals = y - y_pred

    ss_res = float(np.sum(residuals ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    R = float(np.sqrt(max(r2, 0.0)))

    sigma_ro = (1.0 - r2) / np.sqrt(n_common) if n_common > 0 else np.nan

    p = X.shape[1]
    dof = max(n_common - p, 1)
    sigma2 = ss_res / dof
    try:
        cov = np.linalg.inv(X.T @ X) * sigma2
    except np.linalg.LinAlgError:
        cov = np.linalg.pinv(X.T @ X) * sigma2
    sigma_k = np.sqrt(np.abs(np.diag(cov)))

    k_all = np.concatenate([[k0], k])
    ratio_k = k_all / sigma_k

    y_mean = float(np.mean(residuals))
    y_std = float(np.std(residuals, ddof=1)) if n_common > 1 else 0.0
    ratio_y = abs(y_mean) / y_std if y_std > 0 else np.nan

    checks = {
        'n_common_ok': n_common >= n_min,
        'R_ok': ro_cr <= R,
        'ro_over_sigma_ok': (R / sigma_ro) >= ro_over_sigma if sigma_ro > 0 else False,
        'k_over_sigma_ok': bool(np.all(ratio_k[1:] >= k_over_sigma)),
        'y_over_sigma_ok': ratio_y <= y_over_sigma,
    }

    extended = Q_calc.copy().astype(float)
    warnings = []
    missing_years = extended.index[extended.isna()]
    for name in analog_names:
        missing_years = missing_years.intersection(
            analogs[name].dropna().index,
            sort=False,
        )
    missing_years = missing_years.sort_values()

    if len(missing_years) > 0:
        x_missing = np.column_stack([
            np.ones(len(missing_years)),
            *[analogs[name].loc[missing_years].values.astype(float)
              for name in analog_names],
        ])
        raw_missing = x_missing @ beta
        observed_mean = float(np.mean(y))

        if variance_correction == "6.9":
            corrected_missing = apply_formula_6_9(
                raw_missing,
                mean_n=observed_mean,
                correlation=R,
            )
        else:
            if phi is None:
                normal_draws = np.random.default_rng(random_state).normal(
                    size=len(missing_years)
                )
            elif isinstance(phi, pd.Series):
                aligned_phi = phi.reindex(missing_years)
                if aligned_phi.isna().any():
                    raise ValueError("phi должен содержать значения для всех восстанавливаемых лет")
                normal_draws = aligned_phi.to_numpy(dtype=float)
            else:
                normal_draws = np.asarray(phi, dtype=float)

            if len(missing_years) < 30:
                warnings.append(
                    "Для формулы СП 33 п. 6.17 (6.10) рекомендуется "
                    "не менее 30 восстановленных значений"
                )
            corrected_missing = apply_formula_6_10(
                raw_missing,
                correlation=R,
                sigma=float(np.std(y, ddof=1)),
                phi=normal_draws,
            )

        for year, value in zip(missing_years, corrected_missing, strict=True):
            if exclude_negative and value < 0.0:
                extended.loc[year] = np.nan
            else:
                extended.loc[year] = value

    coeffs = {'k0': round(k0, 4)}
    sigma_coeffs = {'s_k0': round(float(sigma_k[0]), 4)}
    ratios = {'r_k0': round(float(ratio_k[0]), 2)}
    for i, name in enumerate(analog_names):
        coeffs[f'k{i + 1}'] = round(float(k[i]), 4)
        sigma_coeffs[f's_k{i + 1}'] = round(float(sigma_k[i + 1]), 4)
        ratios[f'r_k{i + 1}'] = round(float(ratio_k[i + 1]), 2)

    return {
        'success': True,
        'n_common': n_common,
        'n_min': n_min,
        'R': round(R, 4),
        'sigma_Ro': round(float(sigma_ro), 4),
        'R_over_sigmaRo': round(R / sigma_ro, 2) if sigma_ro > 0 else np.nan,
        'S': round(y_std, 4),
        'Y_mean': round(y_mean, 4),
        'Y_over_sigmaY': round(ratio_y, 3) if not np.isnan(ratio_y) else np.nan,
        'analogs': analog_names,
        'coeffs': coeffs,
        'sigma_coeffs': sigma_coeffs,
        'k_over_sigma': ratios,
        'criteria': checks,
        'all_criteria_ok': all(checks.values()),
        'extended_series': extended,
        'variance_correction': variance_correction,
        'variance_correction_clause': (
            f'СП 33-101-2003 п. 6.17, формула {variance_correction}'
        ),
        'warnings': warnings,
        'formula': f'Q = {coeffs["k0"]}' + ''.join(
            f' {"+" if k[i] >= 0 else "-"} {abs(k[i]):.4f}·{name}'
            for i, name in enumerate(analog_names)
        )
    }


# ============================================================
# ИНТЕГРАЛЬНАЯ / РАЗНОСТНО-ИНТЕГРАЛЬНАЯ КРИВАЯ (ГГИ)
# ============================================================
#
# Интегральная кривая: Σki (сумма модульных коэффициентов)
# Разностно-интегральная: Σ(ki - 1) / Cv
#
# ki = xi / x̄ — модульный коэффициент
#
# Форма кривой позволяет выявить:
# - Переломы = границы нестационарности
# - Экстремумы = границы периодов повышенных/пониженных значений


def compute_integral_curves(data: pd.Series) -> dict:
    """
    Вычисление интегральной и разностно-интегральной кривых.

    Аргументы:
        data — pd.Series с индексом=год, значения=Q

    Возвращает dict:
        years — годы
        modular_coefficients — ki = Q/Qср
        integral_curve — Σki (нарастающая сумма)
        diff_integral_curve — Σ(ki-1)/Cv
        mean — среднее значение
        cv — Cv
        breakpoints — список годов с переломами (экстремумы разностно-интегральной)
    """
    data = data.dropna()
    if len(data) < 4:
        return {
            'years': data.index.tolist(),
            'modular_coefficients': [],
            'integral_curve': [],
            'diff_integral_curve': [],
            'mean': 0, 'cv': 0, 'breakpoints': [],
        }

    values = data.values.astype(float)
    years = data.index.tolist()

    mean_val = np.mean(values)
    std_val = np.std(values, ddof=1)
    cv = std_val / mean_val if mean_val > 0 else 0

    # Модульные коэффициенты
    ki = values / mean_val if mean_val > 0 else np.ones_like(values)

    # Интегральная кривая: нарастающая сумма ki
    integral = np.cumsum(ki)

    # Разностно-интегральная кривая: нарастающая сумма (ki-1)/Cv
    if cv > 1e-12:
        diff_integral = np.cumsum((ki - 1) / cv)
    else:
        diff_integral = np.cumsum(ki - 1)

    # Поиск переломов (экстремумы разностно-интегральной кривой)
    breakpoints = []
    if len(diff_integral) >= 3:
        for i in range(1, len(diff_integral) - 1):
            if ((diff_integral[i] > diff_integral[i-1] and
                 diff_integral[i] > diff_integral[i+1]) or
                (diff_integral[i] < diff_integral[i-1] and
                 diff_integral[i] < diff_integral[i+1])):
                breakpoints.append(years[i])

    return {
        'years': years,
        'modular_coefficients': ki.tolist(),
        'integral_curve': integral.tolist(),
        'diff_integral_curve': diff_integral.tolist(),
        'mean': round(mean_val, 4),
        'cv': round(cv, 4),
        'breakpoints': breakpoints,
    }
