from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from adapter.auth import get_request_auth_user
from adapter.deps import get_api, get_auth_store
from adapter.mappers import asr_artifact_to_dto, asr_transcript_result_to_dto, instance_asr_transcript_result_to_dto
from adapter.schemas import RequestAsrRequest, RequestInstanceAsrRequest
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthStore
from backend.system.runtime_features import require_asr_enabled


router = APIRouter()


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


@router.post("/projects/{projectId}/asr")
def request_asr(
    projectId: str,
    req: RequestAsrRequest,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    require_asr_enabled()
    provider = req.provider or "WHISPER"
    current_user = get_request_auth_user(request)
    result = api.request_asr(  # type: ignore[arg-type]
        projectId,
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
    return {"ok": True, "data": asr_transcript_result_to_dto(result)}


@router.post("/projects/{projectId}/asr/audio")
async def request_asr_audio(
    projectId: str,
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
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    require_asr_enabled()
    current_user = get_request_auth_user(request)
    payload = await file.read()
    result = api.request_asr_from_audio_upload(  # type: ignore[arg-type]
        projectId,
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
    return {"ok": True, "data": asr_transcript_result_to_dto(result)}


@router.post("/projects/{projectId}/instances/{instanceId}/asr")
def request_instance_asr(
    projectId: str,
    instanceId: str,
    req: RequestInstanceAsrRequest,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    require_asr_enabled()
    provider = req.provider or "WHISPER"
    current_user = get_request_auth_user(request)
    result = api.request_instance_asr(  # type: ignore[arg-type]
        projectId,
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
    return {"ok": True, "data": instance_asr_transcript_result_to_dto(result)}


@router.post("/projects/{projectId}/instances/{instanceId}/asr/audio")
async def request_instance_asr_audio(
    projectId: str,
    instanceId: str,
    request: Request,
    startMs: int = Form(...),
    endMs: int = Form(...),
    provider: str | None = Form(None),
    serviceBaseUrl: str | None = Form(None),
    serviceModelName: str | None = Form(None),
    serviceApiKey: str | None = Form(None),
    file: UploadFile = File(...),
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    require_asr_enabled()
    current_user = get_request_auth_user(request)
    payload = await file.read()
    result = api.request_instance_asr_from_audio_upload(  # type: ignore[arg-type]
        projectId,
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
    return {"ok": True, "data": instance_asr_transcript_result_to_dto(result)}


@router.get("/projects/{projectId}/asr-artifacts/{asrArtifactId}")
def get_asr_artifact(projectId: str, asrArtifactId: str, api: SystemAPI = Depends(get_api)) -> dict:
    require_asr_enabled()
    art = api.get_asr_artifact(projectId, asrArtifactId)  # type: ignore[arg-type]
    return {"ok": True, "data": asr_artifact_to_dto(art)}
