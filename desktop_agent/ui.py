from __future__ import annotations

import os
import socket
import subprocess
import threading
from pathlib import Path
from typing import Callable

import requests

from backend.system.version import APP_VERSION
from desktop_agent.account_client import (
    DesktopAgentAccountSession,
    account_pair_desktop_agent,
    complete_desktop_agent_account_setup,
    login_desktop_agent_account,
)
from desktop_agent.autostart import AutostartManager, current_agent_command
from desktop_agent.config_store import AgentConfig, AgentUpdateState, ConfigStore
from desktop_agent.instance_lock import SingleInstanceLock
from desktop_agent.relay_client import _raise_for_agent_response
from desktop_agent.runtime_defaults import current_default_server_url
from desktop_agent.setup_client import (
    DesktopAgentSetupBootstrap,
    DesktopAgentSetupCandidateRoot,
    DesktopAgentSetupProject,
    complete_desktop_agent_setup,
    fetch_desktop_agent_setup_bootstrap,
)
from desktop_agent.updater import DesktopAgentUpdateCheckResult, DesktopAgentUpdater


def _default_server_url() -> str:
    return current_default_server_url().rstrip("/")


def _default_device_name() -> str:
    return socket.gethostname() or "WINDOWS-PC"


def _env_enabled(name: str, *, default: bool = False) -> bool:
    raw = str(os.getenv(name) or "").strip()
    if not raw:
        return bool(default)
    return raw.lower() in {"1", "true", "yes", "on"}


def _normalize_project_id(project_id: str) -> str:
    normalized = str(project_id).strip()
    if not normalized:
        raise ValueError("project_id is required")
    if not normalized.startswith("proj_"):
        raise ValueError("project_id must look like proj_000001; use the hosted project ID, not the title or folder name")
    return normalized


def _source_root_label_from_path(path: str) -> str:
    return Path(str(path)).name or "Desktop Media"


def _update_history_label(state: AgentUpdateState | None) -> str:
    if state is None:
        return "最近升级：暂无记录"
    mapping = {
        "IDLE": "暂无记录",
        "INSTALLING": "安装中",
        "SUCCEEDED": "已成功",
        "ROLLED_BACK": "已回滚",
        "FAILED": "失败",
    }
    pieces = [mapping.get(str(state.status).strip().upper(), str(state.status).strip() or "未知状态")]
    version_hint = state.installed_version or state.target_version or state.current_version
    if version_hint:
        pieces.append(version_hint)
    if state.message:
        pieces.append(str(state.message))
    return "最近升级：" + " / ".join(pieces)


def _friendly_setup_error_message(exc: Exception) -> str:
    message = str(exc).strip() or "未知错误"
    lowered = message.lower()
    if "pairing code already used" in lowered or "pairing code expired" in lowered:
        return f"{message}\n\n这个接入码里的配对码已经失效，请回网页重新生成新的接入码后再试。"
    return message


