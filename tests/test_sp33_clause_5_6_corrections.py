"""п. 5.6 СП 33-101-2003: поправки на смещение РЕАЛИЗОВАНЫ по таблице Б.1.

История файла. До 2026-09-28 `calculate_statistical_parameters` отдавала ключи
`corrected_cv` и `corrected_cs`, тождественно равные `cv` и `cs`: поправок не
было никогда, а имена обещали, что были. Первая версия этого файла фиксировала
именно это расхождение и требовала, чтобы оно было видимым.

Сейчас поправки реализованы:

* смещённые оценки Ĉv и Ĉs уже совпадали с (5.8) и (5.9) — проверено численно;
* коэффициенты взяты из таблицы Б.1 печатного экземпляра, стр. 74;
* отказ от поправок применяется только при Cv < 0,6 и Cs < 1,0 — как предписывает
  п. 5.6, а не по умолчанию;
* интерполяция НЕ вводится: стандарт её не предписывает, берётся ближайший узел,
  а выбранные узлы возвращаются в выводе, чтобы выбор был проверяемым.

Формулы стандарта:

    (5.6)  Cv = (a1 + a2/n) + (a3 + a4/n)·Ĉv + (a5 + a6/n)·Ĉv²
    (5.7)  Cs = (b1 + b2/n) + (b3 + b4/n)·Ĉs + (b5 + b6/n)·Ĉs²
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pytest

from core.stats.parameters import (
    SP33_B1_A,
    SP33_B1_B,
    calculate_statistical_parameters,
    sp33_bias_correction_56_57,
)

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests" / "fixtures"
    / "sp33_bias_corrections_Б1_v1.json"
)
TABLE = json.loads(FIXTURE.read_text(encoding="utf-8"))


def low_variability(n: int = 40) -> np.ndarray:
    """Ряд с малым Cv и малой асимметрией — поправки не требуются."""
    rng = np.random.default_rng(20260928)
    return 10.0 + rng.normal(0.0, 0.1, size=n)


def high_variability(n: int = 40) -> np.ndarray:
    """Экспоненциальный ряд: Cv ≈ 1, Cs ≈ 2 — поправки обязательны."""
    rng = np.random.default_rng(20260928)
    return rng.exponential(1.0, size=n)


# --- коэффициенты в коде совпадают с первоисточником -----------------------

def test_module_table_matches_fixture_a() -> None:
    """Копия таблицы Б.1 в коде совпадает с проверенным фикстуром."""
    for row in TABLE["a_coefficients"]:
        node = (row["cs_cv"], row["r1"])
        assert SP33_B1_A[row["cs_cv"]][row["r1"]] == pytest.approx(
            row["a"], abs=1e-12
        ), f"a-коэффициенты разошлись для {node}"


def test_module_table_matches_fixture_b() -> None:
    for row in TABLE["b_coefficients"]:
        assert SP33_B1_B[row["r1"]] == pytest.approx(row["b"], abs=1e-12), (
            f"b-коэффициенты разошлись для r(1)={row['r1']}"
        )


def test_module_table_covers_the_full_grid() -> None:
    assert sorted(SP33_B1_A) == [2.0, 3.0, 4.0]
    for regime, by_r1 in SP33_B1_A.items():
        assert sorted(by_r1) == [0.0, 0.3, 0.5], regime
    assert sorted(SP33_B1_B) == [0.0, 0.3, 0.5]


# --- режим отказа от поправок ---------------------------------------------

def test_low_variability_is_exempt_and_keeps_raw_values() -> None:
    result = calculate_statistical_parameters(low_variability(), show_warnings=False)
    assert result["corrections_required"] is False
    assert result["bias_corrections_applied"] is False
    assert result["corrected_cv"] == result["cv"]
    assert result["corrected_cs"] == result["cs"]
    assert result["table_ratio_node"] is None
    assert "5.6" in result["correction_note"]


def test_exempt_series_does_not_warn_about_corrections() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        calculate_statistical_parameters(low_variability(), show_warnings=False)


# --- поправки применяются --------------------------------------------------

def test_high_variability_gets_corrections_applied() -> None:
    result = calculate_statistical_parameters(high_variability(), show_warnings=False)
    assert result["corrections_required"] is True
    assert result["bias_corrections_applied"] is True
    assert result["corrected_cv"] != result["cv"]
    assert result["table_ratio_node"] in (2.0, 3.0, 4.0)
    assert result["table_r1_node"] in (0.0, 0.3, 0.5)


def test_corrections_match_hand_computation_from_table_b1() -> None:
    """Поправка совпадает с независимым расчётом по (5.6) и (5.7)."""
    data = high_variability()
    result = calculate_statistical_parameters(data, show_warnings=False)
    n = result["n"]
    chat_v, chat_s = result["cv"], result["cs"]

    a = SP33_B1_A[result["table_ratio_node"]][result["table_r1_node"]]
    b = SP33_B1_B[result["table_r1_node"]]
    expect_cv = ((a[0] + a[1] / n)
                + (a[2] + a[3] / n) * chat_v
                + (a[4] + a[5] / n) * chat_v**2)
    expect_cs = ((b[0] + b[1] / n)
                 + (b[2] + b[3] / n) * chat_s
                 + (b[4] + b[5] / n) * chat_s**2)

    assert result["corrected_cv"] == pytest.approx(expect_cv, abs=1e-4)
    assert result["corrected_cs"] == pytest.approx(expect_cs, abs=1e-4)


def test_correction_function_is_directly_verifiable() -> None:
    """Сама функция поправок проверяется на числах из таблицы Б.1."""
    out = sp33_bias_correction_56_57(chat_v=0.5, chat_s=1.0, n=30, lag1_autocorrelation=0.0)
    a = SP33_B1_A[2.0][0.0]
    b = SP33_B1_B[0.0]
    assert out["table_ratio_node"] == 2.0
    assert out["table_r1_node"] == 0.0
    assert out["cs_cv"] == pytest.approx(2.0)
    assert out["cv"] == pytest.approx(
        (a[0] + a[1] / 30) + (a[2] + a[3] / 30) * 0.5 + (a[4] + a[5] / 30) * 0.25,
        abs=1e-12,
    )
    assert out["cs"] == pytest.approx(
        (b[0] + b[1] / 30) + (b[2] + b[3] / 30) * 1.0 + (b[4] + b[5] / 30) * 1.0,
        abs=1e-12,
    )


def test_nearest_node_selection_is_deterministic() -> None:
    """Узел выбирается из таблицы, а не выдумывается."""
    out = sp33_bias_correction_56_57(1.2, 2.5, n=20, lag1_autocorrelation=0.45)
    assert out["table_ratio_node"] in SP33_B1_A
    assert out["table_r1_node"] in SP33_B1_B
    # при r(1) = 0,45 ближайший узел — 0,5
    assert out["table_r1_node"] == 0.5


def test_applying_corrections_does_not_warn() -> None:
    """Применение поправок — нормальный путь, а не повод для предупреждения.

    До реализации поправок предупреждение сообщало, что их НЕТ, и потому было
    уместно. Теперь они есть, и предупреждать о соблюдении нормы — шум: у
    большинства гидрологических рядов Cv > 0,6 либо Cs > 1,0, так что оно
    срабатывало бы на каждом вызове. Сведения остаются в полях вывода.
    """
    # Ловим предупреждения, а не превращаем их в ошибки: тот же ряд вызывает
    # законное и постороннее предупреждение п. 5.1 о погрешности среднего,
    # которое к поправкам отношения не имеет.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = calculate_statistical_parameters(
            high_variability(), show_warnings=True
        )
    about_corrections = [str(w.message) for w in caught if "5.6" in str(w.message)]
    assert not about_corrections, (
        f"поправки не должны вызывать предупреждение, а получили: {about_corrections}"
    )
    assert result["bias_corrections_applied"] is True
    note = result["correction_note"]
    assert "Б.1" in note
    assert "интерполяция" in note
    assert str(result["table_ratio_node"]) in note
    assert str(result["table_r1_node"]) in note


def test_no_stale_claim_that_corrections_are_missing() -> None:
    """Старое сообщение об отсутствии поправок больше не может появиться."""
    result = calculate_statistical_parameters(high_variability(), show_warnings=False)
    blob = " ".join(str(v) for v in result.values())
    assert "не реализованы" not in blob
    assert "не применяются" not in blob


# --- невакуумность --------------------------------------------------------

def test_corrections_actually_change_the_result() -> None:
    """Фикстур не вакуумный: без поправок результат был бы тем же.

    Направление поправки НЕ проверяется как «вниз». Ожидание, что поправка на
    смещение обязана уменьшать Cv, было моей гидрологической интуицией, а не
    требованием стандарта, и оно неверно: (5.6) — эмпирическая аппроксимирующая
    поверхность, где положительный вклад a3, a5, a6 перевешивает отрицательный
    a4, и при умеренном Ĉv поправка увеличивает и Cv, и Cs по всем девяти узлам
    таблицы Б.1. Проверяется поэтому соответствие формуле, а не знак поправки.
    """
    data = high_variability()
    result = calculate_statistical_parameters(data, show_warnings=False)
    assert result["corrected_cv"] != result["cv"], (
        "поправка обязана менять Cv, иначе её применение бессмысленно"
    )
    assert result["corrected_cs"] != result["cs"]


def test_correction_direction_is_not_assumed_downward() -> None:
    """Фиксирует проверенный факт: (5.6) увеличивает оценку в этой области.

    Число 0,9498 получено из (5.6) при Ĉv = 0,9327, n = 40, узел Cs/Cv = 2,
    r(1) = 0. Если бы формула вдруг стала уменьшать, тест это заметил бы —
    значит отслеживает изменение, а не подгоняет ожидание.
    """
    out = sp33_bias_correction_56_57(
        chat_v=0.9327, chat_s=1.4559, n=40, lag1_autocorrelation=0.0
    )
    assert out["table_ratio_node"] == 2.0
    assert out["table_r1_node"] == 0.0
    assert out["cv"] == pytest.approx(0.9498, abs=1e-4)
    assert out["cv"] > 0.9327, "в проверенной точке (5.6) увеличивает Cv"


def test_correction_is_not_applied_when_conditions_are_met() -> None:
    """Два режима различаются, а не выглядят одинаково."""
    low = calculate_statistical_parameters(low_variability(), show_warnings=False)
    high = calculate_statistical_parameters(high_variability(), show_warnings=False)
    assert low["bias_corrections_applied"] is False
    assert high["bias_corrections_applied"] is True
    assert low["corrected_cv"] == low["cv"]
    assert high["corrected_cv"] != high["cv"]


def test_ratio_cs_cv_is_exposed() -> None:
    """П. 5.4 задаёт набор параметров как {среднее, Cv, Cs/Cv}."""
    result = calculate_statistical_parameters(high_variability(), show_warnings=False)
    assert result["cs_cv"] == pytest.approx(result["cs"] / result["cv"], abs=5e-4)


def test_constant_series_does_not_crash_the_correction() -> None:
    """Регрессия, внесённая при реализации поправок, и её причина.

    Ряд из одинаковых значений даёт Cv = 0, а scipy.stats.skew на нём
    возвращает NaN. Сравнение NaN < 1.0 ложно, поэтому наивная проверка
    отказа считала такой ряд требующим поправок и уходила в (5.6) с Ĉv = 0 —
    к исключению во время сбора корневых тестов. Теперь поправки при Ĉv = 0
    неприменимы и корректно пропускаются.
    """
    constant = np.full(40, 5.0)
    result = calculate_statistical_parameters(constant, show_warnings=False)
    assert result["cv"] == 0.0
    assert result["bias_corrections_applied"] is False
    assert result["corrected_cv"] == 0.0
    assert "неприменимы" in result["correction_note"]


def test_constant_series_flows_through_the_frequency_curve() -> None:
    """Тот же случай должен проходить и через публичный путь.

    Именно этот путь раньше ронял сбор корневых тестов: calculate_frequency_curve
    вызывает calculate_statistical_parameters, а тот уходил в (5.6) с Ĉv = 0.
    """
    from core.stats.frequency import calculate_frequency_curve

    constant = np.full(40, 5.0)
    frame = calculate_frequency_curve(
        constant, probabilities=np.array([0.1, 0.5, 0.9])
    )
    assert not frame.empty, "константный ряд должен давать кривую, а не исключение"


def test_frequency_curve_consumes_the_correction() -> None:
    """Поправка действительно доходит до кривой, а не остаётся в статистиках.

    calculate_frequency_curve по умолчанию берёт corrected_* (use_corrected=True),
    поэтому с включённой поправкой кривая должна отличаться от построенной по
    неисправленным значениям. Это и есть смысл всей работы: исправленный Cv
    обязан менять проектные числа.
    """
    from core.stats.frequency import calculate_frequency_curve

    data = high_variability()
    with_correction = calculate_frequency_curve(
        data, probabilities=np.array([0.1, 0.5, 0.9]), use_corrected=True
    )
    without_correction = calculate_frequency_curve(
        data, probabilities=np.array([0.1, 0.5, 0.9]), use_corrected=False
    )
    q_with = float(with_correction["Q"].iloc[1])
    q_without = float(without_correction["Q"].iloc[1])
    assert q_with != q_without, (
        "поправка (5.6)-(5.7) обязана влиять на ординату кривой"
    )
