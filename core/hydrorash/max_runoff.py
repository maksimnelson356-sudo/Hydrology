"""
core/hydrorash/max_runoff.py
Модуль расчёта МАКСИМАЛЬНОГО стока (паводков)

Согласно СП 33-101-2003 раздел 8, РД 52-26-2008.

Основные функции:
- extract_max_annual — извлечение средних максимальных расходов за N суток
- compute_max_runoff_stats — статистические характеристики максимальных стоков
- max_runoff_frequency_curve — кривая обеспечённости максимальных стоков
- index_year_method — метод индексных годов для безструментных рек
- build_rating_curve — кривая функционирования Q = f(H)
- discharge_from_level — расход по уровню воды
- level_from_discharge — уровень воды по расходу
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from scipy import stats
from .utils import compute_basic_stats


def extract_max_annual(
    daily_df: pd.DataFrame,
    year_col: str = 'year',
    value_col: str = 'value',
    period_days: int = 1
) -> pd.Series:
    """
    Извлечение средних максимальных расходов за period_days суток для каждого года.

    period_days=1  — абсолютный суточный максимум
    period_days>1  — скользящее среднее за period_days суток, затем максимум по году

    Parameters:
        daily_df: DataFrame с колонками year и value (суточные расходы)
        year_col: имя колонки с годом
        value_col: имя колонки с расходом
        period_days: длительность окна (сутки)

    Returns:
        Series, индексированная годом, значения — максимальные расходы
    """
    df = daily_df[[year_col, value_col]].dropna().copy()
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
    use_normative_Cs: bool = True
) -> Dict:
    """
    Статистические характеристики ряда максимальных стоков.

    СП 33-101-2003 п. 6.3.3: для максимальных стоков Cs ≈ 2×Cv (при Cv ≤ 0.5)
    или Cs ≈ 3×Cv (при Cv > 0.5).
    """
    data = max_series.dropna().values
    if len(data) < 3:
        return {"mean": None, "Cv": None, "Cs": None, "n": len(data), "reliability_class": "Недостаточно данных"}

    n = len(data)
    mean = float(np.mean(data))
    std = float(np.std(data, ddof=1))
    Cv = std / mean if mean != 0 else 0.0
    Cs_emp = float(pd.Series(data).skew())

    if use_normative_Cs:
        Cs = 2.0 * Cv if Cv <= 0.5 else 3.0 * Cv
    else:
        Cs = Cs_emp

    epsilon = (Cv / np.sqrt(n)) * 100.0

    warnings = []
    reliability_class = "Надёжная"
    if n < 10:
        warnings.append(f"Критично: длина ряда {n} лет < 10")
        reliability_class = "Ненадёжная"
    elif n < 20:
        warnings.append(f"Длина ряда {n} лет < 20. Желательно удлинение")
        reliability_class = "Пониженная надёжность"

    if epsilon > 15:
        warnings.append(f"εQ = {epsilon:.1f}% > 15%. Требуется удлинение")
        reliability_class = "Ненадёжная"

    return {
        "n": n,
        "mean": round(mean, 4),
        "std": round(std, 4),
        "Cv": round(Cv, 4),
        "Cs": round(Cs, 4),
        "Cs_empirical": round(Cs_emp, 4),
        "epsilon": round(epsilon, 2),
        "warnings": warnings,
        "reliability_class": reliability_class
    }


def max_runoff_frequency_curve(
    max_series: pd.Series,
    P_values: Optional[List[float]] = None,
    use_normative_Cs: bool = True
) -> pd.DataFrame:
    """
    Кривая обеспечённости максимальных стоков (Пирсон III типа).

    СП 33-101-2003 п. 8.1: расчётные обеспечённости:
    - Для ГТС I класса: 0.1%
    - Для ГТС II класса: 0.33%
    - Для мостов: 1%, 5%
    - Для берегоукрепления: 1%, 5%, 10%

    Parameters:
        max_series: ряд максимальных стоков
        P_values: обеспеченности в % (по умолчанию стандартные)
        use_normative_Cs: использовать нормативное Cs

    Returns:
        DataFrame: P_%, Q_max, kp
    """
    if P_values is None:
        P_values = [0.1, 0.33, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 33.0, 50.0]

    data = max_series.dropna().values
    if len(data) < 3:
        return pd.DataFrame({"P_%": P_values, "Q_max": [np.nan] * len(P_values), "kp": [np.nan] * len(P_values)})

    params = compute_max_runoff_stats(data, use_normative_Cs)
    mean = params["mean"]
    Cv = params["Cv"]
    Cs = params["Cs"]

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
    P_values: Optional[List[float]] = None
) -> pd.DataFrame:
    """
    Метод индексных годов (СП 33-101-2003 п. 8.2).

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
    if P_values is None:
        P_values = [0.1, 1.0, 3.0, 5.0, 10.0, 20.0, 33.0, 50.0]

    ratios = (gauged_max_series / gauged_mean_annual).dropna()
    if len(ratios) < 3:
        return pd.DataFrame({"P_%": P_values, "K_p": [np.nan] * len(P_values), "Q_max": [np.nan] * len(P_values)})

    stats_result = compute_basic_stats(ratios, use_normative_Cs=True)
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
    H0: Optional[float] = None
) -> Dict:
    """
    Построение кривой функционирования Q = a × (H - H0)^b.

    Если H0 не задан, определяется как минимальный уровень воды на посту.

    Parameters:
        H: массив уровней воды (м)
        Q: массив расходов (м³/с)
        H0: уровень нуля поста (если None — берётся min(H))

    Returns:
        Dict: a, b, H0, R2, formula
    """
    H = np.asarray(H, dtype=float)
    Q = np.asarray(Q, dtype=float)

    mask = Q > 0
    H, Q = H[mask], Q[mask]

    if len(H) < 3:
        raise ValueError("Нужно минимум 3 точки с Q > 0")

    if H0 is None:
        H0 = float(np.min(H)) - 0.01

    dH = H - H0
    if np.any(dH <= 0):
        H0 = float(np.min(H)) - 0.01
        dH = H - H0

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


def discharge_from_level(H: float, params: Dict) -> float:
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


def level_from_discharge(Q: float, params: Dict) -> float:
    """
    Уровень воды по расходу: H = H0 + (Q/a)^(1/b).
    """
    a = params["a"]
    b = params["b"]
    H0 = params["H0"]
    if Q <= 0 or a <= 0:
        return H0
    return float(H0 + (Q / a) ** (1.0 / b))
