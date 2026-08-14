#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Тестирование граничных случаев и потенциальных проблем"""
import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

print('=' * 70)
print('EDGE CASES AND POTENTIAL ISSUES')
print('=' * 70)

issues = []

def check(name, condition, msg=''):
    if not condition:
        issues.append(f'{name}: {msg}')
        print(f'  ISSUE: {name} - {msg}')
    else:
        print(f'  OK: {name}')

# =============================================
# 1. SHORT_SERIES - граничные случаи
# =============================================
print()
print('=== 1. short_series.py ===')
from core.short_series import restore_short_series, fit_analog_relationship

# Мало данных
check('short_1_year',
      restore_short_series(pd.Series([10.0], index=[2000]), {}, [], min_analogs=1)['n_restored'] >= 0,
      '1 year should not crash')

# Нет общих лет
check('short_no_common',
      restore_short_series(pd.Series([10.0], index=[2050]), {'A': pd.Series([10.0], index=[2000])}, ['A'], min_analogs=1)['n_restored'] == 0,
      'No common years should return 0')

# Все NaN
check('short_all_nan',
      restore_short_series(pd.Series([np.nan, np.nan]), {'A': pd.Series([np.nan])}, ['A'], min_analogs=1)['n_restored'] == 0,
      'All NaN should not crash')

# Отрицательные значения
check('short_negative',
      restore_short_series(pd.Series([-10.0, 10.0], index=[2000, 2001]),
                          {'A': pd.Series([-5.0, 15.0], index=[2000, 2001])},
                          ['A'], min_analogs=1)['n_restored'] >= 0,
      'Negative values should not crash')

# =============================================
# 2. HOMOGENEITY - граничные случаи
# =============================================
print()
print('=== 2. homogeneity.py ===')
from core.stats.homogeneity import check_homogeneity_full, stationarity_test

# Мало данных
check('homo_n2', check_homogeneity_full(np.array([10, 20]))['is_homogeneous'], 'n=2 should be homogeneous')
check('homo_n1', check_homogeneity_full(np.array([10]))['is_homogeneous'], 'n=1 should be homogeneous')
check('homo_empty', check_homogeneity_full(np.array([]))['is_homogeneous'], 'Empty should be homogeneous')

# Все одинаковые
check('homo_const', check_homogeneity_full(np.array([100, 100, 100, 100, 100]))['is_homogeneous'], 'Constant should be homogeneous')

# Стационарность с малым набором
check('stat_n4', stationarity_test(np.array([10, 20, 30, 40]))['is_stationary'] is not None, 'n=4 should not crash')

# =============================================
# 3. FREQUENCY - граничные случаи
# =============================================
print()
print('=== 3. frequency.py ===')
from core.stats.frequency import calculate_frequency_curve, auto_select_cs_cv, pearson3_ppf

# Мало данных
check('freq_n5', len(calculate_frequency_curve(np.array([1,2,3,4,5]))) > 0, 'n=5 should work')

# Все одинаковые
check('freq_const', len(calculate_frequency_curve(np.array([100,100,100,100,100]))) > 0, 'Constant should work')

#pearson3 с Cs=0
check('pearson3_cs0', len(pearson3_ppf(np.array([0.5]), 100, 0.2, 0)) > 0, 'Cs=0 should work')

#pearson3 с большими Cs
check('pearson3_cs_high', len(pearson3_ppf(np.array([0.5]), 100, 0.2, 5)) > 0, 'High Cs should work')

# Автоподбор с малым набором
check('auto_cs_cv_n5', auto_select_cs_cv(np.array([1,2,3,4,5]))['cs_cv_optimal'] is not None, 'n=5 should work')

# =============================================
# 4. SERIES_EXTENSION - граничные случаи
# =============================================
print()
print('=== 4. series_extension.py ===')
from core.stats.series_extension import validate_correlation, regression_extension, compute_integral_curves

# Мало данных
check('validate_n3', validate_correlation(pd.Series([1,2,3]), pd.Series([1,2,3]))['R'] is not None, 'n=3 should work')

# Одинаковые данные
check('validate_identical', validate_correlation(pd.Series([1,1,1,1,1]), pd.Series([1,1,1,1,1]))['R'] is not None, 'Identical should work')

# Интегральная с 1 точкой (нужно >= 4)
r = compute_integral_curves(pd.Series([100]))
check('integral_n1', len(r['integral_curve']) == 0, 'n=1 should return empty')

# =============================================
# 5. COMPOSITE - граничные случаи
# =============================================
print()
print('=== 5. composite_curves.py ===')
from core.stats.composite_curves import compute_composite_curve_rodzhestvensky

# Одна категория
check('comp_1cat', 'error' in compute_composite_curve_rodzhestvensky([{'data': np.array([1,2,3]), 'name': 'A'}]),
      '1 category should error')

# Пустые категории
check('comp_empty', 'error' in compute_composite_curve_rodzhestvensky([]),
      'Empty should error')

# =============================================
# 6. ПРОБЛЕМЫ ЛОГИКИ
# =============================================
print()
print('=== 6. Logic checks ===')

# Pearson3 vs Kritsky-Menkel: одинаковые ли результаты при Cs=0?
from core.stats.frequency import pearson3_ppf, kritsky_menkel_ppf
p = np.array([0.01, 0.05, 0.5, 0.95, 0.99])
q_p3 = pearson3_ppf(p, 100, 0.2, 0)
q_km = kritsky_menkel_ppf(p, 100, 0.2, 0)
check('p3_vs_km_cs0', np.allclose(q_p3, q_km, rtol=0.1),
      f'Pearson3 vs KM at Cs=0 differ: {q_p3} vs {q_km}')

# Автоматический подбор Cs/Cv должен быть в диапазоне
np.random.seed(42)
data = np.random.gamma(2, 50, 50)
cs_cv = auto_select_cs_cv(data)
check('auto_cs_cv_range', -2.0 <= cs_cv['cs_cv_optimal'] <= 6.0,
      f'Cs/Cv out of range: {cs_cv["cs_cv_optimal"]}')

# =============================================
# ИТОГИ
# =============================================
print()
print('=' * 70)
if issues:
    print(f'ISSUES FOUND: {len(issues)}')
    for i in issues:
        print(f'  {i}')
else:
    print('NO ISSUES FOUND')
print('=' * 70)
