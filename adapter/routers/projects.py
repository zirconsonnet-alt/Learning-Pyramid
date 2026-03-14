from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from adapter.auth import require_request_auth_user
from adapter.deps import get_api, get_auth_store
from adapter.mappers import (
    audit_log_event_to_dto,
    desktop_agent_to_dto,
    project_config_to_dto,
    project_material_source_binding_to_dto,
    project_storage_config_to_dto,
    project_to_dto,
)
from adapter.schemas import CreateProjectRequest, SetExternalServicesRequest, SetProjectMaterialSourceBindingRequest
from backend.models.project_config import LocalServiceConfig
from backend.models.enums import MaterialSourceKind
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthStore
from backend.system.desktop_agent_presence import desktop_agent_connection_state, effective_desktop_agent_status
from backend.system.desktop_agent_runtime import DesktopAgentRuntime
from backend.system.runtime_features import current_runtime_features
from adapter.deps import get_desktop_agent_runtime


router = APIRouter()


@router.get("/projects")
def list_projects(request: Request, api: SystemAPI = Depends(get_api), auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    items = api.list_projects()
    if current_runtime_features().auth_enabled:
        user = require_request_auth_user(request)
        allowed = set(auth_store.list_project_ids_for_user(user.user_id))
        items = [project for project in items if str(project.project_id) in allowed]
    items = [project_to_dto(p) for p in items]
    return {"ok": True, "data": items}


@router.post("/projects")
def create_project(
    req: CreateProjectRequest,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    pid = api.create_project(req.title)
    if current_runtime_features().auth_enabled:
        user = require_request_auth_user(request)
        auth_store.add_project_owner(pid, user.user_id)
    return {"ok": True, "data": {"projectId": str(pid)}}


@router.delete("/projects/{projectId}")
def delete_project(projectId: str, api: SystemAPI = Depends(get_api), auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    api.delete_project(projectId)  # type: ignore[arg-type]
    if current_runtime_features().auth_enabled:
        auth_store.remove_project_memberships(projectId)
    return {"ok": True, "data": None}


@router.get("/projects/{projectId}/project-config")
def get_project_config(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    cfg = api.get_project_config(projectId)  # type: ignore[arg-type]
    return {"ok": True, "data": project_config_to_dto(cfg)}


@router.post("/projects/{projectId}/external-services")
def set_external_services(projectId: str, req: SetExternalServicesRequest, api: SystemAPI = Depends(get_api)) -> dict:
    api.set_external_services_config(  # type: ignore[arg-type]
        projectId,
        asr=None if req.asr is None else LocalServiceConfig(base_url=req.asr.baseUrl, api_key=req.asr.apiKey, model=req.asr.model),
    )
    return {"ok": True, "data": None}


@router.get("/projects/{projectId}/project-storage-config")
def get_project_storage_config(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    cfg = api.get_project_storage_config(projectId)  # type: ignore[arg-type]
    return {"ok": True, "data": project_storage_config_to_dto(cfg)}


@router.get("/projects/{projectId}/material-source-binding")
def get_project_material_source_binding(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    binding = api.get_project_material_source_binding(projectId)  # type: ignore[arg-type]
    return {"ok": True, "data": project_material_source_binding_to_dto(binding)}


@router.post("/projects/{projectId}/material-source-binding")
def set_project_material_source_binding(
    projectId: str,
    req: SetProjectMaterialSourceBindingRequest,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    if req.desktopAgentId is not None and current_runtime_features().auth_enabled:
        user = require_request_auth_user(request)
        if not auth_store.user_has_desktop_agent(user.user_id, req.desktopAgentId):
            raise HTTPException(status_code=403, detail="Desktop agent access denied")
    api.set_project_material_source_binding(  # type: ignore[arg-type]
        projectId,
        source_kind=MaterialSourceKind(req.sourceKind),
        desktop_agent_id=req.desktopAgentId,
        source_root_label=req.sourceRootLabel,
    )
    return {"ok": True, "data": None}


@router.get("/projects/{projectId}/audit-log-events")
def list_audit_log_events(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    items = [audit_log_event_to_dto(ev) for ev in api.list_audit_log_events(projectId)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}


@router.get("/projects/{projectId}/desktop-agents/status")
def get_project_desktop_agent_status(
    projectId: str,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
    runtime: DesktopAgentRuntime = Depends(get_desktop_agent_runtime),
) -> dict:
    binding = api.get_project_material_source_binding(projectId)  # type: ignore[arg-type]
    agent = None
    if binding.desktop_agent_id is not None:
        try:
            agent = auth_store.get_desktop_agent(str(binding.desktop_agent_id))
        except Exception:
            agent = None
    connected = False
    agent_dto = None
    if agent is not None:
        connected = runtime.is_agent_connected(agent.agent_id)
        agent_dto = {
            **desktop_agent_to_dto(agent),
            "status": effective_desktop_agent_status(agent, connected=connected).value,
            "connected": connected,
            "connectionState": desktop_agent_connection_state(agent, connected=connected),
        }
    return {
        "ok": True,
        "data": {
            "projectId": projectId,
            "binding": project_material_source_binding_to_dto(binding),
            "agent": agent_dto,
        },
    }
