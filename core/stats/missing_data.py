"""
core/stats/missing_data.py
Восстановление пропусков методом линейной интерполяции
"""

import numpy as np
import pandas as pd
from scipy import stats


def fill_missing_interpolation(df, target_col='value', params=None):
    """
    Восстановление пропусков линейной интерполяцией.

    Стратегия:
    1. Если данных мало (< ncr) — заполнение медианой
    2. Линейная интерполяция (limit_direction='both')
    3. Оставшиеся NaN — медиана
    """
    if params is None:
        params = {}
    
    min_ncr = params.get('ncr', 10)
    min_ro = params.get('ro', 0.6)
    
    df = df.copy()
    missing_mask = df[target_col].isna()
    
    if not missing_mask.any():
        return df
    
    n_missing = missing_mask.sum()
    n_total = len(df)
    
    # Простая стратегия: если данных мало — заполняем медианой
    if n_total < min_ncr:
        df[target_col] = df[target_col].fillna(df[target_col].median())
        return df
    
    # Заполняем оставшиеся пропуски интерполяцией + небольшой шум
    df[target_col] = df[target_col].interpolate(method='linear', limit_direction='both')
    
    # Если после интерполяции остались NaN — заполняем медианой
    still_missing = df[target_col].isna()
    if still_missing.any():
        df.loc[still_missing, target_col] = df[target_col].median()
    
    return df


def detect_missing(df, col='value'):
    return df[col].isna().sum()


# Обратная совместимость (старое имя функции)
fill_missing_with_regression = fill_missing_interpolation