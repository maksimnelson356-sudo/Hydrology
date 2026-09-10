"""
core/hydrorash/backwater.py
Кривые подпора (ГВП) — СП 33-101-2003

Основные функции:
- backwater_curve_step — расчёт ГВП методом последовательных сечений
- normal_depth — нормальная глубина (Маннинг)
- critical_depth — критическая глубина
- backwater_from_reservoir — линия подпора от водохранилища
"""


import numpy as np
from scipy.optimize import brentq


def normal_depth(
    Q: float,
    B: float,
    m: float,
    n: float,
    I: float,
) -> float:
    """
    Нормальная глубина (Маннинг).

    Q = (1/n) × ω × R^(2/3) × sqrt(I)

    Решаем уравнение Маннинга через brentq (bracketing метод).

    Parameters:
        Q: расход, м3/с
        B: ширина русла, м
        m: откос (1:m, b=1 — трапеция)
        n: коэффициент шероховатости Маннинга
        I: уклон, м/м

    Returns:
        Нормальная глубина, м
    """
    if Q <= 0 or B <= 0 or n <= 0 or I <= 0:
        raise ValueError("Q, B, n, I должны быть положительными")

    def manning_Q(h):
        if h <= 0:
            return -Q  # отрицательное значение для корректного поиска корня
        omega = B * h + m * h ** 2
        P = B + 2 * h * np.sqrt(1 + m ** 2)
        R = omega / P if P > 0 else 0
        return (1 / n) * omega * (R ** (2 / 3)) * np.sqrt(I)

    # Уравнение: manning_Q(h) - Q = 0
    def residual(h):
        return manning_Q(h) - Q

    # Находим интервал поиска [h_min, h_max]
    # h_min: очень малая глубина, остаток отрицательный
    # h_max: увеличиваем, пока остаток не станет положительным
    h_min = 1e-10
    h_max = 1.0
    max_iterations = 100
    iteration = 0
    while residual(h_max) < 0 and iteration < max_iterations:
        h_max *= 2
        iteration += 1
    
    # Защита: если не нашли знак смену
    if residual(h_max) < 0:
        # Фоллбек: используем аналитическое приближение для широкого русла
        # h ≈ (Q * n / (B * sqrt(I)))^(3/5)
        h_approx = (Q * n / (B * np.sqrt(I))) ** 0.6
        h_max = max(h_max, h_approx * 10)
        # Ограничиваем сверху для физически реалистичных значений
        h_max = min(h_max, 1000.0)

    try:
        h_root = brentq(residual, h_min, h_max, xtol=1e-10, rtol=1e-10, maxiter=100)
        return float(h_root)
    except ValueError:
        # В крайнем случае возвращаем приближение
        return float((Q * n / (B * np.sqrt(I))) ** 0.6)


def critical_depth(
    Q: float,
    B: float,
    m: float,
    g: float = 9.81,
) -> float:
    """
    Критическая глубина для трапецеидального русла.

    Q²/g = ω³/B_где

    Parameters:
        Q: расход, м3/с
        B: ширина дна, м
        m: откос бортов

    Returns:
        Критическая глубина, м
    """
    if Q <= 0 or B <= 0:
        raise ValueError("Q и B должны быть положительными")

    # Аналитическое решение для прямоугольного русла (m=0):
    # h_c = (Q² / (g * B²))^(1/3)
    if m == 0.0:
        return float((Q ** 2 / (g * B ** 2)) ** (1.0 / 3.0))

    # Для трапецеидального русла используем brentq (bracketing метод)
    # Уравнение: Q²/g = ω³ / B_top
    # где ω = B*h + m*h², B_top = B + 2*m*h
    def discharge_number(h: float) -> float:
        if h <= 0:
            return -Q ** 2 / g  # отрицательное значение, чтобы brentq нашёл корень
        omega = B * h + m * h ** 2
        B_top = B + 2 * m * h
        return (Q ** 2 / g) - (omega ** 3 / B_top)

    # Находим интервал поиска: функция монотонно убывает при h > 0
    # Ищем правую границу: h где f(h) < 0
    h_max = 1.0
    while discharge_number(h_max) > 0:
        h_max *= 2
        if h_max > 1e6:  # защита от бесконечного цикла
            break

    try:
        h_root = brentq(discharge_number, 1e-10, h_max, xtol=1e-10, rtol=1e-10, maxiter=100)
        return float(h_root)
    except ValueError:
        # Если brentq не сошёлся (мало вероятно при корректных входных данных),
        # возвращаем максимальное значение как fallback
        return float(h_max)


