"""Нормативная привязка core/hydrorash/min_runoff_extended.py.

Сверка 2026-09-30 по локальному экземпляру
DOCS/NORMATIVE/SP-529.1325800.2023.pdf. Действующая нормативная область
минимального стока — СП 529.1325800.2023, раздел 5.5 «Минимальный сток воды
рек». Что установлено по первоисточнику:

  п. 5.5.1 (стр. 30) — расчёт минимальных расходов при наличии данных
  наблюдений достаточной продолжительности проводят по кривым обеспеченности
  (см. 5.1.3). Для расчётов используют минимальные среднесуточные,
  среднемесячные или 30-суточные (некалендарные) расходы воды, наблюдавшиеся
  в зимний и (или) летне-осенний сезоны. В районах с частыми паводками могут
  быть расчётными минимальные средние расходы воды за 5 и 10 сут.
  п. 5.5.2 (стр. 30) — при резком отклонении последних точек в нижней части
  применяют эмпирические кривы обеспеченности; изгиб обычно в зоне 90 % – 97 %.
  п. 5.5.3 (стр. 30) — при наличии нулевых расходов расчёты по п. 5.1.11.
  п. 7.8.2–7.8.5 (стр. 56) — отдельная ветка: большие и средние реки по данным
  наблюдений, а для неизученных малых равнинных и полугорных рек — зависимости
  (7.41) Qp% = b(A − A1)^m·λp% и (7.42) Qсут p% = k·Q80%·λp% с коэффициентами
  по рекам-аналогам.

Ранее модуль атрибутировал расчёты СП 33-101-2003, п. 5.41–5.43 как действующей
норме. Номера пунктов СП 33 относятся к историческому источнику и на СП 529 не
переносятся: в СП 529 п. 5.5 — расчёт по кривым обеспеченности, а п. 7.8 —
региональные зависимости для неизученных малых рек. Пункт 5.42 СП 33, правило
выбора типа минимума, в текущем модуле не встречается вовсе.

Экосистемный минимум и 7Q10 в СП 529 не установлены: термины
«экологический», «экосистемный», «санитарный», «попуск» и «7Q10» в документе
не встречаются ни разу, а п. 5.5.1 перечисляет 5- и 10-суточные минимумы, но не
7-суточный.

Проверки «пробела нет» выполняются по КОДУ, а не по исходнику целиком: модуль
документирует эти пробелы в докстринге, и поиск по всему файлу давал бы ложное
срабатывание — документирование отсутствия выглядело бы как его наличие.
Комментарии и строковые литералы отбрасываются токенизатором.

Тест не привязан к номерам строк: он опирается на тексты докстрингов и на
значения, которые функции реально возвращают пользователю.
"""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from core.hydrorash import min_runoff_extended as mre

SOURCE = Path(mre.__file__).read_text(encoding="utf-8")

# Без одного из этих маркеров упоминание СП 33 читалось бы как действующая норма.
HISTORICAL_MARKERS = (
    "историческ",
    "снята как действующая",
    "сняты как действующая",
    "не является ссылкой",
    "ошибочн",
    "не переносятся",
)

# Формулировки, выдающие несуществующую норму за действующую.
FALSE_ATTRIBUTION = (
    "соответствует сп 33",
    "реализует сп 33",
    "реализует сп 529",
    "соответствует сп 529",
    "по сп 33-101-2003 п.",
    "по сп 33-101-2003, п.",
)


def code_only(source: str) -> str:
    """Исходник без комментариев и строковых литералов.

    Так отделяется исполняемый код от прозы: докстринг, перечисляющий
    нереализованные пункты, не должен выглядеть как их реализация.
    """
    kept: list[str] = []
    readline = io.StringIO(source).readline
    for token in tokenize.generate_tokens(readline):
        if token.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        kept.append(token.string)
    return " ".join(kept)


CODE = code_only(SOURCE)

MODULE_DOC = mre.__doc__ or ""


def doc_of(name: str) -> str:
    return getattr(mre, name).__doc__ or ""


def _functions() -> tuple:
    """Все функции самого модуля (без импортированных)."""
    return tuple(
        obj
        for name in dir(mre)
        if callable(obj := getattr(mre, name)) and getattr(obj, "__module__", "") == mre.__name__
    )


def all_docstrings() -> dict[str, str]:
    """Докстринги модуля и его функций — без привязки к номерам строк."""
    docs = {"модуль": MODULE_DOC}
    docs.update({f"{f.__name__}": f.__doc__ or "" for f in _functions()})
    return docs


