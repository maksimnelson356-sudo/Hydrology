"""
tests/test_data_quality_service.py
Unit tests for the data quality assessment service (stage 2 of DOCS/ROADMAP.md).

Acceptance criteria covered (DOCS/ROADMAP.md, stage 2):
- a clean series yields quality grade "A" without blocking issues;
- gaps, zero/negative values and outliers each produce their own issue code
  with recommendations attached ("what was found -> why it matters -> what to do");
- a critically short series produces an INSUFFICIENT_DATA error;
- the service never modifies the dataset ("no silent data changes" rule);
- recommendation deduplication, JSON serialization and report registration
  helpers behave as expected.

The tests run without GUI: only `core.domain` and `core.services` are touched.
"""

from __future__ import annotations

from core.domain import (
    Dataset,
    DatasetType,
    ValidationSeverity,
)
from core.services import (
    RECOMMENDATIONS,
    DataQualityService,
)

# Deterministic clean series (numpy default_rng(6), mean=100, std=10):
# verified to produce grade "A", score 1.0 and zero issues.
CLEAN_VALUES = [
    110.5, 117.8, 74.5, 98.6, 110.1, 113.5, 106.5, 115.0, 102.9, 105.5,
    101.8, 89.3, 91.5, 103.8, 94.2, 112.7, 112.9, 118.0, 99.7, 113.8,
    90.9, 91.8, 100.8, 102.8, 84.0, 82.7, 103.6, 91.4, 112.1, 103.9,
]

BLOCKING_SEVERITIES = (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)


def make_dataset(values: dict[int, float], name: str = "Тестовый пост") -> Dataset:
    """Build a Dataset from an explicit {year: value} mapping."""
    return Dataset(
        name=name,
        data=dict(values),
        dataset_type=DatasetType.OBSERVED,
    )


def make_clean_dataset() -> Dataset:
    """Years 1990..2019, no gaps, all positive, homogeneous and stationary."""
    return make_dataset({1990 + i: v for i, v in enumerate(CLEAN_VALUES)})


# ----------------------------------------------------------------------
# Clean series
# ----------------------------------------------------------------------
def test_clean_series_grade_a_without_issues():
    service = DataQualityService()
    report = service.analyze(make_clean_dataset())

    assert report.n_points == 30
    assert report.n_missing == 0
    assert report.quality_score > 0.95
    assert report.quality_grade == "A"
    blocking = [i for i in report.issues if i.severity in BLOCKING_SEVERITIES]
    assert blocking == []


def test_analyze_does_not_modify_dataset():
    dataset = make_clean_dataset()
    snapshot = dict(dataset.data)
    service = DataQualityService()

    service.analyze(dataset)

    assert dataset.data == snapshot
    assert len(snapshot) == 30


# ----------------------------------------------------------------------
# Individual problems -> individual issue codes
# ----------------------------------------------------------------------
def test_gap_years_produce_data_gaps_issue():
    data = {1990 + i: v for i, v in enumerate(CLEAN_VALUES)}
    del data[2000]  # 30 -> 29 points with a single-year gap
    dataset = make_dataset(data)
    service = DataQualityService()

    report = service.analyze(dataset)

    gap_issues = [i for i in report.issues if i.code == "DATA_GAPS"]
    assert len(gap_issues) == 1
    issue = gap_issues[0]
    assert issue.severity == ValidationSeverity.WARNING
    assert issue.details["missing_years"] == [2000]
    # "why it matters" and "what to do" must be attached
    assert issue.details["why_it_matters"]
    action_codes = {a["code"] for a in issue.details["recommended_actions"]}
    assert {"fill_interpolation", "fill_correlation"} <= action_codes


def test_gap_recommendations_exist_in_flat_list():
    service = DataQualityService()
    data = {1990 + i: v for i, v in enumerate(CLEAN_VALUES)}
    del data[2000]

    report = service.analyze(make_dataset(data))
    actions = service.recommendations(report)
    codes = {a["code"] for a in actions}

    assert {"fill_interpolation", "fill_correlation"} <= codes


def test_zero_values_flagged():
    data = {1990 + i: v for i, v in enumerate(CLEAN_VALUES)}
    data[2015] = 0.0
    service = DataQualityService()

    report = service.analyze(make_dataset(data))

    assert any(i.code == "ZERO_VALUES" for i in report.issues)


