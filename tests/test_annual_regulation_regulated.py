"""annual_regulation_table: opt-in режимы regulated, S_0_km3 и losses_km3.

ЧТО ПРОВЕРЯЕТСЯ. Новые ОПЦИОНАЛЬНЫЕ параметры функции, введённые Фазой 3:
  1. легаси-дефолт не изменён (регрессия к test_annual_regulation_table.py);
  2. S_0_km3 — начальный запас, сдвигающий счётчик;
  3. losses_km3 — 12 месячных объёмов потерь, вычитаемых из dV;
  4. regulated=True — модель запаса: клампинг по V_useful_km3 и нулю,
     колонки «Сброс_km3»/«Недобор_km3»/«Запас_на_конец_km3»,
     «Заполнен_%» в диапазоне 0…100;
  5. входной контракт новых параметров (отказы).

Ожидания по dV и по клампингу выведены из формул, записанных в docstring
функции, а не из тела цикла.

НОРМАТИВНЫЙ СТАТУС. Режим regulated — SOURCE_MISSING / ENGINEERING (см.
шапку модуля): регулировочное правило и определения сброса/недобора в
локальном нормативном корпусе не верифицированы. Тесты НЕ приписывают
режиму никакого стандарта.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.hydrorash.reservoir_regulation import annual_regulation_table

SEC_PER_DAY = 86400.0
DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

LEGACY_COLUMNS = [
    "Месяц",
    "Q_приток",
    "Q_забор",
    "dV_km3",
    "V_баланс_km3",
    "Заполнен_%",
]
REGULATED_EXTRA = ["Сброс_km3", "Недобор_km3", "Запас_на_конец_km3"]


def _dV(q_in: float, demand: float, month: int, loss: float = 0.0) -> float:
    """Ожидаемый dV месяца из формулы docstring, без обращения к коду."""
    return (q_in - demand) * DAYS[month] * SEC_PER_DAY / 1e9 - loss


# ----------------------------------------------------------------------
# 1. Регрессия: легаси-дефолт не изменён
# ----------------------------------------------------------------------
def test_legacy_defaults_keep_six_columns_and_old_values() -> None:
    """Вызов без новых аргументов даёт прежние 6 колонок и прежние числа.

    Сравнение с независимой реконструкцией: счётчик с нуля, без потерь,
    без клампинга.
    """
    q, demand = 30.0, 20.0
    frame = annual_regulation_table(np.full(12, q), demand)

    assert list(frame.columns) == LEGACY_COLUMNS

    balance = 0.0
    for i in range(12):
        balance += _dV(q, demand, i)
        assert float(frame["V_баланс_km3"].iloc[i]) == pytest.approx(
            balance, abs=2e-4
        )


def test_legacy_negative_deficit_still_accumulates_unbounded() -> None:
    """В легаси счётчик по-прежнему уходит ниже нуля — клампинга нет."""
    frame = annual_regulation_table(np.zeros(12), demand_m3_s=1.0)
    assert float(frame["V_баланс_km3"].iloc[-1]) < 0.0
    assert "Сброс_km3" not in frame.columns


# ----------------------------------------------------------------------
# 2. S_0_km3: начальный запас
# ----------------------------------------------------------------------
def test_s0_shifts_counter_linearly() -> None:
    """V_баланс_i = S_0 + Σ dV (независимая реконструкция формулы)."""
    q, demand, s0 = 30.0, 20.0, 0.5
    frame = annual_regulation_table(np.full(12, q), demand, S_0_km3=s0)

    balance = s0
    for i in range(12):
        balance += _dV(q, demand, i)
        assert float(frame["V_баланс_km3"].iloc[i]) == pytest.approx(
            balance, abs=2e-4
        )


def test_s0_zero_equals_legacy_start() -> None:
    """S_0_km3=0 эквивалентен вызову без S_0 (прежний старт с нуля)."""
    a = annual_regulation_table(np.full(12, 30.0), 20.0, S_0_km3=0.0)
    b = annual_regulation_table(np.full(12, 30.0), 20.0)
    assert np.allclose(
        a["V_баланс_km3"].to_numpy(float),
        b["V_баланс_km3"].to_numpy(float),
    )


def test_negative_s0_is_rejected() -> None:
    """Отрицательный начальный запас — ошибка входа."""
    with pytest.raises(ValueError, match="S_0_km3 не может быть отрицательным"):
        annual_regulation_table(np.full(12, 30.0), 20.0, S_0_km3=-0.1)


def test_s0_above_useful_rejected_only_in_regulated() -> None:
    """S_0 > V_useful: в regulated — ошибка, в легаси — допустимо.

    В легаси ёмкость не участвует вовсе (только делитель), поэтому
    ограничивать там S_0 негде и нельзя.
    """
    with pytest.raises(ValueError, match="больше полезного"):
        annual_regulation_table(
            np.full(12, 30.0), 20.0,
            V_useful_km3=1.0, S_0_km3=2.0, regulated=True,
        )
    frame = annual_regulation_table(
        np.full(12, 30.0), 20.0, V_useful_km3=1.0, S_0_km3=2.0
    )
    assert float(frame["V_баланс_km3"].iloc[0]) > 1.0


# ----------------------------------------------------------------------
# 3. losses_km3: пользовательские потери
# ----------------------------------------------------------------------
def test_losses_are_subtracted_from_dv() -> None:
    """dV_i = (Q_in − Q_out)·дней·86400/1e9 − losses_i (формула docstring)."""
    q, demand = 30.0, 20.0
    losses = [0.001 * (i + 1) for i in range(12)]
    frame = annual_regulation_table(
        np.full(12, q), demand, losses_km3=losses
    )

    for i in range(12):
        assert float(frame["dV_km3"].iloc[i]) == pytest.approx(
            _dV(q, demand, i, losses[i]), abs=1e-4
        )
    # Итог: баланс уменьшен ровно на сумму потерь за год.
    clean = annual_regulation_table(np.full(12, q), demand)
    total_loss = sum(losses)
    assert float(frame["V_баланс_km3"].iloc[-1]) == pytest.approx(
        float(clean["V_баланс_km3"].iloc[-1]) - total_loss, abs=5e-4
    )


def test_none_losses_equals_no_losses() -> None:
    """losses_km3=None (дефолт) — потерь нет, числа совпадают."""
    a = annual_regulation_table(np.full(12, 30.0), 20.0, losses_km3=None)
    b = annual_regulation_table(np.full(12, 30.0), 20.0)
    assert np.allclose(
        a["V_баланс_km3"].to_numpy(float),
        b["V_баланс_km3"].to_numpy(float),
    )


def test_wrong_length_losses_rejected() -> None:
    """Не 12 значений потерь — ошибка, не молчаливое дополнение."""
    with pytest.raises(ValueError, match="12 значений"):
        annual_regulation_table(
            np.full(12, 30.0), 20.0, losses_km3=[0.001] * 11
        )


def test_nan_losses_rejected() -> None:
    """NaN в потерях — ошибка, не превращение в ноль."""
    losses = [0.001] * 12
    losses[5] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        annual_regulation_table(np.full(12, 30.0), 20.0, losses_km3=losses)


def test_negative_losses_rejected() -> None:
    """Отрицательные потери — ошибка (это был бы приток, а не потери)."""
    losses = [0.001] * 12
    losses[3] = -0.5
    with pytest.raises(ValueError, match="отрицательными"):
        annual_regulation_table(np.full(12, 30.0), 20.0, losses_km3=losses)


# ----------------------------------------------------------------------
# 4. regulated=True: модель запаса
# ----------------------------------------------------------------------
def test_regulated_adds_three_columns_nine_total() -> None:
    """regulated: 6 прежних колонок + 3 новые, порядок прежних сохранён."""
    frame = annual_regulation_table(
        np.full(12, 30.0), 20.0, V_useful_km3=1.0, regulated=True
    )
    assert list(frame.columns) == LEGACY_COLUMNS + REGULATED_EXTRA
    assert len(frame) == 12


def test_regulated_clamps_at_useful_volume_with_spill() -> None:
    """Излишек сверх V_useful уходит в «Сброс_km3», запас не выше ёмкости.

    Независимая реконструкция: в январе raw = 0 + dV > V_useful,
    клампинг должен сработать сразу.
    """
    v_useful = 0.05
    frame = annual_regulation_table(
        np.full(12, 100.0), 20.0,
        V_useful_km3=v_useful, regulated=True,
    )

    jan_dv = _dV(100.0, 20.0, 0)
    jan_spill = jan_dv - v_useful  # raw = 0 + dV > V_useful

    assert float(frame["V_баланс_km3"].iloc[0]) == pytest.approx(
        v_useful, abs=1e-4
    )
    assert float(frame["Сброс_km3"].iloc[0]) == pytest.approx(
        jan_spill, abs=2e-4
    )
    assert float(frame["Сброс_km3"].iloc[0]) > 0.0
    # Все последующие месяцы баланс держится на ёмкости, сброс каждый месяц.
    assert (frame["V_баланс_km3"] <= v_useful + 1e-9).all()
    assert (frame["Сброс_km3"] > 0).all()


def test_regulated_deficit_goes_to_unmet_not_below_zero() -> None:
    """Недостаток притока: баланс не ниже 0, дефицит в «Недобор_km3»."""
    frame = annual_regulation_table(
        np.zeros(12), demand_m3_s=1.0,
        V_useful_km3=1.0, regulated=True,
    )

    jan_dv = _dV(0.0, 1.0, 0)  # январский отрицательный dV
    assert float(frame["V_баланс_km3"].iloc[0]) == pytest.approx(0.0, abs=1e-4)
    assert float(frame["Недобор_km3"].iloc[0]) == pytest.approx(
        -jan_dv, abs=2e-4
    )
    assert (frame["V_баланс_km3"] >= 0.0).all()
    assert (frame["Сброс_km3"] == 0.0).all()


def test_regulated_filled_percent_within_0_100() -> None:
    """«Заполнен_%» в regulated гарантированно в 0…100 при любом входе."""
    for q in (0.0, 5.0, 30.0, 500.0):
        frame = annual_regulation_table(
            np.full(12, q), 20.0, V_useful_km3=0.5, regulated=True
        )
        pct = frame["Заполнен_%"].to_numpy(float)
        assert (pct >= 0.0).all() and (pct <= 100.0).all(), f"Q={q}: {pct}"


def test_regulated_storage_column_equals_balance() -> None:
    """«Запас_на_конец_km3» — тот же уровень, что «V_баланс_km3»."""
    frame = annual_regulation_table(
        np.full(12, 30.0), 20.0, V_useful_km3=1.0, regulated=True
    )
    assert np.allclose(
        frame["Запас_на_конец_km3"].to_numpy(float),
        frame["V_баланс_km3"].to_numpy(float),
        atol=1e-9,
    )


def test_regulated_mass_balance_conservation() -> None:
    """Закон сохранения массы за год (regulated, без потерь):

        S_12 = S_0 + ΣdV − ΣСброс + ΣНедобор

    с точностью до округления публикуемых колонок (4 знака, 12 месяцев →
    допуск 2e-3).
    """
    s0, v_useful = 0.2, 0.5
    q_seq = [5.0, 60.0, 1.0, 80.0] + [20.0] * 8
    frame = annual_regulation_table(
        np.array(q_seq),
        demand_m3_s=25.0,
        V_useful_km3=v_useful,
        S_0_km3=s0,
        regulated=True,
    )

    s_end = float(frame["Запас_на_конец_km3"].iloc[-1])
    total_dv = float(np.sum([
        _dV(q, 25.0, i) for i, q in enumerate(q_seq)
    ]))
    total_spill = float(np.sum(frame["Сброс_km3"]))
    total_unmet = float(np.sum(frame["Недобор_km3"]))

    assert s_end == pytest.approx(
        s0 + total_dv - total_spill + total_unmet, abs=2e-3
    )


def test_regulated_losses_reduce_storage_before_clamping() -> None:
    """Потери вычитаются ДО клампинга: при dV − losses < 0 будет недобор.

    Q_in = 20 = забор → dV = 0; losses января 0.01 → raw = −0.01 → недобор.
    """
    losses = [0.01] + [0.0] * 11
    frame = annual_regulation_table(
        np.full(12, 20.0), demand_m3_s=20.0,
        V_useful_km3=1.0, losses_km3=losses, regulated=True,
    )
    assert float(frame["Недобор_km3"].iloc[0]) == pytest.approx(0.01, abs=1e-4)
    assert float(frame["V_баланс_km3"].iloc[0]) == pytest.approx(0.0, abs=1e-4)
    # Остальные месяцы: приток равен забору, потерь нет — баланс держится на 0.
    assert (frame["Недобор_km3"].iloc[1:] == 0.0).all()


def test_regulated_s0_at_capacity_accepted() -> None:
    """S_0 = V_useful в regulated — штатный случай (граница включена)."""
    frame = annual_regulation_table(
        np.full(12, 25.0), 20.0,
        V_useful_km3=1.0, S_0_km3=1.0, regulated=True,
    )
    # Старт ровно на ёмкости: любой излишек сбрасывается сразу.
    assert (frame["V_баланс_km3"] <= 1.0 + 1e-9).all()
    assert float(frame["Сброс_km3"].iloc[0]) > 0.0


def test_regulated_does_not_change_normative_status() -> None:
    """Режим не повышает нормативный статус: никаких атрибуций стандарту."""
    import inspect

    from core.hydrorash import reservoir_regulation as rr

    doc = inspect.getdoc(rr.annual_regulation_table) or ""
    assert "UNKNOWN" in doc
    assert "CONFLICT" in doc
    assert "SOURCE_MISSING" in doc
    for claim in ("соответствует СП 33", "соответствует СП 529",
                  "реализует СП 529", "по СП 529 п.", "по СП 33 п."):
        assert claim not in doc, f"недопустимая атрибуция: {claim!r}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

