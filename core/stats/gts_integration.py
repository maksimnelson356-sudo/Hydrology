"""
core/stats/gts_integration.py
Интеграция расчётных обеспеченностей ГТС с кривыми обеспеченности

СП 58.13330.2019 раздел 6 — определяет расчётные обеспечённости
по классу сооружения (I–IV), а этот модуль подставляет их в кривые.

Основные функции:
- get_gts_points — извлечение расчётных точек по классу ГТС
- interpolate_gts_discharge — интерполяция расхода для обеспечённости ГТС
- build_gts_frequency_curve — кривая с расчётными точками ГТС
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from scipy import stats

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.gts_reference import GTSClass, GTS_PROBABILITIES, get_probabilities_for_class, get_standard_probabilities
from core.stats.frequency import pearson3_ppf


def get_gts_points(
    gts_class: GTSClass,
    case_type: str = 'osnovnoy'
) -> Dict[str, float]:
    """
    Извлечение расчётных обеспеченностей для класса ГТС.

    Parameters:
        gts_class: класс капитальности (I, II, III, IV)
        case_type: 'osnovnoy' или 'proverochniy'

    Returns:
        Dict с ключами: max_p, min_p, max_p_prov, min_p_prov, description
    """
    osnov = get_probabilities_for_class(gts_class, 'osnovnoy')
    prov = get_probabilities_for_class(gts_class, 'proverochniy')

    return {
        'max_p': osnov['max_discharge_p'],
        'min_p': osnov['min_discharge_p'],
        'max_p_prov': prov['max_discharge_p'],
        'min_p_prov': prov['min_discharge_p'],
        'description': osnov['description'],
        'max_discharge_label': f"P={osnov['max_discharge_p']*100:.2f}%",
        'min_discharge_label': f"P={osnov['min_discharge_p']*100:.1f}%",
    }


def interpolate_gts_discharge(
    P_values: np.ndarray,
    Q_values: np.ndarray,
    target_P: float
) -> float:
    """
    Интерполяция расхода для заданной обеспечённости.

    Parameters:
        P_values: массив обеспеченностей (в долях, от 0 к 1)
        Q_values: массив соответствующих расходов
        target_P: целевая обеспечённость (в долях)

    Returns:
        Интерполированный расход
    """
    log_P = np.log(P_values)
    log_target = np.log(target_P)
    Q_interp = np.interp(log_target, log_P, Q_values)
    return float(Q_interp)


def build_gts_frequency_curve(
    data: np.ndarray,
    gts_class: GTSClass,
    use_corrected: bool = True
) -> Dict:
    """
    Построение кривой обеспечённости с автоматической подстановкой
    расчётных точек по классу ГТС.

    Parameters:
        data: массив годовых расходов (максимальных или средних)
        gts_class: класс ГТС
        use_corrected: использовать поправки на автокорреляцию

    Returns:
        Dict: curve_df, gts_points, stats_dict
    """
    from core.stats.parameters import calculate_statistical_parameters
    params = calculate_statistical_parameters(data)
    mean = params['mean']
    cv = params['corrected_cv'] if use_corrected else params['cv']
    cs = params['corrected_cs'] if use_corrected else params['cs']

    gts_info = get_gts_points(gts_class)

    all_probs = get_standard_probabilities(gts_class)
    P_decimal = np.array(all_probs)

    Q_values = pearson3_ppf(P_decimal, mean, cv, cs)

    curve_df = pd.DataFrame({
        'P_%': np.round(P_decimal * 100, 3),
        'Q': np.round(Q_values, 2)
    })

    gts_max_Q = float(np.interp(
        gts_info['max_p'],
        P_decimal,
        Q_values
    ))
    gts_min_Q = float(np.interp(
        gts_info['min_p'],
        P_decimal,
        Q_values
    ))
    gts_max_prov_Q = float(np.interp(
        gts_info['max_p_prov'],
        P_decimal,
        Q_values
    ))
    gts_min_prov_Q = float(np.interp(
        gts_info['min_p_prov'],
        P_decimal,
        Q_values
    ))

    gts_points = {
        'max_osnovnoy': {
            'P_%': gts_info['max_p'] * 100,
            'Q': round(gts_max_Q, 2),
            'label': f"Паводок {gts_info['max_discharge_label']}"
        },
        'max_proverochniy': {
            'P_%': gts_info['max_p_prov'] * 100,
            'Q': round(gts_max_prov_Q, 2),
            'label': f"Паводок (провер.) P={gts_info['max_p_prov']*100:.3f}%"
        },
        'min_osnovnoy': {
            'P_%': gts_info['min_p'] * 100,
            'Q': round(gts_min_Q, 2),
            'label': f"Межень {gts_info['min_discharge_label']}"
        },
        'min_proverochniy': {
            'P_%': gts_info['min_p_prov'] * 100,
            'Q': round(gts_min_prov_Q, 2),
            'label': f"Межень (провер.) P={gts_info['min_p_prov']*100:.1f}%"
        }
    }

    return {
        'curve_df': curve_df,
        'gts_points': gts_points,
        'gts_class': gts_class,
        'gts_description': gts_info['description'],
        'stats': {
            'mean': mean, 'Cv': cv, 'Cs': cs, 'n': params['n']
        }
    }


def gts_summary_table(
    gts_class: GTSClass,
    data: np.ndarray,
    use_corrected: bool = True
) -> pd.DataFrame:
    """
    Сводная таблица расчётных характеристик для ГТС заданного класса.

    Returns:
        DataFrame с колонками: Параметр, Обеспеченность_%, Q_м3_с, Описание
    """
    result = build_gts_frequency_curve(data, gts_class, use_corrected)
    gts_points = result['gts_points']

    rows = []
    for key, pt in gts_points.items():
        rows.append({
            'Параметр': pt['label'],
            'Обеспеченность_%': pt['P_%'],
            'Q_м3_с': pt['Q'],
            'Класс_ГТС': f"Класс {gts_class}"
        })

    return pd.DataFrame(rows)
