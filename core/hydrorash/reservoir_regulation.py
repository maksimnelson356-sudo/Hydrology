"""
core/hydrorash/reservoir_regulation.py
Многолетнее регулирование стока — СП 58.13330.2019, СП 33-101-2003/СП 33.13330.2016

Основные функции:
- multi_year_regulation — расчёт полезного объёма и гарантии для многолетнего регулирования
- storage_yield_curve — кривая «объём — гарантированная отдача»
- reservoir_storage_calculation — расчёт объёма водохранилища
- annual_regulation_table — таблица годового регулирования
"""

import numpy as np
import pandas as pd

# Константа: секунды в году (СП 33 использует 365 дней)
SECONDS_PER_YEAR = 365 * 86400


def multi_year_regulation(
    Q_annual: np.ndarray,
    demand_m3_s: float,
    V_max_km3: float | None = None,
    S_0_km3: float | None = None,
    target_guarantee: float = 95.0,
    mode: str = "natural_supply",
) -> dict:
    """
    Многолетнее регулирование стока — метод Риппла (СП 58.13330.2019, СП 33-101-2003 п.7).

    Режимы работы:
    - guarantee_for_volume: даны V_max, D — вычислить гарантию и требуемый объём
    - volume_for_guarantee: даны D, целевая гарантия — найти необходимый V_max
    - natural_supply: только статистика исходного ряда (обратная совместимость)

    Метод Риппла (СП 33-101-2003 п.7.2, СП 58 Прил. Б):
    Последовательный водохозяйственный баланс:
    S_{i+1} = min(V_max, max(0, S_i + (Q_i - D) * T))

    Гарантия водоснабжения (СП 33 п.7.3):
    guarantee = (N - N_def) / N * 100%
    где N_def — число лет с S_i = 0 (дефицитный год)

    Parameters:
        Q_annual: среднегодовые расходы за ряд лет, м3/с
        demand_m3_s: среднегодовой забор (потребление), м3/с
        V_max_km3: полезный объём водохранилища, км³ (обязателен для режимов регулирования)
        S_0_km3: начальный запас в водохранилище, км³ (по умолчанию = V_max)
        target_guarantee: целевая гарантия водоснабжения, % (для mode=volume_for_guarantee)
        mode: режим работы
            - "guarantee_for_volume": даны V_max, D — вычислить гарантию
            - "volume_for_guarantee": даны D, target_guarantee — найти V_max
            - "natural_supply": только статистика P(Q >= D) (обратная совместимость)

    Returns:
        Dict с результатами расчёта
    """
    Q = np.array(Q_annual, dtype=float)
    Q = Q[~np.isnan(Q)]
    n = len(Q)

    if n == 0:
        raise ValueError("Ряд притоков не может быть пустым")

    Q_mean = float(np.mean(Q))
    Q_min = float(np.min(Q))

    # Проверка забора
    if demand_m3_s <= 0:
        raise ValueError("Забор должен быть положительным")

    # Режим обратной совместимости: только статистика исходного ряда
    if mode == "natural_supply":
        guarantee = float((Q >= demand_m3_s).mean() * 100) if n > 0 else 0
        natural_supply = guarantee

        # Метод Риппла для оценки требуемого объёма (S_0 = 0, V_max = inf)
        # V_ripple = max_{j>i} (C_i - C_j) * T, где C_0 = 0, C_k = sum_{m=1}^k (Q_m - D)
        Q_D = Q - demand_m3_s
        max_C = 0.0  # C_0 = 0
        c = 0.0  # C_0 = 0 (актуальная накопленная сумма)
        max_drawdown = 0.0
        for q_d in Q_D:
            c = c + q_d
            drawdown = max_C - c
            if drawdown > max_drawdown:
                max_drawdown = drawdown
            if c > max_C:
                max_C = c
        V_ripple_m3 = max_drawdown * SECONDS_PER_YEAR
        V_ripple_km3 = V_ripple_m3 / 1e9

        return {
            'required_volume_km3': round(V_ripple_km3, 3),
            'required_volume_mln_m3': round(V_ripple_m3 / 1e6, 1),
            'guarantee_percent': round(guarantee, 1),
            'natural_supply_percent': round(natural_supply, 1),
            'Q_mean': round(Q_mean, 2),
            'Q_demand': round(demand_m3_s, 2),
            'deficit_fraction': round(float(max_drawdown) / Q_mean, 3) if Q_mean > 0 else 0,
            'balance_cumulative': np.cumsum(Q - demand_m3_s).tolist(),
            'warning': 'Режим natural_supply: гарантия = P(Q >= D), не учитывает регулирование!' if demand_m3_s <= Q_mean else 'Забор > среднего стока! Нужно много летнее регулирование.',
        }

