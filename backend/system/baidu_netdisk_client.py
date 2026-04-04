from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

from backend.models.errors import ExternalServiceError, PreconditionFailure


BAIDU_NETDISK_PROVIDER = "baidu_netdisk"
DEFAULT_BAIDU_NETDISK_SCOPE = "basic,netdisk"
DEFAULT_PLAYBACK_PROFILE = "M3U8_AUTO_480"


class BaiduNetdiskApiError(ExternalServiceError):
    def __init__(
        self,
        message: str,
        *,
        kind: str = "upstream",
        status_code: int | None = None,
        errno: int | None = None,
        payload: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = str(kind)
        self.status_code = status_code
        self.errno = errno
        self.payload = payload


@dataclass(frozen=True, slots=True)
class BaiduNetdiskTokenBundle:
    access_token: str
    refresh_token: str
    expires_in: int | None
    scope: str

    @property
    def expires_at(self) -> str | None:
        if self.expires_in is None:
            return None
        import datetime as _dt

        return (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(seconds=max(0, int(self.expires_in)))).replace(
            microsecond=0
        ).isoformat()


@dataclass(frozen=True, slots=True)
class BaiduNetdiskAccountProfile:
    provider_user_id: str
    display_name: str
    avatar_url: str | None
    meta: dict[str, Any]


@dataclass(frozen=True, slots=True)
class BaiduNetdiskFileItem:
    file_id: str
    path: str
    name: str
    is_dir: bool
    size_bytes: int | None
    mime_type: str | None
    duration_ms: int | None
    category: int | None
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class BaiduNetdiskDownloadLink:
    url: str
    mime_type: str | None
    size_bytes: int | None
    duration_ms: int | None
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class BaiduNetdiskHlsPlaylist:
    text: str
    upstream_url: str


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _env_text(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _append_query(url: str, **params: Any) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in params.items():
        if value is None:
            continue
        query[str(key)] = str(value)
    return urlunparse(parsed._replace(query=urlencode(query)))


def _json_or_none(response: requests.Response) -> dict[str, Any] | None:
    try:
        payload = response.json()
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _looks_like_playlist(text: str) -> bool:
    return str(text or "").lstrip().startswith("#EXTM3U")


def _error_from_response(response: requests.Response, *, default_message: str) -> BaiduNetdiskApiError:
    payload = _json_or_none(response)
    errno = None if payload is None else payload.get("errno")
    try:
        errno = None if errno is None else int(errno)
    except Exception:
        errno = None
    message = default_message
    if payload is not None:
        message = str(payload.get("errmsg") or payload.get("error_description") or payload.get("error_msg") or default_message)
    lowered = message.lower()
    if response.status_code in {401, 403} or "invalid bduss" in lowered or "invalid access token" in lowered or "expired" in lowered:
        kind = "unauthorized"
    elif response.status_code == 404 or "not exist" in lowered or "not found" in lowered or "nofile" in lowered:
        kind = "not_found"
    elif "transcode" in lowered or "stream" in lowered or "m3u8" in lowered:
        kind = "transcode_failed"
    else:
        kind = "upstream"
    return BaiduNetdiskApiError(message, kind=kind, status_code=response.status_code, errno=errno, payload=payload)


class BaiduNetdiskClient:
    def __init__(self) -> None:
        self.enabled = _env_bool("PLM_ENABLE_BAIDU_NETDISK", False)
        self.client_id = _env_text("PLM_BAIDU_NETDISK_CLIENT_ID")
        self.client_secret = _env_text("PLM_BAIDU_NETDISK_CLIENT_SECRET")
        self.redirect_uri = _env_text("PLM_BAIDU_NETDISK_REDIRECT_URI")
        self.scope = _env_text("PLM_BAIDU_NETDISK_SCOPE") or DEFAULT_BAIDU_NETDISK_SCOPE
        self.timeout_sec = 30

    def require_enabled(self) -> None:
        if not self.enabled:
            raise PreconditionFailure("Baidu Netdisk integration is disabled in this deployment")
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise PreconditionFailure("Baidu Netdisk integration is not fully configured")

    def build_authorize_url(self, *, state: str) -> str:
        self.require_enabled()
        return _append_query(
            "https://openapi.baidu.com/oauth/2.0/authorize",
            response_type="code",
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scope=self.scope,
            state=state,
        )

    def exchange_code(self, code: str) -> BaiduNetdiskTokenBundle:
        self.require_enabled()
        response = requests.post(
            "https://openapi.baidu.com/oauth/2.0/token",
            data={
                "grant_type": "authorization_code",
                "code": str(code).strip(),
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
            },
            timeout=self.timeout_sec,
        )
        payload = _json_or_none(response)
        if response.status_code >= 400 or payload is None or payload.get("error"):
            raise _error_from_response(response, default_message="百度网盘授权换取令牌失败")
        return self._parse_token_bundle(payload)

    def refresh_access_token(self, refresh_token: str) -> BaiduNetdiskTokenBundle:
        self.require_enabled()
        response = requests.post(
            "https://openapi.baidu.com/oauth/2.0/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": str(refresh_token).strip(),
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=self.timeout_sec,
        )
        payload = _json_or_none(response)
        if response.status_code >= 400 or payload is None or payload.get("error"):
            raise _error_from_response(response, default_message="百度网盘刷新令牌失败")
        return self._parse_token_bundle(payload)

    @staticmethod
    def _parse_token_bundle(payload: dict[str, Any]) -> BaiduNetdiskTokenBundle:
        access_token = str(payload.get("access_token") or "").strip()
        refresh_token = str(payload.get("refresh_token") or "").strip()
        if not access_token or not refresh_token:
            raise BaiduNetdiskApiError("百度网盘令牌响应缺少 access_token 或 refresh_token")
        expires_in_raw = payload.get("expires_in")
        expires_in = None
        try:
            expires_in = None if expires_in_raw is None else int(expires_in_raw)
        except Exception:
            expires_in = None
        return BaiduNetdiskTokenBundle(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            scope=str(payload.get("scope") or ""),
        )

    def get_account_profile(self, access_token: str) -> BaiduNetdiskAccountProfile:
        self.require_enabled()
        payload = self._request_json(
            "GET",
            "https://pan.baidu.com/rest/2.0/xpan/nas",
            params={"method": "uinfo"},
            access_token=access_token,
            error_message="读取百度网盘账号信息失败",
        )
        provider_user_id = str(
            payload.get("uk")
            or payload.get("userid")
            or payload.get("user_id")
            or payload.get("baidu_name")
            or payload.get("netdisk_name")
            or ""
        ).strip()
        display_name = str(payload.get("netdisk_name") or payload.get("baidu_name") or provider_user_id or "百度网盘用户").strip()
        if not provider_user_id:
            raise BaiduNetdiskApiError("百度网盘账号信息缺少用户标识", payload=payload)
        avatar_url = (
            str(payload.get("avatar_url") or payload.get("avatar") or "").strip() or None
        )
        return BaiduNetdiskAccountProfile(
            provider_user_id=provider_user_id,
            display_name=display_name,
            avatar_url=avatar_url,
            meta=payload,
        )

    def list_files(self, access_token: str, *, dir_path: str = "/", page: int = 1, limit: int = 200) -> tuple[tuple[BaiduNetdiskFileItem, ...], bool]:
        payload = self._request_json(
            "GET",
            "https://pan.baidu.com/rest/2.0/xpan/file",
            params={
                "method": "list",
                "dir": str(dir_path or "/").strip() or "/",
                "start": max(0, (int(page) - 1) * int(limit)),
                "limit": max(1, min(int(limit), 200)),
                "folder": 1,
                "web": 1,
                "showempty": 0,
            },
            access_token=access_token,
            error_message="读取百度网盘目录失败",
        )
        items = payload.get("list")
        rows = list(items) if isinstance(items, list) else []
        parsed = tuple(self._parse_file_item(row) for row in rows if isinstance(row, dict))
        has_more_raw = payload.get("has_more", False)
        has_more = bool(has_more_raw) if isinstance(has_more_raw, bool) else str(has_more_raw).strip() not in {"", "0", "false", "False"}
        return parsed, has_more

    def get_download_link(self, access_token: str, *, file_id: str, remote_path: str | None = None) -> BaiduNetdiskDownloadLink:
        payload = self._request_json(
            "GET",
            "https://pan.baidu.com/rest/2.0/xpan/multimedia",
            params={
                "method": "filemetas",
                "fsids": json.dumps([int(str(file_id)) if str(file_id).isdigit() else str(file_id)], ensure_ascii=False),
                "dlink": 1,
                "thumb": 0,
                "extra": 1,
            },
            access_token=access_token,
            error_message="读取百度网盘文件信息失败",
        )
        rows = list(payload.get("list") or [])
        if not rows:
            raise BaiduNetdiskApiError("百度网盘文件不存在或已无权限访问", kind="not_found", payload=payload)
        row = dict(rows[0])
        dlink = str(row.get("dlink") or "").strip()
        if not dlink and remote_path:
            dlink = _append_query(
                "https://pan.baidu.com/rest/2.0/xpan/file",
                method="download",
                path=remote_path,
                access_token=access_token,
            )
        if not dlink:
            raise BaiduNetdiskApiError("百度网盘文件下载地址缺失", payload=row)
        return BaiduNetdiskDownloadLink(
            url=self._attach_access_token_if_needed(dlink, access_token),
            mime_type=self._mime_type_from_row(row),
            size_bytes=self._optional_int(row.get("size")),
            duration_ms=self._duration_ms_from_row(row),
            raw=row,
        )

    def fetch_hls_playlist(
        self,
        access_token: str,
        *,
        remote_path: str,
        profile: str = DEFAULT_PLAYBACK_PROFILE,
    ) -> BaiduNetdiskHlsPlaylist:
        candidates = (
            ("https://pan.baidu.com/rest/2.0/xpan/file", {"method": "streaming", "path": remote_path, "type": profile}),
            ("https://pan.baidu.com/rest/2.0/xpan/multimedia", {"method": "streaming", "path": remote_path, "type": profile}),
        )
        last_error: BaiduNetdiskApiError | None = None
        for url, params in candidates:
            try:
                response = self._request(
                    "GET",
                    url,
                    params=params,
                    access_token=access_token,
                    allow_redirects=False,
                )
                if response.is_redirect or response.is_permanent_redirect:
                    location = str(response.headers.get("Location") or "").strip()
                    if not location:
                        raise BaiduNetdiskApiError("百度网盘播放地址重定向缺少 Location 头", kind="transcode_failed")
                    return self._fetch_playlist_from_url(access_token, location)
                if response.status_code >= 400:
                    raise _error_from_response(response, default_message="百度网盘转码播放失败")
                if _looks_like_playlist(response.text):
                    return BaiduNetdiskHlsPlaylist(text=response.text, upstream_url=response.url)
                payload = _json_or_none(response)
                if payload is not None:
                    raise _error_from_response(response, default_message="百度网盘转码播放失败")
                raise BaiduNetdiskApiError("百度网盘播放响应不是可识别的 HLS 播放列表", kind="transcode_failed")
            except BaiduNetdiskApiError as exc:
                last_error = exc
                continue
        if last_error is not None:
            raise last_error
        raise BaiduNetdiskApiError("百度网盘转码播放失败", kind="transcode_failed")

    def _fetch_playlist_from_url(self, access_token: str, playlist_url: str) -> BaiduNetdiskHlsPlaylist:
        response = requests.get(self._attach_access_token_if_needed(playlist_url, access_token), timeout=self.timeout_sec)
        if response.status_code >= 400:
            raise _error_from_response(response, default_message="读取百度网盘播放列表失败")
        if not _looks_like_playlist(response.text):
            raise BaiduNetdiskApiError("百度网盘播放列表内容无效", kind="transcode_failed")
        return BaiduNetdiskHlsPlaylist(text=response.text, upstream_url=response.url)

    def download_text(self, access_token: str, download_url: str) -> str:
        response = requests.get(self._attach_access_token_if_needed(download_url, access_token), timeout=self.timeout_sec)
        if response.status_code >= 400:
            raise _error_from_response(response, default_message="读取百度网盘文件内容失败")
        response.encoding = response.encoding or "utf-8"
        return response.text

    def stream_url(self, access_token: str, url: str, *, allow_redirects: bool = True) -> requests.Response:
        response = requests.get(
            self._attach_access_token_if_needed(url, access_token),
            timeout=self.timeout_sec,
            stream=True,
            allow_redirects=allow_redirects,
        )
        if response.status_code >= 400:
            raise _error_from_response(response, default_message="读取百度网盘媒体片段失败")
        return response

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        access_token: str | None = None,
        error_message: str,
    ) -> dict[str, Any]:
        response = self._request(method, url, params=params, access_token=access_token, allow_redirects=True)
        payload = _json_or_none(response)
        if response.status_code >= 400 or payload is None:
            raise _error_from_response(response, default_message=error_message)
        if payload.get("error") or payload.get("errno") not in (None, 0):
            raise _error_from_response(response, default_message=error_message)
        return payload

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        access_token: str | None = None,
        allow_redirects: bool,
    ) -> requests.Response:
        req_params = dict(params or {})
        if access_token:
            req_params.setdefault("access_token", access_token)
        response = requests.request(
            method.upper(),
            url,
            params=req_params,
            timeout=self.timeout_sec,
            allow_redirects=allow_redirects,
        )
        return response

    @staticmethod
    def _attach_access_token_if_needed(url: str, access_token: str) -> str:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return url
        if not parsed.netloc.endswith("baidu.com"):
            return url
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        if "access_token" in query or not access_token:
            return url
        query["access_token"] = access_token
        return urlunparse(parsed._replace(query=urlencode(query)))

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        try:
            if value is None or value == "":
                return None
            return int(value)
        except Exception:
            return None

    def _duration_ms_from_row(self, row: dict[str, Any]) -> int | None:
        candidates = (
            row.get("duration"),
            row.get("duration_ms"),
            row.get("durationMs"),
            row.get("video_duration"),
        )
        for value in candidates:
            if value in (None, ""):
                continue
            try:
                numeric = float(value)
            except Exception:
                continue
            if numeric < 0:
                continue
            if numeric > 10_000:
                return int(numeric)
            return int(numeric * 1000)
        return None

    @staticmethod
    def _mime_type_from_row(row: dict[str, Any]) -> str | None:
        mime = str(row.get("mime_type") or row.get("mimeType") or "").strip()
        if mime:
            return mime
        name = str(row.get("server_filename") or row.get("filename") or row.get("path") or "").lower()
        if name.endswith(".mp4"):
            return "video/mp4"
        if name.endswith(".mkv"):
            return "video/x-matroska"
        if name.endswith(".mov"):
            return "video/quicktime"
        if name.endswith(".webm"):
            return "video/webm"
        if name.endswith(".srt"):
            return "application/x-subrip"
        if name.endswith(".vtt"):
            return "text/vtt"
        return None

    def _parse_file_item(self, row: dict[str, Any]) -> BaiduNetdiskFileItem:
        path = str(row.get("path") or "").strip()
        name = str(row.get("server_filename") or row.get("filename") or path.rsplit("/", 1)[-1] or "").strip()
        file_id = str(row.get("fs_id") or row.get("fsid") or row.get("file_id") or path).strip()
        is_dir = bool(int(row.get("isdir", 0))) if str(row.get("isdir", "")).strip() else bool(row.get("isdir"))
        return BaiduNetdiskFileItem(
            file_id=file_id,
            path=path,
            name=name or file_id,
            is_dir=is_dir,
            size_bytes=self._optional_int(row.get("size")),
            mime_type=self._mime_type_from_row(row),
            duration_ms=self._duration_ms_from_row(row),
            category=self._optional_int(row.get("category")),
            raw=dict(row),
        )
