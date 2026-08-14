#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Комплексное тестирование всех функций"""
import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

print('=' * 70)
print('COMPREHENSIVE TEST OF ALL FUNCTIONS')
print('=' * 70)

errors = []
passed = 0
failed = 0

def test(name, func):
    global passed, failed
    try:
        func()
        passed += 1
        print(f'  PASS: {name}')
    except Exception as e:
        failed += 1
        errors.append(f'{name}: {type(e).__name__}: {e}')
        print(f'  FAIL: {name} - {e}')

# =============================================
# 1. SHORT_SERIES
# =============================================
print()
print('=== 1. short_series.py ===')
from core.short_series import (
    fit_analog_relationship, restore_year, restore_short_series,
    build_protocol, convert_to_module_flow, convert_from_module_flow
)

def test_short_basic():
    np.random.seed(42)
    years = np.arange(1980, 2005)
    calc_years = [1990, 1991, 1992, 1993, 1994]
    Q_calc = pd.Series([15 + 2*np.random.random() for _ in calc_years], index=calc_years)
    analogs = {f'P{i}': pd.Series(np.random.normal(100, 15, 25), index=years) for i in range(5)}
    result = restore_short_series(Q_calc, analogs, list(analogs.keys()), min_analogs=3)
    assert result['n_restored'] > 0, 'No years restored'
    assert result['n_restored'] == len(result['missing_years']), 'Missing years mismatch'

test('short_basic', test_short_basic)

def test_short_protocol():
    np.random.seed(42)
    years = np.arange(1980, 2005)
    Q_calc = pd.Series([15, 16, 17, 18, 19], index=[1990,1991,1992,1993,1994])
    analogs = {f'P{i}': pd.Series(np.random.normal(100, 15, 25), index=years) for i in range(5)}
    result = restore_short_series(Q_calc, analogs, list(analogs.keys()), min_analogs=3)
    protocol = build_protocol(result)
    assert 'restore' in protocol.lower() or len(protocol) > 100, 'Protocol too short'

test('short_protocol', test_short_protocol)

def test_short_module_flow():
    Q = pd.Series([10.0, 20.0], index=[2000, 2001])
    q = convert_to_module_flow(Q, F=500.0)
    Q_back = convert_from_module_flow(q, F=500.0)
    assert abs(Q_back.iloc[0] - 10.0) < 0.01, 'Module flow conversion error'

test('short_module_flow', test_short_module_flow)

# =============================================
# 2. HOMOGENEITY
# =============================================
print()
print('=== 2. homogeneity.py ===')
from core.stats.homogeneity import (
    check_homogeneity_full, batch_homogeneity_check, stationarity_test,
    grubbs_test, dixon_q_test, check_homogeneity
)

def test_homogeneity_clean():
    np.random.seed(42)
    data = np.random.normal(100, 15, 30)
    r = check_homogeneity_full(data, alpha=0.05)
    assert r['n'] == 30, f'Wrong n: {r["n"]}'
    assert len(r['criteria']) == 7, f'Wrong criteria count: {len(r["criteria"])}'

test('homogeneity_clean', test_homogeneity_clean)

def test_homogeneity_outlier():
    np.random.seed(42)
    data = np.random.normal(100, 15, 30)
    data[5] = 200
    r = check_homogeneity_full(data, alpha=0.05)
    assert r['n_heterogeneous'] > 0, 'Outlier not detected'

test('homogeneity_outlier', test_homogeneity_outlier)

def test_homogeneity_batch():
    np.random.seed(42)
    data = np.column_stack([np.random.normal(100, 15, 30) for _ in range(4)])
    batch = batch_homogeneity_check(data, alpha=0.05, min_length=20)
    assert len(batch) == 4, f'Wrong batch count: {len(batch)}'

test('homogeneity_batch', test_homogeneity_batch)

def test_stationarity():
    np.random.seed(42)
    data = np.random.normal(100, 15, 30)
    r = stationarity_test(data)
    assert 't_test' in r, 'No t_test'
    assert 'f_test' in r, 'No f_test'
    assert 'is_stationary' in r, 'No is_stationary'

test('stationarity', test_stationarity)

