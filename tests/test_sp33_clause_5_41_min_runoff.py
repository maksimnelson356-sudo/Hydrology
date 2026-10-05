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
    """Базовая функциональность на месте — регрессию ловим, а не ломаем.

    Кадр несёт колонку month: season="winter" без календаря теперь честно
    отказывает (см. test_absent_calendar_is_an_explicit_error_not_annual),
    поэтому для проверки самих периодов календарь обязан присутствовать.

    Ожидаемое количество — 9, а не 10. Ряд покрывает 10 календарных лет
    (1990…1999), то есть 11 меток расчётного цикла (1990…2000), но полных
    зимних циклов ровно 9 — метки 1991…1999:
      - метка 1990 требует XI–XII 1989 года, которых в кадре нет;
      - метка 2000 требует I–III 2000 года, которых тоже нет;
    неполные краевые циклы отбрасываются (см. test_edge_incomplete_cycles_are_dropped).
    Длина зимнего сезона XI+XII+I+II+III = 151 сут, поэтому на цикл приходится
    151 − period_days + 1 окон (145 / 142 / 122), но в Series попадает по одному
    значению на цикл, то есть 9. Прежнее ожидание 10 получалось из годового
    fallback'а по 10 календарным годам — того самого дефекта, который здесь
    закрыт.
    """
    rng = np.random.default_rng(20260928)
    daily = pd.DataFrame({
        "year": np.repeat(np.arange(1990, 2000), 365),
        "month": np.tile(
            pd.date_range("1989-01-01", periods=365, freq="D").month, 10
        ),
        "value": rng.lognormal(2.0, 0.4, 365 * 10),
    })
    for period in (7, 10, 30):
        series = mre.extract_min_annual(
            daily, period_days=period, season="winter"
        )
        assert len(series) == 9, (
            f"период {period} сут дал {len(series)} значений вместо 9 "
            f"(полных зимних циклов 1991…1999)"
        )


def test_q7_30_still_returns_period_values() -> None:
    """q7_30 сохранил прежнюю форму ответа."""
    result = mre.q7_30(daily_series())
    assert set(result["Q30_values"]) == {90, 95, 99}
    assert result["Q30_90"] is not None


# --------------------------------------------------------------------------
# Методологическая регрессия: сезонный отбор по переданной колонке 'month'
# --------------------------------------------------------------------------


def _contrasting_seasons_years(first: int = 2000, last: int = 2002) -> pd.DataFrame:
    """Ряд с контрастными сезонами, м³/с.

    зима (XI, XII, I, II, III) = 50; летне-осень (VI, VII, VIII, IX, X) = 5;
    остальные месяцы = 30. Годовой минимум 5,0, зимний 50,0 — расхождение
    в 10 раз, поэтому ошибка отбора не может остаться незамеченной.

    Состав летне-осеннего сезона VI-X обязателен по источникам: п. 2.33
    Пособия 1984, п. 5.5.1 СП 529.1325800.2023 и п. 5.42 СП 33-101-2003
    (исторический источник) называют сезон «летне-осенним», поэтому сентябрь
    и октябрь входят в отбор. При составе VI-VIII этот ряд давал бы seasonal
    минимум 30,0 вместо 5,0.

    Ряд намеренно multi-year: расчётный цикл 1 апреля — 31 марта требует
    XI-XII одного года вместе с I-III следующего, поэтому один календарный
    год полного цикла не образует (см. Q2-раздел ниже).
    """
    dates = pd.date_range(f"{first}-01-01", f"{last}-12-31", freq="D")
    months = dates.month
    values = np.where(
        np.isin(months, (11, 12, 1, 2, 3)), 50.0,
        np.where(np.isin(months, (6, 7, 8, 9, 10)), 5.0, 30.0),
    )
    return pd.DataFrame({"year": dates.year, "month": months, "value": values})


def test_season_filter_applies_when_month_column_is_supplied() -> None:
    """Переданная колонка 'month' обязана включать сезонный отбор.

    Раньше df сводился к [year_col, value_col] раньше, чем проверялось
    'month' in df.columns, поэтому проверка была ложна всегда. Итог:
    season='winter' молча давал ГОДОВОЙ минимум 5,0 вместо 50,0 м³/с.
    """
    df = _contrasting_seasons_years()
    assert "month" in df.columns, "исходный DataFrame обязан содержать месяц"

    winter = mre.extract_min_annual(
        df, year_col="year", value_col="value", period_days=7, season="winter"
    )
    assert len(winter) > 0, "полные расчётные циклы обязаны давать значения"
    assert np.allclose(winter.to_numpy(dtype=float), 50.0), (
        f"зимний отбор дал не 50,0: {winter.to_dict()}"
    )

    summer = mre.extract_min_annual(
        df, year_col="year", value_col="value", period_days=7, season="summer"
    )
    assert np.allclose(summer.to_numpy(dtype=float), 5.0), (
        f"летне-осенний отбор (VI-X) дал не 5,0: {summer.to_dict()}"
    )
    # Число циклов у сезонов различается и это законно: VI-X целиком лежат в
    # первом календарном году цикла (апр.-март), поэтому summer даёт три полных
    # цикла, тогда как XI-III переходят через 31 декабря и полными оказываются
    # только два. Приведённый ряд — 2000-01-01 … 2002-12-31.
    assert sorted(summer.index) == [2001, 2002, 2003]
    assert sorted(winter.index) == [2001, 2002]


def test_season_filter_by_column_agrees_with_datetime_index() -> None:
    """Оба способа передачи сведений о месяце дают одинаковый результат."""
    df = _contrasting_seasons_years()
    by_index = df.drop(columns=["month"]).copy()
    by_index.index = pd.DatetimeIndex(
        pd.date_range("2000-01-01", "2002-12-31", freq="D")
    )

    for season, expected in (("winter", 50.0), ("summer", 5.0)):
        by_column = mre.extract_min_annual(
            df, year_col="year", value_col="value", period_days=7, season=season
        )
        by_idx = mre.extract_min_annual(
            by_index, year_col="year", value_col="value", period_days=7, season=season
        )
        assert np.allclose(by_column.to_numpy(dtype=float), expected)
        assert by_column.to_dict() == by_idx.to_dict()


def test_season_filter_survives_shuffled_rows_and_missing_values() -> None:
    """Пропуски не влияют на сезонный отбор (порядок строк — отдельная задача)."""
    with_nan = _contrasting_seasons_years()
    with_nan.loc[with_nan.index[:20], "value"] = np.nan
    got = mre.extract_min_annual(
        with_nan, year_col="year", value_col="value", period_days=7, season="winter"
    )
    assert np.allclose(got.to_numpy(dtype=float), 50.0), (
        f"после dropna зимний отбор изменился: {got.to_dict()}"
    )


def test_season_filter_applies_per_cycle_independently() -> None:
    """Каждый расчётный цикл отбирается по своим месяцам, а не сообщается."""
    df = _contrasting_seasons_years()
    # Удваиваем зимние расходы начиная с 2001 года — циклы после него должны
    # дать 100,0, предыдущие остаются 50,0.
    df = df.copy()
    df.loc[df["year"] >= 2001, "value"] = np.where(
        df.loc[df["year"] >= 2001, "month"].isin([11, 12, 1, 2, 3]), 100.0, 30.0
    )

    got = mre.extract_min_annual(
        df, year_col="year", value_col="value", period_days=7, season="winter"
    )
    assert got.to_dict() == {
        2001: pytest.approx(50.0),
        2002: pytest.approx(100.0),
    }


