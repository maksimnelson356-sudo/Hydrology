"""Tests for the A.8 analog-input template emitted into DOCS.

The template is a derived artifact: its year windows come from the manifest
equations, so it must never be hand-maintained. These tests pin the generation
contract -- which analogs are requested, which are not, and that the published
subject series is pre-filled so the user is never asked for it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from core.services.a8_import import required_analog_coverage
from core.services.a8_import_manifest import load_manifest
from tools import import_a8_data

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "tests" / "fixtures" / "sp33_a8_manifest_v1.json"
SERIES = ROOT / "tests" / "fixtures" / "sp33_a8_published_series_v1.json"
CSV_TEMPLATE = ROOT / "DOCS" / "A8_analog_series_TEMPLATE.csv"
XLSX_TEMPLATE = ROOT / "DOCS" / "A8_analog_series_TEMPLATE.xlsx"

EXPECTED_WINDOWS = {
    1: 39,
    3: 58,
    4: 42,
    5: 73,
    7: 64,
}


@pytest.fixture(scope="module")
def manifest():
    return load_manifest(MANIFEST)


@pytest.fixture(scope="module")
def rows(manifest):
    subject = import_a8_data.load_published_subject(SERIES)
    return import_a8_data.build_template_rows(manifest, subject)


def _windows(years: list[int]) -> list[tuple[int, int]]:
    windows: list[tuple[int, int]] = []
    start = previous = years[0]
    for year in years[1:]:
        if year != previous + 1:
            windows.append((start, previous))
            start = year
        previous = year
    windows.append((start, previous))
    return windows


def test_template_requests_only_analogs_used_by_equations(rows) -> None:
    requested = {row["series_id"] for row in rows if row["value"] == ""}

    assert requested == {"q1", "q3", "q4", "q5", "q7"}
    assert "q2" not in requested, "Меглинка не входит ни в одно уравнение А.8"
    assert "q6" not in requested, "Мета не входит ни в одно уравнение А.8"


def test_template_asks_for_exactly_the_required_coverage(rows, manifest) -> None:
    coverage = required_analog_coverage(manifest)
    blank = [row for row in rows if row["value"] == ""]

    assert len(blank) == 276
    for number, count in EXPECTED_WINDOWS.items():
        years = sorted(row["year"] for row in blank if row["series_id"] == f"q{number}")
        assert len(years) == count == len(coverage[number])


def test_q4_has_no_1940_row(rows) -> None:
    """1940 is restored from the q3 equation, so q4 must not be requested there."""
    q4_years = {row["year"] for row in rows if row["series_id"] == "q4"}

    assert 1940 not in q4_years
    assert _windows(sorted(q4_years)) == [(1933, 1939), (1941, 1953), (1971, 1992)]


def test_published_subject_series_is_prefilled(rows) -> None:
    series = json.loads(SERIES.read_text(encoding="utf-8"))
    published = {
        record["year"]: record["q_published_l_s_km2"]
        for record in series["records"]
        if record["status"] == "observed"
    }
    prefilled = {
        row["year"]: row["value"]
        for row in rows
        if row["series_id"] == "seja_d_stan"
    }

    assert prefilled == published
    assert len(prefilled) == 22
    assert not any(row["year"] < 1971 for row in rows if row["series_id"] == "seja_d_stan")


def test_analog_names_come_from_the_manifest(rows) -> None:
    names = {
        row["series_id"]: row["analog_name"]
        for row in rows
        if row["value"] == ""
    }

    assert names["q3"] == "р. Кобожа – с. Мошеник"
    assert names["q7"] == "р. Волга – г. Старица"
    assert all(name for name in names.values())


def test_template_carries_the_importer_contract_columns(rows) -> None:
    frame = pd.DataFrame(rows)

    assert set(import_a8_data.TEMPLATE_COLUMNS).issubset(frame.columns)
    assert {"series_id", "year", "value", "unit"}.issubset(frame.columns)
    assert set(frame["unit"].dropna().unique()) == {"л/с·км²"}


def _normalise(frame: pd.DataFrame) -> pd.DataFrame:
    """Treat an empty CSV cell and an empty generated cell as the same value."""
    return frame.astype(object).where(frame.notna(), "").reset_index(drop=True)


def test_committed_templates_match_a_fresh_generation(tmp_path, manifest) -> None:
    """Committed DOCS templates must not drift from the manifest."""
    subject = import_a8_data.load_published_subject(SERIES)
    expected = import_a8_data.build_template_rows(manifest, subject)
    expected_frame = _normalise(
        pd.DataFrame(expected, columns=list(import_a8_data.TEMPLATE_COLUMNS))
    )

    assert CSV_TEMPLATE.exists(), "DOCS/A8_analog_series_TEMPLATE.csv отсутствует"
    committed = _normalise(pd.read_csv(CSV_TEMPLATE, encoding="utf-8-sig"))
    pd.testing.assert_frame_equal(committed, expected_frame, check_dtype=False)

    if XLSX_TEMPLATE.exists():
        from_xlsx = _normalise(pd.read_excel(XLSX_TEMPLATE))
        pd.testing.assert_frame_equal(from_xlsx, expected_frame, check_dtype=False)


def test_emit_template_cli_writes_without_input(tmp_path, capsys) -> None:
    target = tmp_path / "tpl.csv"

    exit_code = import_a8_data.main(
        [
            "--manifest",
            str(MANIFEST),
            "--emit-template",
            "--output-template",
            str(target),
        ]
    )

    assert exit_code == 0
    assert target.exists()
    frame = pd.read_csv(target, encoding="utf-8-sig")
    assert len(frame) == 298
    assert int(frame["value"].isna().sum()) == 276
    assert " ждут ввода: 276" in capsys.readouterr().out


def test_cli_reports_missing_arguments_without_emit_template(capsys) -> None:
    exit_code = import_a8_data.main(["--manifest", str(MANIFEST)])

    assert exit_code == 1
    assert "требуются аргументы" in capsys.readouterr().err


def test_unsupported_template_suffix_is_rejected(tmp_path) -> None:
    with pytest.raises(import_a8_data.A8ImportError):
        import_a8_data.write_template(tmp_path / "tpl.txt", [])
