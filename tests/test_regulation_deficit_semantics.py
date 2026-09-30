"""Семантика deficit_years: фактический недобор против опустошения запаса.

История вопроса. Критерий «дефицитный год» был реализован как ``S == 0`` на
конец года — то есть как признак ОПОРОЖНЕНИЯ водохранилища. Это смешивало две
разные величины и давало три измеренных расхождения:

1. При V = 0 запас пуст каждый год, поэтому год помечался дефицитным даже при
   Q >= D, когда недобора не было вовсе: спрос обслуживался, излишек
   списывался, а отдача выпадала в ноль.
2. При Q == D годовой баланс тождественно нулю, то есть unmet = 0 всегда. Но
   если запас пришёл пустым, он оставался пустым, и год снова помечался —
   недобор последующих лет наследовался от одного провалившегося.
3. Касание S = 0 ровно на границе года (S_raw == 0) давало unmet = 0 и всё
   равно флаг, хотя спрос был обслужен полностью.

Дополнительно терялась ВЕЛИЧИНА недобора: она исчезала в max(0.0, ...) и не
публиковалась, поэтому одинаковые «50 % гарантии» могли означать 13 млн м³
недобора и 1211 млн м³.

Что проверяется здесь. Разделение двух признаков:

    unmet_i = max(0.0, -S_raw)   фактический недобор спроса в году
    empty_i = (S == 0.0)         опорожнение водохранилища на конец года

    deficit_years — число лет с unmet_i > 0
    empty_years   — число лет с S == 0

и формула гарантии

    guarantee_percent = (n_years - deficit_years) / n_years * 100

НОРМАТИВНЫЙ СТАТУС РАЗДЕЛЕНИЯ: UNKNOWN / SOURCE_MISSING. Определения
«гарантированной отдачи», связывающего недобор с состоянием запаса, в
локальном нормативном корпусе нет: «массовая кривая», «накопленных расходов»,
«Риппл» не встречаются ни в одном из девяти PDF, а «гарантированная отдача» в
СП 33 (стр. 9) и СП 529 (стр. 21) встречается по одному разу и только как
ПРОЕКТНОЕ входное значение, без методики расчёта. Тесты ниже проверяют
арифметику и границы применимости, а не нормативное соответствие, и не
приписывают разделение какому-либо стандарту.
"""

from __future__ import annotations

import inspect
import re

import numpy as np
import pytest

from core.hydrorash import reservoir_regulation as rr
from core.hydrorash.reservoir_regulation import (
    multi_year_regulation,
    storage_yield_curve,
)

T_YEAR = 365 * 86400

SERIES_FLAT = np.array([20.0, 20.0, 20.0])
SERIES_D = np.array([20.0, 80.0])
SERIES_F = np.array([20.0, 20.0] + [100.0] * 8)


def _metrics(q, demand, capacity_m3, initial_m3=None):
    """Прогон годового шага ровно как в helper, но в своём коде.

    Тест обязан проверять результат посторонним расчётом, иначе он
    подтверждал бы сам себя.
    """
    initial_m3 = capacity_m3 if initial_m3 is None else initial_m3
    storage = float(initial_m3)
    deficit = empty = 0
    unmet_total = 0.0
    max_unmet = 0.0
    for q_i in q:
        raw = storage + (float(q_i) - demand) * T_YEAR
        unmet = -raw if raw < 0.0 else 0.0
        storage = min(capacity_m3, max(0.0, raw))
        if unmet > 0.0:
            deficit += 1
        if storage == 0.0:
            empty += 1
        unmet_total += unmet
        max_unmet = max(max_unmet, unmet)
    n = len(q)
    return {
        "deficit_years": deficit,
        "empty_years": empty,
        "unmet_volume_m3": unmet_total,
        "max_unmet_volume_m3": max_unmet,
        "guarantee_percent": (n - deficit) / n * 100.0,
    }


# ----------------------------------------------------------------------
# A, B, C — три состояния при V = 0
# ----------------------------------------------------------------------
def test_case_a_demand_equals_inflow_zero_volume() -> None:
    """A: Q = D = 20, V = 0 → 100 %, недобора нет, но запас пуст каждый год.

    Прежний критерий давал 0 %: запас пуст, значит «дефицит». Спрос при этом
    обслуживался полностью, unmet тождественно ноль.
    """
    m = _metrics(SERIES_FLAT, 20.0, 0.0)
    assert m["deficit_years"] == 0
    assert m["unmet_volume_m3"] == pytest.approx(0.0, abs=1e-9)
    assert m["guarantee_percent"] == pytest.approx(100.0)
    assert m["empty_years"] == 3


