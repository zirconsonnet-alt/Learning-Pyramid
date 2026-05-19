from fastapi import APIRouter, Depends, Query, Request

from adapter.auth import require_request_auth_user
from adapter.deps import get_api
from adapter.mappers import (
    asr_artifact_to_dto,
    instance_to_dto,
    learning_object_node_to_dto,
    recall_point_to_dto,
    video_watch_progress_to_dto,
)
from adapter.scoped_projects import ScopedProject, resolve_scoped_project
from adapter.schemas import (
    AddInstanceRequest,
    AddLearningObjectContainerRequest,
    AddLearningObjectLeafRequest,
    BulkRemapRecallPointsInstanceRequest,
    ImportLearningObjectsFromBaiduNetdiskRequest,
    ImportBrowserDirectoryRequest,
    ImportNativeLocalDirectoryRequest,
    InitializeBookLearningObjectsRequest,
    InitializeBookLearningObjectsFromMaterialRequest,
    VideoWatchProgressCompletedRequest,
    VideoWatchProgressRangeRequest,
)
from backend.models.types import InstanceId, LearningObjectNodeId
from backend.models.types import RecallPointId
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthStore
from adapter.deps import get_auth_store


router = APIRouter()


@router.get("/subjects/{subjectId}/projects/{scopedProjectId}/instances")
def list_instances(project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    items = [
        instance_to_dto(
            item.instance,
            media_source_kind=item.media_source_kind,
            playback_kind=item.playback_kind,
            duration_ms=item.duration_ms,
        )
        for item in api.list_instances_with_media_summary(project.internal_project_id)  # type: ignore[arg-type]
    ]
    return {"ok": True, "data": items}


@router.post("/subjects/{subjectId}/projects/{scopedProjectId}/instances")
def add_instance(req: AddInstanceRequest, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    iid = api.add_instance(project.internal_project_id, req.materialId)  # type: ignore[arg-type]
    return {"ok": True, "data": {"instanceId": str(iid)}}


@router.post("/subjects/{subjectId}/projects/{scopedProjectId}/initialize-book-learning-objects")
def initialize_book_learning_objects(
    req: InitializeBookLearningObjectsRequest,
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
) -> dict:
    result = api.initialize_book_learning_objects(  # type: ignore[arg-type]
        project.internal_project_id,
        outline_items=tuple((int(item.depth), item.title) for item in req.items),
    )
    return {"ok": True, "data": result}


@router.post("/subjects/{subjectId}/projects/{scopedProjectId}/initialize-book-learning-objects-from-material")
def initialize_book_learning_objects_from_material(
    req: InitializeBookLearningObjectsFromMaterialRequest,
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
) -> dict:
    result = api.initialize_book_learning_objects_from_subject_material(  # type: ignore[arg-type]
        project.internal_project_id,
        source_material_id=req.sourceMaterialId,
    )
    return {"ok": True, "data": result}


@router.post("/subjects/{subjectId}/projects/{scopedProjectId}/sync-learning-objects-from-fs")
def sync_learning_objects_from_fs(project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    report = api.sync_learning_objects_from_fs(project.internal_project_id)  # type: ignore[arg-type]
    return {"ok": True, "data": report}


@router.post("/subjects/{subjectId}/projects/{scopedProjectId}/import-learning-objects-from-browser")
def import_learning_objects_from_browser(
    req: ImportBrowserDirectoryRequest,
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
) -> dict:
    report = api.import_learning_objects_from_browser_scan(  # type: ignore[arg-type]
        project.internal_project_id,
        root_title=req.rootTitle,
        relative_file_paths=req.relativeFilePaths,
    )
    return {"ok": True, "data": report}


@router.post("/subjects/{subjectId}/projects/{scopedProjectId}/import-learning-objects-from-native-local")
def import_learning_objects_from_native_local(
    req: ImportNativeLocalDirectoryRequest,
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
) -> dict:
    report = api.import_learning_objects_from_native_local_scan(  # type: ignore[arg-type]
        project.internal_project_id,
        project_root=req.projectRoot,
        root_title=req.rootTitle,
        relative_file_paths=req.relativeFilePaths,
    )
    return {"ok": True, "data": report}


@router.get("/subjects/{subjectId}/projects/{scopedProjectId}/baidu-netdisk/files")
def list_baidu_netdisk_files(
    request: Request,
    project: ScopedProject = Depends(resolve_scoped_project),
    accountId: str = Query(min_length=1),
    dirPath: str = Query(default="/"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=200, ge=1, le=500),
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    _ = project
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


@router.post("/subjects/{subjectId}/projects/{scopedProjectId}/import-learning-objects-from-baidu-netdisk")
def import_learning_objects_from_baidu_netdisk(
    req: ImportLearningObjectsFromBaiduNetdiskRequest,
    request: Request,
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    report = api.import_learning_objects_from_baidu_netdisk(  # type: ignore[arg-type]
        project.internal_project_id,
        auth_store=auth_store,
        user_id=user.user_id,
        account_id=req.accountId,
        items=[item.dict() for item in req.items],
    )
    return {"ok": True, "data": report}


@router.get("/subjects/{subjectId}/projects/{scopedProjectId}/missing-instances")
def list_missing_instances(project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    ids = api.list_missing_instances(project.internal_project_id)  # type: ignore[arg-type]
    return {"ok": True, "data": {"instanceIds": [str(x) for x in ids]}}


@router.get("/subjects/{subjectId}/projects/{scopedProjectId}/video-watch-progress")
def list_video_watch_progress(
    instanceIds: list[str] | None = Query(default=None),
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
) -> dict:
    ids = None if instanceIds is None else tuple(InstanceId(item) for item in instanceIds)
    items = api.list_video_watch_progress(project.internal_project_id, instance_ids=ids)  # type: ignore[arg-type]
    return {"ok": True, "data": {str(item.instance_id): video_watch_progress_to_dto(item, public_project_id=project.scoped_project_id) for item in items}}


@router.post("/subjects/{subjectId}/projects/{scopedProjectId}/instances/{instanceId}/video-watch-progress/ranges")
def record_video_watch_progress_range(
    instanceId: str,
    req: VideoWatchProgressRangeRequest,
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
) -> dict:
    item = api.record_video_watch_progress_range(  # type: ignore[arg-type]
        project.internal_project_id,
        InstanceId(instanceId),
        start_ms=req.startMs,
        end_ms=req.endMs,
        duration_ms=req.durationMs,
    )
    return {"ok": True, "data": video_watch_progress_to_dto(item, public_project_id=project.scoped_project_id)}


@router.post("/subjects/{subjectId}/projects/{scopedProjectId}/instances/{instanceId}/video-watch-progress/completed")
def mark_video_watch_progress_completed(
    instanceId: str,
    req: VideoWatchProgressCompletedRequest,
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
) -> dict:
    item = api.mark_video_watch_progress_completed(  # type: ignore[arg-type]
        project.internal_project_id,
        InstanceId(instanceId),
        duration_ms=req.durationMs,
    )
    return {"ok": True, "data": video_watch_progress_to_dto(item, public_project_id=project.scoped_project_id)}


@router.get("/subjects/{subjectId}/projects/{scopedProjectId}/instances/{instanceId}/recall-points")
def list_recall_points_by_instance(instanceId: str, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    ids = api.list_recall_points_by_instance(project.internal_project_id, InstanceId(instanceId))  # type: ignore[arg-type]
    return {"ok": True, "data": {"recallPointIds": [str(x) for x in ids]}}


@router.post("/subjects/{subjectId}/projects/{scopedProjectId}/instances/remap-recall-points")
def bulk_remap_recall_points_instance(
    req: BulkRemapRecallPointsInstanceRequest, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)
) -> dict:
    rp_ids = None if req.recallPointIds is None else tuple(RecallPointId(x) for x in req.recallPointIds)
    n = api.bulk_remap_recall_points_instance(  # type: ignore[arg-type]
        project.internal_project_id,
        from_instance_id=InstanceId(req.fromInstanceId),
        to_instance_id=InstanceId(req.toInstanceId),
        recall_point_ids=rp_ids,
    )
    return {"ok": True, "data": {"movedCount": int(n)}}


@router.post("/subjects/{subjectId}/projects/{scopedProjectId}/learning-objects/leaf")
def add_learning_object_leaf(req: AddLearningObjectLeafRequest, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    parent = None if req.parentId is None else LearningObjectNodeId(req.parentId)
    nid = api.add_learning_object_leaf(  # type: ignore[arg-type]
        project.internal_project_id, parent_id=parent, instance_id=InstanceId(req.instanceId), title=req.title
    )
    return {"ok": True, "data": {"nodeId": str(nid)}}


@router.post("/subjects/{subjectId}/projects/{scopedProjectId}/learning-objects/container")
def add_learning_object_container(
    req: AddLearningObjectContainerRequest, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)
) -> dict:
    parent = None if req.parentId is None else LearningObjectNodeId(req.parentId)
    children = tuple(LearningObjectNodeId(x) for x in req.children)
    nid = api.add_learning_object_container(  # type: ignore[arg-type]
        project.internal_project_id, parent_id=parent, children=children, title=req.title
    )
    return {"ok": True, "data": {"nodeId": str(nid)}}


@router.get("/subjects/{subjectId}/projects/{scopedProjectId}/learning-objects/{nodeId}")
def get_learning_object_node(nodeId: str, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    n = api.get_learning_object_node(project.internal_project_id, nodeId)  # type: ignore[arg-type]
    return {"ok": True, "data": learning_object_node_to_dto(n, public_project_id=project.scoped_project_id)}


@router.get("/subjects/{subjectId}/projects/{scopedProjectId}/learning-object-nodes")
def list_learning_object_nodes(project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    items = [learning_object_node_to_dto(n, public_project_id=project.scoped_project_id) for n in api.list_learning_object_nodes(project.internal_project_id)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}


@router.get("/subjects/{subjectId}/projects/{scopedProjectId}/learning-objects/{nodeId}/recall-points")
def list_recall_points_by_learning_object_node(nodeId: str, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    items = [recall_point_to_dto(rp, public_project_id=project.scoped_project_id) for rp in api.list_recall_points_by_learning_object_node(project.internal_project_id, nodeId)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}


@router.get("/subjects/{subjectId}/projects/{scopedProjectId}/learning-objects/{nodeId}/exports/recall-points")
def export_recall_points_by_learning_object_node(nodeId: str, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    items = [recall_point_to_dto(rp, public_project_id=project.scoped_project_id) for rp in api.export_recall_points_by_learning_object_node(project.internal_project_id, nodeId)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}


@router.get("/subjects/{subjectId}/projects/{scopedProjectId}/learning-objects/{nodeId}/exports/asr")
def export_asr_by_learning_object_node(nodeId: str, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    items = [asr_artifact_to_dto(art, public_project_id=project.scoped_project_id) for art in api.export_asr_by_learning_object_node(project.internal_project_id, nodeId)]  # type: ignore[arg-type]
    return {"ok": True, "data": items}


@router.get("/subjects/{subjectId}/projects/{scopedProjectId}/learning-object-roots")
def list_learning_object_roots(project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    ids = api.list_learning_object_roots(project.internal_project_id)  # type: ignore[arg-type]
    return {"ok": True, "data": {"rootLearningObjectNodeIds": [str(x) for x in ids]}}
