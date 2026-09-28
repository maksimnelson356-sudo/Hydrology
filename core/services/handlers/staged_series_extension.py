"""Service adapter for the staged series-extension workflow."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd  # noqa: F401  # noqa: PANDAS_OK

from core.services.calculation_service import CalculationContext
from core.stats.staged_series_extension import (
    AnalogExtensionStage,
    staged_multi_analog_extension,
)


@dataclass(frozen=True, slots=True)
class StagedSeriesConfigurationError(ValueError):
    """Invalid staged series-extension configuration."""

    field: str
    reason: str

    def __str__(self) -> str:
        """Return a field-qualified configuration error."""
        return f"{self.field}: {self.reason}"


def _configuration_error(field: str, reason: str) -> StagedSeriesConfigurationError:
    return StagedSeriesConfigurationError(field=field, reason=reason)


def _parse_year(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise _configuration_error(field, "год должен быть целым числом")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as error:
        raise _configuration_error(field, "год должен быть числом") from error
    if not math.isfinite(numeric) or not numeric.is_integer():
        raise _configuration_error(field, "год должен быть целым числом")
    return int(numeric)


def _parse_years(value: Any, field: str) -> tuple[int, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise _configuration_error(field, "ожидается список годов")
    years = tuple(_parse_year(item, f"{field}[{index}]") for index, item in enumerate(value))
    if not years:
        raise _configuration_error(field, "список годов не может быть пустым")
    return years


def _parse_positive_number(value: Any, field: str, default: float) -> float:
    if value is None:
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError) as error:
        raise _configuration_error(field, "ожидается число") from error
    if not math.isfinite(numeric) or numeric <= 0.0:
        raise _configuration_error(field, "значение должно быть положительным")
    return numeric


def _parse_analog(name: str, value: Any, field: str) -> pd.Series:
    match value:  # noqa: F401  # noqa: MATCH_OK
        case pd.Series():
            series = value.astype(float).copy()
        case Mapping():
            values: dict[int, float] = {}
            for raw_year, raw_value in value.items():
                year = _parse_year(raw_year, f"{field}.{name}.year")
                if raw_value is None:
                    continue
                try:
                    numeric = float(raw_value)
                except (TypeError, ValueError) as error:
                    raise _configuration_error(
                        f"{field}.{name}",
                        "значение аналога должно быть числом",
                    ) from error
                if math.isfinite(numeric):
                    values[year] = numeric
            series = pd.Series(values, dtype=float, name=name)
        case _:
            raise _configuration_error(
                field,
                f"аналог {name!r} должен быть объектом year->value",
            )

    if series.empty:
        raise _configuration_error(f"{field}.{name}", "аналог не содержит числовых значений")
    try:
        series.index = pd.Index([_parse_year(year, f"{field}.{name}.year") for year in series.index])
    except (TypeError, ValueError) as error:
        raise _configuration_error(f"{field}.{name}", "годы аналога должны быть целыми") from error
    return series.dropna()


def _parse_stage(value: Any, index: int) -> AnalogExtensionStage:
    field = f"stages[{index}]"
    if not isinstance(value, Mapping):
        raise _configuration_error(field, "этап должен быть объектом")

    name = value.get("name")
    if not isinstance(name, str) or not name.strip():
        raise _configuration_error(f"{field}.name", "название этапа обязательно")

    raw_analogs = value.get("analogs")
    if not isinstance(raw_analogs, Mapping) or not raw_analogs:
        raise _configuration_error(f"{field}.analogs", "нужен непустой объект аналогов")
    analogs = {
        str(analog_name): _parse_analog(str(analog_name), analog_value, f"{field}.analogs")
        for analog_name, analog_value in raw_analogs.items()
    }

    target_years = _parse_years(value.get("target_years"), f"{field}.target_years")
    raw_fit_years = value.get("fit_years")
    fit_years = (
        None
        if raw_fit_years is None
        else _parse_years(raw_fit_years, f"{field}.fit_years")
    )

    raw_n_min = value.get("n_min", 6)
    try:
        n_min = int(raw_n_min)
    except (TypeError, ValueError) as error:
        raise _configuration_error(f"{field}.n_min", "ожидается целое число") from error
    if n_min < 2:
        raise _configuration_error(f"{field}.n_min", "минимум должен быть не меньше 2")

    ro_cr = _parse_positive_number(value.get("ro_cr"), f"{field}.ro_cr", 0.7)
    if ro_cr > 1.0:
        raise _configuration_error(f"{field}.ro_cr", "порог корреляции должен быть не больше 1")

    variance_correction = value.get("variance_correction", "6.9")
    if not isinstance(variance_correction, str) or variance_correction not in {"6.9", "6.10"}:
        raise _configuration_error(
            f"{field}.variance_correction",
            "допустимы только '6.9' и '6.10'",
        )

    raw_random_state = value.get("random_state")
    if raw_random_state is not None:
        try:
            random_state = int(raw_random_state)
        except (TypeError, ValueError) as error:
            raise _configuration_error(
                f"{field}.random_state",
                "ожидается целое число",
            ) from error
    else:
        random_state = None

    return AnalogExtensionStage(
        name=name.strip(),
        analogs=analogs,
        target_years=target_years,
        fit_years=fit_years,
        n_min=n_min,
        ro_cr=ro_cr,
        ro_over_sigma=_parse_positive_number(
            value.get("ro_over_sigma"), f"{field}.ro_over_sigma", 2.0
        ),
        k_over_sigma=_parse_positive_number(
            value.get("k_over_sigma"), f"{field}.k_over_sigma", 2.0
        ),
        y_over_sigma=_parse_positive_number(
            value.get("y_over_sigma"), f"{field}.y_over_sigma", 0.2
        ),
        variance_correction=str(variance_correction),
        random_state=random_state,
    )


def _parse_stages(value: Any) -> tuple[AnalogExtensionStage, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise _configuration_error("stages", "ожидается непустой список этапов")
    return tuple(_parse_stage(stage, index) for index, stage in enumerate(value))


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, pd.Series):
        return {
            str(year): None if pd.isna(item) else float(item)
            for year, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


# Статус доказательности из манифеста источника -> предупреждение для отчёта.
# Формулировки живут здесь, в доменном слое: отчёт только печатает готовую строку,
# поэтому смена wording не требует правок report_service.
_EVIDENCE_NOTES: dict[str, str] = {
    "partial": (
        "Доказательность сценария частичная: восстановленный ряд опирается на неполное "
        "покрытие наблюдений аналогов и не является независимо верифицированным."
    ),
    "unknown": (
        "Статус доказательности источника не объявлен: восстановленный ряд не проверен "
        "и не должен выдаваться за подтверждённый."
    ),
}
_EVIDENCE_FALLBACK = (
    "Статус доказательности источника: «{status}». Проверьте, соответствует ли он "
    "требуемому уровню обоснованности."
)


def _evidence_note(status: Any) -> str | None:
    """Return a user-facing caveat for a declared evidence status.

    None means the series is declared verified: no caveat is warranted. Unknown
    values are surfaced rather than swallowed, because silence is what made a
    partially supported series indistinguishable from a verified one.
    """
    if not isinstance(status, str):
        return None
    normalized = status.strip()
    if not normalized:
        return None
    if normalized == "published_target_series":
        return None
    return _EVIDENCE_NOTES.get(normalized, _EVIDENCE_FALLBACK.format(status=normalized))


def handle_series_extension_staged(context: CalculationContext) -> dict[str, Any]:
    """Run the staged workflow from a validated service configuration."""
    raw_stages = context.parameters.get("stages")
    if raw_stages is None:
        raise _configuration_error("stages", "обязательный параметр отсутствует")
    exclude_negative = context.parameters.get("exclude_negative", True)
    if not isinstance(exclude_negative, bool):
        raise _configuration_error("exclude_negative", "ожидается boolean")

    observed = pd.Series(
        context.dataset.values,
        index=pd.Index(context.dataset.years, dtype=int),
        name="observed",
        dtype=float,
    )
    result = staged_multi_analog_extension(
        observed,
        _parse_stages(raw_stages),
        exclude_negative=exclude_negative,
    )
    payload = _plain(dict(result))
    status = context.parameters.get("evidence_status")
    if isinstance(status, str) and status.strip():
        payload["evidence_status"] = status.strip()
    note = _evidence_note(status)
    if note:
        payload["evidence_note"] = note
    return payload


__all__ = ["StagedSeriesConfigurationError", "handle_series_extension_staged"]
