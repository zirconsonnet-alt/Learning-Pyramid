from dataclasses import dataclass

from backend.models.enums import AuditEventKind, AuditResultCode
from backend.models.errors import PreconditionFailure
from backend.models.types import ProjectId, Timestamp


@dataclass(frozen=True, slots=True)
class AuditLogEvent:
    """
    1.8 AuditLogEvent（运行日志/审计事件）
    """

    project_id: ProjectId
    event_id: str
    occurred_at: Timestamp
    kind: AuditEventKind
    api_name: str
    result: AuditResultCode
    payload: str

    def validate_write_time(self) -> None:
        if not str(self.project_id):
            raise PreconditionFailure("AuditLogEvent.project_id must be non-empty")
        if self.event_id is None or not str(self.event_id).strip():
            raise PreconditionFailure("AuditLogEvent.event_id must be non-empty")
        if self.occurred_at is None:
            raise PreconditionFailure("AuditLogEvent.occurred_at must be provided")
        if self.api_name is None or not str(self.api_name).strip():
            raise PreconditionFailure("AuditLogEvent.api_name must be non-empty")
        if self.result != AuditResultCode.OK:
            raise PreconditionFailure("AuditLogEvent.result must be OK (spec only records successful commits)")
        if self.payload is None:
            raise PreconditionFailure("AuditLogEvent.payload must be provided")

