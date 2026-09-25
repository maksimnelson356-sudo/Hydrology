"""Keep the normative verification matrix aligned with the methodology registry."""

from __future__ import annotations

from pathlib import Path

from core.services.methodology_registry import build_default_registry

MATRIX_PATH = Path(__file__).parents[1] / "DOCS" / "normative_verification_matrix.md"


def test_matrix_has_a_row_for_every_registered_methodology() -> None:
    text = MATRIX_PATH.read_text(encoding="utf-8")
    missing = [
        methodology_id
        for methodology_id in build_default_registry().ids()
        if f"| `{methodology_id}` |" not in text
    ]

    assert not missing, f"Matrix rows missing for: {missing}"


def test_matrix_distinguishes_tests_from_normative_validation() -> None:
    text = MATRIX_PATH.read_text(encoding="utf-8")

    assert "GOLDEN_VALIDATED" in text
    assert "EXPERT_VALIDATED" in text
    assert "А.8" in text
    assert "staged-workflow" in text
    assert "не является доказательством корректности" in text
