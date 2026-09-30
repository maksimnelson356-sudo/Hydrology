"""Тесты нормативного минимума совместных лет в multi_analog_extension.

Основание: СП 529.1325800.2023, п. 6.1.6, формула (6.1) — n ≥ 6 при одном
аналоге и n ≥ 10 при двух и более.

Ключевая особенность тестов: проверяется ИМЕННО ранний minimum-years gate.
Он срабатывает первым, до регрессии и до остальных критериев (R, R/σR, k/σk,
S, Y/σY), поэтому для случаев «ниже порога» результат однозначен:
success = False. Для случаев «на пороге» проверяется лишь факт прохождения
gate (success = True), а не all_criteria_ok: остальные критерии могут
остаться невыполненными по причинам, не относящимся к проверяемому правилу,
и ослаблять их ради успеха теста нельзя.
"""

from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest

from core.stats.series_extension import (
    MIN_COMMON_YEARS,
    MIN_COMMON_YEARS_MULTI_ANALOG,
    full_extension_workflow,
    multi_analog_extension,
    regression_extension,
)


def _case(n_common: int, n_analogs: int, seed: int = 20260930):
    """Синтетические ряды с РОВНО n_common совместных лет.

    Q_calc определён на n_common годах и NaN на остальных; каждый аналог покрывает
    весь период. Совместный индекс следовательно равен ровно n_common годам.
    Ряды построены так, чтобы регрессия имела высокое R и малые остатки, —
    насколько это возможно без ослабления проверяемых критериев.
    """
    rng = np.random.default_rng(seed)
    total = n_common + 4
    years = pd.Index(range(2000, 2000 + total), name="year")

    drivers = [rng.uniform(5.0, 50.0, total) for _ in range(max(n_analogs, 1))]
    target = 20.0 + 1.5 * drivers[0]
    for k, d in enumerate(drivers[1:], start=2):
        target = target + (0.5 + 0.1 * k) * d
    target = target + rng.normal(0.0, 0.05, total)

    analogs = {
        f"analog-{i + 1}": pd.Series(d, index=years)
        for i, d in enumerate(drivers)
    }

    observed = pd.Series(target, index=years, dtype=float)
    observed.iloc[n_common:] = np.nan
    return observed, analogs


def _rejected_by_gate(result: dict) -> bool:
    """Отказ именно по минимуму лет, а не по иной причине."""
    return result["success"] is False and "Мало общих лет" in result["reason"]


def _single_analog_case(n_common: int, seed: int = 4242):
    """Пара без NaN — для regression_extension и full_extension_workflow.

    Эти функции не отбрасывают пропуски (отдельный методологический долг,
    здесь не затрагивается), поэтому Q_calc задаётся ТОЛЬКО на совместных
    годах, без хвоста из NaN. Аналог длиннее.
    """
    rng = np.random.default_rng(seed)
    total = n_common + 4
    years = pd.Index(range(2000, 2000 + total), name="year")
    x = rng.uniform(5.0, 50.0, total)
    analog = pd.Series(x, index=years)
    full = 20.0 + 1.5 * x + rng.normal(0.0, 0.05, total)
    observed = pd.Series(full[:n_common], index=years[:n_common])
    return observed, analog


# --------------------------------------------------------------------------
# Константы
# --------------------------------------------------------------------------


def test_constants_match_sp529_clause_6_1_6() -> None:
    assert MIN_COMMON_YEARS == 6
    assert MIN_COMMON_YEARS_MULTI_ANALOG == 10


# --------------------------------------------------------------------------
# 1. Один аналог
# --------------------------------------------------------------------------


def test_one_analog_n5_rejected() -> None:
    observed, analogs = _case(n_common=5, n_analogs=1)
    result = multi_analog_extension(observed, analogs)
    assert result["n_common"] == 5
    assert _rejected_by_gate(result)
    assert result["n_min"] == MIN_COMMON_YEARS == 6


def test_one_analog_n6_passes_minimum_years_gate() -> None:
    observed, analogs = _case(n_common=6, n_analogs=1)
    result = multi_analog_extension(observed, analogs)
    # gate пройден: success True, отказа по минимуму лет нет
    assert result["n_common"] == 6
    assert result["success"] is True
    assert "reason" not in result
    assert result["criteria"]["n_common_ok"] is True
    # all_criteria_ok здесь не проверяется осознанно: см. docstring модуля


# --------------------------------------------------------------------------
# 2. Два аналога
# --------------------------------------------------------------------------


def test_two_analogs_n9_rejected() -> None:
    observed, analogs = _case(n_common=9, n_analogs=2)
    result = multi_analog_extension(observed, analogs)
    assert len(analogs) == 2
    assert result["n_common"] == 9
    assert _rejected_by_gate(result)
    assert result["n_min"] == MIN_COMMON_YEARS_MULTI_ANALOG == 10


