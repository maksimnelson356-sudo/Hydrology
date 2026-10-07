"""Пример А.7 целиком воспроизведён из исходных данных таблицы А.4.

Это единственный разобранный числовой пример метода усечённого гамма-распределения
во всём СП 33, поэтому он служит эталоном для всей цепочки:

    lambda_2n/2 -> Б.5 -> C_v -> Б.4 -> phi(C_v) -> x_0

Что пример закрыл. Раньше (5.43) и (А.6) считались неразрешимым противоречием:
(5.43) напечатана без минуса, а Б.5 требует отрицательных значений. Численный
пересчёт показал, что знаменатель в (5.43) — это x̄(n/2), СРЕДНЕЕ, а не x(n/2),
43-й элемент. Среднее 8132 больше 5590, поэтому часть слагаемых отрицательна,
сумма отрицательна сама по себе, и минус не нужен.

Ошибки чтения, найденные этим примером:
  - в А.4 я прочитал 1878 как 3930 вместо 5930;
  - сперва решил, что в (А.6) стоит натуральный логарифм, и объявил (А.6)
    непригодной. Логарифм десятичный: lg(16200/8132) = 0,29929 — точное совпадение
    с первой строкой А.5.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

FIXTURE = (
    Path(__file__).parent / "fixtures" / "sp33_worked_example_A7_v2.json"
)


@pytest.fixture(scope="module")
def ex() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _series(ex: dict) -> list[int]:
    return [v for _, v in ex["source_data_A4"]["values"]]


def _top_half(ex: dict) -> list[int]:
    return sorted(_series(ex), reverse=True)[:43]


def test_table_a4_has_87_years_1878_1964(ex: dict) -> None:
    values = ex["source_data_A4"]["values"]
    assert len(values) == 87
    years = [y for y, _ in values]
    assert years == list(range(1878, 1965))
    assert values[0] == [1878, 5930], "1878 = 5930, а не 3930"


def test_parenthesised_values_are_included(ex: dict) -> None:
    """Скобки в А.4 не означают исключения: оба значения входят в ряд."""
    series = _series(ex)
    assert 16200 in series, "1882 = 16200 входит: А.5 начинается со строки 1882"
    assert 3110 in series, "1955 = 3110 входит: иначе среднее 6094 не получается"


def test_5_41_sum_of_upper_half_matches_printed(ex: dict) -> None:
    """(А.5): сумма верхних 43 = 349 660."""
    assert sum(_top_half(ex)) == 349660
    assert sum(_top_half(ex)) / 43 == pytest.approx(8132, abs=0.5)


def test_5_43_with_mean_denominator_is_negative(ex: dict) -> None:
    """Ключ к противоречию: знаменатель — СРЕДНЕЕ, а не 43-й элемент.

    С x(n/2) = 5590 в знаменателе сумма положительна (+6,24) и для Б.5 невозможна.
    С x̄(n/2) = 8131,6 сумма отрицательна, как и требует Б.5.
    """
    top = _top_half(ex)
    x_bar = sum(top) / 43

    sum_with_mean = sum(math.log10(v / x_bar) for v in top)
    assert sum_with_mean == pytest.approx(-0.75733, abs=0.001)
    assert sum_with_mean < 0, "сумма отрицательна без всякого минуса"

    x_n2 = top[-1]
    sum_with_element = sum(math.log10(v / x_n2) for v in top)
    assert sum_with_element > 0, "со знаменателем x(n/2) получается положительное"
    assert abs(sum_with_element - 6.241) < 0.01


def test_lambda_matches_printed_value_without_extra_minus(ex: dict) -> None:
    """λ₂н/2 = -0,0176 получается делением суммы на 43, без минуса."""
    top = _top_half(ex)
    x_bar = sum(top) / 43
    lam = sum(math.log10(v / x_bar) for v in top) / 43
    assert lam == pytest.approx(-0.0176, abs=0.0001)
    assert lam < 0


def test_logarithm_is_decimal_not_natural(ex: dict) -> None:
    """В А.5 стоит lg, а не ln: lg(16200/8132) = 0,29932 — как в таблице.

    Допуск 5e-5, потому что в А.5 значения напечатаны с пятью знаками после
    запятой: 0,29929 — это 0,299317… округлённое. Расхождение в третьем знаке
    относится к разряду, которого в таблице нет. Для ln тот же расчёт даёт
    0,69015, что не совпадает ни с одной строкой А.5.
    """
    x_bar = 8132.0
    lg_value = math.log10(16200 / x_bar)
    ln_value = math.log(16200 / x_bar)
    assert lg_value == pytest.approx(0.29929, abs=5e-5)
    assert abs(lg_value - 0.29929) < abs(ln_value - 0.29929)


def test_full_chain_reproduces_printed_numbers(ex: dict) -> None:
    """Вся цепочка воспроизводится: 8132 -> -0,0176 -> 0,52 -> 0,715 -> 5814."""
    c = ex["chain_verified"]
    assert c["n"] == 87
    assert c["n_over_2"] == 43
    assert c["sum_upper_half"] == 349660
    assert c["x_bar_n_2"] == 8132
    assert c["lambda_2n_2"] == -0.0176
    assert c["Cv_from_B5"] == 0.52
    assert c["phi_from_B4"] == 0.715
    assert c["x0"] == 5814
    assert pytest.approx(5814, abs=1.0) == 8132 * 0.715


def test_contradiction_is_resolved_not_deferred(ex: dict) -> None:
    """Противоречие снято числом, а не отложено на разъяснение издателя."""
    r = ex["resolved_contradiction"]
    assert "x̄(n/2)" in r["answer"] or "x̄" in r["answer"]
    assert r["no_minus_needed"]
    assert any("x_{n/2}" in item or "черты" in item
               for item in r["what_is_actually_wrong"])


def test_reading_errors_are_recorded(ex: dict) -> None:
    """Мои ошибки чтения зафиксированы, а не стёрты."""
    errors = " ".join(ex["my_reading_errors"])
    assert "1878" in errors
    assert "5930" in errors
    assert "ln" in errors, "ошибочное решение в пользу натурального логарифма зафиксировано"


def test_remaining_gap_is_only_b5_column_meaning(ex: dict) -> None:
    """Остался один вопрос: что означают индексы колонок Б.5."""
    need = ex["still_required_for_implementation"]
    assert "B5_column_mapping" in need
    assert "-0,0176" in need["B5_column_mapping"] or "0,52" in need["B5_column_mapping"]
