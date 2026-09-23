"""
tests/test_decision_support_service.py
Stage P2.5 acceptance tests (DOCS/ROADMAP.md §6.2): P(exceed) against known
analytic samples, risk classes with default cut-offs, user thresholds
(decision 10.3 (a)), errors on empty data, provenance, AST no-banned-deps.

No GUI: only core.domain, core.services, stdlib.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from core.services.decision_support_service import (
    DEFAULT_RISK_CUTOFFS,
    RISK_CLASSES,
    DecisionSupportError,
    DecisionSupportRequest,
    DecisionSupportResult,
    DecisionSupportService,
    ThresholdAssessment,
)

# ----------------------------------------------------------------------
# Analytic samples
# ----------------------------------------------------------------------

# 100 values: 0..99. P(X > 94) = values 95..99 → 5/100 = 0.05 exactly.
SAMPLE_0_99 = [float(i) for i in range(100)]

# 100 values all equal to 10 → P(X > 10) = 0, P(X > 5) = 1.
FLAT = [10.0] * 100


def make_request(samples=None, thresholds=None, risk_cutoffs=None) -> DecisionSupportRequest:
    return DecisionSupportRequest(
        samples=list(samples if samples is not None else SAMPLE_0_99),
        thresholds=dict(thresholds if thresholds is not None else {"Q_крит": 94.0}),
        risk_cutoffs=dict(risk_cutoffs) if risk_cutoffs is not None else dict(DEFAULT_RISK_CUTOFFS),
    )


# ----------------------------------------------------------------------
# Acceptance: known analytic P(exceed)
# ----------------------------------------------------------------------


def test_p_exceed_analytic_on_uniform_ramp():
    # values 0..99, Q=94 → exceed = 95..99 → 5 values → p = 0.05
    result = DecisionSupportService.assess(make_request(thresholds={"Q_крит": 94.0}))
    item = result.assessments[0]
    assert item.n_samples == 100
    assert item.n_exceed == 5
    assert item.p_exceed == pytest.approx(0.05, rel=1e-12)
    assert item.threshold == 94.0


def test_p_exceed_zero_when_all_below_threshold():
    result = DecisionSupportService.assess(make_request(samples=FLAT, thresholds={"Q": 10.0}))
    assert result.assessments[0].n_exceed == 0
    assert result.assessments[0].p_exceed == pytest.approx(0.0)


def test_p_exceed_one_when_all_above_threshold():
    result = DecisionSupportService.assess(make_request(samples=FLAT, thresholds={"Q": 5.0}))
    assert result.assessments[0].n_exceed == 100
    assert result.assessments[0].p_exceed == pytest.approx(1.0)


def test_p_exceed_half_on_bounded_sample():
    # 0..99, Q=49 → 50..99 → 50/100 = 0.5
    result = DecisionSupportService.assess(make_request(thresholds={"Q": 49.0}))
    assert result.assessments[0].p_exceed == pytest.approx(0.5, rel=1e-12)


# ----------------------------------------------------------------------
# Risk class with default cut-offs (low 0.05, medium 0.20)
# ----------------------------------------------------------------------


def test_risk_class_low_at_boundary():
    # p = 0.05 exactly → not < low? p < low is False at equality → medium?
    # Spec: p < low → low; p < medium → medium; else high.
    # p=0.05, low=0.05 → not < low → medium. Document this boundary.
    result = DecisionSupportService.assess(make_request(thresholds={"Q": 94.0}))
    item = result.assessments[0]
    assert item.p_exceed == pytest.approx(0.05)
    assert item.risk_class == "средний"  # equality falls into medium band


def test_risk_class_low_when_p_below_low():
    # p = 0.04 → 4/100 → Q=96 → 97..99 = 3?  0..99, >96 → 97,98,99 = 3 → 0.03
    result = DecisionSupportService.assess(make_request(thresholds={"Q": 96.0}))
    item = result.assessments[0]
    assert item.p_exceed == pytest.approx(0.03)
    assert item.risk_class == "низкий"


def test_risk_class_medium_band():
    # p = 0.10 → Q=90 → 91..99 = 9? >90 → 91..99 = 9 → wait 0..99: 91..99=9
    # Actually >90 from 0..99 = 91..99 = 9 → 0.09. Use Q=89 → 90..99 = 10 → 0.10
    result = DecisionSupportService.assess(make_request(thresholds={"Q": 89.0}))
    item = result.assessments[0]
    assert item.p_exceed == pytest.approx(0.10)
    assert item.risk_class == "средний"


def test_risk_class_high_when_p_at_or_above_medium():
    # p = 1.0 → high
    result = DecisionSupportService.assess(
        make_request(samples=FLAT, thresholds={"Q": 5.0})
    )
    assert result.assessments[0].risk_class == "высокий"
    assert result.worst_class == "высокий"


def test_risk_classes_tuple_order():
    assert RISK_CLASSES == ("низкий", "средний", "высокий")


# ----------------------------------------------------------------------
# Multiple thresholds + worst class + recommendation
# ----------------------------------------------------------------------


def test_multiple_thresholds_and_worst_class():
    thresholds = {"safe": 96.0, "critical": 10.0}
    result = DecisionSupportService.assess(make_request(thresholds=thresholds))
    assert len(result.assessments) == 2
    by_name = {item.name: item for item in result.assessments}
    assert by_name["safe"].risk_class == "низкий"
    assert by_name["critical"].risk_class == "высокий"
    assert result.worst_class == "высокий"
    assert "высокий" in result.recommendation


def test_sample_stats_recorded():
    result = DecisionSupportService.assess(make_request())
    assert result.n_samples == 100
    assert result.sample_mean == pytest.approx(49.5)
    assert result.sample_max == pytest.approx(99.0)


# ----------------------------------------------------------------------
# Decision 10.3 (a): explicit thresholds required
# ----------------------------------------------------------------------


def test_empty_thresholds_rejected_decision_10_3a():
    with pytest.raises(DecisionSupportError, match="10.3"):
        DecisionSupportRequest(samples=[1.0], thresholds={}).validate()


def test_threshold_dict_present_and_used_verbatim():
    # User threshold must appear as-is (no percentile substitution).
    result = DecisionSupportService.assess(
        make_request(thresholds={"Q_крит": 94.0})
    )
    assert result.assessments[0].threshold == 94.0


# ----------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------


def test_empty_samples_rejected():
    with pytest.raises(DecisionSupportError, match="Пустая выборка"):
        DecisionSupportRequest(samples=[], thresholds={"Q": 1.0}).validate()


def test_nan_sample_rejected():
    with pytest.raises(DecisionSupportError, match="NaN"):
        DecisionSupportRequest(samples=[1.0, float("nan")], thresholds={"Q": 1.0}).validate()


def test_non_numeric_threshold_rejected():
    with pytest.raises(DecisionSupportError, match="числом"):
        DecisionSupportRequest(
            samples=[1.0], thresholds={"Q": "high"}  # type: ignore[dict-item]
        ).validate()


def test_bad_risk_cutoffs_rejected():
    with pytest.raises(DecisionSupportError, match="Пороги риска"):
        DecisionSupportRequest(
            samples=[1.0],
            thresholds={"Q": 1.0},
            risk_cutoffs={"low": 0.5, "medium": 0.2},
        ).validate()


def test_empty_threshold_name_rejected():
    with pytest.raises(DecisionSupportError, match="Имя порога"):
        DecisionSupportRequest(samples=[1.0], thresholds={"  ": 1.0}).validate()


# ----------------------------------------------------------------------
# CalculationResult / provenance
# ----------------------------------------------------------------------


def test_run_returns_successful_calculation_result():
    result = DecisionSupportService.run(make_request(thresholds={"Q_крит": 94.0}))
    assert result.is_successful
    assert result.metadata.methodology.qualified_name == "decision_support@1.0"
    assert "10.3" in result.metadata.methodology.description
    assert result.output_data["n_samples"] == 100
    assert result.output_data["worst_class"] in RISK_CLASSES
    assert result.output_data["recommendation"]
    first = result.output_data["assessments"][0]
    for key in ("name", "threshold", "p_exceed", "risk_class", "n_exceed"):
        assert key in first


def test_assessment_to_dict_keys():
    item = ThresholdAssessment(
        name="Q",
        threshold=100.0,
        n_samples=10,
        n_exceed=2,
        p_exceed=0.2,
        risk_class="средний",
    )
    data = item.to_dict()
    assert data["threshold"] == 100.0
    assert data["p_exceed"] == pytest.approx(0.2)
    assert data["risk_class"] == "средний"


def test_result_type():
    result = DecisionSupportService.assess(make_request())
    assert isinstance(result, DecisionSupportResult)


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
    "numpy",
}


def test_no_banned_dependencies_in_decision_support_service():
    path = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "services"
        / "decision_support_service.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    assert not (imported & BANNED), f"banned imports: {imported & BANNED}"


def test_only_allowed_top_level_imports():
    path = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "services"
        / "decision_support_service.py"
    )
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
