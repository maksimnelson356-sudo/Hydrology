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
        show_warnings=False,
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


# ----------------------------------------------------------------------
# Registry: methodology id -> handler
# ----------------------------------------------------------------------
HANDLERS: dict[str, Any] = {
    "stats_parameters": handle_stats_parameters,
    "frequency_pearson3": handle_frequency_pearson3,
    "frequency_kritsky_menkel": handle_frequency_kritsky_menkel,
    "homogeneity_full": handle_homogeneity_full,
    "trends_full": handle_trends_full,
    "max_runoff": handle_max_runoff,
    "min_runoff": handle_min_runoff,
    "flow_duration": handle_flow_duration,
    "reservoir_regulation": handle_reservoir_regulation,
}

__all__ = ["HANDLERS", "VERSION"]