def test_homogeneity_compat():
    np.random.seed(42)
    data = np.random.normal(100, 15, 30)
    g = grubbs_test(data)
    d = dixon_q_test(data)
    old = check_homogeneity(data)
    assert 'G' in g, 'No G in grubbs'
    assert 'Q' in d, 'No Q in dixon'
    assert 'is_homogeneous' in old, 'No is_homogeneous'

test('homogeneity_compat', test_homogeneity_compat)

# =============================================
# 3. FREQUENCY
# =============================================
print()
print('=== 3. frequency.py ===')
from core.stats.frequency import (
    calculate_frequency_curve, auto_select_cs_cv, pearson3_ppf,
    kritsky_menkel_ppf, HistoricalExtreme, compute_params_with_extremes
)

def test_frequency_types():
    np.random.seed(42)
    data = np.random.gamma(2, 50, 50)
    for ct in ['pearson3', 'kritsky_menkel', 'normal', 'empirical', 'piecewise']:
        df = calculate_frequency_curve(data, curve_type=ct)
        assert 'P_%' in df.columns, f'Missing P_% in {ct}'
        assert 'Q' in df.columns, f'Missing Q in {ct}'

test('frequency_types', test_frequency_types)

def test_auto_cs_cv():
    np.random.seed(42)
    data = np.random.gamma(2, 50, 50)
    r = auto_select_cs_cv(data)
    assert r['cs_cv_optimal'] is not None, 'Cs/Cv not found'
    assert r['ss_min'] < float('inf'), 'SS not finite'

test('auto_cs_cv', test_auto_cs_cv)

def test_pearson3_ppf():
    p = np.array([0.01, 0.05, 0.5, 0.95, 0.99])
    q = pearson3_ppf(p, 100, 0.2, 0.5)
    assert len(q) == 5, f'Wrong length: {len(q)}'
    assert q[0] > q[4], 'Monotonicity violated'

test('pearson3_ppf', test_pearson3_ppf)

def test_kritsky_menkel_ppf():
    p = np.array([0.01, 0.05, 0.5, 0.95, 0.99])
    q = kritsky_menkel_ppf(p, 100, 0.2, 0.5)
    assert len(q) == 5, f'Wrong length: {len(q)}'

test('kritsky_menkel_ppf', test_kritsky_menkel_ppf)

def test_historical_extremes():
    np.random.seed(42)
    data = np.random.gamma(2, 50, 50)
    ext = [HistoricalExtreme(year=1950, value=180, period=100)]
    r = compute_params_with_extremes(data, ext, is_max=True)
    assert r['mean_corrected'] > r['mean_raw'], 'Mean not increased'

test('historical_extremes', test_historical_extremes)

# =============================================
# 4. SERIES_EXTENSION
# =============================================
print()
print('=== 4. series_extension.py ===')
from core.stats.series_extension import (
    get_ro_critical, validate_correlation, regression_extension,
    proportional_extension, compute_integral_curves
)

def test_ro_critical():
    ro = get_ro_critical(20, 0.05)
    assert 0 < ro < 1, f'Wrong Ro: {ro}'

test('ro_critical', test_ro_critical)

def test_validate_correlation():
    np.random.seed(42)
    Q_calc = pd.Series(np.random.normal(100, 15, 30))
    Q_analog = pd.Series(np.random.normal(100, 15, 30))
    r = validate_correlation(Q_calc, Q_analog)
    assert 'R' in r, 'No R'
    assert 'is_significant' in r, 'No is_significant'

test('validate_correlation', test_validate_correlation)

def test_regression():
    np.random.seed(42)
    Q_calc = pd.Series(np.random.normal(100, 15, 30))
    Q_analog = pd.Series(np.random.normal(100, 15, 30))
    r = regression_extension(Q_calc, Q_analog)
    assert 'extended_series' in r, 'No extended_series'

test('regression', test_regression)

def test_integral_curves():
    np.random.seed(42)
    data = pd.Series(np.random.normal(100, 15, 30))
    r = compute_integral_curves(data)
    assert 'integral_curve' in r, 'No integral_curve'
    assert 'diff_integral_curve' in r, 'No diff_integral_curve'
    assert len(r['integral_curve']) == len(data), 'Wrong length'

test('integral_curves', test_integral_curves)

