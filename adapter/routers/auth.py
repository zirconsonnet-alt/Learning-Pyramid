from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from adapter.auth import SESSION_COOKIE_NAME, clear_auth_cookie, resolve_session_user, set_auth_cookie
from adapter.deps import get_auth_store
from adapter.schemas import AuthCredentialsRequest
from backend.models.errors import PreconditionFailure
from backend.system.auth_store import AuthStore, AuthUser
from backend.system.runtime_features import current_runtime_features


router = APIRouter()


def _user_to_dto(user: AuthUser, auth_store: AuthStore) -> dict[str, object]:
    return {
        "userId": user.user_id,
        "email": user.email,
        "createdAt": user.created_at,
        "publicUid": user.public_uid,
        "nickname": user.nickname,
        "bio": user.bio,
        "avatarUrl": None if not user.avatar_key else f"/api/profile/avatar/{user.user_id}?v={user.updated_at}",
        "status": user.status,
        "updatedAt": user.updated_at,
        "roles": list(auth_store.list_user_roles(user.user_id)),
    }


@router.post("/auth/register")
def register_auth_user(req: AuthCredentialsRequest, auth_store: AuthStore = Depends(get_auth_store)) -> JSONResponse:
    features = current_runtime_features()
    if not features.auth_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    if not features.allow_signup:
        raise HTTPException(status_code=403, detail="Sign-up is disabled in this deployment")
    user = auth_store.create_user(req.email, req.password)
    session_token = auth_store.create_session(user.user_id)
    resp = JSONResponse(content={"ok": True, "data": _user_to_dto(user, auth_store)})
    set_auth_cookie(resp, session_token)
    return resp


@router.post("/auth/login")
def login_auth_user(req: AuthCredentialsRequest, auth_store: AuthStore = Depends(get_auth_store)) -> JSONResponse:
    features = current_runtime_features()
    if not features.auth_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        user = auth_store.authenticate_user(req.email, req.password)
    except PreconditionFailure as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    session_token = auth_store.create_session(user.user_id)
    resp = JSONResponse(content={"ok": True, "data": _user_to_dto(user, auth_store)})
    set_auth_cookie(resp, session_token)
    return resp


@router.post("/auth/logout")
def logout_auth_user(request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> JSONResponse:
    features = current_runtime_features()
    if not features.auth_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    token = str(request.cookies.get(SESSION_COOKIE_NAME, "")).strip()
    if token:
        auth_store.delete_session(token)
    resp = JSONResponse(content={"ok": True, "data": None})
    clear_auth_cookie(resp)
    return resp


@router.get("/auth/me")
def get_current_auth_user(request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    features = current_runtime_features()
    if not features.auth_enabled:
        return {"ok": True, "data": None}
    user = resolve_session_user(request, auth_store)
    return {"ok": True, "data": None if user is None else _user_to_dto(user, auth_store)}
