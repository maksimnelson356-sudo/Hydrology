"""Политика (б): при Cs/Cv < 2 поправки (5.6) и (5.7) не применяются вовсе.

Решение принято 2026-09-29 после того, как п. 5.6 был прочитан по печати в высоком
разрешении: коэффициенты a1...a6 и b1...b6 для распределения Крицкого-Менкеля
стандарт берёт из таблицы источника [4], а не из приложения Б. Таблица Б.1 — это
Пирсон III.

СНАЧАЛА БЫЛА ТОЛЬКО Cs. Первый шаг ограничился поправкой (5.7), потому что
расхождение по ней было измерено и очевидно. Но по тексту п. 5.6 зависимость от
распределения касается ВСЕХ двенадцати коэффициентов, включая a1...a6, то есть
поправки Cv. Оставить (5.6) с коэффициентами Пирсона III при Cs/Cv < 2 значило
применить половину меры: Cs без поправки, Cv с чужой поправкой. По решению
пользователя политика распространена и на Cv.

Почему не «посчитать по Б.1 и предупредить». Измеренная величина расхождения при
такой подмене — до 27 % по Cs. И cs, и cv уходят прямо в calculate_frequency_curve
(use_corrected=True по умолчанию), confidence_bands и gts_integration, то есть
неверные числа дошли бы до пользователя. Поправка из чужой таблицы — это не
поправка, а новая ошибка. Чтобы подмена не была гипотетической, в результат
кладутся cv_pearson3_would_be и cs_pearson3_would_be: величина ошибки видна в
каждом конкретном расчёте.

Эти тесты закрывают: саму политику, её распространение на оба коэффициента, её
доход до всех трёх потребителей, границу Cs/Cv = 2, измеримость подмены и запрет
на молчаливое применение поправок при Cs/Cv >= 2.
"""

from __future__ import annotations

import inspect

import numpy as np
import pytest

from core.gts_reference import GTSClass
from core.stats.confidence_bands import pearson3_confidence_bands
from core.stats.frequency import calculate_frequency_curve
from core.stats.gts_integration import build_gts_frequency_curve
from core.stats.parameters import (
    calculate_statistical_parameters,
    sp33_bias_correction_56_57,
)


def km_domain(n: int = 40) -> np.ndarray:
    """Cs/Cv = 1,912 < 2: поправки требуются, но коэффициентов нет в СП 33.

    Отдельно от ряда с Cv < 0,6 и Cs < 1,0, где поправки не требуются вовсе по
    прямому допущению п. 5.6. Здесь они требуются — и именно поэтому не
    применяются.
    """
    return np.random.default_rng(4).gamma(3.0, 1.0, n)


def pearson3_domain(n: int = 40) -> np.ndarray:
    """Cs/Cv = 2,744 >= 2: область Пирсона III, где Б.1 корректна."""
    return np.random.default_rng(1).gamma(2.5, 1.0, n)


def test_fixtures_really_sit_in_the_intended_domains() -> None:
    """Сначала проверяем сами фикстуры, иначе всё остальное проверяет не то.

    Прежний ряд для этих тестов был экспоненциальным и давал Cs/Cv = 1,561, то
    есть попадал в отключённую ветвь. Тесты проходили, проверяя отказ, вместо
    применения поправок.
    """
    km = calculate_statistical_parameters(km_domain(), show_warnings=False)
    assert 0.8 < km["cs"] / km["cv"] < 2.0
    assert km["bias_coefficients_applicable"] is False

    pe = calculate_statistical_parameters(pearson3_domain(), show_warnings=False)
    assert pe["cs"] / pe["cv"] >= 2.0
    assert pe["bias_coefficients_applicable"] is True


def test_both_corrections_not_applied_below_ratio_two() -> None:
    result = calculate_statistical_parameters(km_domain(), show_warnings=False)

    assert result["cs"] / result["cv"] < 2.0
    # Поправки требуются — отказ не в том, что они не нужны.
    assert result["corrections_required"] is True
    assert result["bias_corrections_applied"] is True

    assert result["bias_coefficients_applicable"] is False
    assert result["cv_correction_applied"] is False
    assert result["cs_correction_applied"] is False

    # ГЛАВНОЕ: (5.6) тоже не применяется, а не только (5.7).
    assert result["corrected_cv"] == pytest.approx(result["cv"]), (
        "при Cs/Cv < 2 (5.6) применялась бы с коэффициентами Пирсона III — "
        "это половина меры: Cs без поправки, Cv с чужой"
    )
    assert result["corrected_cs"] == pytest.approx(result["cs"]), (
        "при Cs/Cv < 2 возвращается несмещенная Cs, а не поправка по "
        "коэффициентам Пирсона III"
    )


def test_substitution_is_measurable_not_hypothetical() -> None:
    """Величина подмены видна в каждом расчёте, а не только в тексте.

    Без этого утверждение «подмена недопустима» остаётся доводом, который
    невозможно проверить в чужом расчёте.
    """
    out = sp33_bias_correction_56_57(
        chat_v=0.6615, chat_s=1.2648, n=40, lag1_autocorrelation=0.0
    )
    assert out["applicable_km"] is False
    assert out["cv"] == pytest.approx(0.6615)
    assert out["cs"] == pytest.approx(1.2648)

    # Что дала бы Б.1 — и насколько это далеко от несмещённых значений.
    assert out["cv_pearson3_would_be"] != pytest.approx(out["cv"], abs=1e-6)
    assert out["cs_pearson3_would_be"] != pytest.approx(out["cs"], abs=1e-6)

    # Когда коэффициенты применимы, отказа нет — поля не заполняются.
    ok = sp33_bias_correction_56_57(
        chat_v=0.5, chat_s=1.5, n=40, lag1_autocorrelation=0.0
    )
    assert ok["applicable_km"] is True
    assert ok["cv_pearson3_would_be"] is None
    assert ok["cs_pearson3_would_be"] is None


