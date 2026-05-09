from fastapi import APIRouter, Depends

from adapter.deps import get_api
from adapter.mappers import aggregation_event_to_dto, layer_to_dto
from adapter.schemas import ManualRollUpRequest, SetLayerConfigRequest
from backend.models.enums import ReviewChainTemplateItemKind
from backend.models.errors import PreconditionFailure
from backend.models.project_config import ReviewChainTemplateItem
from backend.system.api import SystemAPI


router = APIRouter()


@router.get("/projects/{projectId}/layers")
def list_layers(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    layers = [layer_to_dto(l) for l in api.list_layers(projectId)]  # type: ignore[arg-type]
    return {"ok": True, "data": layers}


@router.get("/projects/{projectId}/aggregation-queue/{layerIndex}")
def get_agg_queue(projectId: str, layerIndex: int, api: SystemAPI = Depends(get_api)) -> dict:
    ids = api.get_aggregation_queue_current(projectId, layerIndex)  # type: ignore[arg-type]
    return {"ok": True, "data": {"currentNodeIds": [str(x) for x in ids]}}


@router.post("/projects/{projectId}/layers/{layerIndex}/roll-up")
def manual_roll_up(projectId: str, layerIndex: int, req: ManualRollUpRequest, api: SystemAPI = Depends(get_api)) -> dict:
    parent = api.manual_roll_up(projectId, layerIndex, req.title)  # type: ignore[arg-type]
    return {"ok": True, "data": {"parentNodeId": None if parent is None else str(parent)}}


@router.get("/projects/{projectId}/aggregation-events")
def list_events(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    events = [aggregation_event_to_dto(ev) for ev in api.list_aggregation_events(projectId)]  # type: ignore[arg-type]
    return {"ok": True, "data": events}


@router.post("/projects/{projectId}/layers/{layerIndex}/config")
def set_layer_config(projectId: str, layerIndex: int, req: SetLayerConfigRequest, api: SystemAPI = Depends(get_api)) -> dict:
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
        projectId,
        layerIndex,
        tmpl,
        req.kNode,
        req.kPoint,
        req.thresholdRollUpEnabled,
    )
    return {"ok": True, "data": None}
