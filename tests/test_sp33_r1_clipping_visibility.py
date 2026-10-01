"""Подмена r(1) при выборе узла таблицы Б.1 должна быть видна, а не молчалива.

Дефект найден ревью 2026-09-29. Таблица Б.1 определена для r(1) в узлах
{0; 0,3; 0,5}, поэтому значение вне диапазона приходится чем-то ограничивать, иначе
выбора узла не будет. Но ограничение — это ПОДМЕНА нормативной величины.

На коротких рядах это не крайний случай, а обычный: нормативное r(1) по (Б.1)
достигает 2,18 при n = 5 и 5,50 при n = 3. Раньше в результате печатался только
узел «r(1)=0,5», и читатель заключал, что r(1) было 0,5. Это тот же класс дефекта,
что был с (7.51) и (Б.1): значение подменено, и подмена не видна.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.stats.parameters import (
    calculate_statistical_parameters,
    sp33_bias_correction_56_57,
    sp33_lag1_autocorrelation,
)


def _series_with_out_of_range_r1() -> tuple[np.ndarray, float]:
    """Ряд с нормативным r(1) > 1 и с применяемыми поправками (5.6)/(5.7).

    Подбирается перебором, а не задаётся вручную: нужно одновременно r(1) > 1
    и НЕ (Cv < 0,6 и Cs < 1,0), иначе поправки не применяются и отсечение не
    сработает.
    """
    rng = np.random.default_rng(4242)
    for _ in range(20000):
        n = int(rng.integers(3, 26))
        series = rng.lognormal(0.0, 0.8, n)
        r1 = sp33_lag1_autocorrelation(series)["r1"]
        if not (np.isfinite(r1) and r1 > 1.0):
            continue
        result = calculate_statistical_parameters(series, show_warnings=False)
        if result["bias_corrections_applied"]:
            return series, r1
    raise AssertionError("не найден ряд с r(1) > 1 при применяемых поправках")


def test_out_of_range_r1_is_reported_not_silently_clipped() -> None:
    """Нормативное r(1) = 5,5 обязано быть видно в результате."""
    series, r1 = _series_with_out_of_range_r1()
    result = calculate_statistical_parameters(series, show_warnings=False)

    assert result["r1"] > 1.0, "исходное значение должно оставаться в результате"
    assert result["r1_clipped_for_table"] is True
    assert result["table_r1_node"] == 0.5, "отсечённое значение даёт верхний узел"
    assert "ВНИМАНИЕ" in result["correction_note"]
    assert "ЗАМЕНИТЕЛЬНА" in result["correction_note"]
    assert f"{result['r1']:.4f}" in result["correction_note"], (
        "в тексте поправки должно стоять фактическое r(1), а не узел"
    )
    assert r1 == pytest.approx(result["r1"], abs=1e-4)


def test_correction_helper_returns_raw_and_clipped_separately() -> None:
    """Помощник отдаёт и исходное, и отсечённое значение."""
    out = sp33_bias_correction_56_57(0.8, 1.5, 20, 3.7)
    assert out["r1_raw"] == pytest.approx(3.7)
    assert out["r1_clipped"] is True
    assert out["r1_clipped_to"] == pytest.approx(0.99)
    assert out["table_r1_node"] == 0.5


def test_legacy_keys_still_present() -> None:
    """Прежние ключи не убраны: ими пользуются существующие потребители."""
    out = sp33_bias_correction_56_57(0.8, 1.5, 20, 0.45)
    for key in ("cv", "cs", "table_ratio_node", "table_r1_node", "cs_cv"):
        assert key in out, key
    assert out["r1_clipped"] is False
    assert out["r1_clipped_to"] == pytest.approx(0.45)


def test_no_false_alarm_for_ordinary_r1() -> None:
    """На нормальном r(1) признака подмены быть не должно."""
    series = np.array([
        0.9659, 1.1075, 0.8959, 0.4848, 0.9404, 0.9363, 0.865, 0.8405,
        1.5414, 1.8147, 1.843, 2.1398, 0.9709, 1.0162, 1.0917, 1.1957,
        1.1778, 1.5432, 0.7142, 1.2368, 0.785, 0.9764, 1.3224, 1.0251,
        0.9722, 0.8901,
    ])
    result = calculate_statistical_parameters(series, show_warnings=False)
    assert result["r1_clipped_for_table"] is False
    assert "ВНИМАНИЕ" not in result["correction_note"]


def test_exempt_case_has_no_clipping_flag() -> None:
    """При отказе от поправок по п. 5.6 признака подмены нет вовсе."""
    series = np.array([10.0, 11.0, 13.0, 12.0, 15.0, 14.0, 17.0, 16.0])
    result = calculate_statistical_parameters(series, show_warnings=False)
    assert result["bias_corrections_applied"] is False
    assert result["r1_clipped_for_table"] is False