# =============================================
# 5. COMPOSITE_CURVES
# =============================================
print()
print('=== 5. composite_curves.py ===')
from core.stats.composite_curves import (
    compute_composite_curve_rodzhestvensky,
    find_change_point, test_homogeneity_two_parts,
    compute_part_stats, compute_composite_curve
)

def test_rodzhestvensky():
    np.random.seed(42)
    cat1 = {'data': np.random.gamma(2, 30, 20), 'name': 'A'}
    cat2 = {'data': np.random.gamma(3, 20, 15), 'name': 'B'}
    r = compute_composite_curve_rodzhestvensky([cat1, cat2])
    assert 'error' not in r, f'Error: {r.get("error")}'
    assert r['total_years'] == 35, f'Wrong N: {r["total_years"]}'

test('rodzhestvensky', test_rodzhestvensky)

def test_change_point():
    np.random.seed(42)
    data = np.concatenate([np.random.normal(100, 10, 20), np.random.normal(120, 10, 20)])
    r = find_change_point(data)
    assert 'change_year' in r, 'No change_year'

test('change_point', test_change_point)

def test_homogeneity_two_parts_func():
    np.random.seed(42)
    data = np.concatenate([np.random.normal(100, 10, 20), np.random.normal(120, 10, 20)])
    r = test_homogeneity_two_parts(data[:20], data[20:])
    assert 'is_homogeneous' in r, 'No is_homogeneous'

test('homogeneity_two_parts', test_homogeneity_two_parts_func)

def test_part_stats():
    np.random.seed(42)
    data = np.random.normal(100, 15, 20)
    r = compute_part_stats(data)
    assert r['n'] == 20, f'Wrong n: {r["n"]}'
    assert r['mean'] > 0, f'Wrong mean: {r["mean"]}'

test('part_stats', test_part_stats)

def test_composite_old():
    np.random.seed(42)
    values = np.random.normal(100, 15, 30)
    years = np.arange(30)
    r = compute_composite_curve(values, years, break_year=15)
    assert 'curve_df' in r, 'No curve_df'

test('composite_old', test_composite_old)

# =============================================
# 6. PARAMETERS
# =============================================
print()
print('=== 6. parameters.py ===')
from core.stats.parameters import calculate_statistical_parameters

def test_parameters():
    np.random.seed(42)
    data = np.random.normal(100, 15, 30)
    p = calculate_statistical_parameters(data)
    assert p['n'] == 30, f'Wrong n: {p["n"]}'
    assert abs(p['mean'] - 100) < 5, f'Wrong mean: {p["mean"]}'
    assert 0 < p['cv'] < 1, f'Wrong cv: {p["cv"]}'

test('parameters', test_parameters)

# =============================================
# 7. COMPLEX INTEGRATION
# =============================================
print()
print('=== 7. Complex integration test ===')

def test_complex():
    np.random.seed(42)
    years = np.arange(1960, 2020)
    n = len(years)
    data = pd.Series(np.random.normal(100, 15, n), index=years)

    # All features together
    params = calculate_statistical_parameters(data.values)
    curve = calculate_frequency_curve(data.values, curve_type='pearson3')
    cs_cv = auto_select_cs_cv(data.values)
    homo = check_homogeneity_full(data.values)
    stat = stationarity_test(data.values, years=years)
    integral = compute_integral_curves(data)
    short = data.iloc[:5]
    analogs = {f'A{i}': pd.Series(np.random.normal(100, 15, n), index=years) for i in range(5)}
    result_short = restore_short_series(short, analogs, list(analogs.keys()), min_analogs=3)
    ext = [HistoricalExtreme(year=1950, value=180, period=100)]
    r_ext = compute_params_with_extremes(data.values, ext)
    cat1 = {'data': data[data > data.median()].values, 'name': 'High'}
    cat2 = {'data': data[data <= data.median()].values, 'name': 'Low'}
    r_comp = compute_composite_curve_rodzhestvensky([cat1, cat2])

test('complex', test_complex)

# =============================================
# RESULTS
# =============================================
print()
print('=' * 70)
print(f'PASSED: {passed}')
print(f'FAILED: {failed}')
if errors:
    print()
    print('ERRORS:')
    for e in errors:
        print(f'  {e}')
print('=' * 70)
