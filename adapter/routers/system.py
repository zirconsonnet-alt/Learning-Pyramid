import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from adapter.auth import get_request_auth_user
from adapter.deps import get_api, get_auth_store, get_membership_store, require_active_membership
from adapter.scoped_projects import ScopedProject, resolve_scoped_project
from adapter.schemas import (
    AskLlmRequest,
    AskProjectLlmRawChatCompletionRequest,
    AskProjectLlmRequest,
    PomodoroTtsPreviewRequest,
    UpdateGlobalLlmSettingsRequest,
)
from adapter.runtime_status import collect_runtime_status
from backend.models.types import LearningObjectNodeId, LearningTaskNodeId, RecallPointId
from backend.models.errors import ExternalServiceError, NotFound, PreconditionFailure
from backend.system.email_verification_delivery import email_verification_enabled
from backend.system.password_reset_delivery import password_reset_enabled
from backend.system.runtime_features import current_runtime_features
from backend.system.signup_human_check import current_signup_human_check_config, signup_human_check_enabled
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthStore
from backend.system.membership_store import MembershipStore
from backend.system.pomodoro_tts import PomodoroTtsUnavailable, synthesize_pomodoro_prompt_audio
from backend.system.public_downloads import list_public_downloads


router = APIRouter()


def _sse_event(event: str, payload: dict[str, object]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


def _stream_error_payload(exc: Exception) -> dict[str, object]:
    if isinstance(exc, PreconditionFailure):
        return {"code": "PRECONDITION", "message": str(exc)}
    if isinstance(exc, NotFound):
        return {"code": "NOT_FOUND", "message": str(exc)}
    if isinstance(exc, ExternalServiceError):
        return {"code": "EXTERNAL_SERVICE", "message": str(exc)}
    return {"code": "UNKNOWN", "message": "Internal server error"}


@router.get("/system/capabilities")
def get_system_capabilities(
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    features = current_runtime_features()
    human_check_cfg = current_signup_human_check_config()
    human_check_enabled = signup_human_check_enabled()
    current_user = get_request_auth_user(request)
    ready, runtime = collect_runtime_status(
        user_id=None if current_user is None else current_user.user_id,
        auth_store=auth_store,
    )
    return {
        "ok": True,
        "data": {
            "appMode": features.app_mode,
            "asrEnabled": features.asr_enabled,
            "serverMediaStreamEnabled": features.server_media_stream_enabled,
            "browserLocalMediaEnabled": features.browser_local_media_enabled,
            "baiduNetdiskEnabled": features.baidu_netdisk_enabled,
            "authEnabled": features.auth_enabled,
            "allowSignup": features.allow_signup,
            "signupInviteRequired": features.signup_invite_required,
            "passwordResetEnabled": password_reset_enabled(),
            "emailVerificationEnabled": email_verification_enabled(),
            "signupHumanCheckEnabled": human_check_enabled,
            "signupHumanCheckProvider": human_check_cfg.provider if human_check_enabled else None,
            "signupHumanCheckChallengeUrl": human_check_cfg.challenge_url if human_check_enabled else None,
            "sqlBackend": runtime.get("sqlBackend"),
            "llmConfigured": bool(runtime.get("llmConfigured", False)),
            "storyGenerationConfigured": bool(runtime.get("storyGenerationConfigured", False)),
            "llmSource": runtime.get("llmSource", "none"),
            "ready": ready,
        },
    }


@router.get("/system/runtime")
def get_system_runtime(
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> JSONResponse:
    current_user = get_request_auth_user(request)
    ready, runtime = collect_runtime_status(
        user_id=None if current_user is None else current_user.user_id,
        auth_store=auth_store,
    )
    return JSONResponse(status_code=200 if ready else 503, content={"ok": ready, "data": runtime})


@router.get("/system/data-safety")
def get_system_data_safety(api: SystemAPI = Depends(get_api)) -> dict:
    return {"ok": True, "data": api.get_data_safety_status()}


@router.post("/system/data-safety/check")
def run_system_data_safety_check(api: SystemAPI = Depends(get_api)) -> dict:
    return {"ok": True, "data": api.get_data_safety_status()}


@router.get("/system/public-downloads")
def get_public_download_catalog() -> dict:
    return {"ok": True, "data": list_public_downloads()}


@router.post("/system/pomodoro/tts-preview")
async def synthesize_pomodoro_tts_preview(
    req: PomodoroTtsPreviewRequest,
    request: Request,
    membership_store: MembershipStore = Depends(get_membership_store),
) -> Response:
    if current_runtime_features().auth_enabled:
        require_active_membership(request, membership_store)
    try:
        audio_bytes = await synthesize_pomodoro_prompt_audio(req.text)
    except PomodoroTtsUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'inline; filename="pomodoro-preview.mp3"',
        },
    )


@router.get("/system/global-llm-settings")
def get_global_llm_settings(
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    if current_runtime_features().auth_enabled:
        raise PreconditionFailure("Global LLM settings are disabled when auth is enabled")
    return {"ok": True, "data": api.get_global_llm_status()}


@router.put("/system/global-llm-settings")
def update_global_llm_settings(
    req: UpdateGlobalLlmSettingsRequest,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    if current_runtime_features().auth_enabled:
        raise PreconditionFailure("Global LLM settings are disabled when auth is enabled")
    return {
        "ok": True,
        "data": api.update_global_llm_settings(
            base_url=req.baseUrl,
            model_name=req.modelName,
            api_key=req.apiKey,
            prompt_assembly_mode=req.promptAssemblyMode,
            clear_api_key=bool(req.clearApiKey),
        ),
    }


@router.post("/system/llm/ask")
def ask_llm(
    req: AskLlmRequest,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
    membership_store: MembershipStore = Depends(get_membership_store),
) -> dict:
    if current_runtime_features().auth_enabled:
        require_active_membership(request, membership_store)
    current_user = get_request_auth_user(request)
    content = api.request_llm_text(
        user_prompt=req.prompt,
        system_prompt=req.systemPrompt,
        model_name=req.modelName,
        temperature=req.temperature,
        auth_store=auth_store,
        user_id=None if current_user is None else current_user.user_id,
    )
    return {"ok": True, "data": {"content": content}}


@router.post("/subjects/{subjectId}/projects/{projectId}/llm/ask")
def ask_project_llm(
    req: AskProjectLlmRequest,
    request: Request,
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
    membership_store: MembershipStore = Depends(get_membership_store),
) -> dict:
    if current_runtime_features().auth_enabled:
        require_active_membership(request, membership_store)
    current_user = get_request_auth_user(request)
    content = api.request_project_llm_text(
        project_id=project.internal_project_id,  # type: ignore[arg-type]
        user_prompt=req.prompt,
        system_prompt=req.systemPrompt,
        supplemental_context=req.supplementalContext,
        model_name=req.modelName,
        temperature=req.temperature,
        recall_point_id=None if req.recallPointId is None else RecallPointId(req.recallPointId),
        learning_task_node_id=None if req.learningTaskNodeId is None else LearningTaskNodeId(req.learningTaskNodeId),
        learning_object_node_id=None if req.learningObjectNodeId is None else LearningObjectNodeId(req.learningObjectNodeId),
        auth_store=auth_store,
        user_id=None if current_user is None else current_user.user_id,
    )
    return {"ok": True, "data": {"content": content}}


def reject_scoped_raw_llm_chat() -> None:
    raise PreconditionFailure("scoped raw LLM chat completions are not supported; use project LLM ask endpoints")


@router.post("/subjects/{subjectId}/projects/{projectId}/llm/chat-completions")
def ask_project_llm_chat_completions(
    req: AskProjectLlmRawChatCompletionRequest,
    request: Request,
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
    membership_store: MembershipStore = Depends(get_membership_store),
) -> dict:
    reject_scoped_raw_llm_chat()


@router.get("/subjects/{subjectId}/projects/{projectId}/llm/debug/latest")
def get_latest_project_llm_debug(
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
) -> dict:
    return {"ok": True, "data": api.get_latest_project_llm_debug(project.internal_project_id)}  # type: ignore[arg-type]


@router.post("/subjects/{subjectId}/projects/{projectId}/llm/ask/stream")
def ask_project_llm_stream(
    req: AskProjectLlmRequest,
    request: Request,
    project: ScopedProject = Depends(resolve_scoped_project),
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
    membership_store: MembershipStore = Depends(get_membership_store),
) -> StreamingResponse:
    current_user = get_request_auth_user(request)

    def _event_stream():
        try:
            if current_runtime_features().auth_enabled:
                require_active_membership(request, membership_store)
            yield _sse_event("start", {"ok": True})
            for chunk in api.request_project_llm_text_stream(
                project_id=project.internal_project_id,  # type: ignore[arg-type]
                user_prompt=req.prompt,
                system_prompt=req.systemPrompt,
                supplemental_context=req.supplementalContext,
                model_name=req.modelName,
                temperature=req.temperature,
                recall_point_id=None if req.recallPointId is None else RecallPointId(req.recallPointId),
                learning_task_node_id=None if req.learningTaskNodeId is None else LearningTaskNodeId(req.learningTaskNodeId),
                learning_object_node_id=None if req.learningObjectNodeId is None else LearningObjectNodeId(req.learningObjectNodeId),
                timeout_sec=90.0,
                auth_store=auth_store,
                user_id=None if current_user is None else current_user.user_id,
            ):
                if chunk:
                    yield _sse_event("delta", {"content": chunk})
            yield _sse_event("done", {"ok": True})
        except Exception as exc:
            yield _sse_event("error", _stream_error_payload(exc))

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
