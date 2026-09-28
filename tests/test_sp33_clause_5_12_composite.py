"""п. 5.12 СП 33-101-2003: реализован только метод «б», формулы (5.23)/(5.24).

Сверка 2026-09-28 по печатному экземпляру. Пункт 5.12 предписывает ДВА метода
построения общей кривой:

  а) в каждом году наблюдаются все однородные элементы (n1 = n2 = n3 = n) —
     (5.21) P = [1 - (1-P1)(1-P2)(1-P3)]·100, для двух элементов
     (5.22) P = (P1 + P2 - P1·P2)·100;
  б) в каждом году имеется лишь одно значение элемента —
     (5.23) P = (n1·P1 + n2·P2 + n3·P3) / (n1 + n2 + n3), для двух
     (5.24) P = (n1·P1 + n2·P2) / (n1 + n2).

В проекте есть только метод «б». Метод «а» не реализован, и выбрать его
нечем. Разница не косметическая: при P1 = P2 = 0,1 формула (5.22) даёт 0,19
против 0,10 у (5.24) — почти вдвое. Формула (5.25) для рядов с нулевыми
значениями тоже отсутствует.

Эти тесты фиксируют не «правильность» (реализовано то, что в стандарте есть),
а соответствие реализованной формулы и размер незакрытого пробела.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.stats.composite_curves import (
    compute_composite_curve,
    compute_composite_curve_rodzhestvensky,
)


def three_categories() -> list[dict]:
    rng = np.random.default_rng(20260928)
    return [
        {"name": "весеннее половодье", "data": rng.normal(120.0, 35.0, 20)},
        {"name": "летняя межень", "data": rng.normal(35.0, 6.0, 25)},
        {"name": "зимняя межень", "data": rng.normal(18.0, 3.0, 30)},
    ]


def test_implemented_composite_equals_formula_523() -> None:
    """Реализация обязана быть ровно взвешенным средним (5.23).

    P_сост = Σ ni·Pi / N при N = Σ ni. Проверяем по внутренностям функции:
    category_curves отдаёт ni и Pi(Q) по той же сетке Q_grid.
    """
    result = compute_composite_curve_rodzhestvensky(three_categories())
    assert "error" not in result, result.get("error")

    total = result["total_years"]
    expected = np.zeros_like(result["Q_grid"], dtype=float)
    for curve in result["category_curves"]:
        expected += (curve["n"] / total) * curve["P_values"]

    assert result["P_composite"] == pytest.approx(expected, abs=1e-9), (
        "составная кривая посчитана не по (5.23) = Σ ni·Pi / N"
    )


def test_weights_are_the_years_of_each_category() -> None:
    """Веса — именно длины рядов, а не число категорий."""
    result = compute_composite_curve_rodzhestvensky(three_categories())
    total = result["total_years"]
    assert total == sum(c["n"] for c in result["category_curves"])
    # доли весов в сумме дают единицу
    assert sum(c["n"] / total for c in result["category_curves"]) == pytest.approx(1.0)


def test_method_a_would_give_a_materially_different_answer() -> None:
    """Пробел с (5.22) — не формальность: показываем величину расхождения.

    При одинаковых вероятностях компонент (5.22) даёт почти вдвое большее
    значение, чем (5.24). Если бы метод «а» подставлялся молча, результат
    расходился бы в разы без всякого признака в выводе.
    """
    p = 0.10
    by_522 = p + p - p * p          # (5.22), вероятности в долях
    by_524 = (10 * p + 10 * p) / 20  # (5.24), равные длины частей
    assert by_522 == pytest.approx(0.19, abs=1e-9)
    assert by_524 == pytest.approx(0.10, abs=1e-9)
    assert by_522 / by_524 == pytest.approx(1.9, abs=1e-6), (
        "расхождение между методами «а» и «б» должно быть существенным, "
        "иначе пробел не стоит фиксировать"
    )


def test_composite_uses_the_weighted_mean_not_the_probabilistic_sum() -> None:
    """Код берёт среднее, а не (5.22) — и это зафиксировано явно.

    Проверяем на данных с равными весами: среднее из (5.23) в точности равно
    среднему арифметическому вероятностей компонент, тогда как (5.22) дало бы
    другое число.
    """
    rng = np.random.default_rng(20260928)
    categories = [
        {"name": "A", "data": rng.normal(100.0, 20.0, 20)},
        {"name": "B", "data": rng.normal(100.0, 20.0, 20)},
    ]
    result = compute_composite_curve_rodzhestvensky(categories)
    mean_of_means = np.mean([c["P_values"] for c in result["category_curves"]], axis=0)
    assert result["P_composite"] == pytest.approx(mean_of_means, abs=1e-9)
    # при равных весах (5.23) — это ровно среднее арифметическое
    assert result["P_composite"] == pytest.approx(
        (result["category_curves"][0]["P_values"]
         + result["category_curves"][1]["P_values"]) / 2,
        abs=1e-9,
    )


def test_two_period_interface_declares_formula_524() -> None:
    """Двухчастный интерфейс — это (5.24), и он это декларирует."""
    years = np.arange(1980, 2000, dtype=float)
    values = np.concatenate([
        np.linspace(140.0, 60.0, 10),
        np.linspace(70.0, 150.0, 10),
    ])
    result = compute_composite_curve(values, years, break_year=1990.0)
    assert "error" not in result, result.get("error")
    assert {"P_%", "Q_часть1", "Q_часть2", "Q_составная"} <= set(result["curve_df"].columns)
    assert result["n_part1"] == 10 and result["n_part2"] == 10


def test_docstrings_keep_declaring_the_missing_methods() -> None:
    """Пробел должен остаться видимым: если о нём забыть, он станет ложью.

    Удаление этих строк означало бы, что документация снова обещает то, чего
    код не делает, — тот же класс дефекта, что закрывался в parameters.py.
    """
    src = (
        __import__("core.stats.composite_curves", fromlist=["x"]).__doc__ or ""
    )
    assert "(5.21)" in src, "докстринг перестал упоминать нереализованную (5.21)"
    assert "(5.22)" in src, "докстринг перестал упоминать нереализованную (5.22)"
    assert "(5.25)" in src, "докстринг перестал упоминать нереализованную (5.25)"
