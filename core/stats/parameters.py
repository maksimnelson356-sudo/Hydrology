"""
core/stats/parameters.py
Расчёт статистических параметров с поправками на автокорреляцию
(по рекомендациям ГГИ / СП 33-11-2003)
"""

import numpy as np
from scipy import stats
import warnings
from typing import Dict, Optional, List


def validate_series_length(n: int, min_probability: Optional[float] = None) -> List[str]:
    """
    Проверка длины ряда наблюдений согласно СП 482.1325800.2020 п. 8.2.

    Параметры:
        n: длина ряда наблюдений (лет)
        min_probability: минимальная обеспеченность для расчета (например, 0.01 для 1%)

    Возвращает:
        Список предупреждений (пустой если все в порядке)
    """
    warnings_list = []

    # СП 482 п. 8.2: Минимальная длина ряда для редких событий
    if min_probability is not None and min_probability <= 0.01 and n < 50:
        warnings_list.append(
            f"⚠️ СП 482 п. 8.2: Для расчета характеристик обеспеченностью P ≤ 1% "
            f"требуется ряд наблюдений ≥ 50 лет (текущая длина: {n} лет)"
        )

    # СП 482 п. 8.2: Общая минимальная длина для рек с снеговым питанием
    if n < 25:
        warnings_list.append(
            f"⚠️ СП 482 п. 8.2: Минимальная длина ряда для рек с преимущественно "
            f"снеговым питанием составляет 25 лет (текущая длина: {n} лет). "
            f"Для рек с дождевым питанием - 30 лет."
        )

    # СП 33-101-2003: Рекомендация для надежных оценок
    if n < 30:
        warnings_list.append(
            f"ℹ️ СП 33-101-2003: Для надежных статистических оценок рекомендуется "
            f"ряд наблюдений ≥ 30 лет (текущая длина: {n} лет)"
        )

    # Критически короткий ряд
    if n < 10:
        warnings_list.append(
            f"❌ КРИТИЧНО: Ряд слишком короткий ({n} лет) для достоверных "
            f"статистических выводов. Результаты могут быть ненадежными."
        )

    return warnings_list


def calculate_statistical_parameters(
    data: np.ndarray,
    apply_autocorr_correction: bool = True,
    min_probability: Optional[float] = None,
    show_warnings: bool = True
) -> Dict:
    """
    Расчёт основных статистических параметров ряда.

    Параметры:
        data: массив значений
        apply_autocorr_correction: не используется (оставлен для совместимости; эталон
            Cv не корректирует)
        min_probability: минимальная обеспеченность для проверки длины ряда (например, 0.01)
        show_warnings: выводить ли предупреждения о длине ряда
    """
    data = np.asarray(data)
    data = data[~np.isnan(data)]

    if len(data) < 3:
        raise ValueError("Для расчёта статистик нужно минимум 3 значения")

    n = len(data)

    # Проверка длины ряда согласно СП 482
    length_warnings = []
    if show_warnings:
        length_warnings = validate_series_length(n, min_probability)
        for warning in length_warnings:
            warnings.warn(warning, UserWarning)
    mean = np.mean(data)
    std = np.std(data, ddof=1)

    cv = std / mean if mean != 0 else 0.0
    cs = stats.skew(data, bias=False)

    # Автокорреляция 1-го порядка
    if n > 2:
        r1 = np.corrcoef(data[:-1], data[1:])[0, 1]
    else:
        r1 = 0.0

    # === Поправки ===
    # Эталон (HydroStatCalc ГГИ, сверено по «Варианты подбора.txt»): Cv_расч ≡ Cv_выб,
    # поправка на автокорреляцию к Cv НЕ применяется (9215: 0.11→0.11; 74425: 1.22→1.22).
    # Cs_расч в эталоне получается подбором кривой, а не явной формулой — открытый вопрос.
    # (Ранее здесь стояла поправка √((1+r1)/(1−r1)) к Cv и Cs — удалена как несоответствующая.)
    corrected_cv = cv
    corrected_cs = cs

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
        'autocorr_correction_applied': False,
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