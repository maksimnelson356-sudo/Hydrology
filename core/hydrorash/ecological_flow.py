"""
core/hydrorash/ecological_flow.py
Экологический сток: сезонный Тессман, ECOFRAME, метод мокрого периметра.

Прежняя ссылка на СП 32.13330.2018 ОШИБОЧНА: по официальным метаданным это
«Канализация. Наружные сети и сооружения» — предмет не совпадает. Правильный
источник не установлен; матрица относит метод к Тессману (не проверено).

Проверено 2026-09-28, исчерпывающе:

- СП 33-101-2003 — «Определение основных расчетных гидрологических
  характеристик» — по «Тессман», «экологическ», «рыбопропуск» НОЛЬ совпадений.
  Стандарт внутригодовое распределение РЕГЛАМЕНТИРУЕТ (разделы 5.2, 6.6, 7.2;
  А.13), но методом КОМПОНОВКИ и по гидрологическим сезонам («лимитирующий
  период / лимитирующий сезон / нелимитирующий сезон / лимитирующий месяц»).
  Совпадений «помесячн» — ноль. Ни структура месячных коэффициентов α_i, β_i,
  ни распределение экологического стока по месяцам в СП 33 не содержатся.
- СП 290.1325800.2016 (водосбросы) — ссылка [3] его библиографии, откуда берутся
  коэффициенты формулы (4), указывает на ВНИИГ П18-74 (1974) и П45-75 (1976),
  а НЕ на Тессмана.
- СП 38.13330.2018 (ледовые нагрузки) — темы не касается.
- Каталог СП (meganorm, 604 позиции) по словам «экологическ» / «рыбопропуск» /
  «санитарный попуск»: только СП 502.1325800.2021 и СП 11-102-97 (инженерно-
  экологические изыскания) и СП 101.13330 (рыбопропускные сооружения). Ни один
  не регламентирует экологический сток.

ИТОГ: атрибуция «Тессман» не подтверждается ни одним достижимым документом.
Реализованная формула Q_эколог_i = α_i * Q_ср * (Q_i / Q_ср)^β_i и наборы α/β —
ИНЖЕНЕРНАЯ КОНСТРУКЦИЯ без нормативного происхождения. Числа в
SEASONAL_TESSMANN_PARAMS не заимствованы из проверяемого источника.

Основные функции:
- tessmann_seasonal — сезонный Тессман (полный, с месячными классами)
- ecoregime_classes — классы экологического режима (I-VI)
- wetted_perimeter_method — метод мокрого периметра
- min_flow_comparison — сравнение методов расчёта экологического стока
"""


import numpy as np
import pandas as pd

# Классы экологического режима. Прежняя ссылка «СП 32, РГГМУ» не подтверждена
ECO_CLASSES = {
    'I': {'name': 'Заморный', 'Q_ratio': 0.05, 'description': 'Допустимо кратковременно'},
    'II': {'name': 'Экстремально низкий', 'Q_ratio': 0.10, 'description': 'Критический для биоты'},
    'III': {'name': 'Низкий', 'Q_ratio': 0.20, 'description': 'Ограниченная среда обитания'},
    'IV': {'name': 'Оптимально низкий', 'Q_ratio': 0.30, 'description': 'Базовый уровень'},
    'V': {'name': 'Оптимальный', 'Q_ratio': 0.50, 'description': 'Комфортная среда'},
    'VI': {'name': 'Высокий', 'Q_ratio': 0.80, 'description': 'Паводковый режим'},
}

# Потоковые классы для сезонного «Тессмана». Прежняя ссылка «СП 32, прил. 8»
# ОШИБОЧНА: СП 32 - документ о канализации.
# ВНИМАНИЕ: числовые значения α и β НЕ имеют подтверждённого нормативного
# источника (см. шапку модуля: исчерпывающий поиск 2026-09-28 без результата).
# Это инженерная конструкция, а не выдержка из стандарта.
# α_i — доля от Q_ср для i-го месяца; β_i — показатель степени