def test_absent_calendar_is_an_explicit_error_not_annual() -> None:
    """Без сведений о месяце season больше НЕ вырождается в годовой минимум.

    Раньше winter/summer/annual давали один и тот же годовой результат, и
    подпись «30-суточные зимние минимумы» не соответствовала вычисленному
    значению. Теперь отсутствие календаря — явная ошибка.
    """
    dates = pd.date_range("2000-01-01", periods=365, freq="D")
    months = dates.month
    values = np.where(
        np.isin(months, (11, 12, 1, 2, 3)), 50.0,
        np.where(np.isin(months, (6, 7, 8, 9, 10)), 5.0, 30.0),
    )
    df = pd.DataFrame({"year": dates.year, "value": values})
    assert "month" not in df.columns
    assert not hasattr(df.index, "month")

    for season in ("winter", "summer"):
        with pytest.raises(ValueError, match=_NO_CALENDAR_MESSAGE):
            mre.extract_min_annual(
                df, year_col="year", value_col="value", period_days=7, season=season
            )


# --------------------------------------------------------------------------
# Инвариант поиска минимума: минимум СРЕДНИХ в окне, а не минимум значений
# --------------------------------------------------------------------------


def test_sliding_window_returns_minimum_of_window_means() -> None:
    """Искомый минимум — среднее по окну, одиночный провал его не задаёт.

    Это отличает корректный расчёт от ошибки вида «минимум кумулятивной
    суммы (Q − D)»: при наличии одного резкого провала
    min(values) = 1,0, а min средних по 7-суточным окнам — заметно больше.
    """
    values = np.array([100.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 100.0])
    got = mre._sliding_window_min_mean(values, 7)

    first = values[:7].mean()
    last = values[1:].mean()
    assert got == pytest.approx(min(first, last))
    assert got == pytest.approx(last)
    assert got > values.min(), "минимум не должен совпадать с одиночным минимумом"


def test_sliding_window_covers_every_position() -> None:
    """Окно перебирается по всем положениям, включая последнее."""
    values = np.array([10.0, 10.0, 10.0, 3.0, 10.0])
    # Окно 3: [0:3]=10, [1:4]=(10+10+3)/3, [2:5]=(10+3+10)/3 -> минимум 7.666...
    got = mre._sliding_window_min_mean(values, 3)
    assert got == pytest.approx((10.0 + 3.0 + 10.0) / 3.0)
    assert got == pytest.approx(23.0 / 3.0)


def test_sliding_window_returns_none_when_series_shorter_than_window() -> None:
    assert mre._sliding_window_min_mean(np.array([1.0, 2.0]), 7) is None
    assert mre._sliding_window_min_mean(np.array([1.0] * 7), 7) == pytest.approx(1.0)


# --------------------------------------------------------------------------
# Q2. Некалендарное окно не обрывается на границе 31 декабря
#
# Основание: «Пособие по определению расчётных гидрологических
# характеристик», Л.: Гидрометеоиздат, 1984, п. 2.33, с. 31 — 30-суточные
# некалендарные расходы фиксируются «независимо от привязки этих
# 30-суточных периодов к календарному году». Конвенция обозначения года —
# табл. 68, с. 107: «Осень» = X, XI, XII, «Зима» = I, II, III, годы вида
# 1897-98. Расчётный цикл реализации — 1 апреля — 31 марта, метка = год
# окончания.
#
# Тестовый ряд покрывает 2000-01-01 … 2003-12-31, то есть три полных
# расчётных цикла (2001, 2002, 2003) и два неполных по краям (2000 и 2004).
# --------------------------------------------------------------------------

Q2_START = "2000-01-01"
Q2_END = "2003-12-31"


def _q2_frame(low_periods=()) -> pd.DataFrame:
    """Ряд за 2000-01-01 … 2003-12-31; по умолчанию Q = 30 м³/с везде.

    low_periods — список (start, end, value) в формате YYYY-MM-DD.
    """
    dates = pd.date_range(Q2_START, Q2_END, freq="D")
    values = np.full(len(dates), 30.0)
    for start, end, value in low_periods:
        mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
        values[mask] = value
    return pd.DataFrame(
        {"year": dates.year, "month": dates.month, "value": values},
        index=pd.DatetimeIndex(dates),
    )


SPELL_CROSS_YEAR = (("2000-12-22", "2001-01-10", 5.0),)


def test_minimum_window_crosses_31_december() -> None:
    """Ключевой случай п. 2.33: окно через 31 декабря должно существовать.

    22-31.12.2000 и 01-10.01.2001 по 5 м³/с, остальное по 30 м³/с.
    Истинное 30-суточное окно 22.12.2000-20.01.2001 = (20·5 + 10·30)/30.
    """
    df = _q2_frame(SPELL_CROSS_YEAR)
    got = mre.extract_min_annual(
        df, year_col="year", value_col="value", period_days=30, season="winter"
    )
    assert 2001 in got.index, "цикл 2001 (апр. 2000 - март 2001) обязан присутствовать"
    assert float(got.loc[2001]) == pytest.approx(13.333333333333334)
    # Прежнее ошибочное значение — минимум внутри календарного года 2001.
    assert not np.any(np.isclose(got.to_numpy(dtype=float), 21.666666666666668))


def test_minimum_window_inside_single_year_unchanged() -> None:
    """Окно целиком внутри года: результат не меняется."""
    df = _q2_frame((("2001-01-01", "2001-01-10", 7.0),))
    got = mre.extract_min_annual(
        df, year_col="year", value_col="value", period_days=30, season="winter"
    )
    # 01-20.01.2001 = (10·7 + 20·30)/30
    assert float(got.loc[2001]) == pytest.approx(22.333333333333332)


def test_seasonal_result_has_one_value_per_complete_cycle() -> None:
    """Три полных цикла дают три значения; края ряда не дают ничего."""
    got = mre.extract_min_annual(
        _q2_frame(), year_col="year", value_col="value", period_days=30, season="winter"
    )
    assert list(got.index) == [2001, 2002, 2003]


def test_edge_incomplete_cycles_are_dropped() -> None:
    """Крайние циклы с неполным сезоном отбрасываются.

    Цикл 2000 содержит только I-III 2000 (нет XI, XII), цикл 2004 — только
    IV-XII 2003 (нет I, II, III). Оба не должны давать значений.
    """
    got = mre.extract_min_annual(
        _q2_frame(), year_col="year", value_col="value", period_days=30, season="winter"
    )
    assert 2000 not in got.index, "цикл 2000 неполон (нет XI-XII) и должен быть отброшен"
    assert 2004 not in got.index, "цикл 2004 неполон (нет I-III) и должен быть отброшен"


def test_seasonal_index_is_cycle_label() -> None:
    """Индекс seasonal-режима — метка цикла: 2001 = апр. 2000 - март 2001."""
    df = _q2_frame()
    got = mre.extract_min_annual(
        df, year_col="year", value_col="value", period_days=30, season="winter"
    )
    cycle_2001 = df[(df["year"] + (df["month"] >= 4).astype(int)) == 2001]
    assert set(cycle_2001["month"].unique()) == {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12}
    assert set(cycle_2001[cycle_2001["month"].isin([11, 12, 1, 2, 3])]["month"]) == {11, 12, 1, 2, 3}
    assert int(got.index.max()) == 2003
    assert sorted(got.index) == [2001, 2002, 2003]


