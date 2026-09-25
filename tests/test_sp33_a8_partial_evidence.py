"""Evidence checks for the partial SP 33 Appendix A.8 archive."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
MANIFEST_PATH = ROOT / "tests" / "fixtures" / "sp33_a8_manifest_v1.json"
DATA_PATH = ROOT / "tests" / "fixtures" / "sp33_a8_siezha_partial_v1.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_manifest_records_partial_a8_source_and_analog_metadata() -> None:
    manifest = _load(MANIFEST_PATH)
    subject = manifest["subject"]
    analogs = {analog["number"]: analog for analog in manifest["analogs"]}

    assert manifest["evidence_status"] == "partial"
    assert manifest["is_normative_validation"] is False
    assert manifest["source"]["standard"] == "СП 33-101-2003"
    assert manifest["source"]["section"] == "Приложение А, А.6–А.8"
    assert subject["observed_period"] == [1971, 1992]
    assert subject["observed_count"] == 22
    assert subject["restored_period"] == [1882, 1970]
    assert subject["catchment_area_km2"] == 407
    assert subject["year_field"] == "year"
    assert analogs[6]["name"] == "р. Мета – с. Березовский рядок"
    assert all(not analog["annual_series_available"] for analog in analogs.values())


def test_manifest_equations_cover_1882_1970_without_overlap() -> None:
    manifest = _load(MANIFEST_PATH)
    restored_years: list[int] = []

    for equation in manifest["equations"]:
        for period in equation["target_periods"]:
            restored_years.extend(range(period["start"], period["end"] + 1))

    assert len(restored_years) == 89
    assert len(set(restored_years)) == len(restored_years)
    assert set(restored_years) == set(range(1882, 1971))
    assert sum(equation["restored_count"] for equation in manifest["equations"]) == 89
    assert manifest["equations"][0]["formula"] == "q = -1.08 + 0.92*q1 + 0.51*q3"
    assert manifest["equations"][-1]["formula"] == "q = -0.44 + 0.88*q5"


def test_partial_fixture_preserves_published_q_and_derived_q() -> None:
    fixture = _load(DATA_PATH)
    records = fixture["records"]

    assert fixture["evidence_status"] == "partial"
    assert fixture["source_fixture"] == "sp33_a8_manifest_v1.json"
    assert len(records) == 22
    assert [record["year"] for record in records] == list(range(1971, 1993))
    for record in records:
        expected_q = record["q_published_l_s_km2"] * 407 / 1000
        assert record["q_derived_m3_s"] == pytest.approx(expected_q, abs=1e-6)
        assert all(record[f"q{number}"] is None for number in range(1, 8))

    assert records[0]["q_derived_m3_s"] == pytest.approx(1.53439)
    assert records[-1]["q_derived_m3_s"] == pytest.approx(2.29955)
