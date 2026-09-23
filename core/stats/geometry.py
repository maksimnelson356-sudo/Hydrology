"""
core/stats/geometry.py
Planar / spherical polygon metrics for basin contours (stage P1.6).

Pure mathematics only: shoelace area, perimeter, vertex centroid.
No GIS stack (decision 9.3 = (b): GeoJSON contours, stdlib + math).
Longitude/latitude rings use a spherical excess approximation; projected
rings (metres) use the planar shoelace formula.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

__all__ = [
    "EARTH_RADIUS_M",
    "polygon_area",
    "polygon_centroid",
    "polygon_perimeter",
]

# Mean Earth radius (IUGG), metres.
EARTH_RADIUS_M = 6_371_008.8

Point = Sequence[float]


def _as_pairs(ring: Sequence[Point]) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for point in ring:
        if len(point) < 2:
            raise ValueError(f"Ring vertex must have at least 2 coords: {point!r}")
        pairs.append((float(point[0]), float(point[1])))
    return pairs


def _open_ring(pairs: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Drop a duplicated closing vertex so shoelace does not double-count."""
    if len(pairs) >= 2 and pairs[0] == pairs[-1]:
        return pairs[:-1]
    return pairs


def _looks_geographic(pairs: Sequence[tuple[float, float]]) -> bool:
    """True when every vertex lies inside lon/lat degree bounds."""
    return all(-180.0 <= x <= 180.0 and -90.0 <= y <= 90.0 for x, y in pairs)


def polygon_perimeter(ring: Sequence[Point]) -> float:
    """
    Perimeter of a closed ring.

    Geographic rings (degrees) → metres on a sphere.
    Projected rings (any other units, treated as metres) → same units.
    """
    pairs = _open_ring(_as_pairs(ring))
    if len(pairs) < 3:
        raise ValueError("Ring needs at least 3 distinct vertices")
    geographic = _looks_geographic(pairs)
    total = 0.0
    n = len(pairs)
    for i in range(n):
        x0, y0 = pairs[i]
        x1, y1 = pairs[(i + 1) % n]
        if geographic:
            total += _haversine_m(x0, y0, x1, y1)
        else:
            total += math.hypot(x1 - x0, y1 - y0)
    return total


def polygon_area(ring: Sequence[Point]) -> float:
    """
    Absolute area enclosed by a ring (non-negative).

    Geographic rings → m² on a sphere (spherical excess / shoelace on lonlat
    scaled by R²). Projected rings → same units² (metres² when coords are metres).
    """
    pairs = _open_ring(_as_pairs(ring))
    if len(pairs) < 3:
        raise ValueError("Ring needs at least 3 distinct vertices")
    if _looks_geographic(pairs):
        return _spherical_area_m2(pairs)
    return abs(_shoelace(pairs))


def polygon_centroid(ring: Sequence[Point]) -> tuple[float, float]:
    """
    Vertex-average centroid (x, y) in the ring's own coordinate system.

    Simple mean of distinct vertices — adequate for basin-summary display;
    not a polygon-area centroid (avoids zero-division on degenerate areas).
    """
    pairs = _open_ring(_as_pairs(ring))
    if not pairs:
        raise ValueError("Ring is empty")
    sx = sum(x for x, _ in pairs)
    sy = sum(y for _, y in pairs)
    n = len(pairs)
    return (sx / n, sy / n)


# ----------------------------------------------------------------------
# Internals
# ----------------------------------------------------------------------
def _shoelace(pairs: Sequence[tuple[float, float]]) -> float:
    total = 0.0
    n = len(pairs)
    for i in range(n):
        x0, y0 = pairs[i]
        x1, y1 = pairs[(i + 1) % n]
        total += x0 * y1 - x1 * y0
    return total / 2.0


def _spherical_area_m2(pairs: Sequence[tuple[float, float]]) -> float:
    """
    Spherical polygon area via the trapezoidal lon-lat formula:

        A = R² · |Σ (λ₁ − λ₀) · (sin φ₁ + sin φ₀)| / 2

    Valid for rings that do not cross the antimeridian (basin contours).
    """
    n = len(pairs)
    total = 0.0
    for i in range(n):
        lon0, lat0 = pairs[i]
        lon1, lat1 = pairs[(i + 1) % n]
        lam0 = math.radians(lon0)
        lam1 = math.radians(lon1)
        phi0 = math.radians(lat0)
        phi1 = math.radians(lat1)
        total += (lam1 - lam0) * (math.sin(phi1) + math.sin(phi0))
    return abs(total) * 0.5 * EARTH_RADIUS_M**2


def _haversine_m(lon0: float, lat0: float, lon1: float, lat1: float) -> float:
    phi0 = math.radians(lat0)
    phi1 = math.radians(lat1)
    dphi = phi1 - phi0
    dlam = math.radians(lon1 - lon0)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi0) * math.cos(phi1) * math.sin(dlam / 2) ** 2
    return 2.0 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))
