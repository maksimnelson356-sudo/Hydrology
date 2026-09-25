"""Typed manifest parsing for the SP 33 A.8 importer."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class A8ImportError(ValueError):
    """Invalid A.8 manifest or observation input."""

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"{field}: {reason}")
        self.field = field
        self.reason = reason


@dataclass(frozen=True, slots=True)
class A8Period:
    """Inclusive year period."""

    start: int
    end: int

    def years(self) -> tuple[int, ...]:
        """Return all years in the inclusive period."""
        return tuple(range(self.start, self.end + 1))


@dataclass(frozen=True, slots=True)
class A8Equation:
    """One published A.8 regression equation and its target periods."""

    identifier: str
    formula: str
    analog_numbers: tuple[int, ...]
    target_periods: tuple[A8Period, ...]


@dataclass(frozen=True, slots=True)
class A8Manifest:
    """Typed subset of the A.8 manifest needed by the importer."""

    subject_id: str
    subject_name: str
    subject_area_km2: float
    observed_period: A8Period
    analog_areas: Mapping[int, float]
    analog_aliases: Mapping[str, str]
    equations: tuple[A8Equation, ...]


def _error(field: str, reason: str) -> A8ImportError:
    return A8ImportError(field=field, reason=reason)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _error(field, "ожидается объект")
    return value


def _period(value: Any, field: str) -> A8Period:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if len(value) != 2:
            raise _error(field, "ожидается [start, end]")
        try:
            start = int(value[0])
            end = int(value[1])
        except (TypeError, ValueError) as error:
            raise _error(field, "период должен содержать целые годы") from error
    else:
        data = _mapping(value, field)
        try:
            start = int(data["start"])
            end = int(data["end"])
        except (KeyError, TypeError, ValueError) as error:
            raise _error(field, "нужен start/end") from error
    if end < start:
        raise _error(field, "end должен быть не меньше start")
    return A8Period(start=start, end=end)


def parse_manifest(payload: Mapping[str, Any]) -> A8Manifest:
    """Parse the checked A.8 manifest into typed importer metadata."""
    subject = _mapping(payload.get("subject"), "subject")
    subject_id = str(subject.get("id", "")).strip()
    if not subject_id:
        raise _error("subject.id", "идентификатор обязателен")
    try:
        subject_area = float(subject["catchment_area_km2"])
        observed_period = _period(subject["observed_period"], "subject.observed_period")
    except (KeyError, TypeError, ValueError) as error:
        raise _error("subject", "некорректные площадь или период") from error
    if not math.isfinite(subject_area) or subject_area <= 0:
        raise _error("subject.catchment_area_km2", "площадь должна быть положительной")

    analog_areas: dict[int, float] = {}
    analog_aliases: dict[str, str] = {}
    for index, raw_analog in enumerate(payload.get("analogs", [])):
        analog = _mapping(raw_analog, f"analogs[{index}]")
        number = int(analog.get("number", -1))
        identifier = str(analog.get("id", "")).strip()
        name = str(analog.get("name", "")).strip()
        try:
            area = float(analog["area_km2"])
        except (KeyError, TypeError, ValueError) as error:
            raise _error(f"analogs[{index}].area_km2", "ожидается число") from error
        if number < 1 or number > 7 or not identifier or not math.isfinite(area) or area <= 0:
            raise _error(f"analogs[{index}]", "некорректный номер, id или площадь")
        canonical = f"q{number}"
        analog_areas[number] = area
        analog_aliases[canonical] = canonical
        analog_aliases[identifier] = canonical
        if name:
            analog_aliases[name] = canonical

    raw_equations = payload.get("equations")
    if not isinstance(raw_equations, Sequence) or isinstance(raw_equations, (str, bytes)):
        raise _error("equations", "ожидается список")
    equations: list[A8Equation] = []
    for index, raw_equation in enumerate(raw_equations):
        equation = _mapping(raw_equation, f"equations[{index}]")
        coefficients = _mapping(
            equation.get("coefficients"), f"equations[{index}].coefficients"
        )
        numbers = tuple(
            sorted(int(key[1:]) for key in coefficients if str(key).startswith("q"))
        )
        if not numbers or any(number not in analog_areas for number in numbers):
            raise _error(f"equations[{index}].coefficients", "неизвестный аналог")
        raw_periods = equation.get("target_periods")
        if not isinstance(raw_periods, Sequence) or isinstance(raw_periods, (str, bytes)):
            raise _error(f"equations[{index}].target_periods", "ожидается список периодов")
        periods = tuple(
            _period(period, f"equations[{index}].target_periods[{period_index}]")
            for period_index, period in enumerate(raw_periods)
        )
        identifier = str(equation.get("id", "")).strip()
        formula = str(equation.get("formula", "")).strip()
        if not identifier or not formula or not periods:
            raise _error(f"equations[{index}]", "нужны id, formula и периоды")
        equations.append(
            A8Equation(
                identifier=identifier,
                formula=formula,
                analog_numbers=numbers,
                target_periods=periods,
            )
        )

    return A8Manifest(
        subject_id=subject_id,
        subject_name=str(subject.get("name", subject_id)),
        subject_area_km2=subject_area,
        observed_period=observed_period,
        analog_areas=analog_areas,
        analog_aliases=analog_aliases,
        equations=tuple(equations),
    )


def load_manifest(path: str | Path) -> A8Manifest:
    """Load and parse a JSON A.8 manifest."""
    manifest_path = Path(path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise _error(str(manifest_path), "не удалось прочитать JSON manifest") from error
    return parse_manifest(_mapping(payload, "manifest"))


__all__ = [
    "A8Equation",
    "A8ImportError",
    "A8Manifest",
    "A8Period",
    "load_manifest",
    "parse_manifest",
]
