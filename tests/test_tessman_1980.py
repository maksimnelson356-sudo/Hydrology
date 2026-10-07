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

import json
from pathlib import Path

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


@pytest.mark.parametrize(
    ("mmf", "expected_label", "expected_value"),
    [
        (0.10, "весь естественный сток (MMF < 0,4·MAF)", 0.10),
        (0.39, "весь естественный сток (MMF < 0,4·MAF)", 0.39),
        (0.40, "0,4·MAF", 0.40),   # ровно на пороге 0,4·MAF
        (0.60, "0,4·MAF", 0.40),   # 0,4·MMF=0,24 < 0,4 <= 0,6 -> вторая
        (0.99, "0,4·MAF", 0.40),   # 0,4·MMF=0,396 ещё меньше порога
        (1.00, "0,4·MMF", 0.40),   # MMF == MAF: третья
        (2.00, "0,4·MMF", 0.80),
    ],
)
def test_branch_boundaries(mmf: float, expected_label: str, expected_value: float) -> None:
    """Границы веток: третья ветка срабатывает ТОЛЬКО при MMF >= MAF.

    Условие negation третьей ветки - «0,4·MMF >= 0,4·MAF», то есть месяц не
    суше среднегодового. Поэтому при MMF = 0,99·MAF ещё вторая ветка, а при
    MMF = MAF ровно третья. Путаница между этими двумя случаями легко
    проскакивает и при чтении, и при написании теста - этот параметризованный
    тест написан именно потому, что такая ошибка была допущена.
    """
    result = tessman_1980(1.0, [mmf] * 12)
    row = result["monthly"][0]
    assert row["ветка"] == expected_label
    assert row["Q_эколог"] == pytest.approx(expected_value, abs=0.011)


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


# --- Независимая перепроверка на втором наборе данных ----------------------
#
# Первый набор (Koldan) — опубликованная таблица чужой работы, MAF = 0,78.
# Второй — независимая реализация того же правила, полученная от пользователя
# проекта 2026-09-28, на данных реки с весенним половодьем и MAF = 16,83.
# Он ценен тем, что пересекает границу третьей ветки на реалистичных
# величинах, а не на синтетике: Июнь (MMF = 25 > MAF) уходит в 0,4·MMF,
# а Июль (MMF = 14,5 < MAF) — в 0,4·MAF.
#
# Это НЕ первоисточник. Фикстур фиксирует провенанс явно, чтобы подтверждение
# реализации не было выдано за новый нормативный статус метода.

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "tessman_independent_model_v1.json"
)
MODEL = json.loads(FIXTURE.read_text(encoding="utf-8"))
MODEL_MAF = MODEL["dataset"]["MAF"]
MODEL_MONTHS = MODEL["months"]


def test_independent_model_is_reproduced_month_by_month() -> None:
    result = tessman_1980(MODEL_MAF, [m["MMF"] for m in MODEL_MONTHS])
    assert result["monthly_Q_eco"] == pytest.approx(
        [m["Q_eco"] for m in MODEL_MONTHS], abs=0.005
    ), (
        "помесячный расхождение с независимой моделью: наш "
        f"{result['monthly_Q_eco']}, источник {[m['Q_eco'] for m in MODEL_MONTHS]}"
    )


def test_independent_model_agrees_on_the_branch_of_every_month() -> None:
    """Не только числа, но и то, какая ветка правила сработала."""
    result = tessman_1980(MODEL_MAF, [m["MMF"] for m in MODEL_MONTHS])
    assert [r["ветка"] for r in result["monthly"]] == [
        m["branch"] for m in MODEL_MONTHS
    ], "расхождение веток с независимой моделью"


def test_independent_model_crosses_the_third_branch_boundary() -> None:
    """Июнь и Июль — пара, ради которой набор и подобран.

    0,4·Июня = 10,0 и 0,4·Июля = 5,8: оба выше и ниже порога 6,733 в разные
    стороны, поэтому третью ветку от второй отличает именно условие
    MMF >= MAF, а не величина 0,4·MMF.
    """
    result = tessman_1980(MODEL_MAF, [m["MMF"] for m in MODEL_MONTHS])
    # источник подписывает месяцы полностью («Июнь»), реализация — коротко
    # («Июн»); соответствие проверяется здесь же, чтобы не молча разъехалось
    assert tuple(m["month"][:3] for m in MODEL_MONTHS) == tuple(
        r["Месяц"] for r in result["monthly"]
    ), "подписи месяцев в фикстуре и в реализации разошлись"
    by_month = {r["Месяц"]: r for r in result["monthly"]}
    assert by_month["Июн"]["ветка"] == "0,4·MMF"
    assert by_month["Июл"]["ветка"] == "0,4·MAF"
    # ровно на границе: оба месяца выше порога 0,4·MAF, но только Июнь выше MAF
    assert by_month["Июн"]["Q_ср_месяц"] > MODEL_MAF
    assert by_month["Июл"]["Q_ср_месяц"] < MODEL_MAF
    assert by_month["Июл"]["Q_ср_месяц"] > 0.4 * MODEL_MAF


def test_independent_model_catches_the_naive_misreading() -> None:
    """Фикстур не вакуумный: наивное прочтение правила им ловится.

    Наивная ошибка — схлопнуть правило до двух веток: в сухих месяцах весь
    естественный сток, во всех остальных 0,4·MMF. Тогда в Марте, Июле, Августе
    и Сентябре бралось бы 0,4·MMF вместо удержания 0,4·MAF.
    """
    result = tessman_1980(MODEL_MAF, [m["MMF"] for m in MODEL_MONTHS])
    floor = 0.4 * MODEL_MAF
    naive = [
        m["MMF"] if m["MMF"] < floor else 0.4 * m["MMF"] for m in MODEL_MONTHS
    ]
    assert naive != pytest.approx(result["monthly_Q_eco"], abs=0.005), (
        "фикстур не отличает верное правило от наивного прочтения — он бесполезен"
    )
    # и расхождение приходится ровно на месяцы второй ветки
    differing = {
        m["month"][:3]
        for m, naive_value in zip(MODEL_MONTHS, naive, strict=True)
        if abs(naive_value - m["Q_eco"]) > 0.005
    }
    assert differing == {"Мар", "Июл", "Авг", "Сен"}


def test_independent_model_is_not_claimed_as_primary_source() -> None:
    """Подтверждение реализации не должно превращаться в новый статус."""
    prov = MODEL["provenance"]
    assert prov["is_primary_source"] is False
    assert prov["kind"] == "independent_restatement"
    assert "Tessman S.A. 1980" in prov["note"], (
        "в провенансе должно называться, кто настоящий первоисточник"
    )

