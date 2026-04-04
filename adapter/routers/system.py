from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from adapter.auth import get_request_auth_user
from adapter.deps import get_api, get_auth_store
from adapter.schemas import (
    AskLlmRequest,
    AskProjectLlmRawChatCompletionRequest,
    AskProjectLlmRequest,
    UpdateGlobalLlmSettingsRequest,
)
from adapter.runtime_status import collect_runtime_status
from backend.models.types import LearningObjectNodeId, LearningTaskNodeId, RecallPointId
from backend.models.errors import ExternalServiceError, NotFound, PreconditionFailure
from backend.system.runtime_features import current_runtime_features
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthStore
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


@router.get("/system/public-downloads")
def get_public_download_catalog() -> dict:
    return {"ok": True, "data": list_public_downloads()}


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
) -> dict:
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


@router.post("/projects/{projectId}/llm/ask")
def ask_project_llm(
    projectId: str,
    req: AskProjectLlmRequest,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    current_user = get_request_auth_user(request)
    content = api.request_project_llm_text(
        project_id=projectId,  # type: ignore[arg-type]
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


@router.post("/projects/{projectId}/llm/chat-completions")
def ask_project_llm_chat_completions(
    projectId: str,
    req: AskProjectLlmRawChatCompletionRequest,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    current_user = get_request_auth_user(request)
    data = api.request_llm_chat_completion_raw(
        messages=req.messages,
        tools=req.tools,
        tool_choice=req.toolChoice,
        parallel_tool_calls=req.parallelToolCalls,
        response_format=req.responseFormat,
        model_name=req.modelName,
        temperature=req.temperature,
        timeout_sec=90.0,
        auth_store=auth_store,
        user_id=None if current_user is None else current_user.user_id,
    )
    return {"ok": True, "data": data}


@router.get("/projects/{projectId}/llm/debug/latest")
def get_latest_project_llm_debug(
    projectId: str,
    api: SystemAPI = Depends(get_api),
) -> dict:
    return {"ok": True, "data": api.get_latest_project_llm_debug(projectId)}  # type: ignore[arg-type]


@router.post("/projects/{projectId}/llm/ask/stream")
def ask_project_llm_stream(
    projectId: str,
    req: AskProjectLlmRequest,
    request: Request,
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
) -> StreamingResponse:
    current_user = get_request_auth_user(request)

    def _event_stream():
        try:
            yield _sse_event("start", {"ok": True})
            for chunk in api.request_project_llm_text_stream(
                project_id=projectId,  # type: ignore[arg-type]
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
