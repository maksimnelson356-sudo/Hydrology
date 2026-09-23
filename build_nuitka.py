"""
build_nuitka.py
Сборка через Nuitka (исправленная версия под SciPy)
"""

import os
import subprocess
import sys

script = "gui/main_window.py"
name = "HydroSphere"

cmd = [
    sys.executable, "-m", "nuitka",
    script,
    f"--output-filename={name}.exe",
    "--standalone",
    "--windows-console-mode=disable",          # пока оставляем консоль для отладки
    "--enable-plugin=pyqt6",
    "--include-package=core",
    "--include-package-data=core",
    "--include-package=core.domain",
    "--include-package=core.services",
    "--include-package=core.services.handlers",
    "--include-package=gui.tabs",
    "--include-package=i18n",
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

if os.path.exists("gui/resources/logo.png"):
    cmd.append("--windows-icon-from-ico=gui/resources/logo.png")
    cmd.append("--include-data-files=gui/resources/logo.png;.")
    print("✅ Иконка добавлена")
elif os.path.exists("gui/resources/logo.svg"):
    cmd.append("--windows-icon-from-ico=gui/resources/logo.svg")
    cmd.append("--include-data-files=gui/resources/logo.svg;.")
    print("✅ Иконка добавлена")
else:
    print("⚠️ logo не найден")

# Дополнительно явно включаем проблемный модуль
cmd.append("--include-module=scipy._external.array_api_compat")
cmd.append("--include-module=scipy._external.array_api_compat.numpy")
cmd.append("--include-module=scipy._external.array_api_compat.numpy.fft")

print("Запускаю сборку Nuitka (это снова займёт время)...")
print()

result = subprocess.run(cmd, shell=False)

if result.returncode == 0:
    print("\n✅ Сборка завершена!")
    print(f"Папка: {name}.dist\\")
    print(f"Запускай: {name}.dist\\{name}.exe")
else:
    print("\n❌ Ошибка при сборке")