# Для режима volume_for_guarantee V_max не требуется на входе (будет найден)
    if mode == "volume_for_guarantee":
        V_max = None
    else:
        # Для режима guarantee_for_volume V_max обязателен
        if V_max_km3 is None:
            raise ValueError("Для режима 'guarantee_for_volume' параметр V_max_km3 обязателен")
        V_max = V_max_km3 * 1e9  # м³
        if V_max <= 0:
            raise ValueError("V_max должен быть положительным")

    # Валидация S_0 (только для режимов с V_max)
    if mode != "volume_for_guarantee":
        S_0 = V_max if S_0_km3 is None else S_0_km3 * 1e9
        if not (0 <= S_0 <= V_max):
            raise ValueError("S_0 должен быть в диапазоне [0, V_max]")
    else:
        S_0 = None

    if not (0 < target_guarantee <= 100):
        raise ValueError("target_guarantee должен быть в (0, 100]")

    D = demand_m3_s
    T = SECONDS_PER_YEAR

    if mode == "guarantee_for_volume":
        # Даны V_max, D — вычислить гарантию
        S = S_0
        deficit_years = 0
        balance_series = [S_0 / 1e9]  # в км³ для удобства

        for Q_i in Q:
            S = min(V_max, max(0.0, S + (Q_i - D) * T))
            balance_series.append(S / 1e9)
            if S == 0:
                deficit_years += 1

        guarantee = (n - deficit_years) / n * 100

        # Метод Риппла для требуемого объёма (при S_0=0)
        # V_ripple = max_{j>i} (C_i - C_j) * T, где C_0 = 0, C_k = sum_{m=1}^k (Q_m - D)
        Q_D = Q - D
        max_C = 0.0  # C_0 = 0
        c = 0.0  # C_0 = 0 (актуальная накопленная сумма)
        max_drawdown = 0.0
        for q_d in Q_D:
            c = c + q_d
            drawdown = max_C - c
            if drawdown > max_drawdown:
                max_drawdown = drawdown
            if c > max_C:
                max_C = c
        V_ripple_m3 = max_drawdown * T

        return {
            'required_volume_km3': round(V_ripple_m3 / 1e9, 3),
            'required_volume_mln_m3': round(V_ripple_m3 / 1e6, 1),
            'guarantee_percent': round(guarantee, 1),
            'deficit_years': deficit_years,
            'Q_mean': round(Q_mean, 2),
            'Q_demand': round(D, 2),
            'deficit_fraction': round(float(max_drawdown) / Q_mean, 3) if Q_mean > 0 else 0,
            'balance_cumulative': np.cumsum(Q - D).tolist(),
            'balance_series_km3': balance_series,
            'V_max_km3': round(V_max / 1e9, 3),
            'S_0_km3': round(S_0 / 1e9, 3),
            'target_guarantee': target_guarantee,
        }

    elif mode == "volume_for_guarantee":
        # Даны D, target_guarantee — найти V_max (бинарный поиск)
        if D >= Q_mean:
            raise ValueError("Для mode=volume_for_guarantee забор должен быть < среднего притока")

        # Нижняя граница: 0
        # Верхняя граница: оценка по методу Риппла + запас
        Q_D = Q - D
        max_C = 0.0  # C_0 = 0
        c = 0.0  # C_0 = 0 (актуальная накопленная сумма)
        max_drawdown = 0.0
        for q_d in Q_D:
            c = c + q_d
            drawdown = max_C - c
            if drawdown > max_drawdown:
                max_drawdown = drawdown
            if c > max_C:
                max_C = c
        V_upper = max_drawdown * T * 2  # с запасом 2x

        if V_upper <= 0:
            V_upper = (Q_mean - D) * T * 1.5  # fallback

        # Бинарный поиск
        V_low = 0.0
        V_high = V_upper
        best_V = V_high

        for _ in range(50):  # достаточно для точности ~1e-15
            if V_high - V_low < 1e6:  # 1 млн м³ = 0.001 км³
                break

            V_mid = (V_low + V_high) / 2

            # Проверка гарантии для V_mid
            S = V_mid  # S_0 = V_max
            deficit_years = 0
            for Q_i in Q:
                S = min(V_mid, max(0.0, S + (Q_i - D) * T))
                if S == 0:
                    deficit_years += 1

            guarantee = (n - deficit_years) / n * 100

            if guarantee >= target_guarantee:
                best_V = V_mid
                V_high = V_mid
            else:
                V_low = V_mid

        # Финальная проверка для best_V
        S = best_V
        deficit_years = 0
        for Q_i in Q:
            S = min(best_V, max(0.0, S + (Q_i - D) * T))
            if S == 0:
                deficit_years += 1

        guarantee = (n - deficit_years) / n * 100

        return {
            'required_volume_km3': round(best_V / 1e9, 3),
            'required_volume_mln_m3': round(best_V / 1e6, 1),
            'guarantee_percent': round(guarantee, 1),
            'deficit_years': deficit_years,
            'Q_mean': round(Q_mean, 2),
            'Q_demand': round(D, 2),
            'target_guarantee': target_guarantee,
            'achieved_guarantee': round(guarantee, 1),
        }

    else:
        raise ValueError(f"Неизвестный mode: {mode}. Доступные: 'guarantee_for_volume', 'volume_for_guarantee', 'natural_supply'")


