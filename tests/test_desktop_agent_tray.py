from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from backend.system.version import APP_VERSION
from desktop_agent.autostart import AutostartManager, current_agent_command
from desktop_agent.config_store import AgentConfig, AgentUpdateState, ConfigStore
from desktop_agent.instance_lock import SingleInstanceLock
from desktop_agent.tray import DesktopAgentTrayController
import desktop_agent.tray as tray_module
from desktop_agent.updater import DesktopAgentPreparedUpdate, DesktopAgentSilentInstallPlan, DesktopAgentUpdateCheckResult


def _seed_config(tmp_path: Path, *, app_version: str = APP_VERSION) -> ConfigStore:
    store = ConfigStore(tmp_path / "config")
    store.save(
        AgentConfig(
            server_url="http://127.0.0.1:8000",
            agent_id="agent_123",
            agent_token="agent-token-1",
            refresh_token="refresh-token-1",
            project_id="proj_123",
            root_dir=str(tmp_path.resolve()),
            device_name="BYLOU-PC",
            app_version=app_version,
        )
    )
    return store


def test_tray_controller_marks_missing_config_when_not_paired(tmp_path: Path) -> None:
    controller = DesktopAgentTrayController(
        config_store=ConfigStore(tmp_path / "config"),
        autostart_manager=AutostartManager(tmp_path / "startup"),
        process_spawner=lambda command: None,
    )

    assert controller.ensure_service_running() is False
    assert controller.current_status().state == "CONFIG_MISSING"


def test_tray_controller_refreshes_saved_app_version(tmp_path: Path) -> None:
    store = _seed_config(tmp_path, app_version="0.1.0-beta.0")

    DesktopAgentTrayController(
        config_store=store,
        autostart_manager=AutostartManager(tmp_path / "startup"),
        process_spawner=lambda command: None,
    )

    assert store.load().app_version == APP_VERSION


def test_tray_controller_auto_update_defaults_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PLM_AGENT_AUTO_UPDATE", raising=False)
    controller = DesktopAgentTrayController(
        config_store=_seed_config(tmp_path),
        autostart_manager=AutostartManager(tmp_path / "startup"),
        process_spawner=lambda command: None,
    )

    assert controller.auto_update_enabled() is True


def test_tray_controller_starts_restarts_and_stops_background_service(tmp_path: Path) -> None:
    store = _seed_config(tmp_path)

    class StubService:
        run_count = 0

        def __init__(self, config_store: ConfigStore) -> None:
            self.config_store = config_store

        def run_forever(self, *, stop_event=None, status_callback=None) -> None:
            StubService.run_count += 1
            if status_callback is not None:
                status_callback("RUNNING", f"run-{StubService.run_count}")
            while stop_event is not None and not stop_event.is_set():
                time.sleep(0.01)

    controller = DesktopAgentTrayController(
        config_store=store,
        autostart_manager=AutostartManager(tmp_path / "startup"),
        service_factory=lambda config_store: StubService(config_store),
        process_spawner=lambda command: None,
    )

    assert controller.ensure_service_running() is True
    for _ in range(50):
        if controller.current_status().state == "RUNNING":
            break
        time.sleep(0.01)
    assert controller.current_status().state == "RUNNING"
    assert StubService.run_count == 1

    assert controller.restart_service() is True
    for _ in range(50):
        if controller.current_status().message == "run-2":
            break
        time.sleep(0.01)
    assert controller.current_status().message == "run-2"
    assert StubService.run_count == 2

    controller.stop_service()
    assert controller.current_status().state == "STOPPED"


def test_tray_controller_processes_restart_service_command(tmp_path: Path) -> None:
    store = _seed_config(tmp_path)

    class StubService:
        run_count = 0

        def __init__(self, config_store: ConfigStore) -> None:
            self.config_store = config_store

        def run_forever(self, *, stop_event=None, status_callback=None) -> None:
            StubService.run_count += 1
            if status_callback is not None:
                status_callback("RUNNING", f"run-{StubService.run_count}")
            while stop_event is not None and not stop_event.is_set():
                time.sleep(0.01)

    controller = DesktopAgentTrayController(
        config_store=store,
        autostart_manager=AutostartManager(tmp_path / "startup"),
        service_factory=lambda config_store: StubService(config_store),
        process_spawner=lambda command: None,
    )

    assert controller.ensure_service_running() is True
    for _ in range(50):
        if controller.current_status().message == "run-1":
            break
        time.sleep(0.01)
    store.request_service_restart(reason="setup_saved")

    assert controller.process_pending_service_command() is True
    for _ in range(50):
        if controller.current_status().message == "run-2":
            break
        time.sleep(0.01)
    assert controller.current_status().message == "run-2"
    assert store.load_service_command() is None

    controller.shutdown()


