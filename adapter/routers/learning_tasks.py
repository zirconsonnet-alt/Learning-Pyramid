from __future__ import annotations

from fastapi import APIRouter, Depends

from adapter.deps import get_api
from adapter.mappers import asr_artifact_to_dto, learning_task_node_to_dto, learning_task_to_dto, recall_point_to_dto, review_chain_binding_to_dto
from adapter.schemas import EditLearningTaskNodeRequest, EditLearningTaskRequest, SubmitLearningTaskRequest
from backend.models.enums import ContentBlockKind, LearningTaskNodeOrigin, RecallPointState
from backend.models.errors import NotFound, PreconditionFailure
from backend.models.learning_task_node import LearningTaskContainer, LearningTaskLeaf, LearningTaskNode
from backend.models.recall_point import Anchor
from backend.models.rich_content import ContentBlock, RichContent
from backend.models.types import InstanceId, LearningTaskId, MediaAssetId, RecallPointId, id_canonical_text
from backend.system.api import SystemAPI


router = APIRouter()


def _learning_task_node_target_layer_index(api: SystemAPI, project_id: str, node_id: str) -> int | None:
    try:
        return int(api.get_learning_task_node_entry_registration(project_id, node_id).target_layer_index)  # type: ignore[arg-type]
    except NotFound:
        return None


def _active_anchor_instance_keys(recall_points) -> set[str]:
    return {
        id_canonical_text(rp.anchor.instance_id)
        for rp in recall_points
        if rp.state == RecallPointState.ACTIVE and rp.anchor is not None
    }


def _learning_task_node_display_child_node_ids(
    api: SystemAPI,
    project_id: str,
    node: LearningTaskNode,
    target_layer_index: int | None,
    *,
    nodes: tuple[LearningTaskNode, ...] | None = None,
    target_layers_by_node_id: dict[str, int | None] | None = None,
) -> tuple[str, ...] | None:
    if not isinstance(node, LearningTaskContainer):
        return None
    if node.node_origin != LearningTaskNodeOrigin.OBJECT_MIRROR:
        return None
    if node.children:
        return None
    if node.bound_learning_object_node_id is None or target_layer_index is None or int(target_layer_index) <= 0:
        return None

    source_layer_index = int(target_layer_index) - 1
    try:
        target_recall_points = api.list_recall_points_by_learning_object_node(project_id, node.bound_learning_object_node_id)  # type: ignore[arg-type]
    except NotFound:
        return None
    target_instance_keys = _active_anchor_instance_keys(target_recall_points)
    if not target_instance_keys:
        return tuple()

    candidates = nodes if nodes is not None else api.list_learning_task_nodes(project_id)  # type: ignore[arg-type]
    out: list[str] = []
    for candidate in candidates:
        candidate_key = id_canonical_text(candidate.node_id)
        if candidate_key == id_canonical_text(node.node_id):
            continue
        candidate_layer = (
            target_layers_by_node_id.get(candidate_key)
            if target_layers_by_node_id is not None
            else _learning_task_node_target_layer_index(api, project_id, str(candidate.node_id))
        )
        if candidate_layer != source_layer_index:
            continue

        try:
            candidate_recall_points = api.list_recall_points_by_learning_task_node(project_id, candidate.node_id)  # type: ignore[arg-type]
        except NotFound:
            continue
        candidate_instance_keys = _active_anchor_instance_keys(candidate_recall_points)
        if candidate_instance_keys and candidate_instance_keys.issubset(target_instance_keys):
            out.append(str(candidate.node_id))

    return tuple(out)


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


@router.post("/projects/{projectId}/learning-tasks")
def submit_learning_task(projectId: str, req: SubmitLearningTaskRequest, api: SystemAPI = Depends(get_api)) -> dict:
    items = []
    for it in req.items:
        anc = None if it.anchor is None else Anchor(instance_id=InstanceId(it.anchor.instanceId), position=it.anchor.position)
        items.append(
            (
                _to_rich_content(it.question),
                _to_rich_content(it.answer),
                anc,
                tuple(RecallPointId(reference) for reference in it.references),
            )
        )
    entry_node_id = api.submit_learning_task(projectId, items=items, title=req.title)  # type: ignore[arg-type]
    return {"ok": True, "data": {"entryNodeId": str(entry_node_id)}}


