from fastapi import APIRouter, Depends

from adapter.deps import get_api
from adapter.mappers import asr_artifact_to_dto, learning_task_node_to_dto, learning_task_to_dto, recall_point_to_dto, review_chain_binding_to_dto
from adapter.scoped_projects import ScopedProject, resolve_scoped_project
from adapter.schemas import EditLearningTaskNodeRequest, EditLearningTaskRequest, SubmitLearningTaskRequest
from backend.models.enums import ContentBlockKind
from backend.models.errors import NotFound, PreconditionFailure
from backend.models.learning_task_node import LearningTaskLeaf
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


@router.post("/subjects/{subjectId}/projects/{projectId}/learning-tasks")
def submit_learning_task(req: SubmitLearningTaskRequest, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
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
    entry_node_id = api.submit_learning_task(project.internal_project_id, items=items, title=req.title)  # type: ignore[arg-type]
    return {"ok": True, "data": {"entryNodeId": str(entry_node_id)}}


@router.get("/subjects/{subjectId}/projects/{projectId}/learning-tasks/{learningTaskId}")
def get_learning_task(learningTaskId: str, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    task = api.get_learning_task(project.internal_project_id, LearningTaskId(learningTaskId))  # type: ignore[arg-type]
    reg = api.get_learning_task_entry_registration(project.internal_project_id, LearningTaskId(learningTaskId))  # type: ignore[arg-type]
    entry_node = api.get_learning_task_node(project.internal_project_id, reg.entry_node)  # type: ignore[arg-type]
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
            public_project_id=project.project_id,
        ),
    }


@router.get("/subjects/{subjectId}/projects/{projectId}/learning-task-nodes/{nodeId}")
def get_learning_task_node(nodeId: str, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    n = api.get_learning_task_node(project.internal_project_id, nodeId)  # type: ignore[arg-type]
    target_layer_index = _learning_task_node_target_layer_index(api, project.internal_project_id, nodeId)
    return {
        "ok": True,
        "data": learning_task_node_to_dto(
            n,
            target_layer_index=target_layer_index,
            public_project_id=project.project_id,
        ),
    }


@router.get("/subjects/{subjectId}/projects/{projectId}/learning-task-nodes/{nodeId}/binding")
def get_learning_task_node_binding(nodeId: str, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    reg = api.get_learning_task_node_entry_registration(project.internal_project_id, nodeId)  # type: ignore[arg-type]
    entry_node = api.get_learning_task_node(project.internal_project_id, nodeId)  # type: ignore[arg-type]
    task = api.get_learning_task(project.internal_project_id, entry_node.bound_learning_task_id) if isinstance(entry_node, LearningTaskLeaf) else None  # type: ignore[arg-type]
    return {
        "ok": True,
        "data": review_chain_binding_to_dto(
            project_id=project.project_id,
            reg=reg,
            entry_node=entry_node,
            learning_task=task,
        ),
    }


@router.get("/subjects/{subjectId}/projects/{projectId}/learning-task-nodes")
def list_learning_task_nodes(project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    nodes = tuple(api.list_learning_task_nodes(project.internal_project_id))  # type: ignore[arg-type]
    target_layers_by_node_id = {
        id_canonical_text(n.node_id): _learning_task_node_target_layer_index(api, project.internal_project_id, str(n.node_id))
        for n in nodes
    }
    items = [
        learning_task_node_to_dto(
            n,
            target_layer_index=target_layers_by_node_id[id_canonical_text(n.node_id)],
            public_project_id=project.project_id,
        )
        for n in nodes
    ]
    return {"ok": True, "data": items}


@router.get("/subjects/{subjectId}/projects/{projectId}/learning-task-nodes/{nodeId}/recall-points")
def list_recall_points_by_learning_task_node(nodeId: str, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    items = [recall_point_to_dto(rp, public_project_id=project.project_id) for rp in api.list_recall_points_by_learning_task_node(project.internal_project_id, nodeId)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}


@router.get("/subjects/{subjectId}/projects/{projectId}/learning-task-nodes/{nodeId}/exports/recall-points")
def export_recall_points_by_learning_task_node(nodeId: str, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    items = [recall_point_to_dto(rp, public_project_id=project.project_id) for rp in api.export_recall_points_by_learning_task_node(project.internal_project_id, nodeId)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}


@router.get("/subjects/{subjectId}/projects/{projectId}/learning-task-nodes/{nodeId}/exports/asr")
def export_asr_by_learning_task_node(nodeId: str, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    items = [asr_artifact_to_dto(art, public_project_id=project.project_id) for art in api.export_asr_by_learning_task_node(project.internal_project_id, nodeId)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}


@router.patch("/subjects/{subjectId}/projects/{projectId}/learning-tasks/{learningTaskId}")
def edit_learning_task(
    learningTaskId: str, req: EditLearningTaskRequest, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)
) -> dict:
    api.edit_learning_task(project.internal_project_id, LearningTaskId(learningTaskId), title=req.title)  # type: ignore[arg-type]
    return {"ok": True, "data": None}


@router.patch("/subjects/{subjectId}/projects/{projectId}/learning-task-nodes/{nodeId}")
def edit_learning_task_node(
    nodeId: str, req: EditLearningTaskNodeRequest, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)
) -> dict:
    api.edit_learning_task_node_title(project.internal_project_id, nodeId, title=req.title)  # type: ignore[arg-type]
    return {"ok": True, "data": None}
