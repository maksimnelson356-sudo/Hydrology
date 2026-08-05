"""
core/short_series.py
Восстановление данных по коротким рядам (<6 лет) — аналог Short2012 (ГГИ)

Метод уравнений регрессии (СП 33-101-2003, п.2):
- Для каждого бассейна-аналога строится линейная связь: Qрасч = k0 + k1 × Qаналог
- Метод «единого решения»: k1 = σy / σx (а не r·σy/σx)
- Для каждого пропущенного года: частные оценки от каждого аналога, осреднение с весом 1/σ²
- σошибки = sqrt(1 / Σ(1/σ²_i))

Используется совместно с gui/widget_short.py
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from scipy import stats

from core.stats.series_extension import get_ro_critical


def fit_analog_relationship(
    Q_calc: pd.Series,
    Q_analog: pd.Series,
    use_single_solution: bool = True,
    alpha: float = 0.05,
) -> dict:
    """
    Построение линии связи расчётного ряда с одним аналогом.

    Метод «единого решения» (по умолчанию):
        k1 = σ_calc / σ_analog  (угловой коэффициент)
        k0 = mean_calc - k1 × mean_analog

    Обычная регрессия:
        k1 = r × σ_calc / σ_analog
        k0 = mean_calc - k1 × mean_analog

    Возвращает dict:
        k0, k1, R, R2, n_common, mean_calc, mean_analog,
        sigma_calc, sigma_analog, sigma_res (стандарт остатков),
        Ro_crit, quality_class, is_usable
    """
    # Общие годы
    common_years = Q_calc.dropna().index.intersection(Q_analog.dropna().index)
    n = len(common_years)

    if n < 3:
        return {
            'success': False,
            'n_common': n,
            'reason': f'Недостаточно общих лет ({n} < 3)',
            'k0': 0, 'k1': 0, 'R': 0, 'R2': 0,
            'sigma_res': 0, 'Ro_crit': 1.0,
            'quality_class': 'Нет связи', 'is_usable': False,
        }

    y = Q_calc.loc[common_years].values.astype(float)
    x = Q_analog.loc[common_years].values.astype(float)

    xbar, ybar = x.mean(), y.mean()
    sx, sy = x.std(ddof=1), y.std(ddof=1)

    if sx < 1e-12 or sy < 1e-12:
        return {
            'success': False, 'n_common': n,
            'reason': 'Нулевая дисперсия',
            'k0': 0, 'k1': 0, 'R': 0, 'R2': 0,
            'sigma_res': 0, 'Ro_crit': get_ro_critical(n, alpha),
            'quality_class': 'Нет связи', 'is_usable': False,
        }

    r, _ = stats.pearsonr(x, y)
    R2 = r ** 2

    # Метод «единого решения»: k1 = σy/σx
    if use_single_solution:
        k1 = sy / sx
    else:
        k1 = r * sy / sx

    k0 = ybar - k1 * xbar

    # Стандарт остатков регрессии
    y_pred = k0 + k1 * x
    residuals = y - y_pred
    sigma_res = np.std(residuals, ddof=1)

    # σRo = (1 - R²) / √n
    sigma_Ro = (1 - R2) / np.sqrt(n) if n > 1 else 1.0
    R_over_sigma = abs(r) / sigma_Ro if sigma_Ro > 1e-12 else 0

    Ro_crit = get_ro_critical(n, alpha)

    # Класс качества
    if abs(r) >= 0.95:
        quality_class = 'Отличная'
    elif abs(r) >= 0.90:
        quality_class = 'Хорошая'
    elif abs(r) >= 0.80:
        quality_class = 'Удовлетворительная'
    elif abs(r) >= 0.70:
        quality_class = 'Слабая'
    else:
        quality_class = 'Неудовлетворительная'

    is_usable = (abs(r) >= Ro_crit) and (R_over_sigma >= 2.0) and (n >= 5)

    return {
        'success': True,
        'k0': round(k0, 6),
        'k1': round(k1, 6),
        'R': round(r, 4),
        'R2': round(R2, 4),
        'n_common': n,
        'mean_calc': round(ybar, 4),
        'mean_analog': round(xbar, 4),
        'sigma_calc': round(sy, 4),
        'sigma_analog': round(sx, 4),
        'sigma_res': round(sigma_res, 4),
        'sigma_Ro': round(sigma_Ro, 4),
        'R_over_sigma': round(R_over_sigma, 2),
        'Ro_crit': round(Ro_crit, 4),
        'quality_class': quality_class,
        'is_usable': is_usable,
    }


def restore_year(
    year: int,
    Q_calc: pd.Series,
    analogs_data: Dict[str, pd.Series],
    fits: Dict[str, dict],
    selected_analogs: List[str],
    excluded_analogs: Optional[List[str]] = None,
    min_analogs: int = 5,
    exclude_negative: bool = True,
    z_limit: float = 3.0,
) -> Optional[dict]:
    """
    Восстановление значения за один пропущенный год.

    Алгоритм:
    1. Найти аналоги, у которых есть значение за этот год и которые не исключены
    2. Для каждого: Q_частная = k0 + k1 × Q_аналог[год]
    3. Исключить Q < 0 (если exclude_negative)
    4. Исключить выбросы по z_limit (итеративно)
    5. Осреднить可靠ные оценки с весом 1/σ²
    6. σош = 1/√(Σ(1/σ²_i))

    Возвращает dict или None (если недостаточно данных).
    """
    excluded = set(excluded_analogs or [])

    # Аналоги с данными за этот год
    candidates = []
    for analog_name in selected_analogs:
        if analog_name in excluded:
            continue
        if analog_name not in fits or not fits[analog_name].get('success', False):
            continue
        series = analogs_data.get(analog_name)
        if series is None:
            continue
        val = series.get(year) if hasattr(series, 'get') else (
            series.loc[year] if year in series.index else np.nan
        )
        if pd.isna(val):
            continue

        fit = fits[analog_name]
        Q_priv = fit['k0'] + fit['k1'] * float(val)
        sigma_priv = fit['sigma_res']

        candidates.append({
            'analog': analog_name,
            'Q_analog': float(val),
            'Q_private': round(Q_priv, 4),
            'sigma_res': sigma_priv,
            'reliable': True,
            'note': '',
        })

    if len(candidates) < min_analogs:
        return None

    # Исключение отрицательных
    if exclude_negative:
        for c in candidates:
            if c['Q_private'] < 0:
                c['reliable'] = False
                c['note'] = 'Q < 0'

    # Итеративное исключение выбросов по z_limit
    for _ in range(3):
        reliable = [c for c in candidates if c['reliable'] and c['note'] == '']
        if len(reliable) < 3:
            break
        values = [c['Q_private'] for c in reliable]
        mean_v = np.mean(values)
        std_v = np.std(values, ddof=1)
        if std_v < 1e-12:
            break
        for c in reliable:
            z = abs(c['Q_private'] - mean_v) / std_v
            if z > z_limit:
                c['reliable'] = False
                c['note'] = f'Выброс (z={z:.1f})'

    # Осреднение reliable оценок с весом 1/σ²
    reliable = [c for c in candidates if c['reliable'] and c['note'] == '']
    if not reliable:
        return None

    weights = []
    for c in reliable:
        s = c['sigma_res']
        w = 1.0 / (s ** 2) if s > 1e-12 else 0
        weights.append(w)

    total_w = sum(weights)
    if total_w < 1e-12:
        return None

    Q_restored = sum(w * c['Q_private'] for w, c in zip(weights, reliable)) / total_w
    sigma_error = 1.0 / np.sqrt(total_w)
    delta_pct = (sigma_error / abs(Q_restored) * 100) if abs(Q_restored) > 1e-12 else 0

    return {
        'year': year,
        'Q_restored': round(Q_restored, 4),
        'sigma': round(sigma_error, 4),
        'delta_pct': round(delta_pct, 1),
        'n_analogs_used': len(reliable),
        'n_analogs_total': len(candidates),
        'private_estimates': candidates,
        'note': '',
    }


def restore_short_series(
    Q_calc: pd.Series,
    analogs: Dict[str, pd.Series],
    selected_analogs: List[str],
    min_analogs: int = 5,
    use_single_solution: bool = True,
    use_module_conversion: bool = False,
    areas: Optional[Dict[str, float]] = None,
    excluded_analogs: Optional[List[str]] = None,
    alpha: float = 0.05,
) -> dict:
    """
    Полный цикл восстановления короткого ряда.

    Аргументы:
        Q_calc — короткий ряд (1-6 лет), index = год
        analogs — dict[имя_аналога → pd.Series с тем же индексом годов]
        selected_analogs — список имён выбранных аналогов
        min_analogs — минимум аналогов с данными за год для восстановления
        use_single_solution — метод «единого решения» (k1=σy/σx)
        use_module_conversion — преобразовать Q→q перед расчётом
        areas — площади бассейнов {имя: F_km2}
        excluded_analogs — исключённые аналоги
        alpha — уровень значимости для Ro

    Возвращает dict с результатами.
    """
    excluded = set(excluded_analogs or [])
    warnings = []

    # Преобразование к модулям стока если нужно
    calc_area = areas.get('_calc', 0) if areas else 0
    if use_module_conversion and calc_area > 0:
        Q_calc = Q_calc * 1000.0 / calc_area
        analogs = {}
        for name, series in analogs.items():
            fa = areas.get(name, 0)
            if fa > 0:
                analogs[name] = series * 1000.0 / fa
            else:
                analogs[name] = series
        warnings.append('Преобразовано к модулям стока (q, л/с·км²)')

    # Шаг 1: Построение связей для каждого выбранного аналога
    fits = {}
    for name in selected_analogs:
        if name in excluded:
            continue
        if name not in analogs:
            warnings.append(f'Аналог "{name}" не найден в данных')
            continue
        fit = fit_analog_relationship(Q_calc, analogs[name],
                                      use_single_solution=use_single_solution,
                                      alpha=alpha)
        fits[name] = fit
        if not fit.get('success'):
            warnings.append(f'Аналог "{name}": {fit.get("reason", "ошибка")}')
        elif not fit.get('is_usable'):
            warnings.append(
                f'Аналог "{name}": R={fit["R"]:.3f}, '
                f'R/σRo={fit["R_over_sigma"]:.1f} — '
                f'{fit["quality_class"]} (ненадёжная связь)')

    # Шаг 2: Определение диапазона лет
    all_years = set()
    for name, series in analogs.items():
        if name in selected_analogs and name not in excluded:
            all_years.update(series.dropna().index)
    if all_years:
        year_min = min(all_years)
        year_max = max(all_years)
    else:
        year_min, year_max = 0, 0

    calc_years = set(Q_calc.dropna().index)
    missing_years = sorted(y for y in range(year_min, year_max + 1)
                          if y not in calc_years)

    # Шаг 3: Восстановление данных за каждый год
    results = []
    for year in missing_years:
        result = restore_year(
            year=year,
            Q_calc=Q_calc,
            analogs_data=analogs,
            fits=fits,
            selected_analogs=selected_analogs,
            excluded_analogs=excluded_analogs,
            min_analogs=min(min_analogs, len(selected_analogs) - len(excluded)),
            exclude_negative=True,
        )
        results.append(result)

    # Таблица результатов
    rows = []
    for year in sorted(calc_years):
        rows.append({
            'year': year,
            'Q': round(Q_calc.loc[year], 4),
            'Q_observed': round(Q_calc.loc[year], 4),
            'sigma': '',
            'delta_pct': '',
            'n_analogs': '',
            'note': 'Наблюдённое',
        })
    for i, r in enumerate(results):
        if r is not None:
            note = f'{r["n_analogs_used"]} из {r["n_analogs_total"]}'
            rows.append({
                'year': r['year'],
                'Q': r['Q_restored'],
                'Q_observed': '',
                'sigma': r['sigma'],
                'delta_pct': r['delta_pct'],
                'n_analogs': note,
                'note': 'Восстановлено',
            })
        else:
            year_val = missing_years[i] if i < len(missing_years) else '?'
            rows.append({
                'year': year_val,
                'Q': '',
                'Q_observed': '',
                'sigma': '',
                'delta_pct': '',
                'n_analogs': '',
                'note': 'Не восстановлено',
            })

    df_results = pd.DataFrame(rows)
    # Ensure year column is numeric for sorting
    df_results['year'] = pd.to_numeric(df_results['year'], errors='coerce')
    df_results = df_results.sort_values('year').reset_index(drop=True)

    # Nэфф
    n_restored = sum(1 for r in results if r is not None)
    n_total = len(calc_years) + n_restored
    N_eff = n_total

    return {
        'results': df_results,
        'pair_regressions': fits,
        'n_restored': n_restored,
        'n_total_years': n_total,
        'N_eff': N_eff,
        'missing_years': missing_years,
        'warnings': warnings,
    }


def build_protocol(result: dict) -> str:
    """
    Формирование текстового протокола восстановления.
    Аналог Протоколы/Продление.txt из ГГИ.
    """
    lines = []
    lines.append('=' * 60)
    lines.append('ПРОТОКОЛ ВОССТАНОВЛЕНИЯ КОРОТКОГО РЯДА (Short)')
    lines.append('=' * 60)

    # Регрессии по аналогам
    lines.append('')
    lines.append('--- Связи с аналогами ---')
    fits = result.get('pair_regressions', {})
    for name, fit in fits.items():
        if not fit.get('success'):
            lines.append(f'  {name}: НЕУСПЕХ — {fit.get("reason", "")}')
            continue
        status = 'ИСПОЛЬЗУЕТСЯ' if fit.get('is_usable') else 'НЕНАДЁЖНА'
        lines.append(
            f'  {name}: R={fit["R"]:.4f}, k0={fit["k0"]:.4f}, '
            f'k1={fit["k1"]:.4f}, σ={fit["sigma_res"]:.4f}, '
            f'n={fit["n_common"]}, {fit["quality_class"]} [{status}]')

    # Предупреждения
    if result.get('warnings'):
        lines.append('')
        lines.append('--- Предупреждения ---')
        for w in result['warnings']:
            lines.append(f'  • {w}')

    # Таблица результатов
    lines.append('')
    lines.append('--- Результаты восстановления ---')
    df = result.get('results', pd.DataFrame())
    if not df.empty:
        header = f'{"Год":>6}  {"Q":>10}  {"σ":>8}  {"δ%":>6}  {"N":>5}  {"Примечание"}'
        lines.append(header)
        lines.append('-' * len(header))
        for _, row in df.iterrows():
            q_str = f'{row["Q"]:>10.4f}' if row['Q'] != '' else f'{"—":>10}'
            s_str = f'{row["sigma"]:>8.4f}' if row['sigma'] != '' else f'{"—":>8}'
            d_str = f'{row["delta_pct"]:>6.1f}' if row['delta_pct'] != '' else f'{"—":>6}'
            n_str = f'{str(row["n_analogs"]):>5}' if row['n_analogs'] != '' else f'{"—":>5}'
            lines.append(
                f'{row["year"]:>6}  {q_str}  {s_str}  {d_str}  {n_str}  {row["note"]}')

    # Итого
    lines.append('')
    lines.append(
        f'Восстановлено: {result.get("n_restored", 0)} из '
        f'{len(result.get("missing_years", []))} пропущенных лет')
    lines.append(f'Nэфф = {result.get("N_eff", 0)}')

    return '\n'.join(lines)


def convert_to_module_flow(Q: pd.Series, F: float) -> pd.Series:
    """Q (м³/с) → q (л/с·км²): q = Q * 1000 / F"""
    if F <= 0:
        raise ValueError(f'Площадь бассейна должна быть > 0 (получено {F})')
    return Q * 1000.0 / F


def convert_from_module_flow(q: pd.Series, F: float) -> pd.Series:
    """q (л/с·км²) → Q (м³/с): Q = q * F / 1000"""
    if F <= 0:
        raise ValueError(f'Площадь бассейна должна быть > 0 (получено {F})')
    return q * F / 1000.0
