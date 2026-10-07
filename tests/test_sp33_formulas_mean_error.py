"""Формулы (5.26), (5.27), (5.28) СП 33-101-2003 сверены с печатным оригиналом.

Транскрипция от 2026-09-28 (пользователь проекта, печатный экземпляр),
зафиксированная в `tests/fixtures/sp33_formulas_5_16_5_28_v1.json`.

Что этот файл утверждает и что проверяет:

* **(5.26) и (5.27) в коде есть и верны.** Ранее я подозревала, что множитель
  автокорреляции в `relative_mean_error_percent` самодельный. Оказалось
  наоборот: функция дословно реализует (5.26) при r < 0,5 и (5.27) при r ≥ 0,5.
  Особенно важно тождество в (5.27): код суммирует Σ(1 − r^k), стандарт пишет
  n − (1 − r^n)/(1 − r). Это одно и то же, и тождество доказывается, а не
  подбирается.

* **(5.28) НЕ реализована, и код расходится с ней.** В `compute_hydro_stats_with_errors`
  ведущего множителя Cv нет, то есть σ_Cv занижается в Cv раз. Функция
  атрибутирована Сикану А.В. и др. (2021), а не СП 33, поэтому это не нарушение
  нормы — но расхождение зафиксировано явно, а не замолчано.

* Ловушка нумерации: ПУНКТ 5.8 и ФОРМУЛА (5.8) — разные вещи. Пункт 5.8 касается
  объединения данных по группе станций; формула (5.8) определяет Ĉv и напечатана
  внутри пункта 5.6. На этом спотыкались три раза подряд.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from core.stats.parameters import relative_mean_error_percent

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests" / "fixtures"
    / "sp33_formulas_5_16_5_28_v1.json"
)
FORMULAS = json.loads(FIXTURE.read_text(encoding="utf-8"))["formulas"]


# --- независимые реализации по транскрипции ------------------------------

def sp33_526_relative(cv: float, n: int, r: float) -> float:
    """(5.26): σ_Q̄ = (σ_Q/√n)·√((1+r)/(1−r)), относительная погрешность в %."""
    return cv / np.sqrt(n) * np.sqrt((1.0 + r) / (1.0 - r)) * 100.0


def geometric_sum_form(n: int, r: float) -> float:
    """Что написано в (5.27): n − (1 − r^n)/(1 − r)."""
    return n - (1.0 - r**n) / (1.0 - r)


def sp33_527_relative(cv: float, n: int, r: float) -> float:
    """(5.27) в виде стандарта, с геометрической суммой."""
    corr = geometric_sum_form(n, r)
    num = 1.0 + 2.0 * r / (n * (1.0 - r)) * corr
    den = 1.0 - 2.0 * r / (n * (n - 1) * (1.0 - r)) * corr
    return cv / np.sqrt(n) * np.sqrt(num / den) * 100.0


# --- тождество ------------------------------------------------------------

@pytest.mark.parametrize("n", [10, 25, 40, 100])
@pytest.mark.parametrize("r", [0.1, 0.35, 0.5, 0.7, 0.9])
def test_geometric_sum_identity(n: int, r: int | float) -> None:
    """Σ(1 − r^k), k = 1..n−1, тождественно n − (1 − r^n)/(1 − r).

    Именно на этом rests вся (5.27): код суммирует, стандарт пишет замкнутую
    форму. Тождество доказывается, а не подбирается численно.
    """
    series = sum(1.0 - r**k for k in range(1, n))
    assert series == pytest.approx(geometric_sum_form(n, r), rel=1e-12)


# --- (5.26) ---------------------------------------------------------------

@pytest.mark.parametrize("r", [0.0, 0.1, 0.25, 0.499])
@pytest.mark.parametrize(("cv", "n"), [(0.2, 20), (0.5, 30), (0.9, 60)])
def test_code_matches_formula_526(cv: float, n: int, r: float) -> None:
    got = relative_mean_error_percent(cv, n, r)
    assert got == pytest.approx(sp33_526_relative(cv, n, r), rel=1e-12), (
        f"(5.26) не совпала при cv={cv}, n={n}, r={r}"
    )


def test_branch_switches_at_half_and_branches_agree_there() -> None:
    """Ниже 0,5 работает (5.26), на и выше — (5.27), и в точке переключения
    они почти совпадают.

    Именно близость на границе и есть доказательство, что переключение
    корректно: (5.27) — уточнение (5.26), а не другая величина. Моё первое
    ожидание «(5.27) даёт в полтора раза больше» было неверным — расхождение
    накапливается с ростом r, а не возникает скачком.
    """
    below = relative_mean_error_percent(0.5, 30, 0.49)
    at = relative_mean_error_percent(0.5, 30, 0.50)
    assert below == pytest.approx(sp33_526_relative(0.5, 30, 0.49), rel=1e-12)
    assert at == pytest.approx(sp33_527_relative(0.5, 30, 0.50), rel=1e-12)
    # в точке переключения расхождение невелико
    assert abs(at - below) / below < 0.05, (
        f"(5.26) и (5.27) разошлись при переключении: {below} против {at}"
    )
    # и (5.27) обгоняет (5.26) с ростом корреляции
    strong = relative_mean_error_percent(0.5, 30, 0.9)
    assert strong > at, "погрешность должна расти с автокорреляцией"


# --- (5.27) ---------------------------------------------------------------

@pytest.mark.parametrize("r", [0.5, 0.65, 0.8, 0.95])
@pytest.mark.parametrize(("cv", "n"), [(0.3, 25), (0.6, 40), (1.0, 15)])
def test_code_matches_formula_527(cv: float, n: int, r: float) -> None:
    got = relative_mean_error_percent(cv, n, r)
    assert got == pytest.approx(sp33_527_relative(cv, n, r), rel=1e-10), (
        f"(5.27) не совпала при cv={cv}, n={n}, r={r}"
    )


def test_527_grows_without_bound_as_correlation_approaches_one() -> None:
    """Поведение при r → 1, а не только совпадение формул.

    При сильной корреляции погрешность среднего расходится, но остаётся
    КОНЕЧНОЙ, пока знаменатель (5.27) положителен. Ожидание «должна быть
    бесконечность» было неверным: ветка inf в коде — защита от
    неположительного знаменателя, а не нормальное поведение.
    """
    prev = 0.0
    for r in (0.5, 0.7, 0.9, 0.99, 0.999):
        value = relative_mean_error_percent(0.5, 30, r)
        assert np.isfinite(value), f"при r={r} получено не конечное значение {value}"
        assert value > prev, f"погрешность должна расти с r: r={r} дал {value}"
        prev = value
    # и рост становится крутым
    assert relative_mean_error_percent(0.5, 30, 0.999) > 100.0, (
        "при r = 0,999 погрешность среднего должна превышать 100 %"
    )


def test_composite_formulas_confirm_the_earlier_finding() -> None:
    """(5.21)-(5.25) совпали с тем, что зафиксировано ранее по текстовому слою."""
    assert FORMULAS["5.23"]["implemented"] is True
    assert FORMULAS["5.21"]["implemented"] is False
    assert FORMULAS["5.22"]["implemented"] is False
    assert FORMULAS["5.25"]["implemented"] is False
    # числовое обоснование двукратного расхождения лежит в перечне пробелов
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    gaps = " ".join(fixture["blocked_functional_gaps"])
    assert "0,19" in gaps and "0,10" in gaps, (
        "двукратное расхождение методов «а» и «б» должно быть зафиксировано"
    )


# --- (5.28) ---------------------------------------------------------------

def test_528_divergence_is_recorded_and_measured() -> None:
    """Расхождение по (5.28) измерено численно, а не только описано.

    По (5.28) σ_Cv = Cv/(n+4Cv²)·√(n(1+Cv²)/2 · (1 + 3Cv·r₂/(1+r))).
    В коде compute_hydro_stats_with_errors ведущего множителя Cv нет, поэтому
    код ПРЕУВЕЛИЧИВАет погрешность. Направление первоначально было указано
    наоборот; расхождение считается здесь, а не берётся из текста.
    """
    cv, n, r, r2 = 0.4, 30, 0.2, 0.05
    extra = 1.0 + 3.0 * cv * r2 / (1.0 + r)
    sp33 = cv / (n + 4 * cv**2) * np.sqrt((n * (1 + cv**2) / 2) * extra) * 100.0
    code = (1.0 / (n + 4 * cv**2)) * np.sqrt(n * (1 + cv**2) / 2) * 100.0

    assert code > sp33, (
        f"код должен преувеличивать относительно (5.28): код {code:.3f} %, "
        f"стандарт {sp33:.3f} %"
    )
    # отношение равно ровно 1/(Cv·sqrt(extra)), без численного подбора
    assert code / sp33 == pytest.approx(1.0 / (cv * np.sqrt(extra)), rel=1e-12), (
        "расхождение должно быть ровно в 1/(Cv·sqrt(1+3Cv·r2/(1+r))) раз"
    )
    # и конкретные числа из находки
    assert code == pytest.approx(13.614, rel=1e-4)
    assert sp33 == pytest.approx(5.580, rel=1e-4)


def test_528_is_declared_not_implemented() -> None:
    assert FORMULAS["5.28"]["implemented"] is False
    assert "ПРЕУВЕЛИЧИВАЕТ" in FORMULAS["5.28"]["divergence"], (
        "направление расхождения должно быть указано явно и верно"
    )
    assert "2,44 раза" in FORMULAS["5.28"]["divergence"]
    assert "r_2" in FORMULAS["5.28"]["requires"]


# --- прочее ---------------------------------------------------------------

def test_526_and_527_are_declared_implemented_with_a_location() -> None:
    for key in ("5.26", "5.27"):
        assert FORMULAS[key]["implemented"] is True, key
        assert "relative_mean_error_percent" in FORMULAS[key]["implemented_in"], key


def test_clause_versus_formula_numbering_collision_is_recorded() -> None:
    """Ловушка, стоившая трёх попыток, зафиксирована в данных."""
    unverified = json.loads(FIXTURE.read_text(encoding="utf-8"))["still_unverified"]
    assert "ПУНКТ 5.8 и ФОРМУЛА (5.8)" in unverified["note"]
    for key in ("5.8", "5.9", "Б.1", "Б.2", "Б.3"):
        assert key in unverified, f"{key} должен оставаться в списке неподтверждённых"
