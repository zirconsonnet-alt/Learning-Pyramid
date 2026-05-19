from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from adapter.auth import SESSION_COOKIE_NAME, require_request_auth_user
from adapter.deps import get_api, get_auth_store, get_membership_store, require_active_membership
from adapter.schemas import (
    ChangePasswordRequest,
    LearningPlansPayloadDTO,
    SyncStudyMetricsRequest,
    UpdateProfileRequest,
    UpdateUserGlobalSettingsRequest,
    UpdateUserServiceSettingsRequest,
)
from backend.system.api import SystemAPI
from backend.system.app_paths import default_data_dir
from backend.system.auth_store import (
    AuthStore,
    AuthUser,
    UserGlobalSettings,
    UserProjectDailyStudyStat,
    UserProjectDailyStudyStatInput,
    _pomodoro_micro_break_settings_to_json,
    _pomodoro_weekly_schedule_to_json,
)
from backend.system.membership_store import MembershipStore
from backend.system.baidu_netdisk_client import BAIDU_NETDISK_PROVIDER

router = APIRouter()

_AVATAR_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
_MAX_AVATAR_BYTES = 2 * 1024 * 1024


def _avatar_dir() -> Path:
    path = default_data_dir() / "avatars" / "users"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _avatar_path_for_key(avatar_key: str) -> Path:
    return _avatar_dir() / avatar_key


def _avatar_url_for_user(user: AuthUser) -> str | None:
    if not user.avatar_key:
        return None
    return f"/api/profile/avatar/{user.user_id}?v={user.updated_at}"


def _profile_to_dto(user: AuthUser) -> dict[str, str | None]:
    return {
        "userId": user.user_id,
        "email": user.email,
        "publicUid": user.public_uid,
        "nickname": user.nickname,
        "bio": user.bio,
        "avatarUrl": _avatar_url_for_user(user),
        "status": user.status,
        "createdAt": user.created_at,
        "updatedAt": user.updated_at,
    }


def _public_user_to_dto(user: AuthUser) -> dict[str, str | None]:
    return {
        "userId": user.user_id,
        "publicUid": user.public_uid,
        "nickname": user.nickname,
        "bio": user.bio,
        "avatarUrl": _avatar_url_for_user(user),
    }


def _study_stat_to_dto(item: UserProjectDailyStudyStat) -> dict:
    def map_ranges(ranges: tuple[tuple[int, int], ...]) -> list[dict[str, int]]:
        return [{"startMs": int(start_ms), "endMs": int(end_ms)} for start_ms, end_ms in ranges]

    return {
        "projectId": item.project_id,
        "dateKey": item.date_key,
        "schemaVersion": item.schema_version,
        "webPresenceMs": item.web_presence_ms,
        "videoMs": item.video_ms,
        "recallEntryMs": item.recall_entry_ms,
        "aiQaMs": item.ai_qa_ms,
        "distractionMs": item.distraction_ms,
        "presenceRanges": map_ranges(item.presence_ranges),
        "videoRanges": map_ranges(item.video_ranges),
        "recallEntryRanges": map_ranges(item.recall_entry_ranges),
        "aiQaRanges": map_ranges(item.ai_qa_ranges),
        "isPartitionComplete": item.is_partition_complete,
        "effectiveMs": item.effective_ms,
        "watchMs": item.watch_ms,
        "composeMs": item.compose_ms,
        "reviewMs": item.review_ms,
        "qaMs": item.qa_ms,
        "effectiveRanges": map_ranges(item.effective_ranges),
        "watchRanges": map_ranges(item.watch_ranges),
        "composeRanges": map_ranges(item.compose_ranges),
        "reviewRanges": map_ranges(item.review_ranges),
        "qaRanges": map_ranges(item.qa_ranges),
        "updatedAt": item.updated_at,
    }


def _global_settings_to_dto(item: UserGlobalSettings) -> dict:
    template = []
    for step in item.default_project_review_template:
        if step.kind == "REVIEW_TASK" and int(step.count or 1) > 1:
            template.append({"kind": "REVIEW_TASK", "count": int(step.count or 1)})
        else:
            template.append({"kind": step.kind})
    weekly_schedule = _pomodoro_weekly_schedule_to_json(item.pomodoro_weekly_schedule)
    return {
        "theme": item.theme,
        "pomodoro": {
            "enabled": item.pomodoro_enabled,
            "transitionSoundEnabled": item.pomodoro_transition_sound_enabled,
            "defaultFocusPrompt": item.pomodoro_default_focus_prompt,
            "defaultBreakPrompt": item.pomodoro_default_break_prompt,
            "microBreaks": _pomodoro_micro_break_settings_to_json(item.pomodoro_micro_breaks),
            "weeklySchedule": weekly_schedule,
        },
        "defaultProjectReviewTemplate": template,
        "learningPlans": item.learning_plans,
        "updatedAt": item.updated_at,
    }


def _learning_plans_to_dto(payload: dict) -> dict:
    dto = LearningPlansPayloadDTO(**payload)
    return dto.dict()