def backwater_curve_step(
    Q: float,
    B: float,
    m: float,
    n: float,
    I: float,
    L_total: float,
    dx: float = 100.0,
    H_downstream: float = 0,
) -> dict:
    """
    Расчёт кривой подпора методом последовательных сечений (direct step).

    Параметрическое уравнение:
    dx = (E₂ - E₁) / (I - S̄f)

    Где E = h + V²/(2g) — энергетический напор
    Sf = Q²n²/(ω²R^(4/3)) — трение по Маннингу

    Parameters:
        Q: расход, м3/с
        B: ширина дна, м
        m: откос бортов
        n: коэффициент Маннинга
        I: уклон, м/м
        L_total: длина участка расчёта, м
        dx: шаг по длине, м
        H_downstream: глубина на нижнем конце (напор от водохранилища), м

    Returns:
        Dict: distances_m, depths_m, normal_depth, L_total, dx
    """
    g = 9.81
    h_n = normal_depth(Q, B, m, n, I)

    h = max(H_downstream, h_n * 1.1)
    distances = [0.0]
    depths = [h]
    velocities = []
    energy_heads = []

    n_steps = int(L_total / dx)

    for i in range(n_steps):
        x = (i + 1) * dx

        omega = B * h + m * h ** 2
        P = B + 2 * h * np.sqrt(1 + m ** 2)
        R = omega / P if P > 0 else 0.01
        V = Q / omega if omega > 0 else 0
        E = h + V ** 2 / (2 * g)
        Sf = (Q * n) ** 2 / (omega ** 2 * R ** (4 / 3)) if R > 0 else 0

        # Решаем уравнение: E2(h2) - E1 = dx * (I - Sf_avg(h2))
        # через brentq (bracketing метод) вместо итераций.
        def _residual(h2):
            omega2 = B * h2 + m * h2 ** 2
            P2 = B + 2 * h2 * np.sqrt(1 + m ** 2)
            R2 = omega2 / P2 if P2 > 0 else 0.01
            V2 = Q / omega2 if omega2 > 0 else 0
            E2 = h2 + V2 ** 2 / (2 * g)
            Sf2 = (Q * n) ** 2 / (omega2 ** 2 * R2 ** (4 / 3)) if R2 > 0 else 0
            Sf_avg = (Sf + Sf2) / 2
            return E2 - E - dx * (I - Sf_avg)

        # Границы поиска: h_min > 0, h_max — достаточно большое
        h_min = 1e-6
        h_max = max(h * 10, 50.0)

        try:
            r_min = _residual(h_min)
            r_max = _residual(h_max)
            # Если знаки одинаковые — расширяем h_max
            if r_min * r_max > 0:
                for _ in range(20):
                    h_max *= 2
                    r_max = _residual(h_max)
                    if r_min * r_max < 0:
                        break
            h_next = brentq(_residual, h_min, h_max, xtol=1e-8, maxiter=100)
        except ValueError:
            # Фоллбек: приближение для широкого русла
            h_next = (Q * n / (B * np.sqrt(I))) ** 0.6

        h_next = max(h_next, 0.01)
        h = h_next
        distances.append(x)
        depths.append(round(float(h), 3))

    return {
        'distances_m': distances,
        'depths_m': depths,
        'normal_depth': round(float(h_n), 3),
        'L_total': L_total,
        'dx': dx,
    }


def backwater_from_reservoir(
    Q: float,
    B: float,
    m: float,
    n: float,
    I: float,
    H_reservoir: float,
    L_max: float = 10000,
    dx: float = 200,
) -> dict:
    """
    Линия подпора от водохранилища (СП 33 п.8.4).

    Показывает, на каком расстоянии от плотины уровень снижается до нормальной глубины.

    Parameters:
        Q: средний расход в реке, м3/с
        B, m, n, I: параметры русла
        H_reservoir: уровень воды в водохранилище (НПУ), м
        L_max: максимальная длина расчёта, м

    Returns:
        Dict: result (distances, depths), normal_depth, L_backwater
    """
    h_n = normal_depth(Q, B, m, n, I)
    L_backwater = L_max

    result = backwater_curve_step(Q, B, m, n, I, L_max, dx, H_reservoir)

    for i, d in enumerate(result['depths_m']):
        if abs(d - h_n) < 0.05:
            L_backwater = result['distances_m'][i]
            break

    return {
        'result': result,
        'normal_depth': round(float(h_n), 3),
        'H_reservoir': H_reservoir,
        'L_backwater_m': round(float(L_backwater), 0),
        'L_backwater_km': round(float(L_backwater) / 1000, 2),
    }
