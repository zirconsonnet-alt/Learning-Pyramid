from __future__ import annotations

from pathlib import Path

import pytest

from backend.system.version import APP_VERSION
from desktop_agent.autostart import AutostartManager
from desktop_agent.config_store import AgentConfig, AgentUpdateState, ConfigStore
from desktop_agent.instance_lock import SingleInstanceLock
from desktop_agent.setup_client import (
    DesktopAgentSetupBootstrap,
    DesktopAgentSetupCandidateRoot,
    DesktopAgentSetupProject,
)
from desktop_agent.ui import DesktopAgentUiController
from desktop_agent.ui import _friendly_setup_error_message
from desktop_agent.updater import DesktopAgentPreparedUpdate, DesktopAgentSilentInstallPlan, DesktopAgentUpdateCheckResult


def test_autostart_manager_writes_and_removes_startup_script(tmp_path: Path) -> None:
    manager = AutostartManager(tmp_path)
    script_path = manager.enable(["C:\\Agent\\LearningPyramidDesktopAgent.exe", "run"])

    assert script_path.exists()
    assert script_path.suffix == ".vbs"
    content = script_path.read_text(encoding="utf-8")
    assert 'CreateObject("WScript.Shell")' in content
    assert 'WshShell.Run' in content
    assert 'C:\\Agent\\LearningPyramidDesktopAgent.exe' in content
    assert " run" in content
    assert manager.is_enabled() is True

    manager.disable()
    assert manager.is_enabled() is False


def test_ui_controller_load_saved_config_refreshes_app_version(tmp_path: Path) -> None:
    config_store = ConfigStore(tmp_path / "config")
    config_store.save(
        AgentConfig(
            server_url="http://127.0.0.1:8000",
            agent_id="agent_123",
            agent_token="agent-token-1",
            refresh_token="refresh-token-1",
            project_id="proj_123",
            root_dir=str(tmp_path.resolve()),
            device_name="BYLOU-PC",
            app_version="0.1.0-beta.0",
        )
    )

    controller = DesktopAgentUiController(
        config_store=config_store,
        autostart_manager=AutostartManager(tmp_path / "startup"),
    )

    config = controller.load_saved_config()

    assert config is not None
    assert config.app_version == APP_VERSION
    assert config_store.load().app_version == APP_VERSION


def test_ui_controller_auto_update_defaults_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PLM_AGENT_AUTO_UPDATE", raising=False)
    controller = DesktopAgentUiController(
        config_store=ConfigStore(tmp_path / "config"),
        autostart_manager=AutostartManager(tmp_path / "startup"),
    )

    assert controller.auto_update_enabled() is True


def test_ui_controller_pairs_saves_config_and_updates_autostart(tmp_path: Path) -> None:
    startup_dir = tmp_path / "startup"
    config_store = ConfigStore(tmp_path / "config")
    controller = DesktopAgentUiController(
        config_store=config_store,
        autostart_manager=AutostartManager(startup_dir),
        pair_request=lambda **_: {
            "agentId": "agent_123",
            "agentToken": "agent-token-1",
            "refreshToken": "refresh-token-1",
        },
        launch_command_factory=lambda: ["C:\\Agent\\LearningPyramidDesktopAgent.exe", "run"],
    )
    media_root = tmp_path / "media"
    media_root.mkdir()

    config = controller.pair_and_save(
        server_url="http://127.0.0.1:8000/",
        pairing_code="abcd-efgh",
        project_id="proj_123",
        root_dir=str(media_root),
        device_name="BYLOU-PC",
        app_version="0.1.0",
        source_root_label="Videos",
    )

    assert config.server_url == "http://127.0.0.1:8000"
    assert config.agent_id == "agent_123"
    assert config.project_id == "proj_123"
    assert config.root_dir == str(media_root.resolve())
    assert config_store.load().agent_token == "agent-token-1"

    controller.set_autostart(True)
    assert controller.autostart_enabled() is True
    assert controller.autostart_manager.script_path.exists()

    controller.set_autostart(False)
    assert controller.autostart_enabled() is False


