#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tools/verify_sheet_reader.py
Без-GUI проверка извлечения данных из unified_template.xlsx.

Запуск (Windows, консоль cp1251):
    set PYTHONIOENCODING=utf-8
    python tools/verify_sheet_reader.py

Exit code 0 — все проверки OK, ненулевой — есть FAIL.
"""

import sys
import os
from pathlib import Path

# Принудительно перенаправляем stdout в UTF-8 для Windows-консоли.
if sys.platform == "win32" and sys.stdout is not None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Добавляем корень репозитория в путь для импорта core.
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

import pandas as pd
from core.stats.sheet_reader import (
    find_sheet, find_header_row, read_work_sheet,
    numeric_column, clean_column_name
)
from core.gts_reference import GTSClass, classify_gts_by_parameters


def main():
    # Путь к шаблону — аргумент или относительный.
    if len(sys.argv) > 1:
        template_path = Path(sys.argv[1])
    else:
        template_path = _root / "unified_template.xlsx"

    if not template_path.exists():
        print(f"FAIL: файл шаблона не найден: {template_path}")
        return 2

    xls = pd.ExcelFile(template_path)
    ok = True

    # ========== 1. find_sheet longest-match ==========
    print("\n=== find_sheet longest-match ===")

    tests_find = [
        (["FDC + Регрессии + Статистика", "FDC", "Кривая"], "FDC + Регрессии + Статистика", "work8"),
        (["Кривая Q(H)", "Кривая", "H-Q"], "Кривая Q(H)", "work4-кривая"),
        (["Экология + Базовый сток", "Экология", "Базовый"], "Экология + Базовый сток", "work10"),
        (["Внутригодовое распределение"], "Внутригодовое распределение", "work2"),
    ]
    for keywords, expected, label in tests_find:
        got = find_sheet(xls, keywords)
        status = "OK" if got == expected else "FAIL"
        if got != expected:
            ok = False
        print(f"{status}: {label}: find_sheet({keywords}) -> '{got}' (ожидалось '{expected}')")

    # ========== 2. find_header_row ==========
    print("\n=== find_header_row (clean-match) ===")

    tests_header = [
        (["Кривая Q(H)", "Кривая"], ("h", "уровень", "q", "расход"), 2, "Кривая Q(H)"),
        (["FDC + Регрессии + Статистика"], ("год", "year", "years"), 2, "FDC"),
        (["Экология + Базовый сток"], ("год", "year", "years"), 2, "Экология"),
        (["Внутригодовое распределение"], ("год", "year", "years"), 3, "Внутригодовое распределение"),
        (["Максимальный сток"], ("год", "year", "years"), 2, "Максимальный сток"),
    ]
    for sheet_keys, header_keys, expected_idx, label in tests_header:
        sheet = find_sheet(xls, sheet_keys)
        if sheet is None:
            print(f"FAIL: {label}: лист не найден по ключам {sheet_keys}")
            ok = False
            continue
        raw = pd.read_excel(xls, sheet, header=None)
        got = find_header_row(raw, header_keys)
        status = "OK" if got == expected_idx else "FAIL"
        if got != expected_idx:
            ok = False
        print(f"{status}: {label}: find_header_row -> {got} (ожидалось {expected_idx})")

    # ========== 3. clean_column_name mapping ==========
    print("\n=== clean_column_name mapping ===")

    tests_clean = [
        ("H, м", "h"),
        ("Q, м³/с", "q"),
        ("Расход Q, м³/с", "расход q"),
        ("Базовый сток, м³/с", "базовый сток"),
        ("Год", "год"),
        ("Осадки, мм/год", "осадки"),
        ("Q_max, м³/с", "q_max"),
        ("Qэкологический, м³/с", "qэкологический"),
    ]
    for raw, expected in tests_clean:
        got = clean_column_name(raw)
        status = "OK" if got == expected else "FAIL"
        if got != expected:
            ok = False
        print(f"{status}: clean_column_name('{raw}') -> '{got}' (ожидалось '{expected}')")

    # ========== 4. work2: read_work_sheet + month_map ==========
    print("\n=== work2: внутригодовое распределение ===")

    df2 = read_work_sheet(str(template_path), ["Внутригодовое распределение"], use_columns=True)
    if df2.empty:
        print("FAIL: work2: read_work_sheet вернул пустой DataFrame")
        ok = False
    else:
        # Проверка колонок.
        expected_cols = ["Год", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
        cols_ok = list(df2.columns) == expected_cols
        if not cols_ok:
            print(f"FAIL: work2: колонки {list(df2.columns)} != {expected_cols}")
            ok = False
        else:
            print(f"OK: work2: колонки {expected_cols[:4]}... (n={len(df2)})")

        # Нормализация month_map (из виджета).
        month_map = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6,
                     "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12}
        renamed = {}
        for c in df2.columns:
            cs = str(c).strip().upper()
            if cs in month_map:
                renamed[c] = month_map[cs]
            elif cs in ["ГОД", "YEAR", "YEARS"]:
                renamed[c] = "год"
        df2r = df2.rename(columns=renamed)
        if "год" not in df2r.columns:
            print("FAIL: work2: нет колонки 'год' после нормализации")
            ok = False
        else:
            df2r["год"] = pd.to_numeric(df2r["год"], errors="coerce")
            years = df2r["год"].dropna()
            if years.min() == 1965 and years.max() == 1975:
                print(f"OK: work2: годы 1965..1975 (n={len(years)})")
            else:
                print(f"FAIL: work2: диапазон лет {years.min()}..{years.max()} != 1965..1975")
                ok = False

    # ========== 5. work4: кривая Q=f(H) ==========
    print("\n=== work4: кривая расходов Q=f(H) ===")

    df4 = read_work_sheet(str(template_path), ["Кривая Q(H)", "Кривая", "H-Q"],
                          header_keywords=("h", "уровень", "q", "расход"))
    if df4.empty:
        print("FAIL: work4: read_work_sheet вернул пустой DataFrame")
        ok = False
    else:
        cols = list(df4.columns)
        # Ожидаем заголовки «H, м» / «Q, м³/с»; после clean_column_name -> h, q.
        cols_clean = [clean_column_name(c) for c in cols]
        if cols_clean == ["h", "q"]:
            print(f"OK: work4: колонки {cols} -> clean {cols_clean} (n={len(df4)})")
        else:
            print(f"FAIL: work4: колонки {cols} -> clean {cols_clean}, ожидалось ['h', 'q']")
            ok = False

        # Проверка данных.
        h_vals = pd.to_numeric(df4.iloc[:, 0], errors="coerce").dropna()
        q_vals = pd.to_numeric(df4.iloc[:, 1], errors="coerce").dropna()
        if len(h_vals) == 20 and h_vals.iloc[0] == 0.5 and (q_vals > 0).all():
            print(f"OK: work4: H от {h_vals.iloc[0]}, n={len(h_vals)}, Q>0")
        else:
            print(f"FAIL: work4: H={h_vals.iloc[0] if len(h_vals)>0 else 'нет'}, n={len(h_vals)}, Q>0? {(q_vals>0).all() if len(q_vals)>0 else False}")
            ok = False

    # ========== 6. work8: FDC ==========
    print("\n=== work8: кривая обеспеченности продолжительности (FDC) ===")

    df8 = read_work_sheet(str(template_path), ["FDC + Регрессии + Статистика", "FDC", "Кривая"])
    if df8.empty:
        print("FAIL: work8: read_work_sheet вернул пустой DataFrame")
        ok = False
    else:
        print(f"OK: work8: колонки {list(df8.columns)}, n={len(df8)}")
        col = numeric_column(df8, prefer_names=["q", "расход", "value"])
        if col is None:
            print("FAIL: work8: numeric_column вернул None")
            ok = False
        else:
            vals = col.values
            in_range = (vals >= 50).all() and (vals <= 300).all()
            not_years = vals.max() < 1980 or vals.min() > 2009 or not ((vals >= 1980) & (vals <= 2009)).all()
            if in_range and not_years:
                print(f"OK: work8: numeric_column значения в [50,300], не годы: head={list(vals[:3])}")
            else:
                print(f"FAIL: work8: numeric_column значения {vals[:5]}, возможно годы?")
                ok = False

    # ========== 7. work10: базовый сток ==========
    print("\n=== work10: экология и базовый сток ===")

    df10 = read_work_sheet(str(template_path), ["Экология + Базовый сток", "Экология", "Базовый"])
    if df10.empty:
        print("FAIL: work10: read_work_sheet вернул пустой DataFrame")
        ok = False
    else:
        print(f"OK: work10: колонки {list(df10.columns)}, n={len(df10)}")
        col = numeric_column(df10, prefer_names=["базовый", "сток", "value", "q"])
        if col is None:
            print("FAIL: work10: numeric_column вернул None")
            ok = False
        else:
            vals = col.values
            expected_head = [79.1, 84.8, 46.0]
            match = list(vals[:3]) == expected_head
            if match:
                print(f"OK: work10: numeric_column -> базовый сток head={expected_head}")
            else:
                print(f"FAIL: work10: numeric_column head={list(vals[:3])} != {expected_head} (возможно годы?)")
                ok = False

    # ========== 8. Регрессия фикса E: pd.read_excel + numeric_column ==========
    print("\n=== Регрессия: pd.read_excel без read_work_sheet (ожидаемо годы) ===")

    sheet_r8 = find_sheet(xls, ["FDC + Регрессии + Статистика", "FDC"])
    if sheet_r8:
        df_raw = pd.read_excel(xls, sheet_r8)
        col_raw = numeric_column(df_raw, prefer_names=["q", "расход", "value"])
        if col_raw is not None:
            vals_raw = col_raw.values
            # Без read_work_sheet колонка-год содержит титул «Кривая обеспеченности продолжительности (FDC)»,
            # но numeric_column по специфичности выберет второй столбец «Расход Q, м³/с» -> расход(6).
            # Однако в текущей реализации без clean-имён колонки — ожидаемо годы.
            # Просто выводим для справки.
            print(f"INFO: pd.read_excel('{sheet_r8}') + numeric_column -> head={list(vals_raw[:3])} (без read_work_sheet)")
        else:
            print("INFO: pd.read_excel + numeric_column -> None")

    # ========== 9. ГТС: параметры + классификация ==========
    print("\n=== ГТС: параметры и классификация ===")

    sheet_gts = find_sheet(xls, ["ГТС"])
    if sheet_gts is None:
        print("FAIL: ГТС: лист не найден")
        ok = False
    else:
        gts_raw = pd.read_excel(xls, sheet_gts, header=None)
        dam_height = None
        reservoir_vol = None
        for _, row in gts_raw.iterrows():
            key = str(row[0]).strip().lower() if pd.notna(row[0]) else ""
            val = row[1]
            if "высота" in key and "плотин" in key:
                try:
                    dam_height = float(val)
                except (ValueError, TypeError):
                    pass
            elif "объём" in key or "объем" in key:
                try:
                    reservoir_vol = float(val)
                except (ValueError, TypeError):
                    pass
        if dam_height == 35.0 and reservoir_vol == 200.0:
            print(f"OK: ГТС: высота={dam_height}, объём={reservoir_vol}")
        else:
            print(f"FAIL: ГТС: высота={dam_height}, объём={reservoir_vol}, ожидалось 35/200")
            ok = False

        gts_class = classify_gts_by_parameters(dam_height, reservoir_vol)
        if gts_class == GTSClass.CLASS_III:
            print(f"OK: ГТС: classify({dam_height}, {reservoir_vol}) -> {gts_class}")
        else:
            print(f"FAIL: ГТС: classify -> {gts_class}, ожидалось CLASS_III")
            ok = False

    # ========== 10. Рацион + IDF + Гидрографы: F / зона / T / t / α ==========
    print("\n=== Рацион + IDF + Гидрографы: F / зона / T / t / α ===")

    sheet_r7 = find_sheet(xls, ["Рацион + IDF + Гидрографы", "Ливневый сток"])
    if sheet_r7 is None:
        print("FAIL: Рацион + IDF + Гидрографы: лист не найден")
        ok = False
    else:
        r7_raw = pd.read_excel(xls, sheet_r7, header=None)
        f7 = zone7 = t7 = time7 = alpha7 = None
        for _, row in r7_raw.iterrows():
            key = str(row[0]).strip().lower() if pd.notna(row[0]) else ""
            val = row[1]
            if "площадь" in key and "f" in key:
                try:
                    f7 = float(val)
                except (ValueError, TypeError):
                    pass
            elif "зона" in key:
                zone7 = str(val).strip() if pd.notna(val) else None
            elif "обеспеченност" in key and "t" in key:
                try:
                    t7 = float(val)
                except (ValueError, TypeError):
                    pass
            elif "время" in key and "концентрац" in key:
                try:
                    time7 = float(val)
                except (ValueError, TypeError):
                    pass
            elif ("стока" in key or "коэфф" in key) and ("α" in key or "alpha" in key or "a" in key):
                try:
                    alpha7 = float(val)
                except (ValueError, TypeError):
                    pass
        expected7 = (25.0, "zone_3", 10.0, 60.0, 0.70)
        got7 = (f7, zone7, t7, time7, alpha7)
        if got7 == expected7:
            print(f"OK: Рацион + IDF + Гидрографы: F={f7}, зона={zone7}, T={t7}, t={time7}, α={alpha7}")
        else:
            print(f"FAIL: Рацион + IDF + Гидрографы: {got7} != {expected7}")
            ok = False

    # ========== 11. ППУ + ГВП + Регулирование: все параметры + slope ==========
    print("\n=== ППУ + ГВП + Регулирование: все параметры (slope не теряется) ===")

    sheet_r9 = find_sheet(xls, ["ППУ + ГВП + Регулирование", "Гидротехнические расчёты"])
    if sheet_r9 is None:
        print("FAIL: ППУ + ГВП + Регулирование: лист не найден")
        ok = False
    else:
        r9_raw = pd.read_excel(xls, sheet_r9, header=None)
        q9 = b9 = slope9 = l9 = h9 = type9 = m9 = n9 = hres9 = lback9 = qmean9 = demand9 = None
        for _, row in r9_raw.iterrows():
            key = str(row[0]).strip().lower() if pd.notna(row[0]) else ""
            val = row[1]
            try:
                if "средний" in key and "q" in key:
                    qmean9 = float(val)
                elif "расход" in key and "q" in key:
                    q9 = float(val)
                elif "ширин" in key and "b" in key:
                    b9 = float(val)
                elif "уклон" in key:
                    slope9 = float(val)
                elif "длина" in key and "гребн" in key:
                    l9 = float(val)
                elif "напор" in key:
                    h9 = float(val)
                elif "тип" in key:
                    type9 = str(val).strip() if pd.notna(val) else None
                elif "откос" in key:
                    m9 = float(val)
                elif "маннинг" in key or "коэфф. манн" in key:
                    n9 = float(val)
                elif "уровень" in key and ("водохр" in key or "hres" in key):
                    hres9 = float(val)
                elif "длина" in key and "участка" in key:
                    lback9 = float(val)
                elif "забор" in key:
                    demand9 = float(val)
            except (ValueError, TypeError):
                pass
        expected9 = (500.0, 45.0, 0.002, 20.0, 3.0, "трапеция", 2.0, 0.035, 5.0, 5000.0, 100.0, 30.0)
        got9 = (q9, b9, slope9, l9, h9, type9, m9, n9, hres9, lback9, qmean9, demand9)
        if got9 == expected9:
            print(f"OK: ППУ + ГВП + Регулирование: Q={q9}, B={b9}, slope={slope9}, L={l9}, H={h9}, тип={type9}, "
                  f"m={m9}, n={n9}, Hres={hres9}, Lback={lback9}, Qmean={qmean9}, demand={demand9}")
        else:
            print(f"FAIL: ППУ + ГВП + Регулирование: {got9} != {expected9}")
            ok = False

    # ========== 12. Интеграция ГТС: шаблон → парсер → класс ==========
    print("\n=== Интеграция ГТС: шаблон → парсер → класс ===")

    gts_cls = None
    gts_params = None
    sheet_gts2 = find_sheet(xls, ["ГТС"])
    if sheet_gts2 is not None:
        gts_raw2 = pd.read_excel(xls, sheet_gts2, header=None)
        dam2 = vol2 = None
        for _, row in gts_raw2.iterrows():
            key = str(row[0]).strip().lower() if pd.notna(row[0]) else ""
            val = row[1]
            if "высота" in key and "плотин" in key:
                try:
                    dam2 = float(val)
                except (ValueError, TypeError):
                    pass
            elif "объём" in key or "объем" in key:
                try:
                    vol2 = float(val)
                except (ValueError, TypeError):
                    pass
        if dam2 is not None or vol2 is not None:
            gts_params = {'dam_height': dam2, 'reservoir_volume': vol2}
            gts_cls = classify_gts_by_parameters(dam2, vol2)
    if gts_cls == GTSClass.CLASS_III and gts_params and gts_params['dam_height'] == 35.0:
        print(f"OK: Интеграция: класс={gts_cls}, параметры={gts_params}")
    else:
        print(f"FAIL: Интеграция: класс={gts_cls}, параметры={gts_params}")
        ok = False

    # ========== Итог ==========
    print("\n" + "=" * 40)
    if ok:
        print("ВСЕ ПРОВЕРКИ OK")
        return 0
    else:
        print("ЕСТЬ FAIL — см. выше")
        return 1


if __name__ == "__main__":
    sys.exit(main())
