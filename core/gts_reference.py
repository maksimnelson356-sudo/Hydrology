"""
core/gts_reference.py
Справочник классов гидротехнических сооружений
по СП 58.13330.2019 "Гидротехнические сооружения. Основные положения"

Проверено по полному тексту СП 58.13330.2019 (2026-09-28):

- **Таблицы 6.1 в стандарте НЕТ.** Прежняя ссылка кода на неё была ложной.
- Вероятности превышения расчётных максимальных расходов — **таблица 8.2**,
  раздел 8 «Основные расчетные положения».
- Класс ответственности по высоте и типу грунтов оснований — **таблица Б.1**;
  она зависит от типа плотины и грунтов основания, поэтому единой шкалы
  «высота -> класс» в стандарте нет.
- Значения обеспеченностей минимального стока в СП 58 **отсутствуют**:
  стандарт требует лишь «обеспечения минимального расхода, необходимого для
  санитарного попуска и устойчивого водоснабжения» без числовых величин.
  Приведённые ниже значения — инженерная оценка, а не норматив.
"""

from enum import IntEnum


class GTSClass(IntEnum):
    """Класс капитальности гидротехнического сооружения"""
    CLASS_I = 1
    CLASS_II = 2
    CLASS_III = 3
    CLASS_IV = 4


# СП 58.13330.2019, таблица 8.2 «Ежегодные вероятности превышения расчетных
# максимальных расходов воды, в процентах» — значения проверены по тексту.
# Основной:  I 0,1 | II 1,0 | III 3,0 | IV 5,0
# Поверочный: I 0,01 | II 0,1 | III 0,5 | IV 1,0
# Ранее в коде стояли 0,3 / 1,0 / 3,0 % для основного случая классов II–IV
# и 0,3 / 1,0 % для поверочного III–IV, что тексту стандарта не соответствует.
GTS_PROBABILITIES = {
    GTSClass.CLASS_I: {
        'max_discharge': {
            'osnovnoy': 0.001,  # 0,1 % - СП 58, табл. 8.2
            'proverochniy': 0.0001,  # 0,01 % - СП 58, табл. 8.2
        },
        'min_discharge': {
            'osnovnoy': 0.95,  # инженерная оценка - в СП 58 нет
            'proverochniy': 0.97,  # инженерная оценка - в СП 58 нет
        },
        'description': 'Класс I (СП 58, табл. Б.1: бетонные/железобетонные плотины при H >= 100 м; грунтовые при H >= 80 м)'
    },
    GTSClass.CLASS_II: {
        'max_discharge': {
            'osnovnoy': 0.01,  # 1,0 % - СП 58, табл. 8.2
            'proverochniy': 0.001,  # 0,1 % - СП 58, табл. 8.2
        },
        'min_discharge': {
            'osnovnoy': 0.95,  # инженерная оценка - в СП 58 нет
            'proverochniy': 0.97,  # инженерная оценка - в СП 58 нет
        },
        'description': 'Класс II (СП 58, табл. Б.1: бетонные/железобетонные при 60 <= H < 100 м; грунтовые при 50 <= H < 80 м)'
    },
    GTSClass.CLASS_III: {
        'max_discharge': {
            'osnovnoy': 0.03,  # 3,0 % - СП 58, табл. 8.2
            'proverochniy': 0.005,  # 0,5 % - СП 58, табл. 8.2
        },
        'min_discharge': {
            'osnovnoy': 0.90,  # инженерная оценка - в СП 58 нет
            'proverochniy': 0.95,  # инженерная оценка - в СП 58 нет
        },
        'description': 'Класс III (СП 58, табл. Б.1: бетонные/железобетонные при 25 <= H < 60 м; грунтовые при 20 <= H < 50 м)'
    },
    GTSClass.CLASS_IV: {
        'max_discharge': {
            'osnovnoy': 0.05,  # 5,0 % - СП 58, табл. 8.2
            'proverochniy': 0.01,  # 1,0 % - СП 58, табл. 8.2
        },
        'min_discharge': {
            'osnovnoy': 0.80,  # инженерная оценка - в СП 58 нет
            'proverochniy': 0.90,  # инженерная оценка - в СП 58 нет
        },
        'description': 'Класс IV (СП 58, табл. Б.1: бетонные/железобетонные при H < 25 м; грунтовые при H < 20 м)'
    },
}


def get_probabilities_for_class(gts_class: GTSClass, case_type: str = 'osnovnoy') -> dict[str, float]:
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


def get_standard_probabilities(gts_class: GTSClass) -> list[float]:
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


def classify_gts_by_parameters(dam_height_m: float | None = None,
                               reservoir_volume_mln_m3: float | None = None) -> GTSClass:
    """
    Определить класс ГТС по параметрам сооружения.

    ВНИМАНИЕ: функция — инженерная эвристика, а не нормативная таблица.

    По полному тексту СП 58.13330.2019 класс ответственности определяется
    **таблицей Б.1** и зависит одновременно от высоты сооружения, типа плотины
    и типа грунтов основания. Единой шкалы «высота -> класс» стандарт не содержит,
    поэтому пороги ниже — компромисс, а не выдержка из текста:

        бетонные/железобетонные:  I >= 100 | II 60–100 | III 25–60 | IV < 25
        грунтовые (основание А):   I >=  80 | II 50–80  | III 20–50 | IV < 20

    Классификация по **объёму водохранилища** (пороги 1000 / 100 / 10 млн м³)
    в СП 58.13330.2019 отсутствует — стандарт оперирует высотой и типом
    грунтов основания, а не объёмом водохранилища. Этот критерий оставлен
    как инженерный и нормативно не подтверждён.

    Параметры:
        dam_height_m: высота плотины, м
        reservoir_volume_mln_m3: объем водохранилища, млн.м³ (не подтверждён СП 58)

    Возвращает:
        Класс капитальности ГТС
    """
    # Классификация по высоте плотины - инженерная эвристика, СП 58 табл. Б.1
    # требует также тип плотины и тип грунтов основания
    if dam_height_m is not None:
        if dam_height_m > 100:
            return GTSClass.CLASS_I
        elif dam_height_m > 50:
            return GTSClass.CLASS_II
        elif dam_height_m > 15:
            return GTSClass.CLASS_III
        else:
            return GTSClass.CLASS_IV

    # Классификация по объёму водохранилища - инженерная эвристика, в СП 58 нет
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


def get_gts_info() -> dict[GTSClass, dict]:
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
    table.append("СПРАВОЧНИК КЛАССОВ ГТС (СП 58.13330.2019, Таблица 8.2)")
    table.append("=" * 120)
    table.append("")

    for gts_class in [GTSClass.CLASS_I, GTSClass.CLASS_II, GTSClass.CLASS_III, GTSClass.CLASS_IV]:
        data = GTS_PROBABILITIES[gts_class]
        table.append(f"КЛАСС {gts_class}: {data['description']}")
        table.append("-" * 120)
        table.append("  Максимальный расход (паводок):")
        table.append(f"    • Основной расчетный случай:     P = {data['max_discharge']['osnovnoy']*100:.2f}%")
        table.append(f"    • Проверочный расчетный случай:  P = {data['max_discharge']['proverochniy']*100:.3f}%")
        table.append("  Минимальный расход (межень):")
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
