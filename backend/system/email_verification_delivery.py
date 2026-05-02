from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from urllib.parse import urlencode

from backend.models.errors import ExternalServiceError
from backend.system.password_reset_delivery import current_password_reset_delivery_config


def _env_bool(name: str, default: bool) -> bool:
    from os import getenv

    raw = getenv(name)
    if raw is None:
        return bool(default)
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    from os import getenv

    raw = getenv(name)
    if raw is None or not str(raw).strip():
        return max(minimum, int(default))
    try:
        value = int(str(raw).strip())
    except Exception:
        value = int(default)
    return max(minimum, value)


@dataclass(frozen=True, slots=True)
class EmailVerificationDeliveryConfig:
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


def current_email_verification_delivery_config() -> EmailVerificationDeliveryConfig:
    mail_cfg = current_password_reset_delivery_config()
    return EmailVerificationDeliveryConfig(
        requested=_env_bool("PLM_ENABLE_EMAIL_VERIFICATION", False),
        auth_enabled=mail_cfg.auth_enabled,
        token_ttl_minutes=_env_int("PLM_EMAIL_VERIFICATION_TOKEN_TTL_MINUTES", 1440, minimum=10),
        public_origin=mail_cfg.public_origin,
        smtp_host=mail_cfg.smtp_host,
        smtp_port=mail_cfg.smtp_port,
        smtp_username=mail_cfg.smtp_username,
        smtp_password=mail_cfg.smtp_password,
        smtp_use_ssl=mail_cfg.smtp_use_ssl,
        smtp_use_starttls=mail_cfg.smtp_use_starttls,
        smtp_timeout_seconds=mail_cfg.smtp_timeout_seconds,
        from_email=mail_cfg.from_email,
        from_name=mail_cfg.from_name,
        credentials_ready=mail_cfg.credentials_ready,
        delivery_ready=mail_cfg.delivery_ready,
    )


def email_verification_enabled() -> bool:
    return current_email_verification_delivery_config().enabled


def build_email_verification_url(verification_token: str) -> str:
    config = current_email_verification_delivery_config()
    if not config.enabled or not config.public_origin:
        raise ExternalServiceError("Email verification is unavailable in this deployment")
    query = urlencode({"mode": "verify", "token": str(verification_token).strip()})
    return f"{config.public_origin}/login?{query}"


def send_email_verification_email(*, to_email: str, verification_url: str, expires_minutes: int) -> None:
    config = current_email_verification_delivery_config()
    if not config.enabled or not config.smtp_host or not config.from_email:
        raise ExternalServiceError("Email verification delivery is unavailable")

    message = EmailMessage()
    if config.from_name:
        message["From"] = f"{config.from_name} <{config.from_email}>"
    else:
        message["From"] = config.from_email
    message["To"] = str(to_email).strip()
    message["Subject"] = "LearningPyramid 邮箱验证"
    message.set_content(
        "\n".join(
            (
                "欢迎注册 LearningPyramid。",
                "请点击下面的链接完成邮箱验证并激活账号：",
                str(verification_url).strip(),
                "",
                f"这个链接将在 {int(expires_minutes)} 分钟后失效。",
                "如果这不是你的操作，请忽略这封邮件。",
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
        raise ExternalServiceError("Failed to send email verification email") from exc
