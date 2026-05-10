from fastapi import APIRouter, Depends

from adapter.deps import get_api
from adapter.mappers import aggregation_event_to_dto, layer_to_dto
from adapter.scoped_projects import ScopedProject, resolve_scoped_project
from adapter.schemas import ManualRollUpRequest, SetLayerConfigRequest
from backend.models.enums import ReviewChainTemplateItemKind
from backend.models.errors import PreconditionFailure
from backend.models.project_config import ReviewChainTemplateItem
from backend.system.api import SystemAPI


router = APIRouter()


@router.get("/subjects/{subjectId}/projects/{projectId}/layers")
def list_layers(project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    layers = [layer_to_dto(l, public_project_id=project.project_id) for l in api.list_layers(project.internal_project_id)]  # type: ignore[arg-type]
    return {"ok": True, "data": layers}


@router.get("/subjects/{subjectId}/projects/{projectId}/aggregation-queue/{layerIndex}")
def get_agg_queue(layerIndex: int, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    ids = api.get_aggregation_queue_current(project.internal_project_id, layerIndex)  # type: ignore[arg-type]
    return {"ok": True, "data": {"currentNodeIds": [str(x) for x in ids]}}


@router.post("/subjects/{subjectId}/projects/{projectId}/layers/{layerIndex}/roll-up")
def manual_roll_up(layerIndex: int, req: ManualRollUpRequest, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    parent = api.manual_roll_up(project.internal_project_id, layerIndex, req.title)  # type: ignore[arg-type]
    return {"ok": True, "data": {"parentNodeId": None if parent is None else str(parent)}}


@router.get("/subjects/{subjectId}/projects/{projectId}/aggregation-events")
def list_events(project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    events = [aggregation_event_to_dto(ev, public_project_id=project.project_id) for ev in api.list_aggregation_events(project.internal_project_id)]  # type: ignore[arg-type]
    return {"ok": True, "data": events}


@router.post("/subjects/{subjectId}/projects/{projectId}/layers/{layerIndex}/config")
def set_layer_config(layerIndex: int, req: SetLayerConfigRequest, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    tmpl = None
    if req.reviewChainTemplate is not None:
        items: list[ReviewChainTemplateItem] = []
        for it in req.reviewChainTemplate:
            try:
                kind = ReviewChainTemplateItemKind(str(it.kind))
            except Exception:
                raise PreconditionFailure(f"Invalid ReviewChainTemplateItem.kind: {it.kind}")
            items.append(ReviewChainTemplateItem(kind=kind, count=it.count))
        tmpl = tuple(items)

    api.set_layer_config(  # type: ignore[arg-type]
        project.internal_project_id,
        layerIndex,
        tmpl,
        req.kNode,
        req.kPoint,
        req.thresholdRollUpEnabled,
    )
    return {"ok": True, "data": None}
