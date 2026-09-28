"""tessman_1980 сверяется с опубликованной месячной таблицей.

Источник опорных чисел: Koldan station, таблица «Flow proposed by Tessman»
(колонки MMF / 40 % of MMF / MAF / 40 % of MAF / Flow proposed by Tessman) из
рецензируемой работы по оценке экологического расхода. MAF = 0,78 м³/с,
0,4·MAF = 0,312, в источнике округлено до 0,31.

Данные внешние, поэтому тест ловит не только опечатку в коде, но и подмену
правила: реализация 2026-09-28 повторила все 12 месяцев и средний расход
0,37 м³/с, совпавший с числом в источнике.

Ранее модуль назывался «сезонный Тессман» и реализовывал Q = α_i·Qср·(Q_i/Qср)^β_i
по типам региона. Ни α, ни β, ни типов региона в методе Tessman (1980) нет:
первоисточник — технический отчёт South Dakota State University, а не
нормативный документ. Совпадение старой формулы с реальным Тессманом было бы
совпадением названий.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.hydrorash.ecological_flow import (
    TESSMAN_1980_FLOOR,
    tessman_1980,
    tessmann_seasonal,
)

MAF = 0.78
MMF = [1.16, 1.52, 1.79, 2.37, 0.86, 0.47, 0.16, 0.12, 0.19, 0.10, 0.22, 0.49]
PUBLISHED = [0.46, 0.61, 0.71, 0.95, 0.34, 0.31, 0.16, 0.12, 0.19, 0.10, 0.22, 0.31]


def test_matches_published_monthly_table() -> None:
    got = tessman_1980(MAF, MMF)["monthly_Q_eco"]
    assert got == pytest.approx(PUBLISHED, abs=0.011), (
        f"расхождение с опубликованной таблицей: наш {got}, источник {PUBLISHED}"
    )


def test_mean_matches_published_average() -> None:
    result = tessman_1980(MAF, MMF)
    assert result["mean_Q_eco"] == pytest.approx(0.37, abs=0.005)


def test_dry_months_take_the_whole_natural_flow() -> None:
    """Ключевое свойство метода: экологический расход не превышает естественный."""
    result = tessman_1980(MAF, MMF)
    dry = [r for r in result["monthly"] if r["Q_ср_месяц"] < 0.4 * MAF]
    # 0,4·MAF = 0,312, поэтому ниже порога Июл..Ноя (5 месяцев)
    assert [r["Месяц"] for r in dry] == ["Июл", "Авг", "Сен", "Окт", "Ноя"]
    for row in dry:
        assert row["Q_эколог"] == pytest.approx(row["Q_ср_месяц"], abs=0.011)
    # и ни один месяц не превышает свой естественный расход
    for row in result["monthly"]:
        assert row["Q_эколог"] <= row["Q_ср_месяц"] + 0.011


def test_floor_is_forty_percent_of_maf() -> None:
    result = tessman_1980(MAF, MMF)
    assert TESSMAN_1980_FLOOR == 0.4
    # в отчёте значение округлено до двух знаков, как в источнике
    assert result["floor_0.4_MAF"] == pytest.approx(0.31, abs=0.005)


def test_three_branches_are_all_exercised() -> None:
    branches = {r["ветка"] for r in tessman_1980(MAF, MMF)["monthly"]}
    assert len(branches) == 3, f"ожидались все три ветки правила, встречено {branches}"


def test_even_regime_uses_forty_percent_of_month() -> None:
    result = tessman_1980(1.0, [1.0] * 12)
    assert all(v == pytest.approx(0.4) for v in result["monthly_Q_eco"])


@pytest.mark.parametrize(
    ("annual", "monthly", "why"),
    [
        (0.0, [1.0] * 12, "нулевой MAF"),
        (-1.0, [1.0] * 12, "отрицательный MAF"),
        (1.0, None, "без MMF"),
        (1.0, [1.0] * 6, "шесть месяцев вместо двенадцати"),
        (1.0, [np.nan] * 12, "нечисловые значения"),
    ],
)
def test_rejects_unusable_input(annual: float, monthly: object, why: str) -> None:
    with pytest.raises(ValueError):
        tessman_1980(annual, monthly)  # type: ignore[arg-type]


def test_legacy_function_is_labelled_as_engineering() -> None:
    """Прежняя α/β-конструкция остаётся, но не выдаётся за метод Тессмана."""
    result = tessmann_seasonal(1.0, "central", [1.0] * 12)
    assert "Q_eco_monthly" in result, f"неожиданный набор ключей: {sorted(result)}"
    # источник Тессмана в ней не заявлен
    blob = str(result)
    assert "Tessman 1980" not in blob, (
        "инженерная α/β-конструкция выдаёт себя за документированный метод Тессмана"
    )