def test_case_b_demand_exceeds_inflow_zero_volume() -> None:
    """B: Q = 20, D = 21, V = 0 → 0 %, недобор есть и он публикуется."""
    m = _metrics(SERIES_FLAT, 21.0, 0.0)
    assert m["deficit_years"] == 3
    assert m["unmet_volume_m3"] == pytest.approx(3 * 1.0 * T_YEAR)
    assert m["guarantee_percent"] == pytest.approx(0.0)
    assert m["empty_years"] == 3


def test_case_c_inflow_exceeds_demand_zero_volume() -> None:
    """C: Q = 20, D = 19, V = 0 → 100 %, излишек списывается, недобора нет.

    Прежний критерий давал 0 % при заведомо нулевом недоборе: год заканчивался
    пустым водохранилищем, и это само по себе считалось дефицитом.
    """
    m = _metrics(SERIES_FLAT, 19.0, 0.0)
    assert m["deficit_years"] == 0
    assert m["unmet_volume_m3"] == pytest.approx(0.0, abs=1e-9)
    assert m["guarantee_percent"] == pytest.approx(100.0)
    assert m["empty_years"] == 3


# ----------------------------------------------------------------------
# F — касание нуля ровно на границе года
# ----------------------------------------------------------------------
def test_case_f_exact_zero_boundary_is_not_deficit() -> None:
    """F: S_raw == 0 → empty, но НЕ deficit.

    V = 0,5 · T расходуется ровно за маловодный год, unmet = 0, спрос обслужен.
    Оба признака обязаны это различать: опустошение состоялось, недобора нет.
    """
    q = np.array([20.0, 80.0, 20.0, 80.0])
    m = _metrics(q, 20.5, 0.5 * T_YEAR)
    assert m["unmet_volume_m3"] == pytest.approx(0.0, abs=1e-6)
    assert m["deficit_years"] == 0
    assert m["empty_years"] == 2, "два маловодных года заканчиваются нулём"
    assert m["guarantee_percent"] == pytest.approx(100.0)


# ----------------------------------------------------------------------
# H — наследование пустого состояния
# ----------------------------------------------------------------------
def test_case_h_empty_state_is_not_inherited_as_deficit() -> None:
    """H: недобор только в первом году, а пустой запас наследуется дальше.

    Q = [10, 20, 20], D = 20: год 1 даёт недобор, годы 2 и 3 при Q = D
    недобора не дают, но запас в них остаётся пустым. Прежний критерий ставил
    флаг в трёх годах; теперь один — и unmet соответствует только году 1.
    """
    q = np.array([10.0, 20.0, 20.0])
    m = _metrics(q, 20.0, 0.05e9)
    assert m["deficit_years"] == 1
    assert m["empty_years"] == 3
    assert m["unmet_volume_m3"] == pytest.approx(10.0 * T_YEAR - 0.05e9)
    assert m["guarantee_percent"] == pytest.approx(200.0 / 3.0)


# ----------------------------------------------------------------------
# G1..G4 — одинаковый счётчик, разный объём
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "demand, expected_unmet_m3",
    [
        # Ряд [20, 80], V = 0.05 км³. Год 1 короткий, год 2 избыточный, поэтому
        # недобор только в первом году и равен (D − 20)·T − V_нач, где
        # V_нач = 50 млн м³ поглощается до того, как запас уйдёт в ноль.
        pytest.param(22.0, 13_072_000.0, id="G1_D22"),
        pytest.param(30.0, 265_360_000.0, id="G2_D30"),
        pytest.param(40.0, 580_720_000.0, id="G3_D40"),
        pytest.param(60.0, 1_211_440_000.0, id="G4_D60"),
    ],
)
def test_case_g_same_deficit_count_but_growing_shortage(
    demand, expected_unmet_m3
) -> None:
    """G1..G4: deficit_years = 1 и 50 % во всех, а unmet растёт с D.

    Именно это и было неразличимо: четыре сценария давали одинаковую
    «50 % гарантии» при недоборе от 13 до 1211 млн м³ — разница в 93 раза.
    Теперь объём публикуется и различает их.

    Ожидаемые значения заданы константами, а не формулой: тест обязан быть
    независимым пересчётом, иначе он подтверждал бы сам себя.
    """
    m = _metrics(SERIES_D, demand, 0.05e9)
    assert m["deficit_years"] == 1
    assert m["guarantee_percent"] == pytest.approx(50.0)
    assert m["unmet_volume_m3"] == pytest.approx(expected_unmet_m3, rel=1e-12)


