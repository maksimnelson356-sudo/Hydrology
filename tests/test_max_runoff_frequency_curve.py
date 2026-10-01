"""Кривая обеспеченности максимальных стоков: непрерывность и пригодность.

ЗАДАЧА ФАЙЛА. Закрепить два исправленных дефекта и защитить их от возврата:

  1. НЕНОРМАТИВНОЕ ПРАВИЛО Cs В ПУТИ ПО УМОЛЧАНИЮ. Правило
     Cs = 2·Cv при Cv ≤ 0,5 и Cs = 3·Cv при Cv > 0,5 не имеет найденного
     нормативного подтверждения и вносит РАЗРЫВ кривой: при изменении Cv
     на 10⁻⁴ асимметрия меняется на 50 %, а расчётный расход — на единицы
     процентов. Измеренный скачок при P = 1 % составляет 15,43 м³/с, тогда
     как локальная чувствительность на том же шаге — 0,04 м³/с.
     Изменение default на НЕПРЕРЫВНУЮ эмпирическую Cs устраняет разрыв;
     ветка True сохранена как явный opt-in.

  2. НЕПРИГОДНАЯ ВЫБОРКА, ОБОЗВАННАЯ «НАДЁЖНОЙ». При mean ≤ 0 или r(1) = NaN
     квантили построить нельзя, но класс надёжности оставался «Надёжная»
     без единого предупреждения, потому что εQ при Cv = 0 равна нулю.

МЕТОД. Ожидания выведены из физических свойств распределения, а не из тела
production: непрерывность по Cv, линейность по масштабу, монотонность по
разбросу, поролок нулевого среднего. Внутренние формулы Пирсона III не
вызываются напрямую — проверяется публичный выход.

Нормативный статус max_runoff остаётся PARTIAL; ложная атрибуция
обеспеченностей ГТС пунктам 5.26–5.31 СП 33 не возвращается — её охраняет
tests/test_sp33_clause_5_26_max_runoff.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.hydrorash import max_runoff as mr

# Для n=20 и двух значений (по 10) при среднем m:
#   var(ddof=1) = [10·(d/2)² + 10·(d/2)²]/19 = 5d²/19
#   std = d·sqrt(5/19) = 0,513005·d  =>  Cv = 0,513005·d/m  =>  d = Cv·m/0,513005
_SPREAD_K = np.sqrt(5.0 / 19.0)


def _two_valued_series(target_cv: float, mean: float = 100.0, n: int = 20) -> np.ndarray:
    """Ряд с ЗАДАННЫМ ровно коэффициентом вариации.

    Два значения, каждое по n//2 раз, симметрично относительно среднего.
    Позволяет подойти к порогу 0,5 сколь угодно близко, не полагаясь на
    подбор случайного ряда.
    """
    spread = target_cv * mean / _SPREAD_K
    low = mean - spread / 2.0
    high = mean + spread / 2.0
    assert low > 0.0, "нижнее значение должно оставаться положительным"
    return np.array([low] * (n // 2) + [high] * (n - n // 2))


# ----------------------------------------------------------------------
# A. Разрыв Cs = 2Cv / 3Cv не должен быть в пути по умолчанию
# ----------------------------------------------------------------------
def test_default_path_has_no_jump_near_cv_half() -> None:
    """Кривая по умолчанию непрерывна при Cv = 0,5.

    Непрерывность — обязательное свойство: два ряда, отличающиеся
    разбросом на 10⁻⁴, не могут давать расчётные паводки, различающиеся на
    6 %. Проверяется публичный выход max_runoff_frequency_curve(data) БЕЗ
    указания ветки, то есть именно значение по умолчанию.
    """
    grid = [0.4999, 0.5000, 0.5001]
    quantiles = {}
    for cv in grid:
        frame = mr.max_runoff_frequency_curve(
            pd.Series(_two_valued_series(cv)), P_values=[1.0]
        )
        quantiles[cv] = float(frame["Q_max"].iloc[0])

    step_below = quantiles[0.5000] - quantiles[0.4999]
    step_above = quantiles[0.5001] - quantiles[0.5000]
    largest = max(abs(step_below), abs(step_above))

    assert largest < 1.0, (
        "в пути по умолчанию сохранился скачок: шаги "
        f"{step_below:+.4f} и {step_above:+.4f} м³/с превышают 1 м³/с — "
        "значит default всё ещё использует правило 2Cv/3Cv"
    )

    # Обе величины Cs на этом шаге должны быть почти одинаковыми: эмпирическая
    # асимметрия для двух значений равна нулю и порога не имеет.
    cs_values = [
        float(mr.compute_max_runoff_stats(pd.Series(_two_valued_series(cv)))["Cs"])
        for cv in grid
    ]
    assert max(cs_values) - min(cs_values) < 0.05, (
        f"Cs на сетке около 0,5 скачет: {cs_values}"
    )


def test_default_path_does_not_apply_two_or_three_times_cv() -> None:
    """Cs по умолчанию не равна ни 2Cv, ни 3Cv.

    Проверка через публичные stats: если бы default-ветка осталась
    нормативной, Cs на сетке 0,4999 / 0,5001 дало бы ровно 0,9998 и 1,5003.
    """
    for cv in (0.4999, 0.5001):
        stats = mr.compute_max_runoff_stats(pd.Series(_two_valued_series(cv)))
        assert float(stats["Cs"]) != pytest.approx(2.0 * cv, abs=1e-3), (
            f"Cv={cv}: Cs = 2·Cv — default всё ещё нормативная ветка"
        )
        assert float(stats["Cs"]) != pytest.approx(3.0 * cv, abs=1e-3), (
            f"Cv={cv}: Cs = 3·Cv — default всё ещё нормативная ветка"
        )


# ----------------------------------------------------------------------
# B. Legacy opt-in сохранён: смена default не должна удалять API
# ----------------------------------------------------------------------
def test_legacy_opt_in_still_applies_the_two_three_cv_rule() -> None:
    """Явный use_normative_Cs=True продолжает работать по старой схеме.

    Если бы правка default удалила ветку, арифметика Cs = 2·Cv / 3·Cv
    исчезла бы вместе с ней. Здесь она проверяется напрямую — это и есть
    контракт сохранённого поведения.
    """
    below = float(
        mr.compute_max_runoff_stats(
            pd.Series(_two_valued_series(0.4999)), use_normative_Cs=True
        )["Cs"]
    )
    above = float(
        mr.compute_max_runoff_stats(
            pd.Series(_two_valued_series(0.5001)), use_normative_Cs=True
        )["Cs"]
    )

    assert below == pytest.approx(2.0 * 0.4999, abs=1e-3)
    assert above == pytest.approx(3.0 * 0.5001, abs=1e-3)
    assert above / below == pytest.approx(1.5, abs=0.01), (
        "legacy-ветка должна сохранять скачок в полтора раза — её поведение "
        "не менялось, и тест фиксирует именно это"
    )


def test_legacy_opt_in_still_changes_the_curve() -> None:
    """Две ветки дают РАЗНЫЕ кривые — значит ветка не вырождена в no-op."""
    series = pd.Series(_two_valued_series(0.6))
    default_curve = mr.max_runoff_frequency_curve(series, P_values=[1.0])
    legacy_curve = mr.max_runoff_frequency_curve(
        series, P_values=[1.0], use_normative_Cs=True
    )

    assert float(default_curve["Q_max"].iloc[0]) != float(legacy_curve["Q_max"].iloc[0])


# ----------------------------------------------------------------------
# C. Непригодная нулевая выборка не должна быть «Надёжная»
# ----------------------------------------------------------------------
def test_zero_series_is_not_reported_as_reliable() -> None:
    """Ряд из нулей: квантили не определены, значит и надёжность не может быть.

    При mean = 0 множитель Cv в εQ обращается в ноль, поэтому εQ = 0 и
    прежняя проверка «εQ > 20 %» не срабатывала. Класс надёжности обязан
    отражать пригодность выборки.
    """
    series = pd.Series([0.0, 0.0, 0.0, 0.0])

    stats = mr.compute_max_runoff_stats(series)

    assert stats["reliability_class"] == "Недостаточно данных", (
        f"непригодная выборка получила класс {stats['reliability_class']!r}"
    )
    assert stats["warnings"], "непригодность обязана сопровождаться предупреждением"
    blob = " ".join(stats["warnings"])
    assert "НЕ построена" in blob, (
        f"предупреждение должно прямо говорить, что кривая не построена: {blob}"
    )


def test_zero_series_curve_is_not_a_valid_numeric_curve() -> None:
    """Кривая для нулевого ряда не должна выглядеть как пригодная."""
    frame = mr.max_runoff_frequency_curve(pd.Series([0.0, 0.0, 0.0, 0.0]),
                                         P_values=[1.0, 50.0])

    assert len(frame) == 2
    assert not np.isfinite(frame["Q_max"].to_numpy()).any(), (
        "для нулевого ряда квантили не определены и не должны быть числами"
    )


# ----------------------------------------------------------------------
# D. Нормальный ряд не деградировал
# ----------------------------------------------------------------------
def test_regular_series_still_reports_reliable() -> None:
    """Достаточный ряд положительных расходов остаётся надёжным.

    Новая проверка r(1) не должна срабатывать на данных, где автокорреляция
    определена, — иначе правка сломала бы штатный случай.
    """
    series = pd.Series(np.random.default_rng(7).normal(100.0, 25.0, 40))

    stats = mr.compute_max_runoff_stats(series)

    assert np.isfinite(float(stats["r1"])), "для такого ряда r(1) определена"
    assert stats["warnings"] == [], (
        f"у пригодного ряда не должно быть предупреждений: {stats['warnings']}"
    )
    assert stats["reliability_class"] == "Надёжная"


def test_short_regular_series_is_not_flagged_by_the_new_r1_check() -> None:
    """Короткий ряд: «Недостаточно данных» должен идти от прежней ветки εQ.

    Для n = 8 ряда [10, 12, 15, 18, 20, 25, 30, 35] величина r(1) по
    формулам (Б.1)–(Б.3) СП 33 равна 2,55 — она КОНЕЧНА, поэтому новая
    проверка пригодности не должна срабатывать. Класс остаётся
    «Недостаточно данных» из-за прежней ветки «εQ не вычислена», и это
    различие проверяется по тексту предупреждения.
    """
    series = pd.Series([10.0, 12.0, 15.0, 18.0, 20.0, 25.0, 30.0, 35.0])

    stats = mr.compute_max_runoff_stats(series)

    assert np.isfinite(float(stats["r1"])), (
        "предположение теста нарушено: r(1) перестала быть конечной"
    )
    blob = " ".join(stats["warnings"])
    assert "НЕ построена" not in blob, (
        "новая проверка пригодности сработала на ряде с конечной r(1): " + blob
    )
    assert "εQ НЕ ВЫЧИСЛЕНА" in blob, (
        "ожидалась прежняя ветка погрешности, а не проверка пригодности: " + blob
    )


def test_regular_series_curve_is_finite() -> None:
    """Кривая штатного ряда конечна и содержит столько строк, сколько задано."""
    series = pd.Series(np.random.default_rng(11).normal(80.0, 18.0, 30))
    p_values = [0.1, 1.0, 3.0, 10.0, 50.0]

    frame = mr.max_runoff_frequency_curve(series, P_values=p_values)

    assert list(frame["P_%"]) == p_values
    assert np.isfinite(frame["Q_max"].to_numpy()).all()
    assert (frame["Q_max"] > 0.0).all()


# ----------------------------------------------------------------------
# E. Линейность по масштабу
# ----------------------------------------------------------------------
@pytest.mark.parametrize("n", [8, 20, 40])
def test_quantiles_scale_linearly_with_magnitude(n) -> None:
    """Удвоение всех расходов удваивает квантили.

    Независимое свойство распределения: параметры формы (Cv, Cs) не меняются
    при умножении ряда на константу, поэтому квантили обязаны умножаться на
    ту же константу. Проверка идёт через публичный выход, без обращения к
    формуле Пирсона III.
    """
    base = np.linspace(50.0, 200.0, n)
    p_values = [0.1, 1.0, 5.0, 50.0]

    single = mr.max_runoff_frequency_curve(
        pd.Series(base), P_values=p_values
    )["Q_max"].to_numpy()
    doubled = mr.max_runoff_frequency_curve(
        pd.Series(2.0 * base), P_values=p_values
    )["Q_max"].to_numpy()

    for value, twice in zip(single, doubled):
        assert twice == pytest.approx(2.0 * value, rel=1e-4), (
            f"линейность по масштабу нарушена: {value} -> {twice}"
        )


# ----------------------------------------------------------------------
# F. Монотонность по разбросу
# ----------------------------------------------------------------------
def test_curve_grows_with_spread_at_fixed_mean() -> None:
    """При фиксированном среднем рост разброса не уменьшает расход.

    Свойство монотонности: разброс увеличивает верхние квантили. Медианная
    обеспеченность при неизменном среднем не меняется — её постоянство
    здесь тоже фиксируется, что делает проверку строже.
    """
    template = np.linspace(50.0, 150.0, 40)
    previous = None

    for amplitude in (0.0, 0.5, 1.0, 2.0, 4.0):
        series = pd.Series(100.0 + amplitude * (template - 100.0))
        quantiles = mr.max_runoff_frequency_curve(
            series, P_values=[0.1, 1.0, 5.0, 50.0]
        )["Q_max"].to_numpy()

        if previous is not None:
            for index in range(3):  # обеспеченности 0,1 / 1 / 5 %
                assert quantiles[index] >= previous[index] - 1e-6, (
                    f"верхняя обеспеченность упала при амплитуде {amplitude}: "
                    f"{previous[index]} -> {quantiles[index]}"
                )
            assert quantiles[3] == pytest.approx(100.0, abs=1.0), (
                "медианная обеспеченность при постоянном среднем должна "
                f"оставаться у среднего, получено {quantiles[3]}"
            )
        previous = quantiles
