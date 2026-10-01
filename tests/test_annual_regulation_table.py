"""annual_regulation_table: входной контракт и арифметика накопительного счётчика.

ЧТО ЭТОТ ФАЙЛ НЕ ПРОВЕРЯЕТ. annual_regulation_table НЕ является моделью
физического запаса водохранилища. В ней нет S_0, клампинга по V_useful,
сброса и недобора, и её собственная документация это объявляет. Поэтому
здесь НЕТ утверждений вида «V_баланс не выходит за 0…V_useful» или
«Заполнен_% лежит в 0…100» — таких инвариантов у накопительного счётчика
нет, и их введение означало бы смену методики.

ЧТО ПРОВЕРЯЕТСЯ. Ровно заявленный контракт функции:
  1. размерность dV = (Q_in − Q_out) · дней · 86400 / 1e9 [км³];
  2. календарные длины месяцев (перечень, а не «30 сут»);
  3. V_баланс_km3 есть cumulative sum от dV_km3, а не уровень запаса;
  4. входной контракт: ровно 12 значений, без NaN, неотрицательные
     расходы, полезный объём положителен;
  5. публичный выход: шесть существующих колонок и 12 строк.

Ожидания выведены арифметически из формулы, указанной в docstring функции,
то есть проверка НЕ переписывает тело функции и не зависит от него.

Нормативный статус функции остаётся UNKNOWN / CONFLICT: численной формулы
«объём — гарантированная отдача» в локальном корпусе нет, и тесты ниже не
приписывают функции какой-либо стандарт.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.hydrorash import reservoir_regulation as rr
from core.hydrorash.reservoir_regulation import annual_regulation_table

SEC_PER_DAY = 86400.0

# Календарный перечень, зафиксированный в теле функции. Сумма ровно 365 сут.
CALENDAR_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

EXPECTED_COLUMNS = [
    "Месяц",
    "Q_приток",
    "Q_забор",
    "dV_km3",
    "V_баланс_km3",
    "Заполнен_%",
]

# Публичные поля округляются: dV и V_баланс — до 4 знаков, Заполнен_% — до 1.
# Допуски ниже это учитывают и ничего не ослабляют по существу.
TOL_DV = 1e-4
TOL_CUMULATIVE = 2e-4
TOL_PERCENT = 0.05


def _frame(q, demand: float = 20.0, v_useful: float = 1.0):
    return annual_regulation_table(np.asarray(q, dtype=float), demand, v_useful)


# ----------------------------------------------------------------------
# A, B. Размерность и календарные длины
# ----------------------------------------------------------------------
def test_first_month_dimension_matches_formula() -> None:
    """dV января = (Q_in − Q_out) · 31 сут · 86400 / 1e9 [км³].

    Проверка размера: (м³/с) · сут · с/сут = м³, / 1e9 = км³.
    """
    frame = _frame([30.0] * 12, demand=20.0)

    expected = (30.0 - 20.0) * 31 * SEC_PER_DAY / 1e9
    assert expected == pytest.approx(0.026784, abs=1e-6)
    assert float(frame["dV_km3"].iloc[0]) == pytest.approx(expected, abs=TOL_DV)


def test_annual_total_uses_365_days() -> None:
    """Итог за год = (Q_in − Q_out) · 365 сут · 86400 / 1e9.

    Сумма календарного перечня равна ровно 365 сут, поэтому итог не зависит
    от того, в каком месяце стоит избыток.
    """
    frame = _frame([30.0] * 12, demand=20.0)

    expected = (30.0 - 20.0) * 365 * SEC_PER_DAY / 1e9
    assert float(frame["V_баланс_km3"].iloc[-1]) == pytest.approx(
        expected, abs=TOL_DV
    )


def test_month_lengths_are_calendar_not_fixed_thirty() -> None:
    """Длины месяцев календарные: 31/28/31/30/..., а не 30 и не 365/12.

    Каждый месяц проверяется отдельно — это и фиксирует сам перечень.
    """
    frame = _frame([0.0] * 12, demand=1.0, v_useful=1.0)

    for month_index, days in enumerate(CALENDAR_DAYS):
        expected = -1.0 * days * SEC_PER_DAY / 1e9
        assert float(frame["dV_km3"].iloc[month_index]) == pytest.approx(
            expected, abs=TOL_DV
        ), f"месяц {month_index + 1}: длины не совпали"

    total = -365 * SEC_PER_DAY / 1e9
    assert float(frame["dV_km3"].sum()) == pytest.approx(total, abs=1e-3)


# ----------------------------------------------------------------------
# C. Накопительная семантика
# ----------------------------------------------------------------------
def test_balance_column_is_cumulative_sum_of_dv() -> None:
    """V_баланс_km3 — накопленная сумма dV, а НЕ уровень запаса.

    Закрепляется именно существующая семантика. Собственный oracle водохранилища
    здесь не строится намеренно: функция не моделирует запас, и такой oracle
    проверял бы другую методику.
    """
    q = [40.0, 10.0, 25.0, 5.0, 60.0, 35.0, 12.0, 48.0, 20.0, 7.0, 33.0, 18.0]
    frame = _frame(q, demand=25.0)

    dV = frame["dV_km3"].to_numpy()
    cumulative = frame["V_баланс_km3"].to_numpy()
    assert len(frame) == 12

    for i in range(12):
        expected = float(dV[: i + 1].sum())
        assert cumulative[i] == pytest.approx(expected, abs=TOL_CUMULATIVE), (
            f"месяц {i + 1}: накопленная сумма не сходится"
        )


# ----------------------------------------------------------------------
# D. Ровно 12 месяцев
# ----------------------------------------------------------------------
def test_twelve_months_are_accepted() -> None:
    """Ровно 12 значений — штатный случай, отказа быть не должно."""
    frame = _frame([30.0] * 12, demand=20.0)

    assert len(frame) == 12


@pytest.mark.parametrize(
    "q, expected_len",
    [
        pytest.param([30.0] * 11, 11, id="eleven"),
        pytest.param([30.0] * 13, 13, id="thirteen"),
        pytest.param([], 0, id="empty"),
        pytest.param([30.0], 1, id="single"),
    ],
)
def test_wrong_month_count_is_rejected(q, expected_len) -> None:
    """Ряд произвольной длины отвергается, а не дополняется нулём.

    До фикса короткий ряд молча получал нулевой приток за недостающие
    месяцы, из-за чего пропуск данных становился неотличим от Q = 0.
    """
    with pytest.raises(ValueError, match="12 месячных расходов"):
        annual_regulation_table(np.asarray(q, dtype=float), 20.0, 1.0)


# ----------------------------------------------------------------------
# E. NaN отвергается, а не подменяется нулём
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "q",
    [
        pytest.param([30.0] * 11 + [float("nan")], id="one_nan"),
        pytest.param([30.0] * 9 + [float("nan")] * 3, id="three_nan"),
        pytest.param([float("nan")] * 12, id="all_nan"),
    ],
)
def test_nan_is_rejected_not_zero_filled(q) -> None:
    """NaN отвергается: молча превращать его в ноль нельзя.

    Q = 0 физически допустим, поэтому подстановка нуля сделала бы пропуск
    данных неотличимым от реального нулевого притока. Отказ явный.
    """
    with pytest.raises(ValueError, match="NaN"):
        annual_regulation_table(np.asarray(q, dtype=float), 20.0, 1.0)


# ----------------------------------------------------------------------
# F. Отрицательные расходы
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "q",
    [
        pytest.param([30.0] * 11 + [-1.0], id="one_negative"),
        pytest.param(
            [30.0] * 9 + [-1.0, -2.0, -3.0], id="three_negative"
        ),
    ],
)
def test_negative_flows_are_rejected(q) -> None:
    """Отрицательный месячный расход отвергается.

    Во всех параметрах среднее положительно, поэтому отказ не может быть
    вызван другой проверкой — он обязан исходить из знака элемента.
    """
    array = np.asarray(q, dtype=float)
    assert array.mean() > 0, "среднее должно быть положительным"

    with pytest.raises(ValueError, match="отрицательн"):
        annual_regulation_table(array, 20.0, 1.0)


# ----------------------------------------------------------------------
# G. Нулевой расход допустим
# ----------------------------------------------------------------------
def test_zero_flows_are_admissible() -> None:
    """Q = 0 — физически допустимо и не должно отклоняться по знаку.

    Нулевой сток реки реален; отклонять его правомерно не на что. Ряд из
    нулей отличается от пропуска данных и от NaN, и все три случая обязаны
    различаться.
    """
    frame = _frame([0.0] * 12, demand=1.0, v_useful=1.0)

    assert len(frame) == 12
    # При Q = 0 и заборе 1 каждый месяц даёт строгий отрицательный прирост,
    # то есть функция честно показывает накопление дефицита, а не ошибку.
    assert float(frame["dV_km3"].iloc[0]) < 0.0
    assert float(frame["V_баланс_km3"].iloc[-1]) < 0.0


# ----------------------------------------------------------------------
# H. Полезный объём
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "v_useful", [0.0, -0.5, -1.0], ids=["zero", "small_negative", "negative"]
)
def test_non_positive_useful_volume_is_rejected(v_useful) -> None:
    """V_useful_km3 <= 0 отвергается.

    Раньше деление было защищено и молча давало «Заполнен_% = 0», чем
    бессмысленный вход маскировался под результат.
    """
    with pytest.raises(ValueError, match="Полезный объём"):
        annual_regulation_table(np.full(12, 30.0), 20.0, v_useful)


def test_positive_useful_volume_is_accepted() -> None:
    """Положительный полезный объём — штатный случай."""
    for v_useful in (0.05, 1.0, 25.0):
        frame = _frame([30.0] * 12, demand=20.0, v_useful=v_useful)
        assert len(frame) == 12


# ----------------------------------------------------------------------
# I. Публичный выход
# ----------------------------------------------------------------------
def test_public_output_columns_and_row_count_unchanged() -> None:
    """Шесть существующих колонок и 12 строк. Имена НЕ переименовываются.

    Набор колонок — часть публичного выхода; его фиксация защищает от
    случайного переименования при будущих правках.
    """
    frame = _frame([30.0] * 12, demand=20.0, v_useful=1.0)

    assert list(frame.columns) == EXPECTED_COLUMNS
    assert len(frame) == 12
    assert list(frame["Месяц"])[:3] == ["Янв", "Фев", "Мар"]


# ----------------------------------------------------------------------
# J. Текущая семантика «Заполнен_%»
# ----------------------------------------------------------------------
def test_filled_percent_is_balance_over_useful_volume() -> None:
    """Заполнен_% = V_баланс_km3 / V_useful_km3 · 100 — как есть.

    Ограничивать процент диапазоном 0…100 ЗДЕСЬ НЕЛЬЗЯ: V_баланс является
    накопительным счётчиком, а не уровнем запаса, поэтому выход за 0…100 —
    следствие конструкции, а не ошибка. Данный тест фиксирует формулу и
    тем самым делает нынешнее поведение явным, а не случайным.
    """
    v_useful = 2.0
    frame = _frame([30.0] * 12, demand=20.0, v_useful=v_useful)

    for i in range(12):
        expected = (
            float(frame["V_баланс_km3"].iloc[i]) / v_useful * 100.0
        )
        assert float(frame["Заполнен_%"].iloc[i]) == pytest.approx(
            expected, abs=TOL_PERCENT
        ), f"месяц {i + 1}: процент не соответствует формуле"


# ----------------------------------------------------------------------
# K. Нормативный статус не меняется
# ----------------------------------------------------------------------
def test_normative_status_stays_unknown() -> None:
    """Проверка входа не может повысить нормативный статус функции.

    Численной формулы «объём — гарантированная отдача» в локальном корпусе
    нет, поэтому правка контракта не приписывает функции стандарт.
    """
    import inspect

    doc = inspect.getdoc(rr.annual_regulation_table) or ""
    assert "UNKNOWN" in doc
    assert "CONFLICT" in doc
    for claim in ("соответствует СП 33", "соответствует СП 529",
                  "реализует СП 529", "по СП 529 п.", "по СП 33 п."):
        assert claim not in doc, f"недопустимая атрибуция: {claim!r}"
