"""Independent benchmark checks for normative statistical calculations."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from core.stats.parameters import calculate_statistical_parameters

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE_PATH = FIXTURE_DIR / "sp33_stats_parameters_hand_calc_v2.json"


def test_stats_parameters_matches_independent_sp33_hand_calculation() -> None:
    """Сверка с независимым ручным расчётом по (Б.1)-(Б.3), (5.6)-(5.7), (5.26).

    Эталон v2, а не v1. Причина замены зафиксирована в самом фикстуре: в v1 вход
    для (5.26)/(5.27) был взят как корреляция Пирсона, тогда как стандарт требует
    для этих формул r(1) по (Б.1)-(Б.3). Это разные величины, и на ряде v1
    нормативное r(1) вообще выходит за единицу.
    """
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    result = calculate_statistical_parameters(fixture["input"]["values"])
    expected = fixture["expected"]

    for key in (
        "n",
        "mean",
        "std",
        "cv",
        "cs",
        "cs_cv",
        "corrected_cv",
        "corrected_cs",
        "r1",
        "r1_tilde",
        "lambda2",
        "lambda3",
    ):
        assert result[key] == pytest.approx(expected[key], abs=5e-4), key

    assert result["length_warnings"] == expected["length_warnings"] == []
    assert result["bias_corrections_applied"] is True
    assert result["table_r1_node"] == fixture["calculation"]["table_b1_r1_node"]
    assert result["table_ratio_node"] == fixture["calculation"]["table_b1_ratio_node"]


def test_benchmark_r1_is_normative_not_pearson() -> None:
    """r(1) в эталоне — из (Б.1), а не переименованная корреляция Пирсона.

    Это отдельная проверка, потому что подмена Пирсона под именем нормативного
    r(1) повторяла бы ровно тот дефект, который закрыли в (Б.1) и (7.51).
    """
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    values = np.asarray(fixture["input"]["values"], dtype=float)
    result = calculate_statistical_parameters(values)

    pearson = float(np.corrcoef(values[:-1], values[1:])[0, 1])
    assert result["r1"] == pytest.approx(fixture["expected"]["r1"], abs=5e-4)
    assert result["r1_pearson"] == pytest.approx(pearson, abs=5e-4)
    assert result["r1"] != pytest.approx(pearson, abs=1e-3), (
        "r(1) по (Б.1) обязан отличаться от корреляции Пирсона"
    )
    assert "Б.1" in result["r1_source"]


def test_short_series_normative_r1_can_exceed_one() -> None:
    """Честная граница стандарта: (Б.1) даёт r(1) > 1 на коротком ряду.

    На восьми значениях из v1 нормативное r(1) = 1,418. Тогда множитель
    sqrt((1+r)/(1-r)) в (5.26)/(5.27) не определён, и погрешность среднего не
    вычисляется. Это свойство формулы, а не дефект реализации, поэтому оно
    проверяется явно, а не замалчивается.
    """
    values = [10.0, 11.0, 13.0, 12.0, 15.0, 14.0, 17.0, 16.0]
    result = calculate_statistical_parameters(values)

    assert result["r1"] > 1.0, "ожидалось r(1) > 1 при n = 8 по (Б.1)"
    assert result["r1_pearson"] < 1.0
    assert result["r1_tilde"] == pytest.approx(0.566122, abs=1e-4)


def test_degenerate_series_falls_back_to_pearson_with_reason() -> None:
    """На ряду без изменений (Б.1)-(Б.3) неприменимы, и причина названа прямо."""
    result = calculate_statistical_parameters(np.full(10, 5.0), show_warnings=False)
    assert result["r1_tilde"] is None
    assert "Пирсон" in result["r1_source"]
    assert "Б.1" in result["r1_source"]