def test_negative_values_flagged():
    data = {1990 + i: v for i, v in enumerate(CLEAN_VALUES)}
    data[2010] = -12.5
    service = DataQualityService()

    report = service.analyze(make_dataset(data))

    assert any(i.code == "NEGATIVE_VALUES" for i in report.issues)


def test_outliers_flagged_with_review_recommendation():
    data = {1990 + i: v for i, v in enumerate(CLEAN_VALUES)}
    data[2020] = 400.0  # far outside the IQR bounds of the clean series
    dataset = make_dataset(data)
    service = DataQualityService()

    report = service.analyze(dataset)

    outlier_issues = [i for i in report.issues if i.code == "OUTLIERS_DETECTED"]
    assert outlier_issues, "expected at least one outlier issue"
    details = outlier_issues[0].details
    assert details["outlier_count"] >= 1
    action_codes = {a["code"] for a in details["recommended_actions"]}
    assert "outliers_review" in action_codes


# ----------------------------------------------------------------------
# Short series
# ----------------------------------------------------------------------
def test_short_series_insufficient_data_error():
    values = {1990 + k: 100.0 + 5.0 * k for k in range(5)}
    dataset = make_dataset(values)
    service = DataQualityService()

    report = service.analyze(dataset)

    errors = [i for i in report.issues if i.code == "INSUFFICIENT_DATA"]
    assert len(errors) == 1
    assert errors[0].severity == ValidationSeverity.ERROR
    assert report.quality_grade == "C"  # 0.7: error penalty x completeness


def test_short_series_against_methodology_min_points():
    # stats_parameters requires >= 25 points (registry, stage 2 catalogue)
    values = {1990 + k: 100.0 + 5.0 * k for k in range(5)}
    dataset = make_dataset(values)
    service = DataQualityService()

    report = service.analyze(dataset, methodology_id="stats_parameters")

    codes = [i.code for i in report.issues]
    assert "METHODOLOGY_MIN_POINTS" in codes
    assert "INSUFFICIENT_DATA" in codes


def test_unknown_methodology_id_is_ignored():
    dataset = make_clean_dataset()
    service = DataQualityService()

    report = service.analyze(dataset, methodology_id="no_such_methodology")

    assert report.quality_grade == "A"


# ----------------------------------------------------------------------
# Report post-processing
# ----------------------------------------------------------------------
def test_issues_are_sorted_by_severity():
    data = {1990 + i: v for i, v in enumerate(CLEAN_VALUES)}
    del data[2000]
    data[2010] = -1.0
    data[2011] = -2.0
    dataset = make_dataset(data)
    service = DataQualityService()

    report = service.analyze(dataset)

    order = {
        ValidationSeverity.CRITICAL: 0,
        ValidationSeverity.ERROR: 1,
        ValidationSeverity.WARNING: 2,
        ValidationSeverity.INFO: 3,
    }
    ranks = [order[i.severity] for i in report.issues]
    assert ranks == sorted(ranks)


def test_recommendations_are_deduplicated_per_issue_and_action():
    data = {1990 + i: v for i, v in enumerate(CLEAN_VALUES)}
    del data[2000], data[2001]  # two gaps -> one DATA_GAPS issue
    dataset = make_dataset(data)
    service = DataQualityService()

    report = service.analyze(dataset)
    actions = service.recommendations(report)

    keys = [(a["issue_code"], a["code"]) for a in actions]
    assert len(keys) == len(set(keys))


def test_to_json_contains_grade_and_recommendations():
    service = DataQualityService()

    payload = service.to_json(service.analyze(make_clean_dataset()))

    assert payload["quality_grade"] == "A"
    assert payload["recommendations"] == []  # nothing to recommend on a clean series


def test_register_report_sets_type_and_dataset_id():
    dataset = make_clean_dataset()
    service = DataQualityService()

    record = service.register_report(service.analyze(dataset), dataset_id=dataset.id)

    assert record["report_type"] == "data_quality"
    assert record["dataset_id"] == str(dataset.id)


def test_insufficient_data_has_recommendation_catalogue_entry():
    # The dialog must be able to show "what to do" for every code in use.
    assert "INSUFFICIENT_DATA" in RECOMMENDATIONS

