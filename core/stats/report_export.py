"""
core/stats/report_export.py
Экспорт технического отчёта по СП 482.1325800.2020 (Раздел 9)

Формирование отчёта в формате DOCX (python-docx) или TXT.
Обязательные разделы по СП 482:
1. Общие сведения
2. Характеристика объекта изысканий
3. Методика работ
4. Результаты статистической обработки
5. Расчётные гидрологические характеристики
6. Выводы и рекомендации
"""

import os
from typing import Dict, List, Optional
from datetime import datetime


def generate_txt_report(
    output_path: str,
    post_name: str,
    stats: Dict,
    frequency_curve=None,
    max_runoff_curve=None,
    min_runoff_curve=None,
    extension_info: Dict = None,
    composite_info: Dict = None,
    gts_info: Dict = None,
    ice_info: Dict = None,
    comments: str = ""
) -> str:
    """
    Генерация текстового техотчёта по СП 482.

    Parameters:
        output_path: путь для сохранения .txt файла
        post_name: название поста
        stats: статистические характеристики (из compute_basic_stats)
        frequency_curve: DataFrame кривой обеспечённости
        max_runoff_curve: DataFrame кривой максимумов
        min_runoff_curve: DataFrame кривой минимумов
        extension_info: информация об удлинении
        composite_info: информация о составной кривой
        gts_info: информация о классе ГТС
        ice_info: информация о ледовых явлениях
        comments: дополнительные комментарии

    Returns:
        Путь к сохранённому файлу
    """
    lines = []

    lines.append("=" * 80)
    lines.append("ТЕХНИЧЕСКИЙ ОТЧЁТ")
    lines.append("Определение основных расчётных гидрологических характеристик")
    lines.append(f"Согласно СП 482.1325800.2020, СП 33-101-2003")
    lines.append("=" * 80)
    lines.append("")

    lines.append("1. ОБЩИЕ СВЕДЕНИЯ")
    lines.append("-" * 40)
    lines.append(f"  Пост: {post_name}")
    lines.append(f"  Период наблюдений: {stats.get('n', '—')} лет")
    lines.append(f"  Дата формирования: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"  Нормативная база: СП 482.1325800.2020, СП 33-101-2003")
    lines.append("")

    lines.append("2. СТАТИСТИЧЕСКИЕ ХАРАКТЕРИСТИКИ")
    lines.append("-" * 40)
    if stats:
        for key, val in stats.items():
            if key not in ('warnings', 'length_warnings'):
                lines.append(f"  {key}: {val}")
    lines.append("")

    if stats.get('warnings') or stats.get('length_warnings'):
        lines.append("  ПРЕДУПРЕЖДЕНИЯ:")
        for w in (stats.get('warnings') or []) + (stats.get('length_warnings') or []):
            lines.append(f"    {w}")
        lines.append("")

    if frequency_curve is not None:
        lines.append("3. КРИВАЯ ОБЕСПЕЧЕННОСТИ")
        lines.append("-" * 40)
        lines.append("  P_%      Q, м³/с")
        lines.append("  " + "-" * 20)
        for _, row in frequency_curve.iterrows():
            p_val = row.get('P_%', row.get('P', ''))
            q_val = row.get('Q', row.get('Q_max', row.get('Q_min', '')))
            lines.append(f"  {p_val:>7}   {q_val:>10}")
        lines.append("")

    if max_runoff_curve is not None:
        lines.append("4. МАКСИМАЛЬНЫЙ СТОК")
        lines.append("-" * 40)
        lines.append("  P_%      Q_max, м³/с    kp")
        lines.append("  " + "-" * 30)
        for _, row in max_runoff_curve.iterrows():
            lines.append(f"  {row.get('P_%', ''):>7}   {row.get('Q_max', ''):>10}   {row.get('kp', ''):>8}")
        lines.append("")

    if min_runoff_curve is not None:
        lines.append("5. МИНИМАЛЬНЫЙ СТОК")
        lines.append("-" * 40)
        lines.append("  P_%      Q_min, м³/с")
        lines.append("  " + "-" * 20)
        for _, row in min_runoff_curve.iterrows():
            lines.append(f"  {row.get('P_%', ''):>7}   {row.get('Q_min', ''):>10}")
        lines.append("")

    if extension_info:
        lines.append("6. УДЛИНЕНИЕ РЯДА НАБЛЮДЕНИЙ")
        lines.append("-" * 40)
        lines.append(f"  Метод: {extension_info.get('method', '—')}")
        lines.append(f"  Река-аналог: {extension_info.get('analog_name', '—')}")
        lines.append(f"  Ряд до: {extension_info.get('n_original', '—')} лет")
        lines.append(f"  Ряд после: {extension_info.get('n_extended', '—')} лет")
        lines.append(f"  R = {extension_info.get('R', '—')}")
        lines.append(f"  ε до: {extension_info.get('epsilon_original', '—')}%")
        lines.append(f"  ε после: {extension_info.get('epsilon_extended', '—')}%")
        lines.append(f"  Надёжность: {extension_info.get('reliability', '—')}")
        lines.append("")

    if composite_info:
        lines.append("7. СОСТАВНАЯ КРИВАЯ")
        lines.append("-" * 40)
        lines.append(f"  Год разрыва: {composite_info.get('break_year', '—')}")
        lines.append(f"  Часть 1: n={composite_info.get('n_part1', '—')}, "
                     f"Cv={composite_info.get('part1_stats', {}).get('cv', '—')}, "
                     f"Cs={composite_info.get('part1_stats', {}).get('cs', '—')}")
        lines.append(f"  Часть 2: n={composite_info.get('n_part2', '—')}, "
                     f"Cv={composite_info.get('part2_stats', {}).get('cv', '—')}, "
                     f"Cs={composite_info.get('part2_stats', {}).get('cs', '—')}")
        homo = composite_info.get('homogeneity_test', {})
        lines.append(f"  Тест Штрихова: p={homo.get('u_p', '—')}, "
                     f"{'однородны' if homo.get('is_homogeneous') else 'НЕОДНОРОДНЫ'}")
        lines.append("")

    if gts_info:
        lines.append("8. РАСЧЁТНЫЕ ХАРАКТЕРИСТИКИ ГТС")
        lines.append("-" * 40)
        lines.append(f"  Класс ГТС: {gts_info.get('gts_class', '—')}")
        for key, pt in gts_info.get('gts_points', {}).items():
            lines.append(f"  {pt.get('label', key)}: P={pt.get('P_%', '')}%, Q={pt.get('Q', '')} м³/с")
        lines.append("")

    if ice_info:
        lines.append("9. ЛЕДОВЫЕ ЯВЛЕНИЯ")
        lines.append("-" * 40)
        for k, v in ice_info.items():
            lines.append(f"  {k}: {v}")
        lines.append("")

    lines.append("10. ВЫВОДЫ И РЕКОМЕНДАЦИИ")
    lines.append("-" * 40)
    if stats.get('reliability_class') == 'Ненадёжная':
        lines.append("  ⚠️ Ряд наблюдений ненадёжный. Рекомендуется удлинение.")
    elif stats.get('reliability_class') == 'Пониженная надёжность':
        lines.append("  ⚠️ Ряд наблюдений пониженной надёжности.")
    else:
        lines.append("  ✅ Ряд наблюдений достаточной надёжности.")

    if extension_info and extension_info.get('is_significant') is False:
        lines.append("  ⚠️ Корреляция с рекой-аналогом статистически незначима.")

    if composite_info and not composite_info.get('homogeneity_test', {}).get('is_homogeneous', True):
        lines.append("  ⚠️ Ряд неоднороден. Рекомендуется составная кривая обеспечённости.")

    lines.append("")
    if comments:
        lines.append("ДОПОЛНИТЕЛЬНЫЕ КОММЕНТАРИИ:")
        lines.append(comments)
        lines.append("")

    lines.append("=" * 80)
    lines.append("Отчёт сформирован автоматически программой ГидроСтатистика 2026")
    lines.append("Согласно СП 482.1325800.2020, СП 33-101-2003")
    lines.append("=" * 80)

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return output_path


def generate_excel_report(
    output_path: str,
    post_name: str,
    stats: Dict,
    frequency_curve=None,
    max_runoff_curve=None,
    min_runoff_curve=None,
) -> str:
    """
    Генерация Excel-отчёта с несколькими листами.
    """
    import pandas as pd

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        info_df = pd.DataFrame({
            'Параметр': ['Пост', 'Длина ряда', 'Надёжность', 'Дата отчёта', 'Нормативная база'],
            'Значение': [
                post_name,
                f"{stats.get('n', '—')} лет",
                stats.get('reliability_class', '—'),
                datetime.now().strftime('%Y-%m-%d %H:%M'),
                'СП 482.1325800.2020, СП 33-101-2003'
            ]
        })
        info_df.to_excel(writer, sheet_name='Информация', index=False)

        stats_df = pd.DataFrame([
            (k, v) for k, v in stats.items()
            if k not in ('warnings', 'length_warnings')
        ], columns=['Показатель', 'Значение'])
        stats_df.to_excel(writer, sheet_name='Статистика', index=False)

        if frequency_curve is not None:
            frequency_curve.to_excel(writer, sheet_name='Кривая_обеспеченности', index=False)

        if max_runoff_curve is not None:
            max_runoff_curve.to_excel(writer, sheet_name='Максимальный_сток', index=False)

        if min_runoff_curve is not None:
            min_runoff_curve.to_excel(writer, sheet_name='Минимальный_сток', index=False)

    return output_path
