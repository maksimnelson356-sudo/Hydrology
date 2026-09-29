"""Таблица Б.1 СП 33-101-2003: коэффициенты поправок (5.6) и (5.7).

Извлечено 2026-09-28 из печатного экземпляра, стр. 74, проверенной однозначностью
разбора: строка из 8 чисел читается как Cs/Cv + r(1) + шесть коэффициентов,
строка из 7 — как r(1) + шесть коэффициентов с Cs/Cv, унаследованным от первой
строки группы.

Таблица сохранена как фикстур ДО появления реализации, потому что выбранная
задача упирается в (5.8) и (5.9): формулы (5.6) и (5.7) читаются полностью, но
принимают на вход Ĉv и Ĉs, а их определения в текстовом слое нечитаемы.

Эти тесты фиксируют СОДЕРЖАНИЕ таблицы и тот факт, что разбор не был догадкой.
Они не заявляют, что поправки применяются: для этого нужны (5.8) и (5.9).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "sp33_bias_corrections_Б1_v1.json"
)
TABLE = json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_declares_it_is_not_yet_applicable() -> None:
    """Блокер зафиксирован в данных, а не только в переписке."""
    assert "(5.8)" in TABLE["blocker"] and "(5.9)" in TABLE["blocker"]
    assert "ЗАПРЕЩЕНА" in TABLE["blocker"], (
        "должно быть записано, что проверка по правдоподобию запрещена"
    )


def test_formulas_56_and_57_are_recorded_verbatim() -> None:
    assert TABLE["formulas"]["5.6"].startswith("Cv = (a1 + a2/n)")
    assert TABLE["formulas"]["5.7"].startswith("Cs = (b1 + b2/n)")


def test_a_coefficients_cover_the_full_grid() -> None:
    """Сетка таблицы: Cs/Cv ∈ {2, 3, 4} × r(1) ∈ {0, 0,3, 0,5} = 9 строк."""
    assert TABLE["grid"]["cs_cv_values"] == [2.0, 3.0, 4.0]
    assert TABLE["grid"]["r1_values"] == [0.0, 0.3, 0.5]
    assert len(TABLE["a_coefficients"]) == 9

    pairs = {(row["cs_cv"], row["r1"]) for row in TABLE["a_coefficients"]}
    expected = {(cv, r) for cv in (2.0, 3.0, 4.0) for r in (0.0, 0.3, 0.5)}
    assert pairs == expected, "не все сочетания Cs/Cv × r(1) присутствуют"


def test_b_coefficients_cover_all_r1_values() -> None:
    """Для b-коэффициентов таблица задана только по r(1) — трёх строк."""
    assert TABLE["grid"]["r1_values_b"] == [0.0, 0.3, 0.5]
    assert len(TABLE["b_coefficients"]) == 3


@pytest.mark.parametrize("row", TABLE["a_coefficients"], ids=lambda r: f"cs_cv={r['cs_cv']}_r={r['r1']}")
def test_every_a_row_has_six_finite_coefficients(row: dict) -> None:
    assert len(row["a"]) == 6
    assert all(isinstance(x, float) for x in row["a"])
    assert all(x == x for x in row["a"]), "NaN в коэффициентах"


@pytest.mark.parametrize("row", TABLE["b_coefficients"], ids=lambda r: f"r={r['r1']}")
def test_every_b_row_has_six_finite_coefficients(row: dict) -> None:
    assert len(row["b"]) == 6
    assert all(isinstance(x, float) for x in row["b"])


def test_known_values_match_the_printed_table() -> None:
    """Контрольные строки, переписанные с печатной страницы 74 вручную.

    Это независимая от разбора проверка: значения здесь проставлены по
    изображению оригинала, а не извлечены программно.
    """
    a = {(r["cs_cv"], r["r1"]): r["a"] for r in TABLE["a_coefficients"]}
    b = {r["r1"]: r["b"] for r in TABLE["b_coefficients"]}

    # Cs/Cv = 2, r(1) = 0:  0  0,19  0,99  -0,88  0,01  1,54
    assert a[(2.0, 0.0)] == [0.0, 0.19, 0.99, -0.88, 0.01, 1.54]
    # Cs/Cv = 3, r(1) = 0,3:  0  1,15  1,02  -7,53  -0,04  12,38
    assert a[(3.0, 0.3)] == [0.0, 1.15, 1.02, -7.53, -0.04, 12.38]
    # Cs/Cv = 4, r(1) = 0,5:  -0,02  3,47  1,18  -29,71  -0,41  58,08
    assert a[(4.0, 0.5)] == [-0.02, 3.47, 1.18, -29.71, -0.41, 58.08]
    # b при r(1) = 0:  0,03  2,00  0,92  -5,09  0,03  8,10
    assert b[0.0] == [0.03, 2.0, 0.92, -5.09, 0.03, 8.1]
    assert b[0.5] == [0.03, 1.63, 0.92, -0.97, 0.03, 7.94]


def test_a1_is_zero_only_at_the_documented_cells() -> None:
    """Свойство, видимое в таблице и полезное как проверка разбора.

    a1 равен нулю во всех строках, кроме Cs/Cv = 4 при r(1) > 0, где он
    отрицателен. Именно так напечатано; если разбор где-то спутал столбцы,
    это свойство сломается.
    """
    for row in TABLE["a_coefficients"]:
        a1 = row["a"][0]
        if row["cs_cv"] == 4.0 and row["r1"] > 0:
            assert a1 == pytest.approx(-0.02), row
        else:
            assert a1 == pytest.approx(0.0), row