SEASONAL_TESSMANN_PARAMS = {
    'northern': {
        'name': 'Северные реки (таяние снега)',
        'alpha': [0.05, 0.05, 0.15, 0.50, 0.80, 0.50, 0.25, 0.15, 0.10, 0.05, 0.05, 0.05],
        'beta': [0.5, 0.5, 0.6, 0.7, 0.8, 0.7, 0.6, 0.5, 0.5, 0.5, 0.5, 0.5],
    },
    'central': {
        'name': 'Центральные реки',
        'alpha': [0.10, 0.10, 0.20, 0.60, 0.90, 0.60, 0.30, 0.20, 0.15, 0.10, 0.10, 0.10],
        'beta': [0.5, 0.5, 0.6, 0.7, 0.85, 0.7, 0.6, 0.5, 0.5, 0.5, 0.5, 0.5],
    },
    'southern': {
        'name': 'Южные реки',
        'alpha': [0.15, 0.12, 0.10, 0.30, 0.50, 0.80, 0.60, 0.40, 0.30, 0.20, 0.15, 0.15],
        'beta': [0.5, 0.5, 0.5, 0.6, 0.7, 0.8, 0.7, 0.6, 0.6, 0.5, 0.5, 0.5],
    },
    'mountain': {
        'name': 'Горные реки',
        'alpha': [0.10, 0.10, 0.15, 0.40, 0.70, 0.90, 0.80, 0.60, 0.30, 0.15, 0.10, 0.10],
        'beta': [0.5, 0.5, 0.6, 0.7, 0.8, 0.9, 0.85, 0.7, 0.6, 0.5, 0.5, 0.5],
    },
}


def tessmann_seasonal(
    Q_annual_mean: float,
    region_type: str = 'central',
    Q_monthly_mean: np.ndarray | None = None,
) -> dict:
    """
    Сезонный Тессман. Прежняя ссылка «СП 32, прил. 8» ОШИБОЧНА - предмет документа
другой; фактический источник не установлен.

    Для каждого месяца:
    Q_эколог_i = α_i × Q_ср × (Q_i / Q_ср)^β_i

    где:
    - α_i — доля экологического стока от среднего расхода
    - β_i — параметр чувствительности (0.5–1.0)
    - Q_i — средний расход месяца

    Parameters:
        Q_annual_mean: среднегодовой расход, м³/с
        region_type: тип региона ('northern', 'central', 'southern', 'mountain')
        Q_monthly_mean: средние месячные расходы (12 значений), м³/с

    Returns:
        Dict: monthly_Q_eco, monthly_alpha, total_deficit
    """
    if region_type not in SEASONAL_TESSMANN_PARAMS:
        region_type = 'central'

    params = SEASONAL_TESSMANN_PARAMS[region_type]
    alpha = np.array(params['alpha'])
    beta = np.array(params['beta'])

    if Q_monthly_mean is None:
        Q_monthly_mean = np.array([Q_annual_mean] * 12)
    else:
        Q_monthly_mean = np.array(Q_monthly_mean)[:12]

    Q_monthly_mean = np.maximum(Q_monthly_mean, 0.01)

    Q_ratio = Q_monthly_mean / Q_annual_mean if Q_annual_mean > 0 else np.ones(12)
    Q_ratio = np.maximum(Q_ratio, 0.01)

    Q_eco = alpha * Q_annual_mean * (Q_ratio ** beta)

    months = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
              'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']

    rows = []
    for i in range(12):
        rows.append({
            'Месяц': months[i],
            'Q_ср_месяц': round(float(Q_monthly_mean[i]), 2),
            'α_i': round(float(alpha[i]), 2),
            'β_i': round(float(beta[i]), 2),
            'Q_эколог': round(float(Q_eco[i]), 2),
        })

    df = pd.DataFrame(rows)
    Q_eco_annual_mean = float(np.mean(Q_eco))
    eco_ratio = Q_eco_annual_mean / Q_annual_mean if Q_annual_mean > 0 else 0

    return {
        'monthly_table': df,
        'Q_eco_monthly': Q_eco.tolist(),
        'Q_eco_annual_mean': round(Q_eco_annual_mean, 2),
        'eco_ratio_to_Qmean': round(eco_ratio, 3),
        'region': params['name'],
    }


