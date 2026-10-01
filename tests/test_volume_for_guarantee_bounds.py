"""Границы бинарного поиска в mode='volume_for_guarantee': два исправленных дефекта.

ИСТОРИЯ. Оба дефекта найдены read-only-аудитом и воспроизведены на
production-коде инструментированием _calculate_regulation_year_metrics.

Дефект 1 — ЛОЖНОЕ ПРИНЯТИЕ ГРАНИЦЫ. best_V инициализировался значением
V_high, а условие выхода из цикла проверялось ДО тела. При V_upper < 1e6 м³
(порог max_drawdown < 0.0159 м³/с) тело не выполнялось ни разу, и наружу
уходила верхняя граница как «найденное решение»: состояние «решение не
найдено» было неотличимо от состояния «найдено ровно на границе».

Дефект 2 — АБСОЛЮТНЫЙ ДОПУСК. Критерий сходимости V_high - V_low < 1e6 м³
был чисто абсолютным, то есть для водохранилища объёмом менее 1 млн м³
допуск превышал сам объём. Это и порождало дефект 1, а также не позволяло
разрешить малые объёмы: истинный ответ 0 возвращался как ~0.9 млн м³.

ИСПРАВЛЕНИЕ. Критерий сходимости стал комбинированным —
max(1 м³, 1e-9 · max(|V_high|, |V_low|, 1)) — а решение дополнительно
проверяется фактическим достижением целевой гарантии в найденной точке.
Возврат границы без подтверждения теперь невозможен.

Значения допуска не введены заново: относительная 1e-9 уже применяется в
этом же модуле для допуска на сумму (Q−D), пол 1.0 — там же для защиты от
нулевого масштаба. Это численный критерий алгоритма, не нормативный параметр.

ЧТО НАМЕРЕННО НЕ ТРОГАЕТСЯ этим набором: множитель запаса `* 2`, fallback
`* 1.5`, ветка `net < 0`, округление полей required_volume_* , Ripple и
методика массовой кривой.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.hydrorash import reservoir_regulation as rr

T_YEAR = 365 * 86400

# Ряд из production-кейса аудита: объём менее 1 млн м³.
SMALL_SERIES = np.array([0.1, 0.1, 0.1, 0.09])
SMALL_DEMAND = 0.096
SMALL_V_UPPER = 378_432.0   # 2 * max_drawdown * T, была возвращена как «решение»
SMALL_TRUE_MIN = 189_216.0  # max_drawdown * T, истинный минимум без недобора

# Обычный случай из задания на аудит.
NORMAL_SERIES = np.array([30.0, 110.0, 130.0, 190.0])
NORMAL_DEMAND = 100.0
NORMAL_EXPECTED_MLN = 2207.5


def _iterations(monkeypatch, series, demand, target=95.0, mode="volume_for_guarantee"):
    """Запустить production-функцию, посчитав итерации тела бинарного поиска.

    Инструментирование в памяти процесса: подменяется только helper, файлы
    не меняются. Число вызовов минус одна финальная проверка равно числу
    итераций тела цикла.

    Третьим элементом возвращается ТОЧНОЕ значение best_V, извлечённое из
    трассировки. Оно необходимо потому, что публичные поля округляются
    (required_volume_mln_m3 — с шагом 0.1 млн м³), и по ним нельзя судить о
    точности самого поиска. Округление публичных полей — отдельная задача и
    в этом наборе намеренно не проверяется.
    """
    real = rr._calculate_regulation_year_metrics
    seen: list[float] = []

    def traced(Q, d, cap, init, years=T_YEAR):
        seen.append(float(cap))
        return real(Q, d, cap, init, years)

    monkeypatch.setattr(rr, "_calculate_regulation_year_metrics", traced)
    result = rr.multi_year_regulation(series, demand, mode=mode, target_guarantee=target)
    return result, max(0, len(seen) - 1), seen[-1]


# ----------------------------------------------------------------------
# Test A — граница больше не выдаётся за найденное решение
# ----------------------------------------------------------------------
def test_small_reservoir_no_longer_returns_the_search_boundary() -> None:
    """Production-кейс: функция больше не возвращает V_upper как решение.

    До исправления: 0 итераций тела цикла, возврат ровно 378 432 м³.
    Теперь поиск выполняется и находит истинный минимум 189 216 м³, а
    публичное поле, округлённое до 0.1 млн м³, даёт 0.2, а не 0.4.
    """
    result = rr.multi_year_regulation(
        SMALL_SERIES, SMALL_DEMAND, mode="volume_for_guarantee",
        target_guarantee=95.0,
    )
    returned_mln = result["required_volume_mln_m3"] * 1e6

    assert returned_mln != pytest.approx(SMALL_V_UPPER, rel=1e-3), (
        "функция вернула верхнюю границу поиска как найденное решение — "
        "дефект не устранён"
    )
    assert result["required_volume_mln_m3"] == pytest.approx(0.2, abs=1e-9)
    assert result["guarantee_percent"] >= 95.0, "возвращённое значение обязано быть проверено"


def test_small_reservoir_search_actually_runs(monkeypatch) -> None:
    """Тело бинарного поиска выполняется ненулевое число раз.

    Это прямое измерение того, что раньше давало ноль итераций: условие выхода
    проверялось до тела, поэтому при V_upper < 1e6 м³ цикл не делал ничего.
    """
    _, iterations, _ = _iterations(monkeypatch, SMALL_SERIES, SMALL_DEMAND)

    assert iterations > 0, (
        "бинарный поиск не выполнил ни одной итерации — граница будет "
        "возвращена как найденное решение"
    )
    assert iterations < 50, "цикл должен сходиться, а не упираться в лимит итераций"


def test_insufficient_upper_bound_is_rejected_explicitly(monkeypatch) -> None:
    """Недостаточная верхняя граница даёт явный отказ, а не число.

    Граница искусственно занижается в 10^6 раз, после чего истинный минимум
    (189 216 м³) оказывается вне диапазона поиска. Функция обязана отказать,
    а не вернуть границу: возвращённое число не является подтверждённым
    минимальным требуемым объёмом.

    Проверка отказа построена на ФАКТИЧЕСКОМ достижении гарантии, а не на
    сравнении best_V == V_high, поэтому корректно отличает «решение найдено
    у границы» от «границы не хватило».
    """
    real_ripple = rr._ripple_mass_curve

    def crippled(q_d):
        result = dict(real_ripple(q_d))
        result["required_m3_s"] = result["required_m3_s"] * 1e-6
        return result

    monkeypatch.setattr(rr, "_ripple_mass_curve", crippled)

    with pytest.raises(ValueError, match="НЕ ПОДТВЕРЖДЕНА"):
        rr.multi_year_regulation(
            SMALL_SERIES, SMALL_DEMAND, mode="volume_for_guarantee",
            target_guarantee=95.0,
        )


def test_refusal_message_states_the_volume_is_not_confirmed() -> None:
    """Сообщение об отказе обязано говорить, что число не подтверждено.

    Иначе отказ неотличим от «ёмкость нулевая» или от обычного отказа по
    неверным входным данным, и пользователь не поймёт, что расчёт не выполнен.
    """
    real_ripple = rr._ripple_mass_curve

    def crippled(q_d):
        result = dict(real_ripple(q_d))
        result["required_m3_s"] = result["required_m3_s"] * 1e-6
        return result

    original = rr._ripple_mass_curve
    try:
        rr._ripple_mass_curve = crippled
        with pytest.raises(ValueError) as excinfo:
            rr.multi_year_regulation(
                SMALL_SERIES, SMALL_DEMAND, mode="volume_for_guarantee",
                target_guarantee=95.0,
            )
    finally:
        rr._ripple_mass_curve = original

    message = str(excinfo.value)
    assert "95" in message, "сообщение должно называть целевую гарантию"
    assert "недостаточной" in message or "не смог найти" in message
    assert "НЕ является подтверждённым" in message


# ----------------------------------------------------------------------
# Test B — обычный случай не сломан
# ----------------------------------------------------------------------
def test_normal_case_still_solves_and_matches_previous_value() -> None:
    """Штатный случай: результат методологически тот же, отказа нет.

    Ожидаемое значение 2 207.5 млн м³ получено ДО исправления при старом
    допуске 1e6. Расхождение означало бы, что изменён критерий сходимости
    самих вычислений, а не только граница поиска.
    """
    result = rr.multi_year_regulation(
        NORMAL_SERIES, NORMAL_DEMAND, mode="volume_for_guarantee",
        target_guarantee=95.0,
    )

    assert result["required_volume_mln_m3"] == pytest.approx(
        NORMAL_EXPECTED_MLN, abs=1e-9
    )
    assert result["guarantee_percent"] >= 95.0
    assert result["deficit_years"] == 0


def test_normal_case_search_really_executes(monkeypatch) -> None:
    """Поиск выполняется ненулевое число итераций и укладывается в лимит."""
    _, iterations, _ = _iterations(monkeypatch, NORMAL_SERIES, NORMAL_DEMAND)

    assert iterations > 0
    assert iterations <= 50


def test_normal_case_boundary_never_returned_verbatim() -> None:
    """Возврат не равен верхней границе поиска, даже с запасом ×2.

    Смысл проверки: запас «2x» не должен попадать в результат. Если бы
    бинарный поиск снова не выполнился, вернулось бы ровно 2 · max_drawdown · T.
    """
    max_drawdown = rr._ripple_mass_curve(NORMAL_SERIES - NORMAL_DEMAND)["required_m3_s"]
    v_upper = max_drawdown * T_YEAR * 2

    result = rr.multi_year_regulation(
        NORMAL_SERIES, NORMAL_DEMAND, mode="volume_for_guarantee",
        target_guarantee=95.0,
    )
    returned_mln = result["required_volume_mln_m3"] * 1e6

    assert returned_mln < v_upper * 0.75, (
        "возврат слишком близок к верхней границе поиска — вероятно, "
        "бинарный поиск не отработал"
    )


# ----------------------------------------------------------------------
# Test C — малый объём и абсолютный пол допуска
# ----------------------------------------------------------------------
def test_sub_million_volume_resolves_with_absolute_tolerance_floor(monkeypatch) -> None:
    """Малый объём разрешается до абсолютного пола 1 м³.

    ВАЖНО О МЕХАНИЗМЕ. При V_high <= 1e9 м³ выражение
    max(volume_abs_tol, volume_rel_tol * scale) выбирает АБСОЛЮТНЫЙ пол
    1 м³, а не относительный член. Относительная точность здесь не
    проверяется и не активна; имя теста отражает именно пол.

    При старом абсолютном допуске 1e6 м³ поиск на этом ряде не выполнялся ни
    одной итерации (V_upper = 189 216 м³ < 1e6), и ответ был ровно вдвое
    больше истинного. Теперь итерации выполняются, а найденное значение
    совпадает с истинным минимумом, что при допуске 1e6 недостижимо.
    """
    series = np.array([0.05, 0.05, 0.05, 0.045])
    demand = 0.048
    true_min = 0.003 * T_YEAR  # 94 608 м³

    assert true_min < 1e6, "объём должен быть заведомо меньше старого допуска"

    result, iterations, best_v = _iterations(monkeypatch, series, demand, target=100.0)

    assert iterations > 0, "поиск обязан выполняться при V_upper < 1e6 м³"
    # Сверка по ТОЧНОМУ best_V, а не по округлённому публичному полю:
    # required_volume_mln_m3 округляется с шагом 0.1 млн м³, что само по
    # себе даёт до 5.7 % погрешности на этом объёме и не характеризует поиск.
    assert best_v == pytest.approx(true_min, rel=1e-9), (
        f"найдено {best_v:,.6f} м³ вместо {true_min:,.6f} м³ — "
        "сходимость к минимуму не достигнута"
    )
    assert result["guarantee_percent"] == pytest.approx(100.0)


def test_zero_answer_case_converges_instead_of_stalling(monkeypatch) -> None:
    """Истинный ответ 0 сходится к нулю в пределах пола 1 м³.

    Ряд без единого дефицитного года: запас не убывает, поэтому минимальная
    ёмкость равна нулю. При старом допуске 1e6 м³ цикл останавливался с
    ответом порядка 10^6 м³, что для нулевого ответа является грубой ошибкой.

    ПРОВЕРКА ИДЁТ ПО ВНУТРЕННЕМУ best_V, а не по публичному полю.
    required_volume_mln_m3 округляется с шагом 0.1 млн м³, поэтому проверка
    публичного поля пропускала бы любой ответ меньше 50 000 м³ — включая
    40 000, что в 40 000 раз больше истинного нуля.

    Ровно ноль не требуется: бисекция останавливается по допуску, и при
    volume_abs_tol = 1.0 фактический результат составляет около 0.9 м³.
    Требуется лишь уложиться в пол.
    """
    series = np.array([60.0, 70.0, 80.0])
    demand = 50.0

    result, iterations, best_v = _iterations(monkeypatch, series, demand)

    assert iterations > 0, "бинарный поиск обязан выполняться"
    assert abs(best_v) <= 1.0, (
        f"при истинном ответе 0 внутренний best_V = {best_v:,.6f} м³ — "
        "это на порядки выше пола 1 м³, значит поиск не сошёлся"
    )
    # Публичные поля — дополнительная проверка, а не основная.
    assert result["required_volume_mln_m3"] == 0.0, (
        "минимальная ёмкость для ряда без дефицита равна 0, а не "
        f"{result['required_volume_mln_m3']} млн м³"
    )
    assert result["guarantee_percent"] == pytest.approx(100.0)


# ----------------------------------------------------------------------
# Test D — решение у верхней границы не считается ошибкой
# ----------------------------------------------------------------------
def test_solution_at_top_of_range_is_not_false_rejected(monkeypatch) -> None:
    """Достижимое решение у верхней границы принимается, отказа нет.

    Отказ срабатывает по фактической проверке гарантии, поэтому решение,
    найденное у границы (здесь — ровно на её половине, то есть в самом
    верхнем возможном положении при множителе запаса 2), обязано быть
    принято. Иначе проверка была бы слишком строгой и ломала бы штатные
    случаи.
    """
    series = NORMAL_SERIES
    demand = NORMAL_DEMAND
    max_drawdown = rr._ripple_mass_curve(series - demand)["required_m3_s"]
    v_upper = max_drawdown * T_YEAR * 2
    half_of_upper = v_upper / 2  # = max_drawdown * T, верхняя граница ответа

    result = rr.multi_year_regulation(
        series, demand, mode="volume_for_guarantee", target_guarantee=100.0
    )
    returned_mln = result["required_volume_mln_m3"] * 1e6

    assert result["guarantee_percent"] >= 100.0, "отказа быть не должно"
    assert returned_mln == pytest.approx(half_of_upper, rel=1e-2), (
        f"ответ {returned_mln:,.0f} м³ должен совпадать с верхним возможным "
        f"положением {half_of_upper:,.0f} м³"
    )
    # Границу поиска наружу не отдаём даже в этом предельном случае.
    assert returned_mln < v_upper * 0.75


def test_strict_target_still_accepted_when_attainable() -> None:
    """Строгая цель (100 %) принимается, когда она достижима.

    Проверка против «ложной строгости»: убеждается, что отказ не срабатывает
    просто из-за высокой целевой гарантии.
    """
    for target in (95.0, 100.0):
        result = rr.multi_year_regulation(
            NORMAL_SERIES, NORMAL_DEMAND, mode="volume_for_guarantee",
            target_guarantee=target,
        )
        assert result["guarantee_percent"] >= target - 1e-9


def test_existing_target_range_validation_is_preserved() -> None:
    """Прежняя проверка диапазона цели не ослаблена исправлением.

    Цель вне (0, 100] отсекается на входе, ДО бинарного поиска, собственным
    сообщением. Новая проверка достижимости не должна перехватывать этот случай
    и не должна позволить ему пройти дальше.
    """
    for bad_target in (0.0, -1.0, 100.0000001, 150.0):
        with pytest.raises(ValueError, match="target_guarantee"):
            rr.multi_year_regulation(
                NORMAL_SERIES, NORMAL_DEMAND, mode="volume_for_guarantee",
                target_guarantee=bad_target,
            )
