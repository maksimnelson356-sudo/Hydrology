"""Хвосты кривой Крицкого-Менкеля: дефект ПОДТВЕРЖДЁН первоисточником.

Что изменилось 2026-09-29. Раньше расхождение хвостов было измерено численно
(сверка с тремя опубликованными таблицами) и объяснено гипотезой: «возможно,
дальние хвосты считают по биномиальной кривой рекуррентной формулой». Теперь
гипотеза опровергнута, а сам дефект подтверждён авторами самого метода.

ПОДТВЕРЖДЕНИЕ. Рождественский, Ежов, Сахарюк (1990), стр. 43:

    «Я-распределение лишено недостатка, присущего распределению
     Крицкого—Менкеля, связанного с выполаживанием кривых обеспеченности
     в области редкой повторяемости при отношениях Cs/Cv < 2»

То есть сполаживание хвостов при Cs/Cv < 2 — признанный недостаток самого
распределения, а не ошибка расчёта. Наш код воспроизводит распределение верно.

ОПРОВЕРЖЕНИЕ ГИПОТЕЗЫ. Рекуррентная формула в [6] есть, формула (2.49), но она
относится к Я-распределению, а НЕ к хвостам Крицкого-Менкеля. Подменять хвосты
на биномиальные было бы реконструкцией без первоисточника, чего в проекте не
делается.

ЧТО ЭТИ ТЕСТЫ ДЕЛАЮТ. Фиксируют измеренную величину расхождения, чтобы его
нельзя было закрыть подгонкой, и фиксируют подтверждение, чтобы дефект не
чинили заново при следующем изменении кода. Тесты падают, если расхождение
исчезнет: значит его закрыли не по источнику.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pytest
from scipy import stats

from core.stats.frequency import kritsky_menkel_ppf

FIXTURE = (
    pathlib.Path(__file__).parent
    / "fixtures"
    / "sp33_km_tail_defect_confirmed_v1.json"
)
ORDINATES = (
    pathlib.Path(__file__).parent
    / "fixtures"
    / "sp33_km_published_ordinates_v1.json"
)


@pytest.fixture(scope="module")
def data() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_defect_is_recorded_as_confirmed_not_fixed(data: dict) -> None:
    """Дефект подтверждён, но НЕ исправлен, и это зафиксировано явно."""
    status = data["status"]
    assert "ПОДТВЕРЖДЁН" in status
    assert "НЕ ИСПРАВЛЯЕТСЯ" in status

    conf = data["tail_defect"]["independent_confirmation"]
    assert "выполаживанием" in conf["quote"]
    assert "редкой повторяемости" in conf["quote"]
    assert "Cs/Cv < 2" in conf["quote"]
    assert "стр. 43" in conf["location"]


def test_hypothesis_of_binomial_tails_is_ruled_out(data: dict) -> None:
    """Рекуррентная формула из [6] относится к Я-распределению, не к хвостам КМ.

    Проверяется именно запрет: если бы кто-то решил «закрыть хвосты
    биномиальной кривой», опираясь на формулу (2.49), это была бы подмена одного
    распределения другим без первоисточника.
    """
    ruled = data["tail_defect"]["consequences_for_code"]["ruled_out_hypothesis"]
    assert "НЕ подтверждена" in ruled
    assert "(2.49)" in ruled
    assert "Я-распределению" in ruled


def test_clipping_is_semantically_correct_per_source(data: dict) -> None:
    """Обрезка в ноль подтверждена первоисточником, а не подобрана."""
    byproduct = data["useful_byproduct"]["cs_cv_limit_sign"]
    assert "отрицателен" in byproduct
    assert "Cs < 2Cv" in byproduct or "Cs/Cv < 2" in byproduct


def test_measured_gap_is_still_measurable(data: dict) -> None:
    """Расхождение хвостов измеримо и не исчезло.

    Проверяется против трёх независимо опубликованных таблиц: наша кривая
    обрезана в ноль там, где публикация даёт положительные значения.
    """
    pub = json.loads(ORDINATES.read_text(encoding="utf-8"))
    ref = pub["published_kp"]["Cv=0.40"]

    # P = 99,9 %: наша кривая обрезана в ровно 0, публикация положительна.
    # Допуск 0,06 здесь НЕ применяется: расхождение опубликовано как 0,11.
    kp = float(kritsky_menkel_ppf(np.array([0.999]), 1.0, 0.40, 0.40)[0])
    assert kp == pytest.approx(0.0, abs=1e-9), (
        f"P = 99,9 %: наша кривая {kp:.4f} вместо обрезки в ноль. "
        "Расхождение в нижнем хвосте исчезло — если это сделано по "
        "первоисточнику, обнови фикстуру и этот тест явно."
    )
    assert ref[10] > 0.06, "в публикации kp(99,9 %) заметно выше нуля"

    # P = 99 %: расхождение реально, но вдвое меньше, чем на 99,9 %. Допуск 0,02
    # подобран по измеренной дельте 0,042 и по её устойчивости на трёх таблицах.
    kp99 = float(kritsky_menkel_ppf(np.array([0.99]), 1.0, 0.40, 0.40)[0])
    assert kp99 < ref[9] - 0.02, (
        f"P = 99 %: наша кривая {kp99:.4f} против публикационных {ref[9]:.2f}."
    )

    # Обрезка в ноль возникает из-за сдвига A0 = -X̄ при Cs = Cv.
    shift = 1.0 * (1.0 - 2.0 * 0.40 / 0.40)
    assert shift == pytest.approx(-1.0)
    raw = -1.0 + (0.40 * 0.40 / 2.0) * stats.gamma.ppf(
        0.001, a=4.0 / 0.40 ** 2, scale=1.0
    )
    assert raw < 0.0
    assert float(kritsky_menkel_ppf(np.array([0.999]), 1.0, 0.40, 0.40)[0]) == 0.0


def test_source_is_cited_with_page_not_vaguely(data: dict) -> None:
    """Источник назван с библиографией и страницей, как требует проект."""
    meta = data["_meta"]
    assert "Рождественский" in meta["provenance"]
    assert "Ежов" in meta["provenance"]
    assert "1990" in meta["provenance"]
    assert "276" in meta["provenance"]
    # Страница указана рядом с цитатой, а не где-то в конце.
    conf = data["tail_defect"]["independent_confirmation"]
    assert conf["location"].startswith("стр. ")


def test_coefficients_are_still_missing(data: dict) -> None:
    """Книги 1990 года НЕ хватает для коэффициентов (5.6)/(5.7).

    Тест защищает от повторной попытки объявить источник достаточным: если
    таблица коэффициентов появится, тест надо будет переписать осознанно.
    """
    missing = data["what_this_source_does_not_give"]
    assert "НЕТ" in missing["coefficients_5_6_5_7"]
    assert "НЕ хватает" in data["status"] or "[4]" in missing["conclusion"]
    assert "[4]" in missing["conclusion"], (
        "коэффициенты остаются в [4] 1977 года, а не в [6] 1990 года"
    )
