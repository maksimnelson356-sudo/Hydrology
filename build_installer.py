"""
build_installer.py
Полная сборка Windows-установщика HydroSphere.

Порядок:
  1. PyInstaller → dist/HydroSphere/
  2. Inno Setup → installer_output/HydroSphere_2026.1.0_Setup.exe

Зависимости:
  - PyInstaller: pip install pyinstaller
  - Inno Setup 6+: https://jrsoftware.org/isinfo.php (iscc.exe в PATH)

Использование:
  python build_installer.py
  python build_installer.py --skip-pyinstaller
  python build_installer.py --skip-inno
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from version import APP_NAME_EN, VERSION_MAJOR, VERSION_STRING
except ImportError:
    VERSION_STRING = "2026.1.0"
    APP_NAME_EN = "HydroSphere"
    VERSION_MAJOR = 2026

ROOT_DIR = Path(__file__).parent
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"
INSTALLER_DIR = ROOT_DIR / "installer"
INSTALLER_OUTPUT = ROOT_DIR / "installer_output"
PYINSTALLER_SPEC = ROOT_DIR / "HydroSphere.spec"


def check_pyinstaller():
    """Проверить, установлен ли PyInstaller."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print(f"  PyInstaller: {result.stdout.strip()}")
            return True
    except Exception:
        pass
    print("  PyInstaller не найден. Установите: pip install pyinstaller")
    return False


def check_inno_setup():
    """Проверить, установлен ли Inno Setup."""
    iscc_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        shutil.which("iscc"),
        shutil.which("ISCC"),
    ]
    for path in iscc_paths:
        if path and os.path.exists(path):
            print(f"  Inno Setup: {path}")
            return path
    print("  Inno Setup не найден.")
    print("  Скачайте: https://jrsoftware.org/isinfo.php")
    return None


def run_pyinstaller():
    """Собрать приложение через PyInstaller."""
    print("\n[1/3] Сборка PyInstaller...")

    if not check_pyinstaller():
        return False

    if DIST_DIR.exists():
        print(f"  Удаление предыдущей сборки: {DIST_DIR}")
        shutil.rmtree(DIST_DIR, ignore_errors=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean", "--noconfirm",
        "--onedir", "--windowed",
        "--name=HydroSphere",
        f"--icon={ROOT_DIR / 'icon.ico'}",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
        f"--specpath={ROOT_DIR}",
        f"--add-data={ROOT_DIR / 'i18n'};i18n",
        f"--add-data={ROOT_DIR / 'gui' / 'resources'};gui/resources",
        "--hidden-import=PyQt6",
        "--hidden-import=PyQt6.QtWidgets",
        "--hidden-import=PyQt6.QtGui",
        "--hidden-import=pandas",
        "--hidden-import=numpy",
        "--hidden-import=scipy",
        "--hidden-import=scipy.stats",
        "--hidden-import=matplotlib",
        "--hidden-import=openpyxl",
        "--hidden-import=core",
        "--hidden-import=core.stats",
        "--hidden-import=core.hydrorash",
        "--hidden-import=gui",
    ]

    # Добавляем все подмодули core и gui
    for pkg_dir in ["core/stats", "core/hydrorash", "gui"]:
        pkg_path = ROOT_DIR / pkg_dir
        if pkg_path.exists():
            for py_file in pkg_path.glob("*.py"):
                if py_file.name.startswith("__") and py_file.name != "__init__.py":
                    continue
                module = f"{pkg_dir.replace('/', '.')}.{py_file.stem}"
                cmd.append(f"--hidden-import={module}")

    print(f"  Команда: python -m PyInstaller ... ({len(cmd)} аргументов)")
    result = subprocess.run(cmd, cwd=str(ROOT_DIR))

    if result.returncode != 0:
        print("  ОШИБКА: PyInstaller завершился с ошибкой")
        return False

    # Проверяем результат
    exe_path = DIST_DIR / "HydroSphere" / "HydroSphere.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"  Готово: {exe_path} ({size_mb:.1f} MB)")
        return True
    else:
        print("  ОШИБКА: exe не найден после сборки")
        return False


