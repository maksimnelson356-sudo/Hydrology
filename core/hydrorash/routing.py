"""
core/hydrorash/routing.py
Muskingum flood routing (stage P3.2, decision 11.1 = (a)).

Classical two-parameter Muskingum channel routing:
    O_{n+1} = C0·I_{n+1} + C1·I_n + C2·O_n
    C0 + C1 + C2 = 1

Stability constraints (enforced by callers / service validation):
    0 ≤ C0, C1, C2 ≤ 1  →  K ≥ dt and 0 ≤ x ≤ 0.5.

No new dependencies (pure Python lists / floats).
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "MuskingumError",
    "muskingum_coefficients",
    "muskingum_route",
]


class MuskingumError(ValueError):
    """Invalid Muskingum parameters or hydrograph."""


def muskingum_coefficients(k: float, x: float, dt: float) -> tuple[float, float, float]:
    """
    Compute Muskingum coefficients (C0, C1, C2).

    Parameters:
        k: storage time constant K, hours (must be ≥ dt).
        x: weighting factor (0 ≤ x ≤ 0.5).
        dt: time step, hours (same units as K).

    Returns:
        (C0, C1, C2) with C0+C1+C2 = 1.

    Raises:
        MuskingumError: dt ≤ 0, k < dt, x outside [0, 0.5], or unstable coefficients.
    """
    if dt <= 0:
        raise MuskingumError(f"dt must be > 0 (got {dt})")
    if k < dt:
        raise MuskingumError(f"K must be >= dt (K={k}, dt={dt})")
    if not (0.0 <= x <= 0.5):
        raise MuskingumError(f"x must be in [0, 0.5] (got {x})")

    denom = 2.0 * k * (1.0 - x) + dt
    if denom == 0:
        raise MuskingumError("degenerate Muskingum denominator (2K(1-x)+dt == 0)")

    c0 = (dt - 2.0 * k * x) / denom
    c1 = (dt + 2.0 * k * x) / denom
    c2 = (2.0 * k * (1.0 - x) - dt) / denom

    coeffs = (c0, c1, c2)
    for name, c in zip(("C0", "C1", "C2"), coeffs, strict=True):
        if not (-1e-12 <= c <= 1.0 + 1e-12):
            raise MuskingumError(
                f"unstable coefficient {name}={c:.6f} outside [0,1] "
                f"(K={k}, x={x}, dt={dt})"
            )
    # Clamp tiny float noise into [0,1] and re-normalise to sum exactly 1.
    c0c = max(0.0, min(1.0, c0))
    c1c = max(0.0, min(1.0, c1))
    c2c = 1.0 - c0c - c1c
    if c2c < 0:
        c2c = 0.0
        total = c0c + c1c
        if total > 0:
            c0c, c1c = c0c / total, c1c / total
    return (c0c, c1c, c2c)


def muskingum_route(
    inflow: list[float],
    dt: float,
    k: float,
    x: float,
    outflow0: float | None = None,
) -> dict[str, Any]:
    """
    Route an inflow hydrograph through a Muskingum reach.

    Parameters:
        inflow: inflow series I_0..I_{N-1} (same units throughout, e.g. m³/s).
        dt: time step between samples (hours or any consistent time unit).
        k: storage constant K (same time unit as dt, K ≥ dt).
        x: weighting factor 0 ≤ x ≤ 0.5.
        outflow0: initial outflow O_0; defaults to inflow[0] (steady start).

    Returns:
        Dict with:
        - outflow: list length == len(inflow); outflow[0] = O_0.
        - coefficients: {"C0", "C1", "C2"}.
        - peak_in_m3s / peak_out_m3s / peak_attenuation_m3s / peak_lag_steps.

    Raises:
        MuskingumError: empty/short inflow, non-finite values, bad K/x/dt,
            or unstable coefficients.
    """
    if not inflow:
        raise MuskingumError("inflow must be a non-empty series")
    if len(inflow) < 2:
        raise MuskingumError(f"inflow needs at least 2 points (got {len(inflow)})")
    for i, v in enumerate(inflow):
        if v != v or v in (float("inf"), float("-inf")):
            raise MuskingumError(f"inflow[{i}] is not finite: {v}")
        if v < 0:
            raise MuskingumError(f"inflow[{i}] must be >= 0 (got {v})")

    c0, c1, c2 = muskingum_coefficients(k, x, dt)

    o_prev = float(inflow[0]) if outflow0 is None else float(outflow0)
    if o_prev < 0:
        raise MuskingumError(f"outflow0 must be >= 0 (got {outflow0})")

    outflow: list[float] = [o_prev]
    i_prev = float(inflow[0])
    for i_next in inflow[1:]:
        o_next = c0 * float(i_next) + c1 * i_prev + c2 * o_prev
        # Physical discharge stays non-negative under stable coefficients.
        if o_next < 0:
            o_next = 0.0
        outflow.append(o_next)
        i_prev = float(i_next)
        o_prev = o_next

    peak_in = max(inflow)
    peak_out = max(outflow)
    peak_in_idx = inflow.index(peak_in)
    peak_out_idx = outflow.index(peak_out)
    # Lag measured only if outflow peak occurs at/after inflow peak.
    lag = peak_out_idx - peak_in_idx if peak_out_idx >= peak_in_idx else 0

    return {
        "outflow": outflow,
        "coefficients": {"C0": c0, "C1": c1, "C2": c2},
        "peak_in_m3s": float(peak_in),
        "peak_out_m3s": float(peak_out),
        "peak_attenuation_m3s": float(peak_in - peak_out),
        "peak_lag_steps": int(lag),
    }
