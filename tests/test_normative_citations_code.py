"""Guard against live citations of normative documents that do not say what we claim.

The audit of 2026-09-28 found that the repository had accumulated normative
citations which are simply false, and that they had spread from module
docstrings into the registry, the Markdown docs and the printed report. The
existing test_sp33_clause_citations.py covers one of them (СП 33 section 8)
but only inside core/ and only for that one document. This guard widens both
axes: five known-false reference shapes, and the whole Python tree.

A citation that a module discusses *in order to correct* is legitimate and is
allowed; a module that still leans on it as a basis is not. Detection is
line-based with a +/-3 line context window, which is a deliberate trade-off:
it can be fooled by a refutation stated far from the citation, but it will not
produce false alarms on the corrective notes, which are the common case here.

Verified 2026-09-28 against the full printed texts of СП 33-101-2003,
СП 290.1325800.2016, СП 58.13330.2019 and thirteen РД catalogue collections.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]

# Directories that hold hand-written source we control. Vendored trees and
# build output are excluded: rewriting a third-party file is not a fix.
SCAN_ROOTS = ("core", "tools", "gui", "tests")
SCAN_ROOT_FILES = True
EXCLUDE_PARTS = {"__pycache__", ".venv", "dist", "build", ".git"}

# (name, pattern, why it is false)
FALSE_REFERENCES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "sp33_typo",
        re.compile(r"СП\s*33-11-2003", re.IGNORECASE),
        "СП 33-11-2003 не существует: правильное обозначение СП 33-101-2003",
    ),
    (
        "sp33_section_eight",
        re.compile(
            r"(?:СП\s*33[^|\n]{0,60}?(?:раздел[аеу]?\s*|п\.\s*)8(?:\.\d+)*"
            r"|(?:раздел[аеу]?\s*|п\.\s*)8(?:\.\d+)*[^|\n]{0,60}?СП\s*33)",
            re.IGNORECASE,
        ),
        "раздела 8 в СП 33-101-2003 нет: главы 1–7 плюс приложения А–Г",
    ),
    (
        "sp482_section_nine",
        re.compile(
            r"(?:СП\s*482[^|\n]{0,60}?раздел[аеу]?\s*9|раздел[аеу]?\s*9[^|\n]{0,60}?СП\s*482)",
            re.IGNORECASE,
        ),
        "раздела 9 в СП 482.1325800.2020 нет: перечень состава отчёта — п. 4.13",
    ),
    (
        "sp58_table_six_one",
        re.compile(
            r"(?:СП\s*58[^|\n]{0,60}?[Тт]аблиц[аы]?\s*6\.1"
            r"|[Тт]аблиц[аы]?\s*6\.1[^|\n]{0,60}?СП\s*58)",
            re.IGNORECASE,
        ),
        "таблицы 6.1 в СП 58.13330.2019 нет: вероятности классов ГТС — таблица 8.2",
    ),
    (
        "rd_52_26_2008",
        re.compile(r"РД\s*52[-.]?26[-.]?2008", re.IGNORECASE),
        "РД 52-26-2008 не найден ни в одной из 13 доступных коллекций",
    ),
]

# Wording that legitimately names a false reference to correct it. Kept broad
# on purpose: the cost of a miss is an annoyed maintainer, the cost of a
# wrongly-passed guard is a false compliance claim reaching the user.
NEGATION = re.compile(
    r"не существует|не содержит|не найден|не подтвержд|не проверен|не воспроизвед|"
    r"не реализован|не реализована|не повторя|ошибочн|опровергнут|ранее|прежн|удал|"
    r"приписыв|исправлено|0 раз|нет\b|не установлен|не обоснован|не воспроизведен|"
    r"could not be|cannot be|does not exist|no such|previously|attribut|"
    r"claiming|admitting|admitted|admit|wrong|false|removed|deleted|never existed",
    re.IGNORECASE,
)

CONTEXT = 0
SELF = Path(__file__).resolve()


def _python_files() -> list[Path]:
    files: list[Path] = []
    for name in SCAN_ROOTS:
        base = ROOT / name
        if base.is_dir():
            files.extend(
                p for p in base.rglob("*.py")
                if not (set(p.parts) & EXCLUDE_PARTS)
            )
    if SCAN_ROOT_FILES:
        files.extend(p for p in ROOT.glob("*.py"))
    # This guard quotes every bad pattern on purpose, in its probes. Scanning
    # itself would make the test permanently red for the right words.
    return sorted({p.resolve() for p in files} - {SELF})


def _offenders(text_lines: list[str], index: int, pattern: re.Pattern[str]) -> bool:
    """True when the match at `index` is a live claim rather than a correction."""
    if not pattern.search(text_lines[index]):
        return False
    lo = max(0, index - CONTEXT)
    hi = min(len(text_lines), index + CONTEXT + 1)
    window = "\n".join(text_lines[lo:hi])
    return not NEGATION.search(window)


def test_scan_actually_reads_the_tree() -> None:
    """Non-vacuity: a scan that finds no files would pass every other test here."""
    files = _python_files()
    assert len(files) > 50, f"скан увидел всего {len(files)} файлов — похоже, пути изменились"
    for expected in ("core", "tools", "tests"):
        assert any(expected in p.parts for p in files), f"каталог {expected} не просканирован"


@pytest.mark.parametrize(("name", "pattern", "why"), FALSE_REFERENCES,
                         ids=[r[0] for r in FALSE_REFERENCES])
def test_pattern_is_detectable(name: str, pattern: re.Pattern[str], why: str) -> None:
    """Each rule must fire on a synthetic live claim, or it guards nothing."""
    probe = {
        "sp33_typo": "по СП 33-11-2003 / рекомендациям ГГИ",
        "sp33_section_eight": "СП 33-101-2003, раздел 8",
        "sp482_section_nine": "состав отчёта по разделу 9 СП 482.1325800.2020",
        "sp58_table_six_one": "Пороги по СП 58.13330.2019, Таблица 6.1",
        "rd_52_26_2008": "формула по РД 52-26-2008",
    }[name]
    lines = probe.splitlines()
    assert _offenders(lines, 0, pattern), f"правило {name!r} не ловит пробу: {probe!r} ({why})"


@pytest.mark.parametrize(("name", "pattern", "why"), FALSE_REFERENCES,
                         ids=[r[0] for r in FALSE_REFERENCES])
def test_correction_wording_is_allowed(name: str, pattern: re.Pattern[str], why: str) -> None:
    """A module that explains the mistake must not be forced to hide the history."""
    probe = {
        "sp33_typo": "Ранее писали «СП 33-11-2003» — опечатка, такого документа нет",
        "sp33_section_eight": "Ранее модуль приписывал «СП 33-101-2003 раздел 8.5» - ошибочно",
        "sp482_section_nine": "Раздел 9 СП 482 не существует, перечень - в п. 4.13",
        "sp58_table_six_one": "таблицы 6.1 в СП 58 нет; вероятности - таблица 8.2",
        "rd_52_26_2008": "РД 52-26-2008 не найден ни в одной из 13 коллекций",
    }[name]
    lines = probe.splitlines()
    assert not _offenders(lines, 0, pattern), f"правило {name!r} мешает корректной оговорке"


def test_no_live_false_normative_citations() -> None:
    found: list[str] = []
    for path in _python_files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for i in range(len(lines)):
            for name, pattern, why in FALSE_REFERENCES:
                if _offenders(lines, i, pattern):
                    found.append(
                        f"{path.relative_to(ROOT)}:{i + 1}: [{name}] {why}\n"
                        f"    {lines[i].strip()[:110]}"
                    )
    assert found == [], (
        "живые ссылки на несуществующие нормативные документы "
        "(допустимо упоминание только в виде опровержения):\n" + "\n".join(found)
    )
