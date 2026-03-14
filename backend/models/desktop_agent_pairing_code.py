from dataclasses import dataclass

from backend.models.errors import PreconditionFailure


@dataclass(frozen=True, slots=True)
class DesktopAgentPairingCode:
    pairing_code: str
    user_id: str
    expires_at: str
    used_at: str | None
    created_at: str

    def validate_write_time(self) -> None:
        if not str(self.pairing_code).strip():
            raise PreconditionFailure("DesktopAgentPairingCode.pairing_code must be non-empty")
        if not str(self.user_id).strip():
            raise PreconditionFailure("DesktopAgentPairingCode.user_id must be non-empty")
        if not str(self.expires_at).strip():
            raise PreconditionFailure("DesktopAgentPairingCode.expires_at must be non-empty")
        if not str(self.created_at).strip():
            raise PreconditionFailure("DesktopAgentPairingCode.created_at must be non-empty")
