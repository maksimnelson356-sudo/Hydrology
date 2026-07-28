"""
create_unified_template.py
Генератор единого Excel-шаблона для всех вкладок приложения.

Листы:
  Гидропост   — ряд наблюдений для статистики/кривых/трендов
  Работа1     — норма годового стока (расчётная река + аналог)
  Работа2     — внутригодовое распределение (помесячные расходы)
  Работа3     — минимальный сток (зимние и летние минимумы)
  ГТС         — параметры ГТС для классификации

Пустые листы — данные по ним не загружаются.
"""

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment


def create_unified_template(path="unified_template.xlsx"):
    """Создаёт Excel-шаблон со всеми листами."""
    wb = Workbook()

    header_fill = PatternFill(start_color="2F5496", end_color="2F5496", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=10)
    yellow_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
    info_font = Font(italic=True, color="C00000", size=9)
    thin = Border(left=Side(style='thin'), right=Side(style='thin'),
                  top=Side(style='thin'), bottom=Side(style='thin'))

    def style_cell(ws, row, col, value, font=None, fill=None):
        cell = ws.cell(row=row, column=col, value=value)
        if font: cell.font = font
        if fill: cell.fill = fill
        cell.border = thin
        cell.alignment = Alignment(horizontal='center')
        return cell

    def write_header_row(ws, row, headers):
        for c, h in enumerate(headers, 1):
            style_cell(ws, row, c, h, font=header_fill, fill=header_fill)
            cell = ws.cell(row=row, column=c)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = thin
            cell.alignment = Alignment(horizontal='center')

    # ========== ЛИСТ 1: Гидропост ==========
    ws1 = wb.active
    ws1.title = "Гидропост"
    ws1['A1'] = "Данные гидрологического поста для статистической обработки"
    ws1['A1'].font = Font(bold=True, size=12)
    ws1.merge_cells('A1:D1')
    ws1['A2'] = "Заполни данные в жёлтых ячейках или оставь как есть"
    ws1['A2'].font = info_font
    ws1.merge_cells('A2:D2')

    # Пытаемся прочитать test_data_clean.xlsx
    post_data = {}
    post_name = "Расход Q, м³/с"  # имя по умолчанию
    try:
        df_test = pd.read_excel("test_data_clean.xlsx")
        year_col = None
        for c in df_test.columns:
            if str(c).strip().lower() in ['год', 'year']:
                year_col = c
                break
        if year_col:
            post_cols = [c for c in df_test.columns if c != year_col]
            if post_cols:
                first_post = post_cols[0]
                post_name = str(first_post)  # имя поста = номер/название
                ws1['A4'] = "Пост:"
                ws1['B4'] = post_name
                ws1['B4'].fill = yellow_fill
                for _, row in df_test.iterrows():
                    y = row[year_col]
                    q = row[first_post]
                    if pd.notna(y) and pd.notna(q):
                        post_data[int(y)] = round(float(q), 2)
    except (FileNotFoundError, ValueError, KeyError, TypeError):
        pass  # шаблон создаётся с дефолтными данными

    if not post_data:
        ws1['A4'] = "Название поста:"
        ws1['B4'] = post_name
        ws1['B4'].fill = yellow_fill
        for y, q in zip(range(1960, 1980), [
            120, 145, 98, 156, 134, 110, 167, 129, 143, 108,
            152, 118, 136, 147, 102, 158, 125, 139, 151, 106
        ]):
            post_data[y] = q

    write_header_row(ws1, 7, ["Год", post_name])
    for i, (y, q) in enumerate(sorted(post_data.items()), start=8):
        style_cell(ws1, i, 1, y, fill=yellow_fill)
        style_cell(ws1, i, 2, q, fill=yellow_fill)

    # ========== ЛИСТ 2: Работа1 ==========
    ws2 = wb.create_sheet("Работа1")
    ws2['A1'] = "Работа 1 — Норма годового стока"
    ws2['A1'].font = Font(bold=True, size=12)
    ws2.merge_cells('A1:E1')

    # Расчётная река
    ws2['A3'] = "РАСЧЁТНАЯ РЕКА"
    ws2['A3'].font = Font(bold=True, color="1F4E79")
    ws2['A4'] = "Название:"
    ws2['B4'] = "Бирюса, с. Шиткино"
    ws2['B4'].fill = yellow_fill
    ws2['A5'] = "Площадь F, км²:"
    ws2['B5'] = 31800
    ws2['B5'].fill = yellow_fill

    write_header_row(ws2, 7, ["Год", "Q, м³/с"])
    calc_years = list(range(1944, 1976))
    calc_Q = [361,210,364,250,225,241,287,284,403,274,306,395,243,291,
              253,264,276,288,268,266,243,318,376,308,310,226,226,260,307,372,203,290]
    for i, (y, q) in enumerate(zip(calc_years, calc_Q), start=8):
        style_cell(ws2, i, 1, y, fill=yellow_fill)
        style_cell(ws2, i, 2, q, fill=yellow_fill)

    # Река-аналог
    ws2['A45'] = "РЕКА-АНАЛОГ"
    ws2['A45'].font = Font(bold=True, color="1F4E79")
    ws2['A46'] = "Название:"
    ws2['B46'] = "Бирюса, р.п. Суетиха"
    ws2['B46'].fill = yellow_fill
    ws2['A47'] = "Площадь F, км²:"
    ws2['B47'] = 24700
    ws2['B47'].fill = yellow_fill

    write_header_row(ws2, 49, ["Год", "Q, м³/с"])
    analog_years = list(range(1936, 1976))
    analog_Q = [335,280,276,292,252,339,200,159,329,177,320,229,203,221,262,249,368,
                243,283,367,218,256,223,250,260,269,252,244,215,297,341,280,203,250,369,252,278,323,181,264]
    for i, (y, q) in enumerate(zip(analog_years, analog_Q), start=50):
        style_cell(ws2, i, 1, y, fill=yellow_fill)
        style_cell(ws2, i, 2, q, fill=yellow_fill)

    ws2.column_dimensions['A'].width = 22
    ws2.column_dimensions['B'].width = 16

    # ========== ЛИСТ 3: Работа2 ==========
    ws3 = wb.create_sheet("Работа2")
    ws3['A1'] = "Работа 2 — Внутригодовое распределение (помесячные расходы)"
    ws3['A1'].font = Font(bold=True, size=12)
    ws3.merge_cells('A1:M1')
    ws3['A2'] = "Год | I | II | III | IV | V | VI | VII | VIII | IX | X | XI | XII"
    ws3['A2'].font = info_font
    ws3.merge_cells('A2:M2')

    write_header_row(ws3, 4, ["Год", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"])

    for yr in range(1965, 1976):
        style_cell(ws3, yr - 1965 + 5, 1, yr, fill=yellow_fill)
        for m in range(1, 13):
            import random
            random.seed(yr * 100 + m)
            style_cell(ws3, yr - 1965 + 5, m + 1,
                       round(random.uniform(5, 60), 1), fill=yellow_fill)

    # ========== ЛИСТ 4: Работа3 ==========
    ws4 = wb.create_sheet("Работа3")
    ws4['A1'] = "Работа 3 — Минимальный сток (30-суточные минимумы)"
    ws4['A1'].font = Font(bold=True, size=12)
    ws4.merge_cells('A1:D1')

    write_header_row(ws4, 3, ["Год", "Зимний минимум", "Летний минимум", "Примечание"])
    for yr in range(1970, 1991):
        import random
        random.seed(yr * 10)
        style_cell(ws4, yr - 1970 + 4, 1, yr, fill=yellow_fill)
        style_cell(ws4, yr - 1970 + 4, 2, round(random.uniform(1.5, 8.0), 2), fill=yellow_fill)
        style_cell(ws4, yr - 1970 + 4, 3, round(random.uniform(3.0, 15.0), 2), fill=yellow_fill)
        style_cell(ws4, yr - 1970 + 4, 4, "—")

    # ========== ЛИСТ 5: ГТС ==========
    ws5 = wb.create_sheet("ГТС")
    ws5['A1'] = "Параметры ГТС для классификации"
    ws5['A1'].font = Font(bold=True, size=12)

    ws5['A3'] = "Высота плотины, м:"
    ws5['B3'] = 35
    ws5['B3'].fill = yellow_fill

    ws5['A4'] = "Объём водохранилища, млн.м³:"
    ws5['B4'] = 200
    ws5['B4'].fill = yellow_fill

    ws5.column_dimensions['A'].width = 35
    ws5.column_dimensions['B'].width = 15

    # ========== Сохранение ==========
    wb.save(path)
    print(f"✅ Единый шаблон создан: {path}")
    print(f"   Листы: {wb.sheetnames}")
    return path


if __name__ == "__main__":
    create_unified_template()