@router.get("/projects/{projectId}/learning-tasks/{learningTaskId}")
def get_learning_task(projectId: str, learningTaskId: str, api: SystemAPI = Depends(get_api)) -> dict:
    task = api.get_learning_task(projectId, LearningTaskId(learningTaskId))  # type: ignore[arg-type]
    reg = api.get_learning_task_entry_registration(projectId, LearningTaskId(learningTaskId))  # type: ignore[arg-type]
    entry_node = api.get_learning_task_node(projectId, reg.entry_node)  # type: ignore[arg-type]
    if not isinstance(entry_node, LearningTaskLeaf):
        raise PreconditionFailure("LearningTask entry node must be a leaf")
    return {
        "ok": True,
        "data": learning_task_to_dto(
            task,
            entry_node_id=str(entry_node.node_id),
            entry_node_title=entry_node.title,
            review_chain_id=str(reg.review_chain_id),
            target_layer_index=int(reg.target_layer_index),
        ),
    }


@router.get("/projects/{projectId}/learning-task-nodes/{nodeId}")
def get_learning_task_node(projectId: str, nodeId: str, api: SystemAPI = Depends(get_api)) -> dict:
    n = api.get_learning_task_node(projectId, nodeId)  # type: ignore[arg-type]
    target_layer_index = _learning_task_node_target_layer_index(api, projectId, nodeId)
    return {
        "ok": True,
        "data": learning_task_node_to_dto(
            n,
            target_layer_index=target_layer_index,
            display_child_node_ids=_learning_task_node_display_child_node_ids(
                api,
                projectId,
                n,
                target_layer_index,
            ),
        ),
    }


@router.get("/projects/{projectId}/learning-task-nodes/{nodeId}/binding")
def get_learning_task_node_binding(projectId: str, nodeId: str, api: SystemAPI = Depends(get_api)) -> dict:
    reg = api.get_learning_task_node_entry_registration(projectId, nodeId)  # type: ignore[arg-type]
    entry_node = api.get_learning_task_node(projectId, nodeId)  # type: ignore[arg-type]
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


@router.get("/projects/{projectId}/learning-task-nodes")
def list_learning_task_nodes(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    nodes = tuple(api.list_learning_task_nodes(projectId))  # type: ignore[arg-type]
    target_layers_by_node_id = {
        id_canonical_text(n.node_id): _learning_task_node_target_layer_index(api, projectId, str(n.node_id))
        for n in nodes
    }
    items = [
        learning_task_node_to_dto(
            n,
            target_layer_index=target_layers_by_node_id[id_canonical_text(n.node_id)],
            display_child_node_ids=_learning_task_node_display_child_node_ids(
                api,
                projectId,
                n,
                target_layers_by_node_id[id_canonical_text(n.node_id)],
                nodes=nodes,
                target_layers_by_node_id=target_layers_by_node_id,
            ),
        )
        for n in nodes
    ]
    return {"ok": True, "data": items}


@router.get("/projects/{projectId}/learning-task-nodes/{nodeId}/recall-points")
def list_recall_points_by_learning_task_node(projectId: str, nodeId: str, api: SystemAPI = Depends(get_api)) -> dict:
    items = [recall_point_to_dto(rp) for rp in api.list_recall_points_by_learning_task_node(projectId, nodeId)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}


@router.get("/projects/{projectId}/learning-task-nodes/{nodeId}/exports/recall-points")
def export_recall_points_by_learning_task_node(projectId: str, nodeId: str, api: SystemAPI = Depends(get_api)) -> dict:
    items = [recall_point_to_dto(rp) for rp in api.export_recall_points_by_learning_task_node(projectId, nodeId)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}


@router.get("/projects/{projectId}/learning-task-nodes/{nodeId}/exports/asr")
def export_asr_by_learning_task_node(projectId: str, nodeId: str, api: SystemAPI = Depends(get_api)) -> dict:
    items = [asr_artifact_to_dto(art) for art in api.export_asr_by_learning_task_node(projectId, nodeId)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}


@router.patch("/projects/{projectId}/learning-tasks/{learningTaskId}")
def edit_learning_task(
    projectId: str, learningTaskId: str, req: EditLearningTaskRequest, api: SystemAPI = Depends(get_api)
) -> dict:
    api.edit_learning_task(projectId, LearningTaskId(learningTaskId), title=req.title)  # type: ignore[arg-type]
    return {"ok": True, "data": None}


@router.patch("/projects/{projectId}/learning-task-nodes/{nodeId}")
def edit_learning_task_node(
    projectId: str, nodeId: str, req: EditLearningTaskNodeRequest, api: SystemAPI = Depends(get_api)
) -> dict:
    api.edit_learning_task_node_title(projectId, nodeId, title=req.title)  # type: ignore[arg-type]
    return {"ok": True, "data": None}
