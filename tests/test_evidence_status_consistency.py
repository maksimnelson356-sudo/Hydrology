"""Registry and the verification matrix must agree on every methodology's status.

Before this, the four evidence categories existed only as prose in
DOCS/normative_verification_matrix.md while the registry carried a single
`is_normative` boolean. The two could not be reconciled, which is how
`spillway` (source verified against СП 290) and `ecological_flow` (source
refuted) came to share one flag with opposite meanings. The matrix now carries
a machine-readable canonical table and this test holds the two in step.

Verified 2026-09-28 against the full text of СП 33-101-2003.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from core.services.methodology_registry import (
    EVIDENCE_STATUSES,
    build_default_registry,
)

ROOT = Path(__file__).parents[1]
MATRIX = ROOT / "DOCS" / "normative_verification_matrix.md"
CANON_HEADING = "### Каноническая таблица статусов"

# | `series_extension` | `partial` | СП 33 п. 6.2 | текст |
ROW = re.compile(
    r"^\|\s*`([a-z_0-9]+)`\s*\|\s*`([a-z_]+)`\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|",
    re.M,
)

# Totals as published in the matrix summary and README. A reclassification must
# be a deliberate edit in two places, not a silent drift in one.
EXPECTED_TOTALS = {
    "source_checked": 6,
    "partial": 7,
    "engineering": 10,
    "unverified": 1,
}


def _canonical_table() -> dict[str, str]:
    text = MATRIX.read_text(encoding="utf-8")
    start = text.find(CANON_HEADING)
    assert start != -1, f"в матрице нет раздела {CANON_HEADING!r}"
    return {mid: status for mid, status, _, _ in ROW.findall(text[start:])}


def _registry() -> dict[str, object]:
    return {d.id: d for d in build_default_registry()}


def test_canonical_table_was_parsed() -> None:
    """Non-vacuity: the parse must find the whole catalogue, not a stray row."""
    table = _canonical_table()
    assert len(table) == 24, f"ожидалось 24 методики в канонической таблице, найдено {len(table)}"


def test_every_status_is_a_known_value() -> None:
    table = _canonical_table()
    unknown = {m: s for m, s in table.items() if s not in EVIDENCE_STATUSES}
    assert unknown == {}, f"неизвестные статусы в матрице: {unknown}"


def test_matrix_and_registry_agree() -> None:
    table = _canonical_table()
    registry = _registry()
    assert set(table) == set(registry), (
        f"расхождение по составу: только в матрице {sorted(set(table) - set(registry))}, "
        f"только в реестре {sorted(set(registry) - set(table))}"
    )
    mismatched = {
        mid: (status, registry[mid].evidence_status)
        for mid, status in table.items()
        if registry[mid].evidence_status != status
    }
    assert mismatched == {}, "статус в матрице не совпадает с реестром: " + str(mismatched)


def test_totals_match_published_counts() -> None:
    table = _canonical_table()
    actual: dict[str, int] = {}
    for status in table.values():
        actual[status] = actual.get(status, 0) + 1
    assert actual == EXPECTED_TOTALS, (
        f"счёт по категориям разошёлся: {actual}, опубликовано {EXPECTED_TOTALS}"
    )


def test_registry_totals_match_published_counts() -> None:
    """The registry must also account for 6/7/10/1, not only the matrix.

    Found by injection: a status flipped in the registry alone left the matrix
    totals test green, because that test only reads the document. Agreement
    between the two is checked per method, but the headline counts published in
    README and the matrix summary come from the registry and need their own
    guard against silent drift.
    """
    actual: dict[str, int] = {}
    for d in build_default_registry():
        actual[d.evidence_status] = actual.get(d.evidence_status, 0) + 1
    assert actual == EXPECTED_TOTALS, (
        f"счёт по категориям в реестре разошёлся: {actual}, опубликовано {EXPECTED_TOTALS}"
    )


def test_unverified_source_can_never_be_normative() -> None:
    """The one hard invariant between the two flags, checked from outside too."""
    offenders = [
        d.id
        for d in build_default_registry()
        if d.evidence_status == "unverified" and d.is_normative
    ]
    assert offenders == [], f"источник опровергнут, но методика помечена нормативной: {offenders}"


def test_source_checked_requires_a_standard() -> None:
    """A verified source cannot exist without a named document."""
    offenders = [
        d.id
        for d in build_default_registry()
        if d.evidence_status == "source_checked" and not d.standard
    ]
    assert offenders == [], f"статус source_checked без указания источника: {offenders}"


@pytest.mark.parametrize("status", sorted(EVIDENCE_STATUSES))
def test_every_status_is_used_somewhere(status: str) -> None:
    """Guards against a category quietly becoming dead weight."""
    used = [d.id for d in build_default_registry() if d.evidence_status == status]
    assert used, f"категория {status!r} не используется ни одной методикой"
