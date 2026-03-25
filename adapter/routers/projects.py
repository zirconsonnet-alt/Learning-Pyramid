from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from adapter.auth import require_request_auth_user
from adapter.deps import get_api, get_auth_store
from adapter.mappers import (
    audit_log_event_to_dto,
    project_config_to_dto,
    project_material_source_binding_to_dto,
    project_storage_config_to_dto,
    project_to_dto,
)
from adapter.schemas import (
    CreateProjectRequest,
    EditProjectRequest,
    SetProjectMaterialSourceBindingRequest,
)
from backend.models.enums import MaterialSourceKind
from backend.models.errors import PreconditionFailure
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthStore
from backend.system.runtime_features import current_runtime_features


router = APIRouter()


def _parse_material_source_kind(raw: str | None) -> MaterialSourceKind:
    value = str(raw or MaterialSourceKind.SERVER_FS.value).strip()
    try:
        return MaterialSourceKind(value)
    except ValueError as exc:
        raise PreconditionFailure("sourceKind must be one of SERVER_FS, BROWSER_LOCAL, NATIVE_LOCAL, MANUAL") from exc


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
    pid = api.create_project(
        req.title,
        project_root=req.projectRoot,
        initial_source_kind=_parse_material_source_kind(req.initialSourceKind),
    )
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


@router.patch("/projects/{projectId}")
def edit_project(projectId: str, req: EditProjectRequest, api: SystemAPI = Depends(get_api)) -> dict:
    api.edit_project(projectId, req.title)  # type: ignore[arg-type]
    return {"ok": True, "data": None}


@router.get("/projects/{projectId}/project-config")
def get_project_config(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    cfg = api.get_project_config(projectId)  # type: ignore[arg-type]
    return {"ok": True, "data": project_config_to_dto(cfg)}


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
    api: SystemAPI = Depends(get_api),
) -> dict:
    api.set_project_material_source_binding(  # type: ignore[arg-type]
        projectId,
        source_kind=_parse_material_source_kind(req.sourceKind),
        source_root_label=req.sourceRootLabel,
    )
    return {"ok": True, "data": None}


@router.get("/projects/{projectId}/audit-log-events")
def list_audit_log_events(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    items = [audit_log_event_to_dto(ev) for ev in api.list_audit_log_events(projectId)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}
