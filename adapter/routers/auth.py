import json
import logging
import hmac

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from adapter.auth import (
    PENDING_EMAIL_VERIFICATION_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    clear_auth_cookie,
    clear_pending_email_verification_cookie,
    issue_pending_email_verification_token,
    require_request_auth_user,
    resolve_pending_email_verification_token,
    resolve_session_user,
    set_auth_cookie,
    set_pending_email_verification_cookie,
)
from adapter.deps import get_api, get_auth_rate_limit_store, get_auth_store, get_membership_marketing_store
from adapter.schemas import (
    AuthCredentialsRequest,
    EmailVerificationConfirmRequest,
    EmailVerificationRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterAuthRequest,
)
from backend.models.errors import NotFound, PreconditionFailure
from backend.system.auth_rate_limit_store import AuthRateLimitStore
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthStore, AuthUser, email_is_bootstrap_super_admin
from backend.system.email_verification_delivery import (
    build_email_verification_url,
    current_email_verification_delivery_config,
    email_verification_enabled,
    send_email_verification_email,
)
from backend.system.password_reset_delivery import (
    build_password_reset_url,
    current_password_reset_delivery_config,
    password_reset_enabled,
    send_password_reset_email,
)
from backend.system.runtime_features import current_runtime_features
from backend.system.signup_human_check import build_signup_human_check_challenge, verify_signup_human_check


router = APIRouter()
logger = logging.getLogger(__name__)


def _client_ip_from_request(request: Request) -> str | None:
    if request.client is None:
        return None
    host = str(request.client.host or "").strip()
    return host or None


def _raise_rate_limit_error(message: str, *, retry_after_seconds: int) -> None:
    retry_after = max(1, int(retry_after_seconds))
    raise HTTPException(status_code=429, detail=message, headers={"Retry-After": str(retry_after)})


def _check_email_flow_allowed(
    *,
    scope_prefix: str,
    too_many_message: str,
    client_ip: str | None,
    email: str,
    auth_rate_limit_store: AuthRateLimitStore,
) -> None:
    cfg = auth_rate_limit_store.config
    ip_decision = auth_rate_limit_store.check_scope_allowed(
        scope=f"{scope_prefix}_ip",
        raw_key=client_ip,
        limit=cfg.signup_max_attempts_per_ip,
        window_seconds=cfg.signup_window_seconds,
    )
    email_decision = auth_rate_limit_store.check_scope_allowed(
        scope=f"{scope_prefix}_email",
        raw_key=email,
        limit=cfg.signup_max_attempts_per_email,
        window_seconds=cfg.signup_window_seconds,
    )
    if ip_decision.allowed and email_decision.allowed:
        return
    _raise_rate_limit_error(
        too_many_message,
        retry_after_seconds=max(ip_decision.retry_after_seconds, email_decision.retry_after_seconds),
    )


def _record_email_flow_attempt(
    *,
    scope_prefix: str,
    client_ip: str | None,
    email: str,
    auth_rate_limit_store: AuthRateLimitStore,
) -> None:
    cfg = auth_rate_limit_store.config
    auth_rate_limit_store.record_scope_action(
        scope=f"{scope_prefix}_ip",
        raw_key=client_ip,
        window_seconds=cfg.signup_window_seconds,
    )
    auth_rate_limit_store.record_scope_action(
        scope=f"{scope_prefix}_email",
        raw_key=email,
        window_seconds=cfg.signup_window_seconds,
    )


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


def _send_signup_verification_email(*, auth_store: AuthStore, email: str) -> bool:
    raw_token = auth_store.create_email_verification_token(email)
    if not raw_token:
        return False
    cfg = current_email_verification_delivery_config()
    send_email_verification_email(
        to_email=email,
        verification_url=build_email_verification_url(raw_token),
        expires_minutes=cfg.token_ttl_minutes,
    )
    return True


@router.get("/auth/human-check/challenge")
def get_signup_human_check_challenge() -> dict:
    return build_signup_human_check_challenge()