def test_ui_controller_rejects_non_project_id_values(tmp_path: Path) -> None:
    controller = DesktopAgentUiController(
        config_store=ConfigStore(tmp_path / "config"),
        autostart_manager=AutostartManager(tmp_path / "startup"),
        pair_request=lambda **_: {
            "agentId": "agent_123",
            "agentToken": "agent-token-1",
            "refreshToken": "refresh-token-1",
        },
    )
    media_root = tmp_path / "media"
    media_root.mkdir()

    try:
        controller.pair_and_save(
            server_url="https://plm.xuebao.chat",
            pairing_code="abcd-efgh",
            project_id="ML",
            root_dir=str(media_root),
            device_name="BYLOU-PC",
            app_version="0.1.0",
            source_root_label="Videos",
        )
    except ValueError as exc:
        assert "proj_000001" in str(exc)
    else:
        raise AssertionError("expected pair_and_save to reject non-project IDs")


def test_ui_controller_setup_code_flow_pairs_finalizes_and_saves(tmp_path: Path) -> None:
    config_store = ConfigStore(tmp_path / "config")
    media_root = tmp_path / "workspace" / "ML" / "learning_objects" / "videos"
    media_root.mkdir(parents=True)
    completed: list[dict[str, object]] = []

    bootstrap = DesktopAgentSetupBootstrap(
        server_url="https://plm.xuebao.chat",
        setup_token="setup-token-1",
        expires_at="2026-03-12T08:00:00+00:00",
        pairing_code="WAFS-ACLK",
        pairing_expires_at="2026-03-12T08:10:00+00:00",
        preferred_project_id="proj_123",
        projects=(
            DesktopAgentSetupProject(
                project_id="proj_123",
                title="ML",
                state="ACTIVE",
                project_root="ML",
                learning_object_root="learning_objects",
                source_kind="SERVER_FS",
                desktop_agent_id=None,
                source_root_label=None,
                candidate_roots=(
                    DesktopAgentSetupCandidateRoot(
                        root_key="videos",
                        relative_path="videos",
                        label="videos",
                        source_root_label="videos",
                    ),
                ),
            ),
        ),
    )

    controller = DesktopAgentUiController(
        config_store=config_store,
        autostart_manager=AutostartManager(tmp_path / "startup"),
        pair_request=lambda **_: {
            "agentId": "agent_123",
            "agentToken": "agent-token-1",
            "refreshToken": "refresh-token-1",
        },
        setup_bootstrap_request=lambda _: bootstrap,
        setup_complete_request=lambda **kwargs: completed.append(dict(kwargs)) or {"ok": True},
    )

    loaded = controller.load_setup_bootstrap("LPDA1.fake")
    candidates = controller.list_candidate_roots(loaded.projects[0])
    config = controller.setup_and_save(
        setup_code="LPDA1.fake",
        bootstrap=loaded,
        project_id="proj_123",
        candidate_root_key=candidates[0].root_key,
        root_dir=str(media_root),
        device_name="BYLOU-PC",
        app_version="0.1.0",
    )

    assert config.server_url == "https://plm.xuebao.chat"
    assert config.project_id == "proj_123"
    assert config.root_dir == str(media_root.resolve())
    assert config.source_root_label == "videos"
    assert config_store.load().agent_token == "agent-token-1"
    mapping = config_store.load_directory_mapping(
        server_url="https://plm.xuebao.chat",
        project_id="proj_123",
        root_key="videos",
    )
    assert mapping is not None
    assert mapping.root_dir == str(media_root.resolve())
    assert completed == [
        {
            "setup_code": "LPDA1.fake",
            "server_url": "https://plm.xuebao.chat",
            "agent_id": "agent_123",
            "project_id": "proj_123",
            "source_root_label": "videos",
        }
    ]


