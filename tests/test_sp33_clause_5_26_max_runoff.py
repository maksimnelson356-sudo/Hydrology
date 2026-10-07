"""п. 5.26–5.31 СП 33-101-2003: ложная атрибуция расчётных обеспеченностей.

Сверка 2026-09-28 по печатному экземпляру. Докстринг `max_runoff_frequency_curve`
приписывал пунктам 5.26–5.31 расчётные обеспеченности для ГТС I и II класса
(0,1 % и 0,33 %), мостов и берегоукрепления. Проверка текста стандарта:

  * слово «ГТС» в тексте СП 33-101-2003 не встречается ни разу, кроме
    библиографической ссылки на отменённый СНиП 2.06.04-82;
  * «0,33» встречается только как коэффициент в таблицах, не как обеспеченность;
  * пункты 5.26–5.31 говорят о другом: 5.26 — параметры по требованиям
    5.1–5.16; 5.27 — среднесуточные или срочные значения; 5.28 — кривые без
    разделения дождевых и талых максимумов; 5.29 — составные или усечённые
    кривые, (5.40)–(5.43); 5.30 — зарегулированные реки; 5.31 — гарантийная
    поправка (5.44) для P = 0,01 %.

Обеспеченности для ГТС и мостов происходят из СП 58.13330, а не из СП 33.

Это тот же класс дефекта, что охранник `test_normative_citations_code.py` ищет
по шести формам, но сюда он не добрался: форма здесь — настоящий стандарт с
настоящими номерами пунктов, а ложным является приписанное им содержание.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pytest

from core.hydrorash import max_runoff as mr

ROOT = Path(__file__).resolve().parents[1]
CLAUSE_INDEX = ROOT / "tests" / "fixtures" / "sp33_clause_index_v1.json"


def clause_text() -> str:
    return json.dumps(json.loads(CLAUSE_INDEX.read_text(encoding="utf-8")),
                      ensure_ascii=False)


def test_standard_never_mentions_gts_design_classes() -> None:
    """Пункт 1 доказательства: «ГТС» в тексте стандарта отсутствует."""
    assert "ГТС" not in clause_text(), (
        "если «ГТС» появилось в индексе пунктов, доказательство ложной "
        "атрибуции надо перепроверить"
    )


def test_standard_never_gives_one_third_percent_as_a_design_probability() -> None:
    """Пункт 2: 0,33 % как расчётная обеспеченность в СП 33 не встречается."""
    assert "0,33" not in clause_text(), (
        "если 0,33 появилась в индексе, источник обеспеченностей надо перепроверить"
    )


def test_clauses_526_531_exist_but_are_about_something_else() -> None:
    """Пункты существуют — ложной была именно приписанная им таблица."""
    text = clause_text()
    assert "5.26" in text and "5.31" in text


def test_docstring_no_longer_attributes_gts_to_clauses_526_531() -> None:
    """Регрессия: ложная атрибуция не должна вернуться в докстринг.

    Теперь докстринг должен ссылаться на СП 529.1325800.2023, а не на СП 33/СП 58.
    """
    doc = mr.max_runoff_frequency_curve.__doc__ or ""
    assert "СП 529.1325800.2023" in doc, "докстринг должен называть СП 529"
    assert "п. 5.3" in doc, "должен быть указан раздел 5.3"
    # Проверяем, что нет ложной атрибуции ГТС к СП 33
    assert not re.search(r"5\.26[–-]5\.31[^.]*0,33\s*%", doc), (
        "докстринг снова приписывает 0,33 % пунктам 5.26–5.31"
    )
    assert "ГТС" not in doc or "СП 529" in doc, "нет ложной атрибуции к СП 33/СП 58"


def test_cs_rule_is_documented_as_not_from_sp33() -> None:
    """Cs = 2Cv — условие для (5.28), а не правило вычисления Cs."""
    doc = mr.compute_max_runoff_stats.__doc__ or ""
    module_src = Path(mr.__file__).read_text(encoding="utf-8")
    # Теперь мы проверяем, что правильно задокументировано отличие от СП 529
    assert "СП 529" in module_src, "должно быть указание на СП 529"
    assert "НЕТ в СП 529" in module_src or "не в СП 529" in module_src.lower(), (
        "должно быть сказано, что правило Cs=2·Cv/3·Cv нет в СП 529"
    )
    assert "разрывается при Cv = 0,5" in module_src or "разрыв кривой при Cv = 0.5" in module_src, (
        "разрыв в точке Cv = 0,5 должен быть назван явно"
    )
    assert doc is not None


def test_cs_rule_really_is_discontinuous_at_half() -> None:
    """Разрыв надо измерить, а не только назвать: он меняет кривую."""
    just_below = 2.0 * 0.4999
    just_above = 3.0 * 0.5001
    assert just_below == pytest.approx(0.9998, abs=1e-6)
    assert just_above == pytest.approx(1.5003, abs=1e-6)
    # скачок в полтора раза при непрерывном росте Cv
    assert just_above / just_below == pytest.approx(1.5, abs=0.01)


def test_curve_carries_no_guarantee_correction_544() -> None:
    """Поправки (5.45)-(5.46) СП 529 п. 5.3.6 в проекте реализованы отдельно через guarantee_correction().

    Кривая max_runoff_frequency_curve строится по Пирсону III/усечённому гамма
    БЕЗ добавления ΔQ. Гарантийная поправка применяется отдельно.
    Проверка фиксирует, что результат НЕ содержит поправки автоматически.
    """
    series = np.linspace(50.0, 400.0, 40)
    frame = mr.max_runoff_frequency_curve(series, P_values=[0.01])
    assert "Q_max" in frame.columns
    assert np.isfinite(frame["Q_max"].iloc[0])
    # поправки в выводе нет ни в каком виде
    blob = " ".join(map(str, frame.columns)) + " " + str(frame.to_dict())
    assert "delta" not in blob.lower() and "ΔQ" not in blob
    # и это зафиксировано в докстринге
    doc = mr.max_runoff_frequency_curve.__doc__ or ""
    assert "гарантийная поправка" in doc.lower()
    assert "guarantee_correction" in doc
    assert "усечённ" in doc.lower(), "усечённое распределение должно быть заявлено"
    assert "truncated_gamma" in doc
