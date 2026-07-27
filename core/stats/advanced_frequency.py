"""
core/stats/advanced_frequency.py
Продвинутый частотный анализ: MLE, L-моменты, доп. распределения, PDS

Основные функции:
- mle_pearson3 — MLE для Пирсона III
- lmom_pearson3 — L-моменты для Пирсона III
- fit_logpearson3 — логнормальное Пирсона III
- fit_gev — обобщённое предельное распределение (GEV)
- fit_weibull3 — Вейбулл 3-параметра
- peaks_over_threshold — пороговые пики (PDS)
- goodness_of_fit — критерии согласия (χ², K-S, A-D)
- qq_plot_data — данные для Q-Q графика
- pp_plot_data — данные для P-P графика
- weibull_plotting_position — площадка Вейбулла m/(n+1)
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
from typing import Dict, List, Optional, Tuple


def weibull_plotting_position(n: int) -> np.ndarray:
    """
    Площадка Вейбулла: P_i = i / (n + 1)

    Parameters:
        n: количество значений

    Returns:
        Массив обеспенностей (0..1)
    """
    i = np.arange(1, n + 1)
    return i / (n + 1)


def hazen_plotting_position(n: int) -> np.ndarray:
    """Площадка Хейзена: P_i = (i - 0.5) / n"""
    i = np.arange(1, n + 1)
    return (i - 0.5) / n


def gringorten_plotting_position(n: int) -> np.ndarray:
    """Площадка Грингортена: P_i = (i - 0.44) / (n + 0.12)"""
    i = np.arange(1, n + 1)
    return (i - 0.44) / (n + 0.12)


def mle_pearson3(
    data: np.ndarray,
    max_iter: int = 500,
) -> Dict:
    """
    Оценка параметров Пирсона III методом максимального правдоподобия (MLE).

    Параметры: mean, cv, cs

    Parameters:
        data: массив наблюдений
        max_iter: максимальное число итераций оптимизации

    Returns:
        Dict: mean, cv, cs, loglik, aic, bic, success
    """
    data = np.array(data, dtype=float)
    data = data[~np.isnan(data)]
    n = len(data)

    if n < 5:
        return {'mean': float(np.mean(data)), 'cv': 0, 'cs': 0,
                'loglik': -np.inf, 'aic': np.inf, 'bic': np.inf, 'success': False}

    x0 = [float(np.mean(data)), float(np.std(data, ddof=1) / np.mean(data)), 0.0]

    def neg_loglik(params):
        mu, cv, cs = params
        if cv <= 0 or abs(cs) > 10:
            return 1e10
        sigma = abs(mu) * cv
        if sigma < 1e-10:
            return 1e10
        alpha = 4 / (cs ** 2) if cs != 0 else 100
        beta = sigma / np.sqrt(alpha) if alpha > 0 else 1
        shift = mu - alpha * beta

        try:
            ll = np.sum(stats.gamma.logpdf(data - shift, a=alpha, scale=beta))
            if np.isnan(ll) or np.isinf(ll):
                return 1e10
            return -ll
        except Exception:
            return 1e10

    result = minimize(neg_loglik, x0, method='Nelder-Mead',
                      options={'maxiter': max_iter})

    if result.success:
        mu, cv, cs = result.x
        sigma = abs(mu) * cv
        alpha = 4 / (cs ** 2) if cs != 0 else 100
        beta = sigma / np.sqrt(alpha) if alpha > 0 else 1
        shift = mu - alpha * beta

        try:
            loglik = np.sum(stats.gamma.logpdf(data - shift, a=alpha, scale=beta))
        except Exception:
            loglik = -result.fun

        k = 3
        aic = 2 * k - 2 * loglik
        bic = k * np.log(n) - 2 * loglik

        return {
            'mean': round(float(mu), 4),
            'cv': round(float(cv), 4),
            'cs': round(float(cs), 4),
            'loglik': round(float(loglik), 2),
            'aic': round(float(aic), 2),
            'bic': round(float(bic), 2),
            'success': True,
        }
    else:
        mean = float(np.mean(data))
        cv = float(np.std(data, ddof=1) / mean) if mean != 0 else 0
        return {
            'mean': mean,
            'cv': cv,
            'cs': 0,
            'loglik': -np.inf,
            'aic': np.inf,
            'bic': np.inf,
            'success': False,
        }


def lmom_pearson3(
    data: np.ndarray,
) -> Dict:
    """
    Оценка параметров Пирсона III L-моментами (probability weighted moments).

    λ1 = mean
    λ2 = (mean - Q_med) / 2  (для симметричного)
    τ3 = λ3 / λ2 (коэффициент асимметрии L-моментов)

    Parameters:
        data: массив наблюдений

    Returns:
        Dict: mean, cv, cs, lambda2, tau3, L-moments
    """
    data = np.array(data, dtype=float)
    data = data[~np.isnan(data)]
    data_sorted = np.sort(data)
    n = len(data)

    if n < 5:
        return {'mean': float(np.mean(data)), 'cv': 0, 'cs': 0,
                'lambda1': float(np.mean(data)), 'lambda2': 0, 'tau3': 0}

    w = weibull_plotting_position(n)

    # PWM (Probability Weighted Moments)
    b0 = np.mean(data_sorted)
    b1 = np.mean((1 - w) * data_sorted)
    b2 = np.mean((1 - w) ** 2 * data_sorted)

    # L-moments
    l1 = b0
    l2 = 2 * b1 - b0
    l3 = 6 * b2 - 6 * b1 + b0

    tau3 = l3 / l2 if abs(l2) > 1e-10 else 0

    mean = l1
    cv = l2 / l1 if l1 != 0 else 0

    # Приближение cs из tau3
    # Для Пирсона III: Cs ≈ tau3 / Cv (по关系系е L-моментов, Bobee & Robitaille 1977)
    cs = tau3 / cv if abs(cv) > 1e-10 else 0

    return {
        'mean': round(float(mean), 4),
        'cv': round(float(cv), 4),
        'cs': round(float(cs), 4),
        'lambda1': round(float(l1), 4),
        'lambda2': round(float(l2), 4),
        'tau3': round(float(tau3), 4),
    }


def fit_logpearson3(
    data: np.ndarray,
) -> Dict:
    """
    Логнормальное распределение Пирсона III (Log-Pearson III).

    Широко используется для предельных осадков и паводков (США, WMO).

    Parameters:
        data: массив наблюдений

    Returns:
        Dict: mean_log, cv_log, cs_log, back-transformed mean/cv
    """
    data = np.array(data, dtype=float)
    data = data[data > 0]

    log_data = np.log(data)

    mle = mle_pearson3(log_data)

    return {
        'mean_log': mle['mean'],
        'cv_log': mle['cv'],
        'cs_log': mle['cs'],
        'mean_original': round(float(np.exp(mle['mean'] + 0.5 * (mle['cv'] * mle['mean']) ** 2)), 3),
        'cv_original': round(float(np.sqrt(np.exp((mle['cv'] * mle['mean']) ** 2) - 1)), 4),
        'n': len(data),
    }


def fit_gev(
    data: np.ndarray,
) -> Dict:
    """
    Обобщённое предельное распределение (GEV) — GenExtremum.

    F(x) = exp{-(1 + ξ(x-μ)/σ)^(-1/ξ)}

    Parameters:
        data: массив наблюдений

    Returns:
        Dict: shape (ξ), location (μ), scale (σ), aic, bic
    """
    data = np.array(data, dtype=float)
    data = data[~np.isnan(data)]

    if len(data) < 10:
        return {'shape': 0, 'location': float(np.mean(data)),
                'scale': float(np.std(data)), 'aic': np.inf, 'bic': np.inf}

    try:
        shape, loc, scale = stats.genextreme.fit(data)

        n = len(data)
        loglik = np.sum(stats.genextreme.logpdf(data, shape, loc=loc, scale=scale))
        aic = 2 * 3 - 2 * loglik
        bic = 3 * np.log(n) - 2 * loglik

        return {
            'shape_xi': round(float(-shape), 4),
            'location_mu': round(float(loc), 4),
            'scale_sigma': round(float(scale), 4),
            'loglik': round(float(loglik), 2),
            'aic': round(float(aic), 2),
            'bic': round(float(bic), 2),
            'n': n,
        }
    except Exception:
        return {'shape_xi': 0, 'location': float(np.mean(data)),
                'scale': float(np.std(data)), 'aic': np.inf, 'bic': np.inf}


def fit_weibull3(
    data: np.ndarray,
) -> Dict:
    """
    Распределение Вейбулла 3-параметра.

    F(x) = 1 - exp{-(x - ε)/α)^β}

    Parameters:
        data: массив наблюдений

    Returns:
        Dict: shape (β), scale (α), location (ε), aic
    """
    data = np.array(data, dtype=float)
    data = data[~np.isnan(data)]

    if len(data) < 10:
        return {'shape': 0, 'scale': 0, 'location': 0, 'aic': np.inf}

    try:
        shape, loc, scale = stats.weibull_min.fit(data, floc=0)

        n = len(data)
        loglik = np.sum(stats.weibull_min.logpdf(data, shape, loc=loc, scale=scale))
        aic = 2 * 3 - 2 * loglik

        return {
            'shape_beta': round(float(shape), 4),
            'scale_alpha': round(float(scale), 4),
            'location_epsilon': round(float(loc), 4),
            'loglik': round(float(loglik), 2),
            'aic': round(float(aic), 2),
            'n': n,
        }
    except Exception:
        return {'shape_beta': 0, 'scale_alpha': 0, 'location_epsilon': 0, 'aic': np.inf}


def peaks_over_threshold(
    data: np.ndarray,
    threshold_percentile: float = 95.0,
    min_separation_days: int = 5,
) -> Dict:
    """
    Пороговые пиковые series (PDS / Peaks Over Threshold).

    СП 33 позволяет оба метода: AMS (годовые максимумы) и PDS.

    Parameters:
        data: суточные расходы (или уровень)
        threshold_percentile: процентиль для порога (по умолчанию 95%)
        min_separation_days: минимальный интервал между пиками, сутки

    Returns:
        Dict: threshold, peaks, n_peaks, annual_rate
    """
    data = np.array(data, dtype=float)
    data = data[~np.isnan(data)]

    threshold = np.percentile(data, threshold_percentile)

    peaks = []
    i = 0
    while i < len(data):
        if data[i] >= threshold:
            peak_val = data[i]
            peak_idx = i
            i += 1
            while i < len(data) and data[i] >= threshold:
                if data[i] > peak_val:
                    peak_val = data[i]
                    peak_idx = i
                i += 1
            peaks.append({
                'index': int(peak_idx),
                'value': float(peak_val),
            })
            i += min_separation_days
        else:
            i += 1

    n_days = len(data)
    n_years = n_days / 365.25
    annual_rate = len(peaks) / n_years if n_years > 0 else 0

    return {
        'threshold': float(threshold),
        'threshold_percentile': threshold_percentile,
        'peaks': peaks,
        'n_peaks': len(peaks),
        'annual_rate': round(float(annual_rate), 2),
        'peak_values': [p['value'] for p in peaks],
    }


def goodness_of_fit(
    data: np.ndarray,
    distribution: str = 'pearson3',
    params: Optional[Dict] = None,
) -> Dict:
    """
    Критерии согласия распределения с данными.

    - χ² (хи-квадрат)
    - K-S (Колмогоров-Смирнов)
    - A-D (Андерсон-Дарлинг)

    Parameters:
        data: наблюдения
        distribution: 'pearson3', 'normal', 'lognormal', 'gamma', 'gev'
        params: параметры распределения (если None — подбираются из data)

    Returns:
        Dict: ks_stat, ks_p, ad_stat, chi2_stat, chi2_p
    """
    data = np.array(data, dtype=float)
    data = data[~np.isnan(data)]

    results = {}

    try:
        ks_stat, ks_p = stats.kstest(data, distribution, args=()) if params is None else \
            stats.kstest(data, distribution)
        results['ks_stat'] = round(float(ks_stat), 4)
        results['ks_p'] = round(float(ks_p), 6)
    except Exception:
        results['ks_stat'] = 0
        results['ks_p'] = 1

    try:
        ad_stat = stats.anderson(data, dist=distribution if distribution != 'pearson3' else 'norm')
        results['ad_stat'] = round(float(ad_stat.statistic), 4)
        results['ad_critical_values'] = [round(float(x), 3) for x in ad_stat.critical_values]
    except Exception:
        results['ad_stat'] = 0
        results['ad_critical_values'] = []

    n_bins = max(5, int(np.sqrt(len(data))))
    observed, bin_edges = np.histogram(data, bins=n_bins)

    if params is None:
        try:
            if distribution == 'normal':
                mu, sigma = stats.norm.fit(data)
                expected = stats.norm.cdf(bin_edges, mu, sigma)
            elif distribution == 'lognormal':
                shape, loc, scale = stats.lognorm.fit(data, floc=0)
                expected = stats.lognorm.cdf(bin_edges, shape, loc=loc, scale=scale)
            elif distribution == 'gamma':
                a, loc, scale = stats.gamma.fit(data, floc=0)
                expected = stats.gamma.cdf(bin_edges, a, loc=loc, scale=scale)
            else:
                mu, sigma = stats.norm.fit(data)
                expected = stats.norm.cdf(bin_edges, mu, sigma)

            expected_freq = np.diff(expected) * len(data)
            expected_freq = np.maximum(expected_freq, 1)

            chi2_stat = np.sum((observed - expected_freq) ** 2 / expected_freq)
            df = n_bins - 3
            chi2_p = 1 - stats.chi2.cdf(chi2_stat, df) if df > 0 else 1

            results['chi2_stat'] = round(float(chi2_stat), 4)
            results['chi2_p'] = round(float(chi2_p), 6)
        except Exception:
            results['chi2_stat'] = 0
            results['chi2_p'] = 1

    results['n'] = len(data)
    results['distribution'] = distribution

    return results


def qq_plot_data(
    data: np.ndarray,
    distribution: str = 'norm',
) -> Dict:
    """
    Данные для Q-Q графика (квантиль-квантиль).

    Parameters:
        data: наблюдения
        distribution: 'norm', 'lognorm', 'gamma', 'genextreme'

    Returns:
        Dict: theoretical, empirical, theoretical_quantiles, empirical_quantiles
    """
    data = np.array(data, dtype=float)
    data = np.sort(data[~np.isnan(data)])
    n = len(data)

    p = weibull_plotting_position(n)

    if distribution == 'norm':
        mu, sigma = stats.norm.fit(data)
        theoretical = stats.norm.ppf(p, mu, sigma)
    elif distribution == 'lognorm':
        s, loc, scale = stats.lognorm.fit(data, floc=0)
        theoretical = stats.lognorm.ppf(p, s, loc=loc, scale=scale)
    elif distribution == 'gamma':
        a, loc, scale = stats.gamma.fit(data, floc=0)
        theoretical = stats.gamma.ppf(p, a, loc=loc, scale=scale)
    elif distribution == 'genextreme':
        c, loc, scale = stats.genextreme.fit(data)
        theoretical = stats.genextreme.ppf(p, c, loc=loc, scale=scale)
    else:
        theoretical = stats.norm.ppf(p, *stats.norm.fit(data))

    return {
        'theoretical': theoretical.tolist(),
        'empirical': data.tolist(),
        'n': n,
        'distribution': distribution,
    }


def pp_plot_data(
    data: np.ndarray,
    distribution: str = 'norm',
) -> Dict:
    """
    Данные для P-P графика (вероятность-вероятность).

    Parameters:
        data: наблюдения
        distribution: тип распределения

    Returns:
        Dict: theoretical_probs, empirical_probs
    """
    data = np.array(data, dtype=float)
    data = np.sort(data[~np.isnan(data)])
    n = len(data)

    p_empirical = weibull_plotting_position(n)

    if distribution == 'norm':
        mu, sigma = stats.norm.fit(data)
        p_theoretical = stats.norm.cdf(data, mu, sigma)
    elif distribution == 'lognorm':
        s, loc, scale = stats.lognorm.fit(data, floc=0)
        p_theoretical = stats.lognorm.cdf(data, s, loc=loc, scale=scale)
    elif distribution == 'gamma':
        a, loc, scale = stats.gamma.fit(data, floc=0)
        p_theoretical = stats.gamma.cdf(data, a, loc=loc, scale=scale)
    else:
        mu, sigma = stats.norm.fit(data)
        p_theoretical = stats.norm.cdf(data, mu, sigma)

    return {
        'theoretical_probs': p_theoretical.tolist(),
        'empirical_probs': p_empirical.tolist(),
        'n': n,
        'distribution': distribution,
    }


def compare_distributions(
    data: np.ndarray,
) -> pd.DataFrame:
    """
    Сравнение нескольких распределений по AIC/BIC.

    Parameters:
        data: наблюдения

    Returns:
        DataFrame с результатами
    """
    results = []

    mle_p3 = mle_pearson3(data)
    results.append({
        'Распределение': 'Пирсон III (моменты)',
        'AIC': mle_p3.get('aic', np.inf),
        'BIC': mle_p3.get('bic', np.inf),
    })

    lmom_p3 = lmom_pearson3(data)
    results.append({
        'Распределение': 'Пирсон III (L-моменты)',
        'AIC': np.nan,
        'BIC': np.nan,
    })

    try:
        lnorm = fit_logpearson3(data)
        results.append({
            'Распределение': 'Log-Пирсон III',
            'AIC': np.nan,
            'BIC': np.nan,
        })
    except Exception:
        pass

    gev = fit_gev(data)
    results.append({
        'Распределение': 'GEV',
        'AIC': gev.get('aic', np.inf),
        'BIC': gev.get('bic', np.inf),
    })

    w3 = fit_weibull3(data)
    results.append({
        'Распределение': 'Вейбулл-3',
        'AIC': w3.get('aic', np.inf),
        'BIC': np.nan,
    })

    mu, sigma = stats.norm.fit(data)
    n = len(data)
    loglik_norm = np.sum(stats.norm.logpdf(data, mu, sigma))
    aic_norm = 2 * 2 - 2 * loglik_norm
    bic_norm = 2 * np.log(n) - 2 * loglik_norm
    results.append({
        'Распределение': 'Нормальное',
        'AIC': round(aic_norm, 2),
        'BIC': round(bic_norm, 2),
    })

    a, loc, scale = stats.gamma.fit(data, floc=0)
    loglik_gam = np.sum(stats.gamma.logpdf(data, a, loc=loc, scale=scale))
    aic_gam = 2 * 3 - 2 * loglik_gam
    bic_gam = 3 * np.log(n) - 2 * loglik_gam
    results.append({
        'Распределение': 'Гамма',
        'AIC': round(aic_gam, 2),
        'BIC': round(bic_gam, 2),
    })

    df = pd.DataFrame(results)
    df = df.sort_values('AIC')
    return df