def storage_yield_curve(
    Q_annual: np.ndarray,
    V_range_km3: list[float] | None = None,
    target_guarantee: float = 95.0,
) -> pd.DataFrame:
    """
    Кривая «объём водохранилища — гарантированная отдача» (СП 58, СП 33 п.7.3).

    Для каждого объёма V_max определяем максимальную гарантированную отдачу D
    при заданной целевой гарантии водоснабжения.

    Parameters:
        Q_annual: среднегодовые расходы
        V_range_km3: список объёмов для расчёта, км³
        target_guarantee: целевая гарантия водоснабжения, % (обычно 95 или 97)

    Returns:
        DataFrame: V_km3, Q_max_demand (гарантированная отдача), achieved_guarantee
    """
    if V_range_km3 is None:
        V_range_km3 = [0.1, 0.5, 1, 2, 3, 5, 8, 10, 15, 20]

    Q = np.array(Q_annual, dtype=float)
    Q = Q[~np.isnan(Q)]
    Q_mean = float(np.mean(Q))

    if Q_mean <= 0:
        raise ValueError("Средний приток должен быть положительным")

    if not (0 < target_guarantee <= 100):
        raise ValueError("target_guarantee должен быть в (0, 100]")

    rows = []
    for V_km3 in V_range_km3:
        # Для данного V_max находим максимальную D при target_guarantee
        # Используем mode=volume_for_guarantee
        try:
            res = multi_year_regulation(
                Q,
                demand_m3_s=Q_mean * 0.5,  # начальная оценка
                V_max_km3=V_km3,
                target_guarantee=target_guarantee,
                mode="volume_for_guarantee",
            )
            best_demand = res['required_volume_km3']  # В этом режиме возвращает V_max
            # Используем найденный D из результата
            # Но multi_year_regulation в этом режиме возвращает V_max, а не D
            # Нужно отдельно найти D для данного V_max
        except (ValueError, KeyError):
            # Fallback: ищем D вручную через бинарный поиск
            pass

        # Правильный подход: для данного V_max найти максимальную D
        # такую, что guarantee_for_volume(V_max, D) >= target_guarantee
        V_max = V_km3 * 1e9
        T = SECONDS_PER_YEAR

        # Бинарный поиск D ∈ (0, Q_mean)
        D_low = 0.0
        D_high = Q_mean
        best_D = 0.0

        for _ in range(40):
            if D_high - D_low < 1e-3:  # точность 0.001 м³/с
                break

            D_mid = (D_low + D_high) / 2

            # Проверка гарантии для D_mid
            S = V_max  # S_0 = V_max
            deficit_years = 0
            for Q_i in Q:
                S = min(V_max, max(0.0, S + (Q_i - D_mid) * SECONDS_PER_YEAR))
                if S == 0:
                    deficit_years += 1

            guarantee = (len(Q) - deficit_years) / len(Q) * 100

            if guarantee >= target_guarantee:
                best_D = D_mid
                D_low = D_mid
            else:
                D_high = D_mid

        # Финальная проверка
        S = V_max
        deficit_years = 0
        for Q_i in Q:
            S = min(V_max, max(0.0, S + (Q_i - best_D) * SECONDS_PER_YEAR))
            if S == 0:
                deficit_years += 1

        guarantee = (len(Q) - deficit_years) / len(Q) * 100

        rows.append({
            'V_km3': V_km3,
            'Q_max_demand': round(best_D, 2),
            'achieved_guarantee': round(guarantee, 1),
            'target_guarantee': target_guarantee,
        })

    return pd.DataFrame(rows)


