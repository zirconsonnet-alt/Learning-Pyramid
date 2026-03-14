from dataclasses import dataclass

from backend.models.errors import PreconditionFailure


DESKTOP_AGENT_DIAGNOSTIC_LEVELS = frozenset({"INFO", "WARNING", "ERROR"})


@dataclass(frozen=True, slots=True)
class DesktopAgentDiagnosticEvent:
    event_id: str
    agent_id: str
    user_id: str
    project_id: str | None
    instance_id: str | None
    relative_path: str | None
    level: str
    category: str
    event_type: str
    message: str
    details: str
    created_at: str

    def validate_write_time(self) -> None:
        if not str(self.event_id).strip():
            raise PreconditionFailure("DesktopAgentDiagnosticEvent.event_id must be non-empty")
        if not str(self.agent_id).strip():
            raise PreconditionFailure("DesktopAgentDiagnosticEvent.agent_id must be non-empty")
        if not str(self.user_id).strip():
            raise PreconditionFailure("DesktopAgentDiagnosticEvent.user_id must be non-empty")
        if str(self.level).strip().upper() not in DESKTOP_AGENT_DIAGNOSTIC_LEVELS:
            raise PreconditionFailure("DesktopAgentDiagnosticEvent.level must be supported")
        if not str(self.category).strip():
            raise PreconditionFailure("DesktopAgentDiagnosticEvent.category must be non-empty")
        if not str(self.event_type).strip():
            raise PreconditionFailure("DesktopAgentDiagnosticEvent.event_type must be non-empty")
        if not str(self.message).strip():
            raise PreconditionFailure("DesktopAgentDiagnosticEvent.message must be non-empty")
        if not str(self.details).strip():
            raise PreconditionFailure("DesktopAgentDiagnosticEvent.details must be non-empty")
        if not str(self.created_at).strip():
            raise PreconditionFailure("DesktopAgentDiagnosticEvent.created_at must be non-empty")
