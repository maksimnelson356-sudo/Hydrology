"""Tests for external A.8 observation import and artifact generation."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from core.domain import Dataset
from core.services.a8_import import (
    A8ImportError,
    build_import_artifacts,
    load_manifest,
    normalize_observations,
)
from core.services.bootstrap import build_container
from tools import import_a8_data

MANIFEST = "tests/fixtures/sp33_a8_manifest_v1.json"


def _manifest():
    return load_manifest(MANIFEST)


def _complete_frame() -> pd.DataFrame:
    rows = []
    for series_id in ("seja_d_stan", "q1", "q3", "q4", "q5", "q7"):
        for year in range(1882, 1993):
            rows.append(
                {
                    "series_id": series_id,
                    "year": year,
                    "value": float(year % 17 + 1),
                    "unit": "л/с·км²",
                }
            )
    return pd.DataFrame(rows)


def test_normalizes_q_and_discharge_to_common_module() -> None:
    frame = pd.DataFrame(
        [
            {
                "series_id": "seja_d_stan",
                "year": 1971,
                "value": 3.77,
                "unit": "л/с·км²",
            },
            {
                "series_id": "q1",
                "year": 1971,
                "value": 2.99,
                "unit": "м³/с",
            },
        ]
    )

    observations = normalize_observations(frame, _manifest())

    assert observations["seja_d_stan"][1971] == pytest.approx(3.77)
    assert observations["q1"][1971] == pytest.approx(2.99 * 1000 / 2990)


def test_duplicate_year_is_rejected() -> None:
    frame = pd.DataFrame(
        [
            {
                "series_id": "q1",
                "year": 1971,
                "value": 1.0,
                "unit": "л/с·км²",
            },
            {
                "series_id": "q1",
                "year": 1971,
                "value": 2.0,
                "unit": "л/с·км²",
            },
        ]
    )

    with pytest.raises(A8ImportError, match="дубликат"):
        normalize_observations(frame, _manifest())


def test_strict_import_requires_complete_subject_series() -> None:
    frame = pd.DataFrame(
        [
            {
                "series_id": "seja_d_stan",
                "year": 1971,
                "value": 3.77,
                "unit": "л/с·км²",
            }
        ]
    )

    with pytest.raises(A8ImportError, match="subject"):
        build_import_artifacts(frame, _manifest())


def test_complete_import_generates_all_a8_stages() -> None:
    config, primary = build_import_artifacts(_complete_frame(), _manifest())

    assert config["metadata"]["strict"] is True
    assert len(config["stages"]) == 6
    assert config["stages"][0]["ro_cr"] == 0.6
    assert config["stages"][0]["fit_years"] == list(range(1971, 1993))
    assert len(config["stages"][0]["target_years"]) == 17
    assert len(primary["data"]) == 22
    assert primary["unit"] == "л/с·км²"
    report = config["metadata"]["observation_report"]
    assert report["input_rows"] == 666
    assert report["unit_counts"] == {"q": 666, "Q": 0}
    assert report["missing_required_years"] == {}
    assert primary["observation_report"] == report
    json.dumps(config)
    json.dumps(primary)


def test_generated_artifacts_are_consumable_by_staged_service() -> None:
    config, primary = build_import_artifacts(_complete_frame(), _manifest())
    dataset = Dataset(
        name="А.8 primary",
        data={int(year): float(value) for year, value in primary["data"].items()},
        unit="л/с·км²",
        catchment_area_km2=407,
    )
    container = build_container()
    descriptor = container.registry.get("series_extension_staged")

    result = container.calculation.execute(
        descriptor.to_methodology(),
        dataset,
        parameters=config,
    )

    assert result.is_successful is True
    assert result.output_data["unresolved_years"] == []


def test_cli_writes_partial_artifacts_when_explicitly_allowed(tmp_path) -> None:
    input_path = tmp_path / "observations.csv"
    config_path = tmp_path / "stages.json"
    primary_path = tmp_path / "primary.json"
    input_path.write_text(
        "series_id,year,value,unit\n"
        "seja_d_stan,1971,3.77,л/с·км²\n",
        encoding="utf-8",
    )

    exit_code = import_a8_data.main(
        [
            "--input", str(input_path),
            "--manifest", MANIFEST,
            "--output-config", str(config_path),
            "--output-primary", str(primary_path),
            "--allow-missing",
        ]
    )

    assert exit_code == 0
    config = json.loads(config_path.read_text(encoding="utf-8"))
    primary = json.loads(primary_path.read_text(encoding="utf-8"))
    assert config["metadata"]["strict"] is False
    assert primary["data"] == {"1971": 3.77}


def test_cli_dry_run_reports_provenance_without_writing(tmp_path, capsys) -> None:
    input_path = tmp_path / "observations.csv"
    config_path = tmp_path / "stages.json"
    primary_path = tmp_path / "primary.json"
    input_path.write_text(
        "series_id,year,value,unit\n"
        "seja_d_stan,1971,3.77,л/с·км²\n",
        encoding="utf-8",
    )

    exit_code = import_a8_data.main(
        [
            "--input", str(input_path),
            "--manifest", MANIFEST,
            "--output-config", str(config_path),
            "--output-primary", str(primary_path),
            "--allow-missing",
            "--dry-run",
        ]
    )

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert not config_path.exists()
    assert not primary_path.exists()
    assert report["dry_run"] is True
    assert len(report["provenance"]["input_sha256"]) == 64
    assert report["observation_report"]["input_rows"] == 1
