"""Lock the transcription of СП 33-101-2003 Appendix A.7 and A.8 tables.

These tests guard the published target series against transcription drift. They
do NOT claim normative validation: the raw analog observations required to
reproduce the restoration are not published in the standard, so the restored
values can only serve as a comparison target, never as an independent result.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.services.a8_import_manifest import load_manifest

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
MANIFEST_PATH = FIXTURES / "sp33_a8_manifest_v1.json"
SERIES_PATH = FIXTURES / "sp33_a8_published_series_v1.json"
PARTIAL_PATH = FIXTURES / "sp33_a8_siezha_partial_v1.json"

AREA_KM2 = 407
OBSERVED = range(1971, 1993)
RESTORED = range(1882, 1971)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def series() -> dict:
    return _load(SERIES_PATH)


@pytest.fixture(scope="module")
def manifest() -> dict:
    return _load(MANIFEST_PATH)


def test_series_covers_1882_1992_without_gaps_or_duplicates(series: dict) -> None:
    years = [record["year"] for record in series["records"]]

    assert len(years) == 111
    assert years == sorted(years)
    assert len(set(years)) == 111
    assert set(years) == set(range(1882, 1993))
    assert series["observed_period"] == [1971, 1992]
    assert series["restored_period"] == [1882, 1970]


def test_series_splits_into_89_restored_and_22_observed(series: dict) -> None:
    records = series["records"]
    restored = [r for r in records if r["status"] == "restored"]
    observed = [r for r in records if r["status"] == "observed"]

    assert len(restored) == 89
    assert len(observed) == 22
    assert [r["year"] for r in restored] == list(RESTORED)
    assert [r["year"] for r in observed] == list(OBSERVED)
    assert all(r["restored_by_equation"] for r in restored)
    assert all(r["restored_by_equation"] is None for r in observed)


def test_derived_discharge_uses_catchment_area(series: dict) -> None:
    for record in series["records"]:
        expected = record["q_published_l_s_km2"] * AREA_KM2 / 1000
        assert record["q_derived_m3_s"] == pytest.approx(expected, abs=1e-5)

    assert series["records"][0]["q_derived_m3_s"] == pytest.approx(2.99 * 407 / 1000)
    assert series["records"][-1]["q_derived_m3_s"] == pytest.approx(5.65 * 407 / 1000)


def test_observed_values_agree_with_earlier_partial_transcription(series: dict) -> None:
    """The 22 observed years were transcribed earlier; both must agree."""
    partial = _load(PARTIAL_PATH)
    earlier = {r["year"]: r["q_published_l_s_km2"] for r in partial["records"]}
    current = {
        r["year"]: r["q_published_l_s_km2"]
        for r in series["records"]
        if r["status"] == "observed"
    }

    assert current == earlier


def test_every_restored_year_is_owned_by_exactly_one_equation(
    series: dict, manifest: dict
) -> None:
    owners: dict[int, list[str]] = {}
    for record in series["records"]:
        equation = record["restored_by_equation"]
        if equation is not None:
            owners.setdefault(record["year"], []).append(equation)

    assert len(owners) == 89
    assert all(len(ids) == 1 for ids in owners.values())

    expected: set[int] = set()
    for equation in manifest["equations"]:
        for period in equation["target_periods"]:
            years = set(range(period["start"], period["end"] + 1))
            for year in years:
                assert owners[year] == [equation["id"]]
            expected |= years
    assert expected == set(RESTORED)


def test_published_fit_matches_restored_counts_and_body_text(manifest: dict) -> None:
    expected = {
        "a8_1954_1970": (0.96, 0.02, 0.85, 17, 14.0, 12.3),
        "a8_1935_1939_1941_1953": (0.93, 0.05, 1.08, 18, 13.1, 10.6),
        "a8_1940_q3": (0.90, 0.05, 1.26, 1, 0.8, 0.6),
        "a8_1933_1934_q4": (0.84, 0.07, 1.58, 2, 1.3, 1.0),
        "a8_1891_1932_q5_q7": (0.78, 0.10, 1.85, 42, 12.6, 6.7),
        "a8_1882_1890_q5": (0.68, 0.13, 2.15, 9, 2.9, 1.4),
    }
    seen = set()
    for equation in manifest["equations"]:
        fit = equation["published_fit"]
        assert fit is not None, equation["id"]
        seen.add(equation["id"])
        assert (
            fit["R"],
            fit["sigma_R"],
            fit["rmse_l_s_km2"],
            fit["N_restored"],
            fit["N_ei_q"],
            fit["N_ei_sigma"],
        ) == pytest.approx(expected[equation["id"]])
        assert fit["N_restored"] == equation["restored_count"]

    assert seen == set(expected)


def test_typed_manifest_exposes_published_fit() -> None:
    manifest = load_manifest(MANIFEST_PATH)

    assert len(manifest.equations) == 6
    for equation in manifest.equations:
        fit = equation.published_fit
        assert fit is not None, equation.identifier
        target_years = sum(len(period.years()) for period in equation.target_periods)
        assert fit.n_restored == target_years
        assert 0.0 < fit.correlation < 1.0
        assert fit.sigma_correlation > 0.0
        assert fit.rmse_l_s_km2 > 0.0
        assert fit.n_equivalent_sigma < fit.n_equivalent_mean


def test_manifest_marks_analogs_absent_from_every_equation(manifest: dict) -> None:
    used = {
        number
        for equation in manifest["equations"]
        for number in equation["coefficients"]
        if str(number).startswith("q")
    }
    assert used == {"q1", "q3", "q4", "q5", "q7"}
    assert manifest["analogs_unused_by_equations"] == [2, 6]
    assert len(manifest["analogs"]) == 7


def test_equivalent_independent_information_for_whole_series(
    series: dict, manifest: dict
) -> None:
    published = series["equivalent_independent_info"]
    assert published["n_years"] == 111
    assert published["n_ei_mean"] == pytest.approx(66.7)
    assert published["n_ei_variance"] == pytest.approx(54.6)
    assert manifest["equivalent_independent_info"] == {
        key: published[key] for key in ("n_years", "n_ei_mean", "n_ei_variance")
    }


def test_1950_footnote_marker_is_preserved_not_silently_dropped(series: dict) -> None:
    marked = [r for r in series["records"] if r["footnote"] is not None]

    assert len(marked) == 1
    assert marked[0]["year"] == 1950
    assert marked[0]["q_published_l_s_km2"] == pytest.approx(8.55)
    assert marked[0]["footnote"] == "I"
    assert any("1950" in question for question in series["open_questions"])


def test_ambiguous_correlation_column_is_declared_not_guessed(series: dict) -> None:
    assert any("А.7" in question for question in series["open_questions"])
    assert any("r12" in question for question in series["open_questions"])
    assert any("вёрстк" in question for question in series["open_questions"])


def test_series_is_not_claimed_as_normative_validation(series: dict) -> None:
    assert series["is_normative_validation"] is False
    assert series["evidence_status"] == "published_target_series"
    assert "не опубликованы" in series["source"]["note"]
