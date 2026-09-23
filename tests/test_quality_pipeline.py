"""
tests/test_quality_pipeline.py
Unit tests for the quality pipeline gates (stage P1.3 of DOCS/ROADMAP.md).

Acceptance criteria covered:
- after_import analyzes without blocking the import and without mutating data;
- before_calculation blocks on ERROR/CRITICAL until ``confirmed=True``;
- WARNING-only issues allow calculation with warnings attached;
- reactive spike rule fires for abrupt year-to-year jumps;
- empty series can never be calculated.

No GUI: only core.domain and core.services.
"""

from __future__ import annotations

from core.domain import Dataset, DatasetType, ValidationSeverity
from core.services import DataQualityService
from core.services.quality_pipeline import QualityPipeline

CLEAN_VALUES = [
    110.5, 117.8, 74.5, 98.6, 110.1, 113.5, 106.5, 115.0, 102.9, 105.5,
    101.8, 89.3, 91.5, 103.8, 94.2, 112.7, 112.9, 118.0, 99.7, 113.8,
    90.9, 91.8, 100.8, 102.8, 84.0, 82.7, 103.6, 91.4, 112.1, 103.9,
]


def make_dataset(values: dict[int, float], name: str = "Тест") -> Dataset:
    return Dataset(name=name, data=dict(values), dataset_type=DatasetType.OBSERVED)


def clean_dataset() -> Dataset:
    return make_dataset({1990 + i: v for i, v in enumerate(CLEAN_VALUES)})


def short_broken_dataset() -> Dataset:
    """Too short + gap → ERROR issues (INSUFFICIENT_DATA, DATA_GAPS)."""
    return make_dataset({1990: 10.0, 1991: 11.0, 1993: 9.0})


def pipeline(**kwargs) -> QualityPipeline:
    return QualityPipeline(quality=DataQualityService(), **kwargs)


# ----------------------------------------------------------------------
# after_import
# ----------------------------------------------------------------------
def test_after_import_allows_and_never_mutates():
    dataset = clean_dataset()
    snapshot = dict(dataset.data)
    result = pipeline().after_import(dataset)

    assert result.allowed is True
    assert result.decision.stage == "after_import"
    assert dataset.data == snapshot
    assert result.report.quality_score > 0.9


def test_after_import_flags_blocking_without_stopping_import():
    dataset = short_broken_dataset()
    result = pipeline().after_import(dataset)

    # Import still succeeds (allowed), but UI is told confirmation is needed.
    assert result.allowed is True
    assert result.needs_confirmation is True
    assert result.decision.blocking
    codes = {i.code for i in result.decision.blocking}
    assert "INSUFFICIENT_DATA" in codes or "DATA_GAPS" in codes


def test_after_import_empty_series_not_allowed():
    result = pipeline().after_import(make_dataset({}))
    assert result.allowed is False
    assert result.needs_confirmation is False
    assert any(i.code == "DATA_EMPTY" for i in result.report.issues)


# ----------------------------------------------------------------------
# before_calculation
# ----------------------------------------------------------------------
def test_before_calculation_blocks_errors_until_confirmed():
    dataset = short_broken_dataset()
    blocked = pipeline().before_calculation(dataset)

    assert blocked.allowed is False
    assert blocked.needs_confirmation is True
    assert blocked.decision.blocking

    confirmed = pipeline().before_calculation(dataset, confirmed=True)
    assert confirmed.allowed is True
    assert confirmed.needs_confirmation is False
    # Confirmation does not clear the report — user still sees issues.
    assert confirmed.decision.blocking


def test_before_calculation_allows_clean_series():
    result = pipeline().before_calculation(clean_dataset())
    assert result.allowed is True
    assert result.needs_confirmation is False
    assert result.decision.blocking == []


def test_before_calculation_empty_always_blocked():
    blocked = pipeline().before_calculation(make_dataset({}))
    assert blocked.allowed is False
    assert blocked.needs_confirmation is False

    forced = pipeline().before_calculation(make_dataset({}), confirmed=True)
    assert forced.allowed is False


def test_before_calculation_never_mutates():
    dataset = short_broken_dataset()
    snapshot = dict(dataset.data)
    pipeline().before_calculation(dataset)
    pipeline().before_calculation(dataset, confirmed=True)
    assert dataset.data == snapshot


# ----------------------------------------------------------------------
# Reactive spike rule
# ----------------------------------------------------------------------
def test_spike_detected_as_warning_not_block():
    # 30 calm years then a 20× jump → DATA_SPIKE warning, calculation allowed.
    values = {1990 + i: 100.0 for i in range(30)}
    values[2020] = 2000.0
    dataset = make_dataset(values)

    result = pipeline(spike_ratio=8.0).before_calculation(dataset)

    codes = {i.code for i in result.extra_issues}
    assert "DATA_SPIKE" in codes
    spike = next(i for i in result.extra_issues if i.code == "DATA_SPIKE")
    assert spike.severity == ValidationSeverity.WARNING
    assert result.allowed is True
    assert spike not in result.decision.blocking


def test_spike_threshold_configurable():
    values = {1990: 100.0, 1991: 150.0}  # 1.5× jump
    dataset = make_dataset(values)

    strict = pipeline(spike_ratio=1.2).before_calculation(dataset)
    loose = pipeline(spike_ratio=8.0).before_calculation(dataset)

    assert any(i.code == "DATA_SPIKE" for i in strict.extra_issues)
    assert not any(i.code == "DATA_SPIKE" for i in loose.extra_issues)


# ----------------------------------------------------------------------
# gate_payload
# ----------------------------------------------------------------------
def test_gate_payload_is_json_safe():
    result = pipeline().after_import(short_broken_dataset())
    payload = pipeline().gate_payload(result)

    assert payload["stage"] == "after_import"
    assert payload["allowed"] is True
    assert isinstance(payload["quality_score"], float)
    assert isinstance(payload["blocking"], list)
    for item in payload["blocking"] + payload["warnings"]:
        assert set(item) >= {"code", "severity", "message"}
