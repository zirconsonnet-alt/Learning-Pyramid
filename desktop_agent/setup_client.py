from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import requests

from backend.models.errors import PreconditionFailure
from backend.system.desktop_agent_setup_code import decode_desktop_agent_setup_code
from desktop_agent.relay_client import _raise_for_agent_response


@dataclass(frozen=True, slots=True)
class DesktopAgentSetupCandidateRoot:
    root_key: str
    relative_path: str
    label: str
    source_root_label: str | None


@dataclass(frozen=True, slots=True)
class DesktopAgentSetupProject:
    project_id: str
    title: str
    state: str
    project_root: str
    learning_object_root: str
    source_kind: str
    desktop_agent_id: str | None
    source_root_label: str | None
    candidate_roots: tuple[DesktopAgentSetupCandidateRoot, ...]


@dataclass(frozen=True, slots=True)
class DesktopAgentSetupBootstrap:
    server_url: str
    setup_token: str
    expires_at: str
    pairing_code: str
    pairing_expires_at: str
    preferred_project_id: str | None
    projects: tuple[DesktopAgentSetupProject, ...]

def fetch_desktop_agent_setup_bootstrap(
    setup_code: str,
    *,
    request_get: Callable[..., requests.Response] = requests.get,
    timeout_seconds: float = 30.0,
) -> DesktopAgentSetupBootstrap:
    decoded = decode_desktop_agent_setup_code(setup_code)
    response = request_get(
        f"{decoded.server_url}/api/desktop-agents/setup-bootstrap",
        params={"setupCode": str(setup_code).strip()},
        timeout=timeout_seconds,
    )
    _raise_for_agent_response(response)
    payload = response.json()["data"]
    projects = tuple(
        DesktopAgentSetupProject(
            project_id=str(item["projectId"]),
            title=str(item["title"]),
            state=str(item["state"]),
            project_root=str(item["projectRoot"]),
            learning_object_root=str(item["learningObjectRoot"]),
            source_kind=str(item["sourceKind"]),
            desktop_agent_id=None if item.get("desktopAgentId") is None else str(item["desktopAgentId"]),
            source_root_label=None if item.get("sourceRootLabel") is None else str(item["sourceRootLabel"]),
            candidate_roots=tuple(
                _parse_candidate_root_payload(root)
                for root in item.get("candidateRoots", [])
            ),
        )
        for item in payload.get("projects", [])
    )
    pairing_code = str(payload.get("pairingCode") or "").strip()
    pairing_expires_at = str(payload.get("pairingExpiresAt") or "").strip()
    if not pairing_code or not pairing_expires_at:
        raise PreconditionFailure("desktop agent setup bootstrap pairing code is missing")
    return DesktopAgentSetupBootstrap(
        server_url=str(payload.get("serverUrl") or decoded.server_url).strip().rstrip("/"),
        setup_token=str(payload.get("setupToken") or decoded.setup_token).strip(),
        expires_at=str(payload.get("expiresAt") or "").strip(),
        pairing_code=pairing_code,
        pairing_expires_at=pairing_expires_at,
        preferred_project_id=None if payload.get("preferredProjectId") is None else str(payload["preferredProjectId"]),
        projects=projects,
    )


def complete_desktop_agent_setup(
    *,
    setup_code: str,
    server_url: str,
    agent_id: str,
    project_id: str,
    source_root_label: str | None,
    request_post: Callable[..., requests.Response] = requests.post,
    timeout_seconds: float = 30.0,
) -> dict[str, object]:
    response = request_post(
        f"{str(server_url).strip().rstrip('/')}/api/desktop-agents/setup-complete",
        json={
            "setupCode": str(setup_code).strip(),
            "agentId": str(agent_id).strip(),
            "projectId": str(project_id).strip(),
            "sourceRootLabel": None if source_root_label is None else str(source_root_label).strip() or None,
        },
        timeout=timeout_seconds,
    )
    _raise_for_agent_response(response)
    return dict(response.json()["data"])


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
