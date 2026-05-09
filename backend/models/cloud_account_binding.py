from dataclasses import dataclass
from typing import Any

from backend.models.errors import PreconditionFailure


@dataclass(frozen=True, slots=True)
class CloudAccountBinding:
    account_id: str
    user_id: str
    provider: str
    provider_user_id: str
    display_name: str
    avatar_url: str | None
    access_token_ciphertext: str
    refresh_token_ciphertext: str
    expires_at: str | None
    scope: str
    meta: dict[str, Any]
    created_at: str
    updated_at: str
    disabled_at: str | None

    @staticmethod
    def create(
        *,
        account_id: str,
        user_id: str,
        provider: str,
        provider_user_id: str,
        display_name: str,
        avatar_url: str | None,
        access_token_ciphertext: str,
        refresh_token_ciphertext: str,
        expires_at: str | None,
        scope: str = "",
        meta: dict[str, Any] | None = None,
        created_at: str,
        updated_at: str,
        disabled_at: str | None = None,
    ) -> "CloudAccountBinding":
        item = CloudAccountBinding(
            account_id=str(account_id).strip(),
            user_id=str(user_id).strip(),
            provider=str(provider).strip(),
            provider_user_id=str(provider_user_id).strip(),
            display_name=str(display_name).strip(),
            avatar_url=None if avatar_url is None else str(avatar_url).strip() or None,
            access_token_ciphertext=str(access_token_ciphertext).strip(),
            refresh_token_ciphertext=str(refresh_token_ciphertext).strip(),
            expires_at=None if expires_at is None else str(expires_at).strip() or None,
            scope=str(scope or "").strip(),
            meta=dict(meta or {}),
            created_at=str(created_at).strip(),
            updated_at=str(updated_at).strip(),
            disabled_at=None if disabled_at is None else str(disabled_at).strip() or None,
        )
        item.validate_write_time()
        return item

    def validate_write_time(self) -> None:
        if not self.account_id:
            raise PreconditionFailure("CloudAccountBinding.account_id must be non-empty")
        if not self.user_id:
            raise PreconditionFailure("CloudAccountBinding.user_id must be non-empty")
        if not self.provider:
            raise PreconditionFailure("CloudAccountBinding.provider must be non-empty")
        if not self.provider_user_id:
            raise PreconditionFailure("CloudAccountBinding.provider_user_id must be non-empty")
        if not self.display_name:
            raise PreconditionFailure("CloudAccountBinding.display_name must be non-empty")
        if not self.access_token_ciphertext:
            raise PreconditionFailure("CloudAccountBinding.access_token_ciphertext must be non-empty")
        if not self.refresh_token_ciphertext:
            raise PreconditionFailure("CloudAccountBinding.refresh_token_ciphertext must be non-empty")
        if not isinstance(self.meta, dict):
            raise PreconditionFailure("CloudAccountBinding.meta must be a dict")
        if not self.created_at:
            raise PreconditionFailure("CloudAccountBinding.created_at must be non-empty")
        if not self.updated_at:
            raise PreconditionFailure("CloudAccountBinding.updated_at must be non-empty")