def reservoir_storage_calculation(
    H_list: list[float],
    A_list: list[float],
    method: str = 'trapezoid',
) -> dict:
    """
    Объём водохранилища по данным нивелировки (кривая «уровень-площадь-объём»).

    Метод трапеций: V_i = (A_i + A_{i+1})/2 × (H_{i+1} - H_i)

    Parameters:
        H_list: уровни, м (по возрастанию)
        A_list: площади зеркала, км²

    Returns:
        Dict: cumulative_volumes, table_df
    """
    H = np.array(H_list)
    A = np.array(A_list)

    # Валидация: H должен быть строго возрастающим
    if len(H) < 2:
        raise ValueError("Нужно минимум 2 уровня")
    if len(H) != len(A):
        raise ValueError("Длины списков H и A должны совпадать")
    if not np.all(np.diff(H) > 0):
        raise ValueError("Уровни H должны быть строго возрастающими")

    V_cumulative = [0.0]
    for i in range(1, len(H)):
        dV = (A[i - 1] + A[i]) / 2 * (H[i] - H[i - 1]) / 1000.0
        V_cumulative.append(V_cumulative[-1] + dV)

    df = pd.DataFrame({
        'H_m': H,
        'A_km2': A,
        'V_cumulative_km3': [round(v, 4) for v in V_cumulative],
    })

    return {
        'table': df,
        'V_total_km3': round(float(V_cumulative[-1]), 4),
    }


def annual_regulation_table(
    Q_monthly: np.ndarray,
    demand_m3_s: float,
    V_useful_km3: float = 1.0,
) -> pd.DataFrame:
    """
    Таблица годового регулирования (месячный баланс).

    Parameters:
        Q_monthly: 12 средних месячных расходов, м3/с
        demand_m3_s: средний забор, м3/с
        V_useful_km3: полезный объём, км³

    Returns:
        DataFrame с месячным балансом
    """
    months = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
              'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']

    days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

    rows = []
    V_balance = 0
    for i, (m, d) in enumerate(zip(months, days)):
        Q_in = Q_monthly[i] if i < len(Q_monthly) else 0
        Q_out = demand_m3_s
        dV = (Q_in - Q_out) * d * 86400 / 1e9
        V_balance += dV

        rows.append({
            'Месяц': m,
            'Q_приток': round(Q_in, 2),
            'Q_забор': round(Q_out, 2),
            'dV_km3': round(dV, 4),
            'V_баланс_km3': round(V_balance, 4),
            'Заполнен_%': round(V_balance / V_useful_km3 * 100, 1) if V_useful_km3 > 0 else 0,
        })

    return pd.DataFrame(rows)
