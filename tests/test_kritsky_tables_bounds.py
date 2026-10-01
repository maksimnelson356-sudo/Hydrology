"""
tests/test_kritsky_tables_bounds.py

Фиксация ТЕКУЩЕГО контракта core.stats.kritsky_tables.get_ordinates().

Тесты фиксируют существующее поведение реализации «как сейчас работает»,
а не желаемое новое поведение. В частности, молчаливая подстановка
ординат крайнего табличного узла при выходе за границы таблицы
закреплена здесь как факт, а не как нормативное предписание: основание
границ и правила подстановки в репозитории не зафиксировано.

Тесты не утверждают, что подстановка соответствует СП 33 или иному
нормативному источнику, и не утверждают, что 0.1 является нормативной
нижней границей коэффициента вариации.
"""

import warnings

import numpy as np
import pytest

from core.stats.kritsky_tables import PROBS, TABLES, get_ordinates

# Фактические границы, документированные в docstring get_ordinates().
# max Cv = последний ключ Cv в блоке TABLES[cs_cv].
EXPECTED_MIN_CV = 0.1
EXPECTED_R_KEYS = [-1, -0.5, 0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6]
EXPECTED_MAX_CV = {
    -1: 0.4,
    -0.5: 0.4,
    0: 0.5,
    0.5: 0.7,
    1: 2.0,
    1.5: 1.5,
    2: 2.0,
    2.5: 2.0,
    3: 2.0,
    3.5: 2.0,
    4: 2.0,
    4.5: 2.0,
    5: 2.0,
    5.5: 2.0,
    6: 2.0,
}

LOW_CV_CASES = [0.0, 0.05, 0.0999]

# Блоки, для которых Cs/Cv является нижним узлом своей пары (или краем
# таблицы): интерполяция по Cs/Cv идёт с весом 0.0, поэтому результат
# побитово совпадает с сохранённой строкой.
EXACT_BLOCKS = [-1, -0.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6]

# Отклонение результата от сохранённой строки при интерполяции по Cs/Cv
# с весом 1.0 не превышает единиц последнего разряда (измерено: 5.6e-17).
FLOAT_TOL = 1e-12


def _row(cs_cv, cv):
    """Ординаты узла TABLES[cs_cv][cv] напрямую, без вызова get_ordinates."""
    return np.asarray(TABLES[cs_cv][cv], dtype=float)


def _lerp(y_lo, y_hi, weight):
    """Линейная интерполяция, вычисленная независимо от реализации."""
    return y_lo + (y_hi - y_lo) * weight


# --------------------------------------------------------------------------
# A. Cv ниже минимума блока
# --------------------------------------------------------------------------

@pytest.mark.parametrize("cs_cv", [0, 1, 2, 4, 6])
def test_get_ordinates_clamps_low_cv_to_table_boundary(cs_cv):
    """Cv < 0.1 даёт тот же результат, что Cv = 0.1: строка Cv = 0.1."""
    baseline = np.asarray(get_ordinates(cs_cv, EXPECTED_MIN_CV), dtype=float)
    assert np.allclose(baseline, _row(cs_cv, EXPECTED_MIN_CV), rtol=FLOAT_TOL, atol=0.0)

    for cv in LOW_CV_CASES:
        got = np.asarray(get_ordinates(cs_cv, cv), dtype=float)
        assert np.array_equal(got, baseline), (
            f"r={cs_cv}, Cv={cv} отличается от Cv={EXPECTED_MIN_CV}"
        )


@pytest.mark.parametrize("cs_cv", EXACT_BLOCKS)
def test_get_ordinates_low_cv_result_is_the_stored_row(cs_cv):
    """Для блоков с весом 0.0 подставляется ровно сохранённая строка Cv = 0.1."""
    for cv in LOW_CV_CASES:
        got = np.asarray(get_ordinates(cs_cv, cv), dtype=float)
        assert np.array_equal(got, _row(cs_cv, EXPECTED_MIN_CV))


# --------------------------------------------------------------------------
# B. Cv выше максимума своего блока
# --------------------------------------------------------------------------

