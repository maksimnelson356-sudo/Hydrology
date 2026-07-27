"""
build.py — сборка в папку (с иконкой)
"""

import PyInstaller.__main__
import os

script = "gui/main_window.py"
name = "ГидроСтатистика_2026"

args = [
    script,
    f"--name={name}",
    "--onedir",
    "--windowed",
    "--clean",
    "--noconfirm",
    "--hidden-import=PyQt6",
    "--hidden-import=PyQt6.QtWidgets",
    "--hidden-import=PyQt6.QtGui",
    "--hidden-import=pandas",
    "--hidden-import=numpy",
    "--hidden-import=scipy",
    "--hidden-import=scipy.stats",
    "--hidden-import=matplotlib",
    "--hidden-import=openpyxl",
    "--hidden-import=matplotlib.backends.backend_qtagg",
    "--hidden-import=core.hydrorash",
    "--hidden-import=core.hydrorash.utils",
    "--hidden-import=core.hydrorash.hydrological_periods",
    "--hidden-import=core.hydrorash.intra_annual",
    "--hidden-import=core.hydrorash.minimal_runoff",
    "--hidden-import=core.hydrorash.max_runoff",
    "--hidden-import=core.hydrorash.ice_phenomena",
    "--hidden-import=core.hydrorash.water_balance",
    "--hidden-import=core.hydrorash.min_runoff_extended",
    "--hidden-import=core.hydrorash.rational_method",
    "--hidden-import=core.hydrorash.flood_hydrograph",
    "--hidden-import=core.hydrorash.snowmelt",
    "--hidden-import=core.hydrorash.regional_regressions",
    "--hidden-import=core.hydrorash.spillway",
    "--hidden-import=core.hydrorash.backwater",
    "--hidden-import=core.hydrorash.reservoir_regulation",
    "--hidden-import=core.hydrorash.sedimentation",
    "--hidden-import=core.hydrorash.ecological_flow",
    "--hidden-import=core.stats.flow_duration",
    "--hidden-import=core.stats.advanced_frequency",
    "--hidden-import=core.stats.confidence_bands",
    "--hidden-import=core.stats.baseflow",
    "--hidden-import=core.stats.spectral",
    "--hidden-import=core.stats.drought",
    "--hidden-import=core.stats.data_loader",
    "--hidden-import=core.stats.frequency",
    "--hidden-import=core.stats.parameters",
    "--hidden-import=core.stats.missing_data",
    "--hidden-import=core.stats.trends",
    "--hidden-import=core.stats.kritsky_tables",
    "--hidden-import=core.stats.composite_curves",
    "--hidden-import=core.stats.series_extension",
    "--hidden-import=core.stats.report_export",
    "--hidden-import=core.stats.report",
    "--hidden-import=core.stats.gts_integration",
    "--hidden-import=core.stats.homogeneity",
    "--hidden-import=core.stats.critical_values",
    "--hidden-import=gui.widget_work1",
    "--hidden-import=gui.widget_work2",
    "--hidden-import=gui.widget_work3",
    "--hidden-import=gui.widget_work4",
    "--hidden-import=gui.widget_work5",
    "--hidden-import=gui.widget_work6",
    "--hidden-import=gui.widget_work7",
    "--hidden-import=gui.widget_work8",
    "--hidden-import=gui.widget_work9",
    "--hidden-import=gui.widget_work10",
]

if os.path.exists("icon.ico"):
    args.append("--icon=icon.ico")
    print("✅ Иконка добавлена")
else:
    print("⚠️ Файл icon.ico не найден")

PyInstaller.__main__.run(args)

print("\nСборка завершена!")
print(f"Папка: dist\\{name}\\")
print("Запускай файл: dist\\ГидроСтатистика_2026\\ГидроСтатистика_2026.exe")