class DesktopAgentUiController:
    def __init__(
        self,
        config_store: ConfigStore | None = None,
        *,
        autostart_manager: AutostartManager | None = None,
        pair_request: Callable[..., dict[str, str]] | None = None,
        setup_bootstrap_request: Callable[[str], DesktopAgentSetupBootstrap] | None = None,
        setup_complete_request: Callable[..., dict[str, object]] | None = None,
        updater: DesktopAgentUpdater | None = None,
        launch_command_factory: Callable[[], list[str]] = lambda: current_agent_command("tray"),
        process_launcher: Callable[..., subprocess.Popen[bytes] | subprocess.Popen[str]] = subprocess.Popen,
    ) -> None:
        self.config_store = config_store or ConfigStore()
        self.autostart_manager = autostart_manager or AutostartManager()
        self._pair_request = pair_request or self._default_pair_request
        self._setup_bootstrap_request = setup_bootstrap_request or fetch_desktop_agent_setup_bootstrap
        self._setup_complete_request = setup_complete_request or complete_desktop_agent_setup
        self.updater = updater or DesktopAgentUpdater()
        self.launch_command_factory = launch_command_factory
        self.process_launcher = process_launcher
        self.config_store.ensure_app_version()

    def _is_tray_instance_running(self) -> bool:
        probe_lock = SingleInstanceLock(self.config_store.tray_lock_path)
        if probe_lock.acquire():
            probe_lock.release()
            return False
        return True

    def _request_running_tray_restart(self, *, reason: str) -> bool:
        if not self._is_tray_instance_running():
            return False
        self.config_store.request_service_restart(reason=reason)
        return True

    def _default_pair_request(
        self,
        *,
        server_url: str,
        pairing_code: str,
        device_name: str,
        app_version: str,
    ) -> dict[str, str]:
        response = requests.post(
            f"{server_url.rstrip('/')}/api/desktop-agents/pair",
            json={
                "pairingCode": pairing_code,
                "deviceName": device_name,
                "platform": "windows",
                "appVersion": app_version,
            },
            timeout=30,
        )
        _raise_for_agent_response(response)
        return dict(response.json()["data"])

    def load_setup_bootstrap(self, setup_code: str) -> DesktopAgentSetupBootstrap:
        normalized_setup_code = str(setup_code).strip()
        if not normalized_setup_code:
            raise ValueError("setup_code is required")
        return self._setup_bootstrap_request(normalized_setup_code)

    def login_account(self, *, server_url: str, email: str, password: str) -> DesktopAgentAccountSession:
        return login_desktop_agent_account(server_url=server_url, email=email, password=password)

    def list_candidate_roots(self, project: DesktopAgentSetupProject) -> list[DesktopAgentSetupCandidateRoot]:
        return list(project.candidate_roots)

    def load_saved_root_dir(
        self,
        *,
        server_url: str,
        project_id: str,
        candidate_root: DesktopAgentSetupCandidateRoot,
    ) -> str | None:
        mapping = self.config_store.load_directory_mapping(
            server_url=server_url,
            project_id=project_id,
            root_key=candidate_root.root_key,
        )
        if mapping is not None:
            root_path = Path(mapping.root_dir)
            if root_path.exists() and root_path.is_dir():
                return str(root_path.resolve())
        saved = self.config_store.ensure_app_version()
        if (
            saved is not None
            and str(saved.server_url).strip().rstrip("/") == str(server_url).strip().rstrip("/")
            and str(saved.project_id).strip() == str(project_id).strip()
            and (saved.source_root_label or None) == candidate_root.source_root_label
        ):
            root_path = Path(saved.root_dir)
            if root_path.exists() and root_path.is_dir():
                return str(root_path.resolve())
        return None

    def setup_and_save(
        self,
        *,
        setup_code: str,
        project_id: str,
        candidate_root_key: str,
        root_dir: str,
        device_name: str,
        app_version: str,
        bootstrap: DesktopAgentSetupBootstrap | None = None,
    ) -> AgentConfig:
        loaded_bootstrap = bootstrap or self.load_setup_bootstrap(setup_code)
        normalized_project_id = _normalize_project_id(project_id)
        target_project = next((item for item in loaded_bootstrap.projects if item.project_id == normalized_project_id), None)
        if target_project is None:
            raise ValueError("selected project is not available in setup bootstrap")
        normalized_candidate_root_key = str(candidate_root_key).strip() or "."
        target_candidate = next((item for item in target_project.candidate_roots if item.root_key == normalized_candidate_root_key), None)
        if target_candidate is None:
            raise ValueError("selected logical root is not available in setup bootstrap")
        resolved_root_dir = str(Path(root_dir).expanduser().resolve())
        root_path = Path(resolved_root_dir)
        if not root_path.exists() or not root_path.is_dir():
            raise ValueError("root_dir must be an existing directory")
        normalized_device_name = str(device_name).strip()
        if not normalized_device_name:
            raise ValueError("device_name is required")
        pair_data = self._pair_request(
            server_url=loaded_bootstrap.server_url,
            pairing_code=loaded_bootstrap.pairing_code,
            device_name=normalized_device_name,
            app_version=str(app_version).strip() or APP_VERSION,
        )
        resolved_source_root_label = target_candidate.source_root_label
        self._setup_complete_request(
            setup_code=str(setup_code).strip(),
            server_url=loaded_bootstrap.server_url,
            agent_id=str(pair_data["agentId"]),
            project_id=normalized_project_id,
            source_root_label=resolved_source_root_label,
        )
        config = AgentConfig(
            server_url=loaded_bootstrap.server_url,
            agent_id=str(pair_data["agentId"]),
            agent_token=str(pair_data["agentToken"]),
            refresh_token=str(pair_data["refreshToken"]),
            project_id=normalized_project_id,
            root_dir=resolved_root_dir,
            device_name=normalized_device_name,
            app_version=str(app_version).strip() or APP_VERSION,
            source_root_label=resolved_source_root_label,
        )
        self.config_store.save_directory_mapping(
            server_url=loaded_bootstrap.server_url,
            project_id=normalized_project_id,
            root_key=target_candidate.root_key,
            root_dir=resolved_root_dir,
            source_root_label=resolved_source_root_label,
        )
        self.config_store.save(config)
        self._request_running_tray_restart(reason="setup_saved")
        return config

    def account_setup_and_save(
        self,
        *,
        account_session: DesktopAgentAccountSession,
        project_id: str,
        candidate_root_key: str,
        root_dir: str,
        device_name: str,
        app_version: str,
    ) -> AgentConfig:
        normalized_project_id = _normalize_project_id(project_id)
        target_project = next((item for item in account_session.bootstrap.projects if item.project_id == normalized_project_id), None)
        if target_project is None:
            raise ValueError("selected project is not available for this account")
        normalized_candidate_root_key = str(candidate_root_key).strip() or "."
        target_candidate = next((item for item in target_project.candidate_roots if item.root_key == normalized_candidate_root_key), None)
        if target_candidate is None:
            raise ValueError("selected logical root is not available for this project")
        resolved_root_dir = str(Path(root_dir).expanduser().resolve())
        root_path = Path(resolved_root_dir)
        if not root_path.exists() or not root_path.is_dir():
            raise ValueError("root_dir must be an existing directory")
        normalized_device_name = str(device_name).strip()
        if not normalized_device_name:
            raise ValueError("device_name is required")
        pair_data = account_pair_desktop_agent(
            account_session=account_session,
            device_name=normalized_device_name,
            app_version=str(app_version).strip() or APP_VERSION,
        )
        resolved_source_root_label = target_candidate.source_root_label
        complete_desktop_agent_account_setup(
            account_session=account_session,
            agent_id=str(pair_data["agentId"]),
            project_id=normalized_project_id,
            source_root_label=resolved_source_root_label,
        )
        config = AgentConfig(
            server_url=account_session.server_url,
            agent_id=str(pair_data["agentId"]),
            agent_token=str(pair_data["agentToken"]),
            refresh_token=str(pair_data["refreshToken"]),
            project_id=normalized_project_id,
            root_dir=resolved_root_dir,
            device_name=normalized_device_name,
            app_version=str(app_version).strip() or APP_VERSION,
            source_root_label=resolved_source_root_label,
        )
        self.config_store.save_directory_mapping(
            server_url=account_session.server_url,
            project_id=normalized_project_id,
            root_key=target_candidate.root_key,
            root_dir=resolved_root_dir,
            source_root_label=resolved_source_root_label,
        )
        self.config_store.save(config)
        self._request_running_tray_restart(reason="account_setup_saved")
        return config

    def _launch_detached(self, command: list[str]) -> None:
        creationflags = 0
        if os.name == "nt":
            creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
            creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        self.process_launcher(
            command,
            close_fds=(os.name != "nt"),
            creationflags=creationflags,
        )

    def load_saved_config(self) -> AgentConfig | None:
        return self.config_store.ensure_app_version()

    def is_tray_running(self) -> bool:
        return self._is_tray_instance_running()

    def build_saved_project_catalog(self) -> tuple[str, tuple[DesktopAgentSetupProject, ...], str | None] | None:
        saved = self.load_saved_config()
        if saved is None:
            return None
        source_root_label = str(saved.source_root_label or "").strip() or "默认根目录"
        candidate_root = DesktopAgentSetupCandidateRoot(
            root_key=source_root_label or ".",
            relative_path="",
            label=source_root_label,
            source_root_label=saved.source_root_label,
        )
        project = DesktopAgentSetupProject(
            project_id=saved.project_id,
            title="已保存项目",
            state="SAVED",
            project_root="",
            learning_object_root="",
            source_kind="SAVED_CONFIG",
            desktop_agent_id=saved.agent_id,
            source_root_label=saved.source_root_label,
            candidate_roots=(candidate_root,),
        )
        return (saved.server_url, (project,), saved.project_id)

    def load_update_state(self) -> AgentUpdateState | None:
        return self.config_store.load_update_state()

    def pair_and_save(
        self,
        *,
        server_url: str,
        pairing_code: str,
        project_id: str,
        root_dir: str,
        device_name: str,
        app_version: str,
        source_root_label: str | None,
    ) -> AgentConfig:
        normalized_server_url = str(server_url).strip().rstrip("/")
        normalized_pairing_code = str(pairing_code).strip().upper()
        normalized_project_id = _normalize_project_id(project_id)
        normalized_device_name = str(device_name).strip()
        resolved_root_dir = str(Path(root_dir).expanduser().resolve())
        if not normalized_server_url:
            raise ValueError("server_url is required")
        if not normalized_pairing_code:
            raise ValueError("pairing_code is required")
        if not normalized_device_name:
            raise ValueError("device_name is required")
        root_path = Path(resolved_root_dir)
        if not root_path.exists() or not root_path.is_dir():
            raise ValueError("root_dir must be an existing directory")

        data = self._pair_request(
            server_url=normalized_server_url,
            pairing_code=normalized_pairing_code,
            device_name=normalized_device_name,
            app_version=str(app_version).strip() or APP_VERSION,
        )
        config = AgentConfig(
            server_url=normalized_server_url,
            agent_id=str(data["agentId"]),
            agent_token=str(data["agentToken"]),
            refresh_token=str(data["refreshToken"]),
            project_id=normalized_project_id,
            root_dir=resolved_root_dir,
            device_name=normalized_device_name,
            app_version=str(app_version).strip() or APP_VERSION,
            source_root_label=str(source_root_label).strip() if source_root_label and str(source_root_label).strip() else root_path.name or "Desktop Media",
        )
        self.config_store.save(config)
        self._request_running_tray_restart(reason="pair_saved")
        return config

    def set_autostart(self, enabled: bool) -> None:
        if enabled:
            self.autostart_manager.enable(self.launch_command_factory())
            return
        self.autostart_manager.disable()

    def autostart_enabled(self) -> bool:
        return self.autostart_manager.is_enabled()

    def require_signed_updates(self) -> bool:
        return _env_enabled("PLM_AGENT_AUTO_UPDATE_REQUIRE_SIGNED")

    def auto_update_enabled(self) -> bool:
        return _env_enabled("PLM_AGENT_AUTO_UPDATE", default=True)

    def start_agent_process(self) -> None:
        if not self.config_store.exists():
            raise RuntimeError("desktop agent is not configured yet")
        self.config_store.ensure_app_version()
        if self._request_running_tray_restart(reason="manual_start_requested"):
            return
        self._launch_detached(self.launch_command_factory())

    def check_for_updates(self, *, server_url: str, current_version: str) -> DesktopAgentUpdateCheckResult:
        normalized_server_url = str(server_url).strip().rstrip("/")
        normalized_current_version = str(current_version).strip() or APP_VERSION
        if not normalized_server_url:
            raise ValueError("server_url is required")
        return self.updater.check_for_updates(
            server_url=normalized_server_url,
            current_version=normalized_current_version,
        )

    def install_update(
        self,
        *,
        server_url: str,
        current_version: str,
        current_pid: int | None = None,
    ) -> str:
        normalized_server_url = str(server_url).strip().rstrip("/")
        normalized_current_version = str(current_version).strip() or APP_VERSION
        if not normalized_server_url:
            raise ValueError("server_url is required")
        staging_dir = self.config_store.updates_dir
        prepared = self.updater.prepare_update(
            server_url=normalized_server_url,
            current_version=normalized_current_version,
            target_dir=staging_dir,
            require_signed=self.require_signed_updates(),
        )
        plan = self.updater.build_silent_install_plan(
            prepared,
            current_pid=os.getpid() if current_pid is None else current_pid,
            helper_dir=staging_dir,
            relaunch=True,
        )
        self._launch_detached(list(plan.command))
        return prepared.latest_version

    def can_rollback_last_update(self) -> bool:
        state = self.load_update_state()
        if state is None or not state.rollback_script_path or not state.backup_dir:
            return False
        return Path(state.rollback_script_path).exists() and Path(state.backup_dir).exists()

    def rollback_last_update(self, *, current_pid: int | None = None) -> str:
        state = self.load_update_state()
        if state is None or not state.rollback_script_path:
            raise RuntimeError("rollback is not available")
        rollback_script = Path(state.rollback_script_path)
        if not rollback_script.exists():
            raise RuntimeError("rollback script is missing")
        self._launch_detached(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(rollback_script),
                "-WaitPid",
                str(os.getpid() if current_pid is None else current_pid),
                "-Relaunch",
            ]
        )
        return state.current_version or state.installed_version or "previous version"