def test_tray_controller_toggles_autostart_to_tray_command(tmp_path: Path) -> None:
    controller = DesktopAgentTrayController(
        config_store=_seed_config(tmp_path),
        autostart_manager=AutostartManager(tmp_path / "startup"),
        process_spawner=lambda command: None,
    )

    assert controller.autostart_enabled() is False
    assert controller.toggle_autostart() is True
    script = controller.autostart_manager.script_path.read_text(encoding="utf-8")
    assert " tray" in script
    assert controller.toggle_autostart() is False
    assert controller.autostart_enabled() is False


def test_tray_controller_debounces_launch_ui_requests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spawned: list[list[str]] = []
    monotonic_values = iter((100.0, 100.2, 101.5))
    monkeypatch.setattr(tray_module.time, "monotonic", lambda: next(monotonic_values))
    controller = DesktopAgentTrayController(
        config_store=_seed_config(tmp_path),
        autostart_manager=AutostartManager(tmp_path / "startup"),
        process_spawner=lambda command: spawned.append(command),
    )

    assert controller.launch_ui() is True
    assert controller.launch_ui() is False
    assert controller.launch_ui() is True
    assert spawned == [current_agent_command("ui"), current_agent_command("ui")]


def test_tray_controller_claims_single_instance_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / "config" / "tray.lock"
    first = DesktopAgentTrayController(
        config_store=_seed_config(tmp_path),
        autostart_manager=AutostartManager(tmp_path / "startup-1"),
        instance_lock=SingleInstanceLock(lock_path),
        process_spawner=lambda command: None,
    )
    second = DesktopAgentTrayController(
        config_store=_seed_config(tmp_path),
        autostart_manager=AutostartManager(tmp_path / "startup-2"),
        instance_lock=SingleInstanceLock(lock_path),
        process_spawner=lambda command: None,
    )

    assert first.claim_single_instance() is True
    assert second.claim_single_instance() is False
    assert second.current_status().state == "ALREADY_RUNNING"

    first.release_single_instance()
    assert second.claim_single_instance() is True
    second.release_single_instance()


def test_tray_controller_opens_log_file(tmp_path: Path) -> None:
    opened: list[str] = []
    controller = DesktopAgentTrayController(
        config_store=_seed_config(tmp_path),
        autostart_manager=AutostartManager(tmp_path / "startup"),
        path_opener=lambda target: opened.append(target),
        process_spawner=lambda command: None,
    )

    controller.open_log_file()

    assert controller.config_store.log_path.exists()
    assert opened == [str(controller.config_store.log_path)]


def test_tray_controller_checks_for_updates_and_opens_download(tmp_path: Path) -> None:
    opened: list[str] = []

    class StubUpdater:
        calls: list[tuple[str, str]] = []

        def check_for_updates(self, *, server_url: str, current_version: str) -> DesktopAgentUpdateCheckResult:
            StubUpdater.calls.append((server_url, current_version))
            return DesktopAgentUpdateCheckResult(
                available=True,
                update_available=True,
                current_version=current_version,
                latest_version="0.1.0-beta.2",
                download_url="https://learn.example.com/api/system/desktop-agent-release/assets/agent-setup.exe",
                published_at="2026-03-11T12:00:00+00:00",
                asset_name="agent-setup.exe",
                asset_kind="installer_exe",
                signature_status="SIGNED",
                silent_install_supported=True,
                silent_install_strategy="inno_exe",
            )

    controller = DesktopAgentTrayController(
        config_store=_seed_config(tmp_path),
        autostart_manager=AutostartManager(tmp_path / "startup"),
        updater=StubUpdater(),
        path_opener=lambda target: opened.append(target),
        process_spawner=lambda command: None,
    )

    update_status = controller.check_for_updates()

    assert StubUpdater.calls == [("http://127.0.0.1:8000", APP_VERSION)]
    assert update_status.state == "UPDATE_AVAILABLE"
    assert update_status.latest_version == "0.1.0-beta.2"
    assert update_status.silent_install_supported is True
    assert update_status.signature_status == "SIGNED"
    assert controller.open_update_download() is True
    assert opened == ["https://learn.example.com/api/system/desktop-agent-release/assets/agent-setup.exe"]