def test_month_column_matches_datetime_index() -> None:
    """Явный столбец month и DatetimeIndex дают одинаковый результат."""
    with_index = _q2_frame(SPELL_CROSS_YEAR)
    with_column = _q2_frame(SPELL_CROSS_YEAR).reset_index(drop=True)
    a = mre.extract_min_annual(
        with_index, year_col="year", value_col="value", period_days=30, season="winter"
    )
    b = mre.extract_min_annual(
        with_column, year_col="year", value_col="value", period_days=30, season="winter"
    )
    assert a.to_dict() == b.to_dict()


def test_datetime_index_provides_month_for_cross_year_window() -> None:
    """Месяц извлекается из DatetimeIndex, окно через Новый год находится."""
    got = mre.extract_min_annual(
        _q2_frame(SPELL_CROSS_YEAR),
        year_col="year", value_col="value", period_days=30, season="winter",
    )
    assert float(got.loc[2001]) == pytest.approx(13.333333333333334)


def test_nan_values_are_dropped_before_window_search() -> None:
    """Существующее поведение dropna сохраняется."""
    df = _q2_frame(SPELL_CROSS_YEAR)
    df.loc[df.index[:40], "value"] = np.nan
    got = mre.extract_min_annual(
        df, year_col="year", value_col="value", period_days=30, season="winter"
    )
    assert float(got.loc[2001]) == pytest.approx(13.333333333333334)


def test_cycle_shorter_than_period_yields_no_result_and_no_exception() -> None:
    """Цикл короче period_days не даёт значения и не роняет расчёт."""
    short = _q2_frame().iloc[:40].copy()
    got = mre.extract_min_annual(
        short, year_col="year", value_col="value", period_days=30, season="winter"
    )
    assert got.empty


@pytest.mark.parametrize("period", [7, 10])
def test_short_periods_use_same_cross_year_capable_mechanism(period) -> None:
    """period_days = 7 и 10 идут тем же алгоритмом, что и 30."""
    got = mre.extract_min_annual(
        _q2_frame(SPELL_CROSS_YEAR),
        year_col="year", value_col="value", period_days=period, season="winter",
    )
    assert float(got.loc[2001]) == pytest.approx(5.0)
    assert sorted(got.index) == [2001, 2002, 2003]


def test_annual_season_keeps_calendar_years() -> None:
    """season="annual" не переходит на cycle_year и не меняет значения."""
    df = _q2_frame(SPELL_CROSS_YEAR)
    got = mre.extract_min_annual(
        df, year_col="year", value_col="value", period_days=30, season="annual"
    )
    assert sorted(got.index) == [2000, 2001, 2002, 2003]
    # Календарный год 2001 содержит I, II, III 2001, где есть маловодье
    # 01-10.01: (10·5 + 20·30)/30 — календарная группировка сохранена.
    assert float(got.loc[2001]) == pytest.approx((10 * 5.0 + 20 * 30.0) / 30.0)
    # Календарный год 2000: внутри только X, XI, XII 2000 с маловодьем 22-31.12.
    year_2000 = df[df["year"] == 2000]["value"].to_numpy(dtype=float)
    expected = min(
        float(year_2000[i:i + 30].mean()) for i in range(len(year_2000) - 29)
    )
    assert float(got.loc[2000]) == pytest.approx(expected)


def test_absent_month_information_keeps_calendar_year_semantics() -> None:
    """Календарная группировка требует календаря: без него winter отказывает.

    Раньше здесь проверялось, что годовая группировка применяется к winter
    без месяца. После исправления это поведение удалено как искажающее, а
    группировку по календарному году проверяем на season="annual", который
    календаря не требует по контракту.
    """
    df = _q2_frame(SPELL_CROSS_YEAR).drop(columns=["month"]).reset_index(drop=True)
    assert not hasattr(df.index, "month"), "индекс должен быть RangeIndex"

    # winter/summer без календаря — явная ошибка, а не молчаливый годовой итог
    for season in ("winter", "summer"):
        with pytest.raises(ValueError, match=_NO_CALENDAR_MESSAGE):
            mre.extract_min_annual(
                df, year_col="year", value_col="value",
                period_days=30, season=season,
            )

    # annual по-прежнему работает без календаря и группирует по календарному году
    got = mre.extract_min_annual(
        df, year_col="year", value_col="value", period_days=30, season="annual"
    )
    assert sorted(got.index) == [2000, 2001, 2002, 2003]
    # Календарная группировка: окно через 31.12.2000 построить нельзя.
    assert float(got.loc[2001]) == pytest.approx(21.666666666666668)


def test_summer_season_no_regression() -> None:
    """season="summer" работает через цикл; разрыва на границе года не возникает."""
    df = _q2_frame((("2001-07-01", "2001-07-20", 4.0),))
    got = mre.extract_min_annual(
        df, year_col="year", value_col="value", period_days=30, season="summer"
    )
    # VI-X 2001 (летне-осенний сезон) входят в цикл 2002 (апр. 2001 - март 2002).
    # 01-30.07.2001 = (20·4 + 10·30)/30 = 12.6666...
    assert float(got.loc[2002]) == pytest.approx((20 * 4.0 + 10 * 30.0) / 30.0)
    # Цикл 2004 (апр. 2003 - дек. 2003) содержит полное лето 2003 и потому
    # является полным, в отличие от зимних краевых циклов.
    assert sorted(got.index) == [2001, 2002, 2003, 2004]


# --------------------------------------------------------------------------
# Летне-осенний сезон: сентябрь и октябрь обязаны быть достижимы
#
# Основание: п. 2.33 Пособия 1984 («для зимнего и летне-осеннего сезонов»),
# п. 5.5.1 СП 529.1325800.2023 («в зимний и (или) летне-осенний сезоны»),
# п. 5.42 СП 33-101-2003 (исторический источник, на СП 529 не переносится).
# При составе summer_months = [6, 7, 8] осенняя межень была недостижима:
# сентябрь и октябрь не попадали в отбор, поэтому минимум года, приходящийся
# на осень, молча терялся. Тест падал на старой реализации.
# --------------------------------------------------------------------------


SUMMER_AUTUMN_MONTHS = (6, 7, 8, 9, 10)


def _summer_autumn_frame(low_month: int = 10) -> pd.DataFrame:
    """Два полных цикла апр. 2000 - март 2002, месяц low_month = 1,0, иначе 30,0."""
    dates = pd.date_range("2000-04-01", "2002-03-31", freq="D")
    values = np.where(dates.month == low_month, 1.0, 30.0)
    return pd.DataFrame({"year": dates.year, "month": dates.month, "value": values})


def test_summer_season_covers_october() -> None:
    """Октябрь — конец летне-осеннего сезона — обязан входить в отбор."""
    got = mre.extract_min_annual(
        _summer_autumn_frame(10),
        year_col="year", value_col="value", period_days=7, season="summer",
    )
    assert sorted(got.index) == [2001, 2002], "два полных цикла дают две метки"
    assert np.allclose(got.to_numpy(dtype=float), 1.0), (
        f"октябрь не достигнут для season='summer': {got.to_dict()}"
    )


