from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from adapter.deps import get_api
from adapter.mappers import (
    convergence_to_dto,
    recall_point_review_projection_to_dto,
    range_snapshot_to_dto,
    recall_point_to_dto,
    review_chain_binding_to_dto,
    review_chain_to_dto,
    review_task_to_dto,
)
from adapter.schemas import CommitReviewTaskRequest, EditRecallPointRequest
from backend.models.enums import ContentBlockKind
from backend.models.errors import PreconditionFailure
from backend.models.learning_task_node import LearningTaskLeaf
from backend.models.recall_point import Anchor
from backend.models.rich_content import ContentBlock, RichContent
from backend.models.types import ConvergenceId, InstanceId, MediaAssetId, RecallPointId, ReviewChainId
from backend.system.api import SystemAPI


router = APIRouter()

def _to_rich_content(blocks) -> RichContent:
    out: list[ContentBlock] = []
    for b in blocks:
        try:
            kind = ContentBlockKind(str(b.kind))
        except Exception:
            raise PreconditionFailure(f"Invalid ContentBlock.kind: {b.kind}")
        if kind == ContentBlockKind.TEXT:
            out.append(ContentBlock(kind=kind, text=b.text))
        elif kind == ContentBlockKind.IMAGE:
            out.append(ContentBlock(kind=kind, asset_id=None if b.assetId is None else MediaAssetId(b.assetId)))
        else:
            raise PreconditionFailure(f"Unknown ContentBlockKind: {b.kind}")
    return tuple(out)


@router.get("/projects/{projectId}/queue")
def get_queue(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    head, ids = api.get_queue(projectId)  # type: ignore[arg-type]
    return {"ok": True, "data": {"headId": None if head is None else str(head), "ids": [str(x) for x in ids]}}


@router.get("/projects/{projectId}/review-tasks/{reviewTaskId}")
def get_review_task(projectId: str, reviewTaskId: str, api: SystemAPI = Depends(get_api)) -> dict:
    rt = api.get_review_task(projectId, reviewTaskId)  # type: ignore[arg-type]
    return {"ok": True, "data": review_task_to_dto(rt)}


@router.get("/projects/{projectId}/convergences/{convergenceId}")
def get_convergence(projectId: str, convergenceId: str, api: SystemAPI = Depends(get_api)) -> dict:
    item = api.get_convergence(projectId, ConvergenceId(convergenceId))  # type: ignore[arg-type]
    return {"ok": True, "data": convergence_to_dto(item)}


@router.get("/projects/{projectId}/review-chains/{reviewChainId}")
def get_review_chain(projectId: str, reviewChainId: str, api: SystemAPI = Depends(get_api)) -> dict:
    chain = api.get_review_chain(projectId, ReviewChainId(reviewChainId))  # type: ignore[arg-type]
    return {"ok": True, "data": review_chain_to_dto(chain)}


@router.get("/projects/{projectId}/review-chains/{reviewChainId}/binding")
def get_review_chain_binding(projectId: str, reviewChainId: str, api: SystemAPI = Depends(get_api)) -> dict:
    reg = api.get_review_chain_entry_registration(projectId, ReviewChainId(reviewChainId))  # type: ignore[arg-type]
    entry_node = api.get_learning_task_node(projectId, reg.entry_node)  # type: ignore[arg-type]
    task = api.get_learning_task(projectId, entry_node.bound_learning_task_id) if isinstance(entry_node, LearningTaskLeaf) else None  # type: ignore[arg-type]
    return {
        "ok": True,
        "data": review_chain_binding_to_dto(
            project_id=projectId,
            reg=reg,
            entry_node=entry_node,
            learning_task=task,
        ),
    }


@router.get("/projects/{projectId}/ranges/{rangeId}")
def get_range(projectId: str, rangeId: str, api: SystemAPI = Depends(get_api)) -> dict:
    snap = api.get_range_snapshot(projectId, rangeId)  # type: ignore[arg-type]
    return {"ok": True, "data": range_snapshot_to_dto(snap)}


@router.get("/projects/{projectId}/recall-points")
def list_recall_points(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    items = [recall_point_to_dto(rp) for rp in api.list_recall_points(projectId)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}


@router.get("/projects/{projectId}/recall-points/search")
def search_recall_points(
    projectId: str,
    q: str | None = Query(default=None, min_length=0, max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
    api: SystemAPI = Depends(get_api),
) -> dict:
    items = [recall_point_to_dto(rp) for rp in api.search_recall_points(projectId, query=q, limit=limit)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}


@router.get("/projects/{projectId}/recall-points/{recallPointId}")
def get_recall_point(projectId: str, recallPointId: str, api: SystemAPI = Depends(get_api)) -> dict:
    rp = api.get_recall_point(projectId, recallPointId)  # type: ignore[arg-type]
    return {"ok": True, "data": recall_point_to_dto(rp)}


@router.get("/projects/{projectId}/recall-points/{recallPointId}/review-projection")
def get_recall_point_review_projection(projectId: str, recallPointId: str, api: SystemAPI = Depends(get_api)) -> dict:
    item = api.get_recall_point_review_projection(projectId, RecallPointId(recallPointId))  # type: ignore[arg-type]
    return {"ok": True, "data": recall_point_review_projection_to_dto(item)}

@router.put("/projects/{projectId}/recall-points/{recallPointId}")
def edit_recall_point(
    projectId: str, recallPointId: str, req: EditRecallPointRequest, api: SystemAPI = Depends(get_api)
) -> dict:
    anc = None if req.anchor is None else Anchor(instance_id=InstanceId(req.anchor.instanceId), position=req.anchor.position)
    api.edit_recall_point(  # type: ignore[arg-type]
        projectId,
        recallPointId,
        _to_rich_content(req.question),
        _to_rich_content(req.answer),
        anc,
    )
    return {"ok": True, "data": None}


@router.delete("/projects/{projectId}/recall-points/{recallPointId}")
def delete_recall_point(projectId: str, recallPointId: str, api: SystemAPI = Depends(get_api)) -> dict:
    api.delete_recall_point(projectId, RecallPointId(recallPointId))  # type: ignore[arg-type]
    return {"ok": True, "data": None}


@router.post("/projects/{projectId}/review-tasks/{reviewTaskId}/commit")
def commit_review_task(
    projectId: str, reviewTaskId: str, req: CommitReviewTaskRequest, api: SystemAPI = Depends(get_api)
) -> dict:
    appended = None
    if req.appendedInsights is not None:
        appended = tuple((RecallPointId(x.recallPointId), _to_rich_content(x.insight)) for x in req.appendedInsights)

    api.executor_commit_review_task(  # type: ignore[arg-type]
        projectId, reviewTaskId, req.canRecall, appended_insights=appended
    )
    return {"ok": True, "data": None}
