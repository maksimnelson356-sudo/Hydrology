"""
test_q.py
Тест расчёта расхода Q по формуле Маннинга с разделением на отсеки
"""
from core.profile import MorphoProfile, ProfilePoint, PointCode
from core.hydraulics import calculate_composite_q

print("=== Тест расчёта расхода Q (формула Маннинга) ===\n")

# Создаём тестовый профиль (как в руководстве)
points = [
    ProfilePoint(b=0, h=30.66, code=PointCode.THALWEG, n=0.025),
    ProfilePoint(b=10, h=31.0, n=0.025),
    ProfilePoint(b=50, h=31.5, code=PointCode.POYMA_BOUNDARY, n=0.035),
    ProfilePoint(b=100, h=32.0, n=0.035),
    ProfilePoint(b=150, h=33.0, code=PointCode.POYMA_BOUNDARY, n=0.040),
    ProfilePoint(b=200, h=35.0, n=0.040),
]

prof = MorphoProfile(
    name="Тестовый профиль",
    points=points,
    slope_i=0.0005          # уклон 0.5 промилле
)

# Расчёт при разных уровнях
for h_level in [31.5, 32.5, 33.5]:
    result = calculate_composite_q(prof, h=h_level)
    print(f"H = {result['H']} м")
    print(f"  ω_общ       = {result['omega_total']:.2f} м²")
    print(f"  ω_русло     = {result['omega_ruslo']:.2f} м²")
    print(f"  ω_лев.пойма = {result['omega_left']:.2f} м²")
    print(f"  ω_прав.пойма= {result['omega_right']:.2f} м²")
    print(f"  Q_итого     = {result['Q_total']:.3f} м³/с")
    print(f"  n_средн.    = {result['n_weighted']:.4f}")
    print("-" * 40)