def test_summer_season_covers_september() -> None:
    """Сентябрь — начало осенней половины сезона — обязан входить в отбор."""
    got = mre.extract_min_annual(
        _summer_autumn_frame(9),
        year_col="year", value_col="value", period_days=7, season="summer",
    )
    assert sorted(got.index) == [2001, 2002]
    assert np.allclose(got.to_numpy(dtype=float), 1.0), (
        f"сентябрь не достигнут для season='summer': {got.to_dict()}"
    )


def test_summer_season_still_excludes_april_and_winter_months() -> None:
    """Расширение до VI-X не должно захватывать IV, V и зимние месяцы."""
    df = _q2_frame((("2001-04-15", "2001-04-25", 1.0), ("2001-05-15", "2001-05-25", 1.0)))
    got = mre.extract_min_annual(
        df, year_col="year", value_col="value", period_days=7, season="summer"
    )
    assert sorted(got.index) == [2001, 2002, 2003, 2004]
    # В цикле 2002 апрель и май 2001 лежат вне сезона: минимум остаётся 30,0.
    assert float(got.loc[2002]) == pytest.approx(30.0), (
        f"апрель/май ошибочно попали в летне-осенний отбор: {got.to_dict()}"
    )


def test_summer_season_composition_is_normative_six_to_ten() -> None:
    """Константа сезона обязана быть VI-X, а не VI-VIII."""
    source = Path(mre.__file__).read_text(encoding="utf-8")
    assert "summer_months = [6, 7, 8, 9, 10]" in source, (
        "летне-осенний сезон должен охватывать VI-X по п. 2.33 / 5.5.1 / 5.42"
    )
    doc = doc_of("extract_min_annual")
    assert "летне-осенний период (VI–X)" in doc, (
        "описание параметра season обязано называть сезон летне-осенним VI-X"
    )
    assert "летний период (VI–VIII)" not in doc, (
        "формулировка «летний период (VI–VIII)» противоречит источникам"
    )


def test_sliding_window_itself_is_unchanged() -> None:
    """_sliding_window_min_mean не тронута: перебирает все окна массива."""
    values = np.arange(10, dtype=float)
    expected = min(float(values[i:i + 4].mean()) for i in range(len(values) - 3))
    assert mre._sliding_window_min_mean(values, 4) == pytest.approx(expected)


# --------------------------------------------------------------------------
# Порядок входных строк
#
# Основание: п. 2.33 Пособия 1984, с. 31 — 30-суточные расходы берутся «за
# 30 сут с наименьшим стоком», то есть за ПОДРЯД ИДУЩИЕ календарные сутки.
# Окно строится по соседним строкам (np.convolve), поэтому перестановка строк
# меняла найденное окно при неизменном наборе суток: расхождение до 5.53 м³/с
# на одном и том же ряде. Набор дней от перестановки не меняется, поэтому и
# минимальный средний расход меняться не должен.
# --------------------------------------------------------------------------


def _order_sensitive_frame() -> pd.DataFrame:
    """Суточный ряд 2000-01-01 … 2003-12-31 с убывающим внутрисезонным градиентом.

    Градиент делает порядок строк значимым: при перестановке «30 соседних
    строк» перестают быть 30 соседними сутками. Месяцы вне зимнего сезона
    (IV, V, IX, X) подняты в 60,0, чтобы окно не могло «съехать» на них.
    """
    dates = pd.date_range("2000-01-01", "2003-12-31", freq="D")
    values = np.linspace(40.0, 2.0, len(dates))
    values[np.isin(np.asarray(dates.month), [4, 5, 9, 10])] = 60.0
    return pd.DataFrame(
        {"year": dates.year, "month": dates.month, "value": values},
        index=pd.DatetimeIndex(dates),
    )


@pytest.mark.parametrize("seed", [1, 42, 2026, 7, 99])
def test_result_is_independent_of_input_row_order(seed) -> None:
    """Перестановка тех же строк не должна менять минимальный 30-суточный расход."""
    frame = _order_sensitive_frame()
    reference = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="winter"
    )
    assert sorted(reference.index) == [2001, 2002, 2003]

    shuffled = frame.sample(frac=1.0, random_state=seed)
    assert len(shuffled) == len(frame), "набор строк должен быть тем же"

    got = mre.extract_min_annual(
        shuffled, year_col="year", value_col="value", period_days=30, season="winter"
    )
    assert got.to_dict() == reference.to_dict(), (
        f"порядок строк изменил результат (seed={seed}): "
        f"{got.to_dict()} != {reference.to_dict()}"
    )


def test_shuffled_input_window_matches_calendar_consecutive_days() -> None:
    """Найденное окно совпадает с минимумом по подряд идущим календарным суткам.

    Ожидаемое значение вычисляется независимо: сезонные месяцы каждого цикла
    отбираются, сортируются по дате и перебираются все окна длиной 30 суток.
    Так утверждается буквальное требование п. 2.33 — «за 30 сут с наименьшим
    стоком», то есть за ПОДРЯД ИДУЩИЕ календарные сутки, а не соседние строки
    входной таблицы.
    """
    frame = _order_sensitive_frame()
    shuffled = frame.sample(frac=1.0, random_state=42)

    for season, months in (
        ("winter", (11, 12, 1, 2, 3)),
        ("summer", (6, 7, 8, 9, 10)),
    ):
        got = mre.extract_min_annual(
            shuffled, year_col="year", value_col="value",
            period_days=30, season=season,
        )

        reference = frame.copy()
        reference["_cyc"] = reference["year"] + (reference["month"] >= 4).astype(int)
        checked = 0
        for label, group in reference.groupby("_cyc"):
            if not set(months).issubset(set(group["month"].unique())):
                continue
            sub = group[group["month"].isin(months)].sort_index()
            vals = sub["value"].to_numpy(dtype=float)
            if len(vals) < 30:
                continue
            expected = min(float(vals[i:i + 30].mean()) for i in range(len(vals) - 29))
            assert float(got.loc[label]) == pytest.approx(expected), (
                f"{season}, цикл {label}: получено {got.loc[label]}, "
                f"минимум по календарным суткам {expected}"
            )
            checked += 1
        assert checked >= 2, f"{season}: проверено слишком мало циклов ({checked})"


def test_month_only_input_still_finds_cross_year_window() -> None:
    """Без временного индекса сортировка не должна разрушать переход 31 декабря.

    Ось защиты: ключ сортировки обязан быть хронологическим. Сортировка по
    одному месяцу поставила бы январь раньше декабря и разорвала бы окно
    через Новый год.
    """
    df = _q2_frame(SPELL_CROSS_YEAR).reset_index(drop=True)
    assert not hasattr(df.index, "month"), "индекс должен быть RangeIndex"
    got = mre.extract_min_annual(
        df, year_col="year", value_col="value", period_days=30, season="winter"
    )
    # 22.12.2000-20.01.2001 = (20*5 + 10*30)/30 — те же 13.3333..., что и
    # при DatetimeIndex: порядок месяцев внутри цикла остаётся XI, XII, I, II, III.
    assert float(got.loc[2001]) == pytest.approx(13.333333333333334)


def test_extraction_does_not_mutate_caller_frame() -> None:
    """Вызывающий DataFrame не должен изменяться."""
    frame = _order_sensitive_frame()
    before = frame.copy()

    shuffled = frame.sample(frac=1.0, random_state=42)
    snapshot = shuffled.copy()
    mre.extract_min_annual(
        shuffled, year_col="year", value_col="value", period_days=30, season="winter"
    )
    pd.testing.assert_frame_equal(shuffled, snapshot)
    pd.testing.assert_frame_equal(frame, before)


