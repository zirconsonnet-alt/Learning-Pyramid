from dataclasses import dataclass

from backend.models.errors import PreconditionFailure


HLS_JOB_AUDIT_STATES = frozenset({"OPENING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"})


@dataclass(frozen=True, slots=True)
class DesktopAgentHlsJobAudit:
    job_id: str
    cache_key: str
    project_id: str
    instance_id: str
    agent_id: str
    relative_path: str
    profile: str
    state: str
    artifact_count: int
    artifact_bytes: int
    created_at: str
    updated_at: str
    expires_at: str
    started_at: str | None = None
    finished_at: str | None = None
    last_artifact_at: str | None = None
    message: str | None = None

    def validate_write_time(self) -> None:
        if not str(self.job_id).strip():
            raise PreconditionFailure("DesktopAgentHlsJobAudit.job_id must be non-empty")
        if not str(self.cache_key).strip():
            raise PreconditionFailure("DesktopAgentHlsJobAudit.cache_key must be non-empty")
        if not str(self.project_id).strip():
            raise PreconditionFailure("DesktopAgentHlsJobAudit.project_id must be non-empty")
        if not str(self.instance_id).strip():
            raise PreconditionFailure("DesktopAgentHlsJobAudit.instance_id must be non-empty")
        if not str(self.agent_id).strip():
            raise PreconditionFailure("DesktopAgentHlsJobAudit.agent_id must be non-empty")
        if not str(self.relative_path).strip():
            raise PreconditionFailure("DesktopAgentHlsJobAudit.relative_path must be non-empty")
        if not str(self.profile).strip():
            raise PreconditionFailure("DesktopAgentHlsJobAudit.profile must be non-empty")
        if str(self.state).strip().upper() not in HLS_JOB_AUDIT_STATES:
            raise PreconditionFailure("DesktopAgentHlsJobAudit.state must be a supported HLS job state")
        if int(self.artifact_count) < 0:
            raise PreconditionFailure("DesktopAgentHlsJobAudit.artifact_count must be >= 0")
        if int(self.artifact_bytes) < 0:
            raise PreconditionFailure("DesktopAgentHlsJobAudit.artifact_bytes must be >= 0")
        if not str(self.created_at).strip():
            raise PreconditionFailure("DesktopAgentHlsJobAudit.created_at must be non-empty")
        if not str(self.updated_at).strip():
            raise PreconditionFailure("DesktopAgentHlsJobAudit.updated_at must be non-empty")
        if not str(self.expires_at).strip():
            raise PreconditionFailure("DesktopAgentHlsJobAudit.expires_at must be non-empty")
        if str(self.state).strip().upper() in {"COMPLETED", "FAILED", "CANCELLED"} and not str(self.finished_at or "").strip():
            raise PreconditionFailure("DesktopAgentHlsJobAudit.finished_at must be provided for terminal state")
