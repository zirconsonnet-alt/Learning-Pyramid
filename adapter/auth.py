from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response

from backend.models.errors import NotFound
from backend.system.auth_store import AuthStore, AuthUser

SESSION_COOKIE_NAME = "plm_session"
PENDING_EMAIL_VERIFICATION_COOKIE_NAME = "plm_pending_email_verification"


def _session_ttl_seconds() -> int:
    raw = (os.getenv("PLM_SESSION_TTL_DAYS") or "30").strip()
    try:
        days = int(raw)
    except Exception:
        days = 30
    return max(1, days) * 24 * 60 * 60


def _pending_email_verification_ttl_seconds() -> int:
    raw = (os.getenv("PLM_PENDING_EMAIL_VERIFICATION_TTL_SECONDS") or "3600").strip()
    try:
        seconds = int(raw)
    except Exception:
        seconds = 3600
    return max(300, seconds)


def _pending_email_verification_secret() -> str:
    return (
        os.getenv("PLM_PENDING_EMAIL_VERIFICATION_SECRET")
        or os.getenv("PLM_MEDIA_ACCESS_TOKEN_SECRET")
        or os.getenv("PLM_ALTCHA_HMAC_SECRET")
        or "learningpyramid-local-pending-email-verification"
    )


def _secure_cookies_enabled() -> bool:
    return (os.getenv("PLM_SECURE_COOKIES") or "").strip().lower() in {"1", "true", "yes", "on"}


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def issue_pending_email_verification_token(*, user_id: str, email: str) -> str:
    expires_at = int(time.time()) + _pending_email_verification_ttl_seconds()
    payload = {
        "sub": str(user_id).strip(),
        "email": str(email).strip().lower(),
        "exp": expires_at,
        "nonce": secrets.token_urlsafe(16),
    }
    payload_text = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload_part = _base64url_encode(payload_text)
    signature = hmac.new(
        _pending_email_verification_secret().encode("utf-8"),
        payload_part.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{payload_part}.{_base64url_encode(signature)}"


def resolve_pending_email_verification_token(token: str) -> dict[str, str] | None:
    raw = str(token or "").strip()
    if not raw or "." not in raw:
        return None
    payload_part, signature_part = raw.split(".", 1)
    expected_signature = hmac.new(
        _pending_email_verification_secret().encode("utf-8"),
        payload_part.encode("ascii"),
        hashlib.sha256,
    ).digest()
    try:
        actual_signature = _base64url_decode(signature_part)
    except Exception:
        return None
    if not hmac.compare_digest(expected_signature, actual_signature):
        return None
    try:
        payload = json.loads(_base64url_decode(payload_part).decode("utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    try:
        expires_at = int(payload.get("exp", 0))
    except Exception:
        return None
    if expires_at < int(time.time()):
        return None
    user_id = str(payload.get("sub") or "").strip()
    email = str(payload.get("email") or "").strip().lower()
    if not user_id or not email:
        return None
    return {"user_id": user_id, "email": email}


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


def set_pending_email_verification_cookie(response: Response, wait_token: str) -> None:
    response.set_cookie(
        key=PENDING_EMAIL_VERIFICATION_COOKIE_NAME,
        value=str(wait_token),
        max_age=_pending_email_verification_ttl_seconds(),
        httponly=True,
        samesite="lax",
        secure=_secure_cookies_enabled(),
        path="/",
    )


def clear_pending_email_verification_cookie(response: Response) -> None:
    response.delete_cookie(
        key=PENDING_EMAIL_VERIFICATION_COOKIE_NAME,
        httponly=True,
        samesite="lax",
        secure=_secure_cookies_enabled(),
        path="/",
    )
