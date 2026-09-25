"""
core/services/handlers/__init__.py
Adapters from CalculationContext to plain result dicts (stage 3 of DOCS/ROADMAP.md).

Each handler delegates to existing core.stats / core.hydrorash functions and
performs NO mathematics itself: it only converts the dataset to the shapes the
core functions expect and serializes their output into plain Python types so
that the result can be stored in a project (.hsp) without numpy/pandas types.

Registered in core.services.bootstrap.build_container().
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from core.services.calculation_service import CalculationContext

VERSION = "1.0"


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _clean_scalar(value: Any) -> Any:
    """Convert a single numpy/pandas scalar or container to plain Python types."""
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return [_clean_scalar(item) for item in value.tolist()]
    if isinstance(value, (pd.Series, pd.Index)):
        return [_clean_scalar(item) for item in value.tolist()]
    if isinstance(value, dict):
        return _clean(value)
    if isinstance(value, (list, tuple)):
        return [_clean_scalar(item) for item in value]
    return value


def _clean(result: dict[str, Any]) -> dict[str, Any]:
    """Convert numpy scalars/arrays and pandas objects in a dict to plain types."""
    plain: dict[str, Any] = {}
    for key, value in result.items():
        if isinstance(value, dict):
            plain[key] = _clean(value)
        elif isinstance(value, (np.integer,)):
            plain[key] = int(value)
        elif isinstance(value, (np.floating,)):
            plain[key] = float(value)
        elif isinstance(value, (np.ndarray, pd.Series, pd.Index)):
            plain[key] = [_clean_scalar(item) for item in value.tolist()]
        elif isinstance(value, pd.DataFrame):
            plain[key] = _to_float_dict(value)
        elif isinstance(value, (list, tuple)):
            plain[key] = [_clean_scalar(item) for item in value]
        else:
            plain[key] = value
    return plain


def _to_float_dict(frame: pd.DataFrame) -> dict[str, list[Any]]:
    """DataFrame -> {"columns": [...], "rows": [[...], ...]} with plain floats."""
    columns = [str(c) for c in frame.columns]
    rows: list[list[Any]] = []
    for record in frame.to_dict(orient="records"):
        row: list[Any] = []
        for column in columns:
            value = record.get(column)
            if isinstance(value, (np.integer,)):
                row.append(int(value))
            elif isinstance(value, (np.floating,)):
                row.append(float(value))
            elif value is None or (isinstance(value, float) and np.isnan(value)):
                row.append(None)
            else:
                row.append(value)
        rows.append(row)
    return {"columns": columns, "rows": rows}


def _values(context: CalculationContext) -> np.ndarray:
    """Series values as float ndarray (chronological order)."""
    return np.asarray(context.dataset.values, dtype=float)


def _years(context: CalculationContext) -> np.ndarray:
    """Series years as float ndarray (chronological order)."""
    return np.asarray(context.dataset.years, dtype=float)


def _param(context: CalculationContext, name: str, default: Any) -> Any:
    return context.parameters.get(name, default)


# ----------------------------------------------------------------------
# Statistics handlers
# ----------------------------------------------------------------------
def handle_stats_parameters(context: CalculationContext) -> dict[str, Any]:
    """Статистические параметры ряда (СП 33-101-2003)."""
    from core.stats.parameters import calculate_statistical_parameters

    result = calculate_statistical_parameters(
        _values(context),
        min_probability=_param(context, "min_probability", None),
    )
    return _clean(dict(result))


def handle_frequency_pearson3(context: CalculationContext) -> dict[str, Any]:
    """Кривая обеспеченности, распределение Пирсона III (СП 33-101-2003)."""
    from core.stats.frequency import calculate_frequency_curve

    frame = calculate_frequency_curve(
        _values(context),
        probabilities=_param(context, "probabilities", None),
        curve_type="pearson3",
        use_corrected=_param(context, "use_corrected", True),
    )
    return _to_float_dict(frame)


def handle_frequency_kritsky_menkel(context: CalculationContext) -> dict[str, Any]:
    """Кривая обеспеченности по Крицкому-Менкелю (СП 33-101-2003)."""
    from core.stats.frequency import calculate_frequency_curve

    frame = calculate_frequency_curve(
        _values(context),
        probabilities=_param(context, "probabilities", None),
        curve_type="kritsky_menkel",
        use_corrected=_param(context, "use_corrected", True),
    )
    return _to_float_dict(frame)


def handle_homogeneity_full(context: CalculationContext) -> dict[str, Any]:
    """Проверка однородности: критерии Диксона/Граббса (СП 33-101-2003, Прил. А)."""
    from core.stats.homogeneity import check_homogeneity_full

    result = check_homogeneity_full(
        _values(context),
        alpha=_param(context, "alpha", 0.05),
    )
    return _clean(dict(result))


def handle_trends_full(context: CalculationContext) -> dict[str, Any]:
    """Полный анализ тренда: линейный, Манн-Кендалл, Сен, Pettitt."""
    from core.stats.trends import full_trend_analysis

    frame = pd.DataFrame({"year": _years(context), "value": _values(context)})
    result = full_trend_analysis(frame)
    return _clean(dict(result))


def handle_series_extension(context: CalculationContext) -> dict[str, Any]:
    """Удлинение короткого ряда по заданному ряду-аналогу."""
    from core.stats.series_extension import full_extension_workflow

    raw_analog = _param(context, "analog_df", None)
    if raw_analog is None:
        raise ValueError("series_extension требует параметр analog_df")

    if isinstance(raw_analog, pd.Series):
        analog = raw_analog.astype(float).copy()
    elif isinstance(raw_analog, pd.DataFrame):
        year_col = str(_param(context, "analog_year_col", "year"))
        value_col = str(_param(context, "analog_value_col", "value"))
        missing = [name for name in (year_col, value_col) if name not in raw_analog.columns]
        if missing:
            raise ValueError(
                f"series_extension: analog_df не содержит колонки {', '.join(missing)}"
            )
        analog = pd.Series(
            pd.to_numeric(raw_analog[value_col], errors="coerce").to_numpy(dtype=float),
            index=pd.to_numeric(raw_analog[year_col], errors="coerce").to_numpy(),
            name="analog",
        ).dropna()
    elif isinstance(raw_analog, dict):
        analog = pd.Series(raw_analog, dtype=float)
    else:
        raise ValueError("series_extension: analog_df должен быть DataFrame, Series или dict")

    try:
        analog.index = analog.index.astype(int)
    except (TypeError, ValueError) as error:
        raise ValueError("series_extension: годы analog_df должны быть целыми") from error

    observed = pd.Series(
        _values(context),
        index=_years(context).astype(int),
        name="observed",
    )
    method = str(_param(context, "method", "regression"))
    if method not in {"regression", "proportional"}:
        raise ValueError("series_extension: method должен быть regression или proportional")

    result = full_extension_workflow(observed, analog, method=method)
    return _clean(dict(result))


def handle_flood_hydrograph(context: CalculationContext) -> dict[str, Any]:
    """Построение гидрографа паводка по пиковому расходу."""
    from core.hydrorash.flood_hydrograph import hydrograph_from_peak

    required = ("Q_peak", "T_peak", "T_base")
    missing = [name for name in required if _param(context, name, None) is None]
    if missing:
        raise ValueError(
            f"flood_hydrograph требует параметры {', '.join(missing)}"
        )

    result = hydrograph_from_peak(
        Q_peak=float(_param(context, "Q_peak", None)),
        T_peak=float(_param(context, "T_peak", None)),
        T_base=float(_param(context, "T_base", None)),
        method=str(_param(context, "method", "gamma")),
        shape=float(_param(context, "shape", 3.5)),
        dt=float(_param(context, "dt", 1.0)),
        asymmetry=float(_param(context, "asymmetry", 0.3)),
    )
    return _clean(dict(result))


def handle_backwater(context: CalculationContext) -> dict[str, Any]:
    """Расчёт линии подпора от водохранилища."""
    from core.hydrorash.backwater import backwater_from_reservoir

    required = ("Q", "B", "m", "n", "I", "H_reservoir")
    missing = [name for name in required if _param(context, name, None) is None]
    if missing:
        raise ValueError(f"backwater требует параметры {', '.join(missing)}")

    result = backwater_from_reservoir(
        Q=float(_param(context, "Q", None)),
        B=float(_param(context, "B", None)),
        m=float(_param(context, "m", None)),
        n=float(_param(context, "n", None)),
        I=float(_param(context, "I", None)),
        H_reservoir=float(_param(context, "H_reservoir", None)),
        L_max=float(_param(context, "L_max", 10000.0)),
        dx=float(_param(context, "dx", 200.0)),
    )
    return _clean(dict(result))


# ----------------------------------------------------------------------
# Runoff / reservoir handlers
# ----------------------------------------------------------------------
def handle_max_runoff(context: CalculationContext) -> dict[str, Any]:
    """Максимальный сток: годовые максимумы и их кривая обеспеченности."""
    from core.hydrorash.max_runoff import extract_max_annual, max_runoff_frequency_curve

    daily = _param(context, "daily_df", None)
    if daily is None:
        raise ValueError("max_runoff требует параметр daily_df (DataFrame с колонками year/value)")
    max_series = extract_max_annual(
        daily,
        year_col=_param(context, "year_col", "year"),
        value_col=_param(context, "value_col", "value"),
        period_days=_param(context, "period_days", 1),
    )
    frame = max_runoff_frequency_curve(
        max_series,
        P_values=_param(context, "P_values", None),
        use_normative_Cs=_param(context, "use_normative_Cs", True),
    )
    return _to_float_dict(frame)


def handle_min_runoff(context: CalculationContext) -> dict[str, Any]:
    """Минимальный сток: 30-дневные зимние минимумы и их кривая обеспеченности."""
    from core.hydrorash.min_runoff_extended import extract_min_annual, min_runoff_frequency_curve

    daily = _param(context, "daily_df", None)
    if daily is None:
        raise ValueError("min_runoff требует параметр daily_df (DataFrame с колонками year/value)")
    min_series = extract_min_annual(
        daily,
        year_col=_param(context, "year_col", "year"),
        value_col=_param(context, "value_col", "value"),
        period_days=_param(context, "period_days", 30),
        season=_param(context, "season", "winter"),
    )
    frame = min_runoff_frequency_curve(
        min_series,
        P_values=_param(context, "P_values", None),
        use_normative_Cs=_param(context, "use_normative_Cs", True),
    )
    return _to_float_dict(frame)


def handle_flow_duration(context: CalculationContext) -> dict[str, Any]:
    """Кривая продолжительности стока."""
    from core.stats.flow_duration import flow_duration_curve

    result = flow_duration_curve(
        _values(context),
        exceedance_probs=_param(context, "exceedance_probs", None),
    )
    return _clean(dict(result))


def handle_reservoir_regulation(context: CalculationContext) -> dict[str, Any]:
    """Многолетнее регулирование стока водохранилищем."""
    from core.hydrorash.reservoir_regulation import multi_year_regulation

    demand = _param(context, "demand_m3_s", None)
    if demand is None:
        raise ValueError("reservoir_regulation требует параметр demand_m3_s")
    result = multi_year_regulation(
        _values(context),
        demand_m3_s=float(demand),
        V_max_km3=_param(context, "V_max_km3", None),
        S_0_km3=_param(context, "S_0_km3", None),
        target_guarantee=_param(context, "target_guarantee", 95.0),
        mode=_param(context, "mode", "natural_supply"),
    )
    return _clean(dict(result))


def handle_storage_yield(context: CalculationContext) -> dict[str, Any]:
    """Кривая «объём водохранилища — гарантированная отдача» (P1.7)."""
    from core.hydrorash.reservoir_regulation import storage_yield_curve

    frame = storage_yield_curve(
        _values(context),
        V_range_km3=_param(context, "V_range_km3", None),
        target_guarantee=float(_param(context, "target_guarantee", 95.0)),
    )
    return _to_float_dict(frame)


# ----------------------------------------------------------------------
# P1.4 extended methodologies (thin adapters only)
# ----------------------------------------------------------------------
def handle_spectral_hurst(context: CalculationContext) -> dict[str, Any]:
    """Экспонента Хёрста (метод R/S) — долгосрочная память ряда."""
    from core.stats.spectral import hurst_exponent

    result = hurst_exponent(
        _values(context),
        max_window=_param(context, "max_window", None),
    )
    return _clean(dict(result))


def handle_drought_spi(context: CalculationContext) -> dict[str, Any]:
    """Стандартный индекс осадков (SPI); ряд трактуется как месячные осадки, мм."""
    from core.stats.drought import spi_index

    result = spi_index(
        _values(context),
        scale=int(_param(context, "scale", 12)),
    )
    return _clean(dict(result))


def handle_baseflow(context: CalculationContext) -> dict[str, Any]:
    """Разделение стока на поверхностный и подземный (baseflow separation)."""
    from core.stats.baseflow import (
        baseflow_digital_filter,
        baseflow_lyne_hollick,
        baseflow_straight_line,
    )

    values = _values(context)
    method = str(_param(context, "method", "straight_line"))
    if method == "digital_filter":
        result = baseflow_digital_filter(
            values,
            alpha=float(_param(context, "alpha", 0.925)),
            threshold=float(_param(context, "threshold", 0.9)),
            passes=int(_param(context, "passes", 3)),
        )
    elif method == "lyne_hollick":
        result = baseflow_lyne_hollick(values, a=float(_param(context, "a", 0.97)))
    else:
        result = baseflow_straight_line(
            values,
            min_separation=int(_param(context, "min_separation", 5)),
        )
    return _clean(dict(result))


def handle_confidence_bands(context: CalculationContext) -> dict[str, Any]:
    """Доверительные полосы кривой обеспеченности (Пирсон III, бутстреп)."""
    from core.stats.confidence_bands import pearson3_confidence_bands

    result = pearson3_confidence_bands(
        _values(context),
        P_values=_param(context, "P_values", None),
        confidence=float(_param(context, "confidence", 0.95)),
        n_bootstrap=int(_param(context, "n_bootstrap", 1000)),
    )
    return _clean(dict(result))


def handle_composite_curves(context: CalculationContext) -> dict[str, Any]:
    """Составная кривая обеспеченности (Рождественский); break_year — параметр или Pettitt."""
    from core.stats.composite_curves import compute_composite_curve, find_change_point

    values = _values(context)
    years = _years(context)
    break_year = _param(context, "break_year", None)
    if break_year is None:
        change = find_change_point(values, years)
        break_year = change.get("change_year")
        if break_year is None:
            raise ValueError(
                "composite_curves: не удалось определить break_year — укажите параметр"
            )
    result = compute_composite_curve(
        values,
        years,
        int(break_year),
        P_values=_param(context, "P_values", None),
        use_normative_Cs=_param(context, "use_normative_Cs", True),
    )
    return _clean(dict(result))


def handle_intra_annual(context: CalculationContext) -> dict[str, Any]:
    """Внутригодовое распределение: суммы по периодам водного года + статистика."""
    from core.hydrorash.intra_annual import calculate_water_year_sums, compute_intra_annual_stats

    monthly_df = _param(context, "monthly_df", None)
    if monthly_df is None:
        raise ValueError("intra_annual требует параметр monthly_df")
    sums = calculate_water_year_sums(monthly_df)
    stats = compute_intra_annual_stats(sums)
    return {"sums": _to_float_dict(sums), "stats": _clean(dict(stats))}


def handle_snowmelt(context: CalculationContext) -> dict[str, Any]:
    """Снеговой баланс бассейна за период таяния (СП 33-101-2003 п. 8.1)."""
    from core.hydrorash.snowmelt import snowmelt_balance

    w_initial = _param(context, "W_initial", None)
    precipitation = _param(context, "precipitation_mm", None)
    t_air = _param(context, "T_air", None)
    if w_initial is None or precipitation is None or t_air is None:
        raise ValueError("snowmelt требует параметры W_initial, precipitation_mm, T_air")
    result = snowmelt_balance(
        float(w_initial),
        float(precipitation),
        float(t_air),
        A=float(_param(context, "A", 3.5)),
        days=int(_param(context, "days", 30)),
    )
    return _clean(dict(result))


def handle_spillway(context: CalculationContext) -> dict[str, Any]:
    """Проверка пропускной способности ППУ (СП 58.13330.2019 п. 6)."""
    from core.hydrorash.spillway import spillway_capacity_check

    q_design = _param(context, "Q_design", None)
    h_max = _param(context, "H_max", None)
    length = _param(context, "L", None)
    if q_design is None or h_max is None or length is None:
        raise ValueError("spillway требует параметры Q_design, H_max, L")
    result = spillway_capacity_check(
        float(q_design),
        float(h_max),
        float(length),
        weir_type=str(_param(context, "weir_type", "sharp_crested")),
        Cd=_param(context, "Cd", None),
        n_openings=int(_param(context, "n_openings", 1)),
        opening_width=float(_param(context, "opening_width", 0)),
        opening_height=float(_param(context, "opening_height", 0)),
    )
    return _clean(dict(result))


def handle_ecological_flow(context: CalculationContext) -> dict[str, Any]:
    """Экологический сток: сезонный Тессман (СП 32.13330.2018, прил. 8)."""
    from core.hydrorash.ecological_flow import tessmann_seasonal

    q_annual = _param(context, "Q_annual_mean", None)
    if q_annual is None:
        raise ValueError("ecological_flow требует параметр Q_annual_mean")
    result = tessmann_seasonal(
        float(q_annual),
        region_type=str(_param(context, "region_type", "central")),
        Q_monthly_mean=_param(context, "Q_monthly_mean", None),
    )
    return _clean(dict(result))


def handle_ice_phenomena(context: CalculationContext) -> dict[str, Any]:
    """Оценка максимальной толщины льда (РД 52-26-2008; СП 58.13330.2019, табл. 7.1)."""
    from core.hydrorash.ice_phenomena import ClimateZone, estimate_max_ice_thickness

    latitude = _param(context, "latitude", None)
    mean_jan = _param(context, "mean_jan_temp", None)
    if latitude is None or mean_jan is None:
        raise ValueError("ice_phenomena требует параметры latitude и mean_jan_temp")
    zone_name = str(_param(context, "zone", ClimateZone.MODERATE.value))
    try:
        zone = ClimateZone(zone_name)
    except ValueError:
        zone = ClimateZone.MODERATE
    result = estimate_max_ice_thickness(
        float(latitude),
        float(mean_jan),
        zone=zone,
    )
    return _clean(dict(result))


# ----------------------------------------------------------------------
# Registry: methodology id -> handler
# ----------------------------------------------------------------------
HANDLERS: dict[str, Any] = {
    "stats_parameters": handle_stats_parameters,
    "series_extension": handle_series_extension,
    "flood_hydrograph": handle_flood_hydrograph,
    "backwater": handle_backwater,
    "frequency_pearson3": handle_frequency_pearson3,
    "frequency_kritsky_menkel": handle_frequency_kritsky_menkel,
    "homogeneity_full": handle_homogeneity_full,
    "trends_full": handle_trends_full,
    "max_runoff": handle_max_runoff,
    "min_runoff": handle_min_runoff,
    "flow_duration": handle_flow_duration,
    "reservoir_regulation": handle_reservoir_regulation,
    # P1.7
    "storage_yield": handle_storage_yield,
    # P1.4
    "spectral_hurst": handle_spectral_hurst,
    "drought_spi": handle_drought_spi,
    "baseflow": handle_baseflow,
    "confidence_bands": handle_confidence_bands,
    "composite_curves": handle_composite_curves,
    "intra_annual": handle_intra_annual,
    "snowmelt": handle_snowmelt,
    "spillway": handle_spillway,
    "ecological_flow": handle_ecological_flow,
    "ice_phenomena": handle_ice_phenomena,
}

__all__ = ["HANDLERS", "VERSION"]