def ecoregime_classes(
    Q: float,
    Q_mean: float,
) -> dict:
    """
    Класс экологического режима по соотношению Q/Q_ср.

    Parameters:
        Q: текущий расход, м³/с
        Q_mean: среднегодовой расход, м³/с

    Returns:
        Dict: class_id, class_name, description
    """
    if Q_mean <= 0:
        return {'class_id': 'I', 'class_name': 'Нет данных', 'description': 'Q_ср ≤ 0'}

    ratio = Q / Q_mean

    for cls_id, cls_data in ECO_CLASSES.items():
        if ratio <= cls_data['Q_ratio']:
            return {
                'class_id': cls_id,
                'class_name': cls_data['name'],
                'description': cls_data['description'],
                'ratio': round(ratio, 3),
            }

    return {'class_id': 'VI', 'class_name': 'Высокий', 'description': 'Паводковый', 'ratio': round(ratio, 3)}


def wetted_perimeter_method(
    Q_range: np.ndarray,
    B: np.ndarray,
    P: np.ndarray,
    Q_critical_percent: float = 70,
) -> dict:
    """
    Метод мокрого периметра для определения минимального экологического стока.

    Минимальный Q соответствует перелому на кривой «Расход — мокрый периметр».

    Parameters:
        Q_range: расходы для расчёта
        B: ширины при каждом расходе
        P: мокрые периметры при каждом расходе
        Q_critical_percent: процент от Q для определения минимума

    Returns:
        Dict: Q_eco, P_eco, critical_point
    """
    Q = np.array(Q_range, dtype=float)
    P_arr = np.array(P, dtype=float)

    dP_dQ = np.diff(P_arr) / np.diff(Q)

    if len(dP_dQ) > 0:
        inflection_idx = np.argmin(dP_dQ)
        Q_eco = float(Q[inflection_idx]) if inflection_idx < len(Q) else float(np.percentile(Q, 10))
    else:
        Q_eco = float(np.percentile(Q, Q_critical_percent))

    return {
        'Q_eco_m3_s': round(Q_eco, 2),
        'critical_point_index': int(inflection_idx) if len(dP_dQ) > 0 else 0,
        'P_at_eco': round(float(np.interp(Q_eco, Q, P_arr)), 2),
    }


def min_flow_comparison(
    Q_annual_mean: float,
    Q_monthly_mean: np.ndarray | None = None,
    Q_min_series: np.ndarray | None = None,
) -> pd.DataFrame:
    """
    Сравнение различных методов расчёта минимального экологического стока.

    Parameters:
        Q_annual_mean: среднегодовой расход
        Q_monthly_mean: месячные расходы
        Q_min_series: минимальные значения (если есть)

    Returns:
        DataFrame с результатами
    """
    methods = []

    # Метод 1: 10% от среднего
    methods.append({
        'Метод': '10% от Q_ср',
        'Q_эколог_м3_с': round(Q_annual_mean * 0.10, 2),
        'Ссылка': 'СП 32 п.8 (мин.) - атрибуция ошибочна',
    })

    # Метод 2: 30% от среднего
    methods.append({
        'Метод': '30% от Q_ср',
        'Q_эколог_м3_с': round(Q_annual_mean * 0.30, 2),
        'Ссылка': 'СП 32 п.8 (опт.) - атрибуция ошибочна',
    })

    # Метод 3: 7Q10
    if Q_min_series is not None and len(Q_min_series) > 5:
        from core.hydrorash.min_runoff_extended import q7_10
        q710 = q7_10(Q_min_series)
        methods.append({
            'Метод': '7Q10',
            'Q_эколог_м3_с': round(q710['Q7_10_value'], 2),
            'Ссылка': 'СП 32, Р 9.1.11 - атрибуция ошибочна',
        })

    # Метод 4: Тессман (среднегодовой)
    tessmann_val = Q_annual_mean * 0.25
    methods.append({
        'Метод': 'Тессман (среднегодовой)',
        'Q_эколог_м3_с': round(tessmann_val, 2),
        'Ссылка': 'Р 9.1.11',
    })

    # Метод 5: Сезонный Тессман (среднее за год)
    if Q_monthly_mean is not None:
        seasonal = tessmann_seasonal(Q_annual_mean, 'central', Q_monthly_mean)
        methods.append({
            'Метод': 'Сезонный Тессман',
            'Q_эколог_м3_с': seasonal['Q_eco_annual_mean'],
            'Ссылка': 'СП 32, прил. 8 - атрибуция ошибочна',
        })

    return pd.DataFrame(methods)
