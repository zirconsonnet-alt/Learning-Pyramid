from __future__ import annotations

import sys

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QMainWindow

from .launcher_window import LauncherWindow
from .theme import APP_STYLESHEET


def _bring_window_to_front(window: QMainWindow) -> None:
    # The tray launches the UI in a detached process on Windows, so we need to
    # explicitly restore and activate the window instead of relying on default
    # focus behavior.
    def _apply() -> None:
        if window.isMinimized():
            window.setWindowState(window.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        else:
            window.setWindowState(window.windowState() | Qt.WindowActive)
        window.show()
        window.raise_()
        window.activateWindow()

    def _nudge_topmost() -> None:
        if sys.platform != "win32":
            return
        window.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        window.show()
        window.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        _apply()

    _apply()
    QTimer.singleShot(0, _apply)
    QTimer.singleShot(150, _nudge_topmost)


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
    _bring_window_to_front(window)
    if not owns_app:
        return 0
    return int(app.exec())
