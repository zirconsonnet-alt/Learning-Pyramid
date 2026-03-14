from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .launcher_window import LauncherWindow
from .theme import APP_STYLESHEET


def launch_qt_ui() -> int:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv)
    app.setApplicationName("LearningPyramid Desktop Agent")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
    window = LauncherWindow()
    window.show()
    if not owns_app:
        return 0
    return int(app.exec())
