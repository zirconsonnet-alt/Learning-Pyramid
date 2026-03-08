from __future__ import annotations

from fastapi import APIRouter, Depends

from adapter.deps import get_api
from adapter.mappers import audit_log_event_to_dto, project_config_to_dto, project_storage_config_to_dto, project_to_dto
from adapter.schemas import CreateProjectRequest, SetExternalServicesRequest
from backend.models.project_config import LocalServiceConfig
from backend.system.api import SystemAPI


router = APIRouter()


@router.get("/projects")
def list_projects(api: SystemAPI = Depends(get_api)) -> dict:
    items = [project_to_dto(p) for p in api.list_projects()]
    return {"ok": True, "data": items}


@router.post("/projects")
def create_project(req: CreateProjectRequest, api: SystemAPI = Depends(get_api)) -> dict:
    pid = api.create_project(req.title)
    return {"ok": True, "data": {"projectId": str(pid)}}


@router.delete("/projects/{projectId}")
def delete_project(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    api.delete_project(projectId)  # type: ignore[arg-type]
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


@router.get("/projects/{projectId}/audit-log-events")
def list_audit_log_events(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    items = [audit_log_event_to_dto(ev) for ev in api.list_audit_log_events(projectId)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}