def test_ui_controller_setup_code_flow_requests_restart_for_running_tray(tmp_path: Path) -> None:
    config_store = ConfigStore(tmp_path / "config")
    media_root = tmp_path / "workspace" / "ML" / "learning_objects" / "videos"
    media_root.mkdir(parents=True)
    bootstrap = DesktopAgentSetupBootstrap(
        server_url="https://plm.xuebao.chat",
        setup_token="setup-token-1",
        expires_at="2026-03-12T08:00:00+00:00",
        pairing_code="WAFS-ACLK",
        pairing_expires_at="2026-03-12T08:10:00+00:00",
        preferred_project_id="proj_123",
        projects=(
            DesktopAgentSetupProject(
                project_id="proj_123",
                title="ML",
                state="ACTIVE",
                project_root="ML",
                learning_object_root="learning_objects",
                source_kind="SERVER_FS",
                desktop_agent_id=None,
                source_root_label=None,
                candidate_roots=(
                    DesktopAgentSetupCandidateRoot(
                        root_key="videos",
                        relative_path="videos",
                        label="videos",
                        source_root_label="videos",
                    ),
                ),
            ),
        ),
    )
    running_tray_lock = SingleInstanceLock(config_store.tray_lock_path)
    assert running_tray_lock.acquire() is True
    try:
        controller = DesktopAgentUiController(
            config_store=config_store,
            autostart_manager=AutostartManager(tmp_path / "startup"),
            pair_request=lambda **_: {
                "agentId": "agent_123",
                "agentToken": "agent-token-1",
                "refreshToken": "refresh-token-1",
            },
            setup_bootstrap_request=lambda _: bootstrap,
            setup_complete_request=lambda **kwargs: {"ok": True},
        )

        controller.setup_and_save(
            setup_code="LPDA1.fake",
            bootstrap=bootstrap,
            project_id="proj_123",
            candidate_root_key="videos",
            root_dir=str(media_root),
            device_name="BYLOU-PC",
            app_version="0.1.0",
        )

        command = config_store.load_service_command()
        assert command is not None
        assert command.action == "restart"
        assert command.reason == "setup_saved"
    finally:
        running_tray_lock.release()


def test_ui_controller_loads_saved_root_dir_for_candidate(tmp_path: Path) -> None:
    config_store = ConfigStore(tmp_path / "config")
    media_root = tmp_path / "workspace" / "ML" / "learning_objects" / "videos"
    media_root.mkdir(parents=True)
    config_store.save_directory_mapping(
        server_url="https://plm.xuebao.chat",
        project_id="proj_123",
        root_key="videos",
        root_dir=str(media_root),
        source_root_label="videos",
    )
    controller = DesktopAgentUiController(
        config_store=config_store,
        autostart_manager=AutostartManager(tmp_path / "startup"),
    )
    candidate_root = DesktopAgentSetupCandidateRoot(
        root_key="videos",
        relative_path="videos",
        label="videos",
        source_root_label="videos",
    )

    root_dir = controller.load_saved_root_dir(
        server_url="https://plm.xuebao.chat",
        project_id="proj_123",
        candidate_root=candidate_root,
    )

    assert root_dir == str(media_root.resolve())


def test_ui_controller_builds_saved_project_catalog(tmp_path: Path) -> None:
    config_store = ConfigStore(tmp_path / "config")
    media_root = tmp_path / "workspace" / "ML" / "learning_objects" / "videos"
    media_root.mkdir(parents=True)
    config_store.save(
        AgentConfig(
            server_url="https://plm.xuebao.chat",
            agent_id="agent_123",
            agent_token="agent-token-1",
            refresh_token="refresh-token-1",
            project_id="proj_000004",
            root_dir=str(media_root),
            device_name="BYLOU-PC",
            source_root_label="videos",
        )
    )
    controller = DesktopAgentUiController(
        config_store=config_store,
        autostart_manager=AutostartManager(tmp_path / "startup"),
    )

    saved_catalog = controller.build_saved_project_catalog()

    assert saved_catalog is not None
    server_url, projects, preferred_project_id = saved_catalog
    assert server_url == "https://plm.xuebao.chat"
    assert preferred_project_id == "proj_000004"
    assert len(projects) == 1
    assert projects[0].project_id == "proj_000004"
    assert projects[0].title == "已保存项目"
    assert len(projects[0].candidate_roots) == 1
    assert projects[0].candidate_roots[0].label == "videos"
    assert projects[0].candidate_roots[0].source_root_label == "videos"


