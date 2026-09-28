"""Таблица 7.5 и формула (7.51) п. 7.72 СП 33-101-2003.

Перенесено 2026-09-28 из полного печатного экземпляра стандарта (85 стр.).
Ранее модуль объявлял, что предписанная формула из п. 7.72 «здесь НЕ реализована»,
и использовал инженерную оценку с неподтверждённой атрибуцией. Формула реализована,
таблица проверена, а чтение формулы помечено как реконструированное.

ПРОВЕРКА ТАБЛИЦЫ, а не только её перенос: третья строка таблицы 7.5 равна
среднему арифметическому первых двух во всех шести столбцах. Это отношение
содержится в самом стандарте и не могло бы возникнуть при ошибке переноса:

    ΔB/B    зажор  затор  среднее  зажор+затор
    0.0      27.1   17.3    22.20       22.2
    0.2      22.2   14.2    18.20       18.2
    0.4      18.2   11.6    14.90       14.9
    0.6      14.9    9.5    12.20       12.2
    0.8      12.2    7.8    10.00       10.0
    1.0      10.0    6.4     8.20        8.2
"""

from __future__ import annotations

import pytest

from core.hydrorash.ice_phenomena import (
    ICE_JAM_MU_TABLE,
    ice_jam_coefficient_mu,
    ice_jam_level_772,
)

COLUMNS = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
JAM, TOR, BOTH = "зажор", "затор", "зажор+затор"


def test_table_75_third_row_is_the_mean_of_the_first_two() -> None:
    """Подтверждение переноса: отношение из самого стандарта."""
    for x in COLUMNS:
        mean = (ICE_JAM_MU_TABLE[JAM][x] + ICE_JAM_MU_TABLE[TOR][x]) / 2
        assert mean == pytest.approx(ICE_JAM_MU_TABLE[BOTH][x], abs=1e-9), (
            f"при ΔB/B={x} среднее {mean} не совпало с таблицей "
            f"{ICE_JAM_MU_TABLE[BOTH][x]}"
        )


def test_table_75_values_match_the_standard() -> None:
    assert [ICE_JAM_MU_TABLE[JAM][x] for x in COLUMNS] == [27.1, 22.2, 18.2, 14.9, 12.2, 10.0]
    assert [ICE_JAM_MU_TABLE[TOR][x] for x in COLUMNS] == [17.3, 14.2, 11.6, 9.5, 7.8, 6.4]
    assert [ICE_JAM_MU_TABLE[BOTH][x] for x in COLUMNS] == [22.2, 18.2, 14.9, 12.2, 10.0, 8.2]


def test_mu_is_read_exactly_at_table_nodes() -> None:
    for x in COLUMNS:
        assert ice_jam_coefficient_mu(JAM, x) == pytest.approx(ICE_JAM_MU_TABLE[JAM][x])


def test_mu_interpolates_between_nodes() -> None:
    assert ice_jam_coefficient_mu(JAM, 0.5) == pytest.approx(16.55)
    assert ice_jam_coefficient_mu(TOR, 0.5) == pytest.approx(10.55)


def test_mu_clamps_above_the_table_but_rejects_below() -> None:
    """Сверх 1.0 ΔB/B — экстраполяция не делается, значение зажимается.

    Отрицательное отношение физически невозможно, поэтому отклоняется, а не
    зажимается: молчаливый возврат 27,1 скрыл бы ошибку входных данных.
    """
    assert ice_jam_coefficient_mu(JAM, 1.5) == pytest.approx(10.0)
    with pytest.raises(ValueError):
        ice_jam_coefficient_mu(JAM, -0.5)


@pytest.mark.parametrize("alias", ["зажор и затор", "зажор+затор", "зажор+затора", "затор+зажор"])
def test_formation_aliases_resolve_to_one_row(alias: str) -> None:
    """Псевдонимы нужны, потому что «зажор и затор» при наивной замене даёт «зажор++затор»."""
    assert ice_jam_coefficient_mu(alias, 0.0) == pytest.approx(22.2)


def test_formula_751_reproduces_the_manual_calculation() -> None:
    """H = (μ·I^0,3 − 1)·h + H при μ=14,9, I=1 ‰, h=2 м, H=3 м."""
    result = ice_jam_level_772(1.0, 2.0, 3.0, BOTH, 0.4)
    assert result["mu"] == pytest.approx(14.9)
    assert result["rise_m"] == pytest.approx((14.9 * 1.0**0.3 - 1.0) * 2.0, abs=0.001)
    assert result["level_m"] == pytest.approx(
        3.0 + (14.9 * 1.0**0.3 - 1.0) * 2.0, abs=0.001
    )


def test_measured_mu_overrides_the_table() -> None:
    """Стандарт требует определять μ полевыми исследованиями; таблица — запасной вариант."""
    from_table = ice_jam_level_772(1.0, 2.0, 3.0, BOTH, 0.4)
    measured = ice_jam_level_772(1.0, 2.0, 3.0, mu=10.0)
    assert measured["mu"] == 10.0
    assert measured["mu_source"] == "полевое исследование"
    assert "таблица 7.5" in from_table["mu_source"]
    assert measured["rise_m"] != from_table["rise_m"]


def test_result_declares_its_normative_basis() -> None:
    """Структура формулы уточнена по печатной формуле; единица I остаётся открытой."""
    result = ice_jam_level_772(1.0, 2.0, 3.0)
    assert "7.72" in result["formula"]
    assert "(7.51)" in result["formula"]
    assert "I^0,3" in result["formula"]
    assert "показатель степени" in result["normative"]
    assert "Открытым остаётся единица уклона" in result["normative"]


@pytest.mark.parametrize(
    ("kwargs", "why"),
    [
        ({"slope_per_mille": 0.0}, "нулевой уклон: входит в степень 0,3"),
        ({"slope_per_mille": -1.0}, "отрицательный уклон"),
        ({"mean_depth": 0.0}, "нулевая глубина"),
        ({"mu": 0.0}, "нулевой μ"),
        ({"mu": -3.0}, "отрицательный μ"),
        ({"slope_per_mille": 0.1, "mu": 1.0}, "μ·I^0,3 < 1: уровень ниже исходного"),
    ],
)
def test_formula_rejects_unusable_input(kwargs: dict, why: str) -> None:
    base = {"slope_per_mille": 1.0, "mean_depth": 2.0, "normal_level": 3.0}
    base.update(kwargs)
    with pytest.raises(ValueError):
        ice_jam_level_772(**base)


def test_unknown_formation_is_rejected_with_the_allowed_list() -> None:
    with pytest.raises(ValueError, match="зажор"):
        ice_jam_coefficient_mu("неведомое", 0.5)


def test_negative_width_ratio_is_rejected() -> None:
    with pytest.raises(ValueError):
        ice_jam_coefficient_mu(JAM, -0.1)
