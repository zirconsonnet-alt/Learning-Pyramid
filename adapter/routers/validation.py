from fastapi import APIRouter, Depends

from adapter.deps import get_api
from adapter.scoped_projects import ScopedProject, resolve_scoped_project
from backend.system.api import SystemAPI


router = APIRouter()


@router.get("/subjects/{subjectId}/projects/{scopedProjectId}/validate/material/{instanceId}")
def validate_material(instanceId: str, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    res = api.validate_material_reachable(project.internal_project_id, instanceId)  # type: ignore[arg-type]
    return {"ok": True, "data": {"code": res.code.value, "message": res.message}}


@router.get("/subjects/{subjectId}/projects/{scopedProjectId}/validate/range/{rangeId}")
def validate_range(rangeId: str, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    res = api.validate_recall_point_ids_resolvable(project.internal_project_id, rangeId)  # type: ignore[arg-type]
    return {"ok": True, "data": {"code": res.code.value, "message": res.message}}