# --------------------------------------------------------------------------
# Тип индекса не должен влиять на хронологический порядок
#
# Ревизия выявила, что DatetimeIndex — не единственный носитель календарной
# даты. PeriodIndex и object-индекс из datetime/date/Timestamp тоже её несут,
# но прежняя проверка isinstance(..., pd.DatetimeIndex) их не узнавала:
#   - PeriodIndex попадал в ветку «только месяц», и сутки внутри месяца
#     оставались в случайном порядке — 30-суточное окно переставало быть
#     окном подряд идущих календарных суток;
#   - object-индекс из дат не давал month_col вовсе, поэтому season="winter"
#     молча превращался в годовой минимум.
# ---------------------------------------------------------------------------


def _cross_year_frame(index_factory) -> pd.DataFrame:
    """2000-01-01 … 2003-12-31; 22.12.2000-10.01.2001 = 5 м³/с, остальное 30.

    Индекс строится через index_factory, чтобы один и тот же ряд проверить
    с разными типами индекса.
    """
    dates = pd.date_range("2000-01-01", "2003-12-31", freq="D")
    values = np.full(len(dates), 30.0)
    values[(dates >= "2000-12-22") & (dates <= "2001-01-10")] = 5.0
    frame = pd.DataFrame({"year": dates.year, "month": dates.month, "value": values})
    frame.index = index_factory(dates)
    return frame


INDEX_FACTORIES = {
    "datetime": pd.DatetimeIndex,
    "period": lambda d: pd.PeriodIndex(d, freq="D"),
    "object_timestamp": lambda d: pd.Index(list(d), dtype=object),
}


@pytest.mark.parametrize("kind", sorted(INDEX_FACTORIES))
def test_calendar_index_type_does_not_change_result(kind: str) -> None:
    """Любой индекс с календарной датой даёт тот же календарный минимум."""
    frame = _cross_year_frame(INDEX_FACTORIES[kind])
    reference = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="winter"
    )
    # 22.12.2000-20.01.2001 = (20*5 + 10*30)/30 — окно через 31 декабря.
    assert float(reference.loc[2001]) == pytest.approx(13.333333333333334)

    shuffled = frame.sample(frac=1.0, random_state=42)
    got = mre.extract_min_annual(
        shuffled, year_col="year", value_col="value", period_days=30, season="winter"
    )
    assert got.to_dict() == reference.to_dict(), (
        f"тип индекса {kind}: порядок строк изменил результат "
        f"{got.to_dict()} != {reference.to_dict()}"
    )


@pytest.mark.parametrize("kind", sorted(INDEX_FACTORIES))
def test_calendar_index_keeps_season_filter_active(kind: str) -> None:
    """season='winter' обязан фильтровать по сезону при любом типе индекса.

    Защита от регрессии, при которой зимний запрос молча превращается в
    годовой: вне сезона (IV, V, IX, X) стоят 60,0, поэтому годовой минимум
    заметно отличается от зимнего.
    """
    frame = _cross_year_frame(INDEX_FACTORIES[kind])
    frame.loc[frame["month"].isin([4, 5, 9, 10]), "value"] = 60.0

    winter = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="winter"
    )
    annual = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="annual"
    )
    assert float(winter.loc[2001]) == pytest.approx(13.333333333333334)
    assert float(annual.loc[2001]) > float(winter.loc[2001]), (
        "сезонный отбор не изменил результат — фильтр не применился"
    )


@pytest.mark.parametrize("kind", sorted(INDEX_FACTORIES))
def test_calendar_index_does_not_mutate_caller_frame(kind: str) -> None:
    """Приведение индекса к временной шкале не мутирует кадр вызывающего."""
    frame = _cross_year_frame(INDEX_FACTORIES[kind])
    shuffled = frame.sample(frac=1.0, random_state=7)
    before = shuffled.copy()
    index_before = shuffled.index.copy()

    mre.extract_min_annual(
        shuffled, year_col="year", value_col="value", period_days=30, season="winter"
    )
    pd.testing.assert_frame_equal(shuffled, before)
    assert shuffled.index.equals(index_before), "индекс вызывающего изменился"
    assert type(shuffled.index) is type(index_before), "тип индекса изменился"


def test_non_calendar_index_is_not_silently_converted() -> None:
    """Неоднозначный индекс не приводится к дате молча.

    Строковый, целочисленный и смешанный индексы календарную дату не несут,
    поэтому функция не должна пытаться их разбирать: для них остаётся
    позиция месяца внутри цикла, что для месячного разрешения достаточно.
    """
    frame = _cross_year_frame(lambda d: pd.Index([str(x.date()) for x in d]))
    assert mre._calendar_order_key(frame.index) is None

    assert mre._calendar_order_key(pd.RangeIndex(5)) is None
    assert mre._calendar_order_key(pd.Index([1, 2, 3])) is None
    assert mre._calendar_order_key(pd.Index([None, "2000-01-02"])) is None

    for kind in INDEX_FACTORIES:
        key = mre._calendar_order_key(_cross_year_frame(INDEX_FACTORIES[kind]).index)
        assert key is not None, f"{kind}: календарный индекс должен давать ключ"
        assert len(key) == 1461


# --------------------------------------------------------------------------
# Объектный календарный индекс БЕЗ колонки month
#
# Ревизия выявила расхождение: _calendar_order_key() относит object-индексы
# из Timestamp и datetime.date к календарным (inferred_type 'datetime'/'date'
# входят в _CALENDAR_INFERRED_TYPES), но определение month в extract_min_annual
# опиралось только на hasattr(index, 'month'). У таких индексов атрибута .month
# нет, поэтому month_col оставался None:
#   - до исправления season="winter" молча превращался в годовой минимум;
#   - после запрета fallback'а guard ошибочно отвергал поддерживаемый календарь.
# Теперь месяц берётся из временной шкалы по тому же признаку календарности.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("index_factory", [
    lambda d: pd.Index([x.date() for x in d], dtype=object),
    lambda d: pd.Index(list(d), dtype=object),
], ids=["object_date", "object_timestamp"])
def test_object_calendar_index_yields_month_without_month_column(
    index_factory,
) -> None:
    """A/B. object-индекс дат без month даёт СЕЗОННЫЙ результат, не ValueError.

    Проверяется не отсутствие исключения, а правильное использование месяца:
    на контрастном ряду winter обязан дать 50,0, а summer — 5,0.
    """
    frame = _seasonal_frame()
    frame = frame.set_axis(index_factory(frame.index))
    assert "month" not in frame.columns, "колонка month отсутствует намеренно"
    assert getattr(frame.index, "inferred_type", None) in {"datetime", "date"}
    assert not hasattr(frame.index, "month"), "у объектного индекса нет .month"
    assert mre._calendar_order_key(frame.index) is not None, (
        "индекс обязан признаваться календарным — иначе тест проверяет не то"
    )

    winter = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="winter"
    )
    summer = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="summer"
    )

    assert float(winter.min()) == pytest.approx(50.0), (
        f"зимний отбор не применён: {winter.to_dict()}"
    )
    assert float(summer.min()) == pytest.approx(5.0), (
        f"летне-осенний отбор не применён: {summer.to_dict()}"
    )


