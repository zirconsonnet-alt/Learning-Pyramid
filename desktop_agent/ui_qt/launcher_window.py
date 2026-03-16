from __future__ import annotations

import os

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from desktop_agent.ui import DesktopAgentUiController

from .onboarding_dialog import OnboardingDialog
from .theme import BADGE_COLORS
from .view_model import LauncherState, build_launcher_state


class LauncherWindow(QMainWindow):
    def __init__(self, controller: DesktopAgentUiController | None = None) -> None:
        super().__init__()
        self.controller = controller or DesktopAgentUiController()
        self.setWindowTitle("LearningPyramid Desktop Agent")
        self.resize(920, 760)
        self.setMinimumSize(760, 620)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.setCentralWidget(scroll)

        central = QWidget()
        central.setObjectName("AppRoot")
        scroll.setWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(16)
        root_layout.setSizeConstraint(QLayout.SetMinimumSize)

        hero = QFrame()
        hero.setProperty("card", True)
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(24, 24, 24, 24)
        hero_layout.setSpacing(16)
        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(6)
        self.title_label = QLabel()
        self.title_label.setProperty("role", "title")
        self.title_label.setWordWrap(True)
        subtitle = QLabel("主界面只负责启动。登录、换账号和重新接入都放到第二层窗口。")
        subtitle.setProperty("role", "subtitle")
        subtitle.setWordWrap(True)
        hero_copy.addWidget(self.title_label)
        hero_copy.addWidget(subtitle)
        hero_layout.addLayout(hero_copy, 1)
        self.badge_label = QLabel()
        self.badge_label.setAlignment(Qt.AlignCenter)
        hero_layout.addWidget(self.badge_label, 0, Qt.AlignTop)
        root_layout.addWidget(hero)

        summary = QFrame()
        summary.setProperty("card", True)
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(24, 24, 24, 24)
        summary_layout.setSpacing(18)
        section = QLabel("当前连接器")
        section.setProperty("role", "section")
        summary_layout.addWidget(section)
        summary_grid = QGridLayout()
        summary_grid.setHorizontalSpacing(24)
        summary_grid.setVerticalSpacing(14)
        self.server_value = self._summary_value(summary_grid, 0, "服务器")
        self.project_value = self._summary_value(summary_grid, 0, "项目", column_offset=2)
        self.root_label_value = self._summary_value(summary_grid, 1, "逻辑根")
        self.device_value = self._summary_value(summary_grid, 1, "设备名称", column_offset=2)
        self.root_dir_value = self._summary_value(summary_grid, 2, "本地目录", span=3)
        self.version_value = self._summary_value(summary_grid, 3, "应用版本")
        summary_layout.addLayout(summary_grid)
        root_layout.addWidget(summary)

        action_card = QFrame()
        action_card.setProperty("card", True)
        action_layout = QVBoxLayout(action_card)
        action_layout.setContentsMargins(24, 24, 24, 24)
        action_layout.setSpacing(16)
        action_title = QLabel("启动控制")
        action_title.setProperty("role", "section")
        action_layout.addWidget(action_title)
        self.message_label = QLabel()
        self.message_label.setProperty("role", "subtitle")
        self.message_label.setWordWrap(True)
        self.message_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        action_layout.addWidget(self.message_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        self.start_button = QPushButton("启动连接器")
        self.start_button.setProperty("variant", "primary")
        self.start_button.clicked.connect(self._start_connector)
        self.reconfigure_button = QPushButton()
        self.reconfigure_button.clicked.connect(self._open_onboarding)
        self.open_logs_button = QPushButton("打开日志")
        self.open_logs_button.clicked.connect(self._open_logs)
        for button, min_width in (
            (self.start_button, 156),
            (self.reconfigure_button, 196),
            (self.open_logs_button, 132),
        ):
            button.setMinimumHeight(44)
            button.setMinimumWidth(min_width)
            button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.reconfigure_button)
        button_row.addWidget(self.open_logs_button)
        button_row.addStretch(1)
        action_layout.addLayout(button_row)

        self.autostart_checkbox = QCheckBox("Windows 登录后自动启动")
        self.autostart_checkbox.stateChanged.connect(self._toggle_autostart)
        action_layout.addWidget(self.autostart_checkbox)

        self.status_line = QLabel()
        self.status_line.setProperty("role", "hint")
        self.status_line.setWordWrap(True)
        self.status_line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.update_line = QLabel()
        self.update_line.setProperty("role", "hint")
        self.update_line.setWordWrap(True)
        self.update_line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.history_line = QLabel()
        self.history_line.setProperty("role", "hint")
        self.history_line.setWordWrap(True)
        self.history_line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        action_layout.addWidget(self.status_line)
        action_layout.addWidget(self.update_line)
        action_layout.addWidget(self.history_line)
        root_layout.addWidget(action_card)

        self.state = build_launcher_state(self.controller)
        self._render(self.state)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(3000)
        self.refresh_timer.timeout.connect(self.refresh_state)
        self.refresh_timer.start()

        if not self.state.start_enabled:
            QTimer.singleShot(80, self._open_onboarding)

    def _summary_value(self, grid: QGridLayout, row: int, label_text: str, *, column_offset: int = 0, span: int = 1) -> QLabel:
        label = QLabel(label_text)
        label.setProperty("role", "meta")
        value = QLabel("-")
        value.setProperty("role", "value")
        value.setWordWrap(True)
        grid.addWidget(label, row, column_offset)
        grid.addWidget(value, row, column_offset + 1, 1, span)
        grid.setColumnStretch(column_offset + 1, 1)
        return value

    def refresh_state(self) -> None:
        self._render(build_launcher_state(self.controller))

    def _render(self, state: LauncherState) -> None:
        self.state = state
        self.title_label.setText(state.title)
        self.message_label.setText(state.message)
        self.server_value.setText(state.server_url)
        self.project_value.setText(state.project_id)
        self.root_label_value.setText(state.root_label)
        self.root_dir_value.setText(state.root_dir)
        self.device_value.setText(state.device_name)
        self.version_value.setText(state.app_version)
        self.start_button.setEnabled(state.start_enabled)
        self.reconfigure_button.setText(state.reconfigure_label)
        self.autostart_checkbox.blockSignals(True)
        self.autostart_checkbox.setChecked(self.controller.autostart_enabled())
        self.autostart_checkbox.blockSignals(False)
        self.status_line.setText(f"状态：{state.status_summary}")
        self.update_line.setText(f"更新：{state.update_status}")
        self.history_line.setText(state.update_history)
        self._set_badge(state.status_key, state.status_badge)

    def _set_badge(self, status_key: str, text: str) -> None:
        color = BADGE_COLORS.get(status_key, "#475569")
        self.badge_label.setText(text)
        self.badge_label.setStyleSheet(
            "QLabel {"
            f"background: {color};"
            "color: white;"
            "border-radius: 999px;"
            "padding: 8px 14px;"
            "font-weight: 700;"
            "}"
        )

    def _start_connector(self) -> None:
        try:
            self.controller.start_agent_process()
            self.refresh_state()
        except Exception as exc:
            QMessageBox.critical(self, "启动失败", str(exc))

    def _open_onboarding(self) -> None:
        dialog = OnboardingDialog(self.controller, self)
        if dialog.exec():
            self.refresh_state()

    def _open_logs(self) -> None:
        log_path = self.controller.config_store.log_path
        try:
            if log_path.exists():
                os.startfile(str(log_path))
            else:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                os.startfile(str(log_path.parent))
        except Exception as exc:
            QMessageBox.critical(self, "打开日志失败", str(exc))

    def _toggle_autostart(self, value: int) -> None:
        try:
            self.controller.set_autostart(bool(value))
        except Exception as exc:
            QMessageBox.critical(self, "更新失败", str(exc))
            self.autostart_checkbox.blockSignals(True)
            self.autostart_checkbox.setChecked(self.controller.autostart_enabled())
            self.autostart_checkbox.blockSignals(False)
