"""Формулы (Б.1)-(Б.3) СП 33-101-2003, приложение Б.

    (Б.3)  Q̄₁ = Σ(i=2..n) Qᵢ / (n-1)
           Q̄₂ = Σ(i=2..n-1) Qᵢ / (n-1)
    (Б.2)  r̃(1) = Σ(Qᵢ - Q̄₁)(Qᵢ₋₁ - Q̄₂) / √[Σ(Qᵢ - Q̄₁)² · Σ(Qᵢ₋₁ - Q̄₂)²]
    (Б.1)  r(1) = -0,01 + 0,98·r̃ - 0,06·r̃² + (1,66 + 6,46·r̃ + 5,69·r̃²)/n

ИСТОЧНИК И КАК ЧИТАЕТСЯ ЗНАМЕНАТЕЛЬ. Снимок печати `Б1.png` (стр. 74,
приложение Б) от 2026-09-29: последнее слагаемое (Б.1) набрано дробью с
числителем 1 и знаменателем n. Это именно 1/n, а не n^(-1/2) и не n^(1/n).

История чтения, чтобы ошибка не повторилась. Текстовый слой PDF дробь здесь не
отдаёт, и по нему сначала была записана n^(-1/2); при ней r(1) выходит за
единицу почти при любом реальном n — при r̃ = 0,35 допустимое значение
достигается лишь с n = 47, при r̃ = 0,50 с n = 140, при r̃ = 0,70 с n = 645.
Ряды речного стока — это 30-60 лет, то есть такое чтение делает формулу
непригодной. Требовалось изображение печати, а не правдоподобие: снимок показал
1/n, при котором r(1) ≤ 1 начиная с n = 4-26.

Ровно та же ошибка, что и с (7.51): догадка, подставленная в нормативную
величину. Здесь она была поймана снимком ДО подключения функции к расчёту.

ОСОБЕННОСТЬ ОРИГИНАЛА. В (Б.3) знаменатель у Q̄₁ и Q̄₂ один — (n-1), хотя
сумма при Q̄₂ берётся по n-2 членам. Воспроизведено буквально; расхождение
зафиксировано тестом, а не «исправлено».
"""

from __future__ import annotations

import numpy as np
import pytest

from core.stats.parameters import sp33_autocorrelation_b1_b2_b3


def reference(series: np.ndarray) -> dict:
    """Независимая реализация (Б.1)-(Б.3) для сверки, знаменатель n."""
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
        + (1.66 + 6.46 * r_tilde + 5.69 * r_tilde**2) / n
    )
    return {
        "r1": float(r1),
        "r_tilde": float(r_tilde),
        "q_bar_1": float(q1),
        "q_bar_2": float(q2),
    }


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


@pytest.mark.parametrize("n", [20, 40, 60])
def test_r1_is_a_valid_correlation_for_real_length_series(n: int) -> None:
    """При 1/n результат остаётся корреляцией на рядах реальной длины.

    Обратная сторона охранного теста прежней транскрипции: при n^(-1/2) на
    таком же ряду было r(1) > 1. Теперь обязано быть r(1) < 1.

    Ряд берётся iid-логнормальным, а не случайным блужданием: у cumsum-ряда
    автокорреляция первого порядка почти единичная, и тогда даже корректное
    чтение 1/n даёт r(1) > 1 — см. отдельный тест ниже.
    """
    rng = np.random.default_rng(20260928)
    series = rng.lognormal(0.0, 0.4, n)
    out = sp33_autocorrelation_b1_b2_b3(series)
    assert out["r1"] < 1.0, (
        f"при n={n} ожидалась корректная корреляция для чтения 1/n, получено {out['r1']}"
    )


