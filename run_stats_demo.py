"""
run_stats_demo.py
Полноценная демонстрация статистической обработки
"""

import numpy as np
import pandas as pd
from core.stats.data_loader import load_hydrological_data, get_series_by_post, get_basic_stats
from core.stats.frequency import calculate_frequency_curve, fit_pearson3
from core.stats.missing_data import detect_missing, fill_missing_interpolation
from core.stats.report import save_report_to_excel
from core.stats.parameters import calculate_statistical_parameters

print("=" * 80)
print("ПОЛНОЦЕННАЯ ДЕМОНСТРАЦИЯ СТАТИСТИЧЕСКОЙ ОБРАБОТКИ")
print("=" * 80)

excel_file = "test_data_clean.xlsx"

# ==================== ЗАГРУЗКА ====================
try:
    df_raw, year_col, available_posts = load_hydrological_data(excel_file)
    print(f"\nЗагружен файл: {excel_file}")
    print(f"Столбец с годами: {year_col}")
    print(f"Доступные посты: {available_posts}")

    # Берём первый пост
    post_name = available_posts[0]
    df = get_series_by_post(df_raw, year_col, post_name)
    print(f"Выбран пост: {post_name}")
    print(f"Значений: {len(df)}")
except FileNotFoundError:
    print(f"\nФайл {excel_file} не найден.")
    print("Создайте тестовые данные через create_test_data.py")
    exit()

# ==================== АНАЛИЗ ПРОПУСКОВ ====================
missing_count = detect_missing(df, 'value')
if len(df) > 0:
    print(f"\nПропущено значений: {missing_count} ({missing_count / len(df) * 100:.1f}%)")
else:
    print("\nНет данных для анализа пропусков.")

# ==================== ЗАПОЛНЕНИЕ ПРОПУСКОВ ====================
df_filled = fill_missing_interpolation(df, target_col='value')

# ==================== БАЗОВАЯ СТАТИСТИКА ====================
stats = get_basic_stats(df_filled)
print("\n--- Базовая статистика ---")
for k, v in stats.items():
    print(f"  {k:20}: {v}")

# ==================== ПАРАМЕТРЫ РАСПРЕДЕЛЕНИЯ ====================
params = calculate_statistical_parameters(df_filled['value'].values)
print("\n--- Параметры распределения ---")
print(f"  Среднее (X̄)         : {params['mean']}")
print(f"  Cv                  : {params['cv']}")
print(f"  Cs                  : {params['cs']}")
print(f"  Cv_скоррект.        : {params['corrected_cv']}")
print(f"  n                   : {params['n']}")
print(f"  r₁ (автокорр.)      : {params['r1']}")

# ==================== ПАРАМЕТРЫ ПИРСОНА III ====================
p3 = fit_pearson3(df_filled['value'].values)
print("\n--- Параметры Пирсона III ---")
for k, v in p3.items():
    print(f"  {k:15}: {v}")

# ==================== КРИВАЯ ОБЕСПЕЧЕННОСТИ ====================
curve = calculate_frequency_curve(df_filled['value'].values, curve_type="pearson3")
print("\n--- Кривая обеспеченности (Пирсон III, первые 8) ---")
print(curve.head(8).to_string(index=False))

# ==================== КРИВАЯ КРИЦКОГО-МЕНКЕЛЯ ====================
curve_km = calculate_frequency_curve(df_filled['value'].values, curve_type="kritsky_menkel")
print("\n--- Кривая обеспеченности (Крицкий-Менкель, первые 8) ---")
print(curve_km.head(8).to_string(index=False))

# ==================== СОХРАНЕНИЕ ОТЧЁТА ====================
save_report_to_excel(stats, curve, filepath="report_stats.xlsx")

print("\n" + "=" * 80)
print("Готово! Отчёт сохранён в report_stats.xlsx")
print("=" * 80)