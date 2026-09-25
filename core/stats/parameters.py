"""
core/stats/parameters.py
Расчёт статистических параметров с поправками на автокорреляцию
(по рекомендациям ГГИ / СП 33-101-2003)
"""

import warnings

import numpy as np
from scipy import stats


DEFAULT_RELATIVE_RMS_ERROR_LIMIT = 0.10
MAX_MIN_RELATIVE_RMS_ERROR_LIMIT = 0.20


def validate_series_length(
    n: int,
    min_probability: float | None = None,
    relative_rms_error: float | None = None,
    error_limit: float = DEFAULT_RELATIVE_RMS_ERROR_LIMIT,
) -> list[str]:
    """Проверить достаточность ряда по критерию СП 33-101-2003 п. 5.1.

    ``min_probability`` сохранён для совместимости с прежним API и больше не
    определяет фиксированное число лет наблюдений.
    """
    if relative_rms_error is None:
        return [
            f"⚠️ СП 33-101-2003 п. 5.1: для ряда n={n} необходимо проверить "
            f"относительную среднеквадратическую погрешность"
        ]

    if relative_rms_error > error_limit:
        return [
            f"⚠️ СП 33-101-2003 п. 5.1: относительная среднеквадратическая "
            f"погрешность {relative_rms_error * 100:.1f}% превышает предел "
            f"{error_limit * 100:.0f}% для ряда n={n}"
        ]

    return []


def relative_mean_error_percent(
    cv: float,
    n: int,
    lag1_autocorrelation: float,
) -> float:
    """Рассчитать погрешность среднего по формулам СП 33 п. 5.26–5.27.

    Для ``r < 0.5`` применяется формула 5.26, для ``r >= 0.5`` — более
    точная формула 5.27. Результат возвращается в процентах.
    """
    if n < 2:
        raise ValueError("Для погрешности среднего нужно минимум 2 наблюдения")
    if not np.isfinite(cv) or cv < 0.0:
        raise ValueError("Cv должен быть конечным и неотрицательным")
    if cv == 0.0:
        return 0.0

    r = float(lag1_autocorrelation)
    if not np.isfinite(r) or abs(r) >= 1.0:
        return float("inf")

    if r < 0.5:
        factor = np.sqrt((1.0 + r) / (1.0 - r))
    else:
        correction = sum(1.0 - r**power for power in range(1, n))
        numerator = 1.0 + 2.0 * r / (n * (1.0 - r)) * correction
        denominator = 1.0 - 2.0 * r / (
            n * (n - 1) * (1.0 - r)
        ) * correction
        if denominator <= 0.0:
            return float("inf")
        factor = np.sqrt(numerator / denominator)

    return float(cv / np.sqrt(n) * factor * 100.0)


def calculate_statistical_parameters(
    data: np.ndarray,
    apply_autocorr_correction: bool = True,
    min_probability: float | None = None,
    show_warnings: bool = True
) -> dict:
    """
    Расчёт основных статистических параметров ряда.

    Параметры:
        data: массив значений
        apply_autocorr_correction: не используется (оставлен для совместимости; эталон
            Cv не корректирует)
        min_probability: сохранённый параметр совместимости; фиксированный минимум лет не задаёт
        show_warnings: выводить ли предупреждения о длине ряда
    """
    data = np.asarray(data)
    data = data[~np.isnan(data)]

    if len(data) < 3:
        raise ValueError("Для расчёта статистик нужно минимум 3 значения")

    n = len(data)
    mean = np.mean(data)
    std = np.std(data, ddof=1)
    cv = std / mean if mean != 0 else 0.0
    cs = stats.skew(data, bias=False)

    r1 = np.corrcoef(data[:-1], data[1:])[0, 1]
    mean_error_percent = relative_mean_error_percent(cv, n, r1)

    length_warnings = []
    if show_warnings:
        length_warnings = validate_series_length(
            n,
            min_probability,
            relative_rms_error=mean_error_percent / 100.0,
            error_limit=DEFAULT_RELATIVE_RMS_ERROR_LIMIT,
        )
        for warning in length_warnings:
            warnings.warn(warning, UserWarning, stacklevel=2)

    # === Поправки ===
    # СП 33-101-2003: поправка на автокорреляцию применяется к
    # стандартной ошибке параметров, НЕ к самим коэффициентам.
    # Убираем некорректный множитель на Cv/Cs.
    # Сохраняем r1 для анализа, но НЕ применяем autocorr_factor к cv/cs.
    corrected_cv = cv
    corrected_cs = cs

    # Примечание: ранее использовался autocorr_factor = sqrt((1+r1)/(1-r1))
    # для корректировки Cv/Cs — это было математически некорректно.
    # Правильный подход — корректировка SE (standard error) параметров.

    # Статистики для Крицкого-Менкеля
    if std == 0:
        deviations = np.zeros_like(data)
    else:
        deviations = (data - mean) / std
    lambda2 = np.mean(deviations ** 2)
    lambda3 = np.mean(deviations ** 3)

    return {
        'mean': round(mean, 4),
        'std': round(std, 4),
        'cv': round(cv, 4),
        'cs': round(cs, 4),
        'corrected_cv': round(corrected_cv, 4),
        'corrected_cs': round(corrected_cs, 4),
        'r1': round(r1, 4),
        'lambda2': round(lambda2, 4),
        'lambda3': round(lambda3, 4),
        'n': n,
        'autocorr_correction_applied': apply_autocorr_correction,
        'autocorr_factor_note': 'autocorr correction applied to SE (not Cv/Cs) per SP 33-101-2003',
        'length_warnings': length_warnings
    }


def compute_hydro_stats_with_errors(Q):
    """
    Расчёт статистических характеристик с относительными погрешностями
    (по методике РГГМУ, Сикан А.В. и др., 2021).

    Возвращает:
        mean, Cv, Cs, eps_mean_%, eps_Cv_%, eps_Cs_%, n
    """
    import numpy as np
    from scipy import stats as sp_stats

    Q = np.asarray(Q, dtype=float)
    Q = Q[~np.isnan(Q)]
    n = len(Q)

    if n < 3:
        return {
            'mean': np.nan, 'Cv': np.nan, 'Cs': np.nan,
            'eps_mean_%': np.nan, 'eps_Cv_%': np.nan, 'eps_Cs_%': np.nan, 'n': n
        }

    m = np.mean(Q)
    S = np.std(Q, ddof=1)
    Cv = S / m if m != 0 else 0.0
    Cs = sp_stats.skew(Q, bias=False)

    # Относительные погрешности по формулам практикума РГГМУ
    eps_Q = (Cv / np.sqrt(n)) * 100
    eps_Cv = (1 / (n + 4 * Cv**2)) * np.sqrt(n * (1 + Cv**2) / 2) * 100

    if Cs != 0 and not np.isnan(Cs):
        eps_Cs = (1 / abs(Cs)) * np.sqrt((6 / n) * (1 + 6*Cv**2 + 5*Cv**4)) * 100
    else:
        eps_Cs = np.nan

    return {
        'mean': round(m, 2),
        'Cv': round(Cv, 4),
        'Cs': round(Cs, 4),
        'eps_mean_%': round(eps_Q, 1),
        'eps_Cv_%': round(eps_Cv, 1),
        'eps_Cs_%': round(eps_Cs, 1) if not np.isnan(eps_Cs) else '—',
        'n': n
    }
