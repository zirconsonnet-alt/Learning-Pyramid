from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import requests

from desktop_agent.relay_client import _raise_for_agent_response
from desktop_agent.setup_client import (
    DesktopAgentSetupCandidateRoot,
    DesktopAgentSetupProject,
)


@dataclass(frozen=True, slots=True)
class DesktopAgentAccountBootstrap:
    server_url: str
    projects: tuple[DesktopAgentSetupProject, ...]


@dataclass(slots=True)
class DesktopAgentAccountSession:
    server_url: str
    email: str
    http: requests.Session
    bootstrap: DesktopAgentAccountBootstrap


def _parse_candidate_root_payload(payload: object) -> DesktopAgentSetupCandidateRoot:
    root = dict(payload or {})
    relative_path = str(root.get("relativePath") or "").strip().replace("\\", "/")
    legacy_path = str(root.get("path") or "").strip().replace("\\", "/")
    root_key = str(root.get("rootKey") or "").strip()
    if not relative_path and legacy_path and not legacy_path.startswith("/"):
        relative_path = legacy_path
    if not root_key:
        root_key = relative_path or "."
    return DesktopAgentSetupCandidateRoot(
        root_key=root_key,
        relative_path=relative_path,
        label=str(root.get("label") or relative_path or "默认根目录"),
        source_root_label=None if root.get("sourceRootLabel") is None else str(root["sourceRootLabel"]),
    )


def _parse_projects(payload: object) -> tuple[DesktopAgentSetupProject, ...]:
    items = []
    for item in list(payload or []):
        row = dict(item or {})
        items.append(
            DesktopAgentSetupProject(
                project_id=str(row["projectId"]),
                title=str(row["title"]),
                state=str(row["state"]),
                project_root=str(row["projectRoot"]),
                learning_object_root=str(row["learningObjectRoot"]),
                source_kind=str(row["sourceKind"]),
                desktop_agent_id=None if row.get("desktopAgentId") is None else str(row["desktopAgentId"]),
                source_root_label=None if row.get("sourceRootLabel") is None else str(row["sourceRootLabel"]),
                candidate_roots=tuple(_parse_candidate_root_payload(root) for root in row.get("candidateRoots", [])),
            )
        )
    return tuple(items)


def login_desktop_agent_account(
    *,
    server_url: str,
    email: str,
    password: str,
    session_factory: Callable[[], requests.Session] = requests.Session,
    timeout_seconds: float = 30.0,
) -> DesktopAgentAccountSession:
    normalized_server_url = str(server_url).strip().rstrip("/")
    normalized_email = str(email).strip()
    normalized_password = str(password)
    if not normalized_server_url:
        raise ValueError("server_url is required")
    if not normalized_email:
        raise ValueError("email is required")
    if not normalized_password:
        raise ValueError("password is required")
    session = session_factory()
    login_response = session.post(
        f"{normalized_server_url}/api/auth/login",
        json={"email": normalized_email, "password": normalized_password},
        timeout=timeout_seconds,
    )
    _raise_for_agent_response(login_response)
    bootstrap_response = session.get(
        f"{normalized_server_url}/api/desktop-agents/account-bootstrap",
        timeout=timeout_seconds,
    )
    _raise_for_agent_response(bootstrap_response)
    payload = bootstrap_response.json()["data"]
    bootstrap = DesktopAgentAccountBootstrap(
        server_url=str(payload.get("serverUrl") or normalized_server_url).strip().rstrip("/"),
        projects=_parse_projects(payload.get("projects", [])),
    )
    return DesktopAgentAccountSession(
        server_url=bootstrap.server_url,
        email=normalized_email,
        http=session,
        bootstrap=bootstrap,
    )


def account_pair_desktop_agent(
    *,
    account_session: DesktopAgentAccountSession,
    device_name: str,
    app_version: str,
    platform: str = "windows",
    timeout_seconds: float = 30.0,
) -> dict[str, object]:
    response = account_session.http.post(
        f"{account_session.server_url}/api/desktop-agents/account-pair",
        json={
            "deviceName": str(device_name).strip(),
            "platform": str(platform).strip() or "windows",
            "appVersion": str(app_version).strip(),
        },
        timeout=timeout_seconds,
    )
    _raise_for_agent_response(response)
    return dict(response.json()["data"])


def complete_desktop_agent_account_setup(
    *,
    account_session: DesktopAgentAccountSession,
    agent_id: str,
    project_id: str,
    source_root_label: str | None,
    timeout_seconds: float = 30.0,
) -> dict[str, object]:
    response = account_session.http.post(
        f"{account_session.server_url}/api/desktop-agents/account-complete",
        json={
            "agentId": str(agent_id).strip(),
            "projectId": str(project_id).strip(),
            "sourceRootLabel": None if source_root_label is None else str(source_root_label).strip() or None,
        },
        timeout=timeout_seconds,
    )
    _raise_for_agent_response(response)
    return dict(response.json()["data"])
