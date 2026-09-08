"""gui/main_frozen.py — точка входа с отладкой для frozen-сборки."""
import os
import sys
import traceback

# Перенаправляем всё в лог-файл
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "startup.log")
if getattr(sys, 'frozen', False):
    LOG = os.path.join(os.path.dirname(sys.executable), "startup.log")

with open(LOG, "w", encoding="utf-8") as _log:
    _log.write(f"sys.frozen={getattr(sys, 'frozen', False)}\n")
    _log.write(f"sys.executable={sys.executable}\n")
    _log.write(f"sys.path={sys.path[:5]}\n")
    _log.write(f"__file__={__file__}\n")

    # Подавляем отображение, перехватывая ошибки
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        _log.write("sys.path inserted\n")

        from PyQt6.QtWidgets import QApplication
        _log.write("QApplication imported\n")
        from PyQt6.QtCore import QThread, QTimer, pyqtSignal
        _log.write("PyQt6.QtCore imported\n")

        from version import VERSION_STRING
        _log.write(f"VERSION={VERSION_STRING}\n")

        from update_checker import get_updater
        _log.write("update_checker imported\n")

        from gui.plot_style import (
            FONT_DEFAULT,
            build_stylesheet,
        )
        _log.write("plot_style imported\n")

        from gui.main_window import MainWindow
        _log.write("MainWindow imported\n")

        # Создаём QApplication
        app = QApplication(sys.argv)
        app.setStyleSheet(build_stylesheet())
        app.setFont(FONT_DEFAULT)
        _log.write("QApp created + styled\n")

        window = MainWindow()
        window.setMinimumSize(1200, 700)
        window.show()
        _log.write("Window shown!\n")

        # Фоновая проверка обновлений
        class _StartupUpdateWorker(QThread):
            update_found = pyqtSignal(object)
            def run(self):
                try:
                    result = get_updater().check_once()
                    self.update_found.emit(result)
                except Exception:
                    self.update_found.emit(None)

        def _on_startup_update(info):
            if info is not None:
                from gui.update_dialog import UpdateDialog
                dialog = UpdateDialog(parent=window, checker=get_updater().get_checker(), update_info=info)
                dialog.show()

        worker = _StartupUpdateWorker(window)
        worker.update_found.connect(_on_startup_update)
        QTimer.singleShot(1500, worker.start)

        _log.write("Starting app.exec()\n")
        _log.flush()
        sys.exit(app.exec())

    except Exception as e:
        _log.write(f"FATAL: {type(e).__name__}: {e}\n")
        _log.write(traceback.format_exc())
        _log.flush()
        print(f"FATAL: {e}", file=sys.stderr)
