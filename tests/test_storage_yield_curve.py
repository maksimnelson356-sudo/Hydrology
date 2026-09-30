"""storage_yield_curve: согласованность публикуемой пары и удаление мёртвого вызова.

История файла. Аудит функции выявил два дефекта, и оба исправлены здесь
не изменением методологии, а приведением вывода в соответствие с расчётом.

1. Пара (Q_max_demand, achieved_guarantee) была противоречивой. Отдача
   печаталась как round(best_D, 2), а гарантия считалась на неокруглённом
   best_D. При округлении вверх колонка achieved_guarantee показывала 100 %
   для значения, которое гарантию нарушало: для ряда [20, 80] × 10 при
   V = 0,05 км³ истинный максимум отдачи 21,5854896 м³/с печатался как 21,59,
   при котором дефицитны 10 лет из 20 и не покрыто 1,42 · 10⁶ м³. Теперь
   отдача округляется консервативно, вниз, ДО финальной проверки, и
   публикуемое значение совпадает с проверяемым.

2. В начале тела цикла вызывался multi_year_regulation в режиме
   volume_for_guarantee, результат записывался в best_demand и нигде не
   читался. Влияния на результат не было (проверено численно), но вызов
   стоил около 278 % лишнего времени, а обёртка
   `except (ValueError, KeyError): pass` молча проглатывала бы любое будущее
   исключение внутри многофункционального расчёта. Вызов удалён.

ЧТО ЗДЕСЬ НЕ МЕНЯЕТСЯ. Критерий «deficit_years растёт только при S == 0»
остаётся прежним, и его следствие при V_km3 = 0 — Q_max_demand = 0, хотя
приток без хранения гарантирует min(Q) — зафиксировано тестом как
существующее поведение, а не «исправлено». Нормативный статус функции
остаётся UNKNOWN: численной формулы «объём — гарантированная отдача» в
локальном нормативном корпусе нет (SOURCE_MISSING), и тесты ниже не
приписывают функции какой-либо стандарт.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.hydrorash import reservoir_regulation as rr
from core.hydrorash.reservoir_regulation import storage_yield_curve

T_YEAR = 365 * 86400

SERIES_D = np.array([20.0, 80.0] * 10)                    # Q_mean = 50
SERIES_F = np.array([20.0, 20.0] + [100.0] * 8)           # Q_mean = 84
SERIES_CONST = np.full(20, 50.0)                          # Q_mean = 50


def _simulate(q: np.ndarray, demand: float, v_max_m3: float) -> tuple[float, int, float]:
    """Пересчёт баланса СВОИМ кодом: (гарантия %, deficit_years, unmet м³).

    Намеренно не вызовом функции модуля: тест обязан проверять опубликованное
    значение посторонним расчётом, иначе он подтверждал бы сам себя.
    Критерий deficit_years воспроизводится буквально — «S == 0 на конец года».
    """
    S = v_max_m3
    deficit_years = 0
    unmet = 0.0
    for q_i in q:
        raw = S + (q_i - demand) * T_YEAR
        if raw < 0.0:
            unmet += -raw
        S = min(v_max_m3, max(0.0, raw))
        if S == 0.0:
            deficit_years += 1
    n = len(q)
    return (n - deficit_years) / n * 100, deficit_years, unmet


# ----------------------------------------------------------------------
# A. Согласованность опубликованной пары
# ----------------------------------------------------------------------
def test_published_demand_reproduces_the_published_guarantee() -> None:
    """Гарантия должна соответствовать ИМЕННО опубликованной отдаче.

    Раньше отдача округлялась вверх, и колонка achieved_guarantee сертифицировала
    неопубликованное значение. Проверка идёт по опубликованным числам, без
    обращения к внутреннему состоянию функции.
    """
    frame = storage_yield_curve(SERIES_D, V_range_km3=[0.05], target_guarantee=95.0)
    demand = float(frame["Q_max_demand"].iloc[0])
    stated = float(frame["achieved_guarantee"].iloc[0])
    v_m3 = 0.05 * 1e9

    guarantee, deficit_years, _ = _simulate(SERIES_D, demand, v_m3)
    assert guarantee == pytest.approx(stated, abs=0.05), (
        f"заявлено {stated}%, при опубликованной отдаче {demand} получается {guarantee}%"
    )
    assert deficit_years == 0, "при заявленной отдаче не должно быть дефицитных лет"


# ----------------------------------------------------------------------
# B, C. Золотые случаи из аудита
# ----------------------------------------------------------------------
def test_golden_series_d_small_volume() -> None:
    """[20, 80] × 10, V = 0,05 км³: отдача 21,58 м³/с, непокрытого стока нет.

    До правки печаталось 21,59 — округление вверх на 0,0045 м³/с, чего
    хватало, чтобы десять маловодных лет стали дефицитными.
    """
    frame = storage_yield_curve(SERIES_D, V_range_km3=[0.05], target_guarantee=95.0)
    demand = float(frame["Q_max_demand"].iloc[0])

    assert demand == pytest.approx(21.58, abs=1e-9)
    _, deficit_years, unmet = _simulate(SERIES_D, demand, 0.05 * 1e9)
    assert unmet == pytest.approx(0.0, abs=1e-6)
    assert deficit_years == 0


def test_golden_series_f_medium_volume() -> None:
    """[20, 20, 100 × 8], V = 0,5 км³: отдача 27,92 м³/с, непокрытого стока нет.

    До правки печаталось 27,93, что давало один дефицитный год при
    одновременно заявленной гарантии 100 %.
    """
    frame = storage_yield_curve(SERIES_F, V_range_km3=[0.5], target_guarantee=95.0)
    demand = float(frame["Q_max_demand"].iloc[0])

    assert demand == pytest.approx(27.92, abs=1e-9)
    _, deficit_years, unmet = _simulate(SERIES_F, demand, 0.5 * 1e9)
    assert unmet == pytest.approx(0.0, abs=1e-6)
    assert deficit_years == 0


def test_demand_is_never_rounded_upwards() -> None:
    """Округление вниз: опубликованная отдача не превышает проверенную.

    Сравнивается с максимальной отдачей, найденной собственным бинарным
    поиском по тому же критерию. Разница допускается в пределах шага поиска
    1e-3 м³/с плюс вес сотого разряда округления.
    """
    def max_verified_demand(q, v_m3, target=100.0):
        lo, hi = 0.0, float(np.mean(q))
        for _ in range(200):
            mid = (lo + hi) / 2
            guarantee, _, _ = _simulate(q, mid, v_m3)
            if guarantee >= target:
                lo = mid
            else:
                hi = mid
            if hi - lo < 1e-10:
                break
        return lo

    for q in (SERIES_D, SERIES_F):
        for v_km3 in (0.05, 0.1, 0.5, 1.0, 5.0):
            frame = storage_yield_curve(q, V_range_km3=[v_km3], target_guarantee=100.0)
            published = float(frame["Q_max_demand"].iloc[0])
            verified = max_verified_demand(q, v_km3 * 1e9)
            assert published <= verified + 1e-3, (
                f"отдача {published} превышает проверенный максимум {verified} "
                f"(ряд {q[:4].tolist()}…, V={v_km3})"
            )


# ----------------------------------------------------------------------
# D. Параметризованная проверка при target = 100 %
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "q, v_km3",
    [
        pytest.param(SERIES_D, 0.05, id="D_V005"),
        pytest.param(SERIES_D, 0.5, id="D_V05"),
        pytest.param(SERIES_D, 5.0, id="D_V5"),
        pytest.param(SERIES_F, 0.05, id="F_V005"),
        pytest.param(SERIES_F, 0.5, id="F_V05"),
        pytest.param(SERIES_F, 5.0, id="F_V5"),
    ],
)
def test_full_target_leaves_no_uncovered_shortage(q, v_km3) -> None:
    """При target = 100 % опубликованная отдача не создаёт непокрытого дефицита.

    Это и есть та величина, которую потребитель вычитывает из таблицы: спрос,
    который можно предъявить водохранилищу при данном объёме.
    """
    frame = storage_yield_curve(q, V_range_km3=[v_km3], target_guarantee=100.0)
    demand = float(frame["Q_max_demand"].iloc[0])

    guarantee, deficit_years, unmet = _simulate(q, demand, v_km3 * 1e9)
    assert unmet == pytest.approx(0.0, abs=1e-6), (
        f"при опубликованной отдаче {demand} не покрыто {unmet} м³"
    )
    assert guarantee == pytest.approx(100.0, abs=1e-9)
    assert deficit_years == 0


# ----------------------------------------------------------------------
# E, F. Монотонность и граница среднего притока
# ----------------------------------------------------------------------
def test_demand_is_monotone_in_volume() -> None:
    """Отдача не должна уменьшаться при росте объёма.

    Больший объём не может ухудшить условия: если отдача поддерживалась при
    меньшем V, она поддерживается и при большем.
    """
    volumes = [0.01, 0.05, 0.1, 0.3, 0.6, 1.0, 2.0, 5.0, 10.0]
    for q in (SERIES_D, SERIES_F, SERIES_CONST):
        frame = storage_yield_curve(q, V_range_km3=volumes, target_guarantee=95.0)
        demands = frame["Q_max_demand"].to_numpy()
        assert np.all(np.diff(demands) >= -1e-9), (
            f"монотонность нарушена: {demands.tolist()}"
        )


def test_demand_never_exceeds_mean_inflow() -> None:
    """Нельзя гарантировать отдачу больше среднего притока.

    Иначе водохранилище опустошается, и никакая ёмкость не помогает: столько
    воды в бассейне просто нет.
    """
    for q in (SERIES_D, SERIES_F, SERIES_CONST, np.arange(50.0, 90.0, 5.0)):
        frame = storage_yield_curve(q, V_range_km3=[0.05, 0.5, 5.0],
                                    target_guarantee=95.0)
        assert float(frame["Q_max_demand"].max()) <= float(np.mean(q)) + 1e-9


# ----------------------------------------------------------------------
# G. Постоянный ряд
# ----------------------------------------------------------------------
def test_constant_series_demand_equals_inflow_for_every_volume() -> None:
    """При Q_i = const отдача равна притоку при любом объёме, с точностью до
    консервативного округления.

    Хранить нечего и нечего покрывать: годовой баланс равен нулю при любой
    отдаче, равной притоку, и отрицателен при любой большей. Ёмкость на ответ
    не влияет.

    Точное равенство недостижимо и не ожидается: бинарный поиск подходит к
    Q_mean снизу, а округление вниз до сотых отбрасывает ещё до 0,01 м³/с.
    Поэтому проверяется, что ответ не превышает приток и отстаёт от него не
    более чем на вес округления.
    """
    for v_km3 in (0.01, 0.05, 0.5, 5.0, 50.0):
        frame = storage_yield_curve(SERIES_CONST, V_range_km3=[v_km3],
                                    target_guarantee=95.0)
        demand = float(frame["Q_max_demand"].iloc[0])
        assert demand <= 50.0 + 1e-9, "отдача не может превышать приток"
        assert demand == pytest.approx(50.0, abs=0.011), (
            f"отдача {demand} слишком далека от притока 50 при V={v_km3}"
        )
        assert float(frame["achieved_guarantee"].iloc[0]) == pytest.approx(100.0)


# ----------------------------------------------------------------------
# H. Мёртвый вызов удалён
# ----------------------------------------------------------------------
def test_storage_yield_curve_does_not_call_multi_year_regulation(monkeypatch) -> None:
    """Функция не должна вызывать multi_year_regulation ни разу.

    Раньше вызов выполнялся, результат писался в best_demand и не читался.
    Подмена на бросающую функцию — самая надёжная проверка: она ломает тест
    при любом постороннем вызове из storage_yield_curve, тогда как подмена
    на пустую функцию пропустила бы и лишний вызов, и его результат.
    """
    def forbidden(*args, **kwargs):
        raise AssertionError(
            "storage_yield_curve не должна вызывать multi_year_regulation"
        )

    monkeypatch.setattr(rr, "multi_year_regulation", forbidden)

    frame = storage_yield_curve(SERIES_D, V_range_km3=[0.05, 0.5, 5.0],
                                target_guarantee=95.0)
    assert len(frame) == 3
    assert float(frame["Q_max_demand"].max()) > 0.0


def test_best_demand_symbol_is_gone() -> None:
    """Мёртвая переменная best_demand удалена из исходника.

    Дополняет поведенческую проверку: переменная без использования — это
    ровно тот дефект, который удалён, и следы его не должны остаться.
    """
    import inspect

    source = inspect.getsource(rr.storage_yield_curve)
    assert "best_demand" not in source
    assert "multi_year_regulation" not in source


# ----------------------------------------------------------------------
# I. Существующий критерий зафиксирован
# ----------------------------------------------------------------------
def test_deficit_years_counts_exactly_empty_reservoir() -> None:
    """deficit_years растёт тогда и только тогда, когда S == 0 на конец года.

    Критерий зафиксирован как есть. Он строже «есть непокрытый сток»: год, в
    который запас опустошился ровно до нуля, считается дефицитным, хотя
    спрос был обслужен полностью. Смена критерия — отдельная задача, здесь
    он лишь закреплён тестом, чтобы правка была осознанной.

    Ёмкость подобрана так, чтобы запас касался нуля ТОЧНО: при D = 20,5 м³/с
    и V = 0,5 · T за каждый маловодный год расходуется ровно 0,5 · T, то есть
    S приходит к нулю, но никогда не уходит ниже. Непокрытого стока при этом
    нет ни в один год.
    """
    q = np.array([20.0, 80.0] * 4)
    demand = 20.5
    v_m3 = 0.5 * T_YEAR  # ровно расходуемое за маловодный год
    assert v_m3 / 1e9 == pytest.approx(0.015768, abs=1e-9)

    guarantee, deficit_years, unmet = _simulate(q, demand, v_m3)
    assert unmet == pytest.approx(0.0, abs=1e-6), "спрос обслужен полностью"
    assert deficit_years == 4, (
        "четыре маловодных года заканчиваются с S == 0 и по действующему "
        "критерию считаются дефицитными, хотя не покрытого стока нет"
    )
    assert guarantee == pytest.approx(50.0), "половина лет — «дефицитные»"


def test_zero_volume_behaviour_is_recorded_not_fixed() -> None:
    """При V = 0 функция выдаёт 0 — это свойство критерия, а не округления.

    При нулевой ёмкости запас пуст каждый год, поэтому все годы считаются
    дефицитными и поиск возвращает нулевую отдачу, хотя приток без хранения
    гарантирует min(Q). Поведение оставлено как есть по прямому указанию не
    менять deficit_years; тест фиксирует его, чтобы будущая правка критерия
    была заметна, а не случайна.
    """
    frame = storage_yield_curve(SERIES_D, V_range_km3=[0.0], target_guarantee=95.0)
    assert float(frame["Q_max_demand"].iloc[0]) == 0.0

    # Для сравнения: любая ненулевая ёмкость уже даёт min(Q) с точностью до
    # консервативного округления вниз.
    nonzero = storage_yield_curve(SERIES_D, V_range_km3=[1e-6],
                                   target_guarantee=95.0)
    demand = float(nonzero["Q_max_demand"].iloc[0])
    assert demand <= float(np.min(SERIES_D)) + 1e-9
    assert demand == pytest.approx(float(np.min(SERIES_D)), abs=0.011)


# ----------------------------------------------------------------------
# Контракт вывода
# ----------------------------------------------------------------------
def test_output_columns_and_inputs_unchanged() -> None:
    """Сигнатура, входы и названия столбцов не менялись.

    Результат читает потребитель `handle_storage_yield`, поэтому переименование
    столбца или их состава сломало бы выгрузку в .hsp и инженерный отчёт.
    """
    import inspect

    signature = inspect.signature(rr.storage_yield_curve)
    assert list(signature.parameters) == [
        "Q_annual", "V_range_km3", "target_guarantee"
    ]

    frame = storage_yield_curve(SERIES_D, V_range_km3=[0.5], target_guarantee=95.0)
    assert list(frame.columns) == [
        "V_km3", "Q_max_demand", "achieved_guarantee", "target_guarantee"
    ]
    assert len(frame) == 1
    assert float(frame["target_guarantee"].iloc[0]) == 95.0


def test_normative_status_stays_unknown() -> None:
    """Нормативный статус остаётся UNKNOWN, приписывать стандарт нельзя.

    Численной формулы «объём — гарантированная отдача» в локальном корпусе
    нет, поэтому правка не должна и не может повысить статус функции.
    """
    doc = inspect_doc(rr.storage_yield_curve)
    assert "UNKNOWN" in doc
    assert "SOURCE_MISSING" in doc
    for claim in ("соответствует СП 33", "соответствует СП 529",
                  "реализует СП 529", "по СП 529 п.", "по СП 33 п."):
        assert claim not in doc, f"недопустимая атрибуция: {claim!r}"


def inspect_doc(func) -> str:
    import inspect

    return inspect.getdoc(func) or ""
