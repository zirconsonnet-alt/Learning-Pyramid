from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from adapter.auth import get_request_auth_user
from adapter.deps import get_api, get_auth_store
from adapter.mappers import asr_artifact_to_dto, asr_transcript_result_to_dto, instance_asr_transcript_result_to_dto
from adapter.scoped_projects import ScopedProject, resolve_scoped_project
from adapter.schemas import RequestAsrRequest, RequestInstanceAsrRequest
from backend.system.api import SystemAPI
from backend.system.api import MAX_ASR_UPLOAD_BYTES
from backend.system.auth_store import AuthStore
from backend.system.runtime_features import require_asr_enabled
from backend.models.errors import PreconditionFailure


router = APIRouter()


def content_length_or_none(request: Request) -> int | None:
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


def reject_oversized_asr_upload(content_length: int | None) -> None:
    if content_length is not None and content_length > MAX_ASR_UPLOAD_BYTES:
        raise PreconditionFailure(f"ASR audio upload is too large (max {MAX_ASR_UPLOAD_BYTES} bytes)")


def _service_config_dict(*, base_url: str | None = None, model_name: str | None = None, api_key: str | None = None) -> dict[str, str | None] | None:
    if base_url is None and model_name is None and api_key is None:
        return None
    return {
        "base_url": base_url,
        "model_name": model_name,
        "api_key": api_key,
    }


@router.get("/public/asr-bridge/{token}/{fileName:path}", include_in_schema=False)
def get_public_asr_bridge_asset(token: str, fileName: str, api: SystemAPI = Depends(get_api)) -> FileResponse:
    asset = api.get_public_asr_temp_asset(token)
    if asset is None:
        raise HTTPException(status_code=404, detail="Not found")
    path, content_type, actual_file_name = asset
    return FileResponse(
        str(path),
        media_type=content_type,
        filename=actual_file_name,
    )


@router.post("/subjects/{subjectId}/projects/{scopedProjectId}/asr")
def request_asr(
    req: RequestAsrRequest,
    request: Request,
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    require_asr_enabled()
    provider = req.provider or "WHISPER"
    current_user = get_request_auth_user(request)
    result = api.request_asr(  # type: ignore[arg-type]
        project.internal_project_id,
        req.recallPointId,
        req.centerMs,
        req.preMs,
        req.postMs,
        provider,
        _service_config_dict(
            base_url=None if req.serviceConfig is None else req.serviceConfig.baseUrl,
            model_name=None if req.serviceConfig is None else req.serviceConfig.modelName,
            api_key=None if req.serviceConfig is None else req.serviceConfig.apiKey,
        ),
        auth_store=auth_store,
        user_id=None if current_user is None else current_user.user_id,
    )
    return {"ok": True, "data": asr_transcript_result_to_dto(result, public_project_id=project.scoped_project_id)}


@router.post("/subjects/{subjectId}/projects/{scopedProjectId}/asr/audio")
async def request_asr_audio(
    request: Request,
    recallPointId: str = Form(...),
    centerMs: int = Form(...),
    preMs: int = Form(...),
    postMs: int = Form(...),
    provider: str | None = Form(None),
    serviceBaseUrl: str | None = Form(None),
    serviceModelName: str | None = Form(None),
    serviceApiKey: str | None = Form(None),
    file: UploadFile = File(...),
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    require_asr_enabled()
    current_user = get_request_auth_user(request)
    reject_oversized_asr_upload(content_length_or_none(request))
    payload = await file.read()
    result = api.request_asr_from_audio_upload(  # type: ignore[arg-type]
        project.internal_project_id,
        recallPointId,
        centerMs,
        preMs,
        postMs,
        payload,
        audio_filename=file.filename,
        audio_content_type=file.content_type,
        provider=provider or "WHISPER",
        service_config=_service_config_dict(
            base_url=serviceBaseUrl,
            model_name=serviceModelName,
            api_key=serviceApiKey,
        ),
        auth_store=auth_store,
        user_id=None if current_user is None else current_user.user_id,
    )
    return {"ok": True, "data": asr_transcript_result_to_dto(result, public_project_id=project.scoped_project_id)}


@router.post("/subjects/{subjectId}/projects/{scopedProjectId}/instances/{instanceId}/asr")
def request_instance_asr(
    instanceId: str,
    req: RequestInstanceAsrRequest,
    request: Request,
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    require_asr_enabled()
    provider = req.provider or "WHISPER"
    current_user = get_request_auth_user(request)
    result = api.request_instance_asr(  # type: ignore[arg-type]
        project.internal_project_id,
        instanceId,
        req.startMs,
        req.endMs,
        provider,
        _service_config_dict(
            base_url=None if req.serviceConfig is None else req.serviceConfig.baseUrl,
            model_name=None if req.serviceConfig is None else req.serviceConfig.modelName,
            api_key=None if req.serviceConfig is None else req.serviceConfig.apiKey,
        ),
        auth_store=auth_store,
        user_id=None if current_user is None else current_user.user_id,
    )
    return {"ok": True, "data": instance_asr_transcript_result_to_dto(result, public_project_id=project.scoped_project_id)}


@router.post("/subjects/{subjectId}/projects/{scopedProjectId}/instances/{instanceId}/asr/audio")
async def request_instance_asr_audio(
    instanceId: str,
    request: Request,
    startMs: int = Form(...),
    endMs: int = Form(...),
    provider: str | None = Form(None),
    serviceBaseUrl: str | None = Form(None),
    serviceModelName: str | None = Form(None),
    serviceApiKey: str | None = Form(None),
    file: UploadFile = File(...),
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    require_asr_enabled()
    current_user = get_request_auth_user(request)
    reject_oversized_asr_upload(content_length_or_none(request))
    payload = await file.read()
    result = api.request_instance_asr_from_audio_upload(  # type: ignore[arg-type]
        project.internal_project_id,
        instanceId,
        startMs,
        endMs,
        payload,
        audio_filename=file.filename,
        audio_content_type=file.content_type,
        provider=provider or "WHISPER",
        service_config=_service_config_dict(
            base_url=serviceBaseUrl,
            model_name=serviceModelName,
            api_key=serviceApiKey,
        ),
        auth_store=auth_store,
        user_id=None if current_user is None else current_user.user_id,
    )
    return {"ok": True, "data": instance_asr_transcript_result_to_dto(result, public_project_id=project.scoped_project_id)}


@router.get("/subjects/{subjectId}/projects/{scopedProjectId}/asr-artifacts/{asrArtifactId}")
def get_asr_artifact(asrArtifactId: str, project: ScopedProject = Depends(resolve_scoped_project), api: SystemAPI = Depends(get_api)) -> dict:
    require_asr_enabled()
    art = api.get_asr_artifact(project.internal_project_id, asrArtifactId)  # type: ignore[arg-type]
    return {"ok": True, "data": asr_artifact_to_dto(art, public_project_id=project.scoped_project_id)}
