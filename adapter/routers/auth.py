from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from adapter.auth import SESSION_COOKIE_NAME, clear_auth_cookie, require_request_auth_user, resolve_session_user, set_auth_cookie
from adapter.deps import get_api, get_auth_rate_limit_store, get_auth_store, get_membership_marketing_store
from adapter.schemas import AuthCredentialsRequest, RegisterAuthRequest
from backend.models.errors import NotFound, PreconditionFailure
from backend.system.auth_rate_limit_store import AuthRateLimitStore
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthStore, AuthUser
from backend.system.runtime_features import current_runtime_features


router = APIRouter()


def _client_ip_from_request(request: Request) -> str | None:
    if request.client is None:
        return None
    host = str(request.client.host or "").strip()
    return host or None


def _raise_rate_limit_error(message: str, *, retry_after_seconds: int) -> None:
    retry_after = max(1, int(retry_after_seconds))
    raise HTTPException(status_code=429, detail=message, headers={"Retry-After": str(retry_after)})


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
    inviter = None
    invite_code = str(req.inviteCode or "").strip()
    try:
        if invite_code:
            try:
                inviter = auth_store.get_user_by_public_uid(invite_code)
            except NotFound as exc:
                raise PreconditionFailure("invite code does not exist") from exc
        user = auth_store.create_user(req.email, req.password)
        if inviter is not None:
            membership_marketing_store = get_membership_marketing_store()
            membership_marketing_store.bind_invite_code(
                user.user_id,
                inviter_user_id=inviter.user_id,
                invite_code_snapshot=inviter.public_uid,
            )
        session_token = auth_store.create_session(user.user_id)
        resp = JSONResponse(content={"ok": True, "data": _user_to_dto(user, auth_store)})
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
                "type": "plm:baidu-netdisk-connect",
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
                "type": "plm:baidu-netdisk-connect",
                "ok": False,
                "message": message,
            },
            status_code=400,
        )
