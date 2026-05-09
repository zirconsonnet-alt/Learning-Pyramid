import mimetypes
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Callable
from urllib.parse import quote, urlencode, urljoin, urlparse

import requests

from backend.models.enums import MaterialSourceKind, SessionMode
from backend.models.errors import NotFound, PreconditionFailure
from backend.models.instance import Instance
from backend.models.instance_media_binding import InstanceMediaBinding
from backend.models.project_material_source_binding import ProjectMaterialSourceBinding
from backend.system.auth_store import AuthStore, CloudAccountBinding, decrypt_secret_value, encrypt_secret_value
from backend.system.baidu_netdisk_client import (
    BAIDU_NETDISK_PROVIDER,
    BaiduNetdiskApiError,
    BaiduNetdiskClient,
    BaiduNetdiskFileItem,
)
from backend.system.inmemory_system import InMemorySystem
from backend.system.material_paths import resolve_material_file_path
from backend.system.persistence_store import SqlStore
from backend.system.subtitle_files import SUPPORTED_SUBTITLE_EXTENSIONS, find_sibling_subtitle_file, parse_subtitle_file, parse_subtitle_text


@dataclass(frozen=True, slots=True)
class PlaybackDescriptor:
    instance_id: str
    source_kind: str
    playback_kind: str
    url: str
    mime_type: str
    duration_ms: int | None
    supports_frame_grab: bool
    supports_server_asr: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "instanceId": self.instance_id,
            "sourceKind": self.source_kind,
            "playbackKind": self.playback_kind,
            "url": self.url,
            "mimeType": self.mime_type,
            "durationMs": self.duration_ms,
            "supportsFrameGrab": self.supports_frame_grab,
            "supportsServerAsr": self.supports_server_asr,
        }