def test_ui_controller_start_agent_requests_restart_when_tray_already_running(tmp_path: Path) -> None:
    launched: list[tuple[list[str], dict[str, object]]] = []
    config_store = ConfigStore(tmp_path / "config")
    config_store.save(
        AgentConfig(
            server_url="https://plm.xuebao.chat",
            agent_id="agent_123",
            agent_token="agent-token-1",
            refresh_token="refresh-token-1",
            project_id="proj_123",
            root_dir=str(tmp_path.resolve()),
            device_name="BYLOU-PC",
        )
    )
    running_tray_lock = SingleInstanceLock(config_store.tray_lock_path)
    assert running_tray_lock.acquire() is True
    try:
        controller = DesktopAgentUiController(
            config_store=config_store,
            autostart_manager=AutostartManager(tmp_path / "startup"),
            process_launcher=lambda command, **kwargs: launched.append((command, kwargs)),
        )

        controller.start_agent_process()

        assert launched == []
        command = config_store.load_service_command()
        assert command is not None
        assert command.action == "restart"
        assert command.reason == "manual_start_requested"
    finally:
        running_tray_lock.release()


def test_friendly_setup_error_message_suggests_regenerating_setup_code() -> None:
    message = _friendly_setup_error_message(Exception("400 Client Error: pairing code already used for url: https://plm.xuebao.chat/api/desktop-agents/pair"))

    assert "pairing code already used" in message
    assert "重新生成新的接入码" in message


def test_ui_controller_checks_for_updates(tmp_path: Path) -> None:
    controller = DesktopAgentUiController(
        config_store=ConfigStore(tmp_path / "config"),
        autostart_manager=AutostartManager(tmp_path / "startup"),
        updater=type(
            "StubUpdater",
            (),
            {
                "check_for_updates": staticmethod(
                    lambda *, server_url, current_version: DesktopAgentUpdateCheckResult(
                        available=True,
                        update_available=True,
                        current_version=current_version,
                        latest_version="0.1.0-beta.2",
                        download_url="https://learn.example.com/download/agent-setup.exe",
                        published_at="2026-03-11T12:00:00+00:00",
                        asset_name="agent-setup.exe",
                        asset_kind="installer_exe",
                        signature_status="SIGNED",
                        silent_install_supported=True,
                        silent_install_strategy="inno_exe",
                    )
                )
            },
        )(),
    )

    result = controller.check_for_updates(server_url="https://learn.example.com/", current_version="0.1.0-beta.1")

    assert result.update_available is True
    assert result.latest_version == "0.1.0-beta.2"
    assert result.download_url == "https://learn.example.com/download/agent-setup.exe"
    assert result.silent_install_supported is True


def test_qt_theme_scopes_background_to_top_level_windows() -> None:
    theme_source = (Path(__file__).resolve().parents[1] / "desktop_agent" / "ui_qt" / "theme.py").read_text(encoding="utf-8")

    assert "QWidget#AppRoot {" in theme_source
    assert "QDialog," in theme_source
    assert "QWidget {\n    background:" not in theme_source


def test_qt_theme_uses_cjk_friendly_font_stack_and_roomier_controls() -> None:
    theme_source = (Path(__file__).resolve().parents[1] / "desktop_agent" / "ui_qt" / "theme.py").read_text(encoding="utf-8")

    assert '"Microsoft YaHei UI"' in theme_source
    assert "QLabel[role=\"title\"]" in theme_source
    assert "min-height: 48px;" in theme_source
    assert "QPushButton {" in theme_source
    assert "min-height: 40px;" in theme_source
    assert "QCheckBox::indicator {" in theme_source