def test_tray_controller_compacts_verbose_menu_labels(tmp_path: Path) -> None:
    controller = DesktopAgentTrayController(
        config_store=_seed_config(tmp_path),
        autostart_manager=AutostartManager(tmp_path / "startup"),
        process_spawner=lambda command: None,
    )

    controller._set_update_status(
        "ERROR",
        "HTTPSConnectionPool(host='plm.xuebao.chat', port=443): Max retries exceeded with url: "
        "/api/system/desktop-agent-release/currentVersion?currentVersion=0.1.0-beta.2 "
        "(Caused by NameResolutionError(\"Failed to resolve 'plm.xuebao.chat'\"))",
    )

    label = controller.current_update_menu_label()

    assert label.startswith("更新: 检查更新失败: HTTPSConnectionPool(")
    assert "..." in label
    assert len(label) <= 64
    assert label.endswith("m.xuebao.chat'\"))")


def test_tray_controller_installs_update_silently(tmp_path: Path) -> None:
    spawned: list[list[str]] = []

    class StubUpdater:
        prepare_calls: list[tuple[str, str, Path, bool]] = []
        build_calls: list[tuple[str, int, Path, bool]] = []

        def prepare_update(self, *, server_url: str, current_version: str, target_dir, require_signed: bool):
            target = Path(target_dir)
            StubUpdater.prepare_calls.append((server_url, current_version, target, require_signed))
            asset_path = target / "agent-setup.exe"
            target.mkdir(parents=True, exist_ok=True)
            asset_path.write_bytes(b"installer")
            return DesktopAgentPreparedUpdate(
                current_version=current_version,
                latest_version="0.1.0-beta.2",
                download_url="https://learn.example.com/download/agent-setup.exe",
                asset_name="agent-setup.exe",
                asset_kind="installer_exe",
                asset_path=asset_path,
                sha256="abc123",
                integrity_mode="sha256",
                signature_status="SIGNED",
                signature_subject="CN=LearningPyramid",
                silent_install_supported=True,
                silent_install_strategy="inno_exe",
            )

        def build_silent_install_plan(self, prepared, *, current_pid: int, helper_dir, relaunch: bool):
            target = Path(helper_dir)
            StubUpdater.build_calls.append((prepared.latest_version, current_pid, target, relaunch))
            target.mkdir(parents=True, exist_ok=True)
            helper_path = target / "apply.ps1"
            helper_path.write_text("Write-Host update", encoding="utf-8")
            return DesktopAgentSilentInstallPlan(
                command=("powershell", "-File", str(helper_path)),
                helper_script_path=helper_path,
                rollback_script_path=target / "rollback.ps1",
                state_path=target / "update-state.json",
                backup_dir=target / "backup-current",
                log_path=target / "apply.log",
                relaunch_exe_path=target / "LearningPyramidDesktopAgent.exe",
            )

    controller = DesktopAgentTrayController(
        config_store=_seed_config(tmp_path),
        autostart_manager=AutostartManager(tmp_path / "startup"),
        updater=StubUpdater(),
        process_spawner=lambda command: spawned.append(command),
    )

    assert controller.install_update(current_pid=4321) is True
    assert StubUpdater.prepare_calls == [("http://127.0.0.1:8000", APP_VERSION, controller.config_store.base_dir / "updates", False)]
    assert StubUpdater.build_calls == [("0.1.0-beta.2", 4321, controller.config_store.base_dir / "updates", True)]
    assert controller.current_update_status().state == "INSTALLING"
    assert spawned == [["powershell", "-File", str(controller.config_store.base_dir / "updates" / "apply.ps1")]]


def test_tray_controller_opens_update_log_and_rolls_back(tmp_path: Path) -> None:
    opened: list[str] = []
    spawned: list[list[str]] = []
    store = _seed_config(tmp_path)
    rollback_path = store.updates_dir / "rollback.ps1"
    backup_dir = store.updates_dir / "backup-current"
    log_path = store.updates_dir / "apply.log"
    rollback_path.parent.mkdir(parents=True, exist_ok=True)
    rollback_path.write_text("Write-Host rollback", encoding="utf-8")
    backup_dir.mkdir(parents=True, exist_ok=True)
    log_path.write_text("update log", encoding="utf-8")
    store.save_update_state(
        AgentUpdateState(
            status="SUCCEEDED",
            message="Installed 0.1.0-beta.2",
            current_version=APP_VERSION,
            target_version="0.1.0-beta.2",
            installed_version="0.1.0-beta.2",
            log_path=str(log_path),
            backup_dir=str(backup_dir),
            rollback_script_path=str(rollback_path),
        )
    )
    controller = DesktopAgentTrayController(
        config_store=store,
        autostart_manager=AutostartManager(tmp_path / "startup"),
        path_opener=lambda target: opened.append(target),
        process_spawner=lambda command: spawned.append(command),
    )

    assert controller.can_open_update_log() is True
    assert controller.open_update_log() is True
    assert opened == [str(log_path)]
    assert controller.can_rollback_last_update() is True
    assert controller.rollback_last_update(current_pid=111) is True
    assert spawned == [
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(rollback_path),
            "-WaitPid",
            "111",
            "-Relaunch",
        ]
    ]


