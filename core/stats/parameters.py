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


# Поправки на смещение по (5.6), (5.7) СП 33-101-2003.
#
# Источник: СП 33-101-2003, п. 5.6, таблица Б.1 приложения Б (обязательное),
# печатный экземпляр, стр. 74. Копия проверена тестами в
# tests/test_sp33_table_b1_bias_coefficients.py, разбор строк однозначен.
#
# Сетка таблицы: a-коэффициенты заданы для Cs/Cv ∈ {2, 3, 4} и r(1) ∈ {0, 0.3, 0.5};
# b-коэффициенты — только по r(1).
SP33_B1_A: dict[float, dict[float, tuple[float, ...]]] = {
    2.0: {
        0.0: (0.0, 0.19, 0.99, -0.88, 0.01, 1.54),
        0.3: (0.0, 0.22, 0.99, -0.41, 0.01, 1.51),
        0.5: (0.0, 0.18, 0.98, 0.41, 0.02, 1.47),
    },
    3.0: {
        0.0: (0.0, 0.69, 0.98, -4.34, 0.01, 6.78),
        0.3: (0.0, 1.15, 1.02, -7.53, -0.04, 12.38),
        0.5: (0.0, 1.75, 1.00, -11.79, -0.05, 21.13),
    },
    4.0: {
        0.0: (0.0, 1.36, 1.02, -9.68, -0.05, 15.55),
        0.3: (-0.02, 2.61, 1.13, -19.85, -0.22, 34.15),
        0.5: (-0.02, 3.47, 1.18, -29.71, -0.41, 58.08),
    },
}
SP33_B1_B: dict[float, tuple[float, ...]] = {
    0.0: (0.03, 2.00, 0.92, -5.09, 0.03, 8.10),
    0.3: (0.03, 1.77, 0.93, -3.45, 0.03, 8.03),
    0.5: (0.03, 1.63, 0.92, -0.97, 0.03, 7.94),
}


def _nearest_node(value: float, nodes) -> float:
    """Ближайший узел таблицы; при равенстве расстояний берётся нижний.

    Интерполяция по (5.6), (5.7) стандартом НЕ предписана, поэтому она не
    вводится: используется прямой выбор строки таблицы, а выбранные узлы
    возвращаются наружу, чтобы решение можно было проверить по первоисточнику.
    """
    return min(nodes, key=lambda node: (abs(value - node), node))