def test_two_analogs_n10_passes_minimum_years_gate() -> None:
    observed, analogs = _case(n_common=10, n_analogs=2)
    result = multi_analog_extension(observed, analogs)
    assert result["n_common"] == 10
    assert result["success"] is True
    assert "reason" not in result
    assert result["criteria"]["n_common_ok"] is True


# --------------------------------------------------------------------------
# 3. Три аналога
# --------------------------------------------------------------------------


def test_three_analogs_n9_rejected() -> None:
    observed, analogs = _case(n_common=9, n_analogs=3)
    result = multi_analog_extension(observed, analogs)
    assert len(analogs) == 3
    assert result["n_common"] == 9
    assert _rejected_by_gate(result)
    assert result["n_min"] == 10


def test_three_analogs_n10_passes_minimum_years_gate() -> None:
    observed, analogs = _case(n_common=10, n_analogs=3)
    result = multi_analog_extension(observed, analogs)
    assert result["n_common"] == 10
    assert result["success"] is True
    assert "reason" not in result
    assert result["criteria"]["n_common_ok"] is True


# --------------------------------------------------------------------------
# Норма — пол
# --------------------------------------------------------------------------


def test_rejection_message_states_the_actual_rule() -> None:
    """Сообщение должно объяснять обе границы, а не только «6 достаточно»."""
    observed, analogs = _case(n_common=9, n_analogs=2)
    result = multi_analog_extension(observed, analogs)
    message = result["reason"]
    assert "6" in message
    assert "10" in message
    assert "6.1.6" in message


def test_n_min_cannot_lower_the_normative_floor() -> None:
    """Явный n_min ужесточает требование, но не опускает его ниже нормы."""
    observed, analogs = _case(n_common=9, n_analogs=2)
    result = multi_analog_extension(observed, analogs, n_min=3)
    assert _rejected_by_gate(result)
    assert result["n_min"] == 10


def test_n_min_can_raise_the_requirement() -> None:
    """Явный n_min выше нормы сохраняется."""
    observed, analogs = _case(n_common=12, n_analogs=1)
    result = multi_analog_extension(observed, analogs, n_min=15)
    assert _rejected_by_gate(result)
    assert result["n_min"] == 15


def test_max_analogs_reduction_lowers_requirement_to_single_analog() -> None:
    """Если max_analogs = 1, фактически используется один аналог → требуется 6."""
    observed, analogs = _case(n_common=6, n_analogs=2)
    result = multi_analog_extension(observed, analogs, max_analogs=1)
    assert result["analogs"] == ["analog-1"]
    assert result["success"] is True


# --------------------------------------------------------------------------
# Побочные эффекты не должны быть
# --------------------------------------------------------------------------


def test_single_analog_regression_extension_unaffected() -> None:
    """regression_extension с одним аналогом не изменился: порог остался 6."""
    observed, analog = _single_analog_case(6)
    result = regression_extension(observed, analog)
    assert result["n_common"] == 6
    assert result["extended_series"] is not None


def test_single_analog_regression_extension_still_rejects_five() -> None:
    observed, analog = _single_analog_case(5)
    with pytest.raises(ValueError, match="совместных лет"):
        regression_extension(observed, analog)


def test_full_extension_workflow_single_analog_warning_matches_clause_6_1_6() -> None:
    """Путь с одним аналогом: норма требует 6, а не 10.

    Предупреждение не превращено в ошибку и не утверждает, что 10 — требование.
    """
    observed, analog = _single_analog_case(7)
    result = full_extension_workflow(observed, analog)
    joined = " ".join(result["warnings"])
    assert "6.1.6" in joined
    assert f"не менее {MIN_COMMON_YEARS}" in joined
    assert "Рекомендуется ≥ 10" not in joined
    # n = 7 < 10, поэтому рекомендательное предупреждение присутствует
    assert any("Мало общих лет" in w for w in result["warnings"])


def test_full_extension_workflow_single_analog_at_ten_has_no_years_warning() -> None:
    observed, analog = _single_analog_case(10)
    result = full_extension_workflow(observed, analog)
    assert not any("Мало общих лет" in w for w in result["warnings"])


def test_full_extension_workflow_takes_single_analog_only() -> None:
    """API workflow принимает ровно один ряд-аналог.

    Случай 2+ аналогов через этот путь недостижим, поэтому норма п. 6.1.6
    для него применяется только в multi_analog_extension. Проверяем по
    сигнатуре, а не некорректным вызовом.
    """
    params = list(inspect.signature(full_extension_workflow).parameters)
    assert params == ["Q_calc", "Q_analog", "method"]
    assert not any("analogs" in p for p in params)
