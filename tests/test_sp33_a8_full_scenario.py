"""End-to-end exercise of the complete СП 33 A.8 staged scenario.

WHAT THIS PROVES
----------------
The published A.8 example is executed as a whole: all six regression equations,
all 89 restored years (1882-1970), the R_кр = 0.60 threshold from the standard,
and the 22 observed years that must survive untouched. This is a STRUCTURAL and
FORMULA-CONSISTENCY check of the machinery.

WHAT THIS DOES NOT PROVE
------------------------
It is NOT numerical validation of A.8. The raw annual series of the seven
analogs are not published in the standard, so the restored values here come from
SYNTHETIC analogs and deliberately differ from table A.8. The restored values
must never be compared to the published series as if they reproduced it.

The recovered R values are close to the published ones only because the
synthetic analogs are *constructed* with the pair correlations that table A.7
reports. That makes this a check that the implementation computes the multiple
correlation R consistently with the standard's own (r1, r2, r12, R) tuples --
not an independent reproduction of the example.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core.domain import Dataset, DatasetType
from core.services.a8_import import build_import_artifacts
from core.services.a8_import_manifest import load_manifest
from core.services.bootstrap import build_container

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
MANIFEST_PATH = FIXTURES / "sp33_a8_manifest_v1.json"
SERIES_PATH = FIXTURES / "sp33_a8_published_series_v1.json"

SYNTHETIC_SEED = 101
# Table A.7 reports these pair correlations for the analogs.
PUBLISHED_PAIR_R = {1: 0.94, 3: 0.91, 4: 0.88, 5: 0.68, 7: 0.67}
# Plausible module levels (л/с·км²) per analog; levels are not prescribed by A.8.
ANALOG_MEAN = {1: 7.9, 3: 7.4, 4: 8.4, 5: 7.1, 7: 8.9}
ANALOG_CV = 0.35


@pytest.fixture(scope="module")
def manifest():
    return load_manifest(MANIFEST_PATH)


@pytest.fixture(scope="module")
def observed() -> dict[int, float]:
    series = json.loads(SERIES_PATH.read_text(encoding="utf-8"))
    return {
        record["year"]: record["q_published_l_s_km2"]
        for record in series["records"]
        if record["status"] == "observed"
    }


def _synthetic_analogs(manifest, observed: dict[int, float]) -> dict[int, pd.Series]:
    """Build deterministic analog series with the published correlation structure.

    Each analog is a positive transform of a latent signal that equals the
    standardized subject series over the fit window, mixed with independent
    noise so the target pair correlation is met and the analogs stay mutually
    decorrelated enough for individual coefficients to remain significant.
    """
    from core.services.a8_import import required_analog_coverage

    coverage = required_analog_coverage(manifest)
    fit_years = sorted(manifest.observed_period.years())
    rng = np.random.default_rng(SYNTHETIC_SEED)

    subject = np.array([observed[year] for year in fit_years], dtype=float)
    standardized = (subject - subject.mean()) / subject.std(ddof=1)
    latent: dict[int, float] = {}
    for year in range(1882, 1993):
        if year in observed:
            continue
        # Resample the subject's own standardized regime so pre-1971 analogs stay
        # in a hydrologically plausible range; an independent draw would let the
        # fitted equation extrapolate to negative modules.
        latent[year] = float(standardized[rng.integers(0, len(standardized))]) + float(
            rng.normal(0.0, 0.15)
        )
    for index, year in enumerate(fit_years):
        latent[year] = float(standardized[index])

    analogs: dict[int, pd.Series] = {}
    for number, years in coverage.items():
        target_r = PUBLISHED_PAIR_R[number]
        years = list(years)
        signal = np.array([latent[year] for year in years])
        noise = rng.normal(size=len(years))
        linear = target_r * signal + np.sqrt(1.0 - target_r**2) * noise
        mean = ANALOG_MEAN[number]
        values = mean + mean * ANALOG_CV * linear
        analogs[number] = pd.Series(dict(zip(years, values, strict=True)), dtype=float)
    return analogs


@pytest.fixture(scope="module")
def artifacts(manifest, observed):
    analogs = _synthetic_analogs(manifest, observed)
    rows: list[dict] = [
        {
            "series_id": "seja_d_stan",
            "year": year,
            "value": value,
            "unit": "q",
        }
        for year, value in sorted(observed.items())
    ]
    for number, series in analogs.items():
        rows.extend(
            {
                "series_id": f"q{number}",
                "year": int(year),
                "value": float(value),
                "unit": "q",
            }
            for year, value in series.items()
        )
    frame = pd.DataFrame(rows)
    return build_import_artifacts(frame, manifest, strict=True), analogs


@pytest.fixture(scope="module")
def staged_result(artifacts, observed):
    (config, primary), _ = artifacts
    container = build_container()
    descriptor = container.registry.get("series_extension_staged")
    dataset = Dataset(
        name=primary["name"],
        data={int(year): float(value) for year, value in primary["data"].items()},
        dataset_type=DatasetType.OBSERVED,
    )
    result = container.calculation.execute(
        descriptor.to_methodology(),
        dataset,
        parameters={"stages": config["stages"], "exclude_negative": True},
    )
    return result


def test_strict_import_accepts_the_complete_scenario(artifacts) -> None:
    (config, primary), analogs = artifacts

    assert primary["observation_report"]["missing_required_years"] == {}
    assert len(config["stages"]) == 6
    assert set(analogs) == {1, 3, 4, 5, 7}
    assert primary["data"].keys() == {str(year) for year in range(1971, 1993)}


def test_generated_config_uses_the_standard_threshold_and_windows(artifacts, manifest) -> None:
    (config, _), _ = artifacts
    stages = config["stages"]
    expected = {equation.identifier: equation for equation in manifest.equations}

    assert [stage["name"] for stage in stages] == [
        equation.identifier for equation in manifest.equations
    ]
    for stage in stages:
        equation = expected[stage["name"]]
        assert stage["ro_cr"] == pytest.approx(0.60), "R_кр из A.8, не дефолт 0.70"
        assert set(stage["fit_years"]) == set(manifest.observed_period.years())
        assert set(stage["target_years"]) == {
            year for period in equation.target_periods for year in period.years()
        }
        assert set(stage["analogs"]) == {f"q{n}" for n in equation.analog_numbers}


def test_scenario_produces_the_full_111_year_period(staged_result, observed) -> None:
    extended = staged_result.output_data["extended_series"]

    assert staged_result.is_successful is True
    assert staged_result.output_data["success"] is True
    assert staged_result.output_data["unresolved_years"] == []
    assert len(extended) == 111
    assert set(map(int, extended)) == set(range(1882, 1993))


def test_all_six_equations_contribute_in_published_order(staged_result, manifest) -> None:
    stages = staged_result.output_data["stages"]

    assert [stage["name"] for stage in stages] == [
        equation.identifier for equation in manifest.equations
    ]
    for stage, equation in zip(stages, manifest.equations, strict=True):
        expected_years = {
            year for period in equation.target_periods for year in period.years()
        }
        assert set(map(int, stage["applied_years"])) == expected_years


def test_observed_years_are_never_overwritten(staged_result, observed) -> None:
    extended = staged_result.output_data["extended_series"]

    for year, value in observed.items():
        assert extended[str(year)] == pytest.approx(value, abs=0.0), (
            f"наблюдённое значение {year} изменено"
        )


def test_restored_years_are_positive_and_finite(staged_result) -> None:
    extended = staged_result.output_data["extended_series"]

    for year in range(1882, 1971):
        value = extended[str(year)]
        assert value is not None
        assert np.isfinite(value)
        assert value > 0.0, f"восстановленное значение {year} неположительно"


def test_every_stage_satisfies_the_standard_acceptance_criteria(staged_result) -> None:
    for stage in staged_result.output_data["stages"]:
        assert stage["R"] >= 0.60, f"{stage['name']}: R ниже R_кр из A.8"
        assert "variance_correction" in stage


def test_recovered_correlation_matches_published_table_a7(staged_result) -> None:
    """Formula consistency: R must follow the published (r1, r2, r12, R) tuples.

    This is NOT independent validation -- the synthetic analogs were built with
    the published pair correlations, so agreement confirms the R formula, not
    the restoration.
    """
    published = {
        "a8_1954_1970": 0.96,
        "a8_1935_1939_1941_1953": 0.93,
        "a8_1940_q3": 0.90,
        "a8_1933_1934_q4": 0.84,
        "a8_1891_1932_q5_q7": 0.78,
        "a8_1882_1890_q5": 0.68,
    }
    recovered = {stage["name"]: stage["R"] for stage in staged_result.output_data["stages"]}

    assert set(recovered) == set(published)
    for name, expected in published.items():
        assert recovered[name] == pytest.approx(expected, abs=0.12), (
            f"{name}: R={recovered[name]} сильно отличается от {expected}"
        )


def test_coverage_conflict_is_reported_alongside_the_successful_run(artifacts) -> None:
    """The q3 shortfall must stay visible even when the run itself succeeds."""
    (_, primary), _ = artifacts

    assert primary["observation_report"]["published_coverage_conflicts"] == {
        "q3": {"required_years": 58, "published_years": 54, "shortfall": 4}
    }


def test_third_correlation_column_matches_inter_analog_correlation(artifacts) -> None:
    """Evidence that A.7's third value is r12, the inter-analog correlation.

    Analogs are built so their correlation with the subject equals the published
    r1 and r2. For independent residual parts that implies r12 ~ r1 * r2, which is
    what the standard's third column reports. This is strong indirect evidence,
    not a substitute for the typeset original.
    """
    (_, _), analogs = artifacts
    fit_years = sorted(range(1971, 1993))
    expected = {
        (1, 3): 0.86,
        (3, 4): 0.85,
        (5, 7): 0.51,
    }

    for (left, right), published in expected.items():
        computed = float(
            np.corrcoef(
                analogs[left].reindex(fit_years).to_numpy(),
                analogs[right].reindex(fit_years).to_numpy(),
            )[0, 1]
        )
        assert computed == pytest.approx(published, abs=0.09), (
            f"r12(q{left},q{right})={computed:.3f} против опубликованного {published}"
        )


def test_restored_values_differ_from_table_a8(staged_result) -> None:
    """Guard against anyone mistaking this synthetic run for a reproduction."""
    series = json.loads(SERIES_PATH.read_text(encoding="utf-8"))
    published = {
        record["year"]: record["q_published_l_s_km2"]
        for record in series["records"]
        if record["status"] == "restored"
    }
    extended = staged_result.output_data["extended_series"]

    matching = [
        year
        for year, value in published.items()
        if extended[str(year)] == pytest.approx(value, abs=1e-6)
    ]
    assert matching == [], "синтетические значения совпали с А.8 — сценарий не синтетический"