def daily_series(first: int = 1990, last: int = 1999, seed: int = 20260930) -> pd.Series:
    """Многолетний суточный ряд на DatetimeIndex — как ждёт q7_10/q7_30."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(f"{first}-01-01", f"{last}-12-31", freq="D")
    return pd.Series(rng.lognormal(2.0, 0.4, len(idx)), index=idx, name="value")


# --------------------------------------------------------------------------
# 1. Пункты СП 33 не выдаются production-кодом за действующую нормативную базу
# --------------------------------------------------------------------------


@pytest.mark.parametrize("clause", ("5.41", "5.42", "5.43"))
def test_sp33_clause_is_never_given_without_historical_marking(clause: str) -> None:
    """Упоминание 5.41/5.42/5.43 допустимо только как историческая атрибуция.

    Инвариант односторонний: если номер встретился, он обязан нести
    историческую маркировку. Отсутствие номера нарушением не является.
    Берётся текст всего докстринга, а не отдельная строка: переносы внутри
    абзаца не должны ломать проверку.
    """
    hits = {k: v for k, v in all_docstrings().items() if clause in v}
    for where, text in hits.items():
        low = text.lower()
        assert any(m in low for m in HISTORICAL_MARKERS), (
            f"{clause} упомянут в докстринге {where} без исторической "
            f"маркировки — он читается как действующая норма СП 33"
        )


def test_sp33_historical_attribution_is_not_silently_erased() -> None:
    """Прежняя (неверная) привязка остаётся прослеживаемой, но помеченной.

    Если номера исчезнут совсем, модуль перестанет объяснять, откуда взялась
    прежняя атрибуция, и её снова смогут воспроизвести.
    """
    assert "СП 33" in MODULE_DOC, "шапка перестала упоминать исторического источника"
    low = MODULE_DOC.lower()
    assert any(m in low for m in HISTORICAL_MARKERS), (
        "в шапке нет исторической маркировки прежней привязки"
    )


def test_no_false_normative_attribution_in_any_prose() -> None:
    """Ни один докстринг не заявляет соответствие/реализацию по СП 33 или СП 529."""
    offenders = [
        f"{where}: {phrase}"
        for where, text in all_docstrings().items()
        for phrase in FALSE_ATTRIBUTION
        if phrase in text.lower()
    ]
    assert not offenders, f"ложная нормативная атрибуция: {offenders}"


def test_sp33_clause_numbers_never_reach_executable_code() -> None:
    """Номера пунктов не должны попадать в исполняемый код.

    Нормативная привязка — проза. Попадание номера в исполняемую часть означало
    бы, что правило участвует в вычислениях, что не подтверждено первоисточником.
    """
    for number in ("5.41", "5.42", "5.43", "6.4"):
        assert number not in CODE, f"номер {number} просочился в исполняемый код"


def test_sp32_reference_remains_marked_as_wrong() -> None:
    """Прежняя ссылка на СП 32.13330.2018 остаётся помеченной как ошибочная."""
    low = SOURCE.lower()
    if "сп 32.13330.2018" in low:
        assert "ошибочн" in low, "СП 32.13330.2018 упомянут без пометки об ошибке"


# --------------------------------------------------------------------------
# 2. Явная историческая/инженерная маркировка присутствует
# --------------------------------------------------------------------------


def test_module_doc_declares_normative_status_block() -> None:
    """Шапка несёт блок нормативного статуса и не заявляет соответствия в целом."""
    assert "СТАТУС НОРМАТИВНОЙ ПРИВЯЗКИ" in MODULE_DOC
    assert "НЕ УСТАНОВЛЕНО" in MODULE_DOC
    for clause in ("5.5.1", "5.5.2", "5.5.3", "7.8.2", "7.8.5"):
        assert clause in MODULE_DOC, f"шапка перестала фиксировать п. {clause}"


def test_module_doc_marks_742_and_741_as_not_implemented() -> None:
    """(7.41) и (7.42) названы и одновременно помечены как не реализованные."""
    for formula in ("(7.41)", "(7.42)"):
        assert formula in MODULE_DOC, f"{formula} не упомянута в шапке"
    assert re.search(
        r"\(7\.41\).*НЕ РЕАЛИЗОВАНЫ|\(7\.42\).*НЕ РЕАЛИЗОВАНЫ", MODULE_DOC
    ), "формулы (7.41)/(7.42) не помечены как не реализованные"


def test_741_742_are_absent_from_code() -> None:
    """Сами формулы в модуле не вычисляются — в этом суть статуса NOT_IMPLEMENTED."""
    for token in ("7.41", "7.42"):
        assert token not in CODE, f"{token} просочился в исполняемый код"


# --------------------------------------------------------------------------
# 3. ecosystem_minimum и q7_10 не представлены как требования СП 529
# --------------------------------------------------------------------------


@pytest.mark.parametrize("fname", ("ecosystem_minimum", "q7_10"))
def test_source_less_methods_are_marked_source_missing(fname: str) -> None:
    """Докстринг прямо говорит: 7Q10/экос — инженерный метод, СП 529 не установлен."""
    low = doc_of(fname).lower()
    assert "не установлено" in low, f"{fname}: нет явного «соответствие не установлено»"
    assert "инженерн" in low, f"{fname}: метод не помечен как инженерный"
    assert "сп 529" in low, f"{fname}: нет ссылки на действующий стандарт"


def test_ecosystem_minimum_returns_non_attributing_normative_note() -> None:
    """Пользователь в отчёте видит нейтральную пометку, а не ссылку на СП 33."""
    note = mre.ecosystem_minimum(1.0, method="tenpct")["normative"]
    low = note.lower()
    assert "не установлено" in low
    assert "соответствие сп 529" in low
    assert "историческ" in low, "прежняя атрибуция должна остаться помеченной как историческая"
    for phrase in FALSE_ATTRIBUTION:
        assert phrase not in low, f"в ответе функции ложная атрибуция: {phrase}"


def test_ecosystem_minimum_7q10_branch_returns_non_attributing_note() -> None:
    """Ветка 7q10 возвращает ту же нейтральную маркировку."""
    note = mre.ecosystem_minimum(1.0, method="7q10")["normative"]
    low = note.lower()
    assert "не установлено" in low
    for phrase in FALSE_ATTRIBUTION:
        assert phrase not in low, f"в ветке 7q10 ложная атрибуция: {phrase}"


def test_q7_10_returns_non_attributing_normative_note() -> None:
    """7Q10: в ответе прямо сказано, что в СП 529 он не обнаружен."""
    note = mre.q7_10(daily_series())["normative"]
    low = note.lower()
    assert "7q10" in low
    assert "не обнаружен" in low or "не установлен" in low
    assert "10-суточн" in low, "не указано, что п. 5.5.1 даёт 5 и 10 сут, а не 7"
    assert "5- и 10-суточные" in low or "5-суточн" in low, (
        "не указано, что п. 5.5.1 перечисляет 5- и 10-суточные минимумы"
    )
    for phrase in FALSE_ATTRIBUTION:
        assert phrase not in low, f"в q7_10 ложная атрибуция: {phrase}"


def test_q7_10_doc_does_not_claim_sp529_ban() -> None:
    """СП 529 не «запрещает» 7Q10 — он его просто не упоминает."""
    low = doc_of("q7_10").lower()
    assert "запрещ" not in low, "СП 529 не запрещает 7Q10 — запрет формулировать нельзя"


# --------------------------------------------------------------------------
# 4. Частичные участки ссылаются на СП 529 п. 5.5
# --------------------------------------------------------------------------


@pytest.mark.parametrize("fname", ("extract_min_annual", "q7_30", "min_runoff_frequency_curve"))
def test_partial_sections_reference_sp529_clause_55(fname: str) -> None:
    """Участки с частичным соответствием обязаны называть СП 529 и п. 5.5.1."""
    low = doc_of(fname).lower()
    assert "сп 529" in low, f"{fname}: нет ссылки на СП 529.1325800.2023"
    assert "5.5.1" in low, f"{fname}: нет ссылки на п. 5.5.1"
    assert "частичн" in low, f"{fname}: не заявлен частичный характер соответствия"


def test_q7_30_keeps_its_name() -> None:
    """Имя функции не переименовано: переименование — отдельное методологическое решение."""
    assert hasattr(mre, "q7_30")
    assert callable(mre.q7_30)


# --------------------------------------------------------------------------
# 5. Остальные пробелы, зафиксированные ранее
# --------------------------------------------------------------------------


def test_ten_percent_rule_from_sp33_is_absent() -> None:
    """Правило выбора типа минимума по «10 %» (СП 33, п. 5.42) в коде отсутствует."""
    assert "5.42" not in CODE


def test_every_ten_percent_mention_is_about_the_ecological_norm() -> None:
    """Все «10 %» в модуле — экологический норматив, а не правило п. 5.42.

    Проверяются абзацы, а не строки: маркер норматива («ЭКОЛОГИЧЕСКОМУ
    нормативу 0,1·Qср») физически стоит на следующей строке после вхождения,
    и построчная проверка давала бы ложный отказ на любом переносе.

    Абзацы, где «10 %» встречается как раз В ДОКУМЕНТАЦИИ отсутствия
    правила, исключаются: иначе проверка ловила бы собственное описание.
    """
    prose_markers = ("не установлено", "не реализовано", "правило 10 %")
    paragraphs = [
        re.sub(r"\s+", " ", para).strip()
        for para in re.split(r"\n\s*\n", SOURCE)
    ]
    hits = [
        para for para in paragraphs
        if re.search(r"10\s*%", para)
        and not any(m in para.lower() for m in prose_markers)
    ]
    assert hits, "ожидались вхождения «10%» в модуле"
    for para in hits:
        assert (
            "Qср" in para
            or "среднегодов" in para
            or "q_ecos" in para
            or "tenpct" in para
            or "Экосистемн" in para
        ), f"обнаружено «10 %» вне экологического норматива: {para}"


def test_24_day_reduction_is_absent() -> None:
    """Сокращение периода до 24 сут (СП 33, п. 5.42) в коде отсутствует."""
    assert not re.search(r"\b24\b", CODE), "сокращение до 24 сут появилось в коде"


def test_empirical_curves_for_lower_deviation_are_absent() -> None:
    """П. 5.5.2 допускает эмпирические кривые при изгибе 90–97 % — этого в коде нет."""
    assert "эмпирич" not in CODE.lower(), "эмпирические кривые появились в коде"


def test_zero_flow_handling_is_absent() -> None:
    """П. 5.5.3: при нулевых расходах расчёты по 5.1.11 — в коде нет."""
    assert "5.1.11" not in CODE, "появилась обработка по 5.1.11 — проверить нули"


def test_nonhomogeneous_curves_are_absent() -> None:
    """П. 5.5.1 отсылает к усечённым 5.3.4 и составным 5.1.11 — их нет в коде."""
    assert "5.3.4" not in CODE


def test_calendar_monthly_regional_restriction_is_absent() -> None:
    """Региональное ограничение на среднемесячный минимум в коде отсутствует."""
    assert "календарн" not in CODE.lower()


def test_area_dependency_formula_is_absent() -> None:
    """Зависимость от площади водосбора (7.41) требует A, A1, b, m, λ — их нет."""
    for name in ("b, m", "A1", "λp%", "Q80%"):
        assert name not in CODE, f"параметр {name} появился в коде — проверить (7.41)/(7.42)"


def test_code_only_actually_strips_prose() -> None:
    """Сам фильтр проверяется: иначе проверки выше могли бы молча
    превратиться в проверки полного исходника."""
    assert "СТАТУС НОРМАТИВНОЙ ПРИВЯЗКИ" in SOURCE, "ожидалась проза в шапке модуля"
    assert "СТАТУС НОРМАТИВНОЙ ПРИВЯЗКИ" not in CODE, "фильтр не отбросил докстринг"
    assert "5.41" in SOURCE, "ожидалось историческое упоминание 5.41 в прозе"
    assert "5.41" not in CODE, "фильтр не отбросил упоминание из докстринга"


# --------------------------------------------------------------------------
# Функциональная регрессия: расчётная логика не тронута
# --------------------------------------------------------------------------


def test_module_still_extracts_the_three_periods() -> None:
    """Базовая функциональность на месте — регрессию ловим, а не ломаем."""
    rng = np.random.default_rng(20260928)
    daily = pd.DataFrame({
        "year": np.repeat(np.arange(1990, 2000), 365),
        "value": rng.lognormal(2.0, 0.4, 365 * 10),
    })
    for period in (7, 10, 30):
        series = mre.extract_min_annual(
            daily, period_days=period, season="winter"
        )
        assert len(series) == 10, f"период {period} сут дал {len(series)} значений"


def test_q7_30_still_returns_period_values() -> None:
    """q7_30 сохранил прежнюю форму ответа."""
    result = mre.q7_30(daily_series())
    assert set(result["Q30_values"]) == {90, 95, 99}
    assert result["Q30_90"] is not None
