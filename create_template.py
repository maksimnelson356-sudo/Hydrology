"""
create_template.py
Генерация единого Excel-шаблона для ГидроСтатистика 2026.

Запуск:  python create_template.py
Результат: шаблон_данных.xlsx
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

np.random.seed(42)

YEARS = list(range(1984, 2024))
N = len(YEARS)


def gen_annual(mean, cv, cs, n=N, miss_pct=0.05):
    std = mean * cv
    from scipy.stats import skewnorm
    raw = skewnorm.rvs(a=cs * 2, loc=mean - std * 0.5, scale=std, size=n)
    raw = np.maximum(raw, mean * 0.05)
    idx_miss = np.random.choice(n, size=int(n * miss_pct), replace=False)
    raw = raw.astype(float)
    raw[idx_miss] = np.nan
    return np.round(raw, 1)


def gen_daily_from_annual(annual_q, year_col):
    rows = []
    for yr, q in zip(year_col, annual_q):
        if pd.isna(q):
            continue
        base = q
        for doy in range(1, 366):
            month = (datetime(yr, 1, 1) + timedelta(days=doy - 1)).month
            if month in [6, 7, 8]:
                factor = 1.3 + 0.4 * np.sin(doy * 0.1)
            elif month in [12, 1, 2]:
                factor = 0.5 + 0.2 * np.sin(doy * 0.05)
            elif month in [3, 4, 5]:
                factor = 0.9 + 0.5 * np.sin((doy - 60) * 0.07)
            else:
                factor = 0.8 + 0.3 * np.sin(doy * 0.06)
            noise = np.random.normal(0, q * 0.08)
            val = max(0.1, base * factor + noise)
            dt = datetime(yr, 1, 1) + timedelta(days=doy - 1)
            rows.append({"date": dt, "value": round(val, 2)})
    return pd.DataFrame(rows)


# === 1. Данные (годовые Qср, 4 поста) ===
angara = gen_annual(650, 0.18, 0.4)
biryusa = gen_annual(155, 0.28, 0.6)
taseeva = gen_annual(52, 0.35, 0.8)
urik = gen_annual(18, 0.42, 1.0)

df_main = pd.DataFrame({
    "Год": YEARS,
    "Ангара": angara,
    "Бирюса": biryusa,
    "Тасеева": taseeva,
    "Урик": urik,
})

# === 2. Норма годового стока ===
calc_q = gen_annual(155, 0.28, 0.6)
analog_q = gen_annual(120, 0.30, 0.5)
df_norma = pd.DataFrame({
    "Год": YEARS,
    "Бирюса, с. Шиткино": calc_q,
    "Бирюса, р.п. Суетиха": analog_q,
})
df_norma_meta = pd.DataFrame({
    "Параметр": [
        "Площадь F расчётной реки (км²)",
        "Площадь F реки-аналога (км²)",
        "Название расчётной реки",
        "Название реки-аналога",
    ],
    "Значение": [31800, 24700, "Бирюса, с. Шиткино", "Бирюса, р.п. Суетиха"],
})

# === 3. Внутригодовое распределение ===
month_sums = {
    "I": (20, 0.35), "II": (18, 0.38), "III": (25, 0.40),
    "IV": (65, 0.50), "V": (180, 0.45), "VI": (350, 0.35),
    "VII": (280, 0.30), "VIII": (150, 0.32), "IX": (80, 0.28),
    "X": (45, 0.30), "XI": (30, 0.35), "XII": (22, 0.38),
}
monthly_rows = []
for yr in YEARS:
    row = {"Год": yr}
    for mname, (mmean, mcv) in month_sums.items():
        row[mname] = round(max(0.1, np.random.normal(mmean, mmean * mcv)), 1)
    monthly_rows.append(row)
df_monthly = pd.DataFrame(monthly_rows)

# === 4. Минимальный сток ===
winter_min = gen_annual(8.5, 0.45, 1.2)
summer_min = gen_annual(25, 0.35, 0.7)
df_min = pd.DataFrame({
    "Год": YEARS,
    "Зимний (янв–мар)": winter_min,
    "Летний (июн–авг)": summer_min,
})

# === 5. Максимальный сток ===
qmax = gen_annual(380, 0.55, 1.5)
df_max = pd.DataFrame({
    "Год": YEARS,
    "Qmax суточный": qmax,
})

# === 6. Кривая Q(H) ===
H_values = np.round(np.linspace(0.5, 8.0, 25), 2)
a, b_coeff, H0 = 45.0, 1.8, 0.3
Q_values = np.round(a * np.maximum(0.01, H_values - H0) ** b_coeff + np.random.normal(0, 2, 25), 2)
df_hq = pd.DataFrame({
    "H (м)": H_values,
    "Q (м³/с)": Q_values,
})

# === 7. Ледовые явления ===
freeze_days = []
breakup_days = []
for yr in YEARS:
    f_day = datetime(yr, 11, 1) + timedelta(days=int(np.random.normal(25, 10)))
    b_day = datetime(yr + 1, 3, 15) + timedelta(days=int(np.random.normal(15, 12)))
    freeze_days.append(f_day)
    breakup_days.append(b_day)
df_ice = pd.DataFrame({
    "Год": YEARS,
    "ледостав": freeze_days,
    "распад": breakup_days,
})

# === 8. Водный баланс (суточные) ===
daily_biryusa = gen_daily_from_annual(biryusa, YEARS)
df_water = daily_biryusa.copy()
df_water.columns = ["date", "value"]

# === 9. FDC (суточные) ===
df_fdc = df_water.copy()

# === 10. Экология и базовый сток (суточные) ===
df_eco = df_water.copy()

# === Запись в Excel ===
output = "шаблон_данных.xlsx"
with pd.ExcelWriter(output, engine="openpyxl") as writer:
    df_main.to_excel(writer, sheet_name="Данные", index=False)

    df_norma_meta.to_excel(writer, sheet_name="Норма годового стока", index=False, startrow=0)
    df_norma.to_excel(writer, sheet_name="Норма годового стока", index=False, startrow=6)

    df_monthly.to_excel(writer, sheet_name="Внутригодовое распределение", index=False)

    df_min.to_excel(writer, sheet_name="Минимальный сток", index=False)

    df_max.to_excel(writer, sheet_name="Максимальный сток", index=False)

    df_hq.to_excel(writer, sheet_name="Кривая Q(H)", index=False)

    df_ice.to_excel(writer, sheet_name="Ледовые явления", index=False)

    df_water.to_excel(writer, sheet_name="Водный баланс", index=False)

    df_fdc.to_excel(writer, sheet_name="FDC", index=False)

    df_eco.to_excel(writer, sheet_name="Экология и базовый сток", index=False)

print("OK: Шаблон создан:", output)
print("   Листы: Данные, Норма годового стока, Внутригодовое распределение,")
print("          Минимальный сток, Максимальный сток, Кривая Q(H),")
print("          Ледовые явления, Водный баланс, FDC, Экология и базовый сток")
print("   Годы:", YEARS[0], "-", YEARS[-1], "(", N, "лет )")
print("   Посты: Ангара, Бирюса, Тасеева, Урик")
