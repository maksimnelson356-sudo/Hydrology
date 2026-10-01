"""Regression tests for СП 33 flow-statistics error limits."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.hydrorash.max_runoff import compute_max_runoff_stats
from core.hydrorash.min_runoff_extended import compute_min_runoff_stats
from core.stats.parameters import calculate_statistical_parameters


def test_short_series_reports_mean_error_as_not_computable() -> None:
    """На коротком ряду нормативное r(1) по (Б.1) больше единицы.

    Тогда множитель в (5.26)/(5.27) не имеет вещественного значения и погрешность
    среднего НЕ ВЫЧИСЛЯЕТСЯ. Прежний тест ожидал здесь 15,4% и r = 0,6722, но то был
    вход по корреляции Пирсона, тогда как стандарт требует для (5.26)/(5.27) именно
    r(1) из (Б.1)-(Б.3). Сообщение обязано говорить «не вычислена», а не «inf% превышает
    предел»: превышение не измерено.
    """
    series = np.array([10.0, 11.0, 13.0, 12.0, 15.0, 14.0, 17.0, 16.0])

    with pytest.warns(UserWarning, match="НЕ ВЫЧИСЛЕНА"):
        result = calculate_statistical_parameters(series)

    assert result["r1"] > 1.0, "на n = 8 нормативное r(1) по (Б.1) выходит за единицу"
    assert result["r1_pearson"] == pytest.approx(0.6722, abs=0.0001)
    assert len(result["length_warnings"]) == 1
    warning = result["length_warnings"][0]
    assert "НЕ ВЫЧИСЛЕНА" in warning
    assert "Б.1" in warning
    assert "не проверен" in warning


def test_stats_parameters_use_sp33_formula_5_27_and_10_percent_limit() -> None:
    """Ветвь (5.27) по нормативному r(1) и предел 10% по п. 5.1.

    Ряд подобран так, чтобы r(1) по (Б.1) попал в [0,5; 1) — тогда применяется (5.27),
    а не (5.26). Ожидаемые числа посчитаны независимо от реализации.
    """
    series = np.array([
        0.9659, 1.1075, 0.8959, 0.4848, 0.9404, 0.9363, 0.865, 0.8405,
        1.5414, 1.8147, 1.843, 2.1398, 0.9709, 1.0162, 1.0917, 1.1957,
        1.1778, 1.5432, 0.7142, 1.2368, 0.785, 0.9764, 1.3224, 1.0251,
        0.9722, 0.8901,
    ])

    with pytest.warns(UserWarning, match=r"13\.5%"):
        result = calculate_statistical_parameters(series)

    assert result["r1"] == pytest.approx(0.6041, abs=0.0001)
    assert result["r1"] >= 0.5, "ветвь (5.27) выбирается только при r(1) >= 0,5"
    assert len(result["length_warnings"]) == 1
    warning = result["length_warnings"][0]
    assert "13.5%" in warning
    assert "10%" in warning


def test_stats_parameters_use_sp33_formula_5_26_below_half() -> None:
    """Ветвь (5.26) при r(1) < 0,5 — множитель проще, погрешность меньше."""
    series = np.array([
        1.1596, 0.8029, 0.9858, 1.236, 0.7323, 1.23, 1.8811, 1.4836,
        1.2198, 0.7696, 0.7334, 0.871, 1.0757, 1.2344, 1.2865, 0.8556,
        0.7029, 1.32, 0.8593, 1.0075, 1.41, 1.2914, 2.6318, 1.4096,
        0.6418, 0.9687, 0.7065, 1.3419, 1.1326, 1.2761,
    ])

    result = calculate_statistical_parameters(series)

    assert result["r1"] == pytest.approx(0.3347, abs=0.0001)
    assert result["r1"] < 0.5, "ветвь (5.26) выбирается только при r(1) < 0,5"
    assert result["length_warnings"] == []


def test_max_runoff_uses_sp33_20_percent_error_limit() -> None:
    series = pd.Series(
        [100.0, 200.0, 200.0, 50.0, 200.0, 0.0, 100.0, 150.0,
         150.0, 0.0, 50.0, 150.0, 100.0, 0.0, 50.0]
    )

    result = compute_max_runoff_stats(series)

    assert 10.0 < result["epsilon"] < 20.0
    assert result["warnings"] == []
    assert result["reliability_class"] == "Надёжная"
    assert result["relative_rms_error_limit"] == pytest.approx(0.20)


def test_min_runoff_uses_sp33_20_percent_error_limit() -> None:
    series = pd.Series(
        [100.0, 200.0, 200.0, 50.0, 200.0, 20.0, 100.0, 150.0,
         150.0, 20.0, 50.0, 150.0, 100.0, 20.0, 50.0]
    )

    result = compute_min_runoff_stats(series)

    assert 10.0 < result["epsilon"] < 20.0
    assert result["warnings"] == []
    assert result["reliability_class"] == "Надёжная"
    assert result["relative_rms_error_limit"] == pytest.approx(0.20)


def test_max_and_min_runoff_warn_above_sp33_20_percent_limit() -> None:
    max_result = compute_max_runoff_stats(
        pd.Series([50.0, 200.0, 0.0, 150.0, 50.0, 0.0])
    )
    min_result = compute_min_runoff_stats(
        pd.Series([5.0, 20.0, 0.0, 15.0, 5.0, 0.0])
    )

    assert max_result["epsilon"] > 20.0
    assert min_result["epsilon"] > 20.0
    assert any("20" in warning for warning in max_result["warnings"])
    assert any("20" in warning for warning in min_result["warnings"])


def _normative_r1(values: np.ndarray) -> float:
    """Независимое вычисление r(1) по (Б.1)-(Б.3), без обращения к коду."""
    x = np.asarray(values, dtype=float)
    n = x.size
    q_bar_1 = x[1:].sum() / (n - 1)
    q_bar_2 = x[1:n - 1].sum() / (n - 1)
    a = x[1:] - q_bar_1
    b = x[:-1] - q_bar_2
    r_tilde = (a * b).sum() / np.sqrt((a**2).sum() * (b**2).sum())
    return float(
        -0.01
        + 0.98 * r_tilde
        - 0.06 * r_tilde**2
        + (1.66 + 6.46 * r_tilde + 5.69 * r_tilde**2) / n
    )


def test_max_runoff_uses_sp33_formula_5_27_for_high_autocorrelation() -> None:
    """Ветвь (5.27) по нормативному r(1) из (Б.1)-(Б.3).

    Ожидание считается из нормативного r(1), а не из корреляции Пирсона: в (Б.2)
    две разные средние и приведение к несмещённой оценке через (Б.1), так что
    величины различаются. Прежний вариант теста считал ожидание через np.corrcoef
    и тем самым закреплял нестандартный источник r(1) в max_runoff.
    """
    values = np.array([
        0.9659, 1.1075, 0.8959, 0.4848, 0.9404, 0.9363, 0.865, 0.8405,
        1.5414, 1.8147, 1.843, 2.1398, 0.9709, 1.0162, 1.0917, 1.1957,
        1.1778, 1.5432, 0.7142, 1.2368, 0.785, 0.9764, 1.3224, 1.0251,
        0.9722, 0.8901,
    ])
    series = pd.Series(values)
    result = compute_max_runoff_stats(series)

    n = values.size
    r1 = _normative_r1(values)
    assert r1 >= 0.5, "ветвь (5.27) выбирается только при r(1) >= 0,5"
    assert result["r1"] == pytest.approx(r1, abs=1e-4)

    correction = sum(1.0 - r1**power for power in range(1, n))
    numerator = 1.0 + 2.0 * r1 / (n * (1.0 - r1)) * correction
    denominator = 1.0 - 2.0 * r1 / (n * (n - 1) * (1.0 - r1)) * correction
    cv = float(values.std(ddof=1) / values.mean())
    expected = cv / np.sqrt(n) * np.sqrt(numerator / denominator) * 100.0

    assert result["epsilon"] == pytest.approx(expected, abs=0.01)
    assert result["epsilon"] == pytest.approx(13.51, abs=0.01)
    assert result["warnings"] == []


def test_max_runoff_reports_not_computable_instead_of_pearson_value() -> None:
    """На коротком ряду εQ не вычисляется, а не подменяется значением по Пирсону.

    Тот же ряд n = 8, на котором раньше получалось 15,4% по корреляции Пирсона.
    Теперь max_runoff берёт нормативное r(1) = 1,418, множитель в (5.27) не
    имеет вещественного значения, и методика обязана сказать об этом прямо.
    """
    series = pd.Series([10.0, 11.0, 13.0, 12.0, 15.0, 14.0, 17.0, 16.0])
    result = compute_max_runoff_stats(series)

    assert not np.isfinite(result["epsilon"])
    assert result["reliability_class"] == "Недостаточно данных"
    assert any("НЕ ВЫЧИСЛЕНА" in warning for warning in result["warnings"])
    assert any("Б.1" in warning for warning in result["warnings"])
