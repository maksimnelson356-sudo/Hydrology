"""
core/gts_reference.py
Справочник классов гидротехнических сооружений
согласно СП 58.13330.2019 "Гидротехнические сооружения. Основные положения"
"""

from typing import Dict, List, Optional
from enum import IntEnum


class GTSClass(IntEnum):
    """Класс капитальности гидротехнического сооружения"""
    CLASS_I = 1
    CLASS_II = 2
    CLASS_III = 3
    CLASS_IV = 4


# Таблица 6.1 СП 58.13330.2019
# Расчетные обеспеченности для различных классов ГТС
GTS_PROBABILITIES = {
    GTSClass.CLASS_I: {
        'max_discharge': {
            'osnovnoy': 0.001,  # 0.1% - основной расчетный случай
            'proverochniy': 0.0001,  # 0.01% - проверочный расчетный случай
        },
        'min_discharge': {
            'osnovnoy': 0.95,  # 95% - для водоснабжения
            'proverochniy': 0.97,  # 97% - для энергетики
        },
        'description': 'Особо ответственные ГТС (высота плотины > 100м или водохранилища V > 1000 млн.м³)'
    },
    GTSClass.CLASS_II: {
        'max_discharge': {
            'osnovnoy': 0.003,  # 0.3%
            'proverochniy': 0.001,  # 0.1%
        },
        'min_discharge': {
            'osnovnoy': 0.95,
            'proverochniy': 0.97,
        },
        'description': 'Ответственные ГТС (высота плотины 50–100м или V = 100–1000 млн.м³)'
    },
    GTSClass.CLASS_III: {
        'max_discharge': {
            'osnovnoy': 0.01,  # 1%
            'proverochniy': 0.003,  # 0.3%
        },
        'min_discharge': {
            'osnovnoy': 0.90,
            'proverochniy': 0.95,
        },
        'description': 'Средней ответственности ГТС (высота плотины 15–50м или V = 10–100 млн.м³)'
    },
    GTSClass.CLASS_IV: {
        'max_discharge': {
            'osnovnoy': 0.03,  # 3%
            'proverochniy': 0.01,  # 1%
        },
        'min_discharge': {
            'osnovnoy': 0.80,
            'proverochniy': 0.90,
        },
        'description': 'Некапитальные ГТС (высота плотины < 15м или V < 10 млн.м³)'
    },
}


def get_probabilities_for_class(gts_class: GTSClass, case_type: str = 'osnovnoy') -> Dict[str, float]:
    """
    Получить расчетные обеспеченности для заданного класса ГТС.

    Параметры:
        gts_class: класс капитальности ГТС (I, II, III, IV)
        case_type: тип расчетного случая ('osnovnoy' или 'proverochniy')

    Возвращает:
        Словарь с обеспеченностями для максимальных и минимальных расходов
    """
    if gts_class not in GTS_PROBABILITIES:
        raise ValueError(f"Неизвестный класс ГТС: {gts_class}")

    if case_type not in ['osnovnoy', 'proverochniy']:
        raise ValueError("case_type должен быть 'osnovnoy' или 'proverochniy'")

    data = GTS_PROBABILITIES[gts_class]
    return {
        'max_discharge_p': data['max_discharge'][case_type],
        'min_discharge_p': data['min_discharge'][case_type],
        'description': data['description'],
        'case_type': case_type
    }


def get_standard_probabilities(gts_class: GTSClass) -> List[float]:
    """
    Получить стандартный набор обеспеченностей для построения кривых обеспеченности.

    Параметры:
        gts_class: класс капитальности ГТС

    Возвращает:
        Список обеспеченностей в долях единицы
    """
    probs = get_probabilities_for_class(gts_class, 'osnovnoy')
    max_p = probs['max_discharge_p']
    min_p = probs['min_discharge_p']

    # Базовый набор обеспеченностей
    standard = [0.01, 0.03, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.8, 0.9, 0.95, 0.99]

    # Добавляем расчетные обеспеченности если их нет в стандартном наборе
    result = sorted(set(standard + [max_p, min_p]))

    return result


