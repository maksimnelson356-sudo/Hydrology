"""Поправки дисперсии по СП 33-101-2003, п. 6.17."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

__all__ = ["apply_formula_6_9", "apply_formula_6_10"]


def _finite_vector(values: NDArray[np.float64], name: str) -> NDArray[np.float64]:
    vector = np.asarray(values, dtype=float)
    if vector.ndim != 1 or vector.size == 0:
        raise ValueError(f"{name} должен быть непустым одномерным массивом")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} должен содержать только конечные значения")
    return vector


def apply_formula_6_9(
    values: NDArray[np.float64],
    mean_n: float,
    correlation: float,
) -> NDArray[np.float64]:
    """``Q'ᵢ = (Qᵢ - Q̄n) / R + Q̄n`` — формула 6.9 СП 33."""
    restored = _finite_vector(values, "Массив восстановленных значений")
    if not np.isfinite(mean_n):
        raise ValueError("Среднее Q̄n должно быть конечным")
    if not np.isfinite(correlation) or not 0.0 < correlation <= 1.0:
        raise ValueError("Коэффициент R должен быть в диапазоне (0, 1]")

    return (restored - float(mean_n)) / float(correlation) + float(mean_n)


def apply_formula_6_10(
    values: NDArray[np.float64],
    correlation: float,
    sigma: float,
    phi: NDArray[np.float64],
) -> NDArray[np.float64]:
    """``Q'ᵢ = Qᵢ + φσ√(1 - R²)`` — формула 6.10 СП 33."""
    restored = _finite_vector(values, "Массив восстановленных значений")
    normal_draws = _finite_vector(phi, "Массив φ")
    if normal_draws.size != restored.size:
        raise ValueError("Массив φ должен совпадать по длине с restored")
    if not np.isfinite(correlation) or not 0.0 <= correlation <= 1.0:
        raise ValueError("Коэффициент R должен быть в диапазоне [0, 1]")
    if not np.isfinite(sigma) or sigma <= 0.0:
        raise ValueError("Среднее квадратическое отклонение σ должно быть > 0")

    correction = float(sigma) * np.sqrt(1.0 - float(correlation) ** 2)
    return restored + normal_draws * correction
