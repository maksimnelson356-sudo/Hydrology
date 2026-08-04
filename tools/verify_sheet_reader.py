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
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Добавляем корень репозитория в путь для импорта core.
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

import pandas as pd
from core.stats.sheet_reader import (
    find_sheet, find_header_row, read_work_sheet,
    numeric_column, clean_column_name
)


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
        (["Работа8", "FDC", "Кривая"], "Работа8", "work8"),
        (["Кривая", "КриваяQH", "H-Q"], "КриваяQH", "work4-кривая"),
        (["Работа10", "Экология", "Базовый"], "Работа10", "work10"),
        (["Внутригодовое распределение", "Работа2"], "Работа2", "work2"),
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
        (["Кривая", "КриваяQH"], ("h", "уровень", "q", "расход"), 2, "КриваяQH"),
        (["Работа8"], ("год", "year", "years"), 2, "Работа8"),
        (["Работа10"], ("год", "year", "years"), 2, "Работа10"),
        (["Работа2"], ("год", "year", "years"), 3, "Работа2"),
        (["Работа4"], ("год", "year", "years"), 2, "Работа4"),
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

    df2 = read_work_sheet(str(template_path), ["Внутригодовое распределение", "Работа2"], use_columns=True)
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

    df4 = read_work_sheet(str(template_path), ["Кривая", "КриваяQH", "H-Q"],
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

    df8 = read_work_sheet(str(template_path), ["Работа8", "FDC", "Кривая"])
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

    df10 = read_work_sheet(str(template_path), ["Работа10", "Экология", "Базовый"])
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

    sheet_r8 = find_sheet(xls, ["FDC", "Работа8"])
    if sheet_r8:
        df_raw = pd.read_excel(xls, sheet_r8)
        col_raw = numeric_column(df_raw, prefer_names=["q", "расход", "value"])
        if col_raw is not None:
            vals_raw = col_raw.values
            # Без read_work_sheet колонка-год содержит титул «Работа8 — …», clean -> «работа 8 …»,
            # но numeric_column по специфичности выберет второй столбец «Расход Q, м³/с» -> расход(6).
            # Однако в текущей реализации без clean-имён колонки — ожидаемо годы.
            # Просто выводим для справки.
            print(f"INFO: pd.read_excel('{sheet_r8}') + numeric_column -> head={list(vals_raw[:3])} (без read_work_sheet)")
        else:
            print("INFO: pd.read_excel + numeric_column -> None")

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
