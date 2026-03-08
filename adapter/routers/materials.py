from __future__ import annotations

from fastapi import APIRouter, Depends

from adapter.deps import get_api
from adapter.mappers import asr_artifact_to_dto, instance_to_dto, learning_object_node_to_dto, recall_point_to_dto
from adapter.schemas import (
    AddInstanceRequest,
    AddLearningObjectContainerRequest,
    AddLearningObjectLeafRequest,
    BulkRemapRecallPointsInstanceRequest,
)
from backend.models.types import InstanceId, LearningObjectNodeId
from backend.models.types import RecallPointId
from backend.system.api import SystemAPI


router = APIRouter()


@router.get("/projects/{projectId}/instances")
def list_instances(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    items = [instance_to_dto(i) for i in api.list_instances(projectId)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}


@router.post("/projects/{projectId}/instances")
def add_instance(projectId: str, req: AddInstanceRequest, api: SystemAPI = Depends(get_api)) -> dict:
    iid = api.add_instance(projectId, req.materialId)  # type: ignore[arg-type]
    return {"ok": True, "data": {"instanceId": str(iid)}}

@router.post("/projects/{projectId}/sync-learning-objects-from-fs")
def sync_learning_objects_from_fs(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    report = api.sync_learning_objects_from_fs(projectId)  # type: ignore[arg-type]
    return {"ok": True, "data": report}


@router.get("/projects/{projectId}/missing-instances")
def list_missing_instances(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    ids = api.list_missing_instances(projectId)  # type: ignore[arg-type]
    return {"ok": True, "data": {"instanceIds": [str(x) for x in ids]}}


@router.get("/projects/{projectId}/instances/{instanceId}/recall-points")
def list_recall_points_by_instance(projectId: str, instanceId: str, api: SystemAPI = Depends(get_api)) -> dict:
    ids = api.list_recall_points_by_instance(projectId, InstanceId(instanceId))  # type: ignore[arg-type]
    return {"ok": True, "data": {"recallPointIds": [str(x) for x in ids]}}


@router.post("/projects/{projectId}/instances/remap-recall-points")
def bulk_remap_recall_points_instance(
    projectId: str, req: BulkRemapRecallPointsInstanceRequest, api: SystemAPI = Depends(get_api)
) -> dict:
    rp_ids = None if req.recallPointIds is None else tuple(RecallPointId(x) for x in req.recallPointIds)
    n = api.bulk_remap_recall_points_instance(  # type: ignore[arg-type]
        projectId,
        from_instance_id=InstanceId(req.fromInstanceId),
        to_instance_id=InstanceId(req.toInstanceId),
        recall_point_ids=rp_ids,
    )
    return {"ok": True, "data": {"movedCount": int(n)}}


@router.post("/projects/{projectId}/learning-objects/leaf")
def add_learning_object_leaf(projectId: str, req: AddLearningObjectLeafRequest, api: SystemAPI = Depends(get_api)) -> dict:
    parent = None if req.parentId is None else LearningObjectNodeId(req.parentId)
    nid = api.add_learning_object_leaf(  # type: ignore[arg-type]
        projectId, parent_id=parent, instance_id=InstanceId(req.instanceId), title=req.title
    )
    return {"ok": True, "data": {"nodeId": str(nid)}}


@router.post("/projects/{projectId}/learning-objects/container")
def add_learning_object_container(
    projectId: str, req: AddLearningObjectContainerRequest, api: SystemAPI = Depends(get_api)
) -> dict:
    parent = None if req.parentId is None else LearningObjectNodeId(req.parentId)
    children = tuple(LearningObjectNodeId(x) for x in req.children)
    nid = api.add_learning_object_container(  # type: ignore[arg-type]
        projectId, parent_id=parent, children=children, title=req.title
    )
    return {"ok": True, "data": {"nodeId": str(nid)}}


@router.get("/projects/{projectId}/learning-objects/{nodeId}")
def get_learning_object_node(projectId: str, nodeId: str, api: SystemAPI = Depends(get_api)) -> dict:
    n = api.get_learning_object_node(projectId, nodeId)  # type: ignore[arg-type]
    return {"ok": True, "data": learning_object_node_to_dto(n)}


@router.get("/projects/{projectId}/learning-object-nodes")
def list_learning_object_nodes(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    items = [learning_object_node_to_dto(n) for n in api.list_learning_object_nodes(projectId)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}


@router.get("/projects/{projectId}/learning-objects/{nodeId}/recall-points")
def list_recall_points_by_learning_object_node(projectId: str, nodeId: str, api: SystemAPI = Depends(get_api)) -> dict:
    items = [recall_point_to_dto(rp) for rp in api.list_recall_points_by_learning_object_node(projectId, nodeId)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}


@router.get("/projects/{projectId}/learning-objects/{nodeId}/exports/recall-points")
def export_recall_points_by_learning_object_node(projectId: str, nodeId: str, api: SystemAPI = Depends(get_api)) -> dict:
    items = [recall_point_to_dto(rp) for rp in api.export_recall_points_by_learning_object_node(projectId, nodeId)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}


@router.get("/projects/{projectId}/learning-objects/{nodeId}/exports/asr")
def export_asr_by_learning_object_node(projectId: str, nodeId: str, api: SystemAPI = Depends(get_api)) -> dict:
    items = [asr_artifact_to_dto(art) for art in api.export_asr_by_learning_object_node(projectId, nodeId)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}


@router.get("/projects/{projectId}/learning-object-roots")
def list_learning_object_roots(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    ids = api.list_learning_object_roots(projectId)  # type: ignore[arg-type]
    return {"ok": True, "data": {"rootLearningObjectNodeIds": [str(x) for x in ids]}}
