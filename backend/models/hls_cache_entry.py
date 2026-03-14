from dataclasses import dataclass

from backend.models.errors import PreconditionFailure


@dataclass(frozen=True, slots=True)
class HlsCacheEntry:
    cache_key: str
    project_id: str
    instance_id: str
    agent_id: str
    profile: str
    segment_name: str
    file_path: str
    size_bytes: int
    created_at: str
    last_accessed_at: str
    expires_at: str

    def validate_write_time(self) -> None:
        if not str(self.cache_key).strip():
            raise PreconditionFailure("HlsCacheEntry.cache_key must be non-empty")
        if not str(self.project_id).strip():
            raise PreconditionFailure("HlsCacheEntry.project_id must be non-empty")
        if not str(self.instance_id).strip():
            raise PreconditionFailure("HlsCacheEntry.instance_id must be non-empty")
        if not str(self.agent_id).strip():
            raise PreconditionFailure("HlsCacheEntry.agent_id must be non-empty")
        if not str(self.profile).strip():
            raise PreconditionFailure("HlsCacheEntry.profile must be non-empty")
        if not str(self.segment_name).strip():
            raise PreconditionFailure("HlsCacheEntry.segment_name must be non-empty")
        if not str(self.file_path).strip():
            raise PreconditionFailure("HlsCacheEntry.file_path must be non-empty")
        if int(self.size_bytes) < 0:
            raise PreconditionFailure("HlsCacheEntry.size_bytes must be >= 0")
        if not str(self.created_at).strip():
            raise PreconditionFailure("HlsCacheEntry.created_at must be non-empty")
        if not str(self.last_accessed_at).strip():
            raise PreconditionFailure("HlsCacheEntry.last_accessed_at must be non-empty")
        if not str(self.expires_at).strip():
            raise PreconditionFailure("HlsCacheEntry.expires_at must be non-empty")
