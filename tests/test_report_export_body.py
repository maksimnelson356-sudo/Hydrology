"""Отчёт generate_txt_report: тело модуля не исполнял ни один тест.

Покрытие core/stats/report_export.py составляло 3%: невыполненными были
строки 61-195 и 209-241, то есть весь текст отчёта. При этом функция
вызывается из GUI (gui/controller/data_controller.py). Проверочный скрипт
запускался вручную и породил тот же класс дефекта, что и сломанный путь
--file: код выглядел правдоподобным и никогда не выполнялся.

Найденное при таком запуске: ветка вывода о надёжности ряда срабатывала и
при отсутствии reliability_class в stats, печатая «✅ Ряд наблюдений
достаточной надёжности». Отсутствие проверки выдавалось за положительный
вывод - ровно то, что эта работа вообще и устраняет.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from core.stats.report_export import generate_txt_report

_FREQ = pd.DataFrame({"P_%": [1, 50, 99], "Q": [210.0, 110.0, 70.0]})
_MAXQ = pd.DataFrame({"P_%": [1, 10], "Q_max": [420.0, 280.0], "kp": [1.8, 1.3]})
_MINQ = pd.DataFrame({"P_%": [90], "Q_min": [32.0]})


def _report(tmp_path: Path, stats: dict, **kwargs) -> str:
    target = tmp_path / "r.txt"
    generate_txt_report(
        str(target), "р. Сьежа – д. Стан", stats=stats, **kwargs
    )
    return target.read_text(encoding="utf-8-sig")


def test_report_is_produced_with_all_sections(tmp_path):
    text = _report(
        tmp_path,
        {"n": 30, "mean": 112.4, "Cv": 0.22, "Cs": 0.4, "epsilon": 8.1},
        frequency_curve=_FREQ, max_runoff_curve=_MAXQ, min_runoff_curve=_MINQ,
    )
    for marker in ("ТЕХНИЧЕСКИЙ ОТЧЁТ", "СТАТИСТИЧЕСКИЕ ХАРАКТЕРИСТИКИ",
                   "КРИВАЯ ОБЕСПЕЧЕННОСТИ", "МАКСИМАЛЬНЫЙ СТОК",
                   "МИНИМАЛЬНЫЙ СТОК", "ВЫВОДЫ И РЕКОМЕНДАЦИИ"):
        assert marker in text, f"в отчёте нет раздела {marker!r}"


def test_missing_reliability_class_is_not_reported_as_sufficient(tmp_path):
    """Главный дефект: отсутствие проверки выдавалось за положительный вывод."""
    text = _report(tmp_path, {"n": 30, "mean": 112.4})

    assert "✅ Ряд наблюдений достаточной надёжности" not in text
    assert "не проверялась" in text


def test_unexpected_reliability_value_is_not_reported_as_sufficient(tmp_path):
    text = _report(tmp_path, {"n": 30, "reliability_class": "какой-то мусор"})

    assert "✅ Ряд наблюдений достаточной надёжности" not in text
    assert "какой-то мусор" in text


@pytest.mark.parametrize(
    ("value", "marker"),
    [
        ("Ненадёжная", "⚠️ Ряд наблюдений ненадёжный"),
        ("Пониженная надёжность", "⚠️ Ряд наблюдений пониженной надёжности"),
        ("Нормальная достаточная надёжность", "✅ Ряд наблюдений достаточной надёжности"),
    ],
)
def test_known_reliability_classes_render_distinctly(tmp_path, value, marker):
    text = _report(tmp_path, {"n": 30, "reliability_class": value})
    assert marker in text


def test_warnings_are_reported(tmp_path):
    text = _report(tmp_path, {"n": 5, "warnings": ["мало данных"],
                              "length_warnings": ["короткий ряд"]})
    assert "ПРЕДУПРЕЖДЕНИЯ" in text
    assert "мало данных" in text
    assert "короткий ряд" in text


def test_no_warning_block_when_there_are_no_warnings(tmp_path):
    text = _report(tmp_path, {"n": 30, "mean": 1.0})
    assert "ПРЕДУПРЕЖДЕНИЯ" not in text


def test_sp482_reference_carries_the_qualification(tmp_path):
    """Оговорка «НЕ воспроизведён» обязана печататься вместе со ссылкой."""
    text = _report(tmp_path, {"n": 30})
    assert "СП 482" in text
    for line in text.splitlines():
        if "СП 482" in line:
            assert any(
                marker in line
                for marker in ("НЕ воспроизведён", "соответствия нет", "см. п.")
            ), f"ссылка на СП 482 без оговорки: {line.strip()!r}"


def test_empty_stats_does_not_crash(tmp_path):
    text = _report(tmp_path, {})
    assert "ТЕХНИЧЕСКИЙ ОТЧЁТ" in text
