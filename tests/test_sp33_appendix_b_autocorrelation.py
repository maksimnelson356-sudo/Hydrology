"""Формулы (Б.1)-(Б.3) СП 33-101-2003: транскрипция реализована, но НЕ подключена.

Транскрипция от 2026-09-28 (печатный экземпляр, стр. 74, приложение Б):

    (Б.3)  Q̄₁ = Σ(i=2..n) Qᵢ / (n-1)
           Q̄₂ = Σ(i=2..n-1) Qᵢ / (n-1)
    (Б.2)  r̃(1) = Σ(Qᵢ - Q̄₁)(Qᵢ₋₁ - Q̄₂) / √[Σ(Qᵢ - Q̄₁)² · Σ(Qᵢ₋₁ - Q̄₂)²]
    (Б.1)  r(1) = -0,01 + 0,98·r̃ - 0,06·r̃² + (1,66 + 6,46·r̃ + 5,69·r̃²)·n^(-1/2)

ПОЧЕМУ ФУНКЦИЯ НЕ ПОДКЛЮЧЕНА К РАСЧЁТУ. Показатель степени записан в
транскрипции как n^(-1/2), и при нём r(1) выходит за единицу почти при любом
реальном n: при r̃ = 0,35 допустимое значение достигается лишь с n = 47, при
r̃ = 0,50 — с n = 140, при r̃ = 0,70 — с n = 645. Ряды речного стока — это
30-60 лет, то есть такое чтение делает формулу непригодной. Чтение с 1/n вместо
n^(-1/2) даёт r(1) ≤ 1 начиная с n = 4-26 и физически осмысленно.

Пока показатель не подтверждён по печати, выбор между чтениями не делается:
это ровно та подстановка догадки в нормативную величину, из-за которой формула
(7.51) в своё время оказалась неверной. Функция реализована как есть, тестируется
и ждёт подтверждения.

ОСОБЕННОСТЬ ОРИГИНАЛА. В (Б.3) знаменатель у Q̄₁ и Q̄₂ один — (n-1), хотя
сумма при Q̄₂ берётся по n-2 членам. Воспроизведено буквально; расхождение
зафиксировано тестом, а не «исправлено».
"""

from __future__ import annotations

import numpy as np
import pytest

from core.stats.parameters import sp33_autocorrelation_b1_b2_b3


def reference(series: np.ndarray) -> dict:
    """Независимая реализация (Б.1)-(Б.3) для сверки."""
    x = np.asarray(series, dtype=float)
    n = x.size
    q1 = np.sum(x[1:]) / (n - 1)
    q2 = np.sum(x[1:n - 1]) / (n - 1)
    a = x[1:] - q1
    b = x[:-1] - q2
    r_tilde = np.sum(a * b) / np.sqrt(np.sum(a**2) * np.sum(b**2))
    r1 = (
        -0.01
        + 0.98 * r_tilde
        - 0.06 * r_tilde**2
        + (1.66 + 6.46 * r_tilde + 5.69 * r_tilde**2) / n**0.5
    )
    return {"r1": float(r1), "r_tilde": float(r_tilde),
            "q_bar_1": float(q1), "q_bar_2": float(q2)}


@pytest.mark.parametrize("n", [10, 30, 60, 120])
def test_matches_independent_implementation(n: int) -> None:
    rng = np.random.default_rng(20260928)
    series = np.cumsum(rng.normal(0.0, 1.0, n)) + 50.0
    got = sp33_autocorrelation_b1_b2_b3(series)
    ref = reference(series)
    assert got["r_tilde"] == pytest.approx(ref["r_tilde"], rel=1e-12)
    assert got["r1"] == pytest.approx(ref["r1"], rel=1e-12)
    assert got["q_bar_1"] == pytest.approx(ref["q_bar_1"], rel=1e-12)
    assert got["q_bar_2"] == pytest.approx(ref["q_bar_2"], rel=1e-12)


