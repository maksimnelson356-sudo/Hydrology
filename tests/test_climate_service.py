"""
tests/test_climate_service.py
Stage P2.3 acceptance tests (DOCS/ROADMAP.md §6.2): delta-change identity,
exact multiplicative ratio, additive mode, empty series errors, Dataset clone
+ ``.hsp``-safe climate metadata, AST no-banned-dependencies guard.

No GUI: only core.domain, core.services, stdlib.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.domain.models import Dataset
from core.services.climate_service import (
    CLIMATE_METADATA_KEY,
    CLIMATE_MODES,
    ClimateError,
    ClimateScenario,
    ClimateService,
)

# ----------------------------------------------------------------------
# Fixtures / helpers
# ----------------------------------------------------------------------

SERIES = {2000: 10.0, 2001: 20.0, 2002: 30.0}


def make_dataset(data: dict[int, float] | None = None) -> Dataset:
    return Dataset(name="Q", data=dict(data if data is not None else SERIES))


# ----------------------------------------------------------------------
# Identity (δ = 0)
# ----------------------------------------------------------------------


def test_zero_delta_multiplicative_is_identity():
    scenario = ClimateScenario(name="none", delta=0.0, mode="multiplicative")
    out = ClimateService.apply_series(SERIES, scenario)
    assert out == SERIES
    assert out is not SERIES  # independent copy


def test_zero_delta_additive_is_identity():
    scenario = ClimateScenario(name="none", delta=0.0, mode="additive")
    out = ClimateService.apply_series(SERIES, scenario)
    assert out == SERIES


# ----------------------------------------------------------------------
# Exact multiplicative ratio (×1.1)
# ----------------------------------------------------------------------


def test_multiplicative_1_1_exact_ratio():
    scenario = ClimateScenario(name="warm", delta=0.1, mode="multiplicative")
    out = ClimateService.apply_series(SERIES, scenario)
    for year, original in SERIES.items():
        assert out[year] == pytest.approx(original * 1.1, rel=1e-12)
    assert out[2000] == pytest.approx(11.0, rel=1e-12)
    assert out[2002] == pytest.approx(33.0, rel=1e-12)


def test_multiplicative_negative_delta_dries():
    scenario = ClimateScenario(name="dry", delta=-0.2, mode="multiplicative")
    out = ClimateService.apply_series(SERIES, scenario)
    assert out[2000] == pytest.approx(8.0, rel=1e-12)


def test_additive_absolute_increment():
    scenario = ClimateScenario(name="shift", delta=5.0, mode="additive")
    out = ClimateService.apply_series(SERIES, scenario)
    assert out[2000] == pytest.approx(15.0, rel=1e-12)
    assert out[2002] == pytest.approx(35.0, rel=1e-12)


# ----------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------


def test_empty_series_rejected():
    scenario = ClimateScenario(name="x", delta=0.1)
    with pytest.raises(ClimateError, match="Пустой ряд"):
        ClimateService.apply_series({}, scenario)


def test_empty_dataset_rejected():
    scenario = ClimateScenario(name="x", delta=0.1)
    with pytest.raises(ClimateError, match="Пустой набор"):
        ClimateService.apply_dataset(make_dataset({}), scenario)


def test_unknown_mode_rejected():
    with pytest.raises(ClimateError, match="Неизвестный режим"):
        ClimateScenario(name="x", delta=0.1, mode="cubic").validate()
    assert "multiplicative" in CLIMATE_MODES and "additive" in CLIMATE_MODES


def test_empty_name_rejected():
    with pytest.raises(ClimateError, match="Имя"):
        ClimateScenario(name="  ", delta=0.1).validate()


def test_nan_delta_rejected():
    with pytest.raises(ClimateError, match="NaN"):
        ClimateScenario(name="x", delta=float("nan")).validate()


def test_non_numeric_delta_rejected():
    with pytest.raises(ClimateError, match="delta"):
        ClimateScenario(name="x", delta="ten").validate()  # type: ignore[arg-type]


def test_nan_series_value_rejected():
    scenario = ClimateScenario(name="x", delta=0.1)
    with pytest.raises(ClimateError, match="Неконечное"):
        ClimateService.apply_series({2000: float("nan")}, scenario)


# ----------------------------------------------------------------------
# Dataset clone + metadata (.hsp-safe)
# ----------------------------------------------------------------------


def test_apply_dataset_does_not_mutate_input():
    ds = make_dataset()
    original = dict(ds.data)
    scenario = ClimateScenario(name="warm", delta=0.1)
    out = ClimateService.apply_dataset(ds, scenario)
    assert ds.data == original
    assert out is not ds
    assert out.data[2000] == pytest.approx(11.0, rel=1e-12)
    assert out.name != ds.name


def test_climate_metadata_roundtrip_json_safe():
    ds = make_dataset()
    scenario = ClimateScenario(name="rcp45", delta=0.05, mode="multiplicative")
    out = ClimateService.apply_dataset(ds, scenario)
    meta = out.metadata[CLIMATE_METADATA_KEY]
    assert meta["delta"] == pytest.approx(0.05)
    assert meta["mode"] == "multiplicative"
    assert meta["method"] == "delta_change@1.0"
    # JSON-safe: only primitives
    import json

    json.dumps(meta)  # must not raise
    restored = ClimateScenario.from_metadata(meta)
    assert restored is not None
    assert restored.delta == pytest.approx(0.05)
    assert ClimateScenario.from_metadata("not-a-dict") is None


def test_identity_helper_copies():
    copy = ClimateService.identity(SERIES)
    assert copy == SERIES
    copy[2000] = -1
    assert SERIES[2000] == 10.0


# ----------------------------------------------------------------------
# AST guard: no banned dependencies
# ----------------------------------------------------------------------

BANNED = {
    "rasterio",
    "shapely",
    "geopandas",
    "fiona",
    "osgeo",
    "pyproj",
    "sklearn",
    "emcee",
    "requests",
}


def test_no_banned_dependencies_in_climate_service():
    path = Path(__file__).resolve().parents[1] / "core" / "services" / "climate_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    assert not (imported & BANNED), f"banned imports: {imported & BANNED}"


def test_only_allowed_top_level_imports():
    path = Path(__file__).resolve().parents[1] / "core" / "services" / "climate_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    allowed = {
        "__future__",
        "collections",
        "dataclasses",
        "typing",
        "core",
        "math",
        "json",
        "pathlib",
        "enum",
        "uuid",
        "datetime",
    }
    top: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            top.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            top.add(node.module.split(".")[0])
    assert top <= allowed, f"unexpected top-level imports: {top - allowed}"
