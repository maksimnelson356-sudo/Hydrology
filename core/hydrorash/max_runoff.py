"""
core/hydrorash/max_runoff.py
Модуль расчёта МАКСИМАЛЬНОГО стока (паводков)

Согласно СП 33-101-2003, п. 5.26–5.31.

Проверено 2026-09-28: прежняя ссылка «раздел 8» была ошибочной - раздела 8
в СП 33-101-2003 не существует (стандарт состоит из разделов 1–7 и приложений).
РД 52-26-2008 как источник не проверен.

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
    use_normative_Cs: bool = True
) -> dict:
    """Статистические характеристики ряда максимальных стоков по СП 33."""
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

    if use_normative_Cs:
        # ПРАВИЛО НЕ ИЗ СП 33. Проверено по печатному экземпляру: соотношение
        # Cs = 2Cv встречается в стандарте ровно один раз — в п. 5.14 при
        # формулировке «случайные средние квадратические ошибки коэффициентов
        # вариации при Cs = 2Cv», то есть как УСЛОВИЕ для формулы погрешности
        # (5.28), а не как правило вычисления Cs по Cv. Ветки 3,0·Cv и порога
        # Cv = 0,5 в стандарте нет вовсе.
        #
        # Следствие: кривая разрывается при Cv = 0,5 — при Cv = 0,4999 получаем
        # Cs ≈ 1,0, при Cv = 0,5001 уже Cs ≈ 1,5, то есть непрерывность
        # обеспеченностей нарушается на размере, не имеющем в стандарте никакого
        # обоснования. Кроме того, Cs/Cv — нормативный параметр по п. 5.4, и
        # задание Cs из Cv подменяет его отношениеми разной величины.
        Cs = 2.0 * Cv if Cv <= 0.5 else 3.0 * Cv
    else:
        Cs = Cs_emp

    # r(1) берётся из нормативного источника (Б.1)-(Б.3) приложения Б, а не из
    # корреляции Пирсона: (5.26) и (5.27) требуют именно её, в (Б.2) две разные
    # средние и приведение к несмещённой оценке через (Б.1). Раньше здесь стоял
    # np.corrcoef, то есть величина считалась не по стандарту.
    lag1 = sp33_lag1_autocorrelation(data)
    r1 = lag1["r1"]
    epsilon = relative_mean_error_percent(Cv, n, r1)
    error_limit_percent = MAX_MIN_RELATIVE_RMS_ERROR_LIMIT * 100.0

    warnings = []
    reliability_class = "Надёжная"
    if not np.isfinite(epsilon):
        warnings.append(
            f"εQ НЕ ВЫЧИСЛЕНА: {lag1['source']}; множитель в (5.26)/(5.27) "
            f"не имеет вещественного значения. Предел "
            f"{error_limit_percent:.0f}% не проверен"
        )
        reliability_class = "Недостаточно данных"
    elif epsilon > error_limit_percent:
        warnings.append(
            f"εQ = {epsilon:.1f}% > {error_limit_percent:.0f}%. "
            "Требуется удлинение ряда (СП 33-101-2003 п. 5.1, 5.14)"
        )
        reliability_class = "Ненадёжная"

    return {
        "n": n,
        "mean": round(mean, 4),
        "std": round(std, 4),
        "Cv": round(Cv, 4),
        "Cs": round(Cs, 4),
        "Cs_empirical": round(Cs_emp, 4),
        "r1": r1,
        "epsilon": round(epsilon, 2),
        "relative_rms_error_limit": MAX_MIN_RELATIVE_RMS_ERROR_LIMIT,
        "warnings": warnings,
        "reliability_class": reliability_class
    }


def max_runoff_frequency_curve(
    max_series: pd.Series,
    P_values: list[float] | None = None,
    use_normative_Cs: bool = True
) -> pd.DataFrame:
    """
    Кривая обеспечённости максимальных стоков (Пирсон III типа).

    СП 33-101-2003 п. 5.26–5.31 НЕ содержит расчётных обеспеченностей для
    ГТС, мостов и берегоукрепления. Проверено по печатному экземпляру:
    в тексте стандарта нет ни слова «ГТС», кроме библиографической ссылки на
    отменённый СНиП 2.06.04-82. Пункты 5.26–5.31 говорят о другом:
      5.26 — параметры максимального стока определяются по требованиям 5.1–5.16;
      5.27 — среднесуточные или срочные значения в зависимости от
             продолжительности стояния максимума;
      5.28 — допускается строить кривые без разделения дождевых и талых максимумов;
      5.29 — при неоднородности применяются составные кривые (см. 5.12) либо
             усечённые распределения, формулы (5.40)–(5.43);
      5.30 — расходы зарегулированных рек;
      5.31 — гарантийная поправка (5.44) для Q при P = 0,01 %.

    Перечень обеспеченностей ниже (0,1 % для ГТС I класса, 0,33 % для ГТС
    II класса и т. д.) происходит из СП 58.13330, а не из СП 33, и ранее
    ошибочно приписывался пунктам 5.26–5.31.

    НЕ РЕАЛИЗОВАНО по СП 33:
      - (5.44) гарантийная поправка ΔQ = α·E₀,₀₁·Q₀,₀₁/√N (п. 5.31), вместе
        с ограничением ΔQ ≤ 20 % от Q₀,₀₁ и требованием не опускаться ниже
        наибольшего наблюдённого расхода;
      - усечённое гамма-распределение, формулы (5.40)–(5.43) (п. 5.29);
      - соотношение (5.1)–(5.16) неполно: поправки (5.6)–(5.9) на смещение
        не применяются, см. core/stats/parameters.py.

    Parameters:
        max_series: ряд максимальных стоков
        P_values: обеспеченности в % (по умолчанию стандартные)
        use_normative_Cs: использовать расчётное Cs (НЕ из СП 33, см. ниже)

    Returns:
        DataFrame: P_%, Q_max, kp
    """
    if P_values is None:
        P_values = [0.1, 0.33, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 33.0, 50.0]

    data = np.asarray(pd.Series(max_series).dropna(), dtype=float)
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
