"""Keep the normative verification matrix aligned with the methodology registry."""

from __future__ import annotations

import re
from pathlib import Path

from core.services.methodology_registry import build_default_registry

MATRIX_PATH = Path(__file__).parents[1] / "DOCS" / "normative_verification_matrix.md"

VALID_STATUSES = {"SOURCE_CHECKED", "PARTIAL", "ENGINEERING", "UNVERIFIED"}


def _matrix_statuses() -> dict[str, str]:
    """Map methodology id to its verification status from the matrix table."""
    table = re.search(
        r"## Матрица\n(.*?)\n## ", MATRIX_PATH.read_text(encoding="utf-8"), re.S
    )
    assert table is not None, "в матрице нет раздела «Матрица»"
    statuses: dict[str, str] = {}
    for line in table.group(1).splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 8:
            continue
        statuses[cells[1].strip("`")] = cells[6]
    return statuses


def test_matrix_has_a_row_for_every_registered_methodology() -> None:
    text = MATRIX_PATH.read_text(encoding="utf-8")
    missing = [
        methodology_id
        for methodology_id in build_default_registry().ids()
        if f"| `{methodology_id}` |" not in text
    ]

    assert not missing, f"Matrix rows missing for: {missing}"


def test_every_matrix_status_is_a_known_value() -> None:
    unknown = {
        methodology_id: status
        for methodology_id, status in _matrix_statuses().items()
        if status not in VALID_STATUSES
    }

    assert not unknown, f"Неизвестный статус в матрице: {unknown}"


def test_no_method_claims_normative_status_while_unverified() -> None:
    """A method marked is_normative must not be UNVERIFIED or ENGINEERING.

    This is the failure mode the 2026-09-28 audit found repeatedly: code that
    presented an unchecked result as standard-backed. The registry flag reaches
    the report and the GUI, so the matrix must never contradict it.
    """
    statuses = _matrix_statuses()
    registry = build_default_registry()
    offending: dict[str, str] = {}

    for methodology_id in registry.ids():
        descriptor = registry.get(methodology_id)
        if getattr(descriptor, "is_normative", False) is not True:
            continue
        status = statuses.get(methodology_id, "— нет строки в матрице —")
        if status in {"UNVERIFIED", "ENGINEERING", "— нет строки в матрице —"}:
            offending[methodology_id] = status

    assert not offending, (
        "Методики помечены нормативными, но по матрице не проверены: "
        f"{offending}. Либо снимите флаг is_normative, либо поднимите статус."
    )



def test_matrix_distinguishes_tests_from_normative_validation() -> None:
    text = MATRIX_PATH.read_text(encoding="utf-8")

    assert "GOLDEN_VALIDATED" in text
    assert "EXPERT_VALIDATED" in text
    assert "А.8" in text
    assert "staged-workflow" in text
    assert "sp33_a8_manifest_v1.json" in text
    assert "Partial evidence A.8" in text
    assert "A.8 import contract" in text
    assert "tools/import_a8_data.py" in text
    assert "--dry-run" in text
    assert "provenance" in text
    assert "не является доказательством корректности" in text


SPILLWAY_PATH = Path(__file__).parents[1] / "core" / "hydrorash" / "spillway.py"


def test_spillway_cites_the_verified_sp290_clause() -> None:
    """The spillway formula was checked against СП 290.1325800.2016 п. 6.3, формула (4).

    The code previously cited СП 58.13330.2019 п. 6, but that clause is «Общие
    требования безопасности ... при эксплуатации» — the full text disproves it.

    The clause is required in two specific places on purpose: the module header
    and ``spillway_capacity_check``. A bare ``"6.3" in text`` check passes as
    long as the digits survive anywhere in the file, and an occurrence count
    passes while either site is silently stripped. Both weaknesses were found
    here on 2026-09-28.
    """
    text = SPILLWAY_PATH.read_text(encoding="utf-8")
    verified = "СП 290.1325800.2016 п. 6.3"

    module_header = text.split("\ndef ", 1)[0]
    assert verified in module_header, (
        "Проверенный пункт 6.3 пропал из шапки модуля"
    )

    # The clause must actually reach the function that performs the check.
    body = text.split("def spillway_capacity_check", 1)[1]
    assert verified in body.split('"""', 2)[1], (
        "Проверенный пункт 6.3 пропал из докстринга spillway_capacity_check"
    )

    # The disproved attribution must not come back as a live citation.
    live = [
        line
        for line in text.splitlines()
        if re.search(r"СП\s*58", line)
        and "ОШИБОЧНА" not in line
        and "ошибочна" not in line
        and not line.lstrip().startswith(("#", "*"))
    ]
    assert not live, f"Возвращена опровергнутая ссылка на СП 58: {live}"


def test_spillway_registry_points_at_sp290() -> None:
    descriptor = build_default_registry().get("spillway")

    assert descriptor.standard == "СП 290.1325800.2016"


def test_spillway_status_is_source_checked_and_matches_registry() -> None:
    assert _matrix_statuses()["spillway"] == "SOURCE_CHECKED"
