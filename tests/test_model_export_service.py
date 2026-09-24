"""P3.5 engineering-model JSON/CSV export and tolerant import tests."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pandas as pd  # noqa: F401  # noqa: PANDAS_OK
import pytest

from core.services.backwater_profile_service import ReachSpec
from core.services.model_export_service import (
    HydrographExportRequest,
    HydrographModel,
    ModelExportError,
    ModelKind,
    ReachExportRequest,
    ReachModel,
    WseProfileExportRequest,
    WseProfileModel,
    export_hydrograph,
    export_reaches,
    export_wse_profile,
    import_json_model,
)
from core.services.model_export_types import JsonValue


def test_reaches_json_csv_roundtrip(tmp_path: Path) -> None:
    # Given: a valid ordered reach chain.
    target = tmp_path / "reaches.json"
    reaches = (
        ReachSpec(name="lower", B=20.0, m=2.0, n=0.035, slope=0.001, L=500.0),
        ReachSpec(name="upper", B=15.0, m=1.5, n=0.04, slope=0.002, L=750.0),
    )

    # When: the model is exported and imported.
    result = export_reaches(ReachExportRequest(reaches=reaches, target=target))
    imported = import_json_model(result.json_path)

    # Then: both formats are emitted and the typed model roundtrips exactly.
    assert result.kind is ModelKind.REACHES
    assert result.csv_path == tmp_path / "reaches.csv"
    assert target.read_bytes().startswith(b"\xef\xbb\xbf")
    assert result.csv_path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert isinstance(imported, ReachModel)
    assert imported.reaches == reaches
    assert imported.warnings == ()
    frame = pd.read_csv(result.csv_path, encoding="utf-8-sig")
    assert frame.loc[0, "name"] == "lower"
    assert frame.loc[1, "L_m"] == 750.0


def test_hydrograph_json_csv_roundtrip(tmp_path: Path) -> None:
    # Given: a routed hydrograph with aligned time and flow arrays.
    request = HydrographExportRequest(
        times_hours=(0.0, 3.0, 6.0, 9.0),
        inflow=(10.0, 30.0, 20.0, 8.0),
        outflow=(10.0, 18.0, 24.0, 12.0),
        target=tmp_path / "routing.json",
    )

    # When: the hydrograph is exported and imported.
    result = export_hydrograph(request)
    imported = import_json_model(result.json_path)

    # Then: the complete aligned series survives the JSON roundtrip.
    assert isinstance(imported, HydrographModel)
    assert imported.times_hours == request.times_hours
    assert imported.inflow == request.inflow
    assert imported.outflow == request.outflow
    frame = pd.read_csv(result.csv_path, encoding="utf-8-sig")
    assert list(frame.columns) == ["time_h", "inflow_m3s", "outflow_m3s"]
    assert len(frame) == 4


def test_wse_profile_json_csv_roundtrip(tmp_path: Path) -> None:
    # Given: sampled water-surface elevations.
    request = WseProfileExportRequest(
        distances_m=(0.0, 100.0, 250.0),
        water_surface_elevation_m=(12.0, 11.7, 11.2),
        target=tmp_path / "wse.json",
    )

    # When: the profile is exported and imported.
    result = export_wse_profile(request)
    imported = import_json_model(result.json_path)

    # Then: WSE ordinates and distances remain unchanged.
    assert isinstance(imported, WseProfileModel)
    assert imported.distances_m == request.distances_m
    assert imported.water_surface_elevation_m == request.water_surface_elevation_m
    frame = pd.read_csv(result.csv_path, encoding="utf-8-sig")
    assert frame.loc[2, "wse_m"] == 11.2


def test_import_tolerates_missing_optional_metadata_and_extra_keys(tmp_path: Path) -> None:
    # Given: a simple compatible payload without format/version metadata.
    target = tmp_path / "legacy.json"
    payload = {
        "kind": "wse_profile",
        "data": {
            "distances_m": [0.0, 10.0],
            "water_surface_elevation_m": [5.0, 4.8],
        },
        "extra": "ignored",
    }
    target.write_text(json.dumps(payload), encoding="utf-8")

    # When: the model is parsed.
    imported = import_json_model(target)

    # Then: required data is accepted and omissions become visible warnings.
    assert isinstance(imported, WseProfileModel)
    assert imported.water_surface_elevation_m == (5.0, 4.8)
    assert len(imported.warnings) == 2
    assert any("format" in warning for warning in imported.warnings)
    assert any("version" in warning for warning in imported.warnings)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"kind": "unknown", "data": {}}, "kind"),
        ({"kind": "hydrograph", "data": {"times_hours": [0.0]}}, "inflow"),
        ({"kind": "reaches", "data": {"reaches": []}}, "reaches"),
    ],
)
def test_import_rejects_incompatible_payload(
    tmp_path: Path,
    payload: dict[str, JsonValue],
    message: str,
) -> None:
    # Given: an incompatible but valid JSON document.
    target = tmp_path / "bad.json"
    target.write_text(json.dumps(payload), encoding="utf-8")

    # When/Then: the boundary reports a typed, understandable error.
    with pytest.raises(ModelExportError, match=message):
        import_json_model(target)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"kind": "reaches", "data": []},
        {"kind": "reaches", "data": {"reaches": [{"name": 1}]}},
        {"kind": "hydrograph", "data": {"times_hours": "bad"}},
    ],
)
def test_import_rejects_wrong_json_shapes(
    tmp_path: Path,
    payload: JsonValue,
) -> None:
    # Given: valid JSON with an incompatible field shape.
    target = tmp_path / "wrong-shape.json"
    target.write_text(json.dumps(payload), encoding="utf-8")

    # When/Then: the boundary raises the typed service error, not an assertion.
    with pytest.raises(ModelExportError):
        import_json_model(target)


def test_import_rejects_malformed_json(tmp_path: Path) -> None:
    # Given: malformed JSON content.
    target = tmp_path / "broken.json"
    target.write_text("{broken", encoding="utf-8")

    # When/Then: parsing fails at the file boundary with a typed error.
    with pytest.raises(ModelExportError, match="JSON"):
        import_json_model(target)


def test_export_rejects_misaligned_hydrograph(tmp_path: Path) -> None:
    # Given: time and flow arrays with different lengths.
    request = HydrographExportRequest(
        times_hours=(0.0, 1.0),
        inflow=(1.0,),
        outflow=(1.0, 0.5),
        target=tmp_path / "bad.json",
    )

    # When/Then: invalid engineering data cannot be written.
    with pytest.raises(ModelExportError, match="length"):
        export_hydrograph(request)


def test_export_is_atomic_and_leaves_no_temp_files(tmp_path: Path) -> None:
    # Given: a valid model export target.
    request = ReachExportRequest(
        reaches=(ReachSpec(name="a", B=2.0, m=1.0, n=0.03, slope=0.001, L=100.0),),
        target=tmp_path / "atomic.json",
    )

    # When: both files are written.
    result = export_reaches(request)

    # Then: outputs exist and temporary files are cleaned up.
    assert result.json_path.exists()
    assert result.csv_path.exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_service_ast_has_no_ui_or_dataframe_dependency() -> None:
    # Given: the production service source.
    service_path = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "services"
        / "model_export_service.py"
    )

    # When: imports are inspected.
    tree = ast.parse(service_path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    # Then: service I/O remains independent from GUI and dataframe packages.
    assert not imported & {"PyQt6", "pandas", "numpy", "scipy", "matplotlib"}
