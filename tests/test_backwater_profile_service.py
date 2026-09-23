"""
tests/test_backwater_profile_service.py
P3.1 — multi-reach backwater profile: equivalence to core, junction continuity,
validation errors, AST dependency guard.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.hydraulics_profile import Reach, route_backwater_profile
from core.hydrorash.backwater import backwater_curve_step
from core.services.backwater_profile_service import (
    BACKWATER_PROFILE_PROVENANCE,
    BackwaterProfileError,
    BackwaterProfileRequest,
    BackwaterProfileService,
    ReachSpec,
)

# Single-reach fixture: matches backwater_curve_step defaults closely.
_SINGLE = ReachSpec(name="r1", B=20.0, m=2.0, n=0.035, slope=0.001, L=1000.0)
_Q = 50.0
_H0 = 5.0
_DX = 100.0


def _request(*reach_specs: ReachSpec, q: float = _Q, h0: float = _H0, dx: float = _DX):
    return BackwaterProfileRequest(
        reaches=list(reach_specs), Q=q, H_downstream=h0, dx=dx
    )


# ---------------------------------------------------------------------------
# Core equivalence: single reach must match backwater_curve_step bit-for-bit
# ---------------------------------------------------------------------------
def test_single_reach_equals_core_backwater_curve_step():
    expected = backwater_curve_step(
        Q=_Q,
        B=_SINGLE.B,
        m=_SINGLE.m,
        n=_SINGLE.n,
        I=_SINGLE.slope,
        L_total=_SINGLE.L,
        dx=_DX,
        H_downstream=_H0,
    )
    result = route_backwater_profile(
        reaches=[
            Reach(
                name="r1",
                B=_SINGLE.B,
                m=_SINGLE.m,
                n=_SINGLE.n,
                slope=_SINGLE.slope,
                L=_SINGLE.L,
            )
        ],
        q=_Q,
        h_downstream=_H0,
        dx=_DX,
    )
    # Single reach: global series is exactly the core series.
    assert result["distances_m"] == expected["distances_m"]
    assert result["depths_m"] == expected["depths_m"]
    assert result["L_total_m"] == _SINGLE.L
    # Per-reach block mirrors core depths.
    block = result["reaches"][0]
    assert block["depths_m"] == expected["depths_m"]
    assert block["normal_depth"] == expected["normal_depth"]


def test_service_single_reach_provenance_and_dict():
    service_result = BackwaterProfileService.run(_request(_SINGLE))
    assert service_result.provenance == BACKWATER_PROFILE_PROVENANCE
    d = service_result.to_dict()
    assert d["Q"] == _Q
    assert d["H_downstream"] == _H0
    assert d["L_total_m"] == _SINGLE.L
    assert d["provenance"] == BACKWATER_PROFILE_PROVENANCE
    # JSON-safe: all floats/strings/lists.
    assert all(isinstance(x, float) for x in d["distances_m"])
    assert all(isinstance(x, float) for x in d["depths_m"])


# ---------------------------------------------------------------------------
# Multi-reach junction continuity
# ---------------------------------------------------------------------------
def test_two_reaches_junction_depth_continuity():
    down = ReachSpec(name="lower", B=20.0, m=2.0, n=0.035, slope=0.001, L=500.0)
    up = ReachSpec(name="upper", B=15.0, m=1.5, n=0.04, slope=0.002, L=500.0)
    result = BackwaterProfileService.run(_request(down, up))

    assert len(result.reaches) == 2
    lower, upper = result.reaches
    # Control depth passed into reach 2 = exit depth of reach 1
    # (core then starts at max(control, 1.1·h_n) — so first point ≥ control).
    junction_from_lower = lower["depths_m"][-1]
    assert lower["junction_depth"] == pytest.approx(junction_from_lower, abs=1e-6)
    assert upper["depths_m"][0] >= junction_from_lower - 1e-9
    # Global length is the sum.
    assert result.L_total_m == pytest.approx(down.L + up.L, abs=1e-9)
    # Global distances are non-decreasing and start at 0.
    assert result.distances_m[0] == 0.0
    assert all(
        result.distances_m[i] <= result.distances_m[i + 1]
        for i in range(len(result.distances_m) - 1)
    )
    # No duplicated junction point in the global series.
    assert result.distances_m.count(lower["L"]) <= 1


def test_three_reaches_normal_depth_per_reach():
    reaches = [
        ReachSpec(name="a", B=20.0, m=2.0, n=0.035, slope=0.001, L=400.0),
        ReachSpec(name="b", B=25.0, m=2.5, n=0.03, slope=0.0015, L=400.0),
        ReachSpec(name="c", B=18.0, m=1.0, n=0.04, slope=0.0008, L=400.0),
    ]
    result = BackwaterProfileService.run(_request(*reaches))
    assert len(result.reaches) == 3
    for block in result.reaches:
        assert block["normal_depth"] > 0
        assert len(block["depths_m"]) == len(block["distances_m"])
        assert block["depths_m"][0] > 0


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------
def test_empty_reaches_error():
    with pytest.raises(BackwaterProfileError, match="пролётов пуст"):
        BackwaterProfileService.run(_request())


def test_non_positive_q_error():
    with pytest.raises(BackwaterProfileError, match="Q"):
        BackwaterProfileService.run(_request(_SINGLE, q=0.0))


def test_negative_h0_error():
    with pytest.raises(BackwaterProfileError, match="H_downstream"):
        BackwaterProfileService.run(_request(_SINGLE, h0=-1.0))


def test_bad_geometry_error():
    bad = ReachSpec(name="bad", B=0.0, m=2.0, n=0.035, slope=0.001, L=100.0)
    with pytest.raises(BackwaterProfileError, match="B"):
        BackwaterProfileService.run(_request(bad))


def test_duplicate_names_error():
    a = ReachSpec(name="same", B=20.0, m=2.0, n=0.035, slope=0.001, L=100.0)
    with pytest.raises(BackwaterProfileError, match="уникальны"):
        BackwaterProfileService.run(_request(a, a))


def test_empty_name_error():
    nameless = ReachSpec(name="", B=20.0, m=2.0, n=0.035, slope=0.001, L=100.0)
    with pytest.raises(BackwaterProfileError, match="имя"):
        BackwaterProfileService.run(_request(nameless))


def test_core_empty_reaches_value_error():
    with pytest.raises(ValueError, match="non-empty"):
        route_backwater_profile(reaches=[], q=_Q, h_downstream=_H0)


def test_reach_validate_negative_l():
    r = Reach(name="x", B=10.0, m=1.0, n=0.03, slope=0.001, L=-1.0)
    with pytest.raises(ValueError, match="L"):
        r.validate()


# ---------------------------------------------------------------------------
# AST guard: service must not import banned heavy / non-core deps
# ---------------------------------------------------------------------------
def test_service_ast_no_banned_deps():
    service_path = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "services"
        / "backwater_profile_service.py"
    )
    source = service_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    banned = {"PyQt6", "pyqt", "matplotlib", "requests", "flask", "django"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
            imported.add(node.module)
    top_levels = {name.split(".")[0] for name in imported}
    assert not (top_levels & banned), f"banned imports: {top_levels & banned}"
    unexpected = top_levels - {"__future__", "dataclasses", "typing", "core"}
    assert not unexpected, f"unexpected import roots: {unexpected}"
    assert "core.hydraulics_profile" in imported or "core" in imported