def _launch_ui_legacy() -> int:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except Exception as exc:  # pragma: no cover - depends on local GUI runtime
        raise RuntimeError("tkinter is required for desktop agent UI") from exc

    controller = DesktopAgentUiController()
    saved = controller.load_saved_config()

    root = tk.Tk()
    root.title("LearningPyramid Desktop Agent")
    root.geometry("860x620")
    root.minsize(860, 620)

    status_var = tk.StringVar(
        value=f"配置文件：{controller.config_store.path}" + (f" | 已配对：{saved.agent_id}" if saved else " | 尚未配对")
    )
    email_var = tk.StringVar()
    password_var = tk.StringVar()
    setup_code_var = tk.StringVar()
    server_url_var = tk.StringVar(value=saved.server_url if saved else _default_server_url())
    project_choice_var = tk.StringVar(value=saved.project_id if saved else "")
    project_id_var = tk.StringVar(value=saved.project_id if saved else "")
    directory_choice_var = tk.StringVar()
    root_dir_var = tk.StringVar(value=saved.root_dir if saved else "")
    device_name_var = tk.StringVar(value=saved.device_name if saved else _default_device_name())
    app_version_var = tk.StringVar(value=saved.app_version if saved else APP_VERSION)
    root_label_var = tk.StringVar(value=saved.source_root_label if saved and saved.source_root_label else "默认根目录")
    autostart_var = tk.BooleanVar(value=controller.autostart_enabled())
    update_status_var = tk.StringVar(
        value="更新：托盘会在后台自动保持最新" if controller.auto_update_enabled() else "更新：自动更新已关闭"
    )
    update_history_var = tk.StringVar(value=_update_history_label(controller.load_update_state()))
    bootstrap_state: list[DesktopAgentSetupBootstrap | None] = [None]
    account_session_state: list[DesktopAgentAccountSession | None] = [None]
    project_display_to_item: dict[str, DesktopAgentSetupProject] = {}
    directory_display_to_item: dict[str, DesktopAgentSetupCandidateRoot] = {}
    loading_state = [False]

    container = tk.Frame(root, padx=16, pady=16)
    container.pack(fill="both", expand=True)
    container.grid_columnconfigure(1, weight=1)

    def _set_status(message: str) -> None:
        status_var.set(message)

    def _refresh_update_history() -> None:
        update_history_var.set(_update_history_label(controller.load_update_state()))

    def _current_server_url() -> str:
        account_session = account_session_state[0]
        if account_session is not None:
            return account_session.server_url
        bootstrap = bootstrap_state[0]
        if bootstrap is not None:
            return bootstrap.server_url
        return server_url_var.get().strip().rstrip("/")

    def _selected_project() -> DesktopAgentSetupProject | None:
        return project_display_to_item.get(project_choice_var.get())

    def _selected_candidate_root() -> DesktopAgentSetupCandidateRoot | None:
        return directory_display_to_item.get(directory_choice_var.get())

    def _current_preferred_project_id() -> str:
        bootstrap = bootstrap_state[0]
        if bootstrap is not None:
            return bootstrap.preferred_project_id or (saved.project_id if saved else "")
        return saved.project_id if saved else ""

    def _has_live_catalog() -> bool:
        return bool(account_session_state[0] is not None or bootstrap_state[0] is not None)

    def _saved_config_available() -> bool:
        return controller.load_saved_config() is not None

    def _primary_action_label() -> str:
        if _has_live_catalog():
            return "保存并启动连接器"
        if _saved_config_available():
            return "启动已保存连接器"
        return "保存并启动连接器"

    def _update_control_states() -> None:
        login_button.configure(state="disabled" if loading_state[0] else "normal")
        load_setup_button.configure(state="disabled" if loading_state[0] else "normal")
        has_projects = bool(project_display_to_item)
        has_candidate_roots = bool(directory_display_to_item)
        has_selected_candidate = _selected_candidate_root() is not None
        has_selected_root_dir = bool(root_dir_var.get().strip())
        project_combo.configure(state="readonly" if has_projects and not loading_state[0] else "disabled")
        directory_combo.configure(state="readonly" if has_candidate_roots and not loading_state[0] else "disabled")
        browse_root_button.configure(state="normal" if has_selected_candidate and not loading_state[0] else "disabled")
        primary_action_button.configure(text=_primary_action_label())
        complete_setup_button.configure(
            state="normal"
            if (
                not loading_state[0]
                and (
                    (_has_live_catalog() and _selected_project() is not None and has_selected_candidate and has_selected_root_dir)
                    or _saved_config_available()
                )
            )
            else "disabled"
        )

    def _candidate_root_display(candidate_root: DesktopAgentSetupCandidateRoot) -> str:
        label = str(candidate_root.label).strip() or "默认根目录"
        relative_path = str(candidate_root.relative_path).strip()
        if not relative_path:
            return label
        return f"{label} ({relative_path})"

    def _find_preferred_candidate_display(
        self_project: DesktopAgentSetupProject,
        values: list[str],
    ) -> str:
        current_server_url = _current_server_url()
        for display in values:
            candidate = directory_display_to_item[display]
            if controller.load_saved_root_dir(
                server_url=current_server_url,
                project_id=self_project.project_id,
                candidate_root=candidate,
            ):
                return display
        if self_project.source_root_label:
            for display in values:
                candidate = directory_display_to_item[display]
                if candidate.source_root_label == self_project.source_root_label:
                    return display
        return values[0] if values else ""

    def _apply_project_catalog(
        *,
        server_url: str,
        projects: tuple[DesktopAgentSetupProject, ...],
        preferred_project_id: str | None,
        status_message: str,
    ) -> None:
        server_url_var.set(server_url)
        project_display_to_item.clear()
        project_values: list[str] = []
        for project in projects:
            display = f"{project.title} [{project.project_id}]"
            project_display_to_item[display] = project
            project_values.append(display)
        project_combo.configure(values=project_values)
        selected_display = next(
            (display for display, project in project_display_to_item.items() if project.project_id == (preferred_project_id or "")),
            project_values[0] if project_values else "",
        )
        project_choice_var.set(selected_display)
        if not project_values:
            project_id_var.set("")
            directory_display_to_item.clear()
            directory_combo.configure(values=())
            directory_choice_var.set("")
            root_dir_var.set("")
            root_label_var.set("")
            _set_status("当前账号没有可接入的项目。")
            _update_control_states()
            return
        _apply_project_selection()
        _set_status(status_message)
        _update_control_states()

    def _apply_candidate_roots(project: DesktopAgentSetupProject) -> None:
        directory_display_to_item.clear()
        values: list[str] = []
        for candidate_root in controller.list_candidate_roots(project):
            display = _candidate_root_display(candidate_root)
            if display in directory_display_to_item:
                display = f"{display} [{candidate_root.root_key}]"
            directory_display_to_item[display] = candidate_root
            values.append(display)
        has_candidates = bool(directory_display_to_item)
        directory_combo.configure(values=values)
        if not values:
            directory_choice_var.set("")
            root_dir_var.set("")
            root_label_var.set("")
            _set_status("请选择逻辑根，然后为它选择一次本地目录。")
            _update_control_states()
            return
        current = directory_choice_var.get().strip()
        if current not in directory_display_to_item:
            directory_choice_var.set(_find_preferred_candidate_display(project, values))
        _apply_directory_selection()
        _set_status("请选择项目、逻辑根和本地目录，然后保存并启动连接器。")
        _update_control_states()

    def _apply_directory_selection(*_args) -> None:
        project = _selected_project()
        candidate_root = _selected_candidate_root()
        if project is None or candidate_root is None:
            root_dir_var.set("")
            root_label_var.set("")
            _update_control_states()
            return
        root_label_var.set(candidate_root.source_root_label or "默认根目录")
        saved_root_dir = controller.load_saved_root_dir(
            server_url=_current_server_url(),
            project_id=project.project_id,
            candidate_root=candidate_root,
        )
        root_dir_var.set(saved_root_dir or "")
        if saved_root_dir:
            _set_status("已加载这台机器上保存过的本地目录映射。")
        else:
            _set_status("这个逻辑根还没有本地目录映射，请点击“选择目录”。")
        _update_control_states()

    def _apply_project_selection(*_args) -> None:
        project = _selected_project()
        if project is None:
            project_id_var.set("")
            directory_display_to_item.clear()
            directory_combo.configure(values=())
            directory_choice_var.set("")
            root_dir_var.set("")
            root_label_var.set("")
            _update_control_states()
            return
        project_id_var.set(project.project_id)
        _apply_candidate_roots(project)

    def _choose_root_dir() -> None:
        project = _selected_project()
        candidate_root = _selected_candidate_root()
        if project is None or candidate_root is None:
            messagebox.showerror("选择目录失败", "请先选择项目和逻辑根", parent=root)
            return
        initial_dir = root_dir_var.get().strip() or str(Path.home())
        selected_dir = filedialog.askdirectory(
            parent=root,
            title=f"为 {project.title} / {candidate_root.label} 选择本地目录",
            initialdir=initial_dir,
            mustexist=True,
        )
        if not selected_dir:
            return
        root_dir_var.set(str(Path(selected_dir).expanduser().resolve()))
        _set_status("已选择本地目录。完成接入后，这台机器会记住这个映射。")
        _update_control_states()

    def _login_account() -> None:
        normalized_server_url = server_url_var.get().strip().rstrip("/")
        normalized_email = email_var.get().strip()
        normalized_password = password_var.get()
        if not normalized_server_url:
            messagebox.showerror("登录失败", "服务器地址不可为空", parent=root)
            return
        if not normalized_email:
            messagebox.showerror("登录失败", "请输入账号邮箱", parent=root)
            return
        if not normalized_password:
            messagebox.showerror("登录失败", "请输入账号密码", parent=root)
            return
        loading_state[0] = True
        account_session_state[0] = None
        bootstrap_state[0] = None
        _set_status("正在登录账号并加载项目列表。")
        _update_control_states()

        def _worker() -> None:
            try:
                account_session = controller.login_account(
                    server_url=normalized_server_url,
                    email=normalized_email,
                    password=normalized_password,
                )
            except Exception as exc:
                root.after(0, lambda: _finish_login_account(None, exc))
                return
            root.after(0, lambda: _finish_login_account(account_session, None))

        threading.Thread(target=_worker, name="desktop-agent-account-login", daemon=True).start()

    def _finish_login_account(account_session: DesktopAgentAccountSession | None, error: Exception | None) -> None:
        loading_state[0] = False
        if error is not None:
            _update_control_states()
            messagebox.showerror("登录失败", str(error), parent=root)
            return
        assert account_session is not None
        account_session_state[0] = account_session
        setup_code_var.set("")
        password_var.set("")
        _apply_project_catalog(
            server_url=account_session.server_url,
            projects=account_session.bootstrap.projects,
            preferred_project_id=_current_preferred_project_id(),
            status_message="账号登录成功。请选择项目、逻辑根和本地目录，然后保存并启动连接器。",
        )

    def _load_setup_code() -> None:
        normalized_setup_code = setup_code_var.get().strip()
        if not normalized_setup_code:
            messagebox.showerror("加载接入码失败", "请输入接入码", parent=root)
            return
        loading_state[0] = True
        bootstrap_state[0] = None
        account_session_state[0] = None
        _set_status("正在加载接入码，这一步会在后台继续。")
        _update_control_states()

        def _worker() -> None:
            try:
                bootstrap = controller.load_setup_bootstrap(normalized_setup_code)
            except Exception as exc:
                root.after(0, lambda: _finish_load_setup_code(None, exc))
                return
            root.after(0, lambda: _finish_load_setup_code(bootstrap, None))

        threading.Thread(target=_worker, name="desktop-agent-setup-bootstrap", daemon=True).start()

    def _finish_load_setup_code(bootstrap: DesktopAgentSetupBootstrap | None, error: Exception | None) -> None:
        loading_state[0] = False
        if error is not None:
            _update_control_states()
            messagebox.showerror("加载接入码失败", str(error), parent=root)
            return
        assert bootstrap is not None
        bootstrap_state[0] = bootstrap
        _apply_project_catalog(
            server_url=bootstrap.server_url,
            projects=bootstrap.projects,
            preferred_project_id=bootstrap.preferred_project_id or (saved.project_id if saved else ""),
            status_message="接入码已加载。请选择项目、逻辑根和本地目录，然后保存并启动连接器。",
        )

    def _save_autostart() -> None:
        try:
            controller.set_autostart(bool(autostart_var.get()))
            _set_status("已更新开机自启设置。")
        except Exception as exc:
            messagebox.showerror("更新失败", str(exc), parent=root)
            autostart_var.set(controller.autostart_enabled())

    def _save_and_start() -> None:
        try:
            config: AgentConfig | None = None
            account_session = account_session_state[0]
            bootstrap = bootstrap_state[0]
            used_live_setup = bool(account_session is not None or bootstrap is not None)
            if account_session is not None or bootstrap is not None:
                if not project_id_var.get().strip():
                    raise RuntimeError("请选择项目")
                candidate_root = _selected_candidate_root()
                if candidate_root is None:
                    raise RuntimeError("请选择逻辑根")
                if not root_dir_var.get().strip():
                    raise RuntimeError("请先选择本地目录")
            if account_session is not None:
                config = controller.account_setup_and_save(
                    account_session=account_session,
                    project_id=project_id_var.get(),
                    candidate_root_key=candidate_root.root_key,
                    root_dir=root_dir_var.get(),
                    device_name=device_name_var.get(),
                    app_version=app_version_var.get(),
                )
            elif bootstrap is not None:
                config = controller.setup_and_save(
                    setup_code=setup_code_var.get(),
                    bootstrap=bootstrap,
                    project_id=project_id_var.get(),
                    candidate_root_key=candidate_root.root_key,
                    root_dir=root_dir_var.get(),
                    device_name=device_name_var.get(),
                    app_version=app_version_var.get(),
                )
            else:
                config = controller.load_saved_config()
                if config is None:
                    raise RuntimeError("请先登录账号，或加载接入码完成一次接入")
            assert config is not None
            app_version_var.set(config.app_version)
            root_label_var.set(config.source_root_label or "默认根目录")
            if autostart_var.get():
                controller.set_autostart(True)
            if used_live_setup:
                setup_code_var.set("")
                password_var.set("")
            controller.start_agent_process()
            if used_live_setup:
                _set_status(f"已保存配置并在后台启动托盘连接器：{config.agent_id}")
            else:
                _set_status(f"已在后台启动已保存的托盘连接器：{config.agent_id}")
        except Exception as exc:
            if account_session_state[0] is not None or bootstrap_state[0] is not None:
                messagebox.showerror("启动失败", _friendly_setup_error_message(exc), parent=root)
            else:
                messagebox.showerror("启动失败", str(exc), parent=root)

    def _row(row_index: int, label: str, variable: tk.StringVar) -> tk.Entry:
        tk.Label(container, text=label, anchor="w").grid(row=row_index, column=0, sticky="w", pady=6)
        entry = tk.Entry(container, textvariable=variable)
        entry.grid(row=row_index, column=1, sticky="ew", pady=6)
        return entry

    _row(0, "服务器", server_url_var).configure(state="readonly")
    _row(1, "账号邮箱", email_var)
    password_entry = _row(2, "账号密码", password_var)
    password_entry.configure(show="*")
    login_button = tk.Button(container, text="登录账号", command=_login_account)
    login_button.grid(row=2, column=2, sticky="ew", padx=(8, 0), pady=6)

    tk.Label(container, text="可选接入码", anchor="w").grid(row=3, column=0, sticky="w", pady=6)
    setup_code_entry = tk.Entry(container, textvariable=setup_code_var)
    setup_code_entry.grid(row=3, column=1, sticky="ew", pady=6)
    load_setup_button = tk.Button(container, text="加载接入码", command=_load_setup_code)
    load_setup_button.grid(row=3, column=2, sticky="ew", padx=(8, 0), pady=6)

    tk.Label(container, text="项目", anchor="w").grid(row=4, column=0, sticky="w", pady=6)
    project_combo = ttk.Combobox(container, textvariable=project_choice_var, state="readonly")
    project_combo.grid(row=4, column=1, sticky="ew", pady=6)
    project_combo.bind("<<ComboboxSelected>>", _apply_project_selection)

    tk.Label(container, text="逻辑根", anchor="w").grid(row=5, column=0, sticky="w", pady=6)
    directory_combo = ttk.Combobox(container, textvariable=directory_choice_var, state="readonly")
    directory_combo.grid(row=5, column=1, sticky="ew", pady=6)
    directory_combo.bind("<<ComboboxSelected>>", _apply_directory_selection)

    _row(6, "本地目录", root_dir_var).configure(state="readonly")
    browse_root_button = tk.Button(container, text="选择目录", command=_choose_root_dir)
    browse_root_button.grid(row=6, column=2, sticky="ew", padx=(8, 0), pady=6)
    _row(7, "设备名称", device_name_var)
    _row(8, "应用版本", app_version_var)
    _row(9, "同步标签", root_label_var).configure(state="readonly")

    tk.Checkbutton(container, text="Windows 登录后自动启动", variable=autostart_var, command=_save_autostart).grid(
        row=10, column=0, columnspan=3, sticky="w", pady=(12, 6)
    )

    action_row = tk.Frame(container)
    action_row.grid(row=11, column=0, columnspan=3, sticky="ew", pady=(12, 6))
    primary_action_button = tk.Button(action_row, text="保存并启动连接器", command=_save_and_start, width=18)
    primary_action_button.pack(side="left")
    complete_setup_button = primary_action_button

    tk.Label(
        container,
        text="主流程：1. 登录账号或加载接入码  2. 选择项目和逻辑根  3. 选择一次本地目录  4. 点击“保存并启动连接器”。如果下方已经显示已保存项目，可直接启动，无需重新登录。",
        anchor="w",
        justify="left",
        fg="#555555",
    ).grid(row=12, column=0, columnspan=3, sticky="w", pady=(12, 4))

    tk.Label(
        container,
        textvariable=status_var,
        anchor="w",
        justify="left",
        wraplength=760,
        fg="#1f2937",
    ).grid(row=13, column=0, columnspan=3, sticky="ew", pady=(8, 0))
    tk.Label(
        container,
        textvariable=update_status_var,
        anchor="w",
        justify="left",
        wraplength=760,
        fg="#1f2937",
    ).grid(row=14, column=0, columnspan=3, sticky="ew", pady=(6, 0))
    tk.Label(
        container,
        textvariable=update_history_var,
        anchor="w",
        justify="left",
        wraplength=760,
        fg="#1f2937",
    ).grid(row=15, column=0, columnspan=3, sticky="ew", pady=(6, 0))

    _refresh_update_history()
    project_combo.configure(values=())
    directory_combo.configure(values=())
    if saved:
        server_url_var.set(saved.server_url)
        root_label_var.set(saved.source_root_label or "默认根目录")
        saved_catalog = controller.build_saved_project_catalog()
        if saved_catalog is not None:
            catalog_server_url, saved_projects, preferred_project_id = saved_catalog
            _apply_project_catalog(
                server_url=catalog_server_url,
                projects=saved_projects,
                preferred_project_id=preferred_project_id,
                status_message=f"已加载保存配置：{saved.agent_id}。可直接启动连接器；如需更换项目或目录，再登录账号。",
            )
    else:
        server_url_var.set(_default_server_url())
    _update_control_states()
    email_var.set("")
    password_var.set("")
    root.focus_set()
    root.mainloop()
    return 0


