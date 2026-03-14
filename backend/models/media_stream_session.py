from dataclasses import dataclass

from backend.models.errors import PreconditionFailure


MEDIA_STREAM_MODES = frozenset({"relay_progressive", "relay_hls"})
MEDIA_STREAM_SESSION_STATUSES = frozenset({"OPENING", "STREAMING", "COMPLETED", "FAILED", "CANCELLED"})


@dataclass(frozen=True, slots=True)
class MediaStreamSession:
    stream_id: str
    project_id: str
    instance_id: str
    agent_id: str
    user_id: str
    mode: str
    status: str
    range_start: int | None
    range_end: int | None
    bytes_from_agent: int
    bytes_to_viewer: int
    created_at: str
    updated_at: str
    expires_at: str
    finished_at: str | None = None
    failure_reason: str | None = None

    def validate_write_time(self) -> None:
        if not str(self.stream_id).strip():
            raise PreconditionFailure("MediaStreamSession.stream_id must be non-empty")
        if not str(self.project_id).strip():
            raise PreconditionFailure("MediaStreamSession.project_id must be non-empty")
        if not str(self.instance_id).strip():
            raise PreconditionFailure("MediaStreamSession.instance_id must be non-empty")
        if not str(self.agent_id).strip():
            raise PreconditionFailure("MediaStreamSession.agent_id must be non-empty")
        if not str(self.user_id).strip():
            raise PreconditionFailure("MediaStreamSession.user_id must be non-empty")
        if str(self.mode) not in MEDIA_STREAM_MODES:
            raise PreconditionFailure("MediaStreamSession.mode must be a supported relay mode")
        if str(self.status) not in MEDIA_STREAM_SESSION_STATUSES:
            raise PreconditionFailure("MediaStreamSession.status must be a supported stream status")
        if self.range_start is not None and int(self.range_start) < 0:
            raise PreconditionFailure("MediaStreamSession.range_start must be >= 0 when provided")
        if self.range_end is not None and int(self.range_end) < 0:
            raise PreconditionFailure("MediaStreamSession.range_end must be >= 0 when provided")
        if self.range_start is not None and self.range_end is not None and int(self.range_end) < int(self.range_start):
            raise PreconditionFailure("MediaStreamSession.range_end must be >= range_start")
        if int(self.bytes_from_agent) < 0:
            raise PreconditionFailure("MediaStreamSession.bytes_from_agent must be >= 0")
        if int(self.bytes_to_viewer) < 0:
            raise PreconditionFailure("MediaStreamSession.bytes_to_viewer must be >= 0")
        if not str(self.created_at).strip():
            raise PreconditionFailure("MediaStreamSession.created_at must be non-empty")
        if not str(self.updated_at).strip():
            raise PreconditionFailure("MediaStreamSession.updated_at must be non-empty")
        if not str(self.expires_at).strip():
            raise PreconditionFailure("MediaStreamSession.expires_at must be non-empty")
        if self.status in {"COMPLETED", "FAILED", "CANCELLED"} and not str(self.finished_at or "").strip():
            raise PreconditionFailure("MediaStreamSession.finished_at must be provided for terminal status")
