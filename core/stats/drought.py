"""
core/stats/drought.py
Индексы засухи: SPI, SPEI — СП 32.13330.2018

Основные функции:
- spi_index — стандартный индекс осадков (SPI)
- spei_index — индекс осадков-испарения (SPEI)
- drought_classification — классификация засухи по SPI
- drought_frequency — частота засух
"""

import numpy as np
from scipy import stats
from typing import Dict, List, Optional


def spi_index(
    P: np.ndarray,
    scale: int = 12,
) -> Dict:
    """
    Стандартный индекс осадков (SPI) — McKee et al., 1993.

    SPI = (X_i - X̄) / σ

    где X_i — накопленные осадки за scale месяцев.

    Parameters:
        P: месячные осадки, мм
        scale: масштаб (1, 3, 6, 12 месяцев)

    Returns:
        Dict: spi_values, dates, drought_events
    """
    P = np.array(P, dtype=float)
    P = np.nan_to_num(P, nan=0)

    n = len(P)

    if n < scale:
        return {
            'spi_values': [0] * n,
            'n_drought': 0,
            'warning': f'Недостаточно данных (нужно ≥{scale} месяцев)',
        }

    cumulative = np.convolve(P, np.ones(scale), mode='valid')

    if len(cumulative) < 3:
        return {'spi_values': [0] * n, 'n_drought': 0}

    mean_c = np.mean(cumulative)
    std_c = np.std(cumulative, ddof=1)

    if std_c == 0:
        spi = np.zeros(len(cumulative))
    else:
        spi = (cumulative - mean_c) / std_c

    drought_events = []
    in_drought = False
    drought_start = 0

    for i, s in enumerate(spi):
        if s < -1.0 and not in_drought:
            in_drought = True
            drought_start = i
        elif s >= -1.0 and in_drought:
            in_drought = False
            drought_events.append({
                'start_index': drought_start,
                'end_index': i,
                'min_spi': round(float(np.min(spi[drought_start:i])), 2),
                'duration': i - drought_start,
            })

    spi_padded = np.zeros(n)
    spi_padded[scale - 1:] = spi

    return {
        'spi_values': spi_padded.tolist(),
        'spi_raw': spi.tolist(),
        'scale_months': scale,
        'n_drought': len(drought_events),
        'drought_events': drought_events,
        'mean_precipitation': round(float(mean_c / scale), 1),
        'std_precipitation': round(float(std_c / scale), 1),
    }


def spei_index(
    P: np.ndarray,
    PET: np.ndarray,
    scale: int = 12,
) -> Dict:
    """
    Индекс осадков-испарения (SPEI) — Vicente-Serrano et al., 2010.

    D_i = P_i - PET_i
    SPI на D

    Parameters:
        P: месячные осадки, мм
        PET: месячное испарение (Потенциальное), мм
        scale: масштаб

    Returns:
        Dict: spei_values, water_balance
    """
    P = np.array(P, dtype=float)
    PET = np.array(PET, dtype=float)

    P = np.nan_to_num(P, nan=0)
    PET = np.nan_to_num(PET, nan=0)

    n = min(len(P), len(PET))
    P = P[:n]
    PET = PET[:n]

    D = P - PET

    return spi_index(D, scale)


def drought_classification(spi_value: float) -> Dict:
    """
    Классификация засухи по SPI (WMO).

    Parameters:
        spi_value: значение SPI

    Returns:
        Dict: category, color, description
    """
    if spi_value >= 2.0:
        cat = 'Экстремально влажно'
        color = '#1565C0'
        desc = 'Аномально высокие осадки'
    elif spi_value >= 1.5:
        cat = 'Сильно влажно'
        color = '#42A5F5'
        desc = 'Значительное увлажнение'
    elif spi_value >= 1.0:
        cat = 'Умеренно влажно'
        color = '#90CAF9'
        desc = 'Повышенные осадки'
    elif spi_value >= 0:
        cat = 'Норма'
        color = '#A5D6A7'
        desc = 'В пределах нормы'
    elif spi_value >= -1.0:
        cat = 'Умеренно сухо'
        color = '#FFF176'
        desc = 'Лёгкий дефицит осадков'
    elif spi_value >= -1.5:
        cat = 'Сильно сухо'
        color = '#FF9800'
        desc = 'Засуха'
    elif spi_value >= -2.0:
        cat = 'Экстремально сухо'
        color = '#F44336'
        desc = 'Сильная засуха'
    else:
        cat = 'Рекордная засуха'
        color = '#B71C1C'
        desc = 'Экстремальная засуха'

    return {
        'category': cat,
        'color': color,
        'description': desc,
        'spi': round(float(spi_value), 2),
    }


def drought_frequency(
    spi_values: np.ndarray,
    threshold: float = -1.0,
) -> Dict:
    """
    Частота и длительность засух.

    Parameters:
        spi_values: массив SPI
        threshold: порог для определения засухи

    Returns:
        Dict: n_droughts, mean_duration, max_severity, drought_free_ratio
    """
    spi = np.array(spi_values, dtype=float)
    spi = spi[~np.isnan(spi)]
    n = len(spi)

    in_drought = False
    droughts = []
    current_start = 0
    current_severity = 0

    for i, s in enumerate(spi):
        if s < threshold and not in_drought:
            in_drought = True
            current_start = i
            current_severity = s
        elif s < threshold and in_drought:
            current_severity = min(current_severity, s)
        elif s >= threshold and in_drought:
            in_drought = False
            droughts.append({
                'start': current_start,
                'end': i,
                'duration': i - current_start,
                'severity': round(float(current_severity), 2),
            })

    if in_drought:
        droughts.append({
            'start': current_start,
            'end': n,
            'duration': n - current_start,
            'severity': round(float(current_severity), 2),
        })

    if droughts:
        mean_duration = np.mean([d['duration'] for d in droughts])
        max_severity = min(d['severity'] for d in droughts)
    else:
        mean_duration = 0
        max_severity = 0

    drought_days = sum(d['duration'] for d in droughts)
    drought_free = (n - drought_days) / n * 100 if n > 0 else 100

    return {
        'n_droughts': len(droughts),
        'mean_duration_months': round(float(mean_duration), 1),
        'max_severity': round(float(max_severity), 2),
        'drought_free_percent': round(drought_free, 1),
        'droughts': droughts,
    }
