from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.models.enums import MaterialSourceKind
from backend.models.errors import PreconditionFailure
from backend.models.types import InstanceId, ProjectId, Timestamp, now_utc_ms


VALID_PLAYBACK_KINDS = frozenset({"FILE", "HLS"})


@dataclass(frozen=True, slots=True)
class InstanceMediaBinding:
    project_id: ProjectId
    instance_id: InstanceId
    source_kind: MaterialSourceKind
    playback_kind: str
    account_id: str | None
    remote_file_id: str | None
    remote_path: str | None
    mime_type: str | None
    size_bytes: int | None
    duration_ms: int | None
    source_payload: dict[str, Any]
    updated_at: Timestamp

    @staticmethod
    def create(
        project_id: ProjectId,
        instance_id: InstanceId,
        *,
        source_kind: MaterialSourceKind,
        playback_kind: str = "FILE",
        account_id: str | None = None,
        remote_file_id: str | None = None,
        remote_path: str | None = None,
        mime_type: str | None = None,
        size_bytes: int | None = None,
        duration_ms: int | None = None,
        source_payload: dict[str, Any] | None = None,
        updated_at: Timestamp | None = None,
    ) -> "InstanceMediaBinding":
        item = InstanceMediaBinding(
            project_id=project_id,
            instance_id=instance_id,
            source_kind=source_kind,
            playback_kind=str(playback_kind or "FILE").strip().upper(),
            account_id=None if account_id is None else str(account_id).strip() or None,
            remote_file_id=None if remote_file_id is None else str(remote_file_id).strip() or None,
            remote_path=None if remote_path is None else str(remote_path).strip() or None,
            mime_type=None if mime_type is None else str(mime_type).strip() or None,
            size_bytes=None if size_bytes is None else int(size_bytes),
            duration_ms=None if duration_ms is None else int(duration_ms),
            source_payload=dict(source_payload or {}),
            updated_at=updated_at or now_utc_ms(),
        )
        item.validate_write_time()
        return item

    def validate_write_time(self) -> None:
        if not str(self.project_id).strip():
            raise PreconditionFailure("InstanceMediaBinding.project_id must be non-empty")
        if not str(self.instance_id).strip():
            raise PreconditionFailure("InstanceMediaBinding.instance_id must be non-empty")
        if not isinstance(self.source_kind, MaterialSourceKind):
            raise PreconditionFailure("InstanceMediaBinding.source_kind must be MaterialSourceKind")
        if self.playback_kind not in VALID_PLAYBACK_KINDS:
            raise PreconditionFailure("InstanceMediaBinding.playback_kind must be FILE or HLS")
        if self.size_bytes is not None and self.size_bytes < 0:
            raise PreconditionFailure("InstanceMediaBinding.size_bytes must be non-negative when provided")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise PreconditionFailure("InstanceMediaBinding.duration_ms must be non-negative when provided")
        if not isinstance(self.source_payload, dict):
            raise PreconditionFailure("InstanceMediaBinding.source_payload must be a dict")
        if self.updated_at is None:
            raise PreconditionFailure("InstanceMediaBinding.updated_at must be provided")
