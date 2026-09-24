#!/usr/bin/env python3
"""
build.py — единый скрипт сборки HydroSphere
Поддерживает два режима:
  python build.py pyinstaller    — сборка через PyInstaller (по умолчанию)
  python build.py nuitka         — сборка через Nuitka
"""

import argparse
import os
import subprocess
import sys

# Название приложения
APP_NAME = "HydroSphere"
SCRIPT = os.path.join("gui", "main_window.py")

# Code signing configuration (environment variables)
CODESIGN_CERT_THUMBPRINT = os.environ.get("CODESIGN_CERT_THUMBPRINT", "")
CODESIGN_PASSWORD = os.environ.get("CODESIGN_PASSWORD", "")
CODESIGN_TIMESTAMP_URL = os.environ.get("CODESIGN_TIMESTAMP_URL", "http://timestamp.digicert.com")

# Скрытые импорты (общие для обоих режимов)
HIDDEN_IMPORTS = [
    "PyQt6", "PyQt6.QtWidgets", "PyQt6.QtGui", "PyQt6.QtCore", "PyQt6.QtSvg",
    "pandas", "numpy", "scipy", "scipy.stats", "scipy.optimize",
    "matplotlib", "matplotlib.backends.backend_qtagg",
    "openpyxl",
    "core", "core.stats", "core.hydrorash",
    "gui", "gui.plot_style", "gui.update_dialog", "gui.main_window",
    "version", "i18n", "update_checker",
    "core.stats.frequency", "core.stats.parameters", "core.stats.homogeneity",
    "core.stats.kritsky_tables", "core.stats.composite_curves",
    "core.stats.series_extension", "core.stats.report_export",
    "core.stats.report", "core.stats.gts_integration",
    "core.stats.advanced_frequency", "core.stats.confidence_bands",
    "core.stats.baseflow", "core.stats.spectral", "core.stats.drought",
    "core.stats.data_loader", "core.stats.missing_data", "core.stats.trends",
    "core.stats.sheet_reader", "core.stats.flow_duration",
    "core.stats.advanced_frequency", "core.stats.confidence_bands",
    "core.hydrorash.utils", "core.hydrorash.hydrological_periods",
    "core.hydrorash.intra_annual", "core.hydrorash.minimal_runoff",
    "core.hydrorash.max_runoff", "core.hydrorash.ice_phenomena",
    "core.hydrorash.water_balance", "core.hydrorash.min_runoff_extended",
    "core.hydrorash.rational_method", "core.hydrorash.flood_hydrograph",
    "core.hydrorash.routing", "core.hydrorash.inundation",
    "core.hydrorash.snowmelt", "core.hydrorash.regional_regressions",
    "core.hydrorash.spillway", "core.hydrorash.backwater",
    "core.hydrorash.reservoir_regulation", "core.hydrorash.sedimentation",
    "core.hydrorash.ecological_flow",
    "core.short_series", "core.gts_reference",
    "core.domain", "core.domain.models", "core.domain.enums",
    "core.domain.serialization",
    "core.services", "core.services.bootstrap", "core.services.calculation_service",
    "core.services.api_source",
    "core.services.calibration_service",
    "core.services.data_quality_service", "core.services.import_service",
    "core.services.geo_service",
    "core.services.monte_carlo_service",
    "core.services.sensitivity_service",
    "core.services.climate_service",
    "core.services.decision_support_service",
    "core.hydraulics_profile",
    "core.services.backwater_profile_service",
    "core.services.routing_service",
    "core.services.inundation_service",
    "core.services.hydraulic_uncertainty_service",
    "core.services.methodology_registry",
    "core.services.project_service", "core.services.quality_pipeline",
    "core.services.report_service",
    "core.services.result_store", "core.services.scenario_service",
    "core.services.reservoir_scenario_service",
    "core.services.validation_service",
    "core.services.handlers", "core.services.handlers.__init__",
    "core.stats.metrics", "core.stats.geometry",
    "gui.widget_work1", "gui.widget_work2", "gui.widget_work3",
    "gui.widget_work4", "gui.widget_work5", "gui.widget_work6",
    "gui.widget_work7", "gui.widget_work8", "gui.widget_work9",
    "gui.widget_work10", "gui.widget_short",
    "gui.plot_style", "gui.update_dialog",
    "gui.controller", "gui.controller.data_controller",
    "gui.controller.plot_controller", "gui.controller.widget_factory",
    "gui.dialogs", "gui.dialogs.data_quality_dialog", "gui.dialogs.import_dialog",
    "gui.dialogs.api_import_dialog",
    "gui.dialogs.calibration_dialog",
    "gui.tabs", "gui.tabs.tab_project", "gui.tabs.tab_methodology",
    "gui.tabs.tab_data", "gui.tabs.tab_data_quality", "gui.tabs.tab_results",
    "gui.tabs.tab_scenarios", "gui.tabs.tab_report", "gui.tabs.tab_geo",
    "gui.tabs.tab_inundation", "gui.tabs.tab_monte_carlo",
    "gui.tabs.hydraulic_uncertainty_panel",
    "gui.tabs.hydraulic_uncertainty_result_view",
    "gui.tabs.hydraulic_uncertainty_support",
    "gui.workers", "gui.workers.calculation_workers",
    "gui.workers.hydraulic_uncertainty_worker",
    "create_unified_template",
]

DATAS = [
    ("i18n", "i18n"),
    ("gui/resources", "gui/resources"),
]