def test_launch_tray_marks_open_setup_as_default_menu_item(monkeypatch: pytest.MonkeyPatch) -> None:
    class _StubLogger:
        def info(self, *args, **kwargs) -> None:
            pass

        def warning(self, *args, **kwargs) -> None:
            pass

        def exception(self, *args, **kwargs) -> None:
            pass

    class _StubController:
        def __init__(self) -> None:
            self._logger = _StubLogger()
            self.launch_ui_calls = 0

        def has_config(self) -> bool:
            return True

        def claim_single_instance(self) -> bool:
            return True

        def release_single_instance(self) -> None:
            pass

        def ensure_service_running(self) -> bool:
            return True

        def ensure_command_watcher_running(self) -> bool:
            return True

        def shutdown_requested(self) -> bool:
            return False

        def shutdown(self) -> None:
            pass

        def launch_ui(self) -> bool:
            self.launch_ui_calls += 1
            return True

        def autostart_enabled(self) -> bool:
            return False

    class _StubIcon:
        created_menu = None

        def __init__(self, *args, **kwargs) -> None:
            self.visible = False
            _StubIcon.created_menu = kwargs.get("menu")

        def run(self, setup=None) -> None:
            del setup

        def stop(self) -> None:
            pass

        def update_menu(self) -> None:
            pass

    class _StubPystray:
        Icon = _StubIcon

        class Menu:
            SEPARATOR = object()

            def __new__(cls, *items):
                return list(items)

        @staticmethod
        def MenuItem(*args, **kwargs):
            return {"args": args, "kwargs": kwargs}

    controller = _StubController()
    monkeypatch.setattr(tray_module, "configure_desktop_agent_logging", lambda: None)
    monkeypatch.setattr(tray_module, "DesktopAgentTrayController", lambda: controller)
    monkeypatch.setattr(tray_module, "_run_headless_fallback", lambda controller, *, reason, poll_interval_seconds=0.5: 0)
    monkeypatch.setitem(sys.modules, "pystray", _StubPystray)

    assert tray_module.launch_tray() == 0
    assert isinstance(_StubIcon.created_menu, list)
    open_setup_item = next(item for item in _StubIcon.created_menu if isinstance(item, dict) and item["args"][0] == "打开配置窗口")
    assert open_setup_item["kwargs"].get("default") is True

    callback = open_setup_item["args"][1]
    callback(None, None)
    assert controller.launch_ui_calls == 1


def test_launch_tray_falls_back_to_headless_when_icon_run_returns_early(monkeypatch: pytest.MonkeyPatch) -> None:
    class _StubLogger:
        def info(self, *args, **kwargs) -> None:
            pass

        def warning(self, *args, **kwargs) -> None:
            pass

        def exception(self, *args, **kwargs) -> None:
            pass

    class _StubController:
        def __init__(self) -> None:
            self._logger = _StubLogger()
            self.ensure_service_running_calls = 0
            self.ensure_command_watcher_running_calls = 0
            self.shutdown_calls = 0
            self.release_calls = 0
            self._shutdown_requested = False

        def has_config(self) -> bool:
            return True

        def claim_single_instance(self) -> bool:
            return True

        def release_single_instance(self) -> None:
            self.release_calls += 1

        def ensure_service_running(self) -> bool:
            self.ensure_service_running_calls += 1
            if self.ensure_service_running_calls >= 2:
                self._shutdown_requested = True
            return True

        def ensure_command_watcher_running(self) -> bool:
            self.ensure_command_watcher_running_calls += 1
            return True

        def shutdown_requested(self) -> bool:
            return bool(self._shutdown_requested)

        def shutdown(self) -> None:
            self.shutdown_calls += 1

        def current_status_label(self) -> str:
            return "running"

        def current_update_label(self) -> str:
            return "up-to-date"

        def current_update_history_label(self) -> str:
            return "none"

        def launch_ui(self) -> None:
            pass

        def restart_service(self) -> bool:
            return True

        def toggle_autostart(self) -> bool:
            return False

        def autostart_enabled(self) -> bool:
            return False

        def open_data_dir(self) -> None:
            pass

        def open_log_file(self) -> None:
            pass

        def check_for_updates(self):
            return None

        def current_update_status(self):
            class _Status:
                state = "UP_TO_DATE"
                silent_install_supported = False

            return _Status()

        def auto_update_enabled(self) -> bool:
            return False

        def install_update(self, *, current_pid: int | None = None) -> bool:
            return False

    class _StubIcon:
        def __init__(self, *args, **kwargs) -> None:
            self.visible = False

        def run(self, setup=None) -> None:
            del setup

        def stop(self) -> None:
            pass

        def update_menu(self) -> None:
            pass

    class _StubPystray:
        Icon = _StubIcon

        class Menu:
            SEPARATOR = object()

            def __new__(cls, *items):
                return list(items)

        @staticmethod
        def MenuItem(*args, **kwargs):
            return (args, kwargs)

    controller = _StubController()
    monkeypatch.setattr(tray_module, "configure_desktop_agent_logging", lambda: None)
    monkeypatch.setattr(tray_module, "DesktopAgentTrayController", lambda: controller)
    monkeypatch.setitem(sys.modules, "pystray", _StubPystray)

    assert tray_module.launch_tray() == 0
    assert controller.ensure_service_running_calls == 2
    assert controller.ensure_command_watcher_running_calls == 2
    assert controller.shutdown_calls == 1
    assert controller.release_calls == 1


