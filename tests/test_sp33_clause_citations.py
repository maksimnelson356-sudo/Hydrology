"""Guard against false citations of non-existent SP 33 clauses.

Verified 2026-09-28 against the public full text of СП 33-101-2003
(https://files.stroyinf.ru/Data2/1/4294815/4294815038.htm): the standard has
sections 1-7 plus appendices, and contains no clause of the form 8.N.

`core/hydrorash/ice_phenomena.py` and `core/hydrorash/snowmelt.py` previously
attributed their numeric tables to "раздел 8.5", "п. 8.5.2-8.5.4" and "п. 8.1"
- clauses that do not exist. Corrective notes that state the citation is wrong
are allowed; a live claim is not.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
CORE = ROOT / "core"
REGISTRY = CORE / "services" / "methodology_registry.py"
ICEPHENOMENA = CORE / "hydrorash" / "ice_phenomena.py"
SNOWMELT = CORE / "hydrorash" / "snowmelt.py"
CLAUSE_INDEX = ROOT / "tests" / "fixtures" / "sp33_clause_index_v1.json"

# A citation of a clause number, as it appears next to the standard name.
CITED_CLAUSE = re.compile(
    r"СП\s*33(?:-101-2003)?[^.;\n]{0,60}?п\.\s*([0-9]\.[0-9]{1,2})"
)

# A citation of a clause that СП 33-101-2003 does not contain.
FALSE_CLAUSE = re.compile(r"(?:п\.\s*|раздел\s*)8(?:\.\d+)*")
SP33 = re.compile(r"СП\s*33(?:-101-2003)?", re.IGNORECASE)
# Wording that legitimately mentions the false clause to correct it.
NEGATION = re.compile(
    r"не существует|не содержит|не реализована|не реализован|ошибочн|"
    r"ИНЖЕНЕР|ранее|нет\b|исправлено",
    re.IGNORECASE,
)


def _python_files() -> list[Path]:
    return sorted(CORE.rglob("*.py"))


def test_core_has_no_live_sp33_section_eight_citation() -> None:
    offenders: list[str] = []
    for path in _python_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not (SP33.search(line) and FALSE_CLAUSE.search(line)):
                continue
            if NEGATION.search(line):
                continue
            offenders.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()[:90]}")
    assert offenders == [], "живые ссылки на несуществующие пункты СП 33:\n" + "\n".join(
        offenders
    )


@pytest.mark.parametrize(
    ("path", "clause"),
    [(ICEPHENOMENA, "8.5"), (ICEPHENOMENA, "8.5.2"), (SNOWMELT, "8.1")],
)
def test_corrected_modules_explain_the_false_citation(path: Path, clause: str) -> None:
    """Each fixed module must record why the citation was wrong, not just drop it."""
    text = path.read_text(encoding="utf-8")

    assert clause in text, f"{path.name}: не упомянут ошибочный пункт {clause}"
    assert "не существует" in text or "ошибочн" in text
    assert "ИНЖЕНЕР" in text.upper()


def test_registry_ice_phenomena_no_longer_cites_clause_5_44() -> None:
    """п. 5.44 is about highest water levels, not ice phenomena.

    Only the ``clause=`` field is asserted: the ``notes`` field legitimately
    mentions 5.44 to record that the old citation was wrong.
    """
    text = REGISTRY.read_text(encoding="utf-8")
    block = text.split('id="ice_phenomena"', 1)[1].split("MethodologyDescriptor(", 1)[0]
    clause = re.search(r'clause="([^"]*)"', block)

    assert clause is not None
    assert "5.44" not in clause.group(1)
    assert "7.70" in clause.group(1)
    assert "7.71" in clause.group(1)
    assert "7.72" in clause.group(1)


def test_registry_snowmelt_records_that_sp33_has_no_degree_day_method() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    block = text.split('id="snowmelt"', 1)[1].split("MethodologyDescriptor(", 1)[0]

    assert "8.1" in block
    assert "ошибочно" in block


def test_ice_phenomena_marks_engineering_status() -> None:
    text = ICEPHENOMENA.read_text(encoding="utf-8")

    assert "ИНЖЕНЕРНАЯ" in text.upper()
    assert "7.72" in text, "не упомянут п. 7.72 с формулой (7.51)"
    assert "7.51" in text


def test_returned_normative_fields_do_not_claim_dead_clauses() -> None:
    text = ICEPHENOMENA.read_text(encoding="utf-8")
    live = [
        line.strip()
        for line in text.splitlines()
        if '"normative"' in line and SP33.search(line) and not NEGATION.search(line)
    ]

    assert live == [], f"поля normative всё ещё ссылаются на мёртвые пункты: {live}"


def _clause_index() -> dict:
    return json.loads(CLAUSE_INDEX.read_text(encoding="utf-8"))


def test_clause_index_records_that_section_eight_is_absent() -> None:
    index = _clause_index()

    assert index["section_8_exists"] is False
    assert index["sections_present"] == [1, 2, 3, 4, 5, 6, 7]
    assert index["clause_count"] == len(index["clauses"]) > 100
    assert all(
        not clause.startswith("8.") for clause in index["clauses"]
    ), "в индексе не должно быть пунктов раздела 8"


def test_every_sp33_clause_cited_in_core_exists_in_the_standard() -> None:
    """Any clause number cited next to СП 33 must be a real clause of the standard."""
    known = set(_clause_index()["clauses"])
    unknown: list[str] = []
    checked = 0

    for path in _python_files():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if NEGATION.search(line):
                continue
            for clause in CITED_CLAUSE.findall(line):
                checked += 1
                if clause not in known:
                    unknown.append(
                        f"{path.relative_to(ROOT)}:{number}: п.{clause} -> {line.strip()[:80]}"
                    )

    assert unknown == [], "ссылки на несуществующие пункты СП 33:\n" + "\n".join(unknown)
    assert checked > 0, "цитаты СП 33 не найдены — проверка бессмысленна"


def test_cited_clauses_are_topically_plausible() -> None:
    """Spot-check that key citations point at clauses about the expected subject."""
    clauses = _clause_index()["clauses"]

    expectations = {
        "5.26": "максимальн",
        "5.32": "гидрограф",
        "5.45": "уровн",
        "6.17": "дисперс",
        "7.70": "затор",
        "7.72": "затор",
    }
    for clause, expected in expectations.items():
        assert clause in clauses, f"п.{clause} отсутствует в индексе"
        assert expected in clauses[clause].lower(), (
            f"п.{clause} не содержит ожидаемого «{expected}»: {clauses[clause][:80]}"
        )
