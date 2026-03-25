from __future__ import annotations

import os
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response

from backend.models.errors import NotFound
from backend.system.auth_store import AuthStore, AuthUser

SESSION_COOKIE_NAME = "plm_session"


def _session_ttl_seconds() -> int:
    raw = (os.getenv("PLM_SESSION_TTL_DAYS") or "30").strip()
    try:
        days = int(raw)
    except Exception:
        days = 30
    return max(1, days) * 24 * 60 * 60


def _secure_cookies_enabled() -> bool:
    return (os.getenv("PLM_SECURE_COOKIES") or "").strip().lower() in {"1", "true", "yes", "on"}


def auth_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {"ok": False, "error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    headers = {"X-Request-ID": request_id} if request_id else None
    return JSONResponse(status_code=status_code, content=payload, headers=headers)


def get_request_auth_user(request: Request) -> AuthUser | None:
    user = getattr(request.state, "auth_user", None)
    return user if isinstance(user, AuthUser) else None


def require_request_auth_user(request: Request) -> AuthUser:
    user = get_request_auth_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def request_user_has_global_role(request: Request, auth_store: AuthStore, roles: tuple[str, ...] | list[str]) -> bool:
    user = require_request_auth_user(request)
    return auth_store.user_has_global_role(user.user_id, roles)


def require_admin_user(request: Request, auth_store: AuthStore) -> AuthUser:
    user = require_request_auth_user(request)
    if not auth_store.user_has_global_role(user.user_id, ("super_admin", "admin")):
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


def require_super_admin_user(request: Request, auth_store: AuthStore) -> AuthUser:
    user = require_request_auth_user(request)
    if not auth_store.user_has_global_role(user.user_id, ("super_admin",)):
        raise HTTPException(status_code=403, detail="Super administrator access required")
    return user


def resolve_session_user(request: Request, auth_store: AuthStore) -> AuthUser | None:
    token = str(request.cookies.get(SESSION_COOKIE_NAME, "")).strip()
    if not token:
        return None
    try:
        return auth_store.get_user_by_session(token)
    except NotFound:
        return None


def set_auth_cookie(response: Response, session_token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=str(session_token),
        max_age=_session_ttl_seconds(),
        httponly=True,
        samesite="lax",
        secure=_secure_cookies_enabled(),
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=_secure_cookies_enabled(),
        path="/",
    )
