"""
run_profile_calc.py
Простой расчёт кривой Q(H) по морфопрофилю
"""

from core.profile import MorphoProfile, ProfilePoint, PointCode
from core.hydraulics import calculate_composite_q
import pandas as pd

print("=" * 60)
print("РАСЧЁТ КРИВОЙ Q(H) ПО МОРФОПОФИЛЮ")
print("=" * 60)

# ==================== СОЗДАЁМ ТЕСТОВЫЙ ПРОФИЛЬ ====================
points = [
    ProfilePoint(b=0,   h=30.66, code=PointCode.THALWEG,   n=0.025),
    ProfilePoint(b=10,  h=31.0,  n=0.025),
    ProfilePoint(b=50,  h=31.5,  code=PointCode.POYMA_BOUNDARY, n=0.035),
    ProfilePoint(b=100, h=32.0,  n=0.035),
    ProfilePoint(b=150, h=33.0,  code=PointCode.POYMA_BOUNDARY, n=0.040),
    ProfilePoint(b=200, h=35.0,  n=0.040),
]

prof = MorphoProfile(
    name="Тестовый профиль реки",
    points=points,
    slope_i=0.0005          # уклон 0.5 ‰
)

print(f"\nПрофиль: {prof.name}")
print(f"Уклон i = {prof.slope_i}")
print(f"Границы поймы: левая = {prof.left_poyma_bound_b}, правая = {prof.right_poyma_bound_b}")

# ==================== РАСЧЁТ КРИВОЙ Q(H) ====================
print("\n" + "-" * 60)
print("Расчёт кривой Q(H)")
print("-" * 60)

results = []
h_values = [31.0, 31.5, 32.0, 32.5, 33.0, 33.5, 34.0]

for h in h_values:
    res = calculate_composite_q(prof, h=h)
    results.append(res)
    print(f"H = {h:5.2f} м  |  Q = {res['Q_total']:8.3f} м³/с  |  ω = {res['omega_total']:7.2f} м²")

# ==================== СОХРАНЕНИЕ РЕЗУЛЬТАТА ====================
df = pd.DataFrame(results)
df = df[['H', 'Q_total', 'omega_total', 'n_weighted']]
df.columns = ['H, м', 'Q, м³/с', 'ω, м²', 'n']

output_file = "result_Q_H.txt"
df.to_csv(output_file, sep='\t', index=False, float_format='%.3f')

print("\n" + "=" * 60)
print(f"Результат сохранён в файл: {output_file}")
print("=" * 60)
print(df.to_string(index=False))