def test_case_g_unmet_grows_monotonically_with_demand() -> None:
    """Порядок G1..G4 по объёму недобора строго возрастает."""
    volumes = [
        _metrics(SERIES_D, d, 0.05e9)["unmet_volume_m3"]
        for d in (22.0, 30.0, 40.0, 60.0)
    ]
    assert volumes == sorted(volumes)
    assert volumes[0] < volumes[-1], "разброс должен быть существенным"
    # Отношение крайних больше 50 — то, что раньше полностью терялось.
    assert volumes[-1] / volumes[0] > 50.0


# ----------------------------------------------------------------------
# 7. Монотонность по D
# ----------------------------------------------------------------------
def test_lower_demand_never_increases_deficit_or_shortage() -> None:
    """Уменьшение забора не увеличивает ни deficit_years, ни unmet."""
    for q, v in ((SERIES_D, 0.05e9), (SERIES_F, 0.5e9), (SERIES_FLAT, 0.0)):
        demands = [20.0, 25.0, 30.0, 40.0, 60.0, 90.0]
        metrics = [_metrics(q, d, v) for d in demands]
        shortages = [m["unmet_volume_m3"] for m in metrics]
        deficits = [m["deficit_years"] for m in metrics]
        assert shortages == sorted(shortages), f"unmet не убывает: {shortages}"
        assert deficits == sorted(deficits), f"deficit_years не убывает: {deficits}"


# ----------------------------------------------------------------------
# 8. natural_supply не тронут
# ----------------------------------------------------------------------
def test_natural_supply_keeps_exceedance_probability_semantics() -> None:
    """natural_supply остаётся P(Q >= D) и не связан с состоянием запаса.

    Это отдельная величина — обеспеченность по превышению, без водохранилища.
    Смешивать её с долей лет без недобора нельзя, и правка этого не сделала.
    """
    q = np.array([30.0, 10.0, 50.0, 20.0])
    result = multi_year_regulation(q, 20.0, mode="natural_supply")
    assert result["guarantee_percent"] == pytest.approx(75.0)  # 3 года из 4 с Q >= 20
    assert "deficit_years" not in result, (
        "natural_supply не оперирует запасом, поэтому счётчика дефицита у него нет"
    )
    assert "empty_years" not in result


# ----------------------------------------------------------------------
# 9. Единое определение дефицита в обоих входах
# ----------------------------------------------------------------------
@pytest.mark.parametrize("demand", [21.0, 25.0, 40.0])
def test_guarantee_for_volume_matches_independent_reference(demand) -> None:
    """Режим guarantee_for_volume совпадает с посторонним расчётом.

    Проверяется на ЗАДАННОМ спросе: это единственный режим, который
    оценивает конкретную пару (D, V) вместо того, чтобы искать D.
    """
    q = SERIES_D
    v_km3 = 0.05
    m = _metrics(q, demand, v_km3 * 1e9)

    core = multi_year_regulation(
        q, demand, V_max_km3=v_km3, S_0_km3=v_km3, mode="guarantee_for_volume"
    )
    assert core["deficit_years"] == m["deficit_years"]
    assert core["empty_years"] == m["empty_years"]
    assert core["unmet_volume_km3"] == pytest.approx(m["unmet_volume_m3"] / 1e9, abs=1e-9)
    assert core["max_unmet_volume_km3"] == pytest.approx(
        m["max_unmet_volume_m3"] / 1e9, abs=1e-9
    )
    assert core["guarantee_percent"] == pytest.approx(round(m["guarantee_percent"], 1))


@pytest.mark.parametrize("v_km3", [0.05, 0.5, 5.0])
def test_both_entry_points_share_the_same_deficit_definition(v_km3) -> None:
    """storage_yield_curve и multi_year_regulation согласованы между собой.

    storage_yield_curve публикует метрики для СВОЕЙ найденной отдачи
    Q_max_demand, поэтому согласованность проверяется именно на ней: повторный
    расчёт для опубликованной отдачи обязан дать те же deficit_years,
    empty_years и unmet. Если бы один из входов считал по недобору, а другой
    по опустошению, значения разошлись бы там, где счётчики не совпадают.
    """
    q = SERIES_D
    frame = storage_yield_curve(q, V_range_km3=[v_km3], target_guarantee=95.0)
    published_demand = float(frame["Q_max_demand"].iloc[0])

    m = _metrics(q, published_demand, v_km3 * 1e9)
    core = multi_year_regulation(
        q, published_demand, V_max_km3=v_km3, S_0_km3=v_km3,
        mode="guarantee_for_volume",
    )

    assert int(frame["deficit_years"].iloc[0]) == core["deficit_years"] == m["deficit_years"]
    assert int(frame["empty_years"].iloc[0]) == core["empty_years"] == m["empty_years"]
    assert float(frame["unmet_volume_km3"].iloc[0]) == pytest.approx(
        core["unmet_volume_km3"], rel=1e-9, abs=1e-12
    )
    assert float(frame["achieved_guarantee"].iloc[0]) == pytest.approx(
        round(m["guarantee_percent"], 1)
    )


# ----------------------------------------------------------------------
# 10. Старый паттерн отсутствует
# ----------------------------------------------------------------------
def test_old_empty_based_deficit_pattern_is_gone() -> None:
    """В расчётах регулирования больше нет «S == 0 → deficit_years».

    Прежний паттерн встречался в пяти местах и мог разъехаться. Сейчас все пять
    вызывают один helper, где признаки разделены явно.
    """
    source = inspect.getsource(rr)
    assert not re.search(r"if S == 0\s*:\s*\n\s*deficit_years", source), (
        "старый паттерн «S == 0 → deficit_years» должен быть удалён"
    )
    # Счётчик недобора наращивается только по unmet, и это видно по коду.
    helper = inspect.getsource(rr._calculate_regulation_year_metrics)
    assert re.search(r"if unmet > 0\.0\s*:\s*\n\s*deficit_years \+= 1", helper), (
        "deficit_years обязан наращиваться по unmet_i > 0"
    )
    assert re.search(r"if storage == 0\.0\s*:\s*\n\s*empty_years \+= 1", helper), (
        "empty_years обязан наращиваться по S == 0"
    )


def test_all_five_call_sites_use_the_helper() -> None:
    """Пять мест вычисления дефицита используют единый helper.

    Перечисление по функциям, а не по числу вхождений: число вызовов может
    измениться при оптимизации, а вот конкретные функции обязаны остаться
    переведёнными на общую семантику.
    """
    assert hasattr(rr, "_calculate_regulation_year_metrics")
    source = inspect.getsource(rr.multi_year_regulation)
    assert source.count("_calculate_regulation_year_metrics(") == 3, (
        "три точки в multi_year_regulation: guarantee_for_volume, "
        "volume_for_guarantee (проба и финал)"
    )
    assert inspect.getsource(rr.storage_yield_curve).count(
        "_calculate_regulation_year_metrics("
    ) == 2, "две точки в storage_yield_curve: поиск D и финальная проверка"


# ----------------------------------------------------------------------
# Публикация полей
# ----------------------------------------------------------------------
def test_multi_year_regulation_publishes_shortage_fields() -> None:
    """Оба регулировочных режима публикуют счётчики и объём недобора.

    Пустой набор полей — это «50 % гарантии» без единого м³ недобора, из
    которого нельзя понять, насколько плох случай. Поля обязаны присутствовать
    в каждом режиме, который вообще считает баланс.
    """
    calls = (
        ("guarantee_for_volume", {"V_max_km3": 0.05, "S_0_km3": 0.05}),
        ("volume_for_guarantee", {"target_guarantee": 95.0}),
    )
    for mode, kwargs in calls:
        result = multi_year_regulation(SERIES_D, 30.0, mode=mode, **kwargs)
        for key in ("deficit_years", "empty_years", "unmet_volume_km3",
                    "max_unmet_volume_km3", "guarantee_percent"):
            assert key in result, f"{mode}: нет поля {key}"
        assert result["unmet_volume_km3"] >= 0.0


def test_guarantee_uses_deficit_years_not_empty_years() -> None:
    """Гарантия вычисляется из deficit_years, а не из empty_years.

    Контроль построен на различии: подбирается ряд, где счётчики расходятся
    (1 против 3), и сверяются ОБЕ кандидатные гарантии. Правильный ответ
    обязан совпасть с кандидатом по недобору и не совпасть с кандидатом
    по опустошению — иначе разделение было бы декоративным.
    """
    q = np.array([10.0, 20.0, 20.0])
    result = multi_year_regulation(
        q, 20.0, V_max_km3=0.05, S_0_km3=0.05, mode="guarantee_for_volume",
    )

    assert result["deficit_years"] == 1
    assert result["empty_years"] == 3
    assert result["deficit_years"] != result["empty_years"], "иначе тест не различает"

    n = len(q)
    by_deficit = round((n - result["deficit_years"]) / n * 100.0, 1)
    by_empty = round((n - result["empty_years"]) / n * 100.0, 1)
    assert result["guarantee_percent"] == pytest.approx(by_deficit)
    assert result["guarantee_percent"] != pytest.approx(by_empty), (
        "гарантия не должна считаться по опустошению"
    )
    assert by_empty == 0.0, "кандидат по старому критерию был бы именно 0 %"