def classify_gts_by_parameters(dam_height_m: Optional[float] = None,
                               reservoir_volume_mln_m3: Optional[float] = None) -> GTSClass:
    """
    Определить класс ГТС по параметрам сооружения.

    Параметры:
        dam_height_m: высота плотины, м
        reservoir_volume_mln_m3: объем водохранилища, млн.м³

    Возвращает:
        Класс капитальности ГТС

    Пороги по СП 58.13330.2019 (Таблица 6.1):
        Класс I:   H > 100 м  ИЛИ  V > 1000 млн м³
        Класс II:  H 50–100 м ИЛИ  V 100–1000 млн м³
        Класс III: H 15–50 м  ИЛИ  V 10–100 млн м³
        Класс IV:  H < 15 м   ИЛИ  V < 10 млн м³
    """
    # Классификация по высоте плотины (СП 58.13330.2019, табл. 6.1)
    if dam_height_m is not None:
        if dam_height_m > 100:
            return GTSClass.CLASS_I
        elif dam_height_m > 50:
            return GTSClass.CLASS_II
        elif dam_height_m > 15:
            return GTSClass.CLASS_III
        else:
            return GTSClass.CLASS_IV

    # Классификация по объёму водохранилища (СП 58.13330.2019, табл. 6.1)
    if reservoir_volume_mln_m3 is not None:
        if reservoir_volume_mln_m3 > 1000:
            return GTSClass.CLASS_I
        elif reservoir_volume_mln_m3 > 100:
            return GTSClass.CLASS_II
        elif reservoir_volume_mln_m3 > 10:
            return GTSClass.CLASS_III
        else:
            return GTSClass.CLASS_IV

    # По умолчанию — самый строгий класс
    return GTSClass.CLASS_I


def get_gts_info() -> Dict[GTSClass, Dict]:
    """
    Получить полную справочную информацию по всем классам ГТС.

    Возвращает:
        Словарь с информацией по каждому классу
    """
    return {
        gts_class: {
            'class': gts_class,
            'class_name': f"Класс {gts_class}",
            'description': data['description'],
            'max_discharge_osnovnoy_%': data['max_discharge']['osnovnoy'] * 100,
            'max_discharge_proverochniy_%': data['max_discharge']['proverochniy'] * 100,
            'min_discharge_osnovnoy_%': data['min_discharge']['osnovnoy'] * 100,
            'min_discharge_proverochniy_%': data['min_discharge']['proverochniy'] * 100,
        }
        for gts_class, data in GTS_PROBABILITIES.items()
    }


def format_gts_reference_table() -> str:
    """
    Форматировать справочную таблицу для отображения.

    Возвращает:
        Строка с форматированной таблицей
    """
    table = []
    table.append("=" * 120)
    table.append("СПРАВОЧНИК КЛАССОВ ГТС (СП 58.13330.2019, Таблица 6.1)")
    table.append("=" * 120)
    table.append("")

    for gts_class in [GTSClass.CLASS_I, GTSClass.CLASS_II, GTSClass.CLASS_III, GTSClass.CLASS_IV]:
        data = GTS_PROBABILITIES[gts_class]
        table.append(f"КЛАСС {gts_class}: {data['description']}")
        table.append("-" * 120)
        table.append(f"  Максимальный расход (паводок):")
        table.append(f"    • Основной расчетный случай:     P = {data['max_discharge']['osnovnoy']*100:.2f}%")
        table.append(f"    • Проверочный расчетный случай:  P = {data['max_discharge']['proverochniy']*100:.3f}%")
        table.append(f"  Минимальный расход (межень):")
        table.append(f"    • Основной расчетный случай:     P = {data['min_discharge']['osnovnoy']*100:.1f}%")
        table.append(f"    • Проверочный расчетный случай:  P = {data['min_discharge']['proverochniy']*100:.1f}%")
        table.append("")

    table.append("=" * 120)
    table.append("ПРИМЕЧАНИЯ:")
    table.append("• Для максимальных расходов: чем ниже P (%), тем больше расчетный расход")
    table.append("• Для минимальных расходов: чем выше P (%), тем меньше расчетный расход")
    table.append("• Основной расчетный случай - для проектирования сооружения")
    table.append("• Проверочный расчетный случай - для проверки прочности и устойчивости")
    table.append("=" * 120)

    return "\n".join(table)


# Пример использования
if __name__ == "__main__":
    print(format_gts_reference_table())
    print("\n\nПример определения класса ГТС:")
    print(f"Плотина высотой 35м → {classify_gts_by_parameters(dam_height_m=35)}")
    print(f"Водохранилище 500 млн.м³ → {classify_gts_by_parameters(reservoir_volume_mln_m3=500)}")

    print("\n\nРасчетные обеспеченности для класса II (основной случай):")
    probs = get_probabilities_for_class(GTSClass.CLASS_II, 'osnovnoy')
    print(f"  Максимальный расход: P = {probs['max_discharge_p']*100:.1f}%")
    print(f"  Минимальный расход: P = {probs['min_discharge_p']*100:.1f}%")

    print("\n\nСтандартный набор обеспеченностей для класса III:")
    std_probs = get_standard_probabilities(GTSClass.CLASS_III)
    print(f"  {[f'{p*100:.2f}%' for p in std_probs]}")
