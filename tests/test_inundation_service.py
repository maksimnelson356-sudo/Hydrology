"""P3.3 acceptance tests for level-to-area/volume inundation."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest

from core.hydrorash.inundation import (
    InundationCalculationError,
    StageAreaPoint,
    inundation_from_stage_area,
    inundation_from_trapezoid,
)
from core.services.inundation_service import (
    INUNDATION_PROVENANCE,
    GeoJsonSource,
    InundationError,
    InundationRequest,
    InundationService,
    StageAreaSource,
    TrapezoidSource,
)

_CURVE = (
    StageAreaPoint(stage_m=0.0, area_m2=0.0),
    StageAreaPoint(stage_m=1.0, area_m2=100.0),
    StageAreaPoint(stage_m=2.0, area_m2=200.0),
    StageAreaPoint(stage_m=4.0, area_m2=800.0),
)


def test_stage_area_interpolation_and_volume():
    # Given: a monotonic stage-area curve.
    # When: the water level is between two known stages.
    result = inundation_from_stage_area(1.5, _CURVE)
    # Then: area is linear and volume follows the trapezoidal integral.
    assert result.effective_stage_m == pytest.approx(1.5)
    assert result.area_m2 == pytest.approx(150.0)
    assert result.volume_m3 == pytest.approx(112.5)
    assert result.warnings == ()


def test_stage_area_curve_is_monotonic():
    # Given: a valid curve.
    # When: increasing water levels are evaluated.
    areas = [inundation_from_stage_area(stage, _CURVE).area_m2 for stage in (0, 1, 2, 3, 4)]
    # Then: the flooded area never decreases.
    assert areas == sorted(areas)


def test_stage_above_curve_is_clamped_with_warning():
    # Given: a curve ending at four metres.
    # When: the requested level is five metres.
    result = inundation_from_stage_area(5.0, _CURVE)
    # Then: the conservative last known value is returned with a warning.
    assert result.effective_stage_m == pytest.approx(4.0)
    assert result.area_m2 == pytest.approx(800.0)
    assert result.volume_m3 == pytest.approx(1200.0)
    assert "выше максимума" in result.warnings[0]


def test_trapezoid_profile_matches_analytic_area_and_volume():
    # Given: a bottom width of 10 m, side slope 2, and a three-metre level.
    # When: the analytic profile inundation is evaluated.
    result = inundation_from_trapezoid(3.0, bottom_width_m=10.0, side_slope=2.0)
    # Then: A=B·H+m·H² and V=B·H²/2+m·H³/3.
    assert result.area_m2 == pytest.approx(48.0)
    assert result.volume_m3 == pytest.approx(63.0)
    assert result.curve[-1].stage_m == pytest.approx(3.0)
    assert result.curve[-1].area_m2 == pytest.approx(48.0)


@pytest.mark.parametrize(
    ("points", "message"),
    [
        ((), "минимум 2"),
        ((StageAreaPoint(0.0, 0.0), StageAreaPoint(0.0, 1.0)), "уникальн"),
        ((StageAreaPoint(0.0, 100.0), StageAreaPoint(1.0, 50.0)), "убыва"),
    ],
)
def test_invalid_stage_area_curves_raise(points, message):
    # Given: an empty, duplicated-stage, or decreasing-area curve.
    # When: core evaluation is requested.
    with pytest.raises(InundationCalculationError, match=message):
        # Then: the malformed curve is rejected.
        inundation_from_stage_area(1.0, points)


def test_negative_stage_raises():
    # Given: a negative requested water level.
    # When: core evaluation is requested.
    with pytest.raises(InundationCalculationError, match="(?i)уровень"):
        # Then: the physical input is rejected.
        inundation_from_stage_area(-1.0, _CURVE)


def test_service_stage_area_result_and_json_round_trip():
    # Given: a service request using an explicit S(H) curve.
    request = InundationRequest(stage_m=1.5, source=StageAreaSource(points=_CURVE))
    # When: the service evaluates the request.
    result = InundationService.run(request)
    # Then: units, provenance, warnings, and JSON serialization are stable.
    assert result.source == "stage_area"
    assert result.area_m2 == pytest.approx(150.0)
    assert result.area_km2 == pytest.approx(0.00015)
    assert result.volume_m3 == pytest.approx(112.5)
    assert result.provenance == INUNDATION_PROVENANCE
    restored = json.loads(json.dumps(result.to_dict(), ensure_ascii=False))
    assert restored["provenance"] == INUNDATION_PROVENANCE
    assert restored["curve"][1] == {"stage_m": 1.0, "area_m2": 100.0}


def test_service_trapezoid_source():
    # Given: a rectangular channel profile represented by a zero side slope.
    request = InundationRequest(
        stage_m=3.0,
        source=TrapezoidSource(bottom_width_m=10.0, side_slope=0.0),
    )
    # When: the service evaluates the request.
    result = InundationService.run(request)
    # Then: area is B·H and volume is B·H²/2.
    assert result.source == "trapezoid"
    assert result.area_m2 == pytest.approx(30.0)
    assert result.volume_m3 == pytest.approx(45.0)


def test_service_geojson_contours_interpolate_area_and_volume():
    # Given: two projected square contours with elevations 1 m and 2 m.
    document = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"elevation": 1.0},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1000, 0], [1000, 1000], [0, 1000], [0, 0]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"elevation_m": 2.0},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[-500, -500], [1500, -500], [1500, 1500], [-500, 1500], [-500, -500]]
                    ],
                },
            },
        ],
    }
    request = InundationRequest(
        stage_m=1.5,
        source=GeoJsonSource(geojson_text=json.dumps(document)),
    )
    # When: the contour elevations are converted to S(H) and evaluated.
    result = InundationService.run(request)
    # Then: area and volume interpolate between the contour areas.
    assert result.source == "geojson"
    assert result.area_m2 == pytest.approx(2_500_000.0)
    assert result.volume_m3 == pytest.approx(1_375_000.0)
    assert [point.stage_m for point in result.curve] == [1.0, 2.0]
    assert [point.area_m2 for point in result.curve] == [1_000_000.0, 4_000_000.0]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("{bad", "JSON"),
        ('{"type": "Feature", "properties": {}, "geometry": null}', "отмет"),
    ],
)
def test_invalid_geojson_source_raises(text, message):
    # Given: malformed JSON or a contour without elevation.
    request = InundationRequest(stage_m=1.0, source=GeoJsonSource(geojson_text=text))
    # When: the service parses the source.
    with pytest.raises(InundationError, match=message):
        # Then: the source is rejected with a domain error.
        InundationService.run(request)


def test_invalid_trapezoid_parameters_raise():
    # Given: a non-positive bottom width.
    request = InundationRequest(
        stage_m=1.0,
        source=TrapezoidSource(bottom_width_m=0.0, side_slope=1.0),
    )
    # When: the service evaluates the request.
    with pytest.raises(InundationError, match="(?i)ширина дна"):
        # Then: the invalid geometry is rejected.
        InundationService.run(request)


def test_public_exports_and_build_hidden_imports():
    # Given: package-level and packaging configuration.
    import build
    import core.services as services

    # When: P3.3 symbols and hidden imports are inspected.
    exported = (
        services.INUNDATION_PROVENANCE,
        services.InundationService,
        services.InundationRequest,
        services.InundationResult,
    )
    hidden = (
        "core.hydrorash.inundation",
        "core.services.inundation_service",
        "gui.tabs.tab_inundation",
    )
    # Then: the public API and packaged application include the feature.
    assert exported[0] == INUNDATION_PROVENANCE
    assert exported[1] is InundationService
    assert all(module in build.HIDDEN_IMPORTS for module in hidden)


def test_inundation_service_ast_no_gis_or_gui_dependencies():
    # Given: the service source.
    service_path = (
        Path(__file__).resolve().parents[1] / "core" / "services" / "inundation_service.py"
    )
    tree = ast.parse(service_path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    # When/Then: no GIS stack or GUI enters the service layer.
    banned = {"PyQt6", "matplotlib", "rasterio", "shapely", "geopandas", "fiona"}
    assert not (imported & banned)


def test_inundation_tab_renders_result_and_clears_on_error():
    # Given: a headless native inundation tab with its demo S(H) curve.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    from gui.tabs.tab_inundation import InundationTab

    app = QApplication.instance() or QApplication([])
    assert app is not None
    tab = InundationTab()
    try:
        # When: a valid request is calculated.
        tab.inundation_stage.setValue(1.5)
        tab.calculate_inundation()
        # Then: the result and S(H) plot are visible.
        assert INUNDATION_PROVENANCE in tab.inundation_result.toPlainText()
        assert tab.inundation_figure.axes[0].lines

        # When: the source table is emptied and calculation is repeated.
        tab.stage_area_table.setRowCount(0)
        tab.calculate_inundation()
        # Then: the stale plot is cleared and an error is shown.
        assert not tab.inundation_figure.axes
        assert "Ошибка" in tab.inundation_result.toPlainText()
    finally:
        tab.close()
        tab.deleteLater()


def test_inundation_tab_uses_square_metres_for_small_areas():
    # Given: a small trapezoidal cross-section whose area is below one km².
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    from gui.tabs.tab_inundation import InundationTab

    app = QApplication.instance() or QApplication([])
    assert app is not None
    tab = InundationTab()
    try:
        tab.inundation_source.setCurrentIndex(1)
        tab.inundation_bottom_width.setValue(20.0)
        tab.inundation_side_slope.setValue(2.0)
        tab.inundation_stage.setValue(3.0)

        # When: the small-area profile is plotted.
        tab.calculate_inundation()

        # Then: square metres are used instead of unreadable 1e-5 km² ticks.
        assert tab.inundation_figure.axes[0].get_ylabel() == "Площадь затопления, м²"
    finally:
        tab.close()
        tab.deleteLater()


def test_inundation_tab_clears_previous_result_when_source_changes():
    # Given: a valid stage-area result already rendered.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    from gui.tabs.tab_inundation import InundationTab

    app = QApplication.instance() or QApplication([])
    assert app is not None
    tab = InundationTab()
    try:
        tab.calculate_inundation()
        assert tab.inundation_figure.axes

        # When: the user selects a different data source.
        tab.inundation_source.setCurrentIndex(2)

        # Then: the old plot and result are cleared immediately.
        assert not tab.inundation_figure.axes
        assert not tab.inundation_result.toPlainText()
    finally:
        tab.close()
        tab.deleteLater()
