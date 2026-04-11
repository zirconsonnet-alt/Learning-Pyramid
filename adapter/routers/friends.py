from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from adapter.auth import require_request_auth_user
from adapter.deps import get_api, get_auth_store
from adapter.schemas import CreateFriendRequestRequest
from backend.models.errors import NotFound
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthStore, AuthUser, FriendListItem, FriendRequest

router = APIRouter()
_LEARNING_EVENT_KIND = "SUBMIT_LEARNING_TASK"
_REVIEW_EVENT_KIND = "EXECUTOR_COMMIT_REVIEW_TASK"
_ACTIVE_FRIEND_LIMIT = 1000


def _avatar_url_for_user(user_id: str, avatar_key: str | None) -> str | None:
    if not avatar_key:
        return None
    return f"/api/profile/avatar/{user_id}"


def _friend_to_dto(item: FriendListItem) -> dict[str, str | None]:
    return {
        "userId": item.user_id,
        "publicUid": item.public_uid,
        "nickname": item.nickname,
        "bio": item.bio,
        "avatarUrl": _avatar_url_for_user(item.user_id, item.avatar_key),
        "friendedAt": item.friended_at,
    }


def _friend_request_to_dto(item: FriendRequest, *, viewer_user_id: str) -> dict[str, object]:
    if str(viewer_user_id) == item.requester_user_id:
        counterpart = {
            "userId": item.receiver_user_id,
            "publicUid": item.receiver_public_uid,
            "nickname": item.receiver_nickname,
            "bio": item.receiver_bio,
            "avatarUrl": _avatar_url_for_user(item.receiver_user_id, item.receiver_avatar_key),
        }
    else:
        counterpart = {
            "userId": item.requester_user_id,
            "publicUid": item.requester_public_uid,
            "nickname": item.requester_nickname,
            "bio": item.requester_bio,
            "avatarUrl": _avatar_url_for_user(item.requester_user_id, item.requester_avatar_key),
        }
    return {
        "requestId": item.request_id,
        "status": item.status,
        "message": item.message,
        "createdAt": item.created_at,
        "handledAt": item.handled_at,
        "handledByUserId": item.handled_by_user_id,
        "user": counterpart,
    }


def _public_user_to_dto(user: AuthUser) -> dict[str, str | None]:
    return {
        "userId": user.user_id,
        "publicUid": user.public_uid,
        "nickname": user.nickname,
        "bio": user.bio,
        "avatarUrl": _avatar_url_for_user(user.user_id, user.avatar_key),
    }


def _event_kind_text(value: object) -> str:
    return str(getattr(value, "value", value))


def _is_successful_study_event(event: object) -> bool:
    result = _event_kind_text(getattr(event, "result", ""))
    if result not in {"OK", "SUCCESS"}:
        return False
    return _event_kind_text(getattr(event, "kind", "")) in {_LEARNING_EVENT_KIND, _REVIEW_EVENT_KIND}


def _build_learning_stats_for_user(user_id: str, *, auth_store: AuthStore, api: SystemAPI) -> dict[str, int | str | None]:
    project_ids = auth_store.list_project_ids_for_user(user_id)
    learning_count = 0
    review_count = 0
    last_study_at: str | None = None
    study_days_from_metrics: set[str] = set()
    study_days_from_audit: set[str] = set()
    effective_ms = 0
    watch_ms = 0
    compose_ms = 0
    review_ms = 0
    qa_ms = 0

    for item in auth_store.list_user_project_daily_study_stats(user_id, project_ids=project_ids):
        effective_ms += item.effective_ms
        watch_ms += item.watch_ms
        compose_ms += item.compose_ms
        review_ms += item.review_ms
        qa_ms += item.qa_ms
        if item.effective_ms > 0 or item.watch_ms > 0 or item.compose_ms > 0 or item.review_ms > 0 or item.qa_ms > 0:
            study_days_from_metrics.add(item.date_key)
            if last_study_at is None or item.updated_at > last_study_at:
                last_study_at = item.updated_at

    for project_id in project_ids:
        try:
            events = api.list_audit_log_events(project_id)
        except NotFound:
            continue
        for event in events:
            if not _is_successful_study_event(event):
                continue
            kind = _event_kind_text(getattr(event, "kind", ""))
            if kind == _LEARNING_EVENT_KIND:
                learning_count += 1
            elif kind == _REVIEW_EVENT_KIND:
                review_count += 1
            occurred_at = str(getattr(event, "occurred_at", "") or "")
            if occurred_at and (last_study_at is None or occurred_at > last_study_at):
                last_study_at = occurred_at
            if occurred_at:
                study_days_from_audit.add(occurred_at[:10])

    # Prefer synced day buckets for user-facing day counts because date_key follows
    # the frontend's local-day semantics; audit timestamps are kept as a fallback for
    # historical records that predate study-metrics sync.
    study_days = study_days_from_metrics or study_days_from_audit

    return {
        "projectCount": len(project_ids),
        "effectiveMs": effective_ms,
        "watchMs": watch_ms,
        "composeMs": compose_ms,
        "reviewMs": review_ms,
        "qaMs": qa_ms,
        "learningCount": learning_count,
        "reviewCount": review_count,
        "totalActions": learning_count + review_count,
        "studyDays": len(study_days),
        "lastStudyAt": last_study_at,
    }


def _leaderboard_entry_sort_key(item: dict[str, object]) -> tuple[int, int, int, int, str, str]:
    stats = item["stats"]
    user = item["user"]
    if not isinstance(stats, dict) or not isinstance(user, dict):
        return (0, 0, 0, 0, "", "")
    return (
        int(stats.get("effectiveMs", 0)),
        int(stats.get("totalActions", 0)),
        int(stats.get("studyDays", 0)),
        int(stats.get("learningCount", 0)),
        str(stats.get("lastStudyAt") or ""),
        str(user.get("nickname") or ""),
    )


@router.get("/friends")
def list_friends(request: Request, limit: int = 100, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    user = require_request_auth_user(request)
    items = auth_store.list_friends_for_user(user.user_id, limit=limit)
    return {"ok": True, "data": [_friend_to_dto(item) for item in items]}


@router.get("/friends/requests")
def list_friend_requests(
    request: Request,
    box: str = "incoming",
    limit: int = 100,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    normalized_box = str(box).strip().lower()
    if normalized_box == "incoming":
        items = auth_store.list_incoming_friend_requests(user.user_id, limit=limit)
    elif normalized_box == "outgoing":
        items = auth_store.list_outgoing_friend_requests(user.user_id, limit=limit)
    else:
        raise HTTPException(status_code=400, detail="box must be incoming or outgoing")
    return {"ok": True, "data": [_friend_request_to_dto(item, viewer_user_id=user.user_id) for item in items]}


@router.get("/friends/leaderboard")
def get_friend_leaderboard(
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    api: SystemAPI = Depends(get_api),
) -> dict:
    user = require_request_auth_user(request)
    viewer = auth_store.get_user_by_id(user.user_id)
    items: list[dict[str, object]] = [
        {
            "user": _public_user_to_dto(viewer),
            "isSelf": True,
            "friendedAt": None,
            "stats": _build_learning_stats_for_user(viewer.user_id, auth_store=auth_store, api=api),
        }
    ]

    for friend in auth_store.list_friends_for_user(user.user_id, limit=_ACTIVE_FRIEND_LIMIT):
        try:
            friend_user = auth_store.get_user_by_id(friend.user_id)
        except NotFound:
            continue
        if friend_user.status != "active":
            continue
        items.append(
            {
                "user": _public_user_to_dto(friend_user),
                "isSelf": False,
                "friendedAt": friend.friended_at,
                "stats": _build_learning_stats_for_user(friend_user.user_id, auth_store=auth_store, api=api),
            }
        )

    items.sort(key=_leaderboard_entry_sort_key, reverse=True)
    return {"ok": True, "data": items}


@router.get("/friends/{friendUserId}/profile")
def get_friend_profile(
    friendUserId: str,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    api: SystemAPI = Depends(get_api),
) -> dict:
    user = require_request_auth_user(request)
    if not auth_store.users_are_friends(user.user_id, friendUserId):
        raise HTTPException(status_code=404, detail="Friend not found")
    try:
        friend = auth_store.get_user_by_id(friendUserId)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail="Friend not found") from exc
    if friend.status != "active":
        raise HTTPException(status_code=404, detail="Friend not found")
    return {
        "ok": True,
        "data": {
            **_public_user_to_dto(friend),
            "stats": _build_learning_stats_for_user(friend.user_id, auth_store=auth_store, api=api),
        },
    }


@router.post("/friends/requests")
def create_friend_request(
    req: CreateFriendRequestRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    user = require_request_auth_user(request)
    try:
        target = auth_store.get_user_by_public_uid(req.publicUid)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    if target.status != "active":
        raise HTTPException(status_code=404, detail="User not found")
    item = auth_store.create_friend_request(
        requester_user_id=user.user_id,
        receiver_user_id=target.user_id,
        message=req.message,
    )
    return {"ok": True, "data": _friend_request_to_dto(item, viewer_user_id=user.user_id)}


@router.post("/friends/requests/{requestId}/accept")
def accept_friend_request(requestId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    user = require_request_auth_user(request)
    try:
        item = auth_store.accept_friend_request(requestId, actor_user_id=user.user_id)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "data": _friend_request_to_dto(item, viewer_user_id=user.user_id)}


@router.post("/friends/requests/{requestId}/reject")
def reject_friend_request(requestId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    user = require_request_auth_user(request)
    try:
        item = auth_store.reject_friend_request(requestId, actor_user_id=user.user_id)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "data": _friend_request_to_dto(item, viewer_user_id=user.user_id)}


@router.post("/friends/requests/{requestId}/cancel")
def cancel_friend_request(requestId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    user = require_request_auth_user(request)
    try:
        item = auth_store.cancel_friend_request(requestId, actor_user_id=user.user_id)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "data": _friend_request_to_dto(item, viewer_user_id=user.user_id)}


@router.delete("/friends/{friendUserId}")
def delete_friendship(friendUserId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    user = require_request_auth_user(request)
    try:
        auth_store.delete_friendship(friendUserId, actor_user_id=user.user_id)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "data": None}