def sp33_bias_correction_56_57(
    chat_v: float,
    chat_s: float,
    n: int,
    lag1_autocorrelation: float,
) -> dict:
    """Поправки на смещение по формулам (5.6) и (5.7) СП 33-101-2003.

    Формулы стандарта:

        (5.6)  Cv = (a1 + a2/n) + (a3 + a4/n)·Ĉv + (a5 + a6/n)·Ĉv²
        (5.7)  Cs = (b1 + b2/n) + (b3 + b4/n)·Ĉs + (b5 + b6/n)·Ĉs²

    Коэффициенты берутся из таблицы Б.1 по узлам Cs/Cv и r(1). Отношение
    Cs/Cv считается по смещённым оценкам (5.8) и (5.9) и используется один
    раз, без итераций: стандарт итерацию не оговаривает.

    Returns:
        Словарь со скорректированными Cv и Cs и выбранными узлами таблицы.
    """
    if n < 3:
        raise ValueError("Для поправок по (5.6)-(5.7) нужно минимум 3 наблюдения")
    if chat_v <= 0.0:
        raise ValueError("Смещённая оценка Ĉv должна быть положительной")

    cs_cv = chat_s / chat_v
    ratio_node = _nearest_node(cs_cv, SP33_B1_A)
    r1 = float(np.clip(lag1_autocorrelation, -0.99, 0.99))
    r1_node = _nearest_node(r1, SP33_B1_B)

    a = SP33_B1_A[ratio_node][r1_node]
    b = SP33_B1_B[r1_node]

    cv = ((a[0] + a[1] / n)
          + (a[2] + a[3] / n) * chat_v
          + (a[4] + a[5] / n) * chat_v**2)
    cs = ((b[0] + b[1] / n)
          + (b[2] + b[3] / n) * chat_s
          + (b[4] + b[5] / n) * chat_s**2)

    return {
        "cv": float(cv),
        "cs": float(cs),
        "table_ratio_node": ratio_node,
        "table_r1_node": r1_node,
        "cs_cv": float(cs_cv),
    }


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

    # === Поправки на смещение (5.6), (5.7) ===
    # Поправки РЕАЛИЗОВАНЫ 2026-09-28 по таблице Б.1 печатного экземпляра.
    # До этого ключи corrected_cv/corrected_cs были тождественны cv/cs: поправок
    # не было никогда, а имена обещали, что были. Исторически сюда применялся
    # множитель sqrt((1+r1)/(1-r1)) — к Cv и Cs, что математически неверно:
    # по (5.26)-(5.27) этот множитель относится к стандартной ошибке среднего,
    # а не к коэффициентам, и он реализован в relative_mean_error_percent.
    #
    # СП 33 п. 5.6 разрешает отказ от поправок ЛИШЬ при Cv < 0,6 и Cs < 1,0:
    #    «При Cv < 0,6 и Cs < 1,0 коэффициенты вариации и асимметрии допускается
    #    определять по формулам (5.8) и (5.9) без введения поправок».
    # То есть отказ — исключение с проверяемым условием, а не режим по
    # умолчанию. Раньше условие не проверялось вовсе: на реке с Cv = 0,9
    # код молча отдавал неверный Cv под именем corrected_cv.
    # === Поправки на смещение (5.6), (5.7) ===
    #
    # Смещённые оценки Ĉv и Ĉs, вычисленные выше, — это в точности (5.8) и
    # (5.9) СП 33: коду они достаются из std(ddof=1)/mean и
    # scipy.stats.skew(bias=False), сверено численно.
    #
    # СП 33 п. 5.6 разрешает отказ от поправок ЛИШЬ при Cv < 0,6 и Cs < 1,0:
    #    «При Cv < 0,6 и Cs < 1,0 коэффициенты вариации и асимметрии допускается
    #    определять по формулам (5.8) и (5.9) без введения поправок».
    # Отказ — исключение с проверяемым условием, а не режим по умолчанию.
    #
    # ОТДЕЛЬНО вырожденный случай. Для ряда из одинаковых значений Cv = 0, а
    # scipy.stats.skew на нём даёт NaN (деление на нулевую дисперсию). Сравнение
    # NaN < 1.0 ложно, поэтому прежняя проверка считала такой ряд требующим
    # поправок и уходила в (5.6) с Ĉv = 0 — к исключению. Поправка при Ĉv = 0
    # неприменима в принципе: отношение Cs/Cv не определено, и вместо 0/0
    # получается деление на ноль в самой формуле.
    degenerate = not (np.isfinite(cs) and cv > 0.0)
    if degenerate:
        corrections_exempt = True
        correction_note = (
            "поправки (5.6)-(5.7) неприменимы: Cv = 0 либо Cs не определена "
            "(ряд из одинаковых значений), отношение Cs/Cv не существует"
        )
    else:
        corrections_exempt = bool(cv < 0.6 and cs < 1.0)
        correction_note = (
            "п. 5.6: Cv < 0,6 и Cs < 1,0 — поправки не вводятся по прямому "
            "допущению стандарта"
        )
    if corrections_exempt:
        corrected_cv = cv
        corrected_cs = cs
        bias_corrections_applied = False
        table_ratio_node = None
        table_r1_node = None
    else:
        correction = sp33_bias_correction_56_57(cv, cs, n, r1)
        corrected_cv = correction["cv"]
        corrected_cs = correction["cs"]
        bias_corrections_applied = True
        table_ratio_node = correction["table_ratio_node"]
        table_r1_node = correction["table_r1_node"]
        correction_note = (
            "п. 5.6, (5.6) и (5.7) по таблице Б.1; выбранные узлы указаны "
            "в table_ratio_node и table_r1_node, интерполяция не применяется"
        )
        if show_warnings:
            warnings.warn(
                "СП 33-101-2003 п. 5.6: Cv >= 0,6 или Cs >= 1,0, поэтому поправки "
                f"на смещение обязательны и применены (Cv={cv:.3f} -> "
                f"{corrected_cv:.3f}, Cs={cs:.3f} -> {corrected_cs:.3f}). "
                f"Коэффициенты взяты из табл. Б.1 для Cs/Cv = {table_ratio_node} "
                f"и r(1) = {table_r1_node} — ближайшие узлы, интерполяция "
                "стандартом не предписана.",
                UserWarning,
                stacklevel=2,
            )
    corrections_required = not corrections_exempt

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
        # Отношение Cs/Cv — нормативный параметр по п. 5.4 и (5.7);
        # раньше в выводе его не было вовсе, только сырая асимметрия.
        'cs_cv': round(float(cs / cv), 4) if cv else float('nan'),
        'corrected_cv': round(corrected_cv, 4),
        'corrected_cs': round(corrected_cs, 4),
        # Поправки на смещение по (5.6)-(5.9) НЕ применяются. corrected_*
        # равны cv/cs тождественно; названия сохранены ради шести
        # потребителей (frequency, gts_integration, confidence_bands и др.).
        'bias_corrections_applied': bias_corrections_applied,
        'corrections_required': corrections_required,
        'correction_note': correction_note,
        'table_ratio_node': table_ratio_node,
        'table_r1_node': table_r1_node,
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
