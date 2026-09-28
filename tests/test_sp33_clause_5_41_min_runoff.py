"""п. 5.41–5.43 СП 33-101-2003: ссылка верна, требования выполнены не все.

Сверка 2026-09-28 по печатному экземпляру. В отличие от `max_runoff`, где
атрибуция оказалась ложной, здесь модуль `min_runoff_extended.py` ссылается на
пункты 5.41–5.43 верно: они действительно посвящены минимальному стоку.

Но предписанного этими пунктами в проекте нет:

  п. 5.41 — неоднородность ряда: усечённые (5.29) или составные (5.12) кривые;
  п. 5.41 — нулевые расходы: расчёты по 5.12;
  п. 5.41 — резкое отклонение нижних точек: эмпирические кривые (изгиб 90–97 %);
  п. 5.42 — среднемесячный минимум берётся, только если не превышает
           30-суточный более чем на 10 %; иначе — среднее за 30 непрерывных
           суток с наименьшим стоком;
  п. 5.42 — при частых паводках период сокращается до 24 сут;
  п. 5.43 — календарный среднемесячный минимум разрешён только для рек
           восточнее/южнее названных границ, без рек Северного Кавказа.

Проверки «пробела нет» выполняются по КОДУ, а не по исходнику целиком: модуль
документирует эти пробелы в докстринге, и поиск по всему файлу давал бы
ложное срабатывание — документирование отсутствия выглядело бы как его
наличие. Комментарии и строковые литералы отбрасываются токенизатором.

Отдельно зафиксирована ловушка чтения: в модуле есть четыре вхождения «10 %»
и «0,1», но все они относятся к экологическому нормативу 0,1·Qср, а не к
правилу 10 % из п. 5.42. Поиск по строке «10 %» даёт ложное подтверждение.
"""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

import numpy as np
import pandas as pd

from core.hydrorash import min_runoff_extended as mre

SOURCE = Path(mre.__file__).read_text(encoding="utf-8")


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


def test_citation_to_541_543_is_correct() -> None:
    """Ссылка верна — это фиксируется, чтобы её не «починили» в другую."""
    assert "5.41-5.43" in SOURCE
    assert SOURCE.count("5.41") >= 1


def test_clause_542_ten_percent_rule_is_absent() -> None:
    """П. 5.42 в коде не встречается: правила выбора типа минимума нет."""
    assert "5.42" not in CODE, (
        "в коде появилась ссылка на 5.42 — если правило 10 % реализовано, "
        "это нужно перепроверить и обновить тест"
    )


def test_every_ten_percent_mention_is_about_the_ecological_norm() -> None:
    """Все «10 %» в коде — экологический норматив, а не п. 5.42.

    Строки, где «10 %» встречается как раз В ДОКУМЕНТАЦИИ отсутствия
    правила п. 5.42, исключаются: иначе проверка ловила бы собственное
    описание пробела.
    """
    prose_markers = ("п. 5.42", "НЕ РЕАЛИЗОВАНО", "правило 10 %")
    lines = [
        ln.strip()
        for ln in SOURCE.splitlines()
        # «10%» в коде и «10 %» в прозе — одно и то же число
        if re.search(r"10\s*%", ln) and not any(m in ln for m in prose_markers)
    ]
    assert lines, "ожидались вхождения «10%» в модуле"
    for ln in lines:
        assert (
            "Qср" in ln
            or "среднегодов" in ln
            or "q_ecos" in ln
            or "tenpct" in ln
            or "Экосистемн" in ln
        ), f"обнаружено «10 %» вне экологического норматива: {ln}"


def test_24_day_reduction_is_absent() -> None:
    """П. 5.42 разрешает сокращение периода до 24 сут — этого нет в коде."""
    assert not re.search(r"\b24\b", CODE), "сокращение до 24 сут появилось в коде"


def test_empirical_curves_for_lower_deviation_are_absent() -> None:
    """П. 5.41 требует эмпирические кривые при отклонении нижних точек."""
    assert "эмпирич" not in CODE.lower(), "эмпирические кривые появились в коде"


def test_zero_flow_handling_is_absent() -> None:
    """П. 5.41: при нулевых расходах расчёты по 5.12 — в коде нет."""
    assert "5.12" not in CODE, "появилась обработка по 5.12 — проверить нули"


def test_nonhomogeneous_curves_are_absent() -> None:
    """П. 5.41 отсылает к 5.29 и 5.12 — этих ссылок в коде нет."""
    assert "5.29" not in CODE


def test_calendar_monthly_regional_restriction_is_absent() -> None:
    """П. 5.43 задаёт региональные границы — в коде их нет."""
    assert "календарн" not in CODE.lower()


def test_code_only_actually_strips_prose() -> None:
    """Сам фильтр проверяется: иначе проверки выше могли бы молча
    превратиться в проверки полного исходника."""
    assert "НЕ РЕАЛИЗОВАНО" in SOURCE, "ожидалась проза в докстринге модуля"
    assert "НЕ РЕАЛИЗОВАНО" not in CODE, "фильтр не отбросил докстринг"
    assert "5.42" in SOURCE, "ожидалось упоминание 5.42 в прозе"
    assert "5.42" not in CODE, "фильтр не отбросил упоминание из докстринга"


def test_docstring_keeps_declaring_the_gaps() -> None:
    """Пробелы должны остаться видимыми: их удаление снова сделало бы
    документацию ложью — ровно тот дефект, который находили уже дважды."""
    doc = mre.__doc__ or ""
    assert "НЕ РЕАЛИЗОВАНО" in doc
    for clause in ("5.41", "5.42", "5.43"):
        assert clause in doc, f"докстринг перестал упоминать {clause}"
    assert "5.29" in doc and "5.12" in doc, "перестали упоминаться 5.29 и 5.12"
    assert "24" in doc, "перестало упоминаться сокращение до 24 сут"
    assert "0,1·Qср" in doc, "перестала упоминаться ловушка с 10 %"


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