@pytest.mark.parametrize("cs_cv,max_cv", sorted(EXPECTED_MAX_CV.items()))
def test_get_ordinates_clamps_high_cv_to_block_boundary(cs_cv, max_cv):
    """Cv > max(Cs/Cv) даёт результат граничной строки Cv = max(Cs/Cv)."""
    baseline = np.asarray(get_ordinates(cs_cv, max_cv), dtype=float)
    assert np.allclose(baseline, _row(cs_cv, max_cv), rtol=FLOAT_TOL, atol=0.0)

    for cv in (max_cv + 0.0001, max_cv + 0.5, 3.0):
        got = np.asarray(get_ordinates(cs_cv, cv), dtype=float)
        assert np.allclose(got, baseline, rtol=FLOAT_TOL, atol=0.0), (
            f"r={cs_cv}, Cv={cv} отличается от граничного Cv={max_cv}"
        )
        assert got.shape == baseline.shape


def test_get_ordinates_high_cv_boundary_differs_between_blocks():
    """Верхняя граница Cv зависит от Cs/Cv, а не является общей."""
    # Блок r = 0 заканчивается на Cv = 0.5, поэтому 0.9 подставляет его узел.
    assert np.array_equal(
        np.asarray(get_ordinates(0, 0.9), dtype=float),
        np.asarray(get_ordinates(0, 0.5), dtype=float),
    )
    # Блок r = 2 продолжается до Cv = 2.0, поэтому 0.9 — интерполяция внутри.
    assert not np.array_equal(
        np.asarray(get_ordinates(2, 0.9), dtype=float),
        np.asarray(get_ordinates(2, 0.5), dtype=float),
    )
    assert not np.array_equal(
        np.asarray(get_ordinates(0, 0.9), dtype=float),
        np.asarray(get_ordinates(2, 0.5), dtype=float),
    )


def test_get_ordinates_high_cv_just_above_boundary_is_not_bit_identical():
    """Нюанс контракта: кланп по Cv применяется в каждом блоке r отдельно.

    Блок r = 1.5 заканчивается на Cv = 1.5, и его строка подставляется.
    Но r = 1.5 интерполируется между блоками 1 и 2, а блок r = 2 продолжается
    до Cv = 2.0, поэтому при Cv = 1.5001 он ещё интерполирует по Cv.
    Результат совпадает с граничным с точностью до последнего разряда,
    но побитово не равен ему.
    """
    boundary = np.asarray(get_ordinates(1.5, 1.5), dtype=float)
    just_above = np.asarray(get_ordinates(1.5, 1.5001), dtype=float)
    assert np.allclose(just_above, boundary, rtol=FLOAT_TOL, atol=0.0)
    assert not np.array_equal(just_above, boundary)


# --------------------------------------------------------------------------
# C. Cs/Cv ниже минимального ключа
# --------------------------------------------------------------------------

@pytest.mark.parametrize("cs_cv", [-1.0001, -1.5, -2, -5, -100])
def test_get_ordinates_clamps_low_r_to_table_boundary(cs_cv):
    """Cs/Cv < -1 даёт тот же результат, что Cs/Cv = -1."""
    for cv in (0.1, 0.2, 0.3, 0.4):
        baseline = get_ordinates(-1, cv)
        assert np.array_equal(_row(-1, cv), baseline)
        got = get_ordinates(cs_cv, cv)
        assert np.array_equal(got, baseline), f"r={cs_cv}, Cv={cv} отличается от r=-1"


# --------------------------------------------------------------------------
# D. Cs/Cv выше максимального ключа
# --------------------------------------------------------------------------

@pytest.mark.parametrize("cs_cv", [6.0001, 6.5, 7, 10, 100])
def test_get_ordinates_clamps_high_r_to_table_boundary(cs_cv):
    """Cs/Cv > 6 даёт тот же результат, что Cs/Cv = 6."""
    for cv in (0.1, 0.5, 1.0, 2.0):
        baseline = get_ordinates(6, cv)
        assert np.array_equal(_row(6, cv), baseline)
        got = get_ordinates(cs_cv, cv)
        assert np.array_equal(got, baseline), f"r={cs_cv}, Cv={cv} отличается от r=6"


