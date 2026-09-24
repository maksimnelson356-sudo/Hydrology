"""Pure stage-to-area/volume inundation calculations for HydroSphere P3.3."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

__all__ = [
    "InundationCalculationError",
    "InundationEstimate",
    "StageAreaPoint",
    "inundation_from_stage_area",
    "inundation_from_trapezoid",
]

_TRAPEZOID_CURVE_STEPS: Final = 20


@dataclass(frozen=True, slots=True)
class InundationCalculationError(ValueError):
    """Invalid stage, geometry, or S(H) curve."""

    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True, slots=True)
class StageAreaPoint:
    """One point of the flooded-area curve S(H)."""

    stage_m: float
    area_m2: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.stage_m) or self.stage_m < 0.0:
            raise InundationCalculationError(
                f"Уровень должен быть конечным и >= 0 (получено {self.stage_m})"
            )
        if not math.isfinite(self.area_m2) or self.area_m2 < 0.0:
            raise InundationCalculationError(
                f"Площадь должна быть конечной и >= 0 (получено {self.area_m2})"
            )


@dataclass(frozen=True, slots=True)
class InundationEstimate:
    """Interpolated inundation area and volume at one water level."""

    requested_stage_m: float
    effective_stage_m: float
    area_m2: float
    volume_m3: float
    curve: tuple[StageAreaPoint, ...]
    warnings: tuple[str, ...] = ()


def inundation_from_stage_area(
    stage_m: float,
    points: Sequence[StageAreaPoint],
) -> InundationEstimate:
    """Interpolate S(H) and integrate its volume below the requested level."""
    curve = _validated_curve(points)
    effective_stage = min(_validated_stage(stage_m), curve[-1].stage_m)
    warnings: tuple[str, ...] = ()
    if effective_stage < stage_m:
        warnings = (
            f"Уровень {stage_m:.3f} м выше максимума кривой "
            f"{curve[-1].stage_m:.3f} м; значение ограничено последней точкой.",
        )

    area = _interpolate_area(curve, effective_stage)
    volume = _volume_below(curve, effective_stage)
    return InundationEstimate(
        requested_stage_m=stage_m,
        effective_stage_m=effective_stage,
        area_m2=area,
        volume_m3=volume,
        curve=curve,
        warnings=warnings,
    )


def inundation_from_trapezoid(
    stage_m: float,
    bottom_width_m: float,
    side_slope: float,
) -> InundationEstimate:
    """Evaluate a trapezoidal cross-section analytically."""
    stage = _validated_stage(stage_m)
    if not math.isfinite(bottom_width_m) or bottom_width_m <= 0.0:
        raise InundationCalculationError(
            f"Ширина дна должна быть конечной и > 0 (получено {bottom_width_m})"
        )
    if not math.isfinite(side_slope) or side_slope < 0.0:
        raise InundationCalculationError(
            f"Откос бортов должен быть конечным и >= 0 (получено {side_slope})"
        )

    area = bottom_width_m * stage + side_slope * stage**2
    volume = bottom_width_m * stage**2 / 2.0 + side_slope * stage**3 / 3.0
    curve_max = stage if stage > 0.0 else 1.0
    curve = tuple(
        StageAreaPoint(
            stage_m=curve_max * index / _TRAPEZOID_CURVE_STEPS,
            area_m2=(
                bottom_width_m * (curve_max * index / _TRAPEZOID_CURVE_STEPS)
                + side_slope * (curve_max * index / _TRAPEZOID_CURVE_STEPS) ** 2
            ),
        )
        for index in range(_TRAPEZOID_CURVE_STEPS + 1)
    )
    return InundationEstimate(
        requested_stage_m=stage,
        effective_stage_m=stage,
        area_m2=area,
        volume_m3=volume,
        curve=curve,
    )


def _validated_stage(stage_m: float) -> float:
    if not math.isfinite(stage_m) or stage_m < 0.0:
        raise InundationCalculationError(
            f"Уровень должен быть конечным и >= 0 (получено {stage_m})"
        )
    return float(stage_m)


def _validated_curve(points: Sequence[StageAreaPoint]) -> tuple[StageAreaPoint, ...]:
    if len(points) < 2:
        raise InundationCalculationError("Кривая S(H) должна содержать минимум 2 точки")
    curve = tuple(sorted(points, key=lambda point: point.stage_m))
    for previous, current in zip(curve, curve[1:], strict=False):
        if current.stage_m == previous.stage_m:
            raise InundationCalculationError("Уровни в кривой S(H) должны быть уникальными")
        if current.area_m2 < previous.area_m2:
            raise InundationCalculationError("Площадь в кривой S(H) не должна убывать")
    return curve


def _interpolate_area(curve: tuple[StageAreaPoint, ...], stage_m: float) -> float:
    first = curve[0]
    if stage_m < first.stage_m:
        return first.area_m2 * stage_m / first.stage_m
    for previous, current in zip(curve, curve[1:], strict=False):
        if stage_m <= current.stage_m:
            ratio = (stage_m - previous.stage_m) / (
                current.stage_m - previous.stage_m
            )
            return previous.area_m2 + ratio * (current.area_m2 - previous.area_m2)
    return curve[-1].area_m2


def _volume_below(curve: tuple[StageAreaPoint, ...], stage_m: float) -> float:
    first = curve[0]
    if stage_m <= first.stage_m:
        return 0.5 * first.area_m2 * stage_m

    volume = 0.0
    if first.stage_m > 0.0:
        volume += 0.5 * first.area_m2 * first.stage_m
    for previous, current in zip(curve, curve[1:], strict=False):
        if stage_m >= current.stage_m:
            volume += 0.5 * (previous.area_m2 + current.area_m2) * (
                current.stage_m - previous.stage_m
            )
            continue
        ratio = (stage_m - previous.stage_m) / (current.stage_m - previous.stage_m)
        area = previous.area_m2 + ratio * (current.area_m2 - previous.area_m2)
        volume += 0.5 * (previous.area_m2 + area) * (stage_m - previous.stage_m)
        break
    return volume