@pytest.mark.parametrize("index_factory", [
    lambda d: pd.Index([x.date() for x in d], dtype=object),
    lambda d: pd.Index(list(d), dtype=object),
], ids=["object_date", "object_timestamp"])
def test_object_calendar_index_agrees_with_datetime_index(index_factory) -> None:
    """C. Сезонный отбор не зависит от типа календарного индекса."""
    base = _seasonal_frame()
    reference = mre.extract_min_annual(
        base, year_col="year", value_col="value", period_days=30, season="winter"
    )
    obj = base.set_axis(index_factory(base.index))
    got = mre.extract_min_annual(
        obj, year_col="year", value_col="value", period_days=30, season="winter"
    )
    assert sorted(got.index) == sorted(reference.index)
    np.testing.assert_allclose(got.to_numpy(), reference.to_numpy())


def test_period_index_path_is_not_regressed() -> None:
    """PeriodIndex обязан работать и через .month, и через календарную ветку."""
    base = _seasonal_frame()
    period = base.set_axis(pd.PeriodIndex(base.index, freq="D"))
    winter = mre.extract_min_annual(
        period, year_col="year", value_col="value", period_days=30, season="winter"
    )
    summer = mre.extract_min_annual(
        period, year_col="year", value_col="value", period_days=30, season="summer"
    )
    assert float(winter.min()) == pytest.approx(50.0)
    assert float(summer.min()) == pytest.approx(5.0)


def test_string_index_is_still_refused_for_seasonal_months() -> None:
    """Строковый индекс месяца не даёт — парсить его нельзя, guard обязан сработать."""
    frame = _seasonal_frame()
    frame = frame.set_axis(pd.Index([x.strftime("%Y-%m-%d") for x in frame.index]))
    assert mre._calendar_order_key(frame.index) is None
    with pytest.raises(ValueError, match="требует сведений о месяце"):
        mre.extract_min_annual(
            frame, year_col="year", value_col="value", period_days=30, season="winter"
        )


# --------------------------------------------------------------------------
# Сезонный контракт: отсутствие календаря — явная ошибка, а не annual fallback
#
# Найдено read-only аудитом производственного пути:
#   core/services/handlers/__init__.py:286  handle_min_runoff(season="winter")
#   gui/main_window.py:1846-1848            daily_df без month и без даты
# До исправления winter/summer/annual давали ОДИН И ТОТ ЖЕ годовой результат,
# поэтому значение, подписанное «30-суточные зимние минимумы», было посчитано
# по всему году. Наличие случайной колонки month в файле пользователя меняло
# поведение того же кода.
#
# Методологические параметры (winter_months, summer_months, цикл Apr-Mar)
# этим исправлением НЕ затронуты: состав сезонов — отдельное решение.
# --------------------------------------------------------------------------

_NO_CALENDAR_MESSAGE = "требует сведений о месяце"


def _seasonal_frame(first: str = "2001-01-01", last: str = "2005-12-31") -> pd.DataFrame:
    """Ряд с контрастными сезонами и С датой в индексе.

    зима (XI, XII, I, II, III) = 50; летне-осень (VI-X) = 5; прочие = 30.
    Годовой минимум 5,0, зимний 50,0 — расхождение в 10 раз, поэтому
    подмена сезонного результата годовым не может остаться незамеченной.
    """
    dates = pd.date_range(first, last, freq="D")
    values = np.where(
        np.isin(dates.month, (11, 12, 1, 2, 3)), 50.0,
        np.where(np.isin(dates.month, (6, 7, 8, 9, 10)), 5.0, 30.0),
    )
    return pd.DataFrame({"year": dates.year, "value": values}, index=dates)


def _same_values_without_calendar() -> pd.DataFrame:
    """Тот же ряд, но с календарной информацией, удалённой полностью."""
    frame = _seasonal_frame().reset_index(drop=True)
    assert list(frame.columns) == ["year", "value"]
    assert not hasattr(frame.index, "month")
    return frame


def test_winter_without_calendar_raises_value_error() -> None:
    """A. season='winter' с одним лишь year+value → ValueError."""
    df = _same_values_without_calendar()
    with pytest.raises(ValueError) as excinfo:
        mre.extract_min_annual(
            df, year_col="year", value_col="value", period_days=30, season="winter"
        )
    message = str(excinfo.value)
    assert _NO_CALENDAR_MESSAGE in message
    assert "month" in message, "сообщение должно называть допустимый источник month"
    assert "DatetimeIndex" in message, "сообщение должно называть допустимый источник даты"
    assert "annual" in message, "сообщение должно подсказывать выход season='annual'"


def test_summer_without_calendar_raises_value_error() -> None:
    """B. season='summer' с одним лишь year+value → ValueError."""
    df = _same_values_without_calendar()
    with pytest.raises(ValueError, match=_NO_CALENDAR_MESSAGE):
        mre.extract_min_annual(
            df, year_col="year", value_col="value", period_days=30, season="summer"
        )


def test_annual_keeps_working_without_calendar() -> None:
    """C. season='annual' без календаря продолжает работать."""
    df = _same_values_without_calendar()
    got = mre.extract_min_annual(
        df, year_col="year", value_col="value", period_days=30, season="annual"
    )
    assert len(got) == 5, "annual обязан дать значение на каждый календарный год"
    assert sorted(got.index) == [2001, 2002, 2003, 2004, 2005]
    assert float(got.min()) == pytest.approx(5.0)


def test_winter_with_datetime_index_still_seasonal() -> None:
    """D. winter с DatetimeIndex по-прежнему даёт СЕЗОННЫЙ результат."""
    frame = _seasonal_frame()
    got = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="winter"
    )
    assert len(got) > 0
    assert float(got.min()) == pytest.approx(50.0), (
        f"winter должен дать зимний минимум 50,0, получено {got.to_dict()}"
    )


def test_summer_with_datetime_index_still_seasonal() -> None:
    """E. summer с DatetimeIndex по-прежнему даёт СЕЗОННЫЙ результат."""
    frame = _seasonal_frame()
    got = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="summer"
    )
    assert len(got) > 0
    assert float(got.min()) == pytest.approx(5.0)


def test_winter_and_annual_never_silently_agree_on_calendardless_input() -> None:
    """F. production-регрессия: тихое совпадение winter и annual невозможно.

    Тот же ряд без календаря обязан дать явную ошибку вместо равных чисел.
    Контроль: с календарём winter и annual расходятся в 10 раз, то есть
    различие действительно содержательное, а не артефакт теста.
    """
    df = _same_values_without_calendar()

    with pytest.raises(ValueError, match=_NO_CALENDAR_MESSAGE):
        mre.extract_min_annual(
            df, year_col="year", value_col="value", period_days=30, season="winter"
        )

    annual = mre.extract_min_annual(
        df, year_col="year", value_col="value", period_days=30, season="annual"
    )
    frame = _seasonal_frame()
    winter = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="winter"
    )
    assert float(winter.min()) == pytest.approx(50.0)
    assert float(annual.min()) == pytest.approx(5.0)
    assert float(winter.min()) != pytest.approx(float(annual.min()))


def test_month_column_remains_a_valid_calendar_source() -> None:
    """G. Колонка month остаётся допустимым источником календаря."""
    frame = _seasonal_frame().reset_index(drop=True)
    frame["month"] = _seasonal_frame().index.month.to_numpy()
    assert "month" in frame.columns
    assert not hasattr(frame.index, "month"), "индекс без даты — календарь из month"

    winter = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="winter"
    )
    summer = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="summer"
    )
    assert float(winter.min()) == pytest.approx(50.0)
    assert float(summer.min()) == pytest.approx(5.0)
    assert float(winter.min()) != pytest.approx(float(summer.min()))