# --------------------------------------------------------------------------
# E. Линейная интерполяция внутри табличной области
# --------------------------------------------------------------------------

def test_get_ordinates_interpolates_between_cv_nodes():
    """Cv = 0.1001 между узлами 0.1 и 0.2: линейная интерполяция по Cv."""
    cv = 0.1001
    lo, hi = 0.1, 0.2
    weight = (cv - lo) / (hi - lo)
    expected = _lerp(_row(1, lo), _row(1, hi), weight)

    got = get_ordinates(1, cv)
    assert np.allclose(got, expected, rtol=1e-12, atol=0.0)

    # Значение строго между узлами — интерполяция, а не подстановка узла.
    assert not np.array_equal(got, _row(1, lo))
    assert not np.array_equal(got, _row(1, hi))


def test_get_ordinates_interpolates_between_r_nodes():
    """r = -0.999 между блоками -1 и -0.5: линейная интерполяция по Cs/Cv."""
    r = -0.999
    r_lo, r_hi = -1, -0.5
    cv = 0.3
    weight = (r - r_lo) / (r_hi - r_lo)
    expected = _lerp(_row(r_lo, cv), _row(r_hi, cv), weight)

    got = get_ordinates(r, cv)
    assert np.allclose(got, expected, rtol=1e-12, atol=0.0)
    assert not np.array_equal(got, _row(r_lo, cv))
    assert not np.array_equal(got, _row(r_hi, cv))


def test_get_ordinates_interpolates_between_high_r_nodes():
    """r = 5.999 между блоками 5.5 и 6: линейная интерполяция по Cs/Cv."""
    r = 5.999
    r_lo, r_hi = 5.5, 6
    cv = 0.5
    weight = (r - r_lo) / (r_hi - r_lo)
    expected = _lerp(_row(r_lo, cv), _row(r_hi, cv), weight)

    got = get_ordinates(r, cv)
    assert np.allclose(got, expected, rtol=1e-12, atol=0.0)
    assert not np.array_equal(got, _row(r_lo, cv))
    assert not np.array_equal(got, _row(r_hi, cv))


# --------------------------------------------------------------------------
# F. Молчаливость подстановки
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "cs_cv,cv",
    [
        (0, 0.0), (1, 0.05), (2, 0.0999),          # ниже минимума Cv
        (0, 0.75), (1.5, 1.5001), (6, 3.0),        # выше максимума Cv
        (-5, 0.3), (100, 1.0),                     # за пределами по Cs/Cv
    ],
)
def test_get_ordinates_out_of_range_raises_no_warning(cs_cv, cv):
    """Подстановка за границу не сигнализируется: ни warning, ни исключения."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = get_ordinates(cs_cv, cv)
    assert [str(w.message) for w in caught] == []
    assert np.all(np.isfinite(np.asarray(result, dtype=float)))


# --------------------------------------------------------------------------
# G. Форма покрытия, заявленная в docstring
# --------------------------------------------------------------------------

def test_table_r_keys_match_documented_range():
    assert sorted(TABLES) == EXPECTED_R_KEYS
    assert min(TABLES) == -1
    assert max(TABLES) == 6


@pytest.mark.parametrize("cs_cv", EXPECTED_R_KEYS)
def test_table_min_cv_is_uniform(cs_cv):
    assert min(TABLES[cs_cv]) == EXPECTED_MIN_CV


@pytest.mark.parametrize("cs_cv", EXPECTED_R_KEYS)
def test_table_max_cv_matches_documented_per_block_boundary(cs_cv):
    assert max(TABLES[cs_cv]) == EXPECTED_MAX_CV[cs_cv]


@pytest.mark.parametrize("cs_cv", EXPECTED_R_KEYS)
def test_table_rows_are_complete_and_finite(cs_cv):
    """Текущее состояние данных: ряды полные, np.nan отсутствует."""
    for cv, row in TABLES[cs_cv].items():
        values = np.asarray(row, dtype=float)
        assert len(values) == len(PROBS), f"r={cs_cv}, Cv={cv}: длина ряда != len(PROBS)"
        assert not np.isnan(values).any(), f"r={cs_cv}, Cv={cv}: есть np.nan"
