from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from adapter.auth import SESSION_COOKIE_NAME, require_request_auth_user
from adapter.deps import get_auth_store
from adapter.schemas import ChangePasswordRequest, UpdateProfileRequest
from backend.system.app_paths import default_data_dir
from backend.system.auth_store import AuthStore, AuthUser

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
