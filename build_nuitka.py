"""
build_nuitka.py
Сборка через Nuitka (исправленная версия под SciPy)
"""

import subprocess
import sys
import os

script = "gui/main_window.py"
name = "ГидроСтатистика_2026"

cmd = [
    sys.executable, "-m", "nuitka",
    script,
    f"--output-filename={name}.exe",
    "--standalone",
    "--windows-console-mode=disable",          # пока оставляем консоль для отладки
    "--enable-plugin=pyqt6",
    "--include-package=core",
    "--include-package-data=core",
    "--include-package=scipy",
    "--include-package=scipy.stats",
    "--include-package=scipy._lib",
    "--include-package=scipy._external",
    "--include-package=scipy.sparse",
    "--include-package=numpy",
    "--include-package=pandas",
    "--include-package=matplotlib",
    "--include-package-data=matplotlib",
    "--include-package=openpyxl",
    "--assume-yes-for-downloads",
    "--remove-output",
]

if os.path.exists("icon.ico"):
    cmd.append("--windows-icon-from-ico=icon.ico")
    cmd.append("--include-data-files=icon.ico;.")
    print("✅ Иконка добавлена")
else:
    print("⚠️ icon.ico не найден")

# Дополнительно явно включаем проблемный модуль
cmd.append("--include-module=scipy._external.array_api_compat")
cmd.append("--include-module=scipy._external.array_api_compat.numpy")
cmd.append("--include-module=scipy._external.array_api_compat.numpy.fft")

print("Запускаю сборку Nuitka (это снова займёт время)...")
print()

result = subprocess.run(cmd)

if result.returncode == 0:
    print("\n✅ Сборка завершена!")
    print(f"Папка: {name}.dist\\")
    print(f"Запускай: {name}.dist\\{name}.exe")
else:
    print("\n❌ Ошибка при сборке")