class _MinimalDesktopAgentUi:
    def __init__(self, tk, filedialog, messagebox, ttk) -> None:
        self.tk = tk
        self.filedialog = filedialog
        self.messagebox = messagebox
        self.ttk = ttk

        self.controller = DesktopAgentUiController()
        self.saved_state: list[AgentConfig | None] = [self.controller.load_saved_config()]
        self.bootstrap_state: list[DesktopAgentSetupBootstrap | None] = [None]
        self.account_session_state: list[DesktopAgentAccountSession | None] = [None]
        self.loading_state = [False]

        self.project_display_to_item: dict[str, DesktopAgentSetupProject] = {}
        self.directory_display_to_item: dict[str, DesktopAgentSetupCandidateRoot] = {}
        self.widget_refs: dict[str, object] = {}
        self.setup_dialog: object | None = None

        self.root = tk.Tk()
        self.root.title("LearningPyramid Desktop Agent")
        self.root.geometry("760x560")
        self.root.minsize(720, 520)
        self.root.configure(bg="#edf2f7")

        self._configure_style()

        saved = self.saved_state[0]
        self.status_var = tk.StringVar(
            value=(
                f"配置文件：{self.controller.config_store.path}"
                + (f" | 已保存连接器：{saved.agent_id}" if saved else " | 还没有保存的连接器")
            )
        )
        self.update_status_var = tk.StringVar(
            value="更新：托盘会在后台自动保持最新" if self.controller.auto_update_enabled() else "更新：自动更新已关闭"
        )
        self.update_history_var = tk.StringVar(value=_update_history_label(self.controller.load_update_state()))
        self.saved_badge_var = tk.StringVar()
        self.saved_server_var = tk.StringVar()
        self.saved_project_var = tk.StringVar()
        self.saved_root_label_var = tk.StringVar()
        self.saved_root_dir_var = tk.StringVar()
        self.saved_device_var = tk.StringVar()
        self.saved_version_var = tk.StringVar()

        self.email_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.setup_code_var = tk.StringVar()
        self.server_url_var = tk.StringVar(value=saved.server_url if saved else _default_server_url())
        self.project_choice_var = tk.StringVar(value=saved.project_id if saved else "")
        self.project_id_var = tk.StringVar(value=saved.project_id if saved else "")
        self.directory_choice_var = tk.StringVar()
        self.root_dir_var = tk.StringVar(value=saved.root_dir if saved else "")
        self.device_name_var = tk.StringVar(value=saved.device_name if saved else _default_device_name())
        self.app_version_var = tk.StringVar(value=saved.app_version if saved else APP_VERSION)
        self.root_label_var = tk.StringVar(value=saved.source_root_label if saved and saved.source_root_label else "默认根目录")
        self.autostart_var = tk.BooleanVar(value=self.controller.autostart_enabled())

        self._build_main_window()
        self._refresh_saved_summary()
        self._refresh_update_history()
        self._update_control_states()
        self.root.focus_set()
        if saved is None:
            self.root.after(80, self._open_setup_dialog)

    def run(self) -> int:
        self.root.mainloop()
        return 0

    def _configure_style(self) -> None:
        style = self.ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("App.TFrame", background="#edf2f7")
        style.configure("Card.TFrame", background="#ffffff", relief="flat")
        style.configure("CardTitle.TLabel", background="#ffffff", foreground="#0f172a", font=("Segoe UI", 18, "bold"))
        style.configure("CardSub.TLabel", background="#ffffff", foreground="#475569", font=("Segoe UI", 10))
        style.configure("Section.TLabel", background="#ffffff", foreground="#0f172a", font=("Segoe UI", 11, "bold"))
        style.configure("MetaLabel.TLabel", background="#ffffff", foreground="#64748b", font=("Segoe UI", 9))
        style.configure("Value.TLabel", background="#ffffff", foreground="#0f172a", font=("Segoe UI", 10))
        style.configure("Hint.TLabel", background="#edf2f7", foreground="#475569", font=("Segoe UI", 9))
        style.configure("Primary.TButton", padding=(16, 10), font=("Segoe UI", 10, "bold"))
        style.configure("Secondary.TButton", padding=(14, 10), font=("Segoe UI", 10))
        style.configure("Dialog.TLabelframe", background="#ffffff")
        style.configure("Dialog.TLabelframe.Label", background="#ffffff", foreground="#0f172a", font=("Segoe UI", 10, "bold"))

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)

    def _refresh_update_history(self) -> None:
        self.update_history_var.set(_update_history_label(self.controller.load_update_state()))

    def _current_server_url(self) -> str:
        account_session = self.account_session_state[0]
        if account_session is not None:
            return account_session.server_url
        bootstrap = self.bootstrap_state[0]
        if bootstrap is not None:
            return bootstrap.server_url
        return self.server_url_var.get().strip().rstrip("/")

    def _selected_project(self) -> DesktopAgentSetupProject | None:
        return self.project_display_to_item.get(self.project_choice_var.get())

    def _selected_candidate_root(self) -> DesktopAgentSetupCandidateRoot | None:
        return self.directory_display_to_item.get(self.directory_choice_var.get())

    def _has_live_catalog(self) -> bool:
        return bool(self.account_session_state[0] is not None or self.bootstrap_state[0] is not None)

    def _saved_config_available(self) -> bool:
        return self.controller.load_saved_config() is not None

    def _primary_action_label(self) -> str:
        return "启动连接器"

    def _dialog_parent(self):
        dialog = self.setup_dialog
        if dialog is not None and bool(dialog.winfo_exists()):
            return dialog
        return self.root

    def _build_main_window(self) -> None:
        shell = self.ttk.Frame(self.root, style="App.TFrame", padding=20)
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=1)

        hero = self.ttk.Frame(shell, style="Card.TFrame", padding=24)
        hero.grid(row=0, column=0, sticky="ew")
        hero.columnconfigure(0, weight=1)
        self.ttk.Label(hero, text="Desktop Agent", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.ttk.Label(
            hero,
            text="主界面只负责启动。登录、换账号、改项目和逻辑根都放到单独接入窗口里。",
            style="CardSub.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))
        badge = self.ttk.Label(hero, textvariable=self.saved_badge_var, style="Section.TLabel")
        badge.grid(row=0, column=1, rowspan=2, sticky="e")
        self.widget_refs["saved_badge"] = badge

        summary = self.ttk.Frame(shell, style="Card.TFrame", padding=24)
        summary.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        summary.columnconfigure(1, weight=1)
        summary.columnconfigure(3, weight=1)
        self.ttk.Label(summary, text="已保存配置", style="Section.TLabel").grid(row=0, column=0, columnspan=4, sticky="w")

        def add_summary_row(row_index: int, left_label: str, left_var, right_label: str, right_var) -> None:
            self.ttk.Label(summary, text=left_label, style="MetaLabel.TLabel").grid(row=row_index, column=0, sticky="w", pady=(14, 0))
            self.ttk.Label(summary, textvariable=left_var, style="Value.TLabel").grid(
                row=row_index, column=1, sticky="ew", pady=(14, 0), padx=(0, 20)
            )
            self.ttk.Label(summary, text=right_label, style="MetaLabel.TLabel").grid(row=row_index, column=2, sticky="w", pady=(14, 0))
            self.ttk.Label(summary, textvariable=right_var, style="Value.TLabel").grid(row=row_index, column=3, sticky="ew", pady=(14, 0))

        add_summary_row(1, "服务器", self.saved_server_var, "项目", self.saved_project_var)
        add_summary_row(2, "逻辑根", self.saved_root_label_var, "设备", self.saved_device_var)
        add_summary_row(3, "本地目录", self.saved_root_dir_var, "版本", self.saved_version_var)

        action_card = self.ttk.Frame(shell, style="Card.TFrame", padding=24)
        action_card.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        action_card.columnconfigure(0, weight=1)
        self.ttk.Label(action_card, text="启动控制", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.ttk.Label(
            action_card,
            text="正常启动不需要重新登录。只要之前保存过连接器，这里一键启动即可。",
            style="CardSub.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(6, 14))

        actions = self.ttk.Frame(action_card, style="Card.TFrame")
        actions.grid(row=2, column=0, sticky="ew")
        start_button = self.ttk.Button(actions, text="启动连接器", style="Primary.TButton", command=self._start_saved_connector)
        start_button.pack(side="left")
        setup_button = self.ttk.Button(actions, text="登录并接入", style="Secondary.TButton", command=self._open_setup_dialog)
        setup_button.pack(side="left", padx=(12, 0))
        log_button = self.ttk.Button(actions, text="打开日志", style="Secondary.TButton", command=self._open_logs)
        log_button.pack(side="left", padx=(12, 0))
        self.widget_refs["main_start_button"] = start_button
        self.widget_refs["main_setup_button"] = setup_button

        options = self.ttk.Frame(action_card, style="Card.TFrame")
        options.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        self.ttk.Checkbutton(
            options,
            text="Windows 登录后自动启动",
            variable=self.autostart_var,
            command=self._save_autostart,
        ).pack(side="left")
        self.ttk.Label(
            options,
            text="密码不会持久化保存，但已保存的连接器 token 会保留，后续启动无需重登。",
            style="Hint.TLabel",
        ).pack(side="right")

        footer = self.ttk.Frame(shell, style="App.TFrame")
        footer.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        self.ttk.Label(footer, textvariable=self.status_var, style="Hint.TLabel", wraplength=680, justify="left").pack(anchor="w")
        self.ttk.Label(footer, textvariable=self.update_status_var, style="Hint.TLabel", wraplength=680, justify="left").pack(anchor="w", pady=(8, 0))
        self.ttk.Label(footer, textvariable=self.update_history_var, style="Hint.TLabel", wraplength=680, justify="left").pack(anchor="w", pady=(6, 0))

    def _refresh_saved_summary(self) -> None:
        saved = self.controller.load_saved_config()
        self.saved_state[0] = saved
        if saved is None:
            self.saved_badge_var.set("尚未接入")
            self.saved_server_var.set(_default_server_url())
            self.saved_project_var.set("还没有保存的项目")
            self.saved_root_label_var.set("-")
            self.saved_root_dir_var.set("请先登录并完成一次接入")
            self.saved_device_var.set(_default_device_name())
            self.saved_version_var.set(APP_VERSION)
            return
        self.saved_badge_var.set("已保存，可直接启动")
        self.saved_server_var.set(saved.server_url)
        self.saved_project_var.set(saved.project_id)
        self.saved_root_label_var.set(saved.source_root_label or "默认根目录")
        self.saved_root_dir_var.set(saved.root_dir)
        self.saved_device_var.set(saved.device_name)
        self.saved_version_var.set(saved.app_version)

    def _candidate_root_display(self, candidate_root: DesktopAgentSetupCandidateRoot) -> str:
        label = str(candidate_root.label).strip() or "默认根目录"
        relative_path = str(candidate_root.relative_path).strip()
        if not relative_path:
            return label
        return f"{label} ({relative_path})"

    def _find_preferred_candidate_display(
        self,
        project: DesktopAgentSetupProject,
        values: list[str],
    ) -> str:
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

    def _update_control_states(self) -> None:
        start_button = self.widget_refs.get("main_start_button")
        if start_button is not None:
            start_button.configure(
                text=self._primary_action_label(),
                state="normal" if (not self.loading_state[0] and self._saved_config_available()) else "disabled",
            )
        setup_button = self.widget_refs.get("main_setup_button")
        if setup_button is not None:
            setup_button.configure(
                text="更换账号或重新接入" if self._saved_config_available() else "登录并接入",
                state="disabled" if self.loading_state[0] else "normal",
            )

        login_button = self.widget_refs.get("login_button")
        if login_button is not None:
            login_button.configure(state="disabled" if self.loading_state[0] else "normal")
        load_setup_button = self.widget_refs.get("load_setup_button")
        if load_setup_button is not None:
            load_setup_button.configure(state="disabled" if self.loading_state[0] else "normal")

        has_projects = bool(self.project_display_to_item)
        has_candidate_roots = bool(self.directory_display_to_item)
        has_selected_candidate = self._selected_candidate_root() is not None
        has_selected_root_dir = bool(self.root_dir_var.get().strip())

        project_combo = self.widget_refs.get("project_combo")
        if project_combo is not None:
            project_combo.configure(state="readonly" if has_projects and not self.loading_state[0] else "disabled")
        directory_combo = self.widget_refs.get("directory_combo")
        if directory_combo is not None:
            directory_combo.configure(state="readonly" if has_candidate_roots and not self.loading_state[0] else "disabled")
        browse_button = self.widget_refs.get("browse_root_button")
        if browse_button is not None:
            browse_button.configure(state="normal" if has_selected_candidate and not self.loading_state[0] else "disabled")
        setup_primary = self.widget_refs.get("setup_primary_button")
        if setup_primary is not None:
            setup_primary.configure(
                state=(
                    "normal"
                    if (
                        not self.loading_state[0]
                        and self._has_live_catalog()
                        and self._selected_project() is not None
                        and has_selected_candidate
                        and has_selected_root_dir
                    )
                    else "disabled"
                )
            )

    def _apply_project_catalog(
        self,
        *,
        server_url: str,
        projects: tuple[DesktopAgentSetupProject, ...],
        preferred_project_id: str | None,
        status_message: str,
    ) -> None:
        self.server_url_var.set(server_url)
        self.project_display_to_item.clear()
        project_values: list[str] = []
        for project in projects:
            display = f"{project.title} [{project.project_id}]"
            self.project_display_to_item[display] = project
            project_values.append(display)
        project_combo = self.widget_refs.get("project_combo")
        if project_combo is not None:
            project_combo.configure(values=project_values)
        selected_display = next(
            (display for display, project in self.project_display_to_item.items() if project.project_id == (preferred_project_id or "")),
            project_values[0] if project_values else "",
        )
        self.project_choice_var.set(selected_display)
        if not project_values:
            self.project_id_var.set("")
            self.directory_display_to_item.clear()
            directory_combo = self.widget_refs.get("directory_combo")
            if directory_combo is not None:
                directory_combo.configure(values=())
            self.directory_choice_var.set("")
            self.root_dir_var.set("")
            self.root_label_var.set("")
            self._set_status("当前账号没有可接入的项目。")
            self._update_control_states()
            return
        self._apply_project_selection()
        self._set_status(status_message)
        self._update_control_states()

    def _apply_candidate_roots(self, project: DesktopAgentSetupProject) -> None:
        self.directory_display_to_item.clear()
        values: list[str] = []
        for candidate_root in self.controller.list_candidate_roots(project):
            display = self._candidate_root_display(candidate_root)
            if display in self.directory_display_to_item:
                display = f"{display} [{candidate_root.root_key}]"
            self.directory_display_to_item[display] = candidate_root
            values.append(display)
        directory_combo = self.widget_refs.get("directory_combo")
        if directory_combo is not None:
            directory_combo.configure(values=values)
        if not values:
            self.directory_choice_var.set("")
            self.root_dir_var.set("")
            self.root_label_var.set("")
            self._set_status("这个项目没有可用逻辑根。")
            self._update_control_states()
            return
        current = self.directory_choice_var.get().strip()
        if current not in self.directory_display_to_item:
            self.directory_choice_var.set(self._find_preferred_candidate_display(project, values))
        self._apply_directory_selection()
        self._set_status("请选择逻辑根和本地目录，然后保存并启动连接器。")
        self._update_control_states()

    def _apply_project_selection(self, *_args) -> None:
        project = self._selected_project()
        if project is None:
            self.project_id_var.set("")
            self.directory_display_to_item.clear()
            directory_combo = self.widget_refs.get("directory_combo")
            if directory_combo is not None:
                directory_combo.configure(values=())
            self.directory_choice_var.set("")
            self.root_dir_var.set("")
            self.root_label_var.set("")
            self._update_control_states()
            return
        self.project_id_var.set(project.project_id)
        self._apply_candidate_roots(project)

    def _apply_directory_selection(self, *_args) -> None:
        project = self._selected_project()
        candidate_root = self._selected_candidate_root()
        if project is None or candidate_root is None:
            self.root_dir_var.set("")
            self.root_label_var.set("")
            self._update_control_states()
            return
        self.root_label_var.set(candidate_root.source_root_label or "默认根目录")
        saved_root_dir = self.controller.load_saved_root_dir(
            server_url=self._current_server_url(),
            project_id=project.project_id,
            candidate_root=candidate_root,
        )
        self.root_dir_var.set(saved_root_dir or "")
        if saved_root_dir:
            self._set_status("已加载这台机器上之前保存过的目录映射。")
        else:
            self._set_status("请为这个逻辑根选择一次本地目录。")
        self._update_control_states()

    def _choose_root_dir(self) -> None:
        project = self._selected_project()
        candidate_root = self._selected_candidate_root()
        if project is None or candidate_root is None:
            self.messagebox.showerror("选择目录失败", "请先选择项目和逻辑根", parent=self._dialog_parent())
            return
        initial_dir = self.root_dir_var.get().strip() or str(Path.home())
        selected_dir = self.filedialog.askdirectory(
            parent=self._dialog_parent(),
            title=f"为 {project.title} / {candidate_root.label} 选择本地目录",
            initialdir=initial_dir,
            mustexist=True,
        )
        if not selected_dir:
            return
        self.root_dir_var.set(str(Path(selected_dir).expanduser().resolve()))
        self._set_status("已选择本地目录。保存后，这台机器会记住这个映射。")
        self._update_control_states()

    def _open_setup_dialog(self) -> None:
        if self.setup_dialog is not None and bool(self.setup_dialog.winfo_exists()):
            self.setup_dialog.deiconify()
            self.setup_dialog.lift()
            self.setup_dialog.focus_force()
            return

        dialog = self.tk.Toplevel(self.root)
        dialog.title("登录并接入")
        dialog.geometry("700x620")
        dialog.minsize(660, 580)
        dialog.configure(bg="#edf2f7")
        dialog.transient(self.root)
        dialog.protocol("WM_DELETE_WINDOW", self._close_setup_dialog)
        self.setup_dialog = dialog

        shell = self.ttk.Frame(dialog, style="App.TFrame", padding=20)
        shell.pack(fill="both", expand=True)
        shell.columnconfigure(0, weight=1)

        hero = self.ttk.Frame(shell, style="Card.TFrame", padding=20)
        hero.grid(row=0, column=0, sticky="ew")
        hero.columnconfigure(0, weight=1)
        self.ttk.Label(hero, text="登录并接入连接器", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.ttk.Label(
            hero,
            text="这里只做登录、换账号、选择项目和逻辑根。保存后回到主界面直接一键启动。",
            style="CardSub.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

        form = self.ttk.Frame(shell, style="Card.TFrame", padding=20)
        form.grid(row=1, column=0, sticky="nsew", pady=(16, 0))
        form.columnconfigure(1, weight=1)

        self.ttk.Label(form, text="服务器", style="MetaLabel.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        server_entry = self.ttk.Entry(form, textvariable=self.server_url_var)
        server_entry.grid(row=0, column=1, sticky="ew", pady=(0, 6))

        self.ttk.Label(form, text="账号邮箱", style="MetaLabel.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        email_entry = self.ttk.Entry(form, textvariable=self.email_var)
        email_entry.grid(row=1, column=1, sticky="ew", pady=6)

        self.ttk.Label(form, text="账号密码", style="MetaLabel.TLabel").grid(row=2, column=0, sticky="w", pady=6)
        password_entry = self.ttk.Entry(form, textvariable=self.password_var, show="*")
        password_entry.grid(row=2, column=1, sticky="ew", pady=6)
        login_button = self.ttk.Button(form, text="登录账号", style="Secondary.TButton", command=self._login_account)
        login_button.grid(row=2, column=2, sticky="ew", padx=(12, 0), pady=6)

        self.ttk.Label(form, text="可选接入码", style="MetaLabel.TLabel").grid(row=3, column=0, sticky="w", pady=6)
        setup_code_entry = self.ttk.Entry(form, textvariable=self.setup_code_var)
        setup_code_entry.grid(row=3, column=1, sticky="ew", pady=6)
        load_setup_button = self.ttk.Button(form, text="加载接入码", style="Secondary.TButton", command=self._load_setup_code)
        load_setup_button.grid(row=3, column=2, sticky="ew", padx=(12, 0), pady=6)

        self.ttk.Label(form, text="项目", style="MetaLabel.TLabel").grid(row=4, column=0, sticky="w", pady=(14, 6))
        project_combo = self.ttk.Combobox(form, textvariable=self.project_choice_var, state="disabled")
        project_combo.grid(row=4, column=1, columnspan=2, sticky="ew", pady=(14, 6))
        project_combo.bind("<<ComboboxSelected>>", self._apply_project_selection)

        self.ttk.Label(form, text="逻辑根", style="MetaLabel.TLabel").grid(row=5, column=0, sticky="w", pady=6)
        directory_combo = self.ttk.Combobox(form, textvariable=self.directory_choice_var, state="disabled")
        directory_combo.grid(row=5, column=1, columnspan=2, sticky="ew", pady=6)
        directory_combo.bind("<<ComboboxSelected>>", self._apply_directory_selection)

        self.ttk.Label(form, text="本地目录", style="MetaLabel.TLabel").grid(row=6, column=0, sticky="w", pady=6)
        root_dir_entry = self.ttk.Entry(form, textvariable=self.root_dir_var, state="readonly")
        root_dir_entry.grid(row=6, column=1, sticky="ew", pady=6)
        browse_button = self.ttk.Button(form, text="选择目录", style="Secondary.TButton", command=self._choose_root_dir)
        browse_button.grid(row=6, column=2, sticky="ew", padx=(12, 0), pady=6)

        self.ttk.Label(form, text="设备名称", style="MetaLabel.TLabel").grid(row=7, column=0, sticky="w", pady=6)
        device_name_entry = self.ttk.Entry(form, textvariable=self.device_name_var)
        device_name_entry.grid(row=7, column=1, columnspan=2, sticky="ew", pady=6)

        self.ttk.Label(form, text="同步标签", style="MetaLabel.TLabel").grid(row=8, column=0, sticky="w", pady=6)
        root_label_entry = self.ttk.Entry(form, textvariable=self.root_label_var, state="readonly")
        root_label_entry.grid(row=8, column=1, columnspan=2, sticky="ew", pady=6)

        actions = self.ttk.Frame(shell, style="App.TFrame")
        actions.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        setup_primary_button = self.ttk.Button(actions, text="保存并启动连接器", style="Primary.TButton", command=self._save_setup_and_start)
        setup_primary_button.pack(side="left")
        cancel_button = self.ttk.Button(actions, text="取消", style="Secondary.TButton", command=self._close_setup_dialog)
        cancel_button.pack(side="left", padx=(12, 0))

        self.widget_refs["login_button"] = login_button
        self.widget_refs["load_setup_button"] = load_setup_button
        self.widget_refs["project_combo"] = project_combo
        self.widget_refs["directory_combo"] = directory_combo
        self.widget_refs["browse_root_button"] = browse_button
        self.widget_refs["setup_primary_button"] = setup_primary_button

        self.ttk.Label(
            shell,
            text="登录账号后可拉取项目列表；接入码只适合临时配对或首次接入。",
            style="Hint.TLabel",
            wraplength=620,
            justify="left",
        ).grid(row=3, column=0, sticky="w", pady=(14, 0))

        email_entry.focus_set()
        if self.account_session_state[0] is not None:
            account_session = self.account_session_state[0]
            self._apply_project_catalog(
                server_url=account_session.server_url,
                projects=account_session.bootstrap.projects,
                preferred_project_id=self.project_id_var.get().strip() or account_session.bootstrap.preferred_project_id,
                status_message="账号已登录。请选择项目、逻辑根和本地目录，然后保存并启动连接器。",
            )
        elif self.bootstrap_state[0] is not None:
            bootstrap = self.bootstrap_state[0]
            self._apply_project_catalog(
                server_url=bootstrap.server_url,
                projects=bootstrap.projects,
                preferred_project_id=self.project_id_var.get().strip() or bootstrap.preferred_project_id,
                status_message="接入码已加载。请选择项目、逻辑根和本地目录，然后保存并启动连接器。",
            )
        self._update_control_states()

    def _close_setup_dialog(self) -> None:
        dialog = self.setup_dialog
        if dialog is not None and bool(dialog.winfo_exists()):
            dialog.destroy()
        self.setup_dialog = None
        for key in (
            "login_button",
            "load_setup_button",
            "project_combo",
            "directory_combo",
            "browse_root_button",
            "setup_primary_button",
        ):
            self.widget_refs.pop(key, None)

    def _login_account(self) -> None:
        normalized_server_url = self.server_url_var.get().strip().rstrip("/")
        normalized_email = self.email_var.get().strip()
        normalized_password = self.password_var.get()
        if not normalized_server_url:
            self.messagebox.showerror("登录失败", "服务器地址不可为空", parent=self._dialog_parent())
            return
        if not normalized_email:
            self.messagebox.showerror("登录失败", "请输入账号邮箱", parent=self._dialog_parent())
            return
        if not normalized_password:
            self.messagebox.showerror("登录失败", "请输入账号密码", parent=self._dialog_parent())
            return
        self.loading_state[0] = True
        self.account_session_state[0] = None
        self.bootstrap_state[0] = None
        self._set_status("正在登录账号并加载项目列表。")
        self._update_control_states()

        def _worker() -> None:
            try:
                account_session = self.controller.login_account(
                    server_url=normalized_server_url,
                    email=normalized_email,
                    password=normalized_password,
                )
            except Exception as exc:
                self.root.after(0, lambda: self._finish_login_account(None, exc))
                return
            self.root.after(0, lambda: self._finish_login_account(account_session, None))

        threading.Thread(target=_worker, name="desktop-agent-account-login", daemon=True).start()

    def _finish_login_account(
        self,
        account_session: DesktopAgentAccountSession | None,
        error: Exception | None,
    ) -> None:
        self.loading_state[0] = False
        if error is not None:
            self._update_control_states()
            self.messagebox.showerror("登录失败", str(error), parent=self._dialog_parent())
            return
        assert account_session is not None
        self.account_session_state[0] = account_session
        self.setup_code_var.set("")
        self._apply_project_catalog(
            server_url=account_session.server_url,
            projects=account_session.bootstrap.projects,
            preferred_project_id=self.saved_state[0].project_id if self.saved_state[0] else account_session.bootstrap.preferred_project_id,
            status_message="账号登录成功。请选择项目、逻辑根和本地目录，然后保存并启动连接器。",
        )
        self._update_control_states()

    def _load_setup_code(self) -> None:
        normalized_setup_code = self.setup_code_var.get().strip()
        if not normalized_setup_code:
            self.messagebox.showerror("加载接入码失败", "请输入接入码", parent=self._dialog_parent())
            return
        self.loading_state[0] = True
        self.bootstrap_state[0] = None
        self.account_session_state[0] = None
        self._set_status("正在加载接入码并准备项目列表。")
        self._update_control_states()

        def _worker() -> None:
            try:
                bootstrap = self.controller.load_setup_bootstrap(normalized_setup_code)
            except Exception as exc:
                self.root.after(0, lambda: self._finish_load_setup_code(None, exc))
                return
            self.root.after(0, lambda: self._finish_load_setup_code(bootstrap, None))

        threading.Thread(target=_worker, name="desktop-agent-setup-bootstrap", daemon=True).start()

    def _finish_load_setup_code(
        self,
        bootstrap: DesktopAgentSetupBootstrap | None,
        error: Exception | None,
    ) -> None:
        self.loading_state[0] = False
        if error is not None:
            self._update_control_states()
            self.messagebox.showerror("加载接入码失败", str(error), parent=self._dialog_parent())
            return
        assert bootstrap is not None
        self.bootstrap_state[0] = bootstrap
        preferred_project_id = bootstrap.preferred_project_id or (self.saved_state[0].project_id if self.saved_state[0] else "")
        self._apply_project_catalog(
            server_url=bootstrap.server_url,
            projects=bootstrap.projects,
            preferred_project_id=preferred_project_id,
            status_message="接入码已加载。请选择项目、逻辑根和本地目录，然后保存并启动连接器。",
        )
        self._update_control_states()

    def _save_autostart(self) -> None:
        try:
            self.controller.set_autostart(bool(self.autostart_var.get()))
            self._set_status("已更新开机自启设置。")
        except Exception as exc:
            self.messagebox.showerror("更新失败", str(exc), parent=self.root)
            self.autostart_var.set(self.controller.autostart_enabled())

    def _start_saved_connector(self) -> None:
        try:
            config = self.controller.load_saved_config()
            if config is None:
                raise RuntimeError("请先登录并完成一次接入")
            if self.autostart_var.get():
                self.controller.set_autostart(True)
            self.controller.start_agent_process()
            self._set_status(f"已启动已保存的托盘连接器：{config.agent_id}")
            self._refresh_saved_summary()
            self._refresh_update_history()
            self._update_control_states()
        except Exception as exc:
            self.messagebox.showerror("启动失败", str(exc), parent=self.root)

    def _save_setup_and_start(self) -> None:
        try:
            config: AgentConfig | None = None
            account_session = self.account_session_state[0]
            bootstrap = self.bootstrap_state[0]
            if account_session is None and bootstrap is None:
                raise RuntimeError("请先登录账号，或加载接入码")
            if not self.project_id_var.get().strip():
                raise RuntimeError("请选择项目")
            candidate_root = self._selected_candidate_root()
            if candidate_root is None:
                raise RuntimeError("请选择逻辑根")
            if not self.root_dir_var.get().strip():
                raise RuntimeError("请先选择本地目录")
            if account_session is not None:
                config = self.controller.account_setup_and_save(
                    account_session=account_session,
                    project_id=self.project_id_var.get(),
                    candidate_root_key=candidate_root.root_key,
                    root_dir=self.root_dir_var.get(),
                    device_name=self.device_name_var.get(),
                    app_version=self.app_version_var.get(),
                )
            elif bootstrap is not None:
                config = self.controller.setup_and_save(
                    setup_code=self.setup_code_var.get(),
                    bootstrap=bootstrap,
                    project_id=self.project_id_var.get(),
                    candidate_root_key=candidate_root.root_key,
                    root_dir=self.root_dir_var.get(),
                    device_name=self.device_name_var.get(),
                    app_version=self.app_version_var.get(),
                )

            assert config is not None
            if self.autostart_var.get():
                self.controller.set_autostart(True)
            self.controller.start_agent_process()
            self.setup_code_var.set("")
            self.password_var.set("")
            self.account_session_state[0] = None
            self.bootstrap_state[0] = None
            self._close_setup_dialog()
            self._set_status(f"已保存配置并启动托盘连接器：{config.agent_id}")
            self._refresh_saved_summary()
            self._refresh_update_history()
            self._update_control_states()
        except Exception as exc:
            self.messagebox.showerror("启动失败", _friendly_setup_error_message(exc), parent=self._dialog_parent())

    def _open_logs(self) -> None:
        log_path = self.controller.config_store.log_path
        try:
            if log_path.exists():
                os.startfile(str(log_path))
            else:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                os.startfile(str(log_path.parent))
        except Exception as exc:
            self.messagebox.showerror("打开日志失败", str(exc), parent=self.root)


def launch_ui() -> int:
    try:
        from desktop_agent.ui_qt import launch_qt_ui
    except ImportError as exc:
        if str(getattr(exc, "name", "")).startswith("PySide6"):
            return _launch_ui_legacy()
        raise
    except ModuleNotFoundError as exc:
        if str(getattr(exc, "name", "")).startswith("PySide6"):
            return _launch_ui_legacy()
        raise
    return int(launch_qt_ui())