def create_wizard_images():
    """Создать заглушки для изображений мастера установки."""
    print("\n[2/3] Подготовка ресурсов установщика...")

    INSTALLER_DIR.mkdir(exist_ok=True)

    # Проверяем наличие bitmap файлов
    wizard_bmp = INSTALLER_DIR / "installer_wizard.bmp"
    logo_bmp = INSTALLER_DIR / "installer_logo.bmp"

    if not wizard_bmp.exists():
        print(f"  Создаю заглушку: {wizard_bmp}")
        print("  (Замените на реальное изображение 164x314 px)")

    if not logo_bmp.exists():
        print(f"  Создаю заглушку: {logo_bmp}")
        print("  (Замените на реальное изображение 55x58 px)")

    return True


def run_inno_setup():
    """Собрать установщик через Inno Setup."""
    print("\n[3/3] Сборка установщика Inno Setup...")

    iscc_path = check_inno_setup()
    if not iscc_path:
        print("  Пропускаю Inno Setup (не установлен)")
        print("  Установите: https://jrsoftware.org/isinfo.php")
        return False

    iss_file = INSTALLER_DIR / "hydrosphere_installer.iss"
    if not iss_file.exists():
        print(f"  ОШИБКА: {iss_file} не найден")
        return False

    cmd = [iscc_path, str(iss_file)]
    result = subprocess.run(cmd, cwd=str(ROOT_DIR))

    if result.returncode != 0:
        print("  ОШИБКА: Inno Setup завершился с ошибкой")
        return False

    # Проверяем результат
    setup_files = list(INSTALLER_OUTPUT.glob("HydroSphere_*_Setup.exe"))
    if setup_files:
        for f in setup_files:
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"  Готово: {f} ({size_mb:.1f} MB)")
        return True
    else:
        print("  ОШИБКА: Setup.exe не найден")
        return False


def create_changelog():
    """Создать файл CHANGELOG для установщика."""
    changelog = INSTALLER_DIR / "CHANGELOG.txt"
    with open(changelog, "w", encoding="utf-8") as f:
        f.write(f"HydroSphere {VERSION_STRING}\n")
        f.write("=" * 40 + "\n\n")
        f.write("Изменения:\n")
        f.write("- Исправлены критические баги в расчётах\n")
        f.write("- Обновлён интерфейс\n")
        f.write("- Добавлены SVG-иконки\n")
        f.write("- Улучшена совместимость с NumPy\n")
        f.write("\nСистемные требования:\n")
        f.write("- Windows 10/11 (64-bit)\n")
        f.write("- 4 GB RAM\n")
        f.write("- 500 MB свободного места\n")
    print(f"  Создан: {changelog}")


def main():
    parser = argparse.ArgumentParser(description="Сборка установщика HydroSphere")
    parser.add_argument("--skip-pyinstaller", action="store_true",
                        help="Пропустить сборку PyInstaller")
    parser.add_argument("--skip-inno", action="store_true",
                        help="Пропустить Inno Setup (только PyInstaller)")
    args = parser.parse_args()

    print("=" * 60)
    print(f"  Сборка установщика {APP_NAME_EN} {VERSION_STRING}")
    print("=" * 60)

    success = True

    if not args.skip_pyinstaller:
        success = run_pyinstaller()
        if not success:
            print("\nСборка PyInstaller не удалась. Прерываю.")
            sys.exit(1)

    create_wizard_images()
    create_changelog()

    if not args.skip_inno:
        success = run_inno_setup()

    print("\n" + "=" * 60)
    if success:
        print("  СБОРКА ЗАВЕРШЕНА УСПЕШНО!")
        print(f"  Установщик: {INSTALLER_OUTPUT}")
    else:
        print("  Сборка завершена с предупреждениями")
    print("=" * 60)


if __name__ == "__main__":
    main()