def get_pyinstaller_args():
    """Формирует аргументы для PyInstaller"""
    args = [
        "--name=HydroSphere",
        "--onedir",
        "--windowed",
        "--clean",
        "--noconfirm",
    ]

    # Hidden imports
    for imp in HIDDEN_IMPORTS:
        args.append(f"--hidden-import={imp}")

    # Data files
    for src, dst in DATAS:
        if os.path.exists(src):
            args.append(f"--add-data={src}{os.pathsep}{dst}")

    # Icon
    if os.path.exists("icon.ico"):
        args.append("--icon=icon.ico")
        print("Icon added")
    else:
        print("Warning: icon.ico not found, build without icon")

    # Code signing
    CODESIGN_CERT_THUMBPRINT = os.environ.get("CODESIGN_CERT_THUMBPRINT", "")
    CODESIGN_PASSWORD = os.environ.get("CODESIGN_PASSWORD", "")
    CODESIGN_TIMESTAMP_URL = os.environ.get("CODESIGN_TIMESTAMP_URL", "http://timestamp.digicert.com")
    if CODESIGN_CERT_THUMBPRINT:
        args.extend([
            f"--codesign-identity={CODESIGN_CERT_THUMBPRINT}",
            f"--codesign-password={CODESIGN_PASSWORD}",
            f"--codesign-timestamp-url={CODESIGN_TIMESTAMP_URL}",
        ])
        print("Code signing enabled")
    else:
        print("Code signing disabled")

    # Entry script
    args.append("gui/main_window.py")

    return args


def get_nuitka_args():
    """Формирует аргументы для Nuitka"""
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--windows-console-mode=disable",
        "--enable-plugin=pyqt6",
        "--output-filename=HydroSphere.exe",
        "--assume-yes-for-downloads",
        "--remove-output",
    ]

    # Packages
    packages = [
        "core", "gui", "i18n", "PyQt6", "pandas", "numpy",
        "scipy", "scipy.stats", "scipy.optimize",
        "matplotlib", "matplotlib.backends.backend_qtagg",
        "openpyxl", "scipy._lib", "scipy._external",
        "scipy.sparse", "numpy", "pandas", "matplotlib",
    ]
    for pkg in packages:
        cmd.append(f"--include-package={pkg}")

    # Package data
    cmd.append("--include-package-data=matplotlib")
    cmd.append("--include-package-data=matplotlib.backends")

    # Explicit modules for scipy compatibility
    cmd.extend([
        "--include-module=scipy._external.array_api_compat",
        "--include-module=scipy._external.array_api_compat.numpy",
        "--include-module=scipy._external.array_api_compat.numpy.fft",
    ])

    # Data files
    for src, dst in DATAS:
        if os.path.exists(src):
            cmd.append(f"--include-data-dir={src}={dst}")

    # Icon
    if os.path.exists("gui/resources/logo.png"):
        cmd.append("--windows-icon-from-ico=gui/resources/logo.png")
        cmd.append("--include-data-files=gui/resources/logo.png;.")
        print("✅ Иконка добавлена (logo.png)")
    elif os.path.exists("icon.ico"):
        cmd.append("--windows-icon-from-ico=icon.ico")
        cmd.append("--include-data-files=icon.ico;.")
        print("✅ Иконка добавлена (icon.ico)")
    else:
        print("⚠️ logo не найден")

    # Code signing for Nuitka
    CODESIGN_CERT_THUMBPRINT = os.environ.get("CODESIGN_CERT_THUMBPRINT", "")
    CODESIGN_PASSWORD = os.environ.get("CODESIGN_PASSWORD", "")
    CODESIGN_TIMESTAMP_URL = os.environ.get("CODESIGN_TIMESTAMP_URL", "http://timestamp.digicert.com")
    if CODESIGN_CERT_THUMBPRINT:
        cmd.extend([
            "--windows-onefile-icons=icon.ico" if os.path.exists("icon.ico") else "",
            "--signer=--signtool=signtool.exe",
            f"--signtool-args=/sha1 {CODESIGN_CERT_THUMBPRINT} /fd sha256 /tr {CODESIGN_TIMESTAMP_URL} /td sha256",
        ])
        print("✅ Code signing enabled (Nuitka)")
    else:
        print("⚠️ Code signing disabled (set CODESIGN_CERT_THUMBPRINT env var to enable)")

    # Entry script
    cmd.append("gui/main_window.py")

    return cmd


def run_pyinstaller():
    """Запуск сборки через PyInstaller"""
    import PyInstaller.__main__

    args = get_pyinstaller_args()
    print("Starting PyInstaller...")
    print("Arguments:", " ".join(args))
    print()

    PyInstaller.__main__.run(args)

    print("\nPyInstaller build completed!")
    print("Папка: dist/HydroSphere/")
    print("Запускай файл: dist/HydroSphere/HydroSphere.exe")


def run_nuitka():
    """Запуск сборки через Nuitka"""
    cmd = get_nuitka_args()
    print("🔨 Запуск Nuitka...")
    print("Команда:", " ".join(cmd))
    print()

    result = subprocess.run(cmd, shell=False)

    if result.returncode == 0:
        print("\n✅ Сборка Nuitka завершена!")
        print("Папка: HydroSphere.dist\\")
        print("Запускай: HydroSphere.dist\\HydroSphere.exe")
    else:
        print("\n❌ Ошибка при сборке Nuitka")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="HydroSphere Build Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python build.py pyinstaller    # Build with PyInstaller (default)
  python build.py nuitka         # Build with Nuitka
  python build.py --help         # Show this help
        """
    )
    parser.add_argument(
        "mode", nargs="?", default="pyinstaller",
        choices=["pyinstaller", "nuitka"],
        help="Build mode (default: pyinstaller)"
    )
    args = parser.parse_args()

    print("HydroSphere Build Script")
    print(f"Mode: {args.mode}")
    print(f"App: {APP_NAME}")
    print()

    if args.mode == "pyinstaller":
        run_pyinstaller()
    elif args.mode == "nuitka":
        run_nuitka()


if __name__ == "__main__":
    main()
