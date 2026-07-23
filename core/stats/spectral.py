"""
core/stats/spectral.py
Спектральный анализ (FFT) + экспонента Хёрста

Основные функции:
- fft_analysis — быстрое преобразование Фурье
- power_spectrum — энергетический спектр
- hurst_exponent — экспонента Хёрста (оценка долгосрочной памяти)
- find_periodicity — поиск периодичности в ряде
"""

import numpy as np
from typing import Dict, List, Optional


def fft_analysis(
    Q: np.ndarray,
    dt: float = 1.0,
) -> Dict:
    """
    Быстрое преобразование Фурье для временного ряда.

    Parameters:
        Q: временной ряд
        dt: шаг времени (1 = сутки, 1/12 = месяц)

    Returns:
        Dict: frequencies, amplitudes, periods, power
    """
    Q = np.array(Q, dtype=float)
    Q = Q[~np.isnan(Q)]
    Q = Q - np.mean(Q)

    N = len(Q)
    if N < 4:
        return {'frequencies': [], 'amplitudes': [], 'periods': [], 'power': []}

    fft_vals = np.fft.rfft(Q)
    amplitudes = np.abs(fft_vals) * 2 / N
    frequencies = np.fft.rfftfreq(N, d=dt)

    valid = frequencies > 0
    freq = frequencies[valid]
    amp = amplitudes[valid]
    power = amp ** 2
    periods = 1.0 / freq

    return {
        'frequencies': freq.tolist(),
        'amplitudes': amp.tolist(),
        'periods_years': periods.tolist(),
        'power': power.tolist(),
        'n': N,
        'dt': dt,
    }


def power_spectrum(
    Q: np.ndarray,
    dt: float = 1.0,
    window: str = 'hanning',
) -> Dict:
    """
    Энергетический спектр с оконной функцией.

    Parameters:
        Q: временной ряд
        dt: шаг времени
        window: тип окна ('hanning', 'hamming', 'blackman')

    Returns:
        Dict: frequencies, power_density, dominant_period
    """
    Q = np.array(Q, dtype=float)
    Q = Q[~np.isnan(Q)]
    Q = Q - np.mean(Q)

    N = len(Q)

    if window == 'hanning':
        w = np.hanning(N)
    elif window == 'hamming':
        w = np.hamming(N)
    elif window == 'blackman':
        w = np.blackman(N)
    else:
        w = np.ones(N)

    Q_windowed = Q * w
    fft_vals = np.fft.rfft(Q_windowed)

    power = np.abs(fft_vals) ** 2 / N
    frequencies = np.fft.rfftfreq(N, d=dt)

    valid = frequencies > 0
    freq = frequencies[valid]
    pwr = power[valid]
    periods = 1.0 / freq

    if len(pwr) > 0:
        dominant_idx = np.argmax(pwr)
        dominant_period = float(periods[dominant_idx])
    else:
        dominant_period = 0

    return {
        'frequencies': freq.tolist(),
        'power_density': pwr.tolist(),
        'periods_years': periods.tolist(),
        'dominant_period': round(dominant_period, 2),
        'n': N,
    }


def hurst_exponent(
    Q: np.ndarray,
    max_window: Optional[int] = None,
) -> Dict:
    """
    Экспонента Хёрста (метод R/S).

    H > 0.5 —ersistentный ряд (долгосрочная память)
    H = 0.5 — случайное блуждание
    H < 0.5 — антипersistentный

    Parameters:
        Q: временной ряд
        max_window: максимальный размер окна

    Returns:
        Dict: H (экспонента Хёрста), R_over_S, confidence
    """
    Q = np.array(Q, dtype=float)
    Q = Q[~np.isnan(Q)]
    N = len(Q)

    if N < 20:
        return {'H': 0.5, 'R_over_S': 0, 'confidence': 'Недостаточно данных'}

    if max_window is None:
        max_window = N // 4

    windows = []
    RS_values = []

    for w in range(10, max_window + 1, max(1, max_window // 20)):
        if w > N:
            break

        n_blocks = N // w
        if n_blocks < 1:
            continue

        rs_list = []
        for b in range(n_blocks):
            block = Q[b * w:(b + 1) * w]
            mean_b = np.mean(block)
            deviations = np.cumsum(block - mean_b)
            R = np.max(deviations) - np.min(deviations)
            S = np.std(block, ddof=1)
            if S > 0:
                rs_list.append(R / S)

        if rs_list:
            windows.append(w)
            RS_values.append(np.mean(rs_list))

    if len(windows) < 3:
        return {'H': 0.5, 'R_over_S': 0, 'confidence': 'Недостаточно окон'}

    log_n = np.log(windows)
    log_RS = np.log(RS_values)

    coeffs = np.polyfit(log_n, log_RS, 1)
    H = float(coeffs[0])

    if H > 0.65:
        conf = 'Значимая положительная корреляция (ersistentный)'
    elif H > 0.55:
        conf = 'Слабая корреляция (слабо persistentный)'
    elif H > 0.45:
        conf = 'Случайное блуждание'
    elif H > 0.35:
        conf = 'Слабая обратная корреляция'
    else:
        conf = 'Антипersistentный (значимая обратная корреляция)'

    return {
        'H': round(H, 4),
        'R_over_S': round(float(np.mean(RS_values)), 4),
        'confidence': conf,
        'n_windows': len(windows),
    }


def find_periodicity(
    Q: np.ndarray,
    dt: float = 1.0,
    significance_level: float = 0.05,
) -> Dict:
    """
    Поиск значимых периодичностей в ряде.

    Parameters:
        Q: временной ряд
        dt: шаг времени
        significance_level: уровень значимости

    Returns:
        Dict: dominant_periods, spectrum_data
    """
    spectrum = power_spectrum(Q, dt)

    if not spectrum['power_density']:
        return {'dominant_periods': [], 'spectrum': spectrum}

    power = np.array(spectrum['power_density'])
    periods = np.array(spectrum['periods_years'])
    n = len(power)

    if n < 3:
        return {'dominant_periods': [], 'spectrum': spectrum}

    mean_power = np.mean(power)
    std_power = np.std(power)
    threshold = mean_power + 3 * std_power

    significant = np.where(power > threshold)[0]

    dominant = []
    for idx in significant:
        dominant.append({
            'period_years': round(float(periods[idx]), 2),
            'power': round(float(power[idx]), 4),
            'significance': 'high' if power[idx] > threshold else 'moderate',
        })

    dominant.sort(key=lambda x: x['power'], reverse=True)

    return {
        'dominant_periods': dominant[:5],
        'threshold': round(float(threshold), 4),
        'n_significant': len(dominant),
        'spectrum': spectrum,
    }
