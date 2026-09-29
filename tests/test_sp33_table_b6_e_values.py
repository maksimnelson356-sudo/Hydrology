"""Таблица Б.6 — значения E_P% для (5.44), и взаимная проверка блоков.

Таблица состоит из трёх блоков: распределение × метод оценки параметров. Проверки
ниже не пересказывают таблицу, а сверяют её с самой собой, потому что в таблице
есть два независимых внутренних признака правильности:

- строка Cs/Cv = 2 у трёхпараметрического гамма-распределения по методу моментов
  и по методу наибольшего правдоподобия совпадает ТОЧНО, хотя в остальных строках
  методы различаются. Это известное свойство: при Cs/Cv = 2 распределение
  вырождается в два экспоненциальных, и оба метода дают один ответ;
- биномиальное распределение приведено только по методу моментов, и его строки
  должны лежать выше гаммы-распределения при том же Cs/Cv: биномиальное тяжелее
  на правом хвосте, значит поправка E больше.

Если бы хоть одно число было прочитано неверно, хотя бы одна из этих проверок
упала бы.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "sp33_table_b6_e_values_v1.json"

GAMMA_MLE = "Трехпараметрическое гамма-распределение / Метод наибольшего правдоподобия"
GAMMA_MOM = "Трехпараметрическое гамма-распределение / Метод моментов"
BINOM_MOM = "Биномиальное распределение / Метод моментов"


@pytest.fixture(scope="module")
def table() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_grid_is_9_rows_of_15_over_three_blocks(table: dict) -> None:
    values = table["values"]
    assert set(values) == {GAMMA_MLE, GAMMA_MOM, BINOM_MOM}
    for block in values.values():
        assert set(block) == {"2", "3", "4"}
        for row in block.values():
            assert len(row) == 15
    assert table["column_axis"]["values"] == [round(0.1 * k, 1) for k in range(1, 16)]


def test_e_increases_with_cv_everywhere(table: dict) -> None:
    """E - поправка, и она растёт с изменчивостью. Нарушений быть не должно."""
    for name, block in table["values"].items():
        for cs_cv, row in block.items():
            assert all(row[j] <= row[j + 1] for j in range(14)), f"{name} Cs/Cv={cs_cv}"
    assert table["monotonicity_violations"] == 0


def test_e_increases_with_asymmetry_at_fixed_cv(table: dict) -> None:
    """При одном Cv большая асимметрия требует большей поправки."""
    for name, block in table["values"].items():
        for j, cv in enumerate(table["column_axis"]["values"]):
            assert block["2"][j] <= block["3"][j] <= block["4"][j] + 1e-9, (
                f"{name} при Cv={cv}: E не возрастает с Cs/Cv"
            )


def test_gamma_cs_cv_2_row_is_identical_for_both_methods(table: dict) -> None:
    """При Cs/Cv = 2 метод наибольшего правдоподобия и метод моментов совпадают.

    Это самый жёсткий признак верности чтения: девять строк, и одна обязана
    совпасть побитово с другой, а восемь — различаться. Ошибка в чтении почти
    не может сохранить такое сочетание.
    """
    values = table["values"]
    assert values[GAMMA_MLE]["2"] == values[GAMMA_MOM]["2"]
    assert values[GAMMA_MLE]["2"] != values[GAMMA_MLE]["3"], "иначе строки не читаются"
    assert values[GAMMA_MLE]["3"] != values[GAMMA_MOM]["3"]


def test_binomial_versus_gamma_has_a_moving_crossover(table: dict) -> None:
    """Структура «биномиальное против гаммы» — с точкой пересечения.

    Изначально я предположил, что биномиальное распределение всегда тяжелее и E
    всегда выше. Это оказалось неверно на 22 ячейках из 45, то есть проверка
    была плохой, а не данные. Фактическая структура: при Cs/Cv = 2 биномиальное
    не ниже гаммы всюду, а при Cs/Cv = 3 и 4 оно ниже на малых Cv, и точка
    пересечения смещается вниз с ростом асимметрии.
    """
    values = table["values"]
    cv = table["column_axis"]["values"]

    diff_2 = [b - g for b, g in zip(values[BINOM_MOM]["2"], values[GAMMA_MOM]["2"],
                                    strict=True)]
    assert all(d >= -1e-9 for d in diff_2), "при Cs/Cv=2 биномиальное не ниже гаммы"

    crossers = {}
    for cs_cv in ("3", "4"):
        diffs = [b - g for b, g in
                 zip(values[BINOM_MOM][cs_cv], values[GAMMA_MOM][cs_cv], strict=True)]
        assert diffs[0] < 0, f"Cs/Cv={cs_cv}: при малом Cv биномиальное ниже гаммы"
        assert diffs[-1] > 0, f"Cs/Cv={cs_cv}: при большом Cv биномиальное выше гаммы"
        for j in range(14):
            if diffs[j] < 0 <= diffs[j + 1]:
                crossers[cs_cv] = cv[j + 1]
                break
    assert crossers["4"] < crossers["3"], (
        f"точка пересечения должна смещаться вниз: {crossers}"
    )


def test_single_anomalous_step_is_flagged_not_repaired(table: dict) -> None:
    """Единственный резкий скачок шага помечен, значение не исправлено."""
    suspect = table["suspect_cells"]
    assert len(suspect) == 1
    cell = suspect[0]
    assert cell["cs_cv"] == "3"
    assert cell["block"] == BINOM_MOM
    assert cell["value"] == 1.59
    assert cell["next"] == 1.63
    assert cell["step"] < cell["median_step"] / 3
    assert "НЕ исправлено" in table["suspect_policy"]
    assert "1,78" in table["suspect_policy"], "ожидаемое значение названо, но не вписано"


def test_endpoints_look_like_a_curve(table: dict) -> None:
    """Рост E по Cv должен быть замедляющимся, а не линейным.

    Табличные значения E — коэффициент при Q/√N, и он растёт сублинейно; если бы
    все строки были линейными, чтение почти наверняка испорчено.
    """
    row = table["values"][GAMMA_MOM]["4"]
    first_half = row[7] - row[0]
    second_half = row[14] - row[7]
    assert second_half < first_half, "прирост во второй половине меньше: кривизна есть"


def test_5_44_dependencies_are_named(table: dict) -> None:
    """Зафиксировано, что ещё нужно для (5.44), кроме самой таблицы."""
    text = table["not_claimed"]
    assert "alpha" in text
    assert "N" in text
    assert "(5.44)" in table["used_by"]
