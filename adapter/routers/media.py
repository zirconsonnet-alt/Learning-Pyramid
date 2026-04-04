from __future__ import annotations

import mimetypes

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse

from adapter.deps import get_api, get_auth_store
from backend.models.enums import InstancePresence, MaterialSourceKind, SessionMode
from backend.models.errors import PreconditionFailure
from backend.models.types import MediaAssetId
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthStore
from backend.system.material_paths import resolve_material_file_path
from backend.system.runtime_features import require_server_media_stream_enabled


router = APIRouter()


@router.post("/projects/{projectId}/media-assets")
async def upload_media_asset(projectId: str, request: Request, api: SystemAPI = Depends(get_api)) -> dict:
    content_type = str(request.headers.get("content-type", "")).strip().lower()
    if not content_type.startswith("image/"):
        raise PreconditionFailure("Only image uploads are supported")
    content = await request.body()
    filename = request.headers.get("x-filename")
    asset = api.create_media_asset(  # type: ignore[arg-type]
        projectId,
        content=content,
        mime_type=content_type,
        filename=None if filename is None else filename,
    )
    return {
        "ok": True,
        "data": {
            "assetId": str(asset.asset_id),
            "mimeType": asset.mime_type,
            "url": f"/api/projects/{projectId}/media-assets/{asset.asset_id}",
        },
    }


@router.get("/projects/{projectId}/media-assets/{assetId}")
def stream_media_asset(projectId: str, assetId: str, api: SystemAPI = Depends(get_api)) -> FileResponse:
    asset = api.get_media_asset(projectId, MediaAssetId(assetId))  # type: ignore[arg-type]
    file_path = api.resolve_media_asset_file_path(projectId, MediaAssetId(assetId))  # type: ignore[arg-type]
    if not file_path.exists():
        raise PreconditionFailure(f"media asset file not found: {file_path}")
    if not file_path.is_file():
        raise PreconditionFailure(f"media asset is not a file: {file_path}")
    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(path=str(file_path), media_type=asset.mime_type or media_type or "application/octet-stream", filename=file_path.name)


@router.get("/projects/{projectId}/media/instances/{instanceId}")
def stream_instance_media(projectId: str, instanceId: str, api: SystemAPI = Depends(get_api)) -> FileResponse:
    require_server_media_stream_enabled()
    source_kind = api._instance_media_service().get_effective_source_kind(projectId, instanceId)  # type: ignore[arg-type]
    if source_kind == MaterialSourceKind.BAIDU_NETDISK:
        raise PreconditionFailure("Baidu Netdisk instances must be played via the playback descriptor")
    inst = api.get_instance(projectId, instanceId)  # type: ignore[arg-type]
    if getattr(inst, "presence", None) == InstancePresence.MISSING:
        raise PreconditionFailure("material is MISSING")

    session = api.begin_session(projectId, SessionMode.READ_ONLY)  # type: ignore[arg-type]
    try:
        storage_cfg = api.sys.project_storage_config_repo.get(session)
    finally:
        api.sys.rollback(session)

    file_path = resolve_material_file_path(storage_cfg, inst.material_id, source_kind=source_kind)
    if not file_path.exists():
        raise PreconditionFailure(f"material file not found: {file_path}")
    if not file_path.is_file():
        raise PreconditionFailure(f"material is not a file: {file_path}")

    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(path=str(file_path), media_type=media_type or "application/octet-stream", filename=file_path.name)


@router.get("/projects/{projectId}/media/instances/{instanceId}/playback")
def get_instance_playback(projectId: str, instanceId: str, api: SystemAPI = Depends(get_api)) -> dict:
    return {
        "ok": True,
        "data": api.get_instance_playback_descriptor(projectId, instanceId),  # type: ignore[arg-type]
    }


@router.get("/projects/{projectId}/media/instances/{instanceId}/hls.m3u8")
def get_instance_hls_playlist(
    projectId: str,
    instanceId: str,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> Response:
    playlist = api.get_instance_hls_playlist(projectId, instanceId, auth_store=auth_store)  # type: ignore[arg-type]
    return Response(content=playlist, media_type="application/vnd.apple.mpegurl")


@router.get("/projects/{projectId}/media/instances/{instanceId}/segments/{segmentPath:path}")
def get_instance_hls_segment(
    projectId: str,
    instanceId: str,
    segmentPath: str,
    upstream_url: str = Query(alias="u"),
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> StreamingResponse:
    upstream_response = api.stream_instance_hls_segment(  # type: ignore[arg-type]
        projectId,
        instanceId,
        auth_store=auth_store,
        upstream_url=upstream_url,
    )
    content_type = str(upstream_response.headers.get("content-type") or "application/octet-stream")

    def _iter_bytes():
        try:
            for chunk in upstream_response.iter_content(chunk_size=64 * 1024):
                if chunk:
                    yield chunk
        finally:
            upstream_response.close()

    return StreamingResponse(_iter_bytes(), media_type=content_type)


@router.get("/projects/{projectId}/instances/{instanceId}/subtitle-file")
def get_instance_subtitle_file(
    projectId: str,
    instanceId: str,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    return {
        "ok": True,
        "data": api.get_instance_subtitle_file_for_user(projectId, instanceId, auth_store=auth_store),  # type: ignore[arg-type]
    }
