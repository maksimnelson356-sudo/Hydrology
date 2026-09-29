"""Хвосты кривой Крицкого-Менкеля: дефект ПОДТВЕРЖДЁН нормативной таблицей.

ИСТОРИЯ ИСПРАВЛЕНИЙ, обе существенны.

Версия 1 фикстуры утверждала: дефект хвостов НЕ является ошибкой реализации,
наш код воспроизводит именно то распределение, которое описано в первоисточнике.
Основанием была формулировка Рождественского, Ежова, Сахарюка (1990) о сполаживании
хвостов как о свойстве метода.

Это оказалось НЕВЕРНЫМ. Таблица 3 приложения 2 [5] — «Ординаты кривых
трехпараметрического гамма-распределения», стр. 126-127 — даёт при Cs = Cv и
Cv = 0,4 значение kp(99,9 %) = 0,108. Ноль, который даёт наш код, нормативом не
предусмотрен. Учебник РГГМУ 2021 даёт 0,11, то есть воспроизводит [5] верно.

Версия 2 фикстуры отменяет прежний вывод и фиксирует новый: расхождение есть и
в середине кривой (kp(50 %) = 0,954 по [5] против 0,973 у нас), значит проблема
в параметризации, а не только в хвостах.

ЧТО ЭТИ ТЕСТЫ ДЕЛАЮТ. Фиксируют измеренную величину расхождения против
НОРМАТИВНОЙ таблицы, чтобы его нельзя было закрыть подгонкой, и фиксируют
провенанс, чтобы дефект не починили заново. Тесты падают, если расхождение
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

# Нормативные значения [5], таблица 3, приложение 2, стр. 126-127.
# Cs = Cv, Cv = 0,4.
SP33_TABLE_3 = {
    0.1: 2.40,
    50.0: 0.954,
    99.0: 0.229,
    99.9: 0.108,
}


@pytest.fixture(scope="module")
def data() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_previous_conclusion_is_explicitly_retracted(data: dict) -> None:
    """Прежний вывод «не ошибка реализации» обязан быть отменён в тексте.

    Иначе утверждение вернётся при следующем чтении фикстуры — а оно было
    неверным и опровергнуто таблицей 3 [5].
    """
    assert "revision" in data["_meta"]
    note = data["_meta"]["revision_note"]
    assert "НЕВЕРНО" in note or "неверно" in note
    assert "0,108" in note

    cons = data["tail_defect"]["consequences_for_code"]
    now = cons["no_change_warranted"].lower()
    assert "отменён" in now
    assert "0,108" in cons["no_change_warranted"]
    assert "дефект параметризации" in (
        cons["kp_zero_at_high_probability"].lower()
    )


def test_defect_is_confirmed_and_not_fixed(data: dict) -> None:
    """Дефект подтверждён нормативной таблицей, но НЕ исправлен."""
    status = data["status"]
    assert "ПОДТВЕРЖДЁН" in status
    assert "НЕ ИСПРАВЛЕН" in status
    assert "ОТМЕНЁН" in status


def test_authoritative_source_is_identified(data: dict) -> None:
    """Нормативная таблица найдена и названа с источником и страницей."""
    src = data["authoritative_source"]
    assert "Гидрометеоиздат" in src["found"]
    assert "1984" in src["found"]
    tables = src["key_tables"]
    assert "126" in tables["table_3_ordinates_3param_gamma"]
    assert "24-28" in tables["nomograms_mp"]


def test_predecessor_standard_provides_the_nomograms(data: dict) -> None:
    """СНиП 2.01.14-83 приложение 1 содержит те же номограммы, что [5].

    Это снимает необходимость добывать листы 24-28 из [5]: предшественник
    СП 33 отдаёт их в обязательном приложении 1, и файл у нас есть.
    """
    pred = data["predecessor_standard"]
    assert "СНиП 2.01.14-83" in pred["found"]
    assert "обязательном приложении 1" in pred["why_it_matters"]
    assert "не требуется" in pred["why_it_matters"]
    assert "прил. 1" in pred["clause_2_5"]
    nomo = pred["nomogram_read"]
    assert "0,20-0,40" in nomo
    assert "λ2" in nomo
    assert "λ3" in nomo


def test_gap_against_normative_table_is_measurable(data: dict) -> None:
    """Расхождение сверяется с [5] табл. 3, а не с учебником РГГМУ.

    Учебник 2021 г. нормативом не является, хотя и воспроизводит [5] верно.
    Ориентиром служит только таблица 3.
    """
    centre = data["tail_defect"]["consequences_for_code"]["wrong_in_centre_too"]
    assert "таблица 3" in centre["location"].lower()
    assert "РГГМУ" in centre["reading"]

    cv = 0.40
    for p, expected in SP33_TABLE_3.items():
        got = float(kritsky_menkel_ppf(np.array([p / 100.0]), 1.0, cv, cv)[0])
        if p == 99.9:
            # Наш код обрезает в ровно 0 - расхождение максимально.
            assert got == pytest.approx(0.0, abs=1e-9)
            assert expected > 0.10
            continue
        assert got != pytest.approx(expected, abs=0.005), (
            f"P = {p} %: наша кривая {got:.4f} совпала с нормативной табл. 3 "
            f"({expected}). Если это сделано по первоисточнику - обнови "
            "фикстуру и этот тест явно."
        )


def test_root_cause_is_negative_shift_still_holds(data: dict) -> None:
    """Названная причина расхождения остаётся в силе: сдвиг A0 = -X."""
    byproduct = data["useful_byproduct"]["cs_cv_limit_sign"]
    assert "отрицателен" in byproduct

    shift = 1.0 * (1.0 - 2.0 * 0.40 / 0.40)
    assert shift == pytest.approx(-1.0)
    raw = -1.0 + (0.40 * 0.40 / 2.0) * stats.gamma.ppf(
        0.001, a=4.0 / 0.40 ** 2, scale=1.0
    )
    assert raw < 0.0
    assert float(kritsky_menkel_ppf(np.array([0.999]), 1.0, 0.40, 0.40)[0]) == 0.0


def test_binomial_substitution_is_still_ruled_out(data: dict) -> None:
    """Рекуррентная формула из [6] относится к Я-распределению, не к хвостам КМ."""
    ruled = data["tail_defect"]["consequences_for_code"]["ruled_out_hypothesis"]
    assert "НЕ подтверждена" in ruled
    assert "(2.49)" in ruled
    assert "Я-распределению" in ruled


def test_coefficient_crosscheck_supports_our_fixture(data: dict) -> None:
    """Б.1 подтверждена печатью СП 33 стр. 74; расхождение объяснено.

    Текстовый слой СНиП 2.01.14-83 даёт в узле Cs/Cv = 4, r(1) = 0,3 значения
    a1 = 0,02 и a6 = 34,18, тогда как печать СП 33 даёт -0,02 и 34,15. Наша
    фикстура соответствует печати СП 33 - то есть тому стандарту, который мы
    реализуем.
    """
    cc = data["coefficient_crosscheck"]
    assert "б.1" in cc["statement"].lower()
    assert "стр. 74" in cc["authoritative"]
    assert "-0,02" in cc["authoritative"]
    assert "34,15" in cc["authoritative"]

    disc = cc["discrepancy_found"]
    assert disc["node"] == "Cs/Cv = 4, r(1) = 0,3"
    assert disc["snip_2_01_14_83_app2_text_layer"]["a1"] == 0.02
    assert disc["sp33_print_and_our_fixture"]["a1"] == -0.02
    assert "монотонност" in disc["resolution"]
    assert "9 узлах" in disc["all_other_nodes"]


def test_ordinates_fixture_remains_nonnormative(data: dict) -> None:
    """Учебник РГГМУ остаётся не-нормативным, даже если совпадает с [5]."""
    pub = json.loads(ORDINATES.read_text(encoding="utf-8"))
    assert "НЕ НОРМАТИВНЫЙ" in pub["_meta"]["normativity"]
    # И при этом он согласуется с нормативной таблицей - полезно как
    # независимая публикационная сверка, но не как основание.
    assert pub["published_kp"]["Cv=0.40"][9] == 0.23
    assert SP33_TABLE_3[99.0] == 0.229
