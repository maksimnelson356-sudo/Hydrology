"""Точка входа для отладки frozen-сборки."""
import os
import sys
import traceback

print("1. Starting frozen app debug...")
print(f"  Frozen: {getattr(sys, 'frozen', False)}")
print(f"  Sys path: {sys.path[:3]}")

# Тест 1: Могут ли импортироваться модули?
print("\n2. Testing imports...")
try:
    print("  PyQt6.QtWidgets: OK")
    print("  PyQt6.QtCore: OK")
    import numpy; print(f"  numpy: OK ({numpy.__version__})")
    import scipy; print(f"  scipy: OK ({scipy.__version__})")
    import pandas; print(f"  pandas: OK ({pandas.__version__})")
    import matplotlib; print(f"  matplotlib: OK ({matplotlib.__version__})")
    import openpyxl; print(f"  openpyxl: OK ({openpyxl.__version__})")
except Exception as e:
    print(f"  IMPORT ERROR: {e}")
    traceback.print_exc()

# Тест 2: Могут ли импортироваться свои модули?
print("\n3. Testing project imports...")
try:
    from i18n import t; print(f"  i18n: OK (t('app_name')={t('app_name')})")
except Exception as e:
    print(f"  i18n ERROR: {e}")

try:
    from version import VERSION_STRING; print(f"  version: OK ({VERSION_STRING})")
except Exception as e:
    print(f"  version ERROR: {e}")

try:
    print("  update_checker: OK")
except Exception as e:
    print(f"  update_checker ERROR: {e}")

try:
    from gui.plot_style import build_stylesheet; s = build_stylesheet(); print(f"  plot_style: OK ({len(s)} chars)")
except Exception as e:
    print(f"  plot_style ERROR: {e}")

try:
    print("  core.stats.frequency: OK")
except Exception as e:
    print(f"  core.stats.frequency ERROR: {e}")

# Тест 3: Старт GUI
print("\n4. Starting GUI...")
try:
    from PyQt6.QtWidgets import QApplication
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    app = QApplication(sys.argv)
    print("  QApplication: OK")

    from gui.plot_style import FONT_DEFAULT, build_stylesheet
    app.setStyleSheet(build_stylesheet())
    app.setFont(FONT_DEFAULT)
    print("  Style: OK")

    from gui.main_window import MainWindow
    win = MainWindow()
    print("  MainWindow: OK")

    win.show()
    print("  show(): OK")

    from PyQt6.QtCore import QTimer
    QTimer.singleShot(1000, app.quit)
    app.exec()
    print("  app.exec: OK (exited)")

except Exception as e:
    print(f"  GUI ERROR: {e}")
    traceback.print_exc()

print("\n5. Done!")
