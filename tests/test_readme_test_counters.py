"""Охрана счётчиков тестов в README.

Счётчики в README разъезжались ДВАЖДЫ за одну сессию: 797/932 -> 830/965 ->
842/977. Причина одна и та же - числа правятся вручную и молча устаревают, а
README продолжает обещать результат, которого не будет. Человек, читающий
README, должен получать ровно то, что видит после запуска pytest.

Сравнение идёт с РЕАЛЬНЫМ сбором, а не с числом, зашитым в этот тест.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

README = pathlib.Path(__file__).resolve().parents[1] / "README.md"

PATTERN = re.compile(r"(\d+)\s+passed")


def _collected(*args: str) -> int:
    """Число собранных тестов по реальному сбору pytest."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(README.parent),
        check=False,
    )
    out = proc.stdout
    for line in reversed(out.splitlines()):
        m = re.search(r"(\d+)\s+tests? collected", line)
        if m:
            return int(m.group(1))
    raise AssertionError(
        "не удалось разобрать вывод pytest --collect-only:\n"
        + out[-2000:]
        + "\n--- stderr ---\n"
        + proc.stderr[-2000:]
    )


def test_readme_test_counters_are_current() -> None:
    """Числа в README обязаны совпадать с тем, что реально собирается."""
    text = README.read_text(encoding="utf-8")

    suite = _collected("tests")
    root = _collected("--ignore=tests")
    total = suite + root

    stated = {int(n) for n in PATTERN.findall(text)}
    expected = {suite, total}

    assert stated == expected, (
        f"README обещает {sorted(stated)}, а реально собирается "
        f"{suite} в tests/ и {root} в корневых, всего {total}. "
        "Обнови счётчики в README: они разъезжаются."
    )