@router.post("/auth/register")
def register_auth_user(
    request: Request,
    req: RegisterAuthRequest,
    auth_store: AuthStore = Depends(get_auth_store),
    auth_rate_limit_store: AuthRateLimitStore = Depends(get_auth_rate_limit_store),
) -> JSONResponse:
    features = current_runtime_features()
    if not features.auth_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    if not features.allow_signup:
        raise HTTPException(status_code=403, detail="Sign-up is disabled in this deployment")
    client_ip = _client_ip_from_request(request)
    decision = auth_rate_limit_store.check_signup_allowed(client_ip=client_ip, email=req.email)
    if not decision.allowed:
        _raise_rate_limit_error("Too many sign-up attempts. Try again later.", retry_after_seconds=decision.retry_after_seconds)
    verify_signup_human_check(req.humanCheckToken, remote_ip=client_ip)
    inviter = None
    invite_code = str(req.inviteCode or "").strip()
    bootstrap_admin_signup = email_is_bootstrap_super_admin(req.email)
    invite_optional = bootstrap_admin_signup or not features.signup_invite_required
    verification_required = email_verification_enabled() and not bootstrap_admin_signup
    try:
        if invite_code:
            try:
                inviter = auth_store.get_user_by_public_uid(invite_code)
            except NotFound as exc:
                raise PreconditionFailure("invite code does not exist") from exc
        elif not invite_optional:
            raise PreconditionFailure("invite code is required for registration")
        user = auth_store.create_user(req.email, req.password, email_verified=not verification_required)
        if inviter is not None:
            membership_marketing_store = get_membership_marketing_store()
            membership_marketing_store.bind_invite_code(
                user.user_id,
                inviter_user_id=inviter.user_id,
                invite_code_snapshot=inviter.public_uid,
            )
            auth_store.create_friendship(user.user_id, inviter.user_id)
        verification_email_sent = False
        if verification_required:
            try:
                verification_email_sent = _send_signup_verification_email(auth_store=auth_store, email=user.email)
            except Exception:
                logger.exception("failed to deliver email verification message")
            verification_wait_token = issue_pending_email_verification_token(user_id=user.user_id, email=user.email)
            resp = JSONResponse(
                content={
                    "ok": True,
                    "data": {
                        **_user_to_dto(user, auth_store),
                        "emailVerificationRequired": True,
                        "verificationEmailSent": verification_email_sent,
                        "verificationWaitToken": verification_wait_token,
                    },
                }
            )
            set_pending_email_verification_cookie(resp, verification_wait_token)
            return resp
        session_token = auth_store.create_session(user.user_id)
        resp = JSONResponse(
            content={
                "ok": True,
                "data": {
                    **_user_to_dto(user, auth_store),
                    "emailVerificationRequired": False,
                    "verificationEmailSent": False,
                },
            }
        )
        set_auth_cookie(resp, session_token)
        return resp
    finally:
        auth_rate_limit_store.record_signup_attempt(client_ip=client_ip, email=req.email)


@router.post("/auth/login")
def login_auth_user(
    request: Request,
    req: AuthCredentialsRequest,
    auth_store: AuthStore = Depends(get_auth_store),
    auth_rate_limit_store: AuthRateLimitStore = Depends(get_auth_rate_limit_store),
) -> JSONResponse:
    features = current_runtime_features()
    if not features.auth_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    client_ip = _client_ip_from_request(request)
    decision = auth_rate_limit_store.check_login_allowed(client_ip=client_ip, email=req.email)
    if not decision.allowed:
        _raise_rate_limit_error("Too many login attempts. Try again later.", retry_after_seconds=decision.retry_after_seconds)
    try:
        user = auth_store.authenticate_user(req.email, req.password)
    except PreconditionFailure as exc:
        auth_rate_limit_store.record_login_failure(client_ip=client_ip, email=req.email)
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    auth_rate_limit_store.reset_login_failures(email=req.email)
    session_token = auth_store.create_session(user.user_id)
    resp = JSONResponse(content={"ok": True, "data": _user_to_dto(user, auth_store)})
    clear_pending_email_verification_cookie(resp)
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
    clear_pending_email_verification_cookie(resp)
    return resp


