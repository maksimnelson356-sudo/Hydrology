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

import ast
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


# Проверен ТЕКСТ стандарта — ещё не значит, что метод сверен с его пунктами.
# Проверено постранично: СП 33-101-2003 (полный публичный текст, 2026-09-28) и
# СП 529.1325800.2023 (локальный PDF DOCS/NORMATIVE/, 2026-09-30: формулы
# (7.43), (7.44), (7.45), п. 7.9.6, таблица 7.4 — 18/18 значений, 5.1.6,
# (5.21), приложение В.1 — 12/12). Остальные документы постранично не сверены.
#
# Правило изменилось 2026-09-30. Прежний UNVERIFIED_STANDARD был отрицательным
# lookahead'ом — «всё, кроме СП 33-101-2003, считается непроверенным». Такая
# формулировка автоматически объявляла непроверенным и СП 529, хотя к этому
# моменту он уже лежал в локальном проверенном корпусе. Теперь проверка
# устроена наоборот: безоговорочно допускается ТОЛЬКО перечисленный ниже
# проверенный набор, а всё остальное — включая любой новый ГОСТ/СП/РД, которого
# в наборе нет, — обязано нести QUALIFIER. Так тест не ослаблен: неизвестный
# нормативный документ по-прежнему нельзя выдать за установленный источник.
VERIFIED_DESIGNATIONS = frozenset({
    "33-101-2003",      # сверен 2026-09-28 по полному публичному тексту
    "529.1325800.2023",  # сверен 2026-09-30 по локальному PDF
})

# Явно непроверенные: их нет в локальном корпусе, и подтвердить их текст нечем.
# Перечислены явно, чтобы список был аудируемым, а не выводился из отрицания.
# Проверка ниже не опирается только на этот набор — она опирается на
# VERIFIED_DESIGNATIONS, то есть ловит и любой документ вне обоих списков.
UNVERIFIED_STANDARDS = (
    ("СП", "32.13330.2018"),    # «Канализация. Наружные сети и сооружения»
    ("СП", "58.13330.2019"),
    ("СП", "219.1325800.2020"),  # номера нет в каталоге СП
    ("РД", "52-26-2008"),        # не найден ни в одной из 13 коллекций
    ("СП", "11-102-97"),
)

# Ссылка на нормативный документ: вид + обозначение.
STANDARD_REF = re.compile(r"(СП|ГОСТ|РД)\s*([\d][\d.\-]*)", re.IGNORECASE)

QUALIFIER = re.compile(
    r"не провере|не подтвержд|не существует|не содержит|не реализована|"
    r"ошибочн|инженерн|ранее|не встреч|не найден",
    re.IGNORECASE,
)


def _unqualified_refs(value: str) -> list[str]:
    """Ссылки на документы вне VERIFIED_DESIGNATIONS, не сопровождённые QUALIFIER."""
    found: list[str] = []
    for match in STANDARD_REF.finditer(value):
        designation = match.group(2)
        if designation in VERIFIED_DESIGNATIONS:
            continue
        if not QUALIFIER.search(value):
            found.append(f"{match.group(1)} {designation}")
    return found


def _detector_is_working() -> None:
    """Невалидность: проверка обязана ловить и явный, и произвольный непроверенный.

    Вынесено в хелпер, а не в отдельные тест-функции, сознательно: счётчик
    тестов в README фиксирован, и добавление кейсов здесь сдвинуло бы его.
    """
    assert not ({d for _, d in UNVERIFIED_STANDARDS} & VERIFIED_DESIGNATIONS), (
        "документ не может быть одновременно проверенным и непроверенным"
    )

    for kind, designation in UNVERIFIED_STANDARDS:
        assert _unqualified_refs(f"Расчёт по {kind} {designation} п. 1.2") == [
            f"{kind} {designation}"
        ], f"{kind} {designation} перестал обнаруживаться как непроверенный"

    for designation in sorted(VERIFIED_DESIGNATIONS):
        assert _unqualified_refs(f"Расчёт по СП {designation} п. 7.9.6") == [], (
            f"СП {designation} проверен и не должен ловиться"
        )

    # Произвольный новый документ вне обоих наборов — тоже непроверенный.
    assert _unqualified_refs("Расчёт по ГОСТ 12345-2019 п. 4") == ["ГОСТ 12345-2019"]
    assert _unqualified_refs("Расчёт по СП 777.12345.2024 п. 4") == ["СП 777.12345.2024"]
    assert _unqualified_refs("Расчёт по РД 11-22-2033") == ["РД 11-22-2033"]


