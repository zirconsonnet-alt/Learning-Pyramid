from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath

from backend.models.enums import MaterialSourceKind
from backend.models.errors import NotFound, PreconditionFailure
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthStore
from backend.system.desktop_agent_setup_code import encode_desktop_agent_setup_code


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _setup_ttl_minutes() -> int:
    from os import getenv

    raw = (getenv("PLM_DESKTOP_AGENT_SETUP_TTL_MINUTES") or "15").strip()
    try:
        value = int(raw)
    except Exception as exc:
        raise PreconditionFailure("PLM_DESKTOP_AGENT_SETUP_TTL_MINUTES must be an integer") from exc
    return max(1, value)


@dataclass(frozen=True, slots=True)
class DesktopAgentSetupSession:
    setup_token: str
    user_id: str
    server_url: str
    created_at: str
    expires_at: str
    preferred_project_id: str | None = None
    pairing_code: str | None = None
    pairing_expires_at: str | None = None


def _normalize_candidate_relative_path(value: str | None) -> str | None:
    text = str(value or "").strip().replace("\\", "/")
    if not text or text == ".":
        return ""
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts:
        return None
    return path.as_posix()


def _candidate_root_item(
    relative_path: str | None,
    *,
    label: str | None = None,
    source_root_label: str | None = None,
) -> dict[str, str | None]:
    normalized_relative_path = _normalize_candidate_relative_path(relative_path)
    if normalized_relative_path is None:
        raise PreconditionFailure("desktop agent setup candidate root relative path is invalid")
    display_label = str(label).strip() if label is not None else PurePosixPath(normalized_relative_path).name or "默认根目录"
    if not display_label:
        display_label = normalized_relative_path or "默认根目录"
    return {
        "rootKey": normalized_relative_path or ".",
        "relativePath": normalized_relative_path,
        "label": display_label,
        "sourceRootLabel": None if source_root_label is None else str(source_root_label).strip() or None,
    }


def _collect_project_candidate_roots(api: SystemAPI, project_id: str) -> list[dict[str, str | None]]:
    binding = api.get_project_material_source_binding(project_id)  # type: ignore[arg-type]
    items: list[dict[str, str | None]] = []
    seen: set[str] = set()

    def _append(relative_path: str | None, *, label: str | None = None, source_root_label: str | None = None) -> None:
        normalized_relative_path = _normalize_candidate_relative_path(relative_path)
        if normalized_relative_path is None:
            return
        root_key = normalized_relative_path or "."
        if root_key in seen:
            return
        seen.add(root_key)
        items.append(_candidate_root_item(normalized_relative_path, label=label, source_root_label=source_root_label))

    _append("", label="默认根目录")
    if binding.source_root_label:
        _append(
            str(binding.source_root_label),
            label=str(binding.source_root_label),
            source_root_label=str(binding.source_root_label),
        )

    try:
        instances = api.list_instances(project_id)  # type: ignore[arg-type]
    except Exception:
        instances = ()
    for instance in instances:
        material_id = PurePosixPath(str(instance.material_id))
        if material_id.parts:
            first_part = str(material_id.parts[0]).strip()
            if first_part and first_part not in {".", ".."}:
                _append(first_part, label=first_part, source_root_label=first_part)

    return items


def collect_desktop_agent_setup_catalog(user_id: str, *, auth_store: AuthStore, api: SystemAPI) -> dict[str, object]:
    allowed = set(auth_store.list_project_ids_for_user(user_id))
    projects = []
    for project in api.list_projects():
        project_id = str(project.project_id)
        project_state = getattr(project.state, "value", str(project.state))
        if project_id not in allowed or str(project_state) != "ACTIVE":
            continue
        binding = api.get_project_material_source_binding(project.project_id)
        storage = api.get_project_storage_config(project.project_id)
        projects.append(
            {
                "projectId": project_id,
                "title": str(project.title),
                "state": str(project.state),
                "projectRoot": storage.project_root.as_posix(),
                "learningObjectRoot": storage.learning_object_root.as_posix(),
                "sourceKind": str(binding.source_kind),
                "desktopAgentId": None if binding.desktop_agent_id is None else str(binding.desktop_agent_id),
                "sourceRootLabel": binding.source_root_label,
                "candidateRoots": _collect_project_candidate_roots(api, project_id),
            }
        )
    projects.sort(key=lambda item: (str(item["title"]).lower(), str(item["projectId"])))
    return {
        "projectCount": len(projects),
        "projects": projects,
    }


class DesktopAgentSetupManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, DesktopAgentSetupSession] = {}

    def _prune_locked(self, *, now: datetime) -> None:
        expired = [
            token
            for token, session in self._sessions.items()
            if datetime.fromisoformat(session.expires_at) <= now
        ]
        for token in expired:
            self._sessions.pop(token, None)

    def create_session(
        self,
        *,
        user_id: str,
        server_url: str,
        preferred_project_id: str | None = None,
    ) -> dict[str, str | None]:
        now = _utc_now()
        expires_at = now + timedelta(minutes=_setup_ttl_minutes())
        session = DesktopAgentSetupSession(
            setup_token=secrets.token_urlsafe(24),
            user_id=str(user_id),
            server_url=str(server_url).strip().rstrip("/"),
            created_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
            preferred_project_id=None if preferred_project_id is None else str(preferred_project_id).strip() or None,
        )
        with self._lock:
            self._prune_locked(now=now)
            self._sessions[session.setup_token] = session
        return {
            "setupCode": encode_desktop_agent_setup_code(server_url=session.server_url, setup_token=session.setup_token),
            "expiresAt": session.expires_at,
            "preferredProjectId": session.preferred_project_id,
        }

    def _require_session(self, setup_token: str) -> DesktopAgentSetupSession:
        normalized = str(setup_token).strip()
        if not normalized:
            raise NotFound("desktop_agent_setup_session")
        now = _utc_now()
        with self._lock:
            self._prune_locked(now=now)
            session = self._sessions.get(normalized)
            if session is None:
                raise NotFound("desktop_agent_setup_session")
            if datetime.fromisoformat(session.expires_at) <= now:
                self._sessions.pop(normalized, None)
                raise PreconditionFailure("desktop agent setup session expired")
            return session

    def bootstrap(self, setup_token: str, *, auth_store: AuthStore, api: SystemAPI) -> dict[str, object]:
        session = self._require_session(setup_token)
        now = _utc_now()
        next_session = session
        pairing_expired = session.pairing_expires_at is None or datetime.fromisoformat(session.pairing_expires_at) <= now
        if session.pairing_code is None or pairing_expired:
            pairing = auth_store.create_desktop_agent_pairing_code(session.user_id)
            next_session = replace(
                session,
                pairing_code=pairing.pairing_code,
                pairing_expires_at=pairing.expires_at,
            )
            with self._lock:
                self._sessions[session.setup_token] = next_session
        catalog = collect_desktop_agent_setup_catalog(session.user_id, auth_store=auth_store, api=api)
        return {
            "serverUrl": next_session.server_url,
            "setupToken": next_session.setup_token,
            "expiresAt": next_session.expires_at,
            "pairingCode": next_session.pairing_code,
            "pairingExpiresAt": next_session.pairing_expires_at,
            "preferredProjectId": next_session.preferred_project_id,
            **catalog,
        }

    def finalize(
        self,
        setup_token: str,
        *,
        auth_store: AuthStore,
        api: SystemAPI,
        agent_id: str,
        project_id: str,
        source_root_label: str | None,
    ) -> dict[str, object]:
        session = self._require_session(setup_token)
        normalized_agent_id = str(agent_id).strip()
        normalized_project_id = str(project_id).strip()
        if not normalized_agent_id:
            raise PreconditionFailure("agent_id must be non-empty")
        if not normalized_project_id:
            raise PreconditionFailure("project_id must be non-empty")
        if not auth_store.user_has_desktop_agent(session.user_id, normalized_agent_id):
            raise PreconditionFailure("desktop agent setup session does not own this agent")
        if not auth_store.user_has_project_access(session.user_id, normalized_project_id):
            raise PreconditionFailure("desktop agent setup session does not own this project")
        normalized_label = None if source_root_label is None else str(source_root_label).strip() or None
        api.set_project_material_source_binding(  # type: ignore[arg-type]
            normalized_project_id,
            source_kind=MaterialSourceKind.DESKTOP_AGENT_MANIFEST,
            desktop_agent_id=normalized_agent_id,
            source_root_label=normalized_label,
        )
        return {
            "projectId": normalized_project_id,
            "agentId": normalized_agent_id,
            "sourceRootLabel": normalized_label,
        }
