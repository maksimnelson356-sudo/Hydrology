"""Источник r(1) в compute_basic_stats: нормативный (Б.1), а не Пирсон.

(5.26) и (5.27) СП 33-101-2003 требуют r(1) по приложению Б. В (Б.2) используются
две разные средние, Q̄₁ и Q̄₂, а смещённая оценка r̃ приводится к несмещённой
через (Б.1). Это другая величина, чем корреляция Пирсона первого порядка.

Здесь она подставлялась через np.corrcoef, то есть εQ считалась не по той
величине, которую требует стандарт. Тест закрепляет нормативный источник.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.hydrorash.utils import compute_basic_stats
from core.stats.parameters import sp33_lag1_autocorrelation

# Ряд длиной 26, у которого нормативное r(1) = 0,604 попадает в ветвь (5.27).
SERIES_5_27 = [
    0.9659, 1.1075, 0.8959, 0.4848, 0.9404, 0.9363, 0.865, 0.8405,
    1.5414, 1.8147, 1.843, 2.1398, 0.9709, 1.0162, 1.0917, 1.1957,
    1.1778, 1.5432, 0.7142, 1.2368, 0.785, 0.9764, 1.3224, 1.0251,
    0.9722, 0.8901,
]

# Ряд из восьми значений, на котором нормативное r(1) = 1,418, то есть больше
# единицы. Раньше по нему получалось 15,4% — но по корреляции Пирсона.
SHORT_SERIES = [10.0, 11.0, 13.0, 12.0, 15.0, 14.0, 17.0, 16.0]


def test_uses_normative_r1_not_pearson() -> None:
    result = compute_basic_stats(pd.Series(SERIES_5_27))

    lag1 = sp33_lag1_autocorrelation(np.asarray(SERIES_5_27, dtype=float))
    pearson = float(np.corrcoef(
        np.asarray(SERIES_5_27)[:-1], np.asarray(SERIES_5_27)[1:]
    )[0, 1])

    assert lag1["normative"] is True
    assert result["r"] == pytest.approx(lag1["r1"], abs=1e-9)
    assert result["r"] != pytest.approx(pearson, abs=1e-3), (
        "compute_basic_stats обязан брать r(1) по (Б.1), а не Пирсона"
    )
    assert "Б.1" in result["r_source"]


def test_epsilon_matches_independent_calculation_of_5_27() -> None:
    """εQ пересчитывается независимо от кода по нормативному r(1)."""
    values = np.asarray(SERIES_5_27, dtype=float)
    result = compute_basic_stats(pd.Series(SERIES_5_27))

    n = values.size
    q_bar_1 = values[1:].sum() / (n - 1)
    q_bar_2 = values[1:n - 1].sum() / (n - 1)
    a = values[1:] - q_bar_1
    b = values[:-1] - q_bar_2
    r_tilde = (a * b).sum() / np.sqrt((a**2).sum() * (b**2).sum())
    r1 = float(
        -0.01
        + 0.98 * r_tilde
        - 0.06 * r_tilde**2
        + (1.66 + 6.46 * r_tilde + 5.69 * r_tilde**2) / n
    )
    assert r1 >= 0.5

    correction = sum(1.0 - r1**power for power in range(1, n))
    numerator = 1.0 + 2.0 * r1 / (n * (1.0 - r1)) * correction
    denominator = 1.0 - 2.0 * r1 / (n * (n - 1) * (1.0 - r1)) * correction
    cv = float(values.std(ddof=1) / values.mean())
    expected = cv / np.sqrt(n) * np.sqrt(numerator / denominator) * 100.0

    assert result["epsilon"] == pytest.approx(expected, abs=1e-9)
    assert result["epsilon"] == pytest.approx(13.51, abs=0.01)


def test_short_series_reports_not_computable_rather_than_pearson_value() -> None:
    """На коротком ряду εQ не вычисляется, и это названо прямо.

    Подстановка Пирсона дала бы здесь правдоподобное 15,4% и создала бы ложное
    впечатление, что методика применима к восьмилетнему ряду.
    """
    result = compute_basic_stats(pd.Series(SHORT_SERIES))

    assert result["r"] > 1.0, "нормативное r(1) по (Б.1) выходит за единицу"
    assert not np.isfinite(result["epsilon"])
    assert result["reliability_class"] == "Недостаточно данных"
    assert any("НЕ ВЫЧИСЛЕНА" in warning for warning in result["warnings"])


def test_explicit_r_argument_is_respected() -> None:
    """Явно переданный r используется как есть, и это видно в r_source."""
    result = compute_basic_stats(pd.Series(SERIES_5_27), r=0.25)
    assert result["r"] == pytest.approx(0.25)
    assert result["r_source"] == "задан вызывающим"
    assert np.isfinite(result["epsilon"])
