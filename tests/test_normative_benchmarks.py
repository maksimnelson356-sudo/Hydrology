"""Independent benchmark checks for normative statistical calculations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.stats.parameters import calculate_statistical_parameters

FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "sp33_stats_parameters_hand_calc_v1.json"
)


def test_stats_parameters_matches_independent_sp33_hand_calculation() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    with pytest.warns(UserWarning, match=r"15\.4%"):
        result = calculate_statistical_parameters(fixture["input"]["values"])
    expected = fixture["expected"]

    for key in (
        "n",
        "mean",
        "std",
        "cv",
        "cs",
        "corrected_cv",
        "corrected_cs",
        "r1",
        "lambda2",
        "lambda3",
    ):
        assert result[key] == pytest.approx(expected[key], abs=5e-4), key

    assert result["length_warnings"] == expected["length_warnings"]
    assert fixture["calculation"]["relative_rms_error_percent"] == pytest.approx(
        15.361832366309494
    )
