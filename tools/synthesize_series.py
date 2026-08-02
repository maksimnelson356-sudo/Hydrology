"""
tools/synthesize_series.py
Синтез гидрологических рядов с заданными статистиками (n, mean, Cv, Cs, r1).

Метод:
1. AR(1)-процесс Гаусса с заданным коэффициентом автокорреляции r1:
   z_t = r1 * z_{t-1} + sqrt(1 - r1^2) * eps_t
2. Вероятностное интегрирование: u_t = Phi(z_t) -> [0, 1]
3. Обратное преобразование к распределению Пирсона III с заданным Cs:
   q_t = pearson3_ppf_std(u_t, cs)
   (стандартизованное, mean=0, std=1, skew=cs)
4. Перенормировка: x_t = mean * (1 + Cv * q_t)

AR(1)-преобразование нормальной величины через Phi^{-1} сохраняет ранг,
поэтому r1 переданный в AR(1) точно воспроизводится в выходном ряду.

Используется для верификации формул статистик против эталонной
программы HydroStatCalc (протоколы Статистики.txt, Расчет Nэкв.txt).
"""

import numpy as np
from scipy import stats
from typing import Optional


def ar1_normal(n: int, r1: float, seed: Optional[int] = None) -> np.ndarray:
    """AR(1)-процесс стандартной нормальной величины с заданным r1."""
    rng = np.random.default_rng(seed)
    eps = rng.normal(size=n)
    z = np.empty(n)
    z[0] = eps[0]
    phi = r1
    sigma_e = np.sqrt(max(1.0 - phi ** 2, 0.0))
    for t in range(1, n):
        z[t] = phi * z[t - 1] + sigma_e * eps[t]
    # Перенормировка, чтобы z имел ровно std=1, mean=0
    z = (z - z.mean()) / z.std(ddof=1)
    return z


def _pearson3_std_ppf(u: np.ndarray, cs: float) -> np.ndarray:
    """Квантили стандартизованного распределения Пирсона III (mean=0, std=1, skew=cs)."""
    u = np.asarray(u, dtype=float)
    u = np.clip(u, 1e-12, 1 - 1e-12)
    cs = float(cs)
    if abs(cs) < 1e-6:
        return stats.norm.ppf(u)
    q = stats.pearson3.ppf(u, skew=cs)
    return q


def _generate_q(n: int, cs_gen: float, r1_gen: float, seed: int) -> np.ndarray:
    """Стандартизованный ряд (mean=0, std=1) с заданными cs_gen/r1_gen генератора."""
    z = ar1_normal(n, r1_gen, seed=seed)
    u = stats.norm.cdf(z)
    q = _pearson3_std_ppf(u, cs_gen)
    q = (q - q.mean()) / q.std(ddof=1)
    return q


def synthesize_series(
    n: int,
    mean: float,
    cv: float,
    cs: float,
    r1: float = 0.0,
    seed: Optional[int] = 42,
) -> np.ndarray:
    """
    Синтез ряда, выборочные статистики которого (mean, cv, cs, r1)
    равны переданным значениям (оценки как в hydrolib: skew bias=False,
    r1 = corrcoef смежных членов).

    Параметры генератора (cs_gen, r1_gen) подгоняются итеративно, так как
    выборочная асимметрия и корреляция Пирсона расходятся с параметрами
    AR(1)+монотонного преобразования из-за конечного n.
    """
    if cv < 0:
        raise ValueError("cv должен быть >= 0")
    if seed is None:
        seed = 42

    # ---- Итеративная подгонка (cs_gen, r1_gen) под целевые выборочные ----
    r1_gen = r1
    cs_gen = cs

    for _ in range(40):
        q = _generate_q(n, cs_gen, r1_gen, seed)

        # Текущие выборочные значения (до перенормировки mean/cv)
        r1_cur = np.corrcoef(q[:-1], q[1:])[0, 1]
        cs_cur = stats.skew(q, bias=False)

        # Уточнение по методу простой итерации с демпфированием
        r1_gen += 0.5 * (r1 - r1_cur)
        r1_gen = float(np.clip(r1_gen, -0.95, 0.95))
        cs_gen += 0.5 * (cs - cs_cur)

        if abs(r1_cur - r1) < 1e-3 and abs(cs_cur - cs) < 1e-3:
            break

    q = _generate_q(n, cs_gen, r1_gen, seed)

    # Восстановление mean и cv: x = mean * (1 + Cv * q)
    x = mean * (1.0 + cv * q)
    return x


def series_stats(x: np.ndarray) -> dict:
    """Оценки статистик ряда (как в hydrolib parameters.py)."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    mean = x.mean()
    std = x.std(ddof=1)
    cv = std / mean if mean != 0 else 0.0
    cs = stats.skew(x, bias=False)
    r1 = np.corrcoef(x[:-1], x[1:])[0, 1] if n > 2 else 0.0
    return {
        'n': n,
        'mean': round(mean, 4),
        'std': round(std, 4),
        'cv': round(cv, 4),
        'cs': round(cs, 4),
        'r1': round(r1, 4),
    }


if __name__ == "__main__":
    print("Синтез ряда n=114, mean=412, Cv=0.11, Cs=0.07, r1=0.50 (пост 9215):")
    x = synthesize_series(114, 412, 0.11, 0.07, 0.50)
    print(series_stats(x))
    print("\nПервые 10 значений:", np.round(x[:10], 1))
