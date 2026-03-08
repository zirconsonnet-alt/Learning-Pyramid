from __future__ import annotations

from fastapi import APIRouter, Depends

from adapter.deps import get_api
from backend.system.api import SystemAPI


router = APIRouter()


@router.get("/projects/{projectId}/validate/material/{instanceId}")
def validate_material(projectId: str, instanceId: str, api: SystemAPI = Depends(get_api)) -> dict:
    res = api.validate_material_reachable(projectId, instanceId)  # type: ignore[arg-type]
    return {"ok": True, "data": {"code": res.code.value, "message": res.message}}


@router.get("/projects/{projectId}/validate/range/{rangeId}")
def validate_range(projectId: str, rangeId: str, api: SystemAPI = Depends(get_api)) -> dict:
    res = api.validate_recall_point_ids_resolvable(projectId, rangeId)  # type: ignore[arg-type]
    return {"ok": True, "data": {"code": res.code.value, "message": res.message}}