def test_b3_uses_n_minus_one_for_both_means_despite_asymmetric_sums() -> None:
    """Знаменатель (n-1) у обеих средних — как напечатано, даже при разном числе слагаемых."""
    series = np.arange(1.0, 11.0)  # n = 10
    out = sp33_autocorrelation_b1_b2_b3(series)
    n = 10
    assert out["q_bar_1"] == pytest.approx(np.sum(series[1:]) / (n - 1))      # 9 слагаемых
    assert out["q_bar_2"] == pytest.approx(np.sum(series[1:n - 1]) / (n - 1))  # 8 слагаемых
    # сумма при Q̄₂ короче, а знаменатель тот же — расхождение зафиксировано
    assert out["q_bar_2"] != pytest.approx(np.sum(series[1:n - 1]) / (n - 2))


def test_r1_exceeds_one_for_short_series_with_sqrt_exponent() -> None:
    """Зафиксированный факт: при n^(-1/2) результат не является корреляцией.

    Это и есть причина не подключать функцию. Проверка существует, чтобы вопрос
    не потерялся и чтобы при подтверждении печати тест показал, что чтение
    изменилось.
    """
    rng = np.random.default_rng(20260928)
    for n in (20, 40, 60):
        series = np.cumsum(rng.normal(0.0, 1.0, n)) + 50.0
        out = sp33_autocorrelation_b1_b2_b3(series)
        assert out["r1"] > 1.0, (
            f"при n={n} ожидалось r(1) > 1 для чтения n^(-1/2), получено {out['r1']}"
        )


def test_one_over_n_reading_needs_far_shorter_series() -> None:
    """Сравнение двух чтений, а не утверждение, что одно из них всегда верно.

    Чтение 1/n тоже может выйти за единицу при очень сильной корреляции на
    коротком ряду — и это честно. Проверяется сравнительный факт: порог
    допустимости у 1/n в разы ниже, чем у n^(-1/2), то есть именно поэтому оно
    пригодно для реальных рядов длиной 30-60 лет.
    """
    def threshold(power: str, r_tilde: float, n_max: int = 5000) -> int:
        for n in range(4, n_max):
            core = 1.66 + 6.46 * r_tilde + 5.69 * r_tilde**2
            tail = core / (n**0.5) if power == "sqrt" else core / n
            value = -0.01 + 0.98 * r_tilde - 0.06 * r_tilde**2 + tail
            if value <= 1.0:
                return n
        return n_max

    for r_tilde in (0.35, 0.5, 0.7):
        need_sqrt = threshold("sqrt", r_tilde)
        need_plain = threshold("plain", r_tilde)
        assert need_plain < need_sqrt, (
            f"при r̃={r_tilde} порог для 1/n ({need_plain}) должен быть ниже, "
            f"чем для n^(-1/2) ({need_sqrt})"
        )
        assert need_plain <= 30, (
            f"при r̃={r_tilde} чтение 1/n должно становиться допустимым к n=30, "
            f"а требуется {need_plain}"
        )


def test_rejects_degenerate_input() -> None:
    with pytest.raises(ValueError, match="минимум 3"):
        sp33_autocorrelation_b1_b2_b3(np.array([1.0, 2.0]))
    with pytest.raises(ValueError, match="без изменений"):
        sp33_autocorrelation_b1_b2_b3(np.full(10, 5.0))


def test_calculation_still_uses_pearson_until_exponent_is_confirmed() -> None:
    """Пока (Б.1) не подтверждена, расчётный путь остаётся на корреляции Пирсона."""
    from core.stats.parameters import calculate_statistical_parameters

    rng = np.random.default_rng(20260928)
    series = rng.lognormal(0.0, 0.4, 40)
    result = calculate_statistical_parameters(series, show_warnings=False)
    assert result["r1"] == pytest.approx(
        float(np.corrcoef(series[:-1], series[1:])[0, 1]), abs=1e-4
    )
    assert "уточняется" in result["r1_source"], (
        "в выводе должно быть видно, что нормативная величина не подключена"
    )
