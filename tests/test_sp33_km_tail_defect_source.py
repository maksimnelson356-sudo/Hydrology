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

Версия 3 фикстуры: дефект ИСПРАВЛЕН по первоисточнику, а не подгонкой.
production-функция переведена с моментентной трёхпараметрической гаммы
(A0 = X*(1 − 2Cv/Cs), то есть при Cs = Cv опорная точка отрицательна) на
нормативную таблицу ординат: core.stats.kritsky_tables, Прил. Б табл. 1 ГГИ
2005 = Прил. 2 табл. 3 пособия Гидрометеоиздата 1984, стр. 126-127. Прежние
пробелы в хвостах закрылись, и на всех одиннадцати уровнях кривая сошлась с
учебником РГГМУ 2021 в пределах 0,005 — при том, что учебник остаётся
не-нормативным ориентиром, а основанием служит [5].

САМА ФИКСТУРА sp33_km_tail_defect_confirmed_v1.json НЕ МЕНЯЛАСЬ. Она остаётся
историческим снимком диагноза, и тесты, читающие её текст, проверяют честность
этого снимка, а не текущее поведение кода.

ЧТО ЭТИ ТЕСТЫ ДЕЛАЮТ. Проверяют провенанс и подтверждают, что расхождение с
[5] табл. 3 закрыто. Два теста прежней версии требовали, чтобы расхождение
ОСТАВАЛОСЬ (kp(99,9 %) = 0 и несовпадение ни в одной ячейке) — они были
верны для прежней реализации и падали после исправления; теперь они утверждают
обратное. См. test_gap_against_normative_table_is_closed.
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


def test_fixture_status_is_an_honest_historical_snapshot(data: dict) -> None:
    """Фикстура честно описывает своё состояние - «подтверждён, но не исправлен».

    Имя теста и его содержимое расходятся с текущим кодом намеренно, и это
    должно быть видно. Фикстура v1 - снимок диагноза на тот момент, когда дефект
    был подтверждён и ещё не исправлен; сам дефект после этого ИСПРАВЛЕН по
    первоисточнику. Тест проверяет, что снимок не переписан задним числом, а
    живое поведение проверяют test_gap_against_normative_table_is_closed и
    test_root_cause_is_removed_from_live_code.

    Переписывать фикстуру под исправленный код здесь нельзя: тогда потеряется
    сам диагноз - почему вообще выбрана таблица, а не гамма.
    """
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


def test_gap_against_normative_table_is_closed(data: dict) -> None:
    """Расхождение с [5] табл. 3 закрыто; сверка идёт с таблицей 3, а не с РГГМУ.

    Учебник 2021 г. нормативом не является, хотя и воспроизводит [5] верно.
    Ориентиром служит только таблица 3.

    ИСТОРИЯ ЭТОЙ ПРОВЕРКИ. Прежде тест назывался
    test_gap_against_normative_table_is_measurable и утверждал обратное:
    требовал, чтобы результат НЕ совпадал с таблицей 3 ни в одной ячейке, а
    при P = 99,9 % равнялся ровно нулю. Это было верно для прежней реализации
    на моментентной гамме. Теперь результат совпадает, и расхождение закрыто
    по первоисточнику, а не подгонкой по учебнику.

    ОДИН КОНФЛИКТ ЗАФИКСИРОВАН, НЕ ЗАТРАНУТ. SP33_TABLE_3[50.0] = 0,954 - это
    ячейка Cv = 0,5, а не Cv = 0,4. Для Cv = 0,4 первоисточник даёт 0,972, и
    production-функция теперь даёт ровно 0,972. Константу в этом файле по
    прямому указанию НЕ правим; расхождение зафиксировано здесь явно, чтобы оно
    не выглядело как неточность самой правки.
    """
    centre = data["tail_defect"]["consequences_for_code"]["wrong_in_centre_too"]
    assert "таблица 3" in centre["location"].lower()
    assert "РГГМУ" in centre["reading"]

    cv = 0.40
    MISINDEXED = {50.0}  # в SP33_TABLE_3 эти ячейки принадлежат Cv = 0,5

    for p, expected in SP33_TABLE_3.items():
        got = float(kritsky_menkel_ppf(np.array([p / 100.0]), 1.0, cv, cv)[0])

        if p in MISINDEXED:
            # Проверка индексации, а не совпадения: константа принадлежит
            # другой строке таблицы, поэтому совпадения ждать нельзя.
            assert got == pytest.approx(0.972, abs=1e-9), (
                f"P = {p} %, Cv = {cv}: получено {got:.4f}, ожидалось 0,972 по "
                f"первоисточнику. SP33_TABLE_3[{p}] = {expected} - это ячейка "
                "Cv = 0,5, ошибочно занесённая сюда."
            )
            assert abs(got - expected) > 0.005, (
                f"P = {p} %: {got:.4f} совпало с {expected} - значит в "
                "SP33_TABLE_3 попалось настоящее значение для Cv = 0,4, и "
                "константу надо исправлять явно, а не молча."
            )
            continue

        assert got == pytest.approx(expected, abs=0.005), (
            f"P = {p} %: наша кривая {got:.4f} разошлась с нормативной табл. 3 "
            f"({expected}). Пробел открылся заново - разбирайтесь, что сломалось."
        )


def test_root_cause_is_removed_from_live_code(data: dict) -> None:
    """Диагноз остаётся в силе как объяснение, но из кода он убран.

    Прежде здесь стояло test_root_cause_is_negative_shift_still_holds, и оно
    требовало, чтобы production-функция возвращала ровно 0 при P = 99,9 % -
    то есть закрепляло именно тот симптом, который признано дефектом.

    Теперь утверждается обратное: арифметика сдвига A0 = -X никуда не делась и
    остаётся верной, но обрезки в коде больше нет, и квантиль положителен.
    """
    byproduct = data["useful_byproduct"]["cs_cv_limit_sign"]
    assert "отрицателен" in byproduct

    shift = 1.0 * (1.0 - 2.0 * 0.40 / 0.40)
    assert shift == pytest.approx(-1.0)
    raw = -1.0 + (0.40 * 0.40 / 2.0) * stats.gamma.ppf(
        0.001, a=4.0 / 0.40 ** 2, scale=1.0
    )
    assert raw < 0.0, "арафметика гаммы изменилась - пересчитайте диагноз"

    # Симптом устранён: в коде нет обрезки, значение положительно и равно
    # первоисточнику 0,108 при Cs = Cv, Cv = 0,4.
    got = float(kritsky_menkel_ppf(np.array([0.999]), 1.0, 0.40, 0.40)[0])
    assert got == pytest.approx(0.108, abs=1e-9), (
        f"kp(99,9 %) = {got:.4f}, ожидалось 0,108 по [5] табл. 3. "
        "Обрезка вернулась в код или таблица испорчена."
    )
    assert got > 0.0


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