def test_handler_min_runoff_fails_loudly_without_calendar() -> None:
    """Production-путь: handle_min_runoff не отдаёт молчаливо неверный ряд.

    Регрессия из аудита: обработчик подписывал результат «30-суточные зимние
    минимумы», а считал годовой минимум. Теперь season='winter' без календаря
    обязан поднять ошибку, и сообщение должно называть причину.
    """
    from core.services.calculation_service import CalculationContext
    from core.services.handlers import handle_min_runoff

    dates = pd.date_range("2001-01-01", "2005-12-31", freq="D")
    values = np.where(
        np.isin(dates.month, (11, 12, 1, 2, 3)), 50.0,
        np.where(np.isin(dates.month, (6, 7, 8, 9, 10)), 5.0, 30.0),
    )
    df = pd.DataFrame({"year": dates.year, "value": values})

    context = CalculationContext(
        dataset=None, parameters={"daily_df": df}, methodology=None
    )
    with pytest.raises(ValueError) as excinfo:
        handle_min_runoff(context)
    assert _NO_CALENDAR_MESSAGE in str(excinfo.value)


def test_handler_min_runoff_still_computes_with_calendar() -> None:
    """С календарём production-путь работает и строит кривую обеспеченности."""
    from core.services.calculation_service import CalculationContext
    from core.services.handlers import handle_min_runoff

    frame = _seasonal_frame()
    context = CalculationContext(
        dataset=None, parameters={"daily_df": frame}, methodology=None
    )
    result = handle_min_runoff(context)
    assert result, "обработчик обязан вернуть кривую обеспеченности"
    assert result["columns"] == ["P_%", "Q_min"], (
        f"неожиданная форма кривой: {result.get('columns')}"
    )
    assert result["rows"], "кривая обеспеченности не должна быть пустой"


# --------------------------------------------------------------------------
# Параметризация границ сезонов
#
# Нормативного предписания месяцев XI–III / VI–X не существует. Закреплено
# другое: границы сезонов едины для всех лет и округляются до месяца, а
# состав сезона зависит от типа режима реки (СНиП 2.01.14-83 п. 2.15, 2.16;
# СП 529.1325800.2023 п. 5.2.3). Поэтому XI–III и VI–X — инженерные значения
# по умолчанию, а расчётная методика задаёт границы для конкретной реки.
# ---------------------------------------------------------------------------


def test_default_season_months_are_unchanged() -> None:
    """A. Без параметров поведение прежнее: XI–III и VI–X."""
    frame = _seasonal_frame()
    default_winter = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="winter"
    )
    default_summer = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="summer"
    )
    explicit_winter = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="winter",
        winter_months=[11, 12, 1, 2, 3], summer_months=[6, 7, 8, 9, 10],
    )
    explicit_summer = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="summer",
        winter_months=[11, 12, 1, 2, 3], summer_months=[6, 7, 8, 9, 10],
    )
    assert default_winter.equals(explicit_winter)
    assert default_summer.equals(explicit_summer)
    # прежние значения сезонного отбора сохраняются
    assert float(default_winter.min()) == pytest.approx(50.0)
    assert float(default_summer.min()) == pytest.approx(5.0)


def test_custom_season_months_are_actually_used() -> None:
    """B. winter=[12,1,2,3], summer=[7,8,9,10,11] — расчёт их применяет."""
    # month=11 входит в пользовательский summer, но не в winter
    dates = pd.date_range("2001-01-01", "2005-12-31", freq="D")
    values = np.where(
        np.isin(dates.month, (12, 1, 2, 3)), 40.0,
        np.where(np.isin(dates.month, (11,)), 4.0,
                 np.where(np.isin(dates.month, (7, 8, 9, 10)), 8.0, 90.0)),
    )
    frame = pd.DataFrame({"year": dates.year.to_numpy(), "value": values}, index=dates)

    winter = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="winter",
        winter_months=[12, 1, 2, 3], summer_months=[7, 8, 9, 10, 11],
    )
    summer = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="summer",
        winter_months=[12, 1, 2, 3], summer_months=[7, 8, 9, 10, 11],
    )
    # ноябрь (4.0) не попал в winter, июнь (90.0) не попал в summer
    assert float(winter.min()) == pytest.approx(40.0), f"winter: {winter.to_dict()}"
    assert float(summer.min()) == pytest.approx(4.0), f"summer: {summer.to_dict()}"

    # при стандартных границах тот же ряд даёт другие значения
    std_winter = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="winter"
    )
    assert float(std_winter.min()) == pytest.approx(4.0), (
        "стандартные XI–III обязаны включать ноябрь — иначе default тоже изменился"
    )


def test_another_valid_custom_month_set() -> None:
    """C. winter=[11,12,1,2], summer=[6,7,8,9,10] — тоже допустимо."""
    dates = pd.date_range("2001-01-01", "2005-12-31", freq="D")
    values = np.where(
        np.isin(dates.month, (11, 12, 1, 2)), 40.0,
        np.where(np.isin(dates.month, (6, 7, 8, 9, 10)), 4.0, 90.0),
    )
    frame = pd.DataFrame({"year": dates.year.to_numpy(), "value": values}, index=dates)
    winter = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="winter",
        winter_months=[11, 12, 1, 2], summer_months=[6, 7, 8, 9, 10],
    )
    summer = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="summer",
        winter_months=[11, 12, 1, 2], summer_months=[6, 7, 8, 9, 10],
    )
    assert float(winter.min()) == pytest.approx(40.0)
    assert float(summer.min()) == pytest.approx(4.0)


@pytest.mark.parametrize("months, fragment", [
    ([0, 1, 2], "1..12"),
    ([13, 1, 2], "1..12"),
    ([-1, 1, 2], "1..12"),
    ([], "пустым"),
    ([11, 12, 1, 11], "уникальны"),
    (["XI", "XII"], "целым числом"),
    ("11-3", "строк"),
    ([11.5, 12], "целым числом"),
    ([True, False], "целым числом"),
], ids=["month0", "month13", "month_minus1", "empty", "duplicate",
        "roman_strings", "range_string", "float", "bool"])
def test_invalid_winter_months_are_rejected(months, fragment) -> None:
    """D. Строгая валидация пользовательских месяцев."""
    frame = _seasonal_frame()
    with pytest.raises(ValueError) as excinfo:
        mre.extract_min_annual(
            frame, year_col="year", value_col="value", period_days=30,
            season="winter", winter_months=months,
        )
    assert fragment in str(excinfo.value), f"неожиданное сообщение: {excinfo.value}"


def test_overlapping_seasons_are_rejected() -> None:
    """D. Пересечение winter/summer запрещено: месяц принадлежит одному сезону."""
    frame = _seasonal_frame()
    with pytest.raises(ValueError, match="не должны пересекаться"):
        mre.extract_min_annual(
            frame, year_col="year", value_col="value", period_days=30, season="winter",
            winter_months=[11, 12, 1, 2], summer_months=[6, 7, 8, 9, 10, 11],
        )