class InstanceMediaService:
    def __init__(
        self,
        *,
        sys: InMemorySystem,
        sql_store: SqlStore | None,
        baidu_client: BaiduNetdiskClient,
    ) -> None:
        self.sys = sys
        self.sql_store = sql_store
        self.baidu_client = baidu_client

    def get_instance_media_binding(self, project_id: str, instance_id: str) -> InstanceMediaBinding | None:
        if self.sql_store is not None:
            return self.sql_store.get_instance_media_binding(str(project_id), str(instance_id))
        session = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.instance_media_binding_repo.maybe_get(session, instance_id)  # type: ignore[arg-type]
        finally:
            self.sys.rollback(session)

    def get_project_binding(self, project_id: str) -> ProjectMaterialSourceBinding:
        session = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.project_material_source_binding_repo.get(session)
        finally:
            self.sys.rollback(session)

    def get_instance(self, project_id: str, instance_id: str) -> Instance:
        if self.sql_store is not None:
            item = self.sql_store.get_instance(str(project_id), str(instance_id))
            if item is not None:
                return item
            raise NotFound(instance_id)
        session = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.instance_repo.get(session, instance_id)  # type: ignore[arg-type]
        finally:
            self.sys.rollback(session)

    def get_effective_source_kind(self, project_id: str, instance_id: str) -> MaterialSourceKind:
        binding = self.get_instance_media_binding(project_id, instance_id)
        if binding is not None:
            return binding.source_kind
        return self.get_project_binding(project_id).source_kind

    def build_playback_descriptor(self, project_id: str, instance_id: str) -> PlaybackDescriptor:
        instance = self.get_instance(project_id, instance_id)
        binding = self.get_instance_media_binding(project_id, instance_id)
        source_kind = binding.source_kind if binding is not None else self.get_project_binding(project_id).source_kind
        if source_kind == MaterialSourceKind.BAIDU_NETDISK:
            return PlaybackDescriptor(
                instance_id=str(instance.instance_id),
                source_kind=source_kind.value,
                playback_kind="HLS",
                url=f"/api/projects/{project_id}/media/instances/{instance_id}/hls.m3u8",
                mime_type="application/vnd.apple.mpegurl",
                duration_ms=None if binding is None else binding.duration_ms,
                supports_frame_grab=False,
                supports_server_asr=False,
            )
        mime_type, _ = mimetypes.guess_type(instance.material_id.as_posix())
        return PlaybackDescriptor(
            instance_id=str(instance.instance_id),
            source_kind=source_kind.value,
            playback_kind="FILE",
            url=f"/api/projects/{project_id}/media/instances/{instance_id}",
            mime_type=mime_type or "application/octet-stream",
            duration_ms=None if binding is None else binding.duration_ms,
            supports_frame_grab=True,
            supports_server_asr=True,
        )

    def resolve_local_material_path(self, project_id: str, instance_id: str):
        instance = self.get_instance(project_id, instance_id)
        session = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            storage_cfg = self.sys.project_storage_config_repo.get(session)
        finally:
            self.sys.rollback(session)
        source_kind = self.get_effective_source_kind(project_id, instance_id)
        return resolve_material_file_path(storage_cfg, instance.material_id, source_kind=source_kind)

    def get_instance_subtitle_file(
        self,
        project_id: str,
        instance_id: str,
        *,
        auth_store: AuthStore | None = None,
    ) -> dict[str, object]:
        source_kind = self.get_effective_source_kind(project_id, instance_id)
        instance = self.get_instance(project_id, instance_id)
        if source_kind == MaterialSourceKind.BAIDU_NETDISK:
            if auth_store is None:
                raise PreconditionFailure("auth store is required for Baidu Netdisk subtitles")
            binding = self.get_instance_media_binding(project_id, instance_id)
            if binding is None or not binding.account_id or not binding.remote_path:
                raise PreconditionFailure("百度网盘媒体绑定不完整")
            subtitle = self._run_with_cloud_account(
                auth_store,
                binding.account_id,
                lambda account, access_token: self._load_baidu_subtitle_document(
                    access_token=access_token,
                    remote_path=binding.remote_path or instance.material_id.as_posix(),
                ),
            )
            if subtitle is None:
                return {"found": False, "instanceId": str(instance_id)}
            return {
                "found": True,
                "instanceId": str(instance_id),
                "fileName": subtitle["fileName"],
                "format": subtitle["format"],
                "segments": subtitle["segments"],
            }

        material_path = self.resolve_local_material_path(project_id, instance_id)
        if not material_path.exists():
            raise PreconditionFailure(f"material file not found: {material_path}")
        if not material_path.is_file():
            raise PreconditionFailure(f"material is not a file: {material_path}")
        subtitle_path = find_sibling_subtitle_file(material_path)
        if subtitle_path is None:
            return {"found": False, "instanceId": str(instance_id)}
        try:
            document = parse_subtitle_file(subtitle_path)
        except Exception as exc:
            raise PreconditionFailure(f"failed to parse subtitle file: {subtitle_path.name}") from exc
        return {
            "found": True,
            "instanceId": str(instance_id),
            "fileName": subtitle_path.name,
            "format": document.format,
            "segments": [
                {"startMs": int(segment.start_ms), "endMs": int(segment.end_ms), "text": segment.text}
                for segment in document.segments
            ],
        }

    def list_baidu_files(
        self,
        *,
        auth_store: AuthStore,
        account_id: str,
        dir_path: str = "/",
        page: int = 1,
        limit: int = 200,
    ) -> tuple[tuple[BaiduNetdiskFileItem, ...], bool]:
        return self._run_with_cloud_account(
            auth_store,
            account_id,
            lambda _account, access_token: self.baidu_client.list_files(
                access_token,
                dir_path=dir_path,
                page=page,
                limit=limit,
            ),
        )

    def resolve_baidu_download_link(
        self,
        *,
        auth_store: AuthStore,
        account_id: str,
        file_id: str,
        remote_path: str | None,
    ):
        return self._run_with_cloud_account(
            auth_store,
            account_id,
            lambda _account, access_token: self.baidu_client.get_download_link(
                access_token,
                file_id=file_id,
                remote_path=remote_path,
            ),
        )

    def build_baidu_hls_playlist(
        self,
        project_id: str,
        instance_id: str,
        *,
        auth_store: AuthStore,
    ) -> str:
        binding = self.get_instance_media_binding(project_id, instance_id)
        if binding is None or binding.source_kind != MaterialSourceKind.BAIDU_NETDISK:
            raise PreconditionFailure("当前实例不是百度网盘视频")
        if not binding.account_id or not binding.remote_path:
            raise PreconditionFailure("百度网盘媒体绑定缺少 account_id 或 remote_path")
        playlist = self._run_with_cloud_account(
            auth_store,
            binding.account_id,
            lambda _account, access_token: self.baidu_client.fetch_hls_playlist(
                access_token,
                remote_path=binding.remote_path,
            ),
        )
        return self._rewrite_hls_playlist(
            project_id=project_id,
            instance_id=instance_id,
            upstream_url=playlist.upstream_url,
            text=playlist.text,
        )

    def stream_baidu_segment(
        self,
        project_id: str,
        instance_id: str,
        *,
        auth_store: AuthStore,
        upstream_url: str,
    ) -> requests.Response:
        binding = self.get_instance_media_binding(project_id, instance_id)
        if binding is None or binding.source_kind != MaterialSourceKind.BAIDU_NETDISK:
            raise PreconditionFailure("当前实例不是百度网盘视频")
        if not binding.account_id:
            raise PreconditionFailure("百度网盘媒体绑定缺少 account_id")
        return self._run_with_cloud_account(
            auth_store,
            binding.account_id,
            lambda _account, access_token: self.baidu_client.stream_url(access_token, upstream_url),
        )

    def _rewrite_hls_playlist(self, *, project_id: str, instance_id: str, upstream_url: str, text: str) -> str:
        lines = []
        for raw_line in str(text or "").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                lines.append(raw_line)
                continue
            target = urljoin(upstream_url, line)
            parsed = urlparse(target)
            segment_path = parsed.path.lstrip("/") or "segment"
            proxy_url = (
                f"/api/projects/{project_id}/media/instances/{instance_id}/segments/{quote(segment_path, safe='/')}"
                f"?{urlencode({'u': target})}"
            )
            lines.append(proxy_url)
        return "\n".join(lines) + ("\n" if text.endswith("\n") else "")

    def _run_with_cloud_account(
        self,
        auth_store: AuthStore,
        account_id: str,
        func: Callable[[CloudAccountBinding, str], Any],
    ) -> Any:
        account = auth_store.get_cloud_account_by_id(account_id)
        access_token = decrypt_secret_value(account.access_token_ciphertext)
        try:
            return func(account, access_token)
        except BaiduNetdiskApiError as exc:
            if exc.kind != "unauthorized":
                raise
        refresh_token = decrypt_secret_value(account.refresh_token_ciphertext)
        refreshed = self.baidu_client.refresh_access_token(refresh_token)
        updated = auth_store.upsert_user_cloud_account(
            user_id=account.user_id,
            provider=account.provider,
            provider_user_id=account.provider_user_id,
            display_name=account.display_name,
            avatar_url=account.avatar_url,
            access_token_ciphertext=encrypt_secret_value(refreshed.access_token),
            refresh_token_ciphertext=encrypt_secret_value(refreshed.refresh_token),
            expires_at=refreshed.expires_at,
            scope=refreshed.scope or account.scope,
            meta=account.meta,
        )
        return func(updated, refreshed.access_token)

    def _load_baidu_subtitle_document(self, *, access_token: str, remote_path: str) -> dict[str, Any] | None:
        media_path = PurePosixPath(str(remote_path))
        if not media_path.name:
            return None
        stem = media_path.stem.casefold()
        siblings, _ = self.baidu_client.list_files(access_token, dir_path=media_path.parent.as_posix() or "/")
        preferred_by_ext = {ext: index for index, ext in enumerate(SUPPORTED_SUBTITLE_EXTENSIONS)}
        best: tuple[int, BaiduNetdiskFileItem] | None = None
        for item in siblings:
            if item.is_dir:
                continue
            suffix = PurePosixPath(item.name).suffix.lower()
            preference = preferred_by_ext.get(suffix)
            if preference is None:
                continue
            if PurePosixPath(item.name).stem.casefold() != stem:
                continue
            if best is None or preference < best[0]:
                best = (preference, item)
        if best is None:
            return None
        subtitle_item = best[1]
        download_link = self.baidu_client.get_download_link(
            access_token,
            file_id=subtitle_item.file_id,
            remote_path=subtitle_item.path,
        )
        raw_text = self.baidu_client.download_text(access_token, download_link.url)
        document = parse_subtitle_text(raw_text, suffix=PurePosixPath(subtitle_item.name).suffix.lower())
        return {
            "fileName": subtitle_item.name,
            "format": document.format,
            "segments": [
                {"startMs": int(segment.start_ms), "endMs": int(segment.end_ms), "text": segment.text}
                for segment in document.segments
            ],
        }
