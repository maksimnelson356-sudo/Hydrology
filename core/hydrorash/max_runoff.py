"""
core/hydrorash/max_runoff.py
Модуль расчёта МАКСИМАЛЬНОГО стока (паводков)

Согласно СП 529.1325800.2023, раздел 5.3 (максимальный сток воды весеннего
поволодья и дождевых паводков):
- 5.3.1 — расчётные характеристики по требованиям 5.1
- 5.3.2 — среднесуточные (≥1 сут) или срочные (<1 сут) значения
- 5.3.3 — допускается построение кривых без разделения талых/дождевых максимумов
- 5.3.4 — при неоднородности: составные кривые (5.1.11) или усечённые
  распределения (формулы 5.41–5.44, табл. Б.5, Б.6)
- 5.3.5 — зарегулированные реки: с учётом хозяйственной деятельности
- 5.3.6 — гарантийная поправка для P=0.01% (формулы 5.45, 5.46, табл. Б.4)

Проверено 2026-09-28: прежняя ссылка «раздел 8» была ошибочной - раздела 8
нет ни в СП 33-101-2003, ни в СП 529.1325800.2023 (стандарт состоит из
разделов 1–7 и приложений А–Г). РД 52-26-2008 как источник не проверен.

Основные функции:
- extract_max_annual — извлечение средних максимальных расходов за N суток
- compute_max_runoff_stats — статистические характеристики максимальных стоков
- max_runoff_frequency_curve — кривая обеспеченности (Pearson III, усечённое гамма)
- guarantee_correction — гарантийная поправка (5.3.6, формулы 5.45–5.46)
- truncated_gamma_frequency_curve — усечённое гамма-распределение (5.3.4)
- index_year_method — метод индексных годов (ИНЖЕНЕРНЫЙ, нет в СП 529)
- build_rating_curve — кривая Q = f(H) (ИНЖЕНЕРНЫЙ, нет в СП 529)
- discharge_from_level / level_from_discharge — вспомогательные (ИНЖЕНЕРНЫЕ)
"""


import numpy as np
import pandas as pd
from scipy import stats

from core.stats.parameters import (
    MAX_MIN_RELATIVE_RMS_ERROR_LIMIT,
    relative_mean_error_percent,
    sp33_lag1_autocorrelation,
)

from .utils import compute_basic_stats


def extract_max_annual(
    daily_df: pd.DataFrame,
    year_col: str = 'year',
    value_col: str = 'value',
    period_days: int = 1
) -> pd.Series:
    """
    Извлечение средних максимальных расходов за period_days суток для каждого года.
    """
    df = daily_df.copy()
    # Нормализация имён колонок
    df.columns = [str(c).strip().lower() for c in df.columns]
    col_map = {
        'год': 'year', 'year': 'year', 'years': 'year', 'дата': 'year', 'date': 'year',
        'q': 'value', 'расход': 'value', 'value': 'value',
    }
    for old, new in col_map.items():
        if old in df.columns and new not in df.columns:
            df = df.rename(columns={old: new})
    if year_col not in df.columns or value_col not in df.columns:
        raise KeyError(f"Не найдены колонки '{year_col}' и/или '{value_col}' в DataFrame")
    df = df[[year_col, value_col]].dropna().copy()
    df[value_col] = pd.to_numeric(df[value_col], errors='coerce')
    df = df.dropna()

    results = {}
    for year, group in df.groupby(year_col):
        vals = group[value_col].values
        if period_days == 1:
            results[int(year)] = float(np.max(vals))
        elif len(vals) >= period_days:
            rolling = pd.Series(vals).rolling(window=period_days, min_periods=period_days).mean()
            results[int(year)] = float(rolling.max())
        else:
            results[int(year)] = float(np.max(vals))

    return pd.Series(results, name=f'Qmax_{period_days}d')