@router.get("/auth/me")
def get_current_auth_user(request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    features = current_runtime_features()
    if not features.auth_enabled:
        return {"ok": True, "data": None}
    user = resolve_session_user(request, auth_store)
    return {"ok": True, "data": None if user is None else _user_to_dto(user, auth_store)}


@router.post("/auth/password-reset/request")
def request_password_reset(
    request: Request,
    req: PasswordResetRequest,
    auth_store: AuthStore = Depends(get_auth_store),
    auth_rate_limit_store: AuthRateLimitStore = Depends(get_auth_rate_limit_store),
) -> dict:
    features = current_runtime_features()
    if not features.auth_enabled or not password_reset_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    client_ip = _client_ip_from_request(request)
    _check_email_flow_allowed(
        scope_prefix="password_reset",
        too_many_message="Too many password reset attempts. Try again later.",
        client_ip=client_ip,
        email=req.email,
        auth_rate_limit_store=auth_rate_limit_store,
    )
    try:
        raw_token = auth_store.create_password_reset_token(req.email)
        if raw_token:
            cfg = current_password_reset_delivery_config()
            try:
                send_password_reset_email(
                    to_email=req.email,
                    reset_url=build_password_reset_url(raw_token),
                    expires_minutes=cfg.token_ttl_minutes,
                )
            except Exception:
                logger.exception("failed to deliver password reset email")
        return {"ok": True, "data": None}
    finally:
        _record_email_flow_attempt(
            scope_prefix="password_reset",
            client_ip=client_ip,
            email=req.email,
            auth_rate_limit_store=auth_rate_limit_store,
        )


@router.post("/auth/password-reset/confirm")
def confirm_password_reset(
    req: PasswordResetConfirmRequest,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    features = current_runtime_features()
    if not features.auth_enabled or not password_reset_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    auth_store.reset_password_with_token(req.token, new_password=req.newPassword)
    return {"ok": True, "data": None}


@router.post("/auth/email-verification/request")
def request_email_verification(
    request: Request,
    req: EmailVerificationRequest,
    auth_store: AuthStore = Depends(get_auth_store),
    auth_rate_limit_store: AuthRateLimitStore = Depends(get_auth_rate_limit_store),
) -> dict:
    features = current_runtime_features()
    if not features.auth_enabled or not email_verification_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    client_ip = _client_ip_from_request(request)
    _check_email_flow_allowed(
        scope_prefix="email_verification",
        too_many_message="Too many verification email attempts. Try again later.",
        client_ip=client_ip,
        email=req.email,
        auth_rate_limit_store=auth_rate_limit_store,
    )
    try:
        try:
            _send_signup_verification_email(auth_store=auth_store, email=req.email)
        except Exception:
            logger.exception("failed to deliver email verification message")
        return {"ok": True, "data": None}
    finally:
        _record_email_flow_attempt(
            scope_prefix="email_verification",
            client_ip=client_ip,
            email=req.email,
            auth_rate_limit_store=auth_rate_limit_store,
        )


@router.post("/auth/email-verification/confirm")
def confirm_email_verification(
    req: EmailVerificationConfirmRequest,
    auth_store: AuthStore = Depends(get_auth_store),
) -> JSONResponse:
    features = current_runtime_features()
    if not features.auth_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    user = auth_store.verify_email_with_token(req.token)
    session_token = auth_store.create_session(user.user_id)
    resp = JSONResponse(content={"ok": True, "data": _user_to_dto(user, auth_store)})
    clear_pending_email_verification_cookie(resp)
    set_auth_cookie(resp, session_token)
    return resp


@router.get("/auth/email-verification/status")
def get_email_verification_status(
    request: Request,
    waitToken: str = Query(min_length=16, max_length=2048),
    auth_store: AuthStore = Depends(get_auth_store),
) -> JSONResponse:
    features = current_runtime_features()
    if not features.auth_enabled or not email_verification_enabled():
        raise HTTPException(status_code=404, detail="Not found")
    cookie_token = str(request.cookies.get(PENDING_EMAIL_VERIFICATION_COOKIE_NAME, "")).strip()
    if not cookie_token or not hmac.compare_digest(cookie_token, str(waitToken).strip()):
        return JSONResponse(content={"ok": True, "data": {"status": "pending"}})
    token_payload = resolve_pending_email_verification_token(cookie_token)
    if token_payload is None:
        resp = JSONResponse(content={"ok": True, "data": {"status": "expired"}})
        clear_pending_email_verification_cookie(resp)
        return resp
    try:
        user = auth_store.get_user_by_id(token_payload["user_id"])
    except NotFound:
        resp = JSONResponse(content={"ok": True, "data": {"status": "expired"}})
        clear_pending_email_verification_cookie(resp)
        return resp
    if user.email.strip().lower() != token_payload["email"].strip().lower() or not auth_store.user_email_verified(user.user_id):
        return JSONResponse(content={"ok": True, "data": {"status": "pending"}})
    session_token = auth_store.create_session(user.user_id)
    resp = JSONResponse(content={"ok": True, "data": {"status": "verified", "user": _user_to_dto(user, auth_store)}})
    clear_pending_email_verification_cookie(resp)
    set_auth_cookie(resp, session_token)
    return resp


def _cloud_callback_html(payload: dict[str, object], status_code: int = 200) -> HTMLResponse:
    payload_text = json.dumps(payload, ensure_ascii=False)
    html = f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <title>百度网盘授权</title>
    <style>
      body {{
        margin: 0;
        font-family: "Segoe UI", "PingFang SC", sans-serif;
        background: #f8fafc;
        color: #0f172a;
      }}
      .shell {{
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 24px;
      }}
      .card {{
        width: min(440px, 100%);
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 20px;
        box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
        padding: 28px;
      }}
      h1 {{
        margin: 0 0 12px;
        font-size: 22px;
      }}
      p {{
        margin: 0;
        line-height: 1.7;
        color: #475569;
      }}
      .muted {{
        margin-top: 10px;
        font-size: 13px;
        color: #64748b;
      }}
    </style>
  </head>
  <body>
    <div class="shell">
      <div class="card">
        <h1 id="title">正在完成百度网盘授权</h1>
        <p id="message">请稍等，这个窗口会在完成后自动关闭。</p>
        <p class="muted">如果窗口没有自动关闭，请返回主页面查看绑定结果。</p>
      </div>
    </div>
    <script>
      const payload = {payload_text};
      const titleEl = document.getElementById("title");
      const messageEl = document.getElementById("message");
      if (payload.ok) {{
        titleEl.textContent = "百度网盘已连接";
        messageEl.textContent = "账号绑定成功，这个窗口即将自动关闭。";
      }} else {{
        titleEl.textContent = "百度网盘授权失败";
        messageEl.textContent = String(payload.message || "授权没有完成，请返回主页面重试。");
      }}
      try {{
        if (window.opener && !window.opener.closed) {{
          window.opener.postMessage(payload, "*");
        }}
      }} catch (error) {{
      }}
      window.setTimeout(() => {{
        window.close();
      }}, payload.ok ? 700 : 1200);
    </script>
  </body>
</html>
"""
    return HTMLResponse(content=html, status_code=status_code)


@router.get("/auth/baidu-netdisk/callback")
def complete_baidu_netdisk_connect(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    auth_store: AuthStore = Depends(get_auth_store),
    api: SystemAPI = Depends(get_api),
) -> HTMLResponse:
    try:
        user = require_request_auth_user(request)
        if error:
            raise PreconditionFailure(str(error_description or error).strip() or "百度网盘授权失败")
        if not str(code or "").strip():
            raise PreconditionFailure("百度网盘授权回调缺少 code")
        if not str(state or "").strip():
            raise PreconditionFailure("百度网盘授权回调缺少 state")
        account = api.complete_baidu_netdisk_connect(
            auth_store=auth_store,
            user_id=user.user_id,
            code=str(code).strip(),
            state=str(state).strip(),
        )
        return _cloud_callback_html(
            {
                "type": "learningpyramid:baidu-netdisk-connect",
                "ok": True,
                "account": account,
            }
        )
    except Exception as exc:
        message = str(exc) or "百度网盘授权失败"
        if isinstance(exc, HTTPException):
            message = str(exc.detail) if exc.detail else message
        return _cloud_callback_html(
            {
                "type": "learningpyramid:baidu-netdisk-connect",
                "ok": False,
                "message": message,
            },
            status_code=400,
        )
