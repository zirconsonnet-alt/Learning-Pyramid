from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from adapter.auth import require_request_auth_user
from adapter.deps import get_api
from adapter.mappers import asr_artifact_to_dto, instance_to_dto, learning_object_node_to_dto, recall_point_to_dto
from adapter.schemas import (
    AddInstanceRequest,
    AddLearningObjectContainerRequest,
    AddLearningObjectLeafRequest,
    BulkRemapRecallPointsInstanceRequest,
    ImportLearningObjectsFromBaiduNetdiskRequest,
    ImportBrowserDirectoryRequest,
    InitializeBookLearningObjectsRequest,
    InitializeBookLearningObjectsFromMaterialRequest,
)
from backend.models.types import InstanceId, LearningObjectNodeId
from backend.models.types import RecallPointId
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthStore
from adapter.deps import get_auth_store


router = APIRouter()


@router.get("/projects/{projectId}/instances")
def list_instances(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    project_binding = api.get_project_material_source_binding(projectId)  # type: ignore[arg-type]
    media_service = api._instance_media_service()
    items = []
    for instance in api.list_instances(projectId):  # type: ignore[arg-type]
        media_binding = media_service.get_instance_media_binding(projectId, str(instance.instance_id))
        effective_source_kind = media_binding.source_kind if media_binding is not None else project_binding.source_kind
        items.append(
            instance_to_dto(
                instance,
                media_source_kind=effective_source_kind.value,
                playback_kind="FILE" if media_binding is None else media_binding.playback_kind,
                duration_ms=None if media_binding is None else media_binding.duration_ms,
            )
        )
    return {"ok": True, "data": items}


@router.post("/projects/{projectId}/instances")
def add_instance(projectId: str, req: AddInstanceRequest, api: SystemAPI = Depends(get_api)) -> dict:
    iid = api.add_instance(projectId, req.materialId)  # type: ignore[arg-type]
    return {"ok": True, "data": {"instanceId": str(iid)}}


@router.post("/projects/{projectId}/initialize-book-learning-objects")
def initialize_book_learning_objects(
    projectId: str,
    req: InitializeBookLearningObjectsRequest,
    api: SystemAPI = Depends(get_api),
) -> dict:
    result = api.initialize_book_learning_objects(  # type: ignore[arg-type]
        projectId,
        outline_items=tuple((int(item.depth), item.title) for item in req.items),
    )
    return {"ok": True, "data": result}


@router.post("/projects/{projectId}/initialize-book-learning-objects-from-material")
def initialize_book_learning_objects_from_material(
    projectId: str,
    req: InitializeBookLearningObjectsFromMaterialRequest,
    api: SystemAPI = Depends(get_api),
) -> dict:
    result = api.initialize_book_learning_objects_from_subject_material(  # type: ignore[arg-type]
        projectId,
        source_material_id=req.sourceMaterialId,
    )
    return {"ok": True, "data": result}


@router.post("/projects/{projectId}/ensure-mistake-inbox")
def ensure_mistake_inbox(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    result = api.ensure_mistake_material_inbox(projectId)  # type: ignore[arg-type]
    return {"ok": True, "data": result}


@router.post("/projects/{projectId}/sync-learning-objects-from-fs")
def sync_learning_objects_from_fs(projectId: str, api: SystemAPI = Depends(get_api)) -> dict:
    report = api.sync_learning_objects_from_fs(projectId)  # type: ignore[arg-type]
    return {"ok": True, "data": report}


@router.post("/projects/{projectId}/import-learning-objects-from-browser")
def import_learning_objects_from_browser(
    projectId: str,
    req: ImportBrowserDirectoryRequest,
    api: SystemAPI = Depends(get_api),
) -> dict:
    report = api.import_learning_objects_from_browser_scan(  # type: ignore[arg-type]
        projectId,
        root_title=req.rootTitle,
        relative_file_paths=req.relativeFilePaths,
    )
    return {"ok": True, "data": report}


@router.get("/projects/{projectId}/baidu-netdisk/files")
def list_baidu_netdisk_files(
    projectId: str,
    request: Request,
    accountId: str = Query(min_length=1),
    dirPath: str = Query(default="/"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=200, ge=1, le=500),
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    data = api.list_baidu_netdisk_files(
        auth_store=auth_store,
        user_id=user.user_id,
        account_id=accountId,
        dir_path=dirPath,
        page=page,
        limit=limit,
    )
    return {"ok": True, "data": data}


@router.post("/projects/{projectId}/import-learning-objects-from-baidu-netdisk")
def import_learning_objects_from_baidu_netdisk(
    projectId: str,
    req: ImportLearningObjectsFromBaiduNetdiskRequest,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    report = api.import_learning_objects_from_baidu_netdisk(  # type: ignore[arg-type]
        projectId,
        auth_store=auth_store,
        user_id=user.user_id,
        account_id=req.accountId,
        items=[item.model_dump() for item in req.items],
    )
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
