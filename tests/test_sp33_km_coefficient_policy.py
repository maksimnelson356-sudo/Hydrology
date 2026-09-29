"""Политика (б): при Cs/Cv < 2 поправка (5.7) не применяется вовсе.

Решение принято 2026-09-29 после того, как п. 5.6 был прочитан по печати в высоком
разрешении: коэффициенты b1...b6 для распределения Крицкого-Менкеля стандарт берёт
из таблицы источника [4], а не из приложения Б. Таблица Б.1 — это Пирсон III.

Почему не «посчитать по Б.1 и предупредить». Измеренная величина расхождения при
такой подмене — до 27 % по Cs (n = 20, r(1) = 0,2: 0,4834 против 0,6608).
corrected_cs уходит прямо в calculate_frequency_curve (use_corrected=True по
умолчанию), confidence_bands и gts_integration, то есть неверное число дошло бы
до пользователя. Поправка из чужой таблицы - это не поправка, а новая ошибка.

Эти тесты закрывают три вещи: саму политику, её распространение на всех трёх
потребителей и запрет на молчаливое применение поправки при Cs/Cv >= 2.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from core.gts_reference import GTSClass
from core.stats.confidence_bands import pearson3_confidence_bands
from core.stats.frequency import calculate_frequency_curve
from core.stats.gts_integration import build_gts_frequency_curve
from core.stats.parameters import (
    calculate_statistical_parameters,
    sp33_bias_correction_56_57,
)


def _find_series(lo: float, hi: float, n: int = 25, seed: int = 5) -> np.ndarray:
    """Ряд с заданным Cs/Cv И с применяемыми поправками.

    Оба условия существенны, и второе неприятно: п. 5.6 разрешает вообще не
    вводить поправки при Cv < 0,6 и Cs < 1,0. Это ОТДЕЛЬНАЯ ветвь, и в ней
    corrected_cs тождественна cs по прямому допущению стандарта, а не из-за
    распределения Крицкого-Менкеля. Смешивать эти две причины нельзя.

    Практически: при sigma = 0,35 ВСЕ ряды с Cs/Cv < 2 удовлетворяют условию
    отказа (проверено: 744 кандидата, из них с применяемыми поправками 0). Чтобы
    получить Cs/Cv < 2 при Cv >= 0,6, нужен больший разброс, поэтому sigma
    перебирается.
    """
    rng = np.random.default_rng(seed)
    for sigma in (0.35, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        for _ in range(4000):
            series = rng.lognormal(0.0, sigma, n)
            cs = float(stats.skew(series, bias=False))
            cv = float(series.std(ddof=1) / series.mean())
            if cv <= 0 or cs <= 0:
                continue
            if not (lo < cs / cv < hi):
                continue
            if cv < 0.6 and cs < 1.0:
                continue
            return series
    raise AssertionError(
        f"не найден ряд с Cs/Cv в ({lo}; {hi}) и с применяемыми поправками"
    )


def test_cs_correction_not_applied_below_ratio_two() -> None:
    series = _find_series(0.7, 1.8)
    result = calculate_statistical_parameters(series, show_warnings=False)

    assert result["cs"] / result["cv"] < 2.0
    assert result["bias_corrections_applied"] is True, "поправка (5.6) применяется"
    assert result["bias_coefficients_applicable"] is False
    assert result["cs_correction_applied"] is False
    assert result["corrected_cs"] == pytest.approx(result["cs"]), (
        "при Cs/Cv < 2 возвращается несмещенная Cs, а не поправка по коэффициентам "
        "Пирсона III"
    )
    assert "НЕ ПРИМЕНЕНА" in result["correction_note"]
    assert "[4]" in result["correction_note"]


def test_cs_correction_still_applied_at_or_above_ratio_two() -> None:
    """Молча отключить поправку нельзя: при Cs/Cv >= 2 коэффициенты Б.1 верны."""
    series = _find_series(2.2, 4.0, n=30, seed=77)
    result = calculate_statistical_parameters(series, show_warnings=False)

    assert result["cs"] / result["cv"] >= 2.0
    assert result["bias_coefficients_applicable"] is True
    assert result["cs_correction_applied"] is True
    assert result["corrected_cs"] != result["cs"]
    assert "НЕ ПРИМЕНЕНА" not in result["correction_note"]


def test_boundary_at_exactly_two() -> None:
    """Граница Cs/Cv = 2: при 2,0 поправка применяется, при 1,9 - нет."""
    assert sp33_bias_correction_56_57(1.0, 1.9, 40, 0.2)["cs_correction_applied"] is False
    assert sp33_bias_correction_56_57(1.0, 2.0, 40, 0.2)["cs_correction_applied"] is True


def test_cv_correction_from_b1_is_kept() -> None:
    """Политика (б) касается (5.7); (5.6) по-прежнему считается.

    Отдельно отмечено: a-коэффициенты (5.6) тоже зависят от распределения по тексту
    п. 5.6, и этот вопрос не решён. Здесь фиксируется лишь то, что поправка Cv не
    отключена молча.
    """
    series = _find_series(0.7, 1.8)
    result = calculate_statistical_parameters(series, show_warnings=False)
    assert result["corrected_cv"] != result["cv"]


@pytest.mark.parametrize("lo, hi", [(0.7, 1.8), (2.2, 4.0)])
def test_flag_reaches_all_three_consumers(lo: float, hi: float) -> None:
    """Признак обязан доходить до кривой, полос и точек ГТС.

    Именно это было дефектом до 2026-09-29: флаг лежал в словаре параметров, и ни
    один потребитель его не смотрел, так что неверный Cs уходил в расчёт молча.
    """
    series = _find_series(lo, hi, n=30, seed=77)
    params = calculate_statistical_parameters(series, show_warnings=False)
    expected = params["cs_correction_applied"]

    curve = calculate_frequency_curve(series)
    assert curve.attrs["cs_correction_applied"] is expected
    assert "bias_coefficients_applicable" in curve.attrs
    assert curve.attrs["cs_correction_note"]

    bands = pearson3_confidence_bands(series, n_bootstrap=25, confidence=0.90)
    assert bands["cs_correction_applied"] is expected
    assert bands["normativity_note"]

    gts = build_gts_frequency_curve(series, GTSClass.CLASS_I)
    assert gts["cs_correction_applied"] is expected
    assert gts["normativity_note"]


def test_flag_is_not_a_data_column() -> None:
    """Признак нормативности - атрибут, а не столбец: иначе он попадёт в выгрузку."""
    series = _find_series(0.7, 1.8)
    curve = calculate_frequency_curve(series)
    assert list(curve.columns) == ["P_%", "Q"]


def test_policy_is_recorded_in_source() -> None:
    """Причина отключения обязана быть в коде, а не только в тесте."""
    import inspect

    from core.stats.parameters import sp33_bias_correction_56_57 as fn

    doc = inspect.getdoc(fn) or ""
    assert "[4]" in doc, "в докстринге назван внешний источник"
    assert "Крицкого-Менкеля" in doc
    assert "НЕ ПРИМЕНЯЕТСЯ" in doc, "в докстринге сказано про отключение (5.7)"