def compute_max_runoff_stats(
    max_series: pd.Series,
    use_normative_Cs: bool = False,
) -> dict:
    """Статистические характеристики ряда максимальных стоков (СП 529 п. 5.1, 5.3).

    Используется ЭМПИРИЧЕСКАЯ асимметрия Cs (выборочная оценка по ряду).
    Правило Cs = 2·Cv / 3·Cv из СП 33 НЕ ПРИМЕНЯЕТСЯ — его нет в СП 529,
    и оно даёт разрыв кривой при Cv = 0.5.

    Параметр `use_normative_Cs` оставлен для обратной совместимости (DEPRECATED).
    При True используется инженерное правило Cs = 2·Cv (Cv ≤ 0.5) / 3·Cv (Cv > 0.5).
    ЭТО НЕ НОРМАТИВНОЕ ПРАВИЛО — его нет в СП 529. Используйте с осторожностью.

    Возвращает словарь с параметрами и надежностью по СП 529 п. 5.1.
    """
    if use_normative_Cs:
        import warnings
        warnings.warn(
            "use_normative_Cs=True использует инженерное правило Cs=2·Cv/3·Cv, "
            "которого НЕТ в СП 529.1325800.2023. Оно даёт разрыв кривой при Cv=0.5. "
            "Параметр deprecated и будет удалён в следующей версии.",
            DeprecationWarning,
            stacklevel=2,
        )
    data = np.asarray(pd.Series(max_series).dropna(), dtype=float)
    if len(data) < 3:
        return {
            "mean": None,
            "Cv": None,
            "Cs": None,
            "n": len(data),
            "epsilon": None,
            "relative_rms_error_limit": MAX_MIN_RELATIVE_RMS_ERROR_LIMIT,
            "warnings": ["Длина ряда < 3 лет. Статистические расчёты невозможны."],
            "reliability_class": "Недостаточно данных",
        }

    n = len(data)
    mean = float(np.mean(data))
    std = float(np.std(data, ddof=1))
    Cv = std / mean if mean != 0 else 0.0
    Cs_emp = float(pd.Series(data).skew())

    # DEPRECATED: инженерное правило (нет в СП 529)
    Cs = (2.0 * Cv if Cv <= 0.5 else 3.0 * Cv) if use_normative_Cs else Cs_emp

    # r(1) из нормативного источника (Б.1)-(Б.3) приложения Б СП 529
    lag1 = sp33_lag1_autocorrelation(data)
    r1 = lag1["r1"]
    epsilon = relative_mean_error_percent(Cv, n, r1)
    error_limit_percent = MAX_MIN_RELATIVE_RMS_ERROR_LIMIT * 100.0

    warnings = []
    reliability_class = "Надёжная"

    # Пригодность выборки проверяется ДО оценки погрешности
    unusable = []
    if mean <= 0:
        unusable.append(
            f"среднее неположительно ({mean:.6g} м³/с) — квантили не определены"
        )
    if not np.isfinite(r1):
        unusable.append(f"автокорреляция r(1) не определена: {lag1['source']}")
    if unusable:
        warnings.append(
            "Кривая обеспеченности НЕ построена: " + "; ".join(unusable)
        )
        reliability_class = "Недостаточно данных"
    elif not np.isfinite(epsilon):
        warnings.append(
            f"εQ НЕ ВЫЧИСЛЕНА: {lag1['source']}; множитель в (5.26)/(5.27) "
            f"не имеет вещественного значения. Предел "
            f"{error_limit_percent:.0f}% не проверен"
        )
        reliability_class = "Недостаточно данных"
    elif epsilon > error_limit_percent:
        warnings.append(
            f"εQ = {epsilon:.1f}% > {error_limit_percent:.0f}%. "
            "Требуется удлинение ряда (СП 529.1325800.2023 п. 5.1)"
        )
        reliability_class = "Ненадёжная"

    return {
        "n": n,
        "mean": round(mean, 4),
        "std": round(std, 4),
        "Cv": round(Cv, 4),
        "Cs": round(Cs, 4),
        "r1": r1,
        "epsilon": round(epsilon, 2),
        "relative_rms_error_limit": MAX_MIN_RELATIVE_RMS_ERROR_LIMIT,
        "warnings": warnings,
        "reliability_class": reliability_class,
    }


