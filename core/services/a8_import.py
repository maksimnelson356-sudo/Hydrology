"""Import and normalize external observations for the SP 33 A.8 example."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import pandas as pd  # noqa: F401  # noqa: PANDAS_OK

from core.services.a8_import_manifest import (
    A8Equation,
    A8ImportError,
    A8Manifest,
    A8Period,
    load_manifest,
    parse_manifest,
)

Q_UNITS = {"l/s/km2", "л/с·км2", "л/с/км2", "l/s/km^2"}
Q_RATE_UNITS = {"m3/s", "м3/с"}


def _error(field: str, reason: str) -> A8ImportError:
    return A8ImportError(field=field, reason=reason)


def _canonical_series(series_id: str, manifest: A8Manifest) -> str:
    normalized = series_id.strip()
    if normalized in {manifest.subject_id, "subject", "main"}:
        return manifest.subject_id
    canonical = manifest.analog_aliases.get(normalized)
    if canonical is None:
        raise _error("series_id", f"неизвестный ряд: {normalized}")
    return canonical


def _unit_key(value: Any) -> str:
    return str(value).strip().lower().replace("³", "3").replace("²", "2").replace(" ", "")


def _unit_kind(unit: Any) -> str:
    unit_key = _unit_key(unit)
    if unit_key in {"q", "q_l_s_km2"} or unit_key in Q_UNITS:
        return "q"
    if unit_key in {"q_m3_s", "discharge"} or unit_key in Q_RATE_UNITS:
        return "Q"
    raise _error("unit", "ожидается q (л/с·км²) или Q (м³/с)")


def _q_value(value: Any, unit: Any, area_km2: float, field: str) -> float:
    unit_kind = _unit_kind(unit)
    if value is None or (isinstance(value, float) and math.isnan(value)):
        raise _error(field, "значение отсутствует")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as error:
        raise _error(field, "значение должно быть числом") from error
    if not math.isfinite(numeric):
        raise _error(field, "значение должно быть конечным")
    # Отрицательные значения НЕ отклоняются: пайплайн штатно выбрасывает их
    # через exclude_negative, и синтетические ряды в тестах их дают. Отказ здесь
    # ломал бы замысел. Проблема была не в допуске, а в молчании — поэтому
    # отрицательные перечисляются в observation_report.
    if unit_kind == "Q":
        return numeric * 1000.0 / area_km2
    return numeric


def _year(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise _error(field, "год должен быть целым")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as error:
        raise _error(field, "год должен быть числом") from error
    if not math.isfinite(numeric) or not numeric.is_integer():
        raise _error(field, "год должен быть целым")
    return int(numeric)


def normalize_observations(
    frame: pd.DataFrame,
    manifest: A8Manifest,
) -> dict[str, dict[int, float]]:
    """Normalize long-form q/Q observations to q series keyed by year."""
    required_columns = {"series_id", "year", "value", "unit"}
    missing = required_columns - set(frame.columns)
    if missing:
        raise _error("input", f"отсутствуют колонки: {', '.join(sorted(missing))}")
    areas = {manifest.subject_id: manifest.subject_area_km2}
    areas.update({f"q{number}": area for number, area in manifest.analog_areas.items()})
    result: dict[str, dict[int, float]] = {}
    seen: set[tuple[str, int]] = set()

    for row_index, row in frame.iterrows():
        field = f"rows[{row_index}]"
        canonical = _canonical_series(str(row["series_id"]), manifest)
        year = _year(row["year"], f"{field}.year")
        key = (canonical, year)
        if key in seen:
            raise _error(f"{field}.year", f"дубликат года {year} для {canonical}")
        seen.add(key)
        raw_value = row["value"]
        if pd.isna(raw_value) or str(raw_value).strip() == "":
            continue
        normalized = _q_value(raw_value, row["unit"], areas[canonical], f"{field}.value")
        result.setdefault(canonical, {})[year] = normalized
    return result


def required_year_gaps(
    observations: Mapping[str, Mapping[int, float]],
    manifest: A8Manifest,
) -> dict[str, list[int]]:
    """Return missing years required by the strict A.8 workflow."""
    required_fit_years = set(manifest.observed_period.years())
    gaps: dict[str, set[int]] = {}
    subject = observations.get(manifest.subject_id, {})
    missing_subject = required_fit_years - subject.keys()
    if missing_subject:
        gaps[manifest.subject_id] = set(missing_subject)
    for equation in manifest.equations:
        target_years = {
            year for period in equation.target_periods for year in period.years()
        }
        for number in equation.analog_numbers:
            canonical = f"q{number}"
            values = observations.get(canonical, {})
            missing = (required_fit_years | target_years) - values.keys()
            if missing:
                gaps.setdefault(canonical, set()).update(missing)
    ordered: dict[str, list[int]] = {}
    if manifest.subject_id in gaps:
        ordered[manifest.subject_id] = sorted(gaps[manifest.subject_id])
    for key in sorted(gaps):
        if key != manifest.subject_id:
            ordered[key] = sorted(gaps[key])
    return ordered


def required_analog_coverage(manifest: A8Manifest) -> dict[int, tuple[int, ...]]:
    """Return the years each analog must cover, derived from the equations.

    An analog is required for every year of the subject's observed period (the
    fit window) plus every year its equations restore. Windows may be
    discontinuous, so the full year set is returned rather than a range.
    """
    fit_years = set(manifest.observed_period.years())
    coverage: dict[int, set[int]] = {}
    for equation in manifest.equations:
        target_years = {
            year for period in equation.target_periods for year in period.years()
        }
        for number in equation.analog_numbers:
            coverage.setdefault(number, set()).update(fit_years | target_years)
    return {
        number: tuple(sorted(years))
        for number, years in sorted(coverage.items())
    }


def published_coverage_conflicts(manifest: A8Manifest) -> dict[int, dict[str, int]]:
    """Compare required analog coverage with the published record lengths.

    Table A.6 states how many years each analog observed. When the equations
    demand more years than the standard says exist, the standard's own example
    is internally inconsistent. This is reported rather than silently accepted,
    because importing such a scenario cannot be independently reproduced.
    """
    conflicts: dict[int, dict[str, int]] = {}
    for number, years in required_analog_coverage(manifest).items():
        published = manifest.analog_observation_years.get(number)
        if published is not None and published < len(years):
            conflicts[number] = {
                "required_years": len(years),
                "published_years": published,
                "shortfall": len(years) - published,
            }
    return conflicts


def observation_report(
    frame: pd.DataFrame,
    manifest: A8Manifest,
    observations: Mapping[str, Mapping[int, float]] | None = None,
) -> dict[str, Any]:
    """Summarize row counts, source units, and required-year gaps."""
    normalized = observations or normalize_observations(frame, manifest)
    series_counts: dict[str, int] = {}
    unit_counts = {"q": 0, "Q": 0}
    for _, row in frame.iterrows():
        canonical = _canonical_series(str(row["series_id"]), manifest)
        raw_value = row["value"]
        if pd.isna(raw_value) or str(raw_value).strip() == "":
            continue
        series_counts[canonical] = series_counts.get(canonical, 0) + 1
        unit_counts[_unit_kind(row["unit"])] += 1
    # Пайплайн выбрасывает отрицательные значения (exclude_negative), поэтому
    # они должны быть видны: раньше они исчезали молча, и опечатку в знаке
    # заподозрить было негде.
    negative_values = {
        series_id: sorted(year for year, value in by_year.items() if value < 0.0)
        for series_id, by_year in normalized.items()
    }
    negative_values = {
        series_id: years
        for series_id, years in sorted(negative_values.items())
        if years
    }
    return {
        "input_rows": len(frame),
        "series_counts": dict(sorted(series_counts.items())),
        "unit_counts": unit_counts,
        "negative_values_excluded": negative_values,
        "missing_required_years": required_year_gaps(normalized, manifest),
        "published_coverage_conflicts": {
            f"q{number}": detail
            for number, detail in published_coverage_conflicts(manifest).items()
        },
    }


def validate_required_observations(
    observations: Mapping[str, Mapping[int, float]],
    manifest: A8Manifest,
) -> None:
    """Ensure strict imports can run every manifest stage."""
    gaps = required_year_gaps(observations, manifest)
    for series_id, missing in gaps.items():
        field = "subject" if series_id == manifest.subject_id else series_id
        raise _error(field, f"отсутствуют годы: {missing}")


def _stage_config(
    observations: Mapping[str, Mapping[int, float]],
    manifest: A8Manifest,
) -> dict[str, Any]:
    fit_years = list(manifest.observed_period.years())
    stages: list[dict[str, Any]] = []
    for equation in manifest.equations:
        analogs = {}
        for number in equation.analog_numbers:
            canonical = f"q{number}"
            values = observations.get(canonical, {})
            analogs[canonical] = {
                str(year): values[year] for year in sorted(values)
            }
        target_years = [
            year for period in equation.target_periods for year in period.years()
        ]
        stages.append(
            {
                "name": equation.identifier,
                "analogs": analogs,
                "fit_years": fit_years,
                "target_years": target_years,
                "ro_cr": 0.6,
            }
        )
    return {"stages": stages, "exclude_negative": True}


def build_primary_payload(
    observations: Mapping[str, Mapping[int, float]],
    manifest: A8Manifest,
) -> dict[str, Any]:
    """Build the JSON dataset consumed by the methodology CLI."""
    values = observations.get(manifest.subject_id, {})
    observed_values = {
        year: values[year]
        for year in manifest.observed_period.years()
        if year in values
    }
    return {
        "schema_version": "1.0",
        "name": manifest.subject_name,
        "unit": "л/с·км²",
        "catchment_area_km2": manifest.subject_area_km2,
        "data": {str(year): observed_values[year] for year in sorted(observed_values)},
        "source_variable": "q",
    }


def build_import_artifacts(
    frame: pd.DataFrame,
    manifest: A8Manifest,
    strict: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Normalize input and build staged config plus primary JSON payload."""
    observations = normalize_observations(frame, manifest)
    if strict:
        validate_required_observations(observations, manifest)
    config = _stage_config(observations, manifest)
    report = observation_report(frame, manifest, observations)
    config["metadata"] = {
        "source_manifest": "sp33_a8_manifest_v1.json",
        "normalized_variable": "q",
        "strict": strict,
        "evidence_status": manifest.evidence_status,
        "observation_report": report,
    }
    primary = build_primary_payload(observations, manifest)
    primary["observation_report"] = report
    return config, primary


__all__ = [
    "A8Equation",
    "A8ImportError",
    "A8Manifest",
    "A8Period",
    "build_import_artifacts",
    "build_primary_payload",
    "load_manifest",
    "normalize_observations",
    "observation_report",
    "parse_manifest",
    "published_coverage_conflicts",
    "required_analog_coverage",
    "required_year_gaps",
    "validate_required_observations",
]
