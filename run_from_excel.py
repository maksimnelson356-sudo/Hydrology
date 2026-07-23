"""
run_from_excel.py
Загрузка из Excel + расчёт Q по отсекам
"""

import pandas as pd
from core.profile import MorphoProfile
from core.hydraulics import calculate_composite_q

print("=" * 75)
print("ЗАГРУЗКА ПРОФИЛЯ ИЗ EXCEL + РАСЧЁТ РАСХОДА ПО ОТСЕКАМ")
print("=" * 75)

excel_file = "profile.xlsx"

prof = MorphoProfile.from_excel(excel_file, profile_name="Профиль из Excel")

print(f"\nЗагружен профиль: {prof.name}")
print(f"Точек: {len(prof.points)}")
print(f"Границы поймы: левая = {prof.left_poyma_bound_b}, правая = {prof.right_poyma_bound_b}")

print("\n" + "-" * 75)
print("Расчёт кривой Q(H) по отсекам")
print("-" * 75)

h_values = [31.5, 32.5, 33.5]
results = []

for h in h_values:
    res = calculate_composite_q(prof, h=h)
    results.append(res)
    
    print(f"\nH = {h} м")
    print(f"  Q_total       = {res['Q_total']} м³/с")
    print(f"  Q_ruslo       = {res['Q_ruslo']} м³/с")
    print(f"  Q_left_poyma  = {res['Q_left_poyma']} м³/с")
    print(f"  Q_right_poyma = {res['Q_right_poyma']} м³/с")

df = pd.DataFrame(results)
output_file = "result_by_compartments.txt"
df.to_csv(output_file, sep='\t', index=False, float_format='%.3f')

print("\n" + "=" * 75)
print(f"Результат сохранён в: {output_file}")
print("=" * 75)