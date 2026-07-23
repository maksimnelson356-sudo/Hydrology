"""
create_test_data.py
Генерация чистого тестового файла для проверки кривых обеспеченности
"""

import pandas as pd
import numpy as np
from scipy import stats

# Параметры распределения (близко к реальным расходам)
mean = 140
cv = 0.35
skew = 0.8          # умеренная положительная асимметрия

n_years = 60
years = np.arange(1960, 1960 + n_years)

# Генерируем данные через гамма-распределение (хорошо описывает расходы)
shape = 4 / (cv ** 2)
scale = mean / shape

np.random.seed(42)  # для воспроизводимости
values = stats.gamma.rvs(a=shape, scale=scale, size=n_years)

# Добавляем небольшой тренд и шум (чтобы было реалистично)
trend = np.linspace(0, 15, n_years)
values = values + trend + np.random.normal(0, 8, n_years)

# Делаем положительными
values = np.maximum(values, 30)

# Создаём DataFrame в формате, как у тебя
df = pd.DataFrame({
    'Год': years,
    '10001': np.round(values, 1),
    '10002': np.round(values * 0.85 + np.random.normal(0, 12, n_years), 1),
    '10003': np.round(values * 1.15 + np.random.normal(0, 15, n_years), 1)
})

# Добавляем немного пропусков (для теста восстановления)
df.loc[5:7, '10002'] = np.nan
df.loc[20, '10003'] = np.nan
df.loc[45:47, '10001'] = np.nan

# Сохраняем
output_path = "test_data_clean.xlsx"
df.to_excel(output_path, index=False)

print(f"Файл создан: {output_path}")
print(f"Количество лет: {n_years}")
print(f"Среднее по посту 10001: {df['10001'].mean():.1f}")
print(f"Cv по посту 10001: {df['10001'].std() / df['10001'].mean():.3f}")
print("\nПервые 10 строк:")
print(df.head(10))