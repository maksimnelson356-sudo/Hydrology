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


GTS_REFERENCE_PATH = Path(__file__).parents[1] / "core" / "gts_reference.py"


def test_gts_probabilities_match_verified_sp58_table_8_2() -> None:
    """Lock the GTS class probabilities to СП 58.13330.2019 table 8.2.

    Verified against the full standard text on 2026-09-28. The code previously
    carried 0.3 / 1.0 / 3.0 % for the main case of classes II–IV and 0.3 / 1.0 %
    for the check case of III–IV, none of which appear in the standard, and the
    whole table had no test at all - which is how five wrong values survived.
    """
    from core.gts_reference import GTS_PROBABILITIES, GTSClass

    # (class, case) -> annual exceedance probability, %, per table 8.2
    verified = {
        (GTSClass.CLASS_I, "osnovnoy"): 0.001,
        (GTSClass.CLASS_II, "osnovnoy"): 0.01,
        (GTSClass.CLASS_III, "osnovnoy"): 0.03,
        (GTSClass.CLASS_IV, "osnovnoy"): 0.05,
        (GTSClass.CLASS_I, "proverochniy"): 0.0001,
        (GTSClass.CLASS_II, "proverochniy"): 0.001,
        (GTSClass.CLASS_III, "proverochniy"): 0.005,
        (GTSClass.CLASS_IV, "proverochniy"): 0.01,
    }

    actual = {
        (gts_class, case): GTS_PROBABILITIES[gts_class]["max_discharge"][case]
        for gts_class in GTSClass
        for case in ("osnovnoy", "proverochniy")
    }

    assert actual == verified


def test_no_live_reference_to_nonexistent_sp58_table_6_1() -> None:
    """«Таблица 6.1» does not exist in СП 58.13330.2019 - probabilities are 8.2.

    A blanket substring check would fire on the module docstring that
    explicitly records the table's non-existence, so the scan keeps only lines
    that still *use* the citation rather than discuss it. The marker match is
    case-insensitive on purpose: the docstring says «НЕТ» in capitals, and a
    case-sensitive filter silently let it through when this test was first
    written.
    """
    offenders: list[str] = []
    for line in GTS_REFERENCE_PATH.read_text(encoding="utf-8").splitlines():
        if not re.search(r"[Тт]абл\w*\s*6\.1", line):
            continue
        lowered = line.lower()
        if any(marker in lowered for marker in ("нет", "опровергнут", "не существует")):
            continue
        offenders.append(line.strip())
    assert not offenders, f"Возвращена ссылка на несуществующую Таблицу 6.1: {offenders}"


def test_sp58_min_discharge_is_labelled_unverified() -> None:
    """СП 58 has no min-discharge probability table - say so in the code.

    The standard only requires «обеспечения минимального расхода, необходимого
    для санитарного попуска» without figures; the values kept in code are an
    engineering estimate and must not be presented as normative. The marker
    lives in the source comments, so the source is what gets scanned - the
    first version of this test inspected the float values and could never pass.
    """
    text = GTS_REFERENCE_PATH.read_text(encoding="utf-8")
    block = text.split("GTS_PROBABILITIES", 1)[1]

    assert "'min_discharge'" in block
    engineering = block.count("инженерная оценка")
    assert engineering >= 8, (
        f"Пометок «инженерная оценка» у min_discharge: {engineering}, ожидалось >= 8 "
        "(по две на каждый из четырёх классов)"
    )
    assert "в СП 58 нет" in block, (
        "В блоке GTS_PROBABILITIES нет прямого указания, что min_discharge "
        "в СП 58 отсутствует"
    )


# Документы и таблицы, которые не подтверждены, опровергнуты или не существуют.
# Проверено по полным текстам 2026-09-28 — см. DOCS/normative_verification_matrix.md.
UNSUBSTANTIATED = (
    "РД 52-26-2008",  # не найден ни в одной из 13 коллекций
    "СП 32.13330.2018",  # «Канализация» — предмет не совпадает
    "Таблица 6.1",  # в СП 58 её нет; вероятности — табл. 8.2
    "табл. 6.1",
    "Таблица 7.1",  # в СП 58 её нет; раздел 7 — реконструкция
    "табл. 7.1",
)


def test_registry_never_presents_unsubstantiated_source_as_standard() -> None:
    """A record must not name a document in `standard`/`clause` that notes call unverified.

    This exact self-contradiction shipped in the registry: `snowmelt` declared
    `standard="РД 52-26-2008"` three lines above a `notes` field admitting the
    document was never checked, and `ice_phenomena` claimed clause 7.72 while its
    notes stated formula 7.51 is not implemented. `standard` and `clause` reach the
    report and the GUI, so a note is not enough to neutralise a false claim there.
    """
    offenders: list[str] = []

    for methodology_id in build_default_registry().ids():
        descriptor = build_default_registry().get(methodology_id)
        live = f"{descriptor.standard} | {descriptor.clause or ''}"
        for marker in UNSUBSTANTIATED:
            if marker in live:
                offenders.append(f"{methodology_id}: «{marker}» в standard/clause")

    assert not offenders, (
        "Неподтверждённый источник вынесен в живое поле реестра, хотя notes "
        f"признаёт его неподтверждённым: {offenders}"
    )


def test_registry_clause_does_not_claim_unimplemented_formula() -> None:
    """A clause must not present a formula as implemented when notes say it is not.

    The marker-list scan in the companion test cannot catch this: «п. 7.72
    (формула 7.51)» contains no string from that list, so reinstating the original
    `ice_phenomena` clause passed silently. Injection 3 of the non-vacuity run
    exposed exactly this, which is why the check is derived from the record's own
    notes rather than from a hand-written list.
    """
    offenders: list[str] = []
    registry = build_default_registry()
    extracted: list[str] = []

    for methodology_id in registry.ids():
        descriptor = registry.get(methodology_id)
        notes = descriptor.notes or ""
        clause = descriptor.clause or ""

        # Формулы, которые notes прямо называет нереализованными.
        # Разделитель — «;», а не точка: между «формула (7.51)» и «не реализована»
        # лежит «из п. 7.72 в core/hydrorash/ice_phenomena.py», где точек много.
        # Регекс с [^.]* молча давал 0 совпадений и тест проходил вхолостую.
        for match in re.finditer(
            r"формул\w*\s*\(?(\d+\.\d+)\)?[^;]{0,200}?не\s+реализован", notes, re.I
        ):
            number = match.group(1)
            extracted.append(f"{methodology_id}:{number}")
            if number not in clause:
                continue
            if re.search(r"НЕ\s+реализован|не\s+реализован", clause):
                continue
            offenders.append(f"{methodology_id}: формула {number} в clause без пометки")

    # Защита от вакуумности: если регекс перестанет извлекать формулы, тест обязан
    # упасть, а молча пропустить всё. Первая версия именно так и молчала.
    assert extracted, (
        "Из notes не извлечено ни одной формулы, объявленной нереализованной - "
        "регекс разъехался с текстом и проверка стала вакуумной"
    )

    assert not offenders, (
        f"clause выдаёт нереализованную формулу за действующую: {offenders}"
    )
