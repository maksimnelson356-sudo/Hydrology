"""Тесты для reservoir_storage_calculation: геометрия объёма, мёртвый/полезный объём."""

from __future__ import annotations

import numpy as np
import pytest

from core.hydrorash.reservoir_regulation import reservoir_storage_calculation


def test_basic_volume_no_dead():
    """Базовый расчёт без H_dead — только общий объём."""
    H = [100.0, 105.0, 110.0]
    A = [1.0, 2.0, 3.0]  # км²
    # dV1 = (1+2)/2 * 5 / 1000 = 0.0075
    # dV2 = (2+3)/2 * 5 / 1000 = 0.0125
    # total = 0.0200 км³
    result = reservoir_storage_calculation(H, A)
    assert result['V_total_km3'] == pytest.approx(0.0200, abs=1e-6)
    assert 'V_dead_km3' not in result
    assert 'V_useful_km3' not in result


def test_dead_storage_at_bottom():
    """H_dead = нижний уровень → мёртвый объём = 0."""
    H = [100.0, 105.0, 110.0]
    A = [1.0, 2.0, 3.0]
    result = reservoir_storage_calculation(H, A, H_dead=100.0)
    assert result['V_dead_km3'] == 0.0
    assert result['V_useful_km3'] == pytest.approx(0.0200, abs=1e-6)


def test_dead_storage_at_top():
    """H_dead = верхний уровень → мёртвый объём = общий, полезный = 0."""
    H = [100.0, 105.0, 110.0]
    A = [1.0, 2.0, 3.0]
    result = reservoir_storage_calculation(H, A, H_dead=110.0)
    assert result['V_dead_km3'] == pytest.approx(0.0200, abs=1e-6)
    assert result['V_useful_km3'] == 0.0


def test_dead_storage_middle():
    """H_dead внутри интервала — интерполяция площади."""
    # H=100..110, A=1..3. H_dead=105 (середина)
    # Площадь на 105 = 2.0 (линейно между 1 и 3)
    # Объём 100-105: (1+2)/2 * 5 / 1000 = 0.0075
    H = [100.0, 105.0, 110.0]
    A = [1.0, 2.0, 3.0]
    result = reservoir_storage_calculation(H, A, H_dead=105.0)
    assert result['V_dead_km3'] == pytest.approx(0.0075, abs=1e-6)
    assert result['V_useful_km3'] == pytest.approx(0.0125, abs=1e-6)
    assert result['H_dead_m'] == 105.0


def test_dead_storage_arbitrary_level():
    """H_dead не на узле сетки — интерполяция работает."""
    H = [100.0, 110.0]  # два узла
    A = [1.0, 3.0]
    # H_dead = 105 → площадь = 2.0
    # Объём 100-105: (1+2)/2 * 5 / 1000 = 0.0075
    result = reservoir_storage_calculation(H, A, H_dead=105.0)
    assert result['V_dead_km3'] == pytest.approx(0.0075, abs=1e-6)
    assert result['V_useful_km3'] == pytest.approx(0.0125, abs=1e-6)


def test_invalid_H_dead_below_range():
    """H_dead ниже минимального уровня — ошибка."""
    H = [100.0, 105.0]
    A = [1.0, 2.0]
    with pytest.raises(ValueError, match="H_dead=95.0 должен быть в диапазоне"):
        reservoir_storage_calculation(H, A, H_dead=95.0)


def test_invalid_H_dead_above_range():
    """H_dead выше максимального уровня — ошибка."""
    H = [100.0, 105.0]
    A = [1.0, 2.0]
    with pytest.raises(ValueError, match="H_dead=110.0 должен быть в диапазоне"):
        reservoir_storage_calculation(H, A, H_dead=110.0)


def test_non_monotonic_H_raises():
    """Немонтонные H — ошибка."""
    H = [100.0, 105.0, 103.0]
    A = [1.0, 2.0, 3.0]
    with pytest.raises(ValueError, match="Уровни H должны быть строго возрастающими"):
        reservoir_storage_calculation(H, A)


def test_mismatched_lengths_raises():
    """Разные длины H и A — ошибка."""
    H = [100.0, 105.0, 110.0]
    A = [1.0, 2.0]
    with pytest.raises(ValueError, match="Длины списков H и A должны совпадать"):
        reservoir_storage_calculation(H, A)


def test_single_point_raises():
    """Один уровень — ошибка."""
    H = [100.0]
    A = [1.0]
    with pytest.raises(ValueError, match="Нужно минимум 2 уровня"):
        reservoir_storage_calculation(H, A)


def test_table_structure():
    """Проверка структуры возвращаемого DataFrame."""
    H = [100.0, 105.0, 110.0]
    A = [1.0, 2.0, 3.0]
    result = reservoir_storage_calculation(H, A)
    df = result['table']
    assert list(df.columns) == ['H_m', 'A_km2', 'V_cumulative_km3']
    assert len(df) == 3
    assert df['V_cumulative_km3'].iloc[0] == 0.0
    assert df['V_cumulative_km3'].iloc[-1] == pytest.approx(0.0200, abs=1e-6)


def test_realistic_reservoir():
    """Реалистичный водохранилище: дно 50м, НРУ 100м, мёртвый до 60м."""
    # Типичная морфометрия: площадь растёт с отметкой
    H = [50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    A = [0.5, 1.2, 2.5, 4.0, 6.0, 8.5]  # км²

    # Общий объём (50-100)
    result_full = reservoir_storage_calculation(H, A)
    # dV: 0.0085 + 0.0185 + 0.0325 + 0.05 + 0.0725 = 0.182
    assert result_full['V_total_km3'] == pytest.approx(0.182, abs=1e-4)

    # Мёртвый объём до 60м
    result_dead = reservoir_storage_calculation(H, A, H_dead=60.0)
    # 50-60: (0.5+1.2)/2 * 10 / 1000 = 0.0085
    assert result_dead['V_dead_km3'] == pytest.approx(0.0085, abs=1e-5)
    assert result_dead['V_useful_km3'] == pytest.approx(0.182 - 0.0085, abs=1e-5)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])