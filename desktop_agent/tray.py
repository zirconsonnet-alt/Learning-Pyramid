from __future__ import annotations

import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from desktop_agent.autostart import AutostartManager, current_agent_command
from desktop_agent.config_store import AgentUpdateState, ConfigStore
from desktop_agent.instance_lock import SingleInstanceLock
from desktop_agent.logging_utils import configure_desktop_agent_logging, get_desktop_agent_logger
from desktop_agent.service import DesktopAgentService
from desktop_agent.updater import DesktopAgentUpdater

_TRAY_MENU_TEXT_LIMIT = 64
_TRAY_MENU_TEXT_TAIL = 20
_UI_LAUNCH_DEBOUNCE_SECONDS = 1.0


def _spawn_process(command: list[str]) -> None:
    creationflags = 0
    if os.name == "nt":
        creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(command, close_fds=(os.name != "nt"), creationflags=creationflags)


def _open_path(target: str) -> None:
    if os.name == "nt":
        os.startfile(target)  # type: ignore[attr-defined]
        return
    _spawn_process(["xdg-open", target])


def _env_enabled(name: str, *, default: bool = False) -> bool:
    raw = str(os.getenv(name) or "").strip()
    if not raw:
        return bool(default)
    return raw.lower() in {"1", "true", "yes", "on"}


@dataclass
class TrayStatus:
    state: str = "STOPPED"
    message: str | None = None


@dataclass
class TrayUpdateStatus:
    state: str = "UNKNOWN"
    message: str | None = None
    latest_version: str | None = None
    download_url: str | None = None
    silent_install_supported: bool = False
    signature_status: str | None = None


def _status_label(state: str, message: str | None = None) -> str:
    mapping = {
        "STARTING": "启动中",
        "CONNECTING": "连接服务器中",
        "RUNNING": "已连接",
        "REFRESHING": "刷新令牌中",
        "AUTH_EXPIRED": "令牌已过期",
        "ALREADY_RUNNING": "已在运行",
        "CONFIG_MISSING": "未配置",
        "ERROR": "运行异常",
        "STOPPED": "已停止",
    }
    base = mapping.get(str(state).strip().upper(), str(state).strip() or "未知状态")
    if message:
        return f"{base}: {message}"
    return base


def _update_label(state: str, message: str | None = None) -> str:
    mapping = {
        "UNKNOWN": "尚未检查更新",
        "UP_TO_DATE": "后台自动更新正常",
        "UPDATE_AVAILABLE": "发现新版本",
        "INSTALLING": "正在安装更新",
        "ROLLING_BACK": "正在回滚版本",
        "UNAVAILABLE": "服务器没有可用安装包",
        "CONFIG_MISSING": "等待完成接入配置",
        "ERROR": "检查更新失败",
    }
    base = mapping.get(str(state).strip().upper(), str(state).strip() or "未知更新状态")
    if message:
        return f"{base}: {message}"
    return base


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


def _normalize_tray_text(value: str | None) -> str:
    return " ".join(str(value or "").split())


def _compact_tray_menu_text(
    value: str | None,
    *,
    max_length: int = _TRAY_MENU_TEXT_LIMIT,
    tail_length: int = _TRAY_MENU_TEXT_TAIL,
) -> str:
    normalized = _normalize_tray_text(value)
    if len(normalized) <= max_length:
        return normalized
    if max_length <= 3:
        return normalized[:max_length]
    safe_tail_length = min(max(8, int(tail_length)), max_length - 4)
    head_length = max_length - safe_tail_length - 3
    if head_length < 8:
        return normalized[: max_length - 3].rstrip() + "..."
    return normalized[:head_length].rstrip() + "..." + normalized[-safe_tail_length:].lstrip()


class DesktopAgentTrayController:
    def __init__(
        self,
        config_store: ConfigStore | None = None,
        *,
        service_factory: Callable[[ConfigStore], DesktopAgentService] | None = None,
        autostart_manager: AutostartManager | None = None,
        updater: DesktopAgentUpdater | None = None,
        process_spawner: Callable[[list[str]], None] = _spawn_process,
        path_opener: Callable[[str], None] = _open_path,
        instance_lock: SingleInstanceLock | None = None,
    ) -> None:
        self.config_store = config_store or ConfigStore()
        self.service_factory = service_factory or (lambda store: DesktopAgentService(store))
        self.autostart_manager = autostart_manager or AutostartManager()
        self.updater = updater or DesktopAgentUpdater()
        self.process_spawner = process_spawner
        self.path_opener = path_opener
        self.instance_lock = instance_lock or SingleInstanceLock(self.config_store.tray_lock_path)
        self._status = TrayStatus()
        self._status_lock = threading.Lock()
        self._update_status = TrayUpdateStatus()
        self._update_status_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._command_thread: threading.Thread | None = None
        self._command_stop_event: threading.Event | None = None
        self._shutdown_requested = threading.Event()
        self._ui_launch_lock = threading.Lock()
        self._last_ui_launch_monotonic = 0.0
        self._logger = get_desktop_agent_logger("tray")
        self.config_store.ensure_app_version()

    def _set_status(self, state: str, message: str | None = None) -> None:
        with self._status_lock:
            self._status = TrayStatus(state=str(state), message=None if message is None else str(message))
        self._logger.info("tray_status state=%s message=%s", state, message)

    def current_status(self) -> TrayStatus:
        with self._status_lock:
            return TrayStatus(self._status.state, self._status.message)

    def current_status_label(self) -> str:
        current = self.current_status()
        return _status_label(current.state, current.message)

    def current_status_menu_label(self) -> str:
        return _compact_tray_menu_text(f"状态: {self.current_status_label()}")

    def _set_update_status(
        self,
        state: str,
        message: str | None = None,
        *,
        latest_version: str | None = None,
        download_url: str | None = None,
        silent_install_supported: bool = False,
        signature_status: str | None = None,
    ) -> None:
        with self._update_status_lock:
            self._update_status = TrayUpdateStatus(
                state=str(state),
                message=None if message is None else str(message),
                latest_version=None if latest_version is None else str(latest_version),
                download_url=None if download_url is None else str(download_url),
                silent_install_supported=bool(silent_install_supported),
                signature_status=None if signature_status is None else str(signature_status),
            )
        self._logger.info(
            "tray_update_status state=%s latest_version=%s download_url=%s silent_install_supported=%s signature_status=%s message=%s",
            state,
            latest_version,
            download_url,
            silent_install_supported,
            signature_status,
            message,
        )

    def current_update_status(self) -> TrayUpdateStatus:
        with self._update_status_lock:
            return TrayUpdateStatus(
                self._update_status.state,
                self._update_status.message,
                self._update_status.latest_version,
                self._update_status.download_url,
                self._update_status.silent_install_supported,
                self._update_status.signature_status,
            )

    def current_update_label(self) -> str:
        current = self.current_update_status()
        return _update_label(current.state, current.message)

    def current_update_menu_label(self) -> str:
        return _compact_tray_menu_text(f"更新: {self.current_update_label()}")

    def load_update_state(self) -> AgentUpdateState | None:
        return self.config_store.load_update_state()

    def current_update_history_label(self) -> str:
        return _update_history_label(self.load_update_state())

    def current_update_history_menu_label(self) -> str:
        return _compact_tray_menu_text(self.current_update_history_label())

    def has_config(self) -> bool:
        return self.config_store.exists()

    def autostart_enabled(self) -> bool:
        return self.autostart_manager.is_enabled()

    def auto_update_enabled(self) -> bool:
        return _env_enabled("PLM_AGENT_AUTO_UPDATE", default=True)

    def require_signed_updates(self) -> bool:
        return _env_enabled("PLM_AGENT_AUTO_UPDATE_REQUIRE_SIGNED")

    def set_autostart(self, enabled: bool) -> None:
        if enabled:
            self.autostart_manager.enable(current_agent_command("tray"))
            return
        self.autostart_manager.disable()

    def toggle_autostart(self) -> bool:
        next_enabled = not self.autostart_enabled()
        self.set_autostart(next_enabled)
        return next_enabled

    def launch_ui(self, *, debounce_seconds: float = _UI_LAUNCH_DEBOUNCE_SECONDS) -> bool:
        now = time.monotonic()
        with self._ui_launch_lock:
            elapsed = now - self._last_ui_launch_monotonic
            if self._last_ui_launch_monotonic > 0 and elapsed < max(0.0, float(debounce_seconds)):
                self._logger.info("launch_ui_skipped reason=debounced elapsed_seconds=%.3f", elapsed)
                return False
            self._last_ui_launch_monotonic = now
        self._logger.info("launch_ui_requested")
        try:
            self.process_spawner(current_agent_command("ui"))
        except Exception:
            with self._ui_launch_lock:
                self._last_ui_launch_monotonic = 0.0
            raise
        return True

    def open_data_dir(self) -> None:
        target = str(self.config_store.base_dir)
        self._logger.info("open_data_dir target=%s", target)
        self.path_opener(target)

    def open_log_file(self) -> None:
        log_path = self.config_store.log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.touch(exist_ok=True)
        self._logger.info("open_log_file target=%s", log_path)
        self.path_opener(str(log_path))

    def open_update_log(self) -> bool:
        state = self.load_update_state()
        target = None if state is None or not state.log_path else Path(state.log_path)
        if target is None or not target.exists():
            return False
        self._logger.info("open_update_log target=%s", target)
        self.path_opener(str(target))
        return True

    def can_open_update_log(self) -> bool:
        state = self.load_update_state()
        target = None if state is None or not state.log_path else Path(state.log_path)
        return target is not None and target.exists()

    def can_rollback_last_update(self) -> bool:
        state = self.load_update_state()
        if state is None or not state.rollback_script_path or not state.backup_dir:
            return False
        rollback_script = Path(state.rollback_script_path)
        backup_dir = Path(state.backup_dir)
        return rollback_script.exists() and backup_dir.exists()

    def rollback_last_update(self, *, current_pid: int | None = None) -> bool:
        state = self.load_update_state()
        if state is None or not state.rollback_script_path:
            return False
        rollback_script = Path(state.rollback_script_path)
        if not rollback_script.exists():
            return False
        command = [
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
        self._set_update_status("ROLLING_BACK", state.current_version or state.installed_version)
        self._logger.info("tray_rollback_update command=%s", " ".join(command))
        self.process_spawner(command)
        return True

    def check_for_updates(self) -> TrayUpdateStatus:
        if not self.has_config():
            self._set_update_status("CONFIG_MISSING", "尚未完成配对配置")
            return self.current_update_status()
        config = self.config_store.ensure_app_version() or self.config_store.load()
        try:
            result = self.updater.check_for_updates(
                server_url=config.server_url,
                current_version=config.app_version,
            )
        except Exception as exc:
            self._set_update_status("ERROR", str(exc))
            return self.current_update_status()
        if not result.available:
            self._set_update_status("UNAVAILABLE", None)
            return self.current_update_status()
        if result.update_available and result.latest_version:
            message_parts = [result.latest_version]
            if result.signature_status:
                message_parts.append(f"签名 {result.signature_status}")
            if result.silent_install_supported and self.auto_update_enabled():
                message_parts.append("支持后台自动更新")
            self._set_update_status(
                "UPDATE_AVAILABLE",
                " / ".join(message_parts),
                latest_version=result.latest_version,
                download_url=result.download_url,
                silent_install_supported=result.silent_install_supported,
                signature_status=result.signature_status,
            )
            return self.current_update_status()
        self._set_update_status(
            "UP_TO_DATE",
            config.app_version,
            latest_version=result.latest_version,
            download_url=result.download_url,
            silent_install_supported=result.silent_install_supported,
            signature_status=result.signature_status,
        )
        return self.current_update_status()

    def install_update(self, *, current_pid: int | None = None) -> bool:
        if not self.has_config():
            self._set_update_status("CONFIG_MISSING", "尚未完成配对配置")
            return False
        config = self.config_store.ensure_app_version() or self.config_store.load()
        staging_dir = self.config_store.updates_dir
        try:
            prepared = self.updater.prepare_update(
                server_url=config.server_url,
                current_version=config.app_version,
                target_dir=staging_dir,
                require_signed=self.require_signed_updates(),
            )
            plan = self.updater.build_silent_install_plan(
                prepared,
                current_pid=os.getpid() if current_pid is None else current_pid,
                helper_dir=staging_dir,
                relaunch=True,
            )
            self._set_update_status(
                "INSTALLING",
                prepared.latest_version,
                latest_version=prepared.latest_version,
                download_url=prepared.download_url,
                silent_install_supported=prepared.silent_install_supported,
                signature_status=prepared.signature_status,
            )
            self._logger.info(
                "tray_install_update asset=%s command=%s",
                prepared.asset_name,
                " ".join(plan.command),
            )
            self.process_spawner(list(plan.command))
            return True
        except Exception as exc:
            self._set_update_status("ERROR", str(exc))
            return False

    def open_update_download(self) -> bool:
        current = self.current_update_status()
        if not current.download_url:
            return False
        self._logger.info("open_update_download target=%s", current.download_url)
        self.path_opener(current.download_url)
        return True

    def claim_single_instance(self) -> bool:
        if self.instance_lock.acquire():
            self._logger.info("tray_instance_lock_acquired path=%s", self.instance_lock.path)
            return True
        self._set_status("ALREADY_RUNNING", "托盘连接器已在运行")
        return False

    def release_single_instance(self) -> None:
        if self.instance_lock.locked():
            self._logger.info("tray_instance_lock_released path=%s", self.instance_lock.path)
        self.instance_lock.release()

    def _run_service_worker(self) -> None:
        service = self.service_factory(self.config_store)
        try:
            service.run_forever(stop_event=self._stop_event, status_callback=self._set_status)
        finally:
            if self._stop_event is not None and self._stop_event.is_set():
                self._set_status("STOPPED", None)

    def ensure_service_running(self) -> bool:
        thread = self._thread
        if thread is not None and thread.is_alive():
            self._logger.info("service_already_running")
            return True
        if not self.has_config():
            self._set_status("CONFIG_MISSING", "尚未完成配对配置")
            return False
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_service_worker, name="desktop-agent-service", daemon=True)
        self._thread.start()
        self._logger.info("service_thread_started")
        return True

    def shutdown_requested(self) -> bool:
        return bool(self._shutdown_requested.is_set())

    def stop_service(self, *, join_timeout: float = 5.0) -> None:
        stop_event = self._stop_event
        if stop_event is not None:
            stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=join_timeout)
        self._thread = None
        self._stop_event = None
        self._set_status("STOPPED", None)
        self._logger.info("service_thread_stopped")

    def restart_service(self) -> bool:
        self.stop_service()
        return self.ensure_service_running()

    def shutdown(self) -> None:
        self._shutdown_requested.set()
        command_stop_event = self._command_stop_event
        if command_stop_event is not None:
            command_stop_event.set()
        command_thread = self._command_thread
        if command_thread is not None and command_thread.is_alive():
            command_thread.join(timeout=2.0)
        self._command_thread = None
        self._command_stop_event = None
        self.stop_service()

    def process_pending_service_command(self) -> bool:
        command = self.config_store.consume_service_command()
        if command is None:
            return False
        if command.action == "restart":
            self._logger.info("service_command action=restart reason=%s requested_at=%s", command.reason, command.requested_at)
            self.restart_service()
            return True
        self._logger.info("service_command_ignored action=%s", command.action)
        return False

    def ensure_command_watcher_running(self) -> bool:
        thread = self._command_thread
        if thread is not None and thread.is_alive():
            return True
        stop_event = threading.Event()
        self._command_stop_event = stop_event

        def _watch() -> None:
            while not stop_event.wait(0.5):
                try:
                    self.process_pending_service_command()
                except Exception:
                    self._logger.exception("service_command_processing_failed")

        self._command_thread = threading.Thread(target=_watch, name="desktop-agent-command-watch", daemon=True)
        self._command_thread.start()
        return True


def _build_tray_image():
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (64, 64), (18, 44, 78, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((6, 6, 58, 58), radius=14, fill=(22, 78, 99, 255))
    draw.rectangle((18, 16, 30, 48), fill=(255, 255, 255, 255))
    draw.rectangle((34, 24, 46, 48), fill=(183, 230, 255, 255))
    draw.rectangle((18, 16, 46, 20), fill=(255, 214, 102, 255))
    return image


def _run_headless_fallback(
    controller: DesktopAgentTrayController,
    *,
    reason: str,
    poll_interval_seconds: float = 0.5,
) -> int:
    controller._logger.warning("tray_headless_fallback_entered reason=%s", reason)
    controller.ensure_service_running()
    controller.ensure_command_watcher_running()
    try:
        while not controller.shutdown_requested():
            time.sleep(float(poll_interval_seconds))
    except KeyboardInterrupt:
        controller._logger.info("tray_headless_fallback_interrupted")
    finally:
        controller.shutdown()
        controller.release_single_instance()
    return 0


def launch_tray() -> int:
    configure_desktop_agent_logging()
    controller = DesktopAgentTrayController()
    if not controller.has_config():
        from desktop_agent.ui import launch_ui

        return int(launch_ui())
    if not controller.claim_single_instance():
        return 0

    try:
        import pystray
    except Exception:
        controller._logger.exception("tray_pystray_import_failed")
        return _run_headless_fallback(controller, reason="pystray import failed")

    def _open_setup(icon, item) -> None:
        del icon, item
        controller.launch_ui()

    def _reconnect(icon, item) -> None:
        del item
        controller.restart_service()
        icon.update_menu()

    def _toggle_autostart(icon, item) -> None:
        del item
        controller.toggle_autostart()
        icon.update_menu()

    def _open_data_dir(icon, item) -> None:
        del icon, item
        controller.open_data_dir()

    def _open_log_file(icon, item) -> None:
        del icon, item
        controller.open_log_file()

    def _quit(icon, item) -> None:
        del item
        controller.shutdown()
        icon.stop()

    icon = pystray.Icon(
        "learningpyramid-desktop-agent",
        _build_tray_image(),
        "LearningPyramid Desktop Agent",
        menu=pystray.Menu(
            pystray.MenuItem(lambda item: controller.current_status_menu_label(), lambda icon, item: None, enabled=False),
            pystray.MenuItem(lambda item: controller.current_update_menu_label(), lambda icon, item: None, enabled=False),
            pystray.MenuItem(lambda item: controller.current_update_history_menu_label(), lambda icon, item: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("打开配置窗口", _open_setup, default=True),
            pystray.MenuItem("立即重连", _reconnect),
            pystray.MenuItem("开机自启", _toggle_autostart, checked=lambda item: controller.autostart_enabled()),
            pystray.MenuItem("打开数据目录", _open_data_dir),
            pystray.MenuItem("打开日志文件", _open_log_file),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", _quit),
        ),
    )
    controller.ensure_service_running()
    controller.ensure_command_watcher_running()
    setup_completed = threading.Event()

    def _background_update_check(icon_instance) -> None:
        controller.check_for_updates()
        icon_instance.update_menu()
        current = controller.current_update_status()
        if (
            controller.auto_update_enabled()
            and current.state == "UPDATE_AVAILABLE"
            and current.silent_install_supported
            and controller.install_update(current_pid=os.getpid())
        ):
            controller._logger.info("tray_update_install_requested")
            controller.shutdown()
            icon_instance.stop()

    def _setup(icon_instance) -> None:
        setup_completed.set()
        controller._logger.info("tray_icon_setup_completed")
        icon_instance.visible = True
        threading.Thread(
            target=lambda: _background_update_check(icon_instance),
            name="desktop-agent-update-check",
            daemon=True,
        ).start()

    fallback_reason: str | None = None
    try:
        icon.run(setup=_setup)
    except Exception:
        controller._logger.exception("tray_icon_run_failed")
        fallback_reason = "icon.run failed"
    if controller.shutdown_requested():
        controller.shutdown()
        controller.release_single_instance()
        return 0
    if fallback_reason is None and not setup_completed.is_set():
        controller._logger.warning("tray_icon_setup_not_completed")
    if fallback_reason is None:
        controller._logger.warning("tray_icon_run_returned_unexpectedly")
        fallback_reason = "icon.run returned unexpectedly"
    return _run_headless_fallback(controller, reason=fallback_reason)
