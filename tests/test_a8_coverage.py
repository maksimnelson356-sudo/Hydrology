"""Coverage requirements implied by the СП 33 A.8 regression equations.

The equations in table A.7 dictate which years each analog must cover. Comparing
that against the record lengths published in table A.6 exposes an internal
inconsistency in the standard's own example: analog q3 is required over 58
years but A.6 states it observed 54. The finding is asserted here so it cannot be
silently dropped, and so a future fix in the standard can be detected.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from core.services.a8_import import (
    observation_report,
    published_coverage_conflicts,
    required_analog_coverage,
)
from core.services.a8_import_manifest import A8ImportError, load_manifest, parse_manifest

ROOT = Path(__file__).parents[1]
MANIFEST_PATH = ROOT / "tests" / "fixtures" / "sp33_a8_manifest_v1.json"


@pytest.fixture(scope="module")
def manifest():
    return load_manifest(MANIFEST_PATH)


def _windows(years: tuple[int, ...]) -> list[tuple[int, int]]:
    windows: list[tuple[int, int]] = []
    start = previous = years[0]
    for year in years[1:]:
        if year != previous + 1:
            windows.append((start, previous))
            start = year
        previous = year
    windows.append((start, previous))
    return windows


def test_required_coverage_windows_per_analog(manifest) -> None:
    coverage = required_analog_coverage(manifest)

    assert set(coverage) == {1, 3, 4, 5, 7}
    assert _windows(coverage[1]) == [(1954, 1992)]
    assert _windows(coverage[3]) == [(1935, 1992)]
    assert _windows(coverage[4]) == [(1933, 1939), (1941, 1953), (1971, 1992)]
    assert _windows(coverage[5]) == [(1882, 1932), (1971, 1992)]
    assert _windows(coverage[7]) == [(1891, 1932), (1971, 1992)]


def test_every_coverage_window_includes_the_subject_fit_period(manifest) -> None:
    fit_years = set(manifest.observed_period.years())
    for number, years in required_analog_coverage(manifest).items():
        assert fit_years <= set(years), f"q{number} не покрывает период аппроксимации"


def test_coverage_counts_match_expected_totals(manifest) -> None:
    coverage = required_analog_coverage(manifest)

    assert {number: len(years) for number, years in coverage.items()} == {
        1: 39,
        3: 58,
        4: 42,
        5: 73,
        7: 64,
    }


def test_analogs_absent_from_every_equation_need_no_coverage(manifest) -> None:
    coverage = required_analog_coverage(manifest)

    assert 2 not in coverage, "q2 не входит ни в одно уравнение регрессии"
    assert 6 not in coverage, "q6 не входит ни в одно уравнение регрессии"
    assert manifest.analog_observation_years[2] == 38
    assert manifest.analog_observation_years[6] == 69


def test_q3_coverage_conflict_is_detected(manifest) -> None:
    conflicts = published_coverage_conflicts(manifest)

    assert conflicts == {3: {"required_years": 58, "published_years": 54, "shortfall": 4}}


def test_q1_exact_length_match_validates_the_coverage_derivation(manifest) -> None:
    """q1 needs exactly as many years as A.6 publishes, which cross-checks the rule."""
    coverage = required_analog_coverage(manifest)

    assert len(coverage[1]) == manifest.analog_observation_years[1] == 39
    assert 1 not in published_coverage_conflicts(manifest)


def test_only_insufficient_analogs_are_reported(manifest) -> None:
    conflicts = published_coverage_conflicts(manifest)

    for number in (1, 4, 5, 7):
        assert number not in conflicts
        assert len(required_analog_coverage(manifest)[number]) <= (
            manifest.analog_observation_years[number]
        )


def test_observation_report_surfaces_the_conflict(manifest) -> None:
    frame = pd.DataFrame(
        [{"series_id": "seja_d_stan", "year": 1971, "value": 3.77, "unit": "q"}]
    )

    report = observation_report(frame, manifest)

    assert report["published_coverage_conflicts"] == {
        "q3": {"required_years": 58, "published_years": 54, "shortfall": 4}
    }


def test_manifest_requires_published_observation_counts() -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    del payload["analogs"][0]["observation_years_count"]

    with pytest.raises(A8ImportError) as error:
        parse_manifest(payload)
    assert "observation_years_count" in str(error.value)


def test_negative_observation_count_is_rejected() -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payload["analogs"][0]["observation_years_count"] = -1

    with pytest.raises(A8ImportError):
        parse_manifest(payload)
