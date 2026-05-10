import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse

from adapter.deps import get_api, get_auth_store
from adapter.scoped_projects import ScopedProject, resolve_scoped_project
from backend.models.errors import PreconditionFailure
from backend.models.types import MediaAssetId
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthStore
from backend.system.runtime_features import require_server_media_stream_enabled
from backend.system.runtime_env import resource_root


router = APIRouter()
MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024


def _content_length_or_none(request: Request) -> int | None:
    raw = str(request.headers.get("content-length", "")).strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise PreconditionFailure("Content-Length must be an integer") from exc
    if value < 0:
        raise PreconditionFailure("Content-Length must be non-negative")
    return value


def reject_oversized_image_upload(content_length: int | None) -> None:
    if content_length is not None and content_length > MAX_IMAGE_UPLOAD_BYTES:
        raise PreconditionFailure(f"image upload is too large (max {MAX_IMAGE_UPLOAD_BYTES} bytes)")


def _guide_demo_media_path(demo_id: str) -> Path:
    assets = {
        "study-review": "study-review-demo.mp4",
    }
    filename = assets.get(demo_id)
    if filename is None:
        raise PreconditionFailure("guide demo media not found")
    return resource_root() / "backend" / "system" / "guide_demo_assets" / filename


@router.get("/guide/demo-media/{demoId}")
def stream_guide_demo_media(demoId: str) -> FileResponse:
    file_path = _guide_demo_media_path(demoId)
    if not file_path.exists():
        raise PreconditionFailure(f"guide demo media file not found: {file_path}")
    if not file_path.is_file():
        raise PreconditionFailure(f"guide demo media is not a file: {file_path}")

    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(
        path=str(file_path),
        media_type=media_type or "video/mp4",
        filename=file_path.name,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.post("/subjects/{subjectId}/projects/{projectId}/media-assets")
async def upload_media_asset(request: Request, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    content_type = str(request.headers.get("content-type", "")).strip().lower()
    if not content_type.startswith("image/"):
        raise PreconditionFailure("Only image uploads are supported")
    reject_oversized_image_upload(_content_length_or_none(request))
    content = await request.body()
    if len(content) > MAX_IMAGE_UPLOAD_BYTES:
        raise PreconditionFailure(f"image upload is too large (max {MAX_IMAGE_UPLOAD_BYTES} bytes)")
    filename = request.headers.get("x-filename")
    asset = api.create_media_asset(  # type: ignore[arg-type]
        project.internal_project_id,
        content=content,
        mime_type=content_type,
        filename=None if filename is None else filename,
    )
    return {
        "ok": True,
        "data": {
            "assetId": str(asset.asset_id),
            "mimeType": asset.mime_type,
            "url": f"/api/subjects/{project.subject_id}/projects/{project.project_id}/media-assets/{asset.asset_id}",
        },
    }


@router.get("/subjects/{subjectId}/projects/{projectId}/media-assets/{assetId}")
def stream_media_asset(assetId: str, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> FileResponse:
    asset = api.get_media_asset(project.internal_project_id, MediaAssetId(assetId))  # type: ignore[arg-type]
    file_path = api.resolve_media_asset_file_path(project.internal_project_id, MediaAssetId(assetId))  # type: ignore[arg-type]
    if not file_path.exists():
        raise PreconditionFailure(f"media asset file not found: {file_path}")
    if not file_path.is_file():
        raise PreconditionFailure(f"media asset is not a file: {file_path}")
    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(path=str(file_path), media_type=asset.mime_type or media_type or "application/octet-stream", filename=file_path.name)


@router.get("/subjects/{subjectId}/projects/{projectId}/media/instances/{instanceId}")
def stream_instance_media(instanceId: str, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> FileResponse:
    require_server_media_stream_enabled()
    file_path = api.resolve_instance_media_file_path(project.internal_project_id, instanceId)  # type: ignore[arg-type]
    if not file_path.exists():
        raise PreconditionFailure(f"material file not found: {file_path}")
    if not file_path.is_file():
        raise PreconditionFailure(f"material is not a file: {file_path}")

    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(path=str(file_path), media_type=media_type or "application/octet-stream", filename=file_path.name)


@router.get("/subjects/{subjectId}/projects/{projectId}/media/instances/{instanceId}/playback")
def get_instance_playback(instanceId: str, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    media_base_path = f"/api/subjects/{project.subject_id}/projects/{project.project_id}/media/instances/{instanceId}"
    return {
        "ok": True,
        "data": api.get_instance_playback_descriptor(project.internal_project_id, instanceId, media_base_path=media_base_path),  # type: ignore[arg-type]
    }


@router.get("/subjects/{subjectId}/projects/{projectId}/media/instances/{instanceId}/hls.m3u8")
def get_instance_hls_playlist(
    instanceId: str,
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> Response:
    media_base_path = f"/api/subjects/{project.subject_id}/projects/{project.project_id}/media/instances/{instanceId}"
    playlist = api.get_instance_hls_playlist(project.internal_project_id, instanceId, auth_store=auth_store, media_base_path=media_base_path)  # type: ignore[arg-type]
    return Response(content=playlist, media_type="application/vnd.apple.mpegurl")


@router.get("/subjects/{subjectId}/projects/{projectId}/media/instances/{instanceId}/segments/{segmentPath:path}")
def get_instance_hls_segment(
    instanceId: str,
    segmentPath: str,
    upstream_url: str = Query(alias="u"),
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> StreamingResponse:
    upstream_response = api.stream_instance_hls_segment(  # type: ignore[arg-type]
        project.internal_project_id,
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


@router.get("/subjects/{subjectId}/projects/{projectId}/instances/{instanceId}/subtitle-file")
def get_instance_subtitle_file(
    instanceId: str,
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    return {
        "ok": True,
        "data": api.get_instance_subtitle_file_for_user(project.internal_project_id, instanceId, auth_store=auth_store),  # type: ignore[arg-type]
    }