def test_r1_exceeds_one_only_on_near_unit_autocorrelation() -> None:
    """Честная граница применимости: r(1) > 1 возможно и это не дефект.

    При почти единичной автокорреляции (r̃ = 0,92) хвост (Б.1) велик, и
    значение честно выходит за единицу даже при правильном чтении 1/n. Порог
    допустимости зависит от r̃: при r̃ = 0,35 достаточно n = 7, при r̃ = 0,70
    уже n = 26. Утверждать, что 1/n «всегда даёт корреляцию», нельзя.
    """

    def threshold(power: float, r_tilde: float, n_max: int = 20000) -> int:
        for n in range(3, n_max):
            core = 1.66 + 6.46 * r_tilde + 5.69 * r_tilde**2
            value = -0.01 + 0.98 * r_tilde - 0.06 * r_tilde**2 + core / n**power
            if value <= 1.0:
                return n
        return n_max

    # Числа получены прямым расчётом, а не подобраны на глаз.
    assert threshold(1.0, 0.35) == 7
    assert threshold(1.0, 0.70) == 26
    assert threshold(0.5, 0.35) == 47


def test_denominator_is_n_not_sqrt_n() -> None:
    """Прямая фиксация структуры (Б.1): хвост делится на n, а не на √n."""
    series = np.array([3.0, 7.0, 2.0, 9.0, 5.0, 8.0, 4.0, 6.0])  # n = 8
    out = sp33_autocorrelation_b1_b2_b3(series)
    r_t = out["r_tilde"]
    n = series.size
    tail = (1.66 + 6.46 * r_t + 5.69 * r_t**2) / n
    expected = -0.01 + 0.98 * r_t - 0.06 * r_t**2 + tail
    wrong = -0.01 + 0.98 * r_t - 0.06 * r_t**2 + (
        (1.66 + 6.46 * r_t + 5.69 * r_t**2) / np.sqrt(n)
    )
    assert out["r1"] == pytest.approx(expected, rel=1e-12)
    assert out["r1"] != pytest.approx(wrong, rel=1e-6)


def test_sqrt_reading_would_be_physically_invalid() -> None:
    """Отброшенное чтение n^(-1/2) остаётся непригодным — регрессия назад.

    Если в (Б.1) снова впишут √n, порог допустимости уедет с n = 7 на n = 47
    при r̃ = 0,35. Числа ниже получены прямым расчётом.
    """

    def r1_with(power: float, r_tilde: float, n: int) -> float:
        core = 1.66 + 6.46 * r_tilde + 5.69 * r_tilde**2
        return -0.01 + 0.98 * r_tilde - 0.06 * r_tilde**2 + core / n**power

    for n in (10, 20, 40):
        assert r1_with(0.5, 0.35, n) > 1.0, f"n^(-1/2) при n={n} должно давать r(1) > 1"
        assert r1_with(1.0, 0.35, n) < 1.0, f"1/n при n={n} должно давать r(1) < 1"
    # На n = 47 вариант √n тоже становится допустимым — он не абсурден всегда,
    # а просто требует неправдоподобно длинных рядов.
    assert r1_with(0.5, 0.35, 46) > 1.0
    assert r1_with(0.5, 0.35, 47) < 1.0


def test_b3_uses_n_minus_one_for_both_means_despite_asymmetric_sums() -> None:
    """Знаменатель (n-1) у обеих средних — как напечатано, даже при разном числе слагаемых."""
    series = np.arange(1.0, 11.0)  # n = 10
    out = sp33_autocorrelation_b1_b2_b3(series)
    n = 10
    assert out["q_bar_1"] == pytest.approx(np.sum(series[1:]) / (n - 1))      # 9 слагаемых
    assert out["q_bar_2"] == pytest.approx(np.sum(series[1:n - 1]) / (n - 1))  # 8 слагаемых
    # сумма при Q̄₂ короче, а знаменатель тот же — расхождение зафиксировано
    assert out["q_bar_2"] != pytest.approx(np.sum(series[1:n - 1]) / (n - 2))


def test_rejects_degenerate_input() -> None:
    with pytest.raises(ValueError, match="минимум 3"):
        sp33_autocorrelation_b1_b2_b3(np.array([1.0, 2.0]))
    with pytest.raises(ValueError, match="без изменений"):
        sp33_autocorrelation_b1_b2_b3(np.full(10, 5.0))