def _require_owned_project_ids(user_id: str, project_ids: list[str], auth_store: AuthStore) -> list[str]:
    normalized = list(dict.fromkeys(str(project_id).strip() for project_id in project_ids if str(project_id).strip()))
    if not normalized:
        return []
    allowed = set(auth_store.list_project_ids_for_user(user_id))
    forbidden = [project_id for project_id in normalized if project_id not in allowed]
    if forbidden:
        raise HTTPException(status_code=403, detail=f"Project access denied: {forbidden[0]}")
    return normalized


@router.get("/profile/me")
def get_my_profile(request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    user = require_request_auth_user(request)
    return {"ok": True, "data": _profile_to_dto(auth_store.get_user_by_id(user.user_id))}


@router.patch("/profile/me")
def update_my_profile(
    req: UpdateProfileRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    updated = auth_store.update_user_profile(user.user_id, nickname=req.nickname, bio=req.bio)
    return {"ok": True, "data": _profile_to_dto(updated)}


@router.post("/profile/me/password")
def change_my_password(
    req: ChangePasswordRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    auth_store.change_password(user.user_id, current_password=req.currentPassword, new_password=req.newPassword)
    current_token = str(request.cookies.get(SESSION_COOKIE_NAME, "")).strip() or None
    auth_store.delete_other_sessions_for_user(user.user_id, except_session_token=current_token)
    return {"ok": True, "data": None}


@router.get("/profile/me/llm-settings")
def get_my_llm_settings(
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    api: SystemAPI = Depends(get_api),
    membership_store: MembershipStore = Depends(get_membership_store),
) -> dict:
    require_active_membership(request, membership_store)
    user = require_request_auth_user(request)
    return {"ok": True, "data": api.get_user_llm_status(auth_store=auth_store, user_id=user.user_id)}


@router.put("/profile/me/llm-settings")
def update_my_llm_settings(
    req: UpdateUserServiceSettingsRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    api: SystemAPI = Depends(get_api),
    membership_store: MembershipStore = Depends(get_membership_store),
) -> dict:
    require_active_membership(request, membership_store)
    user = require_request_auth_user(request)
    return {
        "ok": True,
        "data": api.update_user_llm_settings(
            auth_store=auth_store,
            user_id=user.user_id,
            base_url=req.baseUrl,
            model_name=req.modelName,
            api_key=req.apiKey,
            prompt_assembly_mode=req.promptAssemblyMode,
            clear_api_key=bool(req.clearApiKey),
        ),
    }


@router.get("/profile/me/asr-settings")
def get_my_asr_settings(
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    api: SystemAPI = Depends(get_api),
) -> dict:
    user = require_request_auth_user(request)
    return {"ok": True, "data": api.get_user_asr_status(auth_store=auth_store, user_id=user.user_id)}


@router.put("/profile/me/asr-settings")
def update_my_asr_settings(
    req: UpdateUserServiceSettingsRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    api: SystemAPI = Depends(get_api),
) -> dict:
    user = require_request_auth_user(request)
    return {
        "ok": True,
        "data": api.update_user_asr_settings(
            auth_store=auth_store,
            user_id=user.user_id,
            base_url=req.baseUrl,
            model_name=req.modelName,
            api_key=req.apiKey,
            clear_api_key=bool(req.clearApiKey),
        ),
    }


@router.get("/profile/me/global-settings")
def get_my_global_settings(
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    return {"ok": True, "data": _global_settings_to_dto(auth_store.get_user_global_settings(user.user_id))}


@router.put("/profile/me/global-settings")
def update_my_global_settings(
    req: UpdateUserGlobalSettingsRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    updated = auth_store.upsert_user_global_settings(
        user.user_id,
        theme=req.theme,
        pomodoro_enabled=bool(req.pomodoro.enabled),
        pomodoro_transition_sound_enabled=bool(req.pomodoro.transitionSoundEnabled),
        pomodoro_default_focus_prompt=req.pomodoro.defaultFocusPrompt,
        pomodoro_default_break_prompt=req.pomodoro.defaultBreakPrompt,
        pomodoro_micro_breaks=req.pomodoro.microBreaks.dict(),
        pomodoro_weekly_schedule=req.pomodoro.weeklySchedule.dict(),
        default_project_review_template=(
            {"kind": item.kind, "count": item.count} for item in req.defaultProjectReviewTemplate
        ),
    )
    return {"ok": True, "data": _global_settings_to_dto(updated)}


@router.get("/profile/me/learning-plans")
def get_my_learning_plans(
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    return {"ok": True, "data": _learning_plans_to_dto(auth_store.get_user_learning_plans(user.user_id))}


@router.put("/profile/me/learning-plans")
def update_my_learning_plans(
    req: LearningPlansPayloadDTO,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    updated = auth_store.upsert_user_learning_plans(user.user_id, learning_plans=req.dict())
    return {"ok": True, "data": _learning_plans_to_dto(updated)}


@router.get("/profile/me/cloud-accounts/baidu-netdisk")
def list_my_baidu_netdisk_accounts(
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    api: SystemAPI = Depends(get_api),
) -> dict:
    user = require_request_auth_user(request)
    return {
        "ok": True,
        "data": api.list_user_cloud_accounts(
            auth_store=auth_store,
            user_id=user.user_id,
            provider=BAIDU_NETDISK_PROVIDER,
        ),
    }


@router.post("/profile/me/cloud-accounts/baidu-netdisk/connect")
def begin_baidu_netdisk_connect(
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    api: SystemAPI = Depends(get_api),
) -> dict:
    user = require_request_auth_user(request)
    return {"ok": True, "data": api.begin_baidu_netdisk_connect(auth_store=auth_store, user_id=user.user_id)}


@router.delete("/profile/me/cloud-accounts/baidu-netdisk/{accountId}")
def disable_baidu_netdisk_account(
    accountId: str,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    api: SystemAPI = Depends(get_api),
) -> dict:
    user = require_request_auth_user(request)
    api.disable_baidu_netdisk_account(
        auth_store=auth_store,
        user_id=user.user_id,
        account_id=accountId,
    )
    return {"ok": True, "data": None}


@router.put("/profile/me/avatar")
async def upload_my_avatar(request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    user = require_request_auth_user(request)
    content_type = str(request.headers.get("content-type", "")).split(";", 1)[0].strip().lower()
    suffix = _AVATAR_CONTENT_TYPES.get(content_type)
    if suffix is None:
        raise HTTPException(status_code=400, detail="Only jpeg, png, and webp avatars are supported")
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Avatar payload is empty")
    if len(body) > _MAX_AVATAR_BYTES:
        raise HTTPException(status_code=400, detail="Avatar must be 2 MB or smaller")

    for candidate in _avatar_dir().glob(f"{user.user_id}.*"):
        if candidate.is_file():
            candidate.unlink(missing_ok=True)
    avatar_key = f"{user.user_id}{suffix}"
    _avatar_path_for_key(avatar_key).write_bytes(body)
    updated = auth_store.update_user_avatar(user.user_id, avatar_key=avatar_key)
    return {"ok": True, "data": _profile_to_dto(updated)}


@router.get("/profile/avatar/{userId}")
def get_user_avatar(userId: str, auth_store: AuthStore = Depends(get_auth_store)):
    user = auth_store.get_user_by_id(userId)
    if not user.avatar_key:
        raise HTTPException(status_code=404, detail="Avatar not found")
    path = _avatar_path_for_key(user.avatar_key)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Avatar not found")
    return FileResponse(str(path))


@router.get("/users/by-uid/{publicUid}")
def find_user_by_public_uid(publicUid: str, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    user = auth_store.get_user_by_public_uid(publicUid)
    if user.status != "active":
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "data": _public_user_to_dto(user)}


@router.post("/profile/me/study-metrics/sync")
def sync_my_study_metrics(
    req: SyncStudyMetricsRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    entry_project_ids = [entry.projectId for entry in req.entries]
    requested_project_ids = _require_owned_project_ids(user.user_id, [*req.projectIds, *entry_project_ids], auth_store)
    if not requested_project_ids:
        return {"ok": True, "data": []}

    entries = tuple(
        UserProjectDailyStudyStatInput.create(
            project_id=entry.projectId,
            date_key=entry.dateKey,
            schema_version=entry.schemaVersion,
            web_presence_ms=entry.webPresenceMs,
            video_ms=entry.videoMs,
            recall_entry_ms=entry.recallEntryMs,
            ai_qa_ms=entry.aiQaMs,
            distraction_ms=entry.distractionMs,
            presence_ranges=((item.startMs, item.endMs) for item in entry.presenceRanges),
            video_ranges=((item.startMs, item.endMs) for item in entry.videoRanges),
            recall_entry_ranges=((item.startMs, item.endMs) for item in entry.recallEntryRanges),
            ai_qa_ranges=((item.startMs, item.endMs) for item in entry.aiQaRanges),
            is_partition_complete=entry.isPartitionComplete,
            effective_ms=entry.effectiveMs,
            watch_ms=entry.watchMs,
            compose_ms=entry.composeMs,
            review_ms=entry.reviewMs,
            qa_ms=entry.qaMs,
            effective_ranges=((item.startMs, item.endMs) for item in entry.effectiveRanges),
            watch_ranges=((item.startMs, item.endMs) for item in entry.watchRanges),
            compose_ranges=((item.startMs, item.endMs) for item in entry.composeRanges),
            review_ranges=((item.startMs, item.endMs) for item in entry.reviewRanges),
            qa_ranges=((item.startMs, item.endMs) for item in entry.qaRanges),
        )
        for entry in req.entries
    )
    if entries:
        auth_store.upsert_user_project_daily_study_stats(user.user_id, entries=entries)
    items = auth_store.list_user_project_daily_study_stats(
        user.user_id,
        project_ids=requested_project_ids,
        date_from=req.dateFrom,
        date_to=req.dateTo,
    )
    return {"ok": True, "data": [_study_stat_to_dto(item) for item in items]}
