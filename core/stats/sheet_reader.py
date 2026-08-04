"""
core/stats/sheet_reader.py
Утилиты чтения листов единого Excel-шаблона.

Листы шаблона имеют титульные строки (0-2): название работы и подсказку,
а заголовок данных («Год | ...») находится ниже. Эти утилиты находят
строку-заголовок и читают данные корректно, игнорируя титул.
"""

import re

import pandas as pd
from typing import Optional, Sequence

# Составные единицы измерения — убираем ЦЕЛИКОМ, до разбиения по разделителям,
# иначе «Осадки, мм/год» распадётся на «мм» + «год», и «год» останется в имени,
# из-за чего колонка осадков ошибочно попадёт в годовые.
_COMPOUND_UNITS = re.compile(
    r"\b(мм\s*/\s*год|м3\s*/\s*с|м\s*/\s*с|л\s*/\s*с|км2\s*/\s*с|m3/s|m/s)\b"
)
# Одиночные единицы — длинные раньше коротких, чтобы «м3» не съедалось «м».
_SINGLE_UNITS = re.compile(r"\b(м3|мм|см|км2|км|л|м|с|m3|mm|m)\b")
_SEPARATORS = re.compile(r"[(),;:|/]+")


def clean_column_name(name) -> str:
    """Нормализовать имя колонки: lower и снять единицы измерения.

    «H, м» -> "h", «Q, м³/с» -> "q", «Расход Q, м³/с» -> "расход q",
    «Базовый сток, м³/с» -> "базовый сток", «Год» -> "год".
    Слово «год» НЕ удаляется (это колонка-год).
    """
    s = str(name).strip().lower()
    s = s.replace("³", "3").replace("²", "2")
    s = _COMPOUND_UNITS.sub(" ", s)
    s = _SEPARATORS.sub(" ", s)
    s = _SINGLE_UNITS.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def find_sheet(xls: pd.ExcelFile, keywords: Sequence[str]) -> Optional[str]:
    """Найти имя листа с самым длинным совпавшим ключевым словом.

    Пробелы игнорируются, чтобы «Работа8» матчил и лист «Работа8 (FDC)».
    При равной длине ключа побеждает лист, встречающийся раньше.
    """
    lower_keywords = [str(k).strip().lower().replace(" ", "")
                      for k in keywords if str(k).strip()]
    best = None  # (score, order, name)
    for order, sn in enumerate(xls.sheet_names):
        sn_lower = sn.strip().lower().replace(" ", "")
        for kw in lower_keywords:
            if kw in sn_lower:
                score = len(kw)
                if best is None or score > best[0] or (score == best[0] and order < best[1]):
                    best = (score, order, sn)
    return best[2] if best else None


def find_header_row(raw: pd.DataFrame, header_keywords: Sequence[str],
                    max_scan: int = 15) -> int:
    """Найти индекс строки-заголовка, содержащей одно из ключевых слов.

    Ячейки чистятся через clean_column_name, поэтому «H, м» матчится по «h».
    Длинные титулы/подсказки (содержащие «год», «расход» внутри слов) отсекаются
    ограничением на длину: len(nc) <= len(kw) + 3.
    """
    lower_keys = [str(k).strip().lower() for k in header_keywords if str(k).strip()]
    for idx in range(min(max_scan, len(raw))):
        cells = [str(v).strip().lower() for v in raw.iloc[idx].tolist() if pd.notna(v)]
        for c in cells:
            nc = clean_column_name(c)
            if not nc:
                continue
            for kw in lower_keys:
                if kw == nc or (kw in nc and len(nc) <= len(kw) + 3):
                    return idx
    return -1


def read_work_sheet(filepath_or_xls,
                    sheet_keywords: Sequence[str],
                    header_keywords: Sequence[str] = ("год", "year", "years"),
                    use_columns: bool = False) -> pd.DataFrame:
    """Прочитать рабочий лист шаблона, пропустив титульные строки.

    Args:
        filepath_or_xls: путь к файлу Excel или открытый pd.ExcelFile.
        sheet_keywords: ключевые слова для поиска листа (например ["Работа8", "FDC"]).
        header_keywords: слова для поиска строки-заголовка.
        use_columns: если True — возвращать DataFrame с колонками из заголовка,
            иначе читать с skiprows=header_row.

    Returns:
        pd.DataFrame с данными; пустой DataFrame, если лист не найден.
    """
    xls = filepath_or_xls if isinstance(filepath_or_xls, pd.ExcelFile) else pd.ExcelFile(filepath_or_xls)
    sheet = find_sheet(xls, sheet_keywords)
    if sheet is None:
        return pd.DataFrame()

    raw = pd.read_excel(xls, sheet, header=None)
    header_idx = find_header_row(raw, header_keywords)
    if header_idx < 0:
        return raw

    if use_columns:
        df = raw.iloc[header_idx + 1:].copy()
        df.columns = [str(c) for c in raw.iloc[header_idx].values]
        return df.reset_index(drop=True)

    return pd.read_excel(xls, sheet, skiprows=header_idx)


def numeric_column(df: pd.DataFrame,
                   prefer_names: Sequence[str] = ("value", "q", "расход")) -> Optional[pd.Series]:
    """Вернуть числовой столбец, иначе None.

    Проход 1: колонки, чьё clean-имя содержит одно из предпочитаемых слов
    (подстрока, не точное равенство). Выбор по специфичности: самое длинное
    совпавшее слово, затем индекс колонки. Так «Базовый сток, м³/с» матчится по
    «базовый»/«сток», а не теряется из-за суффикса с единицами.
    Проход 2: любой числовой столбец, кроме year-like (имя содержит «год»/«year»).
    Проход 3: любой числовой столбец.
    """
    if df is None or df.empty:
        return None

    prefers = [str(n).strip().lower() for n in prefer_names if str(n).strip()]

    # Проход 1: предпочтительные имена (подстрока + специфичность).
    best = None  # (score, idx, series)
    for i, col in enumerate(df.columns):
        nc = clean_column_name(col)
        for p in prefers:
            if p in nc:
                score = len(p)
                if best is None or score > best[0] or (score == best[0] and i < best[1]):
                    vals = pd.to_numeric(df[col], errors="coerce")
                    if vals.notna().sum() >= 3:
                        best = (score, i, vals.dropna())
    if best is not None:
        return best[2]

    # Проход 2: любой числовой, кроме колонки-года.
    for col in df.columns:
        nc = clean_column_name(col)
        if "год" in nc or "year" in nc:
            continue
        vals = pd.to_numeric(df[col], errors="coerce")
        if vals.notna().sum() >= 3:
            return vals.dropna()

    # Проход 3: любой числовой.
    for col in df.columns:
        vals = pd.to_numeric(df[col], errors="coerce")
        if vals.notna().sum() >= 3:
            return vals.dropna()
    return None


def first_data_frame(xls: pd.ExcelFile, sheet_keywords: Sequence[str]) -> pd.DataFrame:
    """Читать лист целиком (первая строка — заголовок). Удобно для «плоских» листов."""
    sheet = find_sheet(xls, sheet_keywords)
    if sheet is None:
        return pd.DataFrame()
    return pd.read_excel(xls, sheet)
