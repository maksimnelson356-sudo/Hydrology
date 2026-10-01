"""
core/hydrorash/ecological_flow.py
Экологический сток: сезонный Тессман, ECOFRAME, метод мокрого периметра.

Прежняя ссылка на СП 32.13330.2018 ОШИБОЧНА: по официальным метаданным это
«Канализация. Наружные сети и сооружения» — предмет не совпадает.

ИСТОЧНИК МЕТОДА НАЙДЕН 2026-09-28 (ранее значился как неустановленный, причём
в одной из версий был назван «греческой статьёй» — это было неверно, статья
не греческая):

  Tessman, S.A. 1980. Environmental Assessment, Technical Appendix E, in
  Environmental Use Sector Reconnaissance Elements of the Western Dakotas
  Region of South Dakota Study. Water Resources Research Institute, South
  Dakota State University, Brookings, SD. (Ранняя версия того же отчёта —
  1979.)

РАСХОЖДЕНИЕ СУЩЕСТВЕННОЕ. Документированное правило Тессмана не содержит
ни α_i, ни β_i и не зависит от «типа региона». Оно трёхчастное, на среднем
месячном расходе MMF и среднегодовом MAF:

  REF = MMF            если MMF < 0,4·MAF   (весь естественный сток месяца)
  REF = 0,4·MAF        если 0,4·MMF < 0,4·MAF <= MMF
  REF = 0,4·MMF        иначе

То есть в методе Тессмана РЕШАЮЩИЙ признак — сравнение месяца со среднегодовым,
а не «северные/центральные/южные/горные» реки. Реализованная здесь формула
Q_эколог_i = α_i · Q_ср · (Q_i / Q_ср)^β_i с наборами α/β по типу региона —
НЕ метод Тессмана и не его региональная калибровка. Это инженерная конструкция,
получившая имя метода, к которому отношения не имеет. Доказательство: в
первоисточнике 1980 года ни типов региона, ни месячных коэффициентов нет, а
коэффициент 0,4 в нём есть.

Документированное правило реализовано отдельно: tessman_1980(). Функция
tessmann_seasonal() сохранена для совместимости с прежним API и помечена как
инженерная, а не как Тессман.

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

ИТОГ: атрибуция «метод Тессмана 1980» теперь ПОДТВЕРЖДЕНА как источник, но
НЕ как источник реализованной формулы. Формула
Q_эколог_i = α_i · Q_ср · (Q_i / Q_ср)^β_i и наборы α/β в
SEASONAL_TESSMANN_PARAMS — инженерная конструкция без нормативного
происхождения, и в отчёте её нельзя предъявлять как Тессмана.

Основные функции:
- tessman_1980 — документированное правило Тессмана (Tessman 1980, прил. E)
- tessmann_seasonal — инженерная конструкция с α/β; имя историческое,
  к методу Тессмана отношения не имеет
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


MONTH_LABELS = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
                'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']

# Коэффициент из первоисточника: 40 % от среднегодового как нижняя граница.
TESSMAN_1980_FLOOR = 0.4


def tessman_1980(
    Q_annual_mean: float,
    Q_monthly_mean: np.ndarray | list[float] | None = None,
) -> dict:
    """Документированное правило Тессмана (Tessman S.A., 1980, Technical Appendix E).

    Метод уточняет Теннанта помесячно. Для каждого месяца решающим признаком
    служит сравнение среднемесячного расхода MMF с 40 % среднегодового MAF, а не
    принадлежность реки к «типу региона»:

    - ``MMF < 0,4·MAF``           → рекомендуется весь естественный сток месяца
    - ``0,4·MMF < 0,4·MAF <= MMF`` → удерживается 0,4·MAF
    - иначе                        → 0,4·MMF

    Смысл: в засушливые месяцы фиксированная доля нереалистична, поэтому
    берётся полный естественный расход; в среднем диапазоне держится 40 %
    годового; в многоводные месяцы доля от самого месяца сохраняет сезонные
    паводковые всплески.

    Обратите внимание на границы веток: третья ветка «0,4·MMF» срабатывает
    ТОЛЬКО при ``MMF >= MAF``, потому что условие её negation -
    ``0,4·MMF >= 0,4·MAF``, то есть месяц не суше среднегодового. При
    ``MMF == MAF`` попадает именно она, при MMF чуть ниже - вторая. Это легко
    перепутать при чтении и при проверке тестами.

    Parameters:
        Q_annual_mean: среднегодовой расход MAF, м³/с
        Q_monthly_mean: 12 среднемесячных расходов MMF, м³/с

    Returns:
        Dict с monthly_Q_eco, ветками правила по месяцам и долей от MAF.
    """
    if Q_annual_mean <= 0:
        raise ValueError("Среднегодовой расход должен быть положительным")

    if Q_monthly_mean is None:
        raise ValueError("Нужны 12 среднемесячных расходов: правило без MMF не работает")

    mmf = np.asarray(Q_monthly_mean, dtype=float)[:12]
    if mmf.size != 12:
        raise ValueError(f"Ожидалось 12 значений MMF, получено {mmf.size}")
    if not np.all(np.isfinite(mmf)):
        raise ValueError("MMF содержит нечисловые значения")

    floor_maf = TESSMAN_1980_FLOOR * Q_annual_mean
    floor_mmf = TESSMAN_1980_FLOOR * mmf

    q_eco = np.where(mmf < floor_maf, mmf, np.where(floor_mmf < floor_maf, floor_maf, floor_mmf))

    rows = []
    for i in range(12):
        if mmf[i] < floor_maf:
            branch = "весь естественный сток (MMF < 0,4·MAF)"
        elif floor_mmf[i] < floor_maf:
            branch = "0,4·MAF"
        else:
            branch = "0,4·MMF"
        rows.append({
            'Месяц': MONTH_LABELS[i],
            'Q_ср_месяц': round(float(mmf[i]), 2),
            'Q_эколог': round(float(q_eco[i]), 2),
            'ветка': branch,
        })

    return {
        'source': ('Tessman S.A. 1980, Environmental Assessment, Technical Appendix E, '
                   'Water Resources Research Institute, South Dakota State University'),
        'method': 'Tessman 1980 (документированное трёхчастное правило)',
        'Q_ср_год': round(float(Q_annual_mean), 2),
        'floor_0.4_MAF': round(float(floor_maf), 2),
        'monthly': rows,
        'monthly_Q_eco': [row['Q_эколог'] for row in rows],
        'mean_Q_eco': round(float(np.mean(q_eco)), 2),
        'share_of_MAF_percent': round(float(np.sum(q_eco) / (12 * Q_annual_mean) * 100), 1),
        'normative': ('первоисточник — технический отчёт, не нормативный документ; '
                      'коэффициент 0,4 требует региональной калибровки'),
    }


def tessmann_seasonal(
    Q_annual_mean: float,
    region_type: str = 'central',
    Q_monthly_mean: np.ndarray | None = None,
) -> dict:
    """
    ИНЖЕНЕРНАЯ КОНСТРУКЦИЯ. Имя историческое, к методу Тессмана отношения не имеет.

    Ни α_i, ни β_i, ни «типы региона» в методе Тессмана (Tessman 1980) нет —
    документированное правило реализовано в tessman_1980(). Эта функция
    сохранена для совместимости с прежним API и в отчёте предъявляться как
    Тессман не должна.

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