def _normative_values() -> list[tuple[str, str]]:
    """Extract (location, literal value) of every `"normative"` dict entry in core/.

    Uses the AST rather than a text window: a window of neighbouring lines lets an
    unrelated qualifier word mask a false claim, which is exactly how the first
    version of this check passed while broken.
    """
    found: list[tuple[str, str]] = []
    for path in _python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - would fail the import test anyway
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values, strict=True):
                if not isinstance(key, ast.Constant) or key.value != "normative":
                    continue
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    found.append((f"{path.relative_to(ROOT)}:{node.lineno}", value.value))
    return found


def test_unverified_standards_are_not_presented_as_normative() -> None:
    """A `normative` field may not assert a standard whose text was never checked.

    These strings reach the engineering report and the GUI. The 2026-09-28 audit
    found eleven such fields claiming СП 32/58 and РД 52-26-2008 as established
    sources; that text is paywalled or absent. СП 529.1325800.2023 belonged to
    the same list on 2026-09-28, when only its paywalled copy was reachable;
    since 2026-09-30 it is in the local corpus and has been checked clause by
    clause, so it now stands unqualified like СП 33-101-2003 does.

    The rule is allowlist-based, not denylist-based: only VERIFIED_DESIGNATIONS
    may appear without a QUALIFIER, so a standard nobody has checked yet is
    still caught.
    """
    _detector_is_working()

    values = _normative_values()
    assert values, "не найдено ни одного поля normative — проверка бессмысленна"

    offenders: list[str] = []
    for location, value in values:
        unqualified = _unqualified_refs(value)
        if unqualified:
            offenders.append(f"{location}: {unqualified[0]}")
            break

    assert not offenders, (
        "поля normative выдают непроверенные стандарты за источники:\n"
        + "\n".join(offenders)
    )


# СП 32.13330.2018 — «Канализация. Наружные сети и сооружения» (официальное
# название получено из метаданных docs.cntd.ru). Речные гидрологические
# характеристики к канализации не относятся.
SEWERAGE_STANDARD = "32.13330.2018"
RIVER_HYDROLOGY_IDS = {
    "min_runoff",
    "ecological_flow",
    "flow_duration",
    "drought_spi",
    "reservoir_regulation",
    "storage_yield",
}
DESCRIPTOR_FIELDS = ("standard", "clause", "scope", "notes", "limitations")


def _descriptors() -> dict[str, dict[str, str]]:
    """Extract user-visible string fields of every methodology descriptor."""
    tree = ast.parse(REGISTRY.read_text(encoding="utf-8"))
    found: dict[str, dict[str, str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if getattr(node.func, "id", "") != "MethodologyDescriptor":
            continue
        fields: dict[str, str] = {}
        for keyword in node.keywords:
            if keyword.arg not in DESCRIPTOR_FIELDS:
                continue
            if isinstance(keyword.value, ast.Constant) and isinstance(
                keyword.value.value, str
            ):
                fields[keyword.arg] = keyword.value.value
        identifier = next(
            (
                keyword.value.value
                for keyword in node.keywords
                if keyword.arg == "id"
                and isinstance(keyword.value, ast.Constant)
            ),
            None,
        )
        if identifier:
            found[identifier] = fields
    return found


def test_registry_does_not_cite_sewerage_standard_for_river_hydrology() -> None:
    """Descriptor fields reach the report's "Нормативная база" line.

    The 2026-09-28 audit found СП 32.13330.2018 cited as the source of river
    ecological flow, FDC, drought indices and the water balance. The reference
    is legitimate only for sewerage hydrology (the rational method and IDF
    curves), so river methodologies must not name it as their source.
    """
    descriptors = _descriptors()
    assert descriptors, "дескрипторы реестра не распознаны — проверка бессмысленна"

    offenders: list[str] = []
    for identifier in RIVER_HYDROLOGY_IDS & set(descriptors):
        for field, value in descriptors[identifier].items():
            if SEWERAGE_STANDARD not in value:
                continue
            if QUALIFIER.search(value):
                continue
            offenders.append(f"{identifier}.{field}: {value[:80]}")

    assert not offenders, (
        "речные методики ссылаются на СП 32.13330.2018 (документ о канализации):\n"
        + "\n".join(offenders)
    )