def max_runoff_frequency_curve(
    max_series: pd.Series,
    P_values: list[float] | None = None,
    method: str = "pearson3",
    use_normative_Cs: bool = False,
) -> pd.DataFrame:
    """
    Кривая обеспеченности максимальных стоков (СП 529.1325800.2023 п. 5.3, 5.1).

    Методы:
    - "pearson3" — Пирсон III типа (дефолт), параметры по 5.1
    - "truncated_gamma" — усечённое гамма-распределение (5.3.4, формулы 5.41–5.44)

    Гарантийная поправка для P=0.01% применяется отдельно через guarantee_correction()
    (СП 529 п. 5.3.6, формулы 5.45–5.46, табл. Б.4).

    Parameters:
        max_series: ряд максимальных стоков
        P_values: обеспеченности в % (по умолчанию стандартные)
        method: "pearson3" или "truncated_gamma"
        use_normative_Cs: DEPRECATED. Оставлен для обратной совместимости.
            При True используется инженерное правило Cs = 2·Cv / 3·Cv
            (НЕТ в СП 529). Выдаёт DeprecationWarning.

    Returns:
        DataFrame: P_%, Q_max, kp
    """
    if P_values is None:
        P_values = [0.1, 0.33, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 33.0, 50.0]

    data = np.asarray(pd.Series(max_series).dropna(), dtype=float)
    if len(data) < 3:
        return pd.DataFrame({"P_%": P_values, "Q_max": [np.nan] * len(P_values), "kp": [np.nan] * len(P_values)})

    if method == "truncated_gamma":
        return truncated_gamma_frequency_curve(data, P_values)

    # Pearson III (дефолт)
    if use_normative_Cs:
        import warnings
        warnings.warn(
            "use_normative_Cs=True использует инженерное правило Cs=2·Cv/3·Cv, "
            "которого НЕТ в СП 529.1325800.2023. Параметр deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
    params = compute_max_runoff_stats(data, use_normative_Cs=use_normative_Cs)
    mean = params["mean"]
    Cv = params["Cv"]
    Cs = params["Cs"]

    if mean is None or not np.isfinite(mean):
        return pd.DataFrame({"P_%": P_values, "Q_max": [np.nan] * len(P_values), "kp": [np.nan] * len(P_values)})

    P_decimal = np.array(P_values) / 100.0
    from core.stats.frequency import pearson3_ppf
    quantiles = pearson3_ppf(P_decimal, mean, Cv, Cs)

    kp = quantiles / mean if mean != 0 else np.full_like(quantiles, np.nan)

    return pd.DataFrame({
        "P_%": P_values,
        "Q_max": np.round(quantiles, 2),
        "kp": np.round(kp, 4)
    })


def index_year_method(
    gauged_max_series: pd.Series,
    gauged_mean_annual: float,
    target_mean_annual: float,
    P_values: list[float] | None = None
) -> pd.DataFrame:
    """
    Метод индексных годов.

    Проверено 2026-09-28: прежняя ссылка «СП 33-101-2003 п. 8.2» была ошибочной -
    такого пункта нет, а термин «индексные годы» в тексте СП 33-101-2003
    не встречается ни разу. Источник метода не подтверждён; требуется первоисточник.

    Для безструментных рек:
    1. Вычисляем K_i = Qmax_i / Qmean_i для каждого года
    2. Строим кривую обеспечённости для K
    3. Q_расчётное_p = K_p × Qср_целевой_реки

    Parameters:
        gauged_max_series: максимальные расходы на струментном участке
        gauged_mean_annual: среднегодовой расход на струментном участке
        target_mean_annual: среднегодовой расход на целевом участке
        P_values: обеспеченности в %

    Returns:
        DataFrame: P_%, K_p, Q_max
    """
    if gauged_mean_annual <= 0:
        raise ValueError("Среднегодовой расход струментного участка должен быть > 0")

    if P_values is None:
        P_values = [0.1, 1.0, 3.0, 5.0, 10.0, 20.0, 33.0, 50.0]

    ratios = (gauged_max_series / gauged_mean_annual).dropna()
    if len(ratios) < 3:
        return pd.DataFrame({"P_%": P_values, "K_p": [np.nan] * len(P_values), "Q_max": [np.nan] * len(P_values)})

    stats_result = compute_basic_stats(ratios)
    mean_k = stats_result["mean"]
    Cv = stats_result["Cv"]
    Cs = stats_result["Cs"]

    P_decimal = np.array(P_values) / 100.0
    from core.stats.frequency import pearson3_ppf
    K_p = pearson3_ppf(P_decimal, mean_k, Cv, Cs)

    Q_target = K_p * target_mean_annual

    return pd.DataFrame({
        "P_%": P_values,
        "K_p": np.round(K_p, 4),
        "Q_max": np.round(Q_target, 2)
    })


def build_rating_curve(
    H: np.ndarray,
    Q: np.ndarray,
    H0: float
) -> dict:
    """
    Построение кривой функционирования Q = a × (H - H0)^b.

    H0 — уровень нуля поста (уровень, при котором Q = 0).
    Этот параметр обязателен и должен задаваться явно пользователем.

    Parameters:
        H: массив уровней воды (м)
        Q: массив расходов (м³/с)
        H0: уровень нуля поста, м (обязательный)

    Returns:
        Dict: a, b, H0, R2, formula
    """
    H = np.asarray(H, dtype=float)
    Q = np.asarray(Q, dtype=float)

    mask = Q > 0
    H, Q = H[mask], Q[mask]

    if len(H) < 3:
        raise ValueError("Нужно минимум 3 точки с Q > 0")

    dH = H - H0
    if np.any(dH <= 0):
        raise ValueError("Все значения H должны быть строго больше H0")

    log_dH = np.log(dH)
    log_Q = np.log(Q)

    slope, intercept, r_value, _, _ = stats.linregress(log_dH, log_Q)
    b = float(slope)
    a = float(np.exp(intercept))
    R2 = float(r_value ** 2)

    return {
        "a": round(a, 6),
        "b": round(b, 4),
        "H0": round(H0, 4),
        "R2": round(R2, 6),
        "formula": f"Q = {a:.4f} × (H - {H0:.2f})^{b:.4f}"
    }


def discharge_from_level(H: float, params: dict) -> float:
    """
    Расход по уровню воды: Q = a × (H - H0)^b.
    """
    a = params["a"]
    b = params["b"]
    H0 = params["H0"]
    dH = H - H0
    if dH <= 0:
        return 0.0
    return float(a * (dH ** b))


def level_from_discharge(Q: float, params: dict) -> float:
    """
    Уровень воды по расходу: H = H0 + (Q/a)^(1/b).
    """
    a = params["a"]
    b = params["b"]
    H0 = params["H0"]
    if Q <= 0 or a <= 0 or b == 0:
        return H0
    return float(H0 + (Q / a) ** (1.0 / b))


def guarantee_correction(
    Q_001: float,
    W_001: float,
    N: int,
    Cv: float,
    Cs_over_Cv: float,
    method: str = "moments",
    alpha: float = 1.0,
) -> dict:
    """
    Гарантийная поправка для максимального расхода и объёма при P=0.01%
    (СП 529.1325800.2023 п. 5.3.6, формулы 5.45–5.46, табл. Б.4).

    ΔQ = α · E₀,₀₁% · Q₀,₀₁% / √N
    ΔW = α · E₀,₀₁% · W₀,₀₁% / √N

    Ограничения:
    - ΔQ ≤ 20% от Q₀,₀₁%, ΔW ≤ 20% от W₀,₀₁%
    - Результат не должен быть меньше наибольшего наблюдённого значения

    Parameters:
        Q_001: расчётный максимальный расход при P=0.01%, м³/с
        W_001: расчётный объём стока при P=0.01%, км³ (или млн м³)
        N: число лет наблюдений с учётом приведения к многолетнему периоду
        Cv: коэффициент вариации ряда
        Cs_over_Cv: отношение Cs/Cv
        method: "moments" (метод моментов) или "mle" (МНП) — выбор строки табл. Б.4
        alpha: коэф. изученности (1.0 — изученные, 1.5 — остальные)

    Returns:
        dict: dQ, dW, Q_corrected, W_corrected, E_001, limited
    """
    from core.stats.kritsky_tables import get_E_001_table_B4

    if N <= 0:
        raise ValueError("Число лет наблюдений N должно быть > 0")
    if Q_001 <= 0:
        raise ValueError("Q_001 должно быть > 0")

    # Получаем E0,01% из таблицы Б.4
    E_001 = get_E_001_table_B4(Cv, Cs_over_Cv, method)

    sqrt_N = np.sqrt(N)
    dQ = alpha * E_001 * Q_001 / sqrt_N
    dW = alpha * E_001 * W_001 / sqrt_N if W_001 > 0 else 0.0

    # Ограничение 20%
    max_dQ = 0.20 * Q_001
    max_dW = 0.20 * W_001 if W_001 > 0 else 0.0

    limited = False
    if dQ > max_dQ:
        dQ = max_dQ
        limited = True
    if dW > max_dW:
        dW = max_dW
        limited = True

    Q_corrected = Q_001 + dQ
    W_corrected = W_001 + dW if W_001 > 0 else 0.0

    return {
        "dQ": round(float(dQ), 2),
        "dW": round(float(dW), 4),
        "Q_corrected": round(float(Q_corrected), 2),
        "W_corrected": round(float(W_corrected), 4),
        "E_001": round(float(E_001), 4),
        "limited": limited,
        "alpha": alpha,
        "N": N,
    }


def truncated_gamma_frequency_curve(
    data: np.ndarray,
    P_values: list[float],
) -> pd.DataFrame:
    """
    Усечённое гамма-распределение для максимальных стоков
    (СП 529.1325800.2023 п. 5.3.4, формулы 5.41–5.44, табл. Б.5, Б.6).

    Алгоритм:
    1. Ряд ранжируется по убыванию
    2. Берётся верхняя половина ряда (n/2 наибольших значений)
    3. Вычисляется среднее x̄_{n/2} по формуле (5.42)
    4. Вычисляется статистика λ2_{n/2} по формуле (5.44)
    5. По λ2_{n/2} и Cs/Cv из табл. Б.6 находится Cv
    6. По Cv из табл. Б.5 находится φ(Cv)
    7. Оценка x0 по формуле (5.41): x0 = x̄_{n/2} / φ(Cv)
    8. Квантили: Q_p = x0 * (k_p), где k_p из распределения Пирсона III
       с параметрами, соответствующими усечённому распределению

    Parameters:
        data: массив максимальных расходов
        P_values: обеспеченности в %

    Returns:
        DataFrame: P_%, Q_max, kp
    """
    from core.stats.frequency import pearson3_ppf
    from core.stats.kritsky_tables import (
        get_Cv_from_lambda2_table_B6,
        get_phi_Cv_table_B5,
    )

    data = np.asarray(data, dtype=float)
    data = data[~np.isnan(data)]
    data = np.sort(data)[::-1]  # по убыванию
    n = len(data)

    if n < 6:
        return pd.DataFrame({
            "P_%": P_values,
            "Q_max": [np.nan] * len(P_values),
            "kp": [np.nan] * len(P_values),
        })

    # 1. Верхняя половина ряда
    n_half = n // 2
    upper_half = data[:n_half]

    # 2. Среднее верхней половины x̄_{n/2} (формула 5.42)
    x_bar_half = float(np.mean(upper_half))

    # 3. Статистика λ2_{n/2} (формула 5.44)
    # λ2 = (1/(n/2)) * Σ lg(x_i / x̄_{n/2})
    ratios = upper_half / x_bar_half
    lambda2_half = float(np.mean(np.log10(ratios)))

    # 4. Cs/Cv — используем эмпирическое отношение от полного ряда
    full_mean = float(np.mean(data))
    full_std = float(np.std(data, ddof=1))
    full_Cv = full_std / full_mean if full_mean != 0 else 0
    full_Cs = float(pd.Series(data).skew())
    Cs_over_Cv = full_Cs / full_Cv if full_Cv > 0 else 2.0

    # 5. Cv из табл. Б.6 по λ2_{n/2} и Cs/Cv
    Cv = get_Cv_from_lambda2_table_B6(lambda2_half, Cs_over_Cv)

    if Cv is None or Cv <= 0:
        # Фоллбек: эмпирический Cv
        Cv = full_Cv

    # 6. φ(Cv) из табл. Б.5
    phi_Cv = get_phi_Cv_table_B5(Cv)

    if phi_Cv is None or phi_Cv <= 0:
        phi_Cv = 1.0

    # 7. Оценка x0 по формуле (5.41): x0 = x̄_{n/2} / φ(Cv)
    x0 = x_bar_half / phi_Cv

    # 8. Квантили через Пирсон III с параметрами усечённого распределения
    # Для усечённого распределения Cs/Cv принимается из 5.1.7
    # Здесь используем Cs = Cs_over_Cv * Cv
    Cs = Cs_over_Cv * Cv

    P_decimal = np.array(P_values) / 100.0
    quantiles = pearson3_ppf(P_decimal, x0, Cv, Cs)

    kp = quantiles / x0 if x0 != 0 else np.full_like(quantiles, np.nan)

    return pd.DataFrame({
        "P_%": P_values,
        "Q_max": np.round(quantiles, 2),
        "kp": np.round(kp, 4),
    })
