"""
core/hydraulics_profile.py
Multi-reach backwater profile (stage P3.1).

Chains the existing single-reach ``backwater_curve_step`` (direct step method)
along a sequence of trapezoidal reaches with different geometry (B, m, n, I, L).
Depth continuity is enforced at junctions: the exit depth of reach *i* becomes
the downstream control depth of reach *i+1*.

The core single-reach solver in ``core.hydrorash.backwater`` is NOT modified —
this module only calls it. No new runtime dependencies (stdlib + numpy already
used by the backwater core).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.hydrorash.backwater import backwater_curve_step, normal_depth

__all__ = [
    "Reach",
    "route_backwater_profile",
]


@dataclass(frozen=True)
class Reach:
    """One trapezoidal reach of the river profile (ordered downstream → upstream)."""

    name: str
    B: float
    m: float
    n: float
    #: Bed slope (dimensionless); named ``slope`` to satisfy lint (core uses ``I``).
    slope: float
    L: float

    def validate(self) -> None:
        """Raise ValueError on non-physical geometry."""
        if not self.name:
            raise ValueError("Reach name must be non-empty")
        if self.B <= 0:
            raise ValueError(f"Reach {self.name!r}: B must be > 0 (got {self.B})")
        if self.m < 0:
            raise ValueError(f"Reach {self.name!r}: m must be >= 0 (got {self.m})")
        if self.n <= 0:
            raise ValueError(f"Reach {self.name!r}: n must be > 0 (got {self.n})")
        if self.slope <= 0:
            raise ValueError(f"Reach {self.name!r}: slope must be > 0 (got {self.slope})")
        if self.L <= 0:
            raise ValueError(f"Reach {self.name!r}: L must be > 0 (got {self.L})")


def route_backwater_profile(
    reaches: list[Reach],
    q: float,
    h_downstream: float,
    dx: float = 100.0,
) -> dict[str, Any]:
    """
    Compute a multi-reach water surface profile from a downstream control depth.

    Reaches are ordered **downstream → upstream** (first reach starts at the
    control section, e.g. a reservoir). For each reach the existing
    ``backwater_curve_step`` is called; the exit depth of reach *i* becomes
    the downstream control of reach *i+1*.

    Note: the core solver starts each reach at ``max(H_downstream, 1.1·h_n)``
    (same as single-reach mode); junction continuity is on the *control depth
    passed in*, not necessarily on the first stored point of the next block.

    Parameters:
        reaches: non-empty list of Reach, ordered downstream → upstream.
        q: discharge through all reaches, m³/s (same q for continuity).
        h_downstream: control depth at the downstream end of the first reach, m.
        dx: step length along each reach, m (passed to backwater_curve_step).

    Returns:
        Dict with reaches (per-block), global distances_m / depths_m,
        L_total_m, q, h_downstream, method provenance string.

    Raises:
        ValueError: empty reaches, q <= 0, h_downstream < 0, dx <= 0,
            or invalid reach geometry (delegated to Reach.validate).
    """
    if not reaches:
        raise ValueError("reaches must be a non-empty list")
    if q <= 0:
        raise ValueError(f"q must be > 0 (got {q})")
    if h_downstream < 0:
        raise ValueError(f"h_downstream must be >= 0 (got {h_downstream})")
    if dx <= 0:
        raise ValueError(f"dx must be > 0 (got {dx})")

    global_distances: list[float] = []
    global_depths: list[float] = []
    reach_blocks: list[dict[str, Any]] = []
    offset = 0.0
    control_h = float(h_downstream)

    for reach in reaches:
        reach.validate()
        block = backwater_curve_step(
            Q=q,
            B=reach.B,
            m=reach.m,
            n=reach.n,
            I=reach.slope,
            L_total=reach.L,
            dx=dx,
            H_downstream=control_h,
        )
        h_n = normal_depth(q, reach.B, reach.m, reach.n, reach.slope)
        dists = block["distances_m"]
        depths = block["depths_m"]

        # Junction control for the next reach: exit depth of this reach.
        junction_h = float(depths[-1]) if depths else control_h

        # Concatenate with global offset (skip first point of every reach
        # after the first to avoid duplicating the junction distance).
        start = 1 if reach_blocks else 0
        for i in range(start, len(dists)):
            global_distances.append(offset + dists[i])
            global_depths.append(depths[i])

        reach_blocks.append(
            {
                "name": reach.name,
                "distances_m": [offset + d for d in dists],
                "depths_m": list(depths),
                "normal_depth": round(float(h_n), 3),
                "L": reach.L,
                "B": reach.B,
                "m": reach.m,
                "n": reach.n,
                "slope": reach.slope,
                "junction_depth": round(junction_h, 3),
            }
        )
        offset += reach.L
        control_h = junction_h

    return {
        "reaches": reach_blocks,
        "distances_m": global_distances,
        "depths_m": global_depths,
        "L_total_m": offset,
        "Q": q,
        "H_downstream": h_downstream,
        "method": "backwater_profile@1.0",
    }
