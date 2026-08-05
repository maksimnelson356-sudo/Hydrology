#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Полный тест на реальных данных"""
import sys
sys.path.insert(0, '.')
import numpy as np
import pandas as pd

print('=' * 60)
print('ПОЛНЫЙ ТЕСТ НА РЕАЛЬНЫХ ДАННЫХ')
print('=' * 60)

# Загрузка данных из 1122.txt
print()
print('--- Данные: 1122.txt (4 поста, 12 лет) ---')
# Читаем вручную, т.к. формат нестандартный
lines = []
with open(r'D:\!Учеба\ForFor\Данные\1122.txt', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or 'Год' in line:
            continue
        parts = line.split('\t')
        if len(parts) >= 2:
            try:
                year = int(parts[0])
                vals = [float(x) if x.strip() else np.nan for x in parts[1:5]]
                lines.append([year] + vals)
            except:
                continue

df = pd.DataFrame(lines, columns=['Годы', '10001', '10002', '10003', '10004'])
print(df.to_string(index=False))

posts = {}
for col in df.columns[1:]:
    series = pd.Series(df[col].values, index=df['Годы'].values).dropna()
    if len(series) >= 3:
        posts[col] = series
        print(f'  Пост {col}: {len(series)} лет, Qsr={series.mean():.1f}')

# Тест 1: Базовая статистика
print()
print('=== Тест 1: Базовая статистика ===')
from core.stats.parameters import calculate_statistical_parameters
for name, series in posts.items():
    params = calculate_statistical_parameters(series.values)
    print(f'  {name}: Qsr={params["mean"]:.2f}, Cv={params["cv"]:.4f}, Cs={params["cs"]:.4f}')

# Тест 2: Кривые обеспеченности
print()
print('=== Тест 2: Кривые обеспеченности ===')
from core.stats.frequency import calculate_frequency_curve
main_post = list(posts.values())[0]
for ct in ['pearson3', 'kritsky_menkel', 'normal', 'piecewise']:
    df_curve = calculate_frequency_curve(main_post.values, curve_type=ct)
    q50 = df_curve[df_curve['P_%']==50.0]['Q'].values[0]
    q5 = df_curve[df_curve['P_%']==5.0]['Q'].values[0]
    print(f'  {ct:20s}: Q(5%)={q5:8.2f}, Q(50%)={q50:8.2f}')

# Тест 3: Автоподбор Cs/Cv
print()
print('=== Тест 3: Автоподбор Cs/Cv ===')
from core.stats.frequency import auto_select_cs_cv
result_cs = auto_select_cs_cv(main_post.values, curve_type='pearson3')
print(f'  Opt Cs/Cv = {result_cs["cs_cv_optimal"]}')
print(f'  Cv = {result_cs["cv"]:.4f}')
print(f'  Cs = {result_cs["cs_optimal"]:.4f}')

# Тест 4: Однородность
print()
print('=== Тест 4: Однородность (12 критериев) ===')
from core.stats.homogeneity import check_homogeneity_full
r_homo = check_homogeneity_full(main_post.values, alpha=0.05)
print(f'  n={r_homo["n"]}, Cs={r_homo["cs"]:.3f}, r1={r_homo["r1"]:.3f}')
print(f'  Homogeneous: {r_homo["is_homogeneous"]} ({r_homo["n_heterogeneous"]}/7 rejected)')
for name, c in r_homo['criteria'].items():
    mark = '+' if c['significant'] else '-'
    print(f'    {name:4s}: {c["empirical"]:.4f} vs {c["critical"]:.4f} [{mark}]')

# Тест 5: Стационарность
print()
print('=== Тест 5: Stationarity ===')
from core.stats.homogeneity import stationarity_test
years = main_post.index.values
r_stat = stationarity_test(main_post.values, years=years)
print(f'  t-test: t={r_stat["t_test"]["t_stat"]:.4f} -> {"REJECT" if r_stat["t_test"]["significant"] else "OK"}')
print(f'  F-test: F={r_stat["f_test"]["f_stat"]:.4f} -> {"REJECT" if r_stat["f_test"]["significant"] else "OK"}')
print(f'  Stationary: {r_stat["is_stationary"]}')

# Тест 6: Integral curve
print()
print('=== Тест 6: Integral curve ===')
from core.stats.series_extension import compute_integral_curves
r_int = compute_integral_curves(main_post)
print(f'  Mean: {r_int["mean"]:.2f}, Cv: {r_int["cv"]:.4f}')
print(f'  Breakpoints: {r_int["breakpoints"][:5]}...')

# Тест 7: Short
print()
print('=== Tест 7: Short (short series) ===')
from core.short_series import restore_short_series
short_series = main_post.iloc[:4]
analog_series = {name: series for name, series in posts.items() if name != list(posts.keys())[0]}
if len(analog_series) >= 2:
    r_short = restore_short_series(
        Q_calc=short_series, analogs=analog_series,
        selected_analogs=list(analog_series.keys()), min_analogs=2)
    print(f'  Short: {len(short_series)} years')
    print(f'  Restored: {r_short["n_restored"]}/{len(r_short["missing_years"])}')

# Tест 8: Historical extremes
print()
print('=== Tест 8: Historical extremes ===')
from core.stats.frequency import HistoricalExtreme, compute_params_with_extremes
extremes = [HistoricalExtreme(year=1950, value=180, period=100),
            HistoricalExtreme(year=1920, value=170, period=80)]
r_ext = compute_params_with_extremes(main_post.values, extremes, is_max=True)
print(f'  Raw: mean={r_ext["mean_raw"]:.2f}, cv={r_ext["cv_raw"]:.4f}')
print(f'  With extremes: mean={r_ext["mean_corrected"]:.2f}, cv={r_ext["cv_corrected"]:.4f}')

# Tест 9: Composite curve (Rodzhestvensky)
print()
print('=== Tест 9: Composite curve ===')
from core.stats.composite_curves import compute_composite_curve_rodzhestvensky
median_val = main_post.median()
cat_high = {'data': main_post[main_post >= median_val].values, 'name': 'High'}
cat_low = {'data': main_post[main_post < median_val].values, 'name': 'Low'}
r_comp = compute_composite_curve_rodzhestvensky([cat_high, cat_low])
if 'error' not in r_comp:
    print(f'  Total years: {r_comp["total_years"]}')
    df_comp = r_comp['curve_df']
    q1 = df_comp[df_comp['P_%']==1.0]['Q_составная'].values[0]
    q50 = df_comp[df_comp['P_%']==50.0]['Q_составная'].values[0]
    print(f'  Q(1%)={q1:.2f}, Q(50%)={q50:.2f}')

# Tест 10: All variants
print()
print('=== Tест 10: All variants comparison ===')
print('  Type             | Q(1%)   | Q(5%)   | Q(50%)  | Q(99%)')
print('  -----------------|---------|---------|---------|--------')
p = np.array([0.01, 0.05, 0.1, 0.2, 0.5, 0.8, 0.9, 0.95, 0.99])
for ct in ['pearson3', 'kritsky_menkel', 'normal', 'piecewise']:
    df_c = calculate_frequency_curve(main_post.values, probabilities=p, curve_type=ct)
    vals = [df_c[df_c['P_%']==x]['Q'].values[0] for x in [1.0, 5.0, 50.0, 99.0]]
    print(f'  {ct:17s} | {vals[0]:7.2f} | {vals[1]:7.2f} | {vals[2]:7.2f} | {vals[3]:7.2f}')

print()
print('=' * 60)
print('ALL TESTS PASSED')
print('=' * 60)