def test_custom_seasons_work_without_calendar_guard_being_bypassed() -> None:
    """F. Параметризация не обходит guard «нет календаря»."""
    no_calendar = _seasonal_frame().reset_index(drop=True)
    for season in ("winter", "summer"):
        with pytest.raises(ValueError, match=_NO_CALENDAR_MESSAGE):
            mre.extract_min_annual(
                no_calendar, year_col="year", value_col="value", period_days=30,
                season=season, winter_months=[12, 1, 2, 3], summer_months=[7, 8, 9, 10, 11],
            )


@pytest.mark.parametrize("index_factory", [
    lambda d: pd.DatetimeIndex(d),
    lambda d: pd.PeriodIndex(d, freq="D"),
    lambda d: pd.Index([x.date() for x in d], dtype=object),
    lambda d: pd.Index(list(d), dtype=object),
], ids=["datetime", "period", "object_date", "object_timestamp"])
def test_custom_seasons_on_every_calendar_variant(index_factory) -> None:
    """G. Все поддерживаемые календарные индексы работают с параметрами."""
    frame = _seasonal_frame().set_axis(index_factory(_seasonal_frame().index))
    winter = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="winter",
        winter_months=[12, 1, 2, 3], summer_months=[7, 8, 9, 10, 11],
    )
    assert float(winter.min()) == pytest.approx(50.0)


def test_string_index_still_refused_with_custom_months() -> None:
    """G. Строковый индекс по-прежнему отвергается, месяцы из строк не выдумываются."""
    base = _seasonal_frame()
    frame = base.set_axis(pd.Index([x.strftime("%Y-%m-%d") for x in base.index]))
    with pytest.raises(ValueError, match=_NO_CALENDAR_MESSAGE):
        mre.extract_min_annual(
            frame, year_col="year", value_col="value", period_days=30, season="winter",
            winter_months=[12, 1, 2, 3], summer_months=[7, 8, 9, 10, 11],
        )


def test_annual_is_unaffected_by_season_months() -> None:
    """H. annual не зависит от параметров границ сезонов."""
    frame = _seasonal_frame()
    default = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="annual"
    )
    customised = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="annual",
        winter_months=[12, 1, 2], summer_months=[7, 8, 9],
    )
    assert default.equals(customised)
    assert float(default.min()) == pytest.approx(5.0)


def test_only_one_season_group_may_be_overridden() -> None:
    """Переопределение ОДНОЙ группы не ломает вторую — в обе стороны.

    Регрессия строгого ревью: проверка пересечения выполнялась по фактическим
    спискам, поэтому summer_months=[7..11] отвергался из-за месяца XI,
    пришедшего из значения по умолчанию winter_months. Пользователь XI не
    передавал, а НС = VII–XI — реальный пример из МР ГГИ 2005 (р. Унжа) и
    СП 33-101-2003, Приложение А.
    """
    # ноябрь входит в пользовательский summer, но не в пользовательский winter
    dates = pd.date_range("2001-01-01", "2005-12-31", freq="D")
    values = np.where(
        np.isin(dates.month, (7, 8, 9, 10, 11)), 5.0,
        np.where(dates.month == 6, 1.0,
                 np.where(np.isin(dates.month, (12, 1, 2, 3)), 50.0, 30.0)),
    )
    frame = pd.DataFrame({"year": dates.year.to_numpy(), "value": values},
                         index=dates)

    # A) переопределён только winter -> default summer сохраняется
    a_w = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="winter",
        winter_months=[12, 1, 2, 3],
    )
    a_s = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="summer",
        winter_months=[12, 1, 2, 3],
    )
    assert float(a_w.min()) == pytest.approx(50.0), f"winter: {a_w.to_dict()}"
    assert float(a_s.min()) == pytest.approx(1.0), (
        f"default summer VI–X обязан сохраниться и дать 1,0: {a_s.to_dict()}"
    )

    # B) переопределён только summer -> default winter сохраняется
    b_w = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="winter",
        summer_months=[7, 8, 9, 10, 11],
    )
    b_s = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="summer",
        summer_months=[7, 8, 9, 10, 11],
    )
    # default winter XI–III не изменился: в нём есть ноябрь, а в контрастном
    # ряде XI = 5,0, поэтому min равен 5,0 — ровно как при полном default
    pure_w = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="winter",
    )
    assert b_w.equals(pure_w), (
        f"default winter XI–III обязан сохраниться: {b_w.to_dict()} vs {pure_w.to_dict()}"
    )
    assert float(b_w.min()) == pytest.approx(5.0)
    assert float(b_s.min()) == pytest.approx(5.0), (
        f"custom summer VII–XI обязан дать 5,0: {b_s.to_dict()}"
    )
    # custom summer действительно VII–XI: июнь (1,0) исключён
    assert float(b_s.min()) != pytest.approx(1.0), (
        "параметр summer_months=[7..11] не применился — использован старый VI–X"
    )


def test_summer_only_vii_xi_matches_normative_example() -> None:
    """A (blocking regression). summer_months=[7..11] в одиночку — рабочий сценарий.

    Доказательство не только отсутствия исключения: контрастный ряд даёт
    разные значения для custom VII–XI и для default VI–X, поэтому тест падает,
    если код примет параметр, но продолжит считать по старому default.
    """
    dates = pd.date_range("2001-01-01", "2005-12-31", freq="D")
    values = np.where(
        np.isin(dates.month, (7, 8, 9, 10, 11)), 5.0,
        np.where(dates.month == 6, 1.0,
                 np.where(np.isin(dates.month, (12, 1, 2, 3)), 50.0, 30.0)),
    )
    frame = pd.DataFrame({"year": dates.year.to_numpy(), "value": values},
                         index=dates)

    custom = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="summer",
        summer_months=[7, 8, 9, 10, 11],
    )
    default = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="summer",
    )

    assert float(custom.min()) == pytest.approx(5.0), (
        f"VII–XI должны дать 5,0: {custom.to_dict()}"
    )
    assert float(default.min()) == pytest.approx(1.0), (
        f"default VI–X должен дать 1,0: {default.to_dict()}"
    )
    assert not custom.equals(default), (
        "результат совпал с default — пользовательские месяцы не применены"
    )


def test_explicit_overlap_still_rejected() -> None:
    """D. Оба набора заданы ЯВНО и пересекаются -> ValueError остаётся."""
    frame = _seasonal_frame()
    with pytest.raises(ValueError, match="не должны пересекаться"):
        mre.extract_min_annual(
            frame, year_col="year", value_col="value", period_days=30,
            season="winter",
            winter_months=[11, 12, 1, 2, 3], summer_months=[6, 7, 8, 9, 10, 11],
        )
    # пересечение ровно по одному месяцу тоже запрещено
    with pytest.raises(ValueError, match="не должны пересекаться"):
        mre.extract_min_annual(
            frame, year_col="year", value_col="value", period_days=30,
            season="summer",
            winter_months=[12, 1, 2, 3], summer_months=[3, 7, 8],
        )


def test_tuple_and_range_are_accepted() -> None:
    """Любая последовательность целых допустима, не только list."""
    frame = _seasonal_frame()
    base = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="winter"
    )
    as_tuple = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="winter",
        winter_months=(11, 12, 1, 2, 3),
    )
    as_range = mre.extract_min_annual(
        frame, year_col="year", value_col="value", period_days=30, season="winter",
        winter_months=range(6, 11), summer_months=range(11, 13),
    )
    assert base.equals(as_tuple)
    assert float(as_range.min()) == pytest.approx(5.0), (
        "range(6, 11) = VI–X обязан дать тот же летне-осенний минимум"
    )