def test_corrections_still_applied_at_or_above_ratio_two() -> None:
    """Молча отключить поправки нельзя: при Cs/Cv >= 2 коэффициенты Б.1 верны."""
    result = calculate_statistical_parameters(
        pearson3_domain(), show_warnings=False
    )

    assert result["cs"] / result["cv"] >= 2.0
    assert result["bias_coefficients_applicable"] is True
    assert result["cv_correction_applied"] is True
    assert result["cs_correction_applied"] is True
    assert result["corrected_cv"] != result["cv"]
    assert result["corrected_cs"] != result["cs"]
    assert "НЕ ПРИМЕНЕНЫ" not in result["correction_note"]


def test_boundary_at_exactly_two() -> None:
    """Граница Cs/Cv = 2: при 2,0 поправки применяются, при 1,9 — нет."""
    below = sp33_bias_correction_56_57(1.0, 1.9, 40, 0.2)
    at = sp33_bias_correction_56_57(1.0, 2.0, 40, 0.2)

    assert below["cv_correction_applied"] is False
    assert below["cs_correction_applied"] is False
    assert at["cv_correction_applied"] is True
    assert at["cs_correction_applied"] is True
    assert at["cv"] != pytest.approx(1.0)
    assert at["cs"] != pytest.approx(2.0)


def test_note_names_both_corrections_and_the_source() -> None:
    """Пользователь должен видеть, ЧТО не применено и ПОЧЕМУ."""
    result = calculate_statistical_parameters(km_domain(), show_warnings=False)
    note = result["correction_note"]

    assert "НЕ ПРИМЕНЕНЫ" in note
    assert "(5.6)" in note and "(5.7)" in note
    assert "[4]" in note
    assert "Крицкого-Менкеля" in note


@pytest.mark.parametrize(
    "series, expected",
    [(km_domain, False), (pearson3_domain, True)],
    ids=["cs_cv_below_2", "cs_cv_at_or_above_2"],
)
def test_flags_reach_all_three_consumers(series, expected: bool) -> None:
    """Признаки обязаны доходить до кривой, полос и точек ГТС.

    Именно это было дефектом до 2026-09-29: флаг лежал в словаре параметров, и ни
    один потребитель его не проверял, так что неверный Cs уходил в расчёт молча.
    """
    params = calculate_statistical_parameters(series(), show_warnings=False)
    assert params["cs_correction_applied"] is expected

    curve = calculate_frequency_curve(series())
    assert curve.attrs["cs_correction_applied"] is expected
    assert curve.attrs["cv_correction_applied"] is expected
    assert curve.attrs["bias_coefficients_applicable"] is expected
    assert curve.attrs["cs_correction_note"]

    bands = pearson3_confidence_bands(series(), n_bootstrap=25, confidence=0.90)
    assert bands["cs_correction_applied"] is expected
    assert bands["cv_correction_applied"] is expected
    assert bands["normativity_note"]

    gts = build_gts_frequency_curve(series(), GTSClass.CLASS_I)
    assert gts["cs_correction_applied"] is expected
    assert gts["cv_correction_applied"] is expected
    assert gts["normativity_note"]


def test_notes_in_consumers_mention_both_corrections() -> None:
    """Заметки потребителей не должны говорить только про (5.7).

    Формулировка «поправка (5.7) не применена» стала бы неверной: не применены
    обе, и по другой причине, чем отказ при Cv < 0,6 и Cs < 1,0.
    """
    series = km_domain()
    curve = calculate_frequency_curve(series)
    bands = pearson3_confidence_bands(series, n_bootstrap=10, confidence=0.90)
    gts = build_gts_frequency_curve(series, GTSClass.CLASS_I)

    for text in (curve.attrs["cs_correction_note"],
                 bands["normativity_note"],
                 gts["normativity_note"]):
        assert "(5.6)" in text
        assert "(5.7)" in text
        assert "НЕ ПРИМЕНЕНЫ" in text


def test_flag_is_not_a_data_column() -> None:
    """Признаки нормативности — атрибуты, а не столбцы: иначе попадут в выгрузку."""
    series = km_domain()
    curve = calculate_frequency_curve(series)
    assert list(curve.columns) == ["P_%", "Q"]


def test_policy_is_recorded_in_source() -> None:
    """Причина отключения обязана быть в коде, а не только в тесте."""
    doc = inspect.getdoc(sp33_bias_correction_56_57) or ""
    assert "[4]" in doc, "в докстринге назван внешний источник"
    assert "Крицкого-Менкеля" in doc
    assert "НЕ ПРИМЕНЯЮТСЯ ОБЕ ПОПРАВКИ" in doc
    assert "a1...a6" in doc, (
        "в докстринге должно быть сказано, что (5.6) тоже зависит "
        "от распределения, иначе решение выглядит как недосмотр"
    )
    assert "cv_correction_applied" in doc
