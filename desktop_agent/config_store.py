from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from backend.system.version import APP_VERSION


def _default_config_dir() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata).expanduser().resolve() / "LearningPyramidDesktopAgent"
    return Path.home().resolve() / ".learningpyramid-desktop-agent"


@dataclass
class AgentConfig:
    server_url: str
    agent_id: str
    agent_token: str
    refresh_token: str
    project_id: str
    root_dir: str
    device_name: str
    platform: str = "windows"
    app_version: str = APP_VERSION
    source_root_label: str | None = None


@dataclass
class AgentUpdateState:
    status: str = "IDLE"
    message: str | None = None
    current_version: str | None = None
    target_version: str | None = None
    installed_version: str | None = None
    updated_at: str | None = None
    log_path: str | None = None
    backup_dir: str | None = None
    rollback_script_path: str | None = None
    asset_path: str | None = None
    asset_kind: str | None = None
    relaunch_exe_path: str | None = None


@dataclass
class AgentDirectoryMapping:
    server_url: str
    project_id: str
    root_key: str
    root_dir: str
    source_root_label: str | None = None
    updated_at: str | None = None


@dataclass
class AgentServiceCommand:
    action: str
    reason: str | None = None
    requested_at: str | None = None


class ConfigStore:
    def __init__(self, base_dir: Path | str | None = None) -> None:
        self.base_dir = Path(base_dir or _default_config_dir()).resolve()
        self.path = self.base_dir / "agent.json"
        self.directory_mappings_path = self.base_dir / "directory-mappings.json"
        self.service_command_path = self.base_dir / "service-command.json"
        self.updates_dir = self.base_dir / "updates"
        self.update_state_path = self.updates_dir / "update-state.json"
        self.logs_dir = self.base_dir / "logs"
        self.log_path = self.logs_dir / "desktop-agent.log"
        self.tray_lock_path = self.base_dir / "tray.lock"

    def load(self) -> AgentConfig:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return AgentConfig(**raw)

    def save(self, config: AgentConfig) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")

    def exists(self) -> bool:
        return self.path.exists()

    def load_directory_mappings(self) -> tuple[AgentDirectoryMapping, ...]:
        if not self.directory_mappings_path.exists():
            return ()
        raw = json.loads(self.directory_mappings_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            return ()
        items: list[AgentDirectoryMapping] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                items.append(
                    AgentDirectoryMapping(
                        server_url=str(entry.get("server_url") or "").strip().rstrip("/"),
                        project_id=str(entry.get("project_id") or "").strip(),
                        root_key=str(entry.get("root_key") or "").strip() or ".",
                        root_dir=str(entry.get("root_dir") or "").strip(),
                        source_root_label=None
                        if entry.get("source_root_label") is None
                        else str(entry.get("source_root_label") or "").strip() or None,
                        updated_at=None if entry.get("updated_at") is None else str(entry.get("updated_at") or "").strip() or None,
                    )
                )
            except Exception:
                continue
        return tuple(
            item
            for item in items
            if item.server_url and item.project_id and item.root_key and item.root_dir
        )

    def save_directory_mappings(self, mappings: tuple[AgentDirectoryMapping, ...] | list[AgentDirectoryMapping]) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        payload = [asdict(item) for item in mappings]
        self.directory_mappings_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_directory_mapping(
        self,
        *,
        server_url: str,
        project_id: str,
        root_key: str,
    ) -> AgentDirectoryMapping | None:
        normalized_server_url = str(server_url).strip().rstrip("/")
        normalized_project_id = str(project_id).strip()
        normalized_root_key = str(root_key).strip() or "."
        for item in self.load_directory_mappings():
            if (
                item.server_url == normalized_server_url
                and item.project_id == normalized_project_id
                and item.root_key == normalized_root_key
            ):
                return item
        return None

    def save_directory_mapping(
        self,
        *,
        server_url: str,
        project_id: str,
        root_key: str,
        root_dir: str,
        source_root_label: str | None = None,
    ) -> AgentDirectoryMapping:
        normalized_server_url = str(server_url).strip().rstrip("/")
        normalized_project_id = str(project_id).strip()
        normalized_root_key = str(root_key).strip() or "."
        normalized_root_dir = str(Path(root_dir).expanduser().resolve())
        normalized_source_root_label = None if source_root_label is None else str(source_root_label).strip() or None
        mapping = AgentDirectoryMapping(
            server_url=normalized_server_url,
            project_id=normalized_project_id,
            root_key=normalized_root_key,
            root_dir=normalized_root_dir,
            source_root_label=normalized_source_root_label,
            updated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )
        items = [
            item
            for item in self.load_directory_mappings()
            if not (
                item.server_url == normalized_server_url
                and item.project_id == normalized_project_id
                and item.root_key == normalized_root_key
            )
        ]
        items.append(mapping)
        items.sort(key=lambda item: (item.server_url, item.project_id, item.root_key))
        self.save_directory_mappings(items)
        return mapping

    def load_service_command(self) -> AgentServiceCommand | None:
        if not self.service_command_path.exists():
            return None
        raw = json.loads(self.service_command_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None
        action = str(raw.get("action") or "").strip().lower()
        if not action:
            return None
        return AgentServiceCommand(
            action=action,
            reason=None if raw.get("reason") is None else str(raw.get("reason") or "").strip() or None,
            requested_at=None if raw.get("requested_at") is None else str(raw.get("requested_at") or "").strip() or None,
        )

    def save_service_command(self, command: AgentServiceCommand) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.service_command_path.write_text(json.dumps(asdict(command), ensure_ascii=False, indent=2), encoding="utf-8")

    def request_service_restart(self, *, reason: str | None = None) -> AgentServiceCommand:
        command = AgentServiceCommand(
            action="restart",
            reason=None if reason is None else str(reason).strip() or None,
            requested_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )
        self.save_service_command(command)
        return command

    def consume_service_command(self) -> AgentServiceCommand | None:
        command = self.load_service_command()
        if command is None:
            return None
        try:
            self.service_command_path.unlink()
        except FileNotFoundError:
            pass
        return command

    def load_update_state(self) -> AgentUpdateState | None:
        if not self.update_state_path.exists():
            return None
        raw = json.loads(self.update_state_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None
        return AgentUpdateState(**raw)

    def save_update_state(self, state: AgentUpdateState) -> None:
        self.updates_dir.mkdir(parents=True, exist_ok=True)
        self.update_state_path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")

    def ensure_app_version(self, app_version: str = APP_VERSION) -> AgentConfig | None:
        if not self.exists():
            return None
        config = self.load()
        normalized = str(app_version).strip() or APP_VERSION
        if str(config.app_version).strip() == normalized:
            return config
        config.app_version = normalized
        self.save(config)
        return config
