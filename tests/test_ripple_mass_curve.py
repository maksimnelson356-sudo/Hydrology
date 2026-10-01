"""Метод накопленных расходов: регрессии по периодическому продолжению.

История файла. Реализация метода накопленных расходов (массовой кривой)
считала максимальную просадку ТОЛЬКО внутри расчётного периода. Для
многолетнего регулирования это неверно: период повторяется, и водохранилище
обязано обслуживать сток за пределами последнего года записи. На рядах с
Σ(Q−D) = 0 вершина в конце периода должна покрывать яму в начале следующего,
и прежний расчёт этого не видел.

Что проверяется здесь — не «правильность формулы вообще», а три вещи, которые
нельзя пропустить:

1. Золотые значения на двух контрпримерах, где величина просадки известна
   независимо (см. модуль ``reservoir_regulation`` и разбор метода).
2. Поведение на невозможном режиме: при Σ(Q−D) < 0 запас не восстанавливается,
   и конечной ёмкости не существует. Прежний код выдавал здесь правдоподобное
   число, что опаснее явного отказа.
3. Сохранность результатов там, где прежний расчёт был верен: иначе правка
   была бы не исправлением дефекта, а заменой одного числа другим.
4. Признак замкнутости — знак суммы баланса net = Σ(Q−D), а не сравнение
   просадок на продолжениях разной длины: сравнение даёт тот же ответ, но
   является следствием, и на него нельзя опираться как на признак.

НОРМАТИВНЫЙ СТАТУС. Метод не отнесён ни к одному локальному стандарту:
в девяти PDF локального корпуса (СП 529.1325800.2023, СП 33-101-2003,
СП 47.13330.2016, СП 482.1325800.2020, ГОСТ 19179-73, СП 38.13330.2018,
Методические рекомендации, Рождественский, Пособие к СП 33) НОЛЬ вхождений
терминов «Риппл», «массовая кривая», «накопленных расходов». Первичный
источник — Крицкий С.Н., Менкель М.Ф. (1935), в локальном корпусе
отсутствует. Условие установившегося заполнения S_нач = S_кон взято из
приказа МПР РФ от 30.11.2007 № 314. Тесты ниже НЕ приписывают методу
нормативного статуса и проверяют только арифметику и границы применимости.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.hydrorash import reservoir_regulation as rr
from core.hydrorash.reservoir_regulation import multi_year_regulation

T_YEAR = 365 * 86400
D = 100.0

# Два контрпримера из разбора метода. T = 365*86400, поэтому 1 м³/с в
# кумулятивной сумме соответствует 0.031536 км³.
CASE_A = np.array([30.0, 190.0, 30.0, 150.0])   # Σ(Q−D) = 0
CASE_B = np.array([30.0, 110.0, 130.0, 190.0])  # Σ(Q−D) = +60


def _simulate(q_minus_d: np.ndarray, capacity: float, storage: float) -> tuple[float, float, float]:
    """Независимая симуляция цикла: (S_end, сброс, непокрытый сток), м³/с.

    Пишется здесь намеренно своей строкой, а не вызовом приватной функции
    модуля: тест должен проверять опубликованный результат посторонним
    расчётом, иначе он подтверждал бы сам себя.
    """
    spill = 0.0
    unmet = 0.0
    for delta in q_minus_d:
        raw = storage + delta
        if raw < 0.0:
            unmet += -raw
            storage = 0.0
        elif raw > capacity:
            spill += raw - capacity
            storage = capacity
        else:
            storage = raw
    return storage, spill, unmet


def _simulate_cycles(
    q_minus_d: np.ndarray, capacity: float, storage: float, n_cycles: int
) -> tuple[float, float, float]:
    """То же, но n_cycles подряд: незамкнутый режим виден только со второго цикла."""
    spill = 0.0
    unmet = 0.0
    for _ in range(n_cycles):
        storage, cycle_spill, cycle_unmet = _simulate(q_minus_d, capacity, storage)
        spill += cycle_spill
        unmet += cycle_unmet
    return storage, spill, unmet


# ----------------------------------------------------------------------
# Контрпример A: Σ(Q−D) = 0, межцикловая просадка
# ----------------------------------------------------------------------
def test_case_a_required_capacity_crosses_period_boundary() -> None:
    """Золото: 2.838 км³, а не прежние 2.208.

    Q−D = [−70, +90, −70, +50], C = [0, −70, +20, −50, 0], Σ = 0.
    Внутри периода наибольшая просадка 70 (0 → −70). Но вершина C = +20
    (год 2) при Σ = 0 обязана покрыть яму C = −70 года 1 СЛЕДУЮЩЕГО цикла:
    20 − (−70) = 90. Прежний расход останавливался на границе периода.
    """
    result = multi_year_regulation(CASE_A, D, mode="natural_supply")

    assert result["required_volume_km3"] == pytest.approx(2.838, abs=1e-3)
    assert result["required_volume_km3"] != pytest.approx(2.208, abs=1e-3)
    assert result["net_balance_m3_s"] == pytest.approx(0.0)
    assert result["stable_cycle"] is True
    assert result["regulation_possible"] is True


def test_case_a_initial_storage_is_seventy_cubic_metres_per_second() -> None:
    """Начальное заполнение = 70 м³/с × T, и цикл замыкается.

    S* = −min(C) = 70. В установившемся режиме водохранилище проходит
    размах 0…90 и возвращается к 70, поэтому невязка S_кон − S_нач равна нулю.
    """
    result = multi_year_regulation(CASE_A, D, mode="natural_supply")

    assert result["initial_storage_km3"] == pytest.approx(70.0 * T_YEAR / 1e9, abs=1e-6)
    assert result["closure_error_m3_s"] == pytest.approx(0.0, abs=1e-6)
    # При Σ = 0 избытка не образуется: холостого сброса нет.
    assert result["spill_volume_km3"] == pytest.approx(0.0, abs=1e-9)


def test_case_a_cycle_closes_under_independent_simulation() -> None:
    """Замыкание цикла проверяется посторонней симуляцией, а не полем результата.

    Один цикл при ёмкости 90 и старте 70 обязан вернуть ровно 70 без
    непокрытого стока. Если этого нет, заявленная ёмкость нерабочая.
    """
    capacity = 90.0
    start = 70.0
    end, spill, unmet = _simulate(CASE_A - D, capacity, start)

    assert end == pytest.approx(start, abs=1e-9)
    assert unmet == pytest.approx(0.0, abs=1e-9)
    assert spill == pytest.approx(0.0, abs=1e-9)


def test_capacity_seventy_serves_one_cycle_but_fails_the_second() -> None:
    """Почему 2.208 км³ были негодны: первый цикл проходит, второй — нет.

    При ёмкости 70 и старте 70 первый цикл обслуживается полностью (даже со
    сбросом 20), но запас падает до 50 и уже во втором цикле первая яма не
    покрывается. Незамкнутость видна только при многократном прогоне, поэтому
    проверка на одном периоде прошла бы, не заметив дефекта.
    """
    one_cycle = _simulate(CASE_A - D, 70.0, 70.0)
    assert one_cycle[2] == pytest.approx(0.0, abs=1e-9), "первый цикл обслуживается"

    two_cycles = _simulate_cycles(CASE_A - D, 70.0, 70.0, 2)
    assert two_cycles[2] > 0.0, "со второго цикла ёмкости 70 перестаёт хватать"


# ----------------------------------------------------------------------
# Контрпример B: Σ(Q−D) > 0, возникает холостой сброс
# ----------------------------------------------------------------------
def test_case_b_required_capacity_and_spill() -> None:
    """Золото: 2.208 км³ и сброс ровно 60 м³/с × T.

    Q−D = [−70, +10, +30, +90], C = [0, −70, −60, −30, +60], Σ = +60.
    Избыток последнего года покрывает яму первого года следующего цикла
    (90 ≥ 70), поэтому межцикловая просадка здесь не превышает внутрипериодную,
    и ёмкость остаётся прежней — 70. Но избыток не накапливается: ёмкость
    конечна, и 60 м³/с ежегодно уходят на холостой сброс.
    """
    result = multi_year_regulation(CASE_B, D, mode="natural_supply")

    assert result["required_volume_km3"] == pytest.approx(2.208, abs=1e-3)
    assert result["net_balance_m3_s"] == pytest.approx(60.0)
    assert result["spill_volume_km3"] == pytest.approx(60.0 * T_YEAR / 1e9, abs=1e-6)
    assert result["stable_cycle"] is True
    assert result["closure_error_m3_s"] == pytest.approx(0.0, abs=1e-6)


def test_case_b_surplus_does_not_carry_over_between_cycles() -> None:
    """Положительный годовой баланс НЕ переносится на следующий цикл.

    Ёмкость конечна, поэтому избыток покидает систему. Проверяется пошагово:
    на четвёртом году запас насыщается и ровно 60 м³/с сбрасывается, после
    чего цикл начинается заново с полного — то есть следующий цикл не имеет
    «вкладного» излишка и яма первого года покрывается из ёмкости, а не из
    прошлого избытка.
    """
    capacity = 70.0
    end, spill, unmet = _simulate(CASE_B - D, capacity, capacity)

    assert spill == pytest.approx(60.0), "сброс обязан равняться сумме (Q−D)"
    assert unmet == pytest.approx(0.0, abs=1e-9)
    assert end == pytest.approx(capacity, abs=1e-9), "цикл обязан быть установившимся"


# ----------------------------------------------------------------------
# Невозможный режим
# ----------------------------------------------------------------------
def test_negative_net_balance_reports_impossible_not_a_finite_number() -> None:
    """Σ(Q−D) < 0: замкнутый режим невозможен, и это сказано явно.

    Запас теряет |Σ| за каждый цикл и никогда не восстанавливается, поэтому
    никакая конечная ёмкость не обеспечит работу без дефицита. Прежний код
    выдавал здесь правдоподобное число (для Q=[50,60,90,120], D=100 это были
    3.154 км³ при Σ = −80), что опаснее отказа: число выглядит как проектный
    результат.
    """
    q = np.array([50.0, 60.0, 90.0, 120.0])
    result = multi_year_regulation(q, D, mode="natural_supply")

    assert result["net_balance_m3_s"] < 0.0
    assert result["regulation_possible"] is False
    assert result["capacity_unbounded"] is True
    assert result["stable_cycle"] is False
    assert np.isnan(result["required_volume_km3"]), (
        "ёмкость не должна подменяться нулём: нулевой объём означал бы, что "
        "регулирование не нужно, а не что оно невозможно"
    )


def test_two_and_three_period_drawdowns_diverge_only_for_negative_balance() -> None:
    """ДИАГНОСТИКА, не признак: 3-периодная просадка совпадает с 2-периодной
    ровно при net ≥ 0.

    Раньше это расхождение и было критерием замкнутости. Теперь критерий
    физический — знак суммы баланса, — а расхождение просадок осталось
    проверкой согласованности: если при net ≥ 0 они разошлись, то ошибка в
    самой формуле, а не в выводе о возможности регулирования.
    """
    q_minus_d = np.array([-70.0, 90.0, -70.0, 50.0])  # Σ = 0
    cumulative = np.concatenate([[0.0], np.cumsum(q_minus_d)])
    two = rr._periodic_max_drawdown(cumulative, 0.0, 2)
    three = rr._periodic_max_drawdown(cumulative, 0.0, 3)
    assert two == pytest.approx(three, abs=1e-9)
    assert two == pytest.approx(90.0)

    rising = np.array([-70.0, 10.0, 30.0, 90.0])  # Σ = +60
    cumulative = np.concatenate([[0.0], np.cumsum(rising)])
    assert rr._periodic_max_drawdown(cumulative, 60.0, 3) == pytest.approx(
        rr._periodic_max_drawdown(cumulative, 60.0, 2), abs=1e-9
    )

    falling = np.array([-10.0, 3.0, 3.0, 3.0])  # Σ = −1
    cumulative = np.concatenate([[0.0], np.cumsum(falling)])
    assert rr._periodic_max_drawdown(cumulative, -1.0, 3) > rr._periodic_max_drawdown(
        cumulative, -1.0, 2
    )


def test_stability_is_decided_by_net_sign_not_by_drawdown_comparison() -> None:
    """Критерий замкнутости — знак Σ(Q−D), а не сравнение просадок.

    Проверяется тем, что при net ≥ 0 просадка на 2 и 3 периодах совпадает, и
    тем, что при net < 0 совпадения нет, — и в обоих случаях решение
    принимается по знаку суммы. Отдельно проверяется, что почти нулевая
    отрицательная сумма в пределах допуска даёт устойчивый цикл: иначе ряд с
    ошибкой округления в 1e-10 м³/с объявлялся бы нерегулируемым.
    """
    # net = 0: сумма с плавающей точкой может дать крошечный отри остаток.
    ripple = rr._ripple_mass_curve(np.array([-70.0, 90.0, -70.0, 50.0]))
    assert ripple["net_balance_m3_s"] == pytest.approx(0.0, abs=1e-12)
    assert ripple["stable_cycle"] is True
    assert ripple["three_period_m3_s"] == pytest.approx(ripple["required_m3_s"], abs=1e-9)

    # Заметно отрицательная сумма — устойчивого цикла нет.
    falling = rr._ripple_mass_curve(np.array([-10.0, 3.0, 3.0, 3.0]))
    assert falling["net_balance_m3_s"] == pytest.approx(-1.0)
    assert falling["stable_cycle"] is False
    assert np.isnan(falling["required_m3_s"])


def test_tiny_negative_balance_within_tolerance_is_treated_as_balanced() -> None:
    """Допуск отделяет ошибку округления от настоящего дефицита.

    Ряд из четырёх одинаковых значений при D = 100 + 1e-10 даёт сумму
    −4e-10 м³/с. Это не истощение водохранилища, а погрешность float, и
    объявлять такой ряд нерегулируемым было бы ошибкой на единицы порядка
    меньше самой величины.
    """
    ripple = rr._ripple_mass_curve(np.full(4, 100.0) - (100.0 + 1e-10))
    assert ripple["net_balance_m3_s"] < 0.0
    assert ripple["stable_cycle"] is True, "сумма в пределах допуска — не дефицит"
    assert ripple["regulation_possible"] is True
    assert np.isfinite(ripple["required_m3_s"])


def test_deficit_fraction_keeps_previous_within_period_semantics() -> None:
    """deficit_fraction не задет правкой метода накопленных расходов.

    Поле по-прежнему считается по просадке ВНУТРИ одного периода, а не по
    требуемой ёмкости, и остаётся конечным даже там, где ёмкость невозможна.
    Иначе правка Ripple задела бы поле, чья методология разбирается отдельно.
    """
    def old_algorithm(q, demand):
        q = np.asarray(q, dtype=float)
        mean = float(np.mean(q))
        max_c = c = 0.0
        mdd = 0.0
        for x in (q - demand):
            c += x
            if max_c - c > mdd:
                mdd = max_c - c
            if c > max_c:
                max_c = c
        return round(mdd / mean, 3) if mean > 0 else 0

    for q, demand in (
        (CASE_A, D),
        (CASE_B, D),
        (np.array([50.0, 60.0, 90.0, 120.0]), D),          # net < 0
        (np.array([100.0, 80.0, 120.0, 90.0, 110.0, 70.0, 130.0, 95.0, 105.0, 85.0]), 95.0),
    ):
        result = multi_year_regulation(q, demand, mode="natural_supply")
        assert result["deficit_fraction"] == old_algorithm(q, demand), q.tolist()


def test_deficit_fraction_stays_finite_where_capacity_is_impossible() -> None:
    """При невозможном режиме ёмкость NaN, но deficit_fraction — конечное число.

    Смешивать эти два отказа нельзя: одно означает «регулирование невозможно»,
    другое остаётся характеристикой исходного ряда.
    """
    result = multi_year_regulation(np.array([50.0, 60.0, 90.0, 120.0]), D,
                                   mode="natural_supply")
    assert result["regulation_possible"] is False
    assert np.isnan(result["required_volume_km3"])
    assert np.isfinite(result["deficit_fraction"])
    assert result["deficit_fraction"] == pytest.approx(1.25, abs=1e-9)


# ----------------------------------------------------------------------
# Периодическое продолжение
# ----------------------------------------------------------------------
def test_capacity_uses_periodic_extension_not_single_pass() -> None:
    """Ёмкость обязана быть больше внутрипериодной просадки там, где есть граница.

    Проверяется напрямую: просадка на 2-периодном продолжении равна сумме
    двух внутрипериодных, а не внутрипериодной.
    """
    q_minus_d = CASE_A - D
    cumulative = np.concatenate([[0.0], np.cumsum(q_minus_d)])

    single = rr._periodic_max_drawdown(cumulative, 0.0, 1)
    double = rr._periodic_max_drawdown(cumulative, 0.0, 2)

    assert single == pytest.approx(70.0)
    assert double == pytest.approx(90.0)
    assert double > single


def test_max_drawdown_equals_exhaustive_pair_search() -> None:
    """Цикл с «текущим максимумом» эквивалентен прямому перебору пар i < j.

    Это не проверка метода, а проверка реализации: оптимизированный проход
    обязан совпадать с определением max_{i<j}(C_i − C_j) на всех парах, иначе
    расхождение объяснить нечем.
    """
    rng = np.random.default_rng(0)
    for _ in range(200):
        q_minus_d = rng.integers(-90, 90, size=rng.integers(2, 9)).astype(float)
        cumulative = np.concatenate([[0.0], np.cumsum(q_minus_d)])
        net = float(cumulative[-1])

        fast = rr._periodic_max_drawdown(cumulative, net, 2)

        n = len(q_minus_d)
        extended = np.concatenate([cumulative + p * net for p in range(2)])
        best = 0.0
        for i in range(len(extended)):
            for j in range(i + 1, len(extended)):
                best = max(best, extended[i] - extended[j])
        assert fast == pytest.approx(best), f"расхождение на {q_minus_d.tolist()}"


# ----------------------------------------------------------------------
# Единственная реализация для трёх режимов
# ----------------------------------------------------------------------
def test_all_three_modes_go_through_the_same_function(monkeypatch) -> None:
    """Три прежние копии цикла заменены одной функцией — проверяем поведением.

    Считать вызовы самой функции надёжнее, чем искать её телом в исходнике:
    проверка исходника ломается от любого переименования, а счётчик вызовов
    подтверждает именно то, что нужно, — все три режима берут ёмкость
    оттуда.
    """
    calls: list[int] = []
    original = rr._ripple_mass_curve

    def counted(q_minus_d):
        calls.append(len(q_minus_d))
        return original(q_minus_d)

    monkeypatch.setattr(rr, "_ripple_mass_curve", counted)

    multi_year_regulation(CASE_A, D, mode="natural_supply")
    assert len(calls) == 1, "natural_supply обязан использовать общую функцию"

    calls.clear()
    multi_year_regulation(CASE_A, D, V_max_km3=1.0, mode="guarantee_for_volume")
    assert len(calls) == 1, "guarantee_for_volume обязан использовать общую функцию"

    calls.clear()
    multi_year_regulation(CASE_A, 50.0, mode="volume_for_guarantee")
    assert len(calls) == 1, "volume_for_guarantee обязан использовать общую функцию"


def test_duplicate_drawdown_loop_is_gone() -> None:
    """Цикл просадки не должен быть продублирован в трёх местах.

    Прежние копии опознаются по характерной связке «текущий максимум —
    просадка»; если она вернулась в двух местах, правка частично откатилась.
    """
    import inspect

    source = inspect.getsource(rr)
    marker = "running_max - value"
    assert source.count(marker) == 1, (
        f"цикл просадки должен быть единственным, найдено {source.count(marker)}"
    )


def test_all_modes_agree_on_required_capacity() -> None:
    """Все три режима публикуют одну и ту же ёмкость для одних и тех же данных."""
    natural = multi_year_regulation(CASE_A, D, mode="natural_supply")
    by_volume = multi_year_regulation(CASE_A, D, V_max_km3=1.0, mode="guarantee_for_volume")

    assert natural["required_volume_km3"] == by_volume["required_volume_km3"]
    for key in ("net_balance_m3_s", "initial_storage_km3", "spill_volume_km3",
                "stable_cycle", "regulation_possible"):
        assert natural[key] == by_volume[key], key


# ----------------------------------------------------------------------
# Сохранность прежних корректных результатов
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "q, demand, expected_km3",
    [
        pytest.param(
            np.array([100.0, 80.0, 120.0, 90.0, 110.0, 70.0, 130.0, 95.0, 105.0, 85.0]),
            95.0, 0.788, id="test_backwater_фикс",
        ),
        pytest.param(np.array([30.0, 101.0, 100.0, 170.0]), 100.0, 2.208,
                     id="sigma_plus_1_простой"),
        pytest.param(np.array([120.0, 60.0, 120.0, 100.0]), 100.0, 1.261,
                     id="sigma_0_две_волны"),
        pytest.param(np.arange(50.0, 90.0, 5.0), 60.0, 0.473,
                     id="монотонно_растущий"),
    ],
)
def test_previously_correct_capacities_are_preserved(q, demand, expected_km3) -> None:
    """Там, где прежний расчёт был верен, число не изменилось.

    Правка обязана исправлять дефект, а не подменять одно число другим. На
    этих рядах избыток приходится на конец периода, поэтому межцикловая
    просадка не превышает внутрипериодную и результат совпадает.
    """
    result = multi_year_regulation(q, demand, mode="natural_supply")
    assert result["required_volume_km3"] == pytest.approx(expected_km3, abs=1e-3)
    assert result["regulation_possible"] is True
    # Замкнутость обязана выполняться, иначе ёмкость нерабочая.
    assert result["closure_error_m3_s"] == pytest.approx(0.0, abs=1e-6)


def test_legacy_keys_are_still_present() -> None:
    """Новые поля не должны были вытеснить старые.

    Результат читают по фиксированным ключам, и молчаливое удаление ключа
    сломало бы выгрузку в .hsp и отчёт.
    """
    for mode, kwargs in (
        ("natural_supply", {}),
        ("guarantee_for_volume", {"V_max_km3": 1.0}),
    ):
        result = multi_year_regulation(CASE_A, D, mode=mode, **kwargs)
        for key in ("required_volume_km3", "required_volume_mln_m3",
                    "guarantee_percent", "Q_mean", "Q_demand"):
            assert key in result, f"{mode}: потерян ключ {key}"
        for key in ("net_balance_m3_s", "initial_storage_km3", "spill_volume_km3",
                    "stable_cycle", "regulation_possible"):
            assert key in result, f"{mode}: нет нового ключа {key}"

    # У этого режима забор задаётся отдельно, поэтому позиционного аргумента нет.
    result = multi_year_regulation(CASE_A, demand_m3_s=50.0, mode="volume_for_guarantee")
    for key in ("required_volume_km3", "achieved_guarantee", "target_guarantee"):
        assert key in result, f"volume_for_guarantee: потерян ключ {key}"
    for key in ("net_balance_m3_s", "initial_storage_km3", "spill_volume_km3",
                "stable_cycle", "regulation_possible"):
        assert key in result, f"volume_for_guarantee: нет нового ключа {key}"


def test_module_does_not_claim_ripple_comes_from_a_local_standard() -> None:
    """Метод не должен быть приписан локальным СП.

    Терминов «Риппл», «массовая кривая», «накопленных расходов» нет ни в
    одном из девяти PDF локального корпуса, поэтому модуль обязан сохранять
    SOURCE_MISSING и не заявлять соответствие СП 33, СП 529, СП 47, СП 482
    или ГОСТ 19179-73.
    """
    import inspect

    doc = inspect.getdoc(rr) or ""
    assert "SOURCE_MISSING" in doc
    assert "OUT_OF_SCOPE" in doc
    for claim in ("соответствует СП 33", "соответствует СП 529",
                  "реализует СП 529", "по СП 33 п. 7.2", "по СП 33 п. 7.3"):
        assert claim not in doc, f"недопустимая атрибуция: {claim!r}"


# ----------------------------------------------------------------------
# P2. Запрет возврата к исторической формуле  V = -min(cumsum(Q - D))
# ----------------------------------------------------------------------
# ИСТОРИЯ. До коммита e39cb39 ёмкость считалась как
#     max_deficit = float(-np.min(cumulative))
# где cumulative = cumsum(Q - D) БЕЗ начального нуля. Величина измеряет
# просадку накопленного баланса ОТ НУЛЯ, то есть предполагает пустой запас
# и однократный прогон. Многолетнее регулирование так не работает: запас
# наполняется, расходуется и снова наполняется, поэтому нужна просадка от
# ЛЮБОГО раннего максимума до ЛЮБОЙ последующей ямы, то есть
# max_{i<j}(C_i - C_j) на периодическом продолжении ряда.
#
# Проверка физическая, а не текстовая: сравнивается опубликованная ёмкость с
# независимо зафиксированным числом. Возврат старой формулы дал бы на этих
# рядах 0 или отрицательное значение, и тест упал бы на численном
# несовпадении — независимо от того, каким текстом написана реализация.


@pytest.mark.parametrize(
    "q_minus_d, expected_capacity, historical_value, why",
    [
        pytest.param(
            [0.004, 0.004, 0.004, -0.006], 0.006, -0.004,
            "min(Cumsum) = +0.004 > 0, поэтому -min даёт ОТРИЦАТЕЛЬНУю емкость; "
            "год 4 всё же не покрыт и требует (D-Q4)*T",
            id="negative_historical_value",
        ),
        pytest.param(
            [10.0, -10.0, 10.0, -10.0], 10.0, 0.0,
            "Cumsum = [10, 0, 10, 0], минимум 0 => -min = 0, но яма в 10 ед/с "
            "реальна: от пика 10 до следующего нуля",
            id="two_equal_valleys",
        ),
        pytest.param(
            [10.0, -10.0, 10.0], 10.0, 0.0,
            "переход через ноль: C = [0, 10, 0], -min = 0 при дефиците 10",
            id="crossing_zero",
        ),
        pytest.param(
            [30.0, 30.0, -10.0], 10.0, 0.0,
            "дефицит в последнем году: C = [0, 30, 60, 50], -min = 0",
            id="deficit_in_last_year",
        ),
        pytest.param(
            [-10.0, 30.0, -10.0, 30.0, -10.0], 20.0, 10.0,
            "net = +30: однопериодная просадка 10, но второй период сдвинут "
            "вверх на 30, и яма после пика достигает 20",
            id="positive_net_periodic_matters",
        ),
    ],
)
def test_capacity_is_not_negative_min_of_cumulative_balance(
    q_minus_d, expected_capacity, historical_value, why
) -> None:
    """Ёмкость не равна -min(cumsum(Q−D)): историческая формула неверна.

    Ожидаемые значения зафиксированы независимо, разбором ряда вручную;
    historical_value показывает, что вернула бы старая формула. Проверяется
    публикуемое число, а не исходный текст.
    """
    ripple = rr._ripple_mass_curve(np.asarray(q_minus_d, dtype=float))

    assert ripple["regulation_possible"] is True
    published = ripple["required_m3_s"]

    assert published == pytest.approx(expected_capacity, abs=1e-9), (
        f"ожидалась ёмкость {expected_capacity}, получено {published}. {why}"
    )
    assert abs(published - historical_value) > 1e-9, (
        f"ряд не различает формулы: обе дают {published}. {why}"
    )


def test_monotonic_growth_reports_zero_capacity_not_negative() -> None:
    """Ряд без единого дефицита даёт нулевую ёмкость, а не отрицательную.

    -min(cumsum) на монотонно растущем балансе строго отрицателен, то есть
    формула выдавала бы отрицательный объём при заведомо нулевой потребности.
    """
    ripple = rr._ripple_mass_curve(np.array([5.0, 15.0, 25.0]))

    assert ripple["net_balance_m3_s"] == pytest.approx(45.0)
    assert ripple["required_m3_s"] == pytest.approx(0.0, abs=1e-12)
    assert ripple["required_m3_s"] >= 0.0


# ----------------------------------------------------------------------
# P3. Физическая перекрёстная проверка: ёмкость против симуляции баланса
# ----------------------------------------------------------------------
def _min_capacity_by_simulation(q_minus_d, n_periods: int = 2) -> float:
    """Минимальная ёмкость без недобора, найденная ПОИСКОМ ПО САМОЙ ВЕЛИЧИНЕ.

    Оракул намеренно не повторяет production-формулу max_{i<j}(C_i - C_j):
    здесь V ищется делением отрезка пополам, пока посторонняя симуляция
    баланса (функция _simulate выше) не перестанет давать недобор. Это
    независимый путь к тому же ответу, а не проверка формулы её же кодом.

    ЕДИНИЦЫ. Аргумент и результат — в м³/с накопленного баланса, то есть
    ровно те же единицы, что у required_m3_s. Умножение на T_year здесь НЕ
    выполняется намеренно: так обе величины сравниваются напрямую.
    """
    delta = np.asarray(q_minus_d, dtype=float)
    seq = np.tile(delta, n_periods)

    # Допуск недобора масштабируется величиной самого ряда. Абсолютный допуск
    # здесь был бы груб: для ряда порядка 0.006 м³/с величина 1e-9 дала бы
    # относительную терпимость 1.7e-7 и бисекция остановилась бы заметно ниже
    # истинной ёмкости — то есть оракул врал бы из-за своей точности, а не
    # из-за ошибки production.
    scale = float(np.abs(seq).sum()) or 1.0
    tolerance = 1e-12 * scale

    def no_unmet(capacity: float) -> bool:
        return _simulate(seq, capacity, capacity)[2] <= tolerance

    hi = float(np.abs(seq).sum()) or 1.0
    for _ in range(64):
        if no_unmet(hi):
            break
        hi *= 2.0
    else:
        raise AssertionError("не удалось найти заведомо достаточную ёмкость")

    lo = 0.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if no_unmet(mid):
            hi = mid
        else:
            lo = mid
    return hi


@pytest.mark.parametrize(
    "q_minus_d, label",
    [
        pytest.param([20.0, 20.0, -10.0, -10.0], "net=+20, яма в конце", id="s1_positive_net"),
        pytest.param([30.0, -10.0, 30.0, 30.0], "net=+80, яма в середине", id="s2_valley_middle"),
        pytest.param([10.0, -10.0, 10.0, -10.0], "net=0, две одинаковые ямы", id="s3_two_valleys"),
        pytest.param([20.0, -20.0, 20.0, -20.0], "net=0, зеркальные ямы", id="s4_mirrored"),
        pytest.param([-10.0, 30.0, -10.0, 30.0, -10.0], "net=+30, три ямы", id="s5_three_valleys"),
        pytest.param([-70.0, 90.0, -70.0, 50.0], "CASE_A, net=0", id="case_a"),
        pytest.param([-70.0, 10.0, 30.0, 90.0], "CASE_B, net=+60", id="case_b"),
        pytest.param([0.004, 0.004, 0.004, -0.006], "аудит: net=+0.006", id="audit_control"),
    ],
)
def test_required_capacity_matches_physical_simulation(q_minus_d, label) -> None:
    """Ёмкость production совпадает с минимумом, найденным симуляцией баланса.

    Ряды покрывают разные конфигурации: положительный net, нулевой net,
    одиночную яму, несколько ям, ряды с масштабом порядка 1 и 0.004 м³/с.
    Oracle (_min_capacity_by_simulation) не обращается к production-формуле
    расчёта дефицита — он ищет ёмкость бисекцией по условию нулевого
    недобора в посторонней симуляции.
    """
    ripple = rr._ripple_mass_curve(np.asarray(q_minus_d, dtype=float))
    published = ripple["required_m3_s"]
    simulated = _min_capacity_by_simulation(q_minus_d, n_periods=2)

    assert ripple["regulation_possible"] is True, label
    assert published == pytest.approx(simulated, rel=1e-9, abs=1e-12), (
        f"{label}: production {published} против симуляции {simulated} м³/с"
    )


# ----------------------------------------------------------------------
# P4. net > 0: однопериодная и двухпериодная просадка различаются
# ----------------------------------------------------------------------
def test_positive_net_two_period_drawdown_exceeds_one_period() -> None:
    """При net > 0 периодическое продолжение даёт БОЛЬШУЮ ёмкость.

    Ряд [−10, +30, −10, +30, −10], net = +30. Кумулятивная кривая
    C = [0, −10, 20, 10, 40, 30].

    Один период: пары i<j дают максимум 40 − 30 = 10 (пик конца периода и
    следующая за ним яма). Два периода: кривая повторяется со сдвигом вверх
    на net = 30, то есть [30, 20, 50, 40, 70, 60]. Теперь пик 40 (конец
    первого периода) и яма 20 (начало второго) дают 40 − 20 = 20. Поэтому
    ёмкость 20, а не 10.

    Именно эта разница отличает периодический расчёт от однократного: при
    net = 0 оба дают одно число (тест test_3_period_drawdown_... на этом и
    построен), поэтому случай net > 0 — единственный, где видна разница.
    """
    q_minus_d = np.array([-10.0, 30.0, -10.0, 30.0, -10.0])
    assert q_minus_d.sum() == pytest.approx(30.0), "net должен быть положительным"

    # Независимая опора: перебор всех пар, без production-функции.
    cumulative = np.concatenate([[0.0], np.cumsum(q_minus_d)])

    def exhaustive(extended: np.ndarray) -> float:
        best = 0.0
        for i in range(len(extended)):
            for j in range(i + 1, len(extended)):
                best = max(best, float(extended[i] - extended[j]))
        return best

    net = float(cumulative[-1])
    one_period = exhaustive(cumulative)
    two_period = exhaustive(np.concatenate([cumulative, cumulative + net]))

    assert one_period == pytest.approx(10.0), "однопериодная просадка"
    assert two_period == pytest.approx(20.0), "двухпериодная просадка"
    assert two_period > one_period, "периодическое продолжение обязано давать больше"

    ripple = rr._ripple_mass_curve(q_minus_d)
    assert ripple["within_period_m3_s"] == pytest.approx(one_period)
    assert ripple["required_m3_s"] == pytest.approx(two_period), (
        "required_m3_s обязан быть двухпериодным, а не однопериодным"
    )
    assert ripple["required_m3_s"] > ripple["within_period_m3_s"]

    # Трёхпериодное продолжение при net > 0 обязано совпасть с двухпериодным:
    # дальше кривая только поднимается, новых ям глубже не появляется.
    assert ripple["three_period_m3_s"] == pytest.approx(
        ripple["required_m3_s"], abs=1e-9
    )