def test_ui_controller_installs_update_silently(tmp_path: Path) -> None:
    launched: list[tuple[list[str], dict[str, object]]] = []

    class StubUpdater:
        prepare_calls: list[tuple[str, str, Path, bool]] = []
        build_calls: list[tuple[str, int, Path, bool]] = []

        def prepare_update(self, *, server_url: str, current_version: str, target_dir, require_signed: bool):
            target = Path(target_dir)
            StubUpdater.prepare_calls.append((server_url, current_version, target, require_signed))
            target.mkdir(parents=True, exist_ok=True)
            asset_path = target / "agent-setup.exe"
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
            helper = target / "apply.ps1"
            helper.write_text("Write-Host update", encoding="utf-8")
            return DesktopAgentSilentInstallPlan(
                command=("powershell", "-File", str(helper)),
                helper_script_path=helper,
                rollback_script_path=target / "rollback.ps1",
                state_path=target / "update-state.json",
                backup_dir=target / "backup-current",
                log_path=target / "apply.log",
                relaunch_exe_path=target / "LearningPyramidDesktopAgent.exe",
            )

    controller = DesktopAgentUiController(
        config_store=ConfigStore(tmp_path / "config"),
        autostart_manager=AutostartManager(tmp_path / "startup"),
        updater=StubUpdater(),
        process_launcher=lambda command, **kwargs: launched.append((command, kwargs)),
    )

    latest_version = controller.install_update(
        server_url="https://learn.example.com/",
        current_version="0.1.0-beta.1",
        current_pid=4321,
    )

    assert latest_version == "0.1.0-beta.2"
    assert StubUpdater.prepare_calls == [("https://learn.example.com", "0.1.0-beta.1", controller.config_store.base_dir / "updates", False)]
    assert StubUpdater.build_calls == [("0.1.0-beta.2", 4321, controller.config_store.base_dir / "updates", True)]
    assert len(launched) == 1
    command, kwargs = launched[0]
    assert command == ["powershell", "-File", str(controller.config_store.base_dir / "updates" / "apply.ps1")]
    assert isinstance(kwargs.get("close_fds"), bool)
    assert isinstance(kwargs.get("creationflags"), int)


def test_ui_controller_rolls_back_last_update(tmp_path: Path) -> None:
    launched: list[tuple[list[str], dict[str, object]]] = []
    config_store = ConfigStore(tmp_path / "config")
    rollback_path = config_store.updates_dir / "rollback.ps1"
    backup_dir = config_store.updates_dir / "backup-current"
    rollback_path.parent.mkdir(parents=True, exist_ok=True)
    rollback_path.write_text("Write-Host rollback", encoding="utf-8")
    backup_dir.mkdir(parents=True, exist_ok=True)
    config_store.save_update_state(
        AgentUpdateState(
            status="SUCCEEDED",
            current_version=APP_VERSION,
            target_version="0.1.0-beta.2",
            installed_version="0.1.0-beta.2",
            backup_dir=str(backup_dir),
            rollback_script_path=str(rollback_path),
        )
    )
    controller = DesktopAgentUiController(
        config_store=config_store,
        autostart_manager=AutostartManager(tmp_path / "startup"),
        process_launcher=lambda command, **kwargs: launched.append((command, kwargs)),
    )

    version_hint = controller.rollback_last_update(current_pid=222)

    assert version_hint == APP_VERSION
    assert len(launched) == 1
    command, kwargs = launched[0]
    assert command == [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(rollback_path),
        "-WaitPid",
        "222",
        "-Relaunch",
    ]
    assert isinstance(kwargs.get("close_fds"), bool)
    assert isinstance(kwargs.get("creationflags"), int)
