from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from urllib.parse import urlencode

from backend.models.errors import ExternalServiceError
from backend.system.runtime_features import current_runtime_features


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return max(minimum, int(default))
    try:
        value = int(str(raw).strip())
    except Exception:
        value = int(default)
    return max(minimum, value)


def _env_text(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _normalized_origin(value: str | None) -> str | None:
    text = str(value or "").strip().rstrip("/")
    if not text:
        return None
    if text.startswith("http://") or text.startswith("https://"):
        return text
    return None


@dataclass(frozen=True, slots=True)
class PasswordResetDeliveryConfig:
    requested: bool
    auth_enabled: bool
    token_ttl_minutes: int
    public_origin: str | None
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    smtp_use_ssl: bool
    smtp_use_starttls: bool
    smtp_timeout_seconds: int
    from_email: str | None
    from_name: str | None
    credentials_ready: bool
    delivery_ready: bool

    @property
    def enabled(self) -> bool:
        return bool(self.requested and self.auth_enabled and self.delivery_ready)


def current_password_reset_delivery_config() -> PasswordResetDeliveryConfig:
    smtp_use_ssl = _env_bool("PLM_SMTP_USE_SSL", False)
    default_port = 465 if smtp_use_ssl else 587
    smtp_port = _env_int("PLM_SMTP_PORT", default_port, minimum=1)
    smtp_username = _env_text("PLM_SMTP_USERNAME")
    smtp_password = _env_text("PLM_SMTP_PASSWORD")
    credentials_ready = (smtp_username is None and smtp_password is None) or (
        smtp_username is not None and smtp_password is not None
    )
    public_origin = _normalized_origin(_env_text("PLM_PUBLIC_ORIGIN"))
    auth_enabled = current_runtime_features().auth_enabled
    requested = _env_bool("PLM_ENABLE_PASSWORD_RESET", False)
    smtp_host = _env_text("PLM_SMTP_HOST")
    from_email = _env_text("PLM_SMTP_FROM_EMAIL")
    delivery_ready = bool(public_origin and smtp_host and from_email and credentials_ready)
    return PasswordResetDeliveryConfig(
        requested=requested,
        auth_enabled=auth_enabled,
        token_ttl_minutes=_env_int("PLM_PASSWORD_RESET_TOKEN_TTL_MINUTES", 30, minimum=5),
        public_origin=public_origin,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_username=smtp_username,
        smtp_password=smtp_password,
        smtp_use_ssl=smtp_use_ssl,
        smtp_use_starttls=_env_bool("PLM_SMTP_USE_STARTTLS", not smtp_use_ssl),
        smtp_timeout_seconds=_env_int("PLM_SMTP_TIMEOUT_SECONDS", 10, minimum=1),
        from_email=from_email,
        from_name=_env_text("PLM_SMTP_FROM_NAME"),
        credentials_ready=credentials_ready,
        delivery_ready=delivery_ready,
    )


def password_reset_enabled() -> bool:
    return current_password_reset_delivery_config().enabled


def build_password_reset_url(reset_token: str) -> str:
    config = current_password_reset_delivery_config()
    if not config.enabled or not config.public_origin:
        raise ExternalServiceError("Password reset is unavailable in this deployment")
    query = urlencode({"mode": "reset", "token": str(reset_token).strip()})
    return f"{config.public_origin}/login?{query}"


def send_password_reset_email(*, to_email: str, reset_url: str, expires_minutes: int) -> None:
    config = current_password_reset_delivery_config()
    if not config.enabled or not config.smtp_host or not config.from_email:
        raise ExternalServiceError("Password reset email delivery is unavailable")

    message = EmailMessage()
    if config.from_name:
        message["From"] = f"{config.from_name} <{config.from_email}>"
    else:
        message["From"] = config.from_email
    message["To"] = str(to_email).strip()
    message["Subject"] = "LearningPyramid 密码重置"
    message.set_content(
        "\n".join(
            (
                "你正在为 LearningPyramid 账号申请重置密码。",
                f"这个链接将在 {int(expires_minutes)} 分钟后失效：",
                str(reset_url).strip(),
                "",
                "如果这不是你的操作，请忽略这封邮件；当前密码不会被直接修改。",
            )
        )
    )

    try:
        if config.smtp_use_ssl:
            with smtplib.SMTP_SSL(
                config.smtp_host,
                config.smtp_port,
                timeout=config.smtp_timeout_seconds,
                context=ssl.create_default_context(),
            ) as server:
                if config.smtp_username and config.smtp_password:
                    server.login(config.smtp_username, config.smtp_password)
                server.send_message(message)
            return

        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=config.smtp_timeout_seconds) as server:
            server.ehlo()
            if config.smtp_use_starttls:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            if config.smtp_username and config.smtp_password:
                server.login(config.smtp_username, config.smtp_password)
            server.send_message(message)
    except Exception as exc:
        raise ExternalServiceError("Failed to send password reset email") from exc