def test_launch_tray_falls_back_to_headless_when_icon_run_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    class _StubLogger:
        def info(self, *args, **kwargs) -> None:
            pass

        def warning(self, *args, **kwargs) -> None:
            pass

        def exception(self, *args, **kwargs) -> None:
            pass

    class _StubController:
        def __init__(self) -> None:
            self._logger = _StubLogger()
            self.ensure_service_running_calls = 0
            self.ensure_command_watcher_running_calls = 0
            self.shutdown_calls = 0
            self.release_calls = 0
            self._shutdown_requested = False

        def has_config(self) -> bool:
            return True

        def claim_single_instance(self) -> bool:
            return True

        def release_single_instance(self) -> None:
            self.release_calls += 1

        def ensure_service_running(self) -> bool:
            self.ensure_service_running_calls += 1
            if self.ensure_service_running_calls >= 2:
                self._shutdown_requested = True
            return True

        def ensure_command_watcher_running(self) -> bool:
            self.ensure_command_watcher_running_calls += 1
            return True

        def shutdown_requested(self) -> bool:
            return bool(self._shutdown_requested)

        def shutdown(self) -> None:
            self.shutdown_calls += 1

        def current_status_label(self) -> str:
            return "running"

        def current_update_label(self) -> str:
            return "up-to-date"

        def current_update_history_label(self) -> str:
            return "none"

        def launch_ui(self) -> None:
            pass

        def restart_service(self) -> bool:
            return True

        def toggle_autostart(self) -> bool:
            return False

        def autostart_enabled(self) -> bool:
            return False

        def open_data_dir(self) -> None:
            pass

        def open_log_file(self) -> None:
            pass

        def check_for_updates(self):
            return None

        def current_update_status(self):
            class _Status:
                state = "UP_TO_DATE"
                silent_install_supported = False

            return _Status()

        def auto_update_enabled(self) -> bool:
            return False

        def install_update(self, *, current_pid: int | None = None) -> bool:
            return False

    class _StubIcon:
        def __init__(self, *args, **kwargs) -> None:
            self.visible = False

        def run(self, setup=None) -> None:
            del setup
            raise RuntimeError("tray backend failed")

        def stop(self) -> None:
            pass

        def update_menu(self) -> None:
            pass

    class _StubPystray:
        Icon = _StubIcon

        class Menu:
            SEPARATOR = object()

            def __new__(cls, *items):
                return list(items)

        @staticmethod
        def MenuItem(*args, **kwargs):
            return (args, kwargs)

    controller = _StubController()
    monkeypatch.setattr(tray_module, "configure_desktop_agent_logging", lambda: None)
    monkeypatch.setattr(tray_module, "DesktopAgentTrayController", lambda: controller)
    monkeypatch.setitem(sys.modules, "pystray", _StubPystray)

    assert tray_module.launch_tray() == 0
    assert controller.ensure_service_running_calls == 2
    assert controller.ensure_command_watcher_running_calls == 2
    assert controller.shutdown_calls == 1
    assert controller.release_calls == 1
