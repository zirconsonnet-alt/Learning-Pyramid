from dataclasses import dataclass

from backend.models.enums import DesktopAgentStatus
from backend.models.errors import PreconditionFailure


@dataclass(frozen=True, slots=True)
class DesktopAgent:
    agent_id: str
    user_id: str
    device_name: str
    platform: str
    app_version: str
    status: DesktopAgentStatus
    last_seen_at: str
    paired_at: str

    def validate_write_time(self) -> None:
        if not str(self.agent_id).strip():
            raise PreconditionFailure("DesktopAgent.agent_id must be non-empty")
        if not str(self.user_id).strip():
            raise PreconditionFailure("DesktopAgent.user_id must be non-empty")
        if not str(self.device_name).strip():
            raise PreconditionFailure("DesktopAgent.device_name must be non-empty")
        if not str(self.platform).strip():
            raise PreconditionFailure("DesktopAgent.platform must be non-empty")
        if not str(self.app_version).strip():
            raise PreconditionFailure("DesktopAgent.app_version must be non-empty")
        if not isinstance(self.status, DesktopAgentStatus):
            raise PreconditionFailure("DesktopAgent.status must be DesktopAgentStatus")
        if not str(self.last_seen_at).strip():
            raise PreconditionFailure("DesktopAgent.last_seen_at must be non-empty")
        if not str(self.paired_at).strip():
            raise PreconditionFailure("DesktopAgent.paired_at must be non-empty")
