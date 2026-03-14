from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
)

from backend.system.version import APP_VERSION
from desktop_agent.account_client import DesktopAgentAccountSession
from desktop_agent.config_store import AgentConfig
from desktop_agent.setup_client import DesktopAgentSetupBootstrap, DesktopAgentSetupCandidateRoot, DesktopAgentSetupProject
from desktop_agent.ui import DesktopAgentUiController, _default_device_name, _default_server_url, _friendly_setup_error_message


class OnboardingDialog(QDialog):
    login_finished = Signal(object, object)
    setup_code_finished = Signal(object, object)
    save_finished = Signal(object, object)

    def __init__(self, controller: DesktopAgentUiController, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("登录并接入")
        self.setModal(True)
        self.resize(760, 620)

        self.account_session: DesktopAgentAccountSession | None = None
        self.bootstrap: DesktopAgentSetupBootstrap | None = None
        self.project_display_to_item: dict[str, DesktopAgentSetupProject] = {}
        self.directory_display_to_item: dict[str, DesktopAgentSetupCandidateRoot] = {}
        self._busy = False

        saved = self.controller.load_saved_config()
        self.server_input = QLineEdit(saved.server_url if saved else _default_server_url())
        self.email_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.setup_code_input = QLineEdit()
        self.project_combo = QComboBox()
        self.directory_combo = QComboBox()
        self.root_dir_input = QLineEdit(saved.root_dir if saved else "")
        self.root_dir_input.setReadOnly(True)
        self.device_name_input = QLineEdit(saved.device_name if saved else _default_device_name())
        self.root_label_value = QLabel(saved.source_root_label if saved and saved.source_root_label else "-")
        self.status_label = QLabel("登录只用于完成接入。保存后回到首页可以直接一键启动。")
        self.status_label.setProperty("role", "hint")

        self.login_button = QPushButton("登录账号")
        self.load_setup_button = QPushButton("加载接入码")
        self.choose_dir_button = QPushButton("选择目录")
        self.save_button = QPushButton("保存并启动连接器")
        self.cancel_button = QPushButton("取消")
        self.toggle_setup_button = QToolButton()
        self.setup_code_frame = QFrame()

        self.login_button.clicked.connect(self._login_account)
        self.load_setup_button.clicked.connect(self._load_setup_code)
        self.choose_dir_button.clicked.connect(self._choose_root_dir)
        self.save_button.clicked.connect(self._save_and_start)
        self.cancel_button.clicked.connect(self.reject)
        self.project_combo.currentTextChanged.connect(self._apply_project_selection)
        self.directory_combo.currentTextChanged.connect(self._apply_directory_selection)
        self.login_finished.connect(self._finish_login_account)
        self.setup_code_finished.connect(self._finish_load_setup_code)
        self.save_finished.connect(self._finish_save_and_start)

        self._build_ui()
        self._update_controls()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(16)

        hero = QFrame()
        hero.setProperty("card", True)
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 24, 24, 24)
        hero_layout.setSpacing(6)
        title = QLabel("登录并接入")
        title.setProperty("role", "title")
        subtitle = QLabel("登录只用于接入。后续启动使用已保存令牌，不需要重复输入密码。")
        subtitle.setProperty("role", "subtitle")
        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        root_layout.addWidget(hero)

        form_card = QFrame()
        form_card.setProperty("card", True)
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(24, 24, 24, 24)
        form_layout.setSpacing(18)
        root_layout.addWidget(form_card, 1)

        login_section = self._create_section("1. 登录账号")
        login_grid = QGridLayout()
        login_grid.setHorizontalSpacing(12)
        login_grid.setVerticalSpacing(12)
        self._add_form_row(login_grid, 0, "服务器", self.server_input)
        self._add_form_row(login_grid, 1, "账号邮箱", self.email_input)
        login_row = QHBoxLayout()
        login_row.setSpacing(12)
        login_row.addWidget(self.password_input, 1)
        login_row.addWidget(self.login_button)
        self._add_form_row(login_grid, 2, "账号密码", login_row)
        login_section.layout().addLayout(login_grid)
        form_layout.addWidget(login_section)

        self.toggle_setup_button.setText("使用接入码接入")
        self.toggle_setup_button.setCheckable(True)
        self.toggle_setup_button.toggled.connect(self._toggle_setup_code_panel)
        form_layout.addWidget(self.toggle_setup_button)

        self.setup_code_frame.setProperty("card", True)
        self.setup_code_frame.setVisible(False)
        setup_code_layout = QVBoxLayout(self.setup_code_frame)
        setup_code_layout.setContentsMargins(16, 16, 16, 16)
        setup_code_layout.setSpacing(10)
        setup_code_hint = QLabel("如果你拿到网页生成的接入码，也可以直接完成接入。")
        setup_code_hint.setProperty("role", "subtitle")
        setup_code_layout.addWidget(setup_code_hint)
        setup_code_row = QHBoxLayout()
        setup_code_row.setSpacing(12)
        setup_code_row.addWidget(self.setup_code_input, 1)
        setup_code_row.addWidget(self.load_setup_button)
        setup_code_layout.addLayout(setup_code_row)
        form_layout.addWidget(self.setup_code_frame)

        bind_section = self._create_section("2. 选择项目和目录")
        bind_grid = QGridLayout()
        bind_grid.setHorizontalSpacing(12)
        bind_grid.setVerticalSpacing(12)
        self.project_combo.setEnabled(False)
        self.directory_combo.setEnabled(False)
        self._add_form_row(bind_grid, 0, "项目", self.project_combo)
        self._add_form_row(bind_grid, 1, "逻辑根", self.directory_combo)
        root_dir_row = QHBoxLayout()
        root_dir_row.setSpacing(12)
        root_dir_row.addWidget(self.root_dir_input, 1)
        root_dir_row.addWidget(self.choose_dir_button)
        self._add_form_row(bind_grid, 2, "本地目录", root_dir_row)
        self._add_form_row(bind_grid, 3, "设备名称", self.device_name_input)
        self._add_form_row(bind_grid, 4, "同步标签", self.root_label_value)
        bind_section.layout().addLayout(bind_grid)
        form_layout.addWidget(bind_section)

        footer = QHBoxLayout()
        footer.setSpacing(12)
        self.save_button.setProperty("variant", "primary")
        footer.addWidget(self.save_button)
        footer.addWidget(self.cancel_button)
        footer.addStretch(1)
        form_layout.addWidget(self.status_label)
        form_layout.addLayout(footer)

    def _create_section(self, title: str) -> QFrame:
        section = QFrame()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        label = QLabel(title)
        label.setProperty("role", "section")
        layout.addWidget(label)
        return section

    def _add_form_row(self, layout: QGridLayout, row: int, label_text: str, field) -> None:
        label = QLabel(label_text)
        label.setProperty("role", "meta")
        layout.addWidget(label, row, 0, alignment=Qt.AlignTop)
        if isinstance(field, QHBoxLayout):
            wrapper = QFrame()
            wrapper_layout = QHBoxLayout(wrapper)
            wrapper_layout.setContentsMargins(0, 0, 0, 0)
            wrapper_layout.addLayout(field)
            layout.addWidget(wrapper, row, 1)
        else:
            layout.addWidget(field, row, 1)
        layout.setColumnStretch(1, 1)

    def _toggle_setup_code_panel(self, checked: bool) -> None:
        self.setup_code_frame.setVisible(bool(checked))

    def _set_busy(self, busy: bool, message: str | None = None) -> None:
        self._busy = bool(busy)
        if message:
            self.status_label.setText(message)
        self._update_controls()

    def _selected_project(self) -> DesktopAgentSetupProject | None:
        return self.project_display_to_item.get(self.project_combo.currentText())

    def _selected_candidate_root(self) -> DesktopAgentSetupCandidateRoot | None:
        return self.directory_display_to_item.get(self.directory_combo.currentText())

    def _current_server_url(self) -> str:
        if self.account_session is not None:
            return self.account_session.server_url
        if self.bootstrap is not None:
            return self.bootstrap.server_url
        return self.server_input.text().strip().rstrip("/")

    def _update_controls(self) -> None:
        self.login_button.setEnabled(not self._busy)
        self.load_setup_button.setEnabled(not self._busy)
        self.project_combo.setEnabled(bool(self.project_display_to_item) and not self._busy)
        self.directory_combo.setEnabled(bool(self.directory_display_to_item) and not self._busy)
        self.choose_dir_button.setEnabled(self._selected_candidate_root() is not None and not self._busy)
        can_save = (
            not self._busy
            and (self.account_session is not None or self.bootstrap is not None)
            and self._selected_project() is not None
            and self._selected_candidate_root() is not None
            and bool(self.root_dir_input.text().strip())
        )
        self.save_button.setEnabled(can_save)

    def _find_preferred_candidate_display(self, project: DesktopAgentSetupProject, values: list[str]) -> str:
        current_server_url = self._current_server_url()
        for display in values:
            candidate = self.directory_display_to_item[display]
            if self.controller.load_saved_root_dir(
                server_url=current_server_url,
                project_id=project.project_id,
                candidate_root=candidate,
            ):
                return display
        if project.source_root_label:
            for display in values:
                candidate = self.directory_display_to_item[display]
                if candidate.source_root_label == project.source_root_label:
                    return display
        return values[0] if values else ""

    def _apply_project_catalog(
        self,
        *,
        server_url: str,
        projects: tuple[DesktopAgentSetupProject, ...],
        preferred_project_id: str | None,
        status_message: str,
    ) -> None:
        self.server_input.setText(server_url)
        self.project_display_to_item.clear()
        self.project_combo.clear()
        for project in projects:
            display = f"{project.title} [{project.project_id}]"
            self.project_display_to_item[display] = project
            self.project_combo.addItem(display)
        preferred_display = next(
            (display for display, project in self.project_display_to_item.items() if project.project_id == (preferred_project_id or "")),
            self.project_combo.itemText(0) if self.project_combo.count() else "",
        )
        if preferred_display:
            self.project_combo.setCurrentText(preferred_display)
        self.status_label.setText(status_message)
        self._apply_project_selection()
        self._update_controls()

    def _apply_project_selection(self) -> None:
        project = self._selected_project()
        self.directory_display_to_item.clear()
        self.directory_combo.clear()
        if project is None:
            self.root_dir_input.setText("")
            self.root_label_value.setText("-")
            self._update_controls()
            return
        values: list[str] = []
        for candidate_root in self.controller.list_candidate_roots(project):
            label = str(candidate_root.label).strip() or "默认根目录"
            relative_path = str(candidate_root.relative_path).strip()
            display = label if not relative_path else f"{label} ({relative_path})"
            if display in self.directory_display_to_item:
                display = f"{display} [{candidate_root.root_key}]"
            self.directory_display_to_item[display] = candidate_root
            values.append(display)
            self.directory_combo.addItem(display)
        preferred = self._find_preferred_candidate_display(project, values)
        if preferred:
            self.directory_combo.setCurrentText(preferred)
        self._apply_directory_selection()

    def _apply_directory_selection(self) -> None:
        project = self._selected_project()
        candidate_root = self._selected_candidate_root()
        if project is None or candidate_root is None:
            self.root_dir_input.setText("")
            self.root_label_value.setText("-")
            self._update_controls()
            return
        self.root_label_value.setText(candidate_root.source_root_label or "默认根目录")
        saved_root_dir = self.controller.load_saved_root_dir(
            server_url=self._current_server_url(),
            project_id=project.project_id,
            candidate_root=candidate_root,
        )
        self.root_dir_input.setText(saved_root_dir or "")
        self.status_label.setText("已加载保存目录。" if saved_root_dir else "请选择这个逻辑根对应的本地目录。")
        self._update_controls()

    def _choose_root_dir(self) -> None:
        project = self._selected_project()
        candidate_root = self._selected_candidate_root()
        if project is None or candidate_root is None:
            QMessageBox.critical(self, "选择目录失败", "请先选择项目和逻辑根。")
            return
        initial_dir = self.root_dir_input.text().strip() or str(Path.home())
        selected = QFileDialog.getExistingDirectory(self, f"为 {project.title} / {candidate_root.label} 选择本地目录", initial_dir)
        if not selected:
            return
        self.root_dir_input.setText(str(Path(selected).expanduser().resolve()))
        self.status_label.setText("已选择本地目录。保存后，这台机器会记住这个映射。")
        self._update_controls()

    def _login_account(self) -> None:
        server_url = self.server_input.text().strip().rstrip("/")
        email = self.email_input.text().strip()
        password = self.password_input.text()
        if not server_url:
            QMessageBox.critical(self, "登录失败", "服务器地址不可为空。")
            return
        if not email:
            QMessageBox.critical(self, "登录失败", "请输入账号邮箱。")
            return
        if not password:
            QMessageBox.critical(self, "登录失败", "请输入账号密码。")
            return
        self._set_busy(True, "正在登录账号并加载项目列表。")

        def _worker() -> None:
            try:
                result = self.controller.login_account(server_url=server_url, email=email, password=password)
                self.login_finished.emit(result, None)
            except Exception as exc:
                self.login_finished.emit(None, exc)

        threading.Thread(target=_worker, name="desktop-agent-qt-login", daemon=True).start()

    def _finish_login_account(self, account_session: object, error: object) -> None:
        self._set_busy(False)
        if error is not None:
            QMessageBox.critical(self, "登录失败", str(error))
            return
        assert isinstance(account_session, DesktopAgentAccountSession)
        self.account_session = account_session
        self.bootstrap = None
        self.setup_code_input.clear()
        self._apply_project_catalog(
            server_url=account_session.server_url,
            projects=account_session.bootstrap.projects,
            preferred_project_id=account_session.bootstrap.preferred_project_id,
            status_message="账号登录成功。请选择项目、逻辑根和本地目录，然后保存并启动连接器。",
        )

    def _load_setup_code(self) -> None:
        setup_code = self.setup_code_input.text().strip()
        if not setup_code:
            QMessageBox.critical(self, "加载接入码失败", "请输入接入码。")
            return
        self._set_busy(True, "正在加载接入码并准备项目列表。")

        def _worker() -> None:
            try:
                result = self.controller.load_setup_bootstrap(setup_code)
                self.setup_code_finished.emit(result, None)
            except Exception as exc:
                self.setup_code_finished.emit(None, exc)

        threading.Thread(target=_worker, name="desktop-agent-qt-setup-code", daemon=True).start()

    def _finish_load_setup_code(self, bootstrap: object, error: object) -> None:
        self._set_busy(False)
        if error is not None:
            QMessageBox.critical(self, "加载接入码失败", str(error))
            return
        assert isinstance(bootstrap, DesktopAgentSetupBootstrap)
        self.bootstrap = bootstrap
        self.account_session = None
        self._apply_project_catalog(
            server_url=bootstrap.server_url,
            projects=bootstrap.projects,
            preferred_project_id=bootstrap.preferred_project_id,
            status_message="接入码已加载。请选择项目、逻辑根和本地目录，然后保存并启动连接器。",
        )

    def _save_and_start(self) -> None:
        project = self._selected_project()
        candidate_root = self._selected_candidate_root()
        root_dir = self.root_dir_input.text().strip()
        if self.account_session is None and self.bootstrap is None:
            QMessageBox.critical(self, "保存失败", "请先登录账号，或加载接入码。")
            return
        if project is None:
            QMessageBox.critical(self, "保存失败", "请选择项目。")
            return
        if candidate_root is None:
            QMessageBox.critical(self, "保存失败", "请选择逻辑根。")
            return
        if not root_dir:
            QMessageBox.critical(self, "保存失败", "请先选择本地目录。")
            return
        self._set_busy(True, "正在保存配置并启动连接器。")

        def _worker() -> None:
            try:
                saved = self.controller.load_saved_config()
                app_version = saved.app_version if saved is not None else APP_VERSION
                if self.account_session is not None:
                    config = self.controller.account_setup_and_save(
                        account_session=self.account_session,
                        project_id=project.project_id,
                        candidate_root_key=candidate_root.root_key,
                        root_dir=root_dir,
                        device_name=self.device_name_input.text(),
                        app_version=app_version,
                    )
                else:
                    assert self.bootstrap is not None
                    config = self.controller.setup_and_save(
                        setup_code=self.setup_code_input.text(),
                        bootstrap=self.bootstrap,
                        project_id=project.project_id,
                        candidate_root_key=candidate_root.root_key,
                        root_dir=root_dir,
                        device_name=self.device_name_input.text(),
                        app_version=app_version,
                    )
                self.controller.start_agent_process()
                self.save_finished.emit(config, None)
            except Exception as exc:
                self.save_finished.emit(None, exc)

        threading.Thread(target=_worker, name="desktop-agent-qt-save", daemon=True).start()

    def _finish_save_and_start(self, config: object, error: object) -> None:
        self._set_busy(False)
        if error is not None:
            QMessageBox.critical(self, "启动失败", _friendly_setup_error_message(error))
            return
        assert isinstance(config, AgentConfig)
        self.password_input.clear()
        self.setup_code_input.clear()
        self.accept()
