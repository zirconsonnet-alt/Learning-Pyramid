import base64
import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Mapping, Protocol
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.parse import urlencode

import qrcode
import qrcode.image.svg
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.models.errors import PreconditionFailure
from backend.system.runtime_features import current_runtime_features

PAYMENT_PROVIDER_MANUAL_TEST = "manual_test"
PAYMENT_PROVIDER_WECHAT_NATIVE = "wechat_native"
PAYOUT_STATUS_AWAITING_CONFIRMATION = "awaiting_confirmation"
PAYOUT_STATUS_PROCESSING = "processing"
PAYOUT_STATUS_SUCCEEDED = "succeeded"
PAYOUT_STATUS_FAILED = "failed"
PAYOUT_STATUS_CANCELED = "canceled"
PAYOUT_STATUS_NEEDS_ATTENTION = "needs_attention"
logger = logging.getLogger("learningpyramid.wechatpay")


def _env_text(name: str) -> str:
    return str(os.getenv(name) or "").strip()


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


def _env_int(name: str, default: int, *, min_value: int, max_value: int) -> int:
    raw = _env_text(name)
    if not raw:
        return default
    try:
        parsed = int(raw)
    except Exception:
        return default
    return min(max(parsed, min_value), max_value)


def manual_test_payment_enabled() -> bool:
    features = current_runtime_features()
    return _env_bool("LEARNINGPYRAMID_ENABLE_MANUAL_TEST_PAYMENT", features.app_mode != "hosted")


def _normalize_provider(provider: str) -> str:
    value = str(provider or "").strip().lower()
    supported_providers = list_supported_membership_payment_providers()
    if not supported_providers:
        raise PreconditionFailure("membership payments are unavailable in this deployment")
    if value not in supported_providers:
        supported = ", ".join(supported_providers)
        raise PreconditionFailure(f"membership payment provider must be one of: {supported}")
    return value


def _normalize_status(value: str) -> str:
    return str(value or "").strip().lower() or "unknown"


def _parse_iso_datetime(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _provider_label(provider: str) -> str:
    normalized = _normalize_status(provider)
    if normalized == PAYMENT_PROVIDER_WECHAT_NATIVE:
        return "微信扫码支付"
    if normalized == PAYMENT_PROVIDER_MANUAL_TEST:
        return "测试支付"
    return normalized


def _safe_path(raw_path: str) -> Path | None:
    text = str(raw_path or "").strip()
    if text:
        resolved = Path(text).expanduser().resolve()
        if resolved.exists():
            return resolved
    return None


def _looks_like_uuid_hex(value: str) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 32 and all(ch in "0123456789abcdef" for ch in text)


def _wechat_out_trade_no(order_id: str) -> str:
    normalized_order_id = str(order_id or "").strip()
    if not normalized_order_id:
        raise PreconditionFailure("membership order id must be non-empty")
    if normalized_order_id.startswith("mord_"):
        suffix = normalized_order_id.split("mord_", 1)[1].strip()
        if _looks_like_uuid_hex(suffix):
            return suffix
    if len(normalized_order_id) <= 32:
        return normalized_order_id
    raise PreconditionFailure("membership order id cannot be represented as a valid wechat out_trade_no")


def _local_order_id_from_wechat_out_trade_no(out_trade_no: str) -> str:
    normalized_out_trade_no = str(out_trade_no or "").strip()
    if not normalized_out_trade_no:
        raise PreconditionFailure("wechat out_trade_no must be non-empty")
    if _looks_like_uuid_hex(normalized_out_trade_no):
        return f"mord_{normalized_out_trade_no}"
    return normalized_out_trade_no


@dataclass(frozen=True, slots=True)
class WeChatNativePaymentConfig:
    app_id: str
    mch_id: str
    cert_serial_no: str
    api_v3_key: str
    private_key_pem_path: Path | None
    wechatpay_public_key_id: str
    wechatpay_public_key_pem_path: Path | None
    api_base_url: str
    notify_url: str | None
    refund_notify_url: str | None
    timeout_seconds: float
    description_prefix: str

    @property
    def enabled(self) -> bool:
        return all(
            (
                self.app_id,
                self.mch_id,
                self.cert_serial_no,
                self.api_v3_key,
                len(self.api_v3_key) == 32,
                self.private_key_pem_path is not None and self.private_key_pem_path.exists(),
                self.wechatpay_public_key_id,
                self.wechatpay_public_key_pem_path is not None and self.wechatpay_public_key_pem_path.exists(),
            )
        )


@dataclass(frozen=True, slots=True)
class WeChatPayoutConfig:
    app_id: str
    mch_id: str
    app_secret: str
    api_base_url: str
    transfer_scene_id: str
    transfer_remark: str
    user_recv_perception: str
    notify_url: str | None
    oauth_authorize_url: str
    oauth_token_url: str
    scene_report_infos: tuple[dict[str, str], ...]
    binding_qr_ttl_minutes: int
    provider_mode: str

    @property
    def enabled(self) -> bool:
        native = current_wechat_native_payment_config()
        return native.enabled and bool(self.transfer_scene_id) and self.provider_mode == PAYMENT_PROVIDER_WECHAT_NATIVE


def current_wechat_native_payment_config() -> WeChatNativePaymentConfig:
    api_base_url = _env_text("LEARNINGPYRAMID_WECHAT_PAY_API_BASE_URL") or "https://api.mch.weixin.qq.com"
    raw_timeout = _env_text("LEARNINGPYRAMID_WECHAT_PAY_TIMEOUT_SECONDS") or "10"
    try:
        timeout_seconds = max(3.0, float(raw_timeout))
    except Exception:
        timeout_seconds = 10.0
    return WeChatNativePaymentConfig(
        app_id=_env_text("LEARNINGPYRAMID_WECHAT_PAY_APP_ID"),
        mch_id=_env_text("LEARNINGPYRAMID_WECHAT_PAY_MCH_ID"),
        cert_serial_no=_env_text("LEARNINGPYRAMID_WECHAT_PAY_CERT_SERIAL_NO"),
        api_v3_key=_env_text("LEARNINGPYRAMID_WECHAT_PAY_API_V3_KEY"),
        private_key_pem_path=_safe_path(_env_text("LEARNINGPYRAMID_WECHAT_PAY_PRIVATE_KEY_PEM_PATH")),
        wechatpay_public_key_id=_env_text("LEARNINGPYRAMID_WECHAT_PAY_PUBLIC_KEY_ID"),
        wechatpay_public_key_pem_path=_safe_path(_env_text("LEARNINGPYRAMID_WECHAT_PAY_PUBLIC_KEY_PEM_PATH")),
        api_base_url=api_base_url.rstrip("/"),
        notify_url=_env_text("LEARNINGPYRAMID_WECHAT_PAY_NOTIFY_URL") or None,
        refund_notify_url=_env_text("LEARNINGPYRAMID_WECHAT_PAY_REFUND_NOTIFY_URL") or None,
        timeout_seconds=timeout_seconds,
        description_prefix=_env_text("LEARNINGPYRAMID_WECHAT_PAY_DESCRIPTION_PREFIX") or "LearningPyramid 月会员",
    )


def current_wechat_payout_config() -> WeChatPayoutConfig:
    native = current_wechat_native_payment_config()
    provider_mode = _env_text("LEARNINGPYRAMID_WECHAT_PAY_PAYOUT_PROVIDER_MODE") or PAYMENT_PROVIDER_WECHAT_NATIVE
    if provider_mode not in {PAYMENT_PROVIDER_WECHAT_NATIVE, PAYMENT_PROVIDER_MANUAL_TEST, "disabled"}:
        provider_mode = PAYMENT_PROVIDER_WECHAT_NATIVE
    raw_scene_infos = _env_text("LEARNINGPYRAMID_WECHAT_PAY_TRANSFER_SCENE_REPORT_INFOS_JSON")
    scene_infos: tuple[dict[str, str], ...] = (
        {"info_type": "岗位类型", "info_content": "推广员"},
        {"info_type": "报酬说明", "info_content": "会员邀请佣金"},
    )
    if raw_scene_infos:
        try:
            parsed = json.loads(raw_scene_infos)
            if isinstance(parsed, list):
                scene_infos = tuple(
                    {
                        "info_type": str(item.get("info_type") or item.get("type") or "").strip(),
                        "info_content": str(item.get("info_content") or item.get("content") or "").strip(),
                    }
                    for item in parsed
                    if isinstance(item, dict)
                )
        except Exception:
            scene_infos = scene_infos
    return WeChatPayoutConfig(
        app_id=native.app_id,
        mch_id=native.mch_id,
        app_secret=_env_text("LEARNINGPYRAMID_WECHAT_PAY_APP_SECRET"),
        api_base_url=native.api_base_url,
        transfer_scene_id=_env_text("LEARNINGPYRAMID_WECHAT_PAY_TRANSFER_SCENE_ID"),
        transfer_remark=_env_text("LEARNINGPYRAMID_WECHAT_PAY_TRANSFER_REMARK") or "会员邀请佣金提现",
        user_recv_perception=_env_text("LEARNINGPYRAMID_WECHAT_PAY_USER_RECV_PERCEPTION"),
        notify_url=_env_text("LEARNINGPYRAMID_WECHAT_PAY_TRANSFER_NOTIFY_URL") or None,
        oauth_authorize_url=_env_text("LEARNINGPYRAMID_WECHAT_PAY_OAUTH_AUTHORIZE_URL") or "https://open.weixin.qq.com/connect/oauth2/authorize",
        oauth_token_url=_env_text("LEARNINGPYRAMID_WECHAT_PAY_OAUTH_TOKEN_URL") or "https://api.weixin.qq.com/sns/oauth2/access_token",
        scene_report_infos=tuple(item for item in scene_infos if item["info_type"] and item["info_content"]),
        binding_qr_ttl_minutes=_env_int("LEARNINGPYRAMID_WECHAT_PAY_BINDING_QR_TTL_MINUTES", 10, min_value=1, max_value=60),
        provider_mode=provider_mode,
    )


def list_supported_membership_payment_providers() -> tuple[str, ...]:
    providers: set[str] = set()
    if manual_test_payment_enabled():
        providers.add(PAYMENT_PROVIDER_MANUAL_TEST)
    if current_wechat_native_payment_config().enabled:
        providers.add(PAYMENT_PROVIDER_WECHAT_NATIVE)
    return tuple(sorted(providers))


class MembershipOrderLike(Protocol):
    order_id: str
    user_id: str
    order_type: str
    payable_amount_cent: int
    provider: str
    expired_at: str | None


class MembershipPaymentRecordLike(Protocol):
    order_id: str
    provider: str
    provider_trade_no: str
    amount_cent: int
    refund_out_refund_no: str | None


class CommissionWithdrawalLike(Protocol):
    withdrawal_id: str
    user_id: str
    amount_cent: int
    wechat_open_id: str
    out_bill_no: str


@dataclass(frozen=True, slots=True)
class MembershipPaymentPayload:
    mode: str
    provider: str
    provider_label: str
    instruction: str
    provider_trade_no_hint: str
    expires_at: str | None
    code_url: str | None
    qr_image_data_url: str | None
    open_url: str | None
    poll_interval_seconds: int | None
    status_check_supported: bool


@dataclass(frozen=True, slots=True)
class MembershipRemotePaymentStatus:
    provider: str
    order_id: str
    provider_trade_no: str
    remote_status: str
    paid_at: str | None
    amount_cent: int | None
    payer_id: str | None
    raw_payload_json: str


@dataclass(frozen=True, slots=True)
class MembershipRemoteRefundStatus:
    provider: str
    order_id: str
    refund_out_trade_no: str
    provider_refund_no: str | None
    remote_status: str
    refunded_at: str | None
    refund_amount_cent: int | None
    raw_payload_json: str


@dataclass(frozen=True, slots=True)
class CommissionPayoutStatus:
    withdrawal_id: str
    provider_transfer_no: str | None
    remote_status: str
    failure_reason: str
    raw_payload_json: str
    out_bill_no: str = ""
    provider_state: str = ""
    package_info: str | None = None
    amount_cent: int | None = None
    appid: str | None = None
    confirmation: "PayoutConfirmationPayload | None" = None


@dataclass(frozen=True, slots=True)
class PayoutConfirmationPayload:
    mode: str
    mch_id: str
    app_id: str
    package_info: str


class MembershipPaymentService:
    def __init__(self) -> None:
        self._session = requests.Session()
        self._private_key = None
        self._wechat_public_key_cache = None

    def supported_providers(self) -> tuple[str, ...]:
        return list_supported_membership_payment_providers()

    def current_wechat_payout_config(self) -> WeChatPayoutConfig:
        return current_wechat_payout_config()

    def create_payment_payload(
        self,
        order: MembershipOrderLike,
        *,
        client_ip: str = "",
        public_origin: str | None = None,
    ) -> MembershipPaymentPayload:
        provider = _normalize_provider(order.provider)
        if provider == PAYMENT_PROVIDER_MANUAL_TEST:
            return MembershipPaymentPayload(
                mode=PAYMENT_PROVIDER_MANUAL_TEST,
                provider=provider,
                provider_label=_provider_label(provider),
                instruction="仅在本地或验收环境中使用 manual_test 回调模拟支付成功。",
                provider_trade_no_hint=f"manual_{order.order_id}",
                expires_at=order.expired_at,
                code_url=None,
                qr_image_data_url=None,
                open_url=None,
                poll_interval_seconds=None,
                status_check_supported=False,
            )
        if provider == PAYMENT_PROVIDER_WECHAT_NATIVE:
            return self._create_wechat_native_payload(order, client_ip=client_ip, public_origin=public_origin)
        raise PreconditionFailure("membership payment provider is unavailable")

    def query_payment_status(self, order: MembershipOrderLike) -> MembershipRemotePaymentStatus:
        provider = _normalize_provider(order.provider)
        if provider != PAYMENT_PROVIDER_WECHAT_NATIVE:
            raise PreconditionFailure("membership payment status sync is only available for wechat_native")
        return self._query_wechat_native_payment(order)

    def parse_payment_notification(
        self,
        provider: str,
        *,
        headers: Mapping[str, str],
        body_text: str,
    ) -> MembershipRemotePaymentStatus:
        normalized_provider = _normalize_provider(provider)
        if normalized_provider != PAYMENT_PROVIDER_WECHAT_NATIVE:
            raise PreconditionFailure("membership payment notification is unsupported for this provider")
        return self._parse_wechat_native_notification(headers=headers, body_text=body_text)

    def request_refund(
        self,
        order: MembershipOrderLike,
        payment: MembershipPaymentRecordLike,
        *,
        reason: str = "",
        public_origin: str | None = None,
    ) -> MembershipRemoteRefundStatus:
        provider = _normalize_provider(order.provider)
        if provider != PAYMENT_PROVIDER_WECHAT_NATIVE:
            raise PreconditionFailure("membership refund requests are only available for wechat_native")
        return self._request_wechat_refund(order, payment, reason=reason, public_origin=public_origin)

    def query_refund_status(
        self,
        order: MembershipOrderLike,
        payment: MembershipPaymentRecordLike,
    ) -> MembershipRemoteRefundStatus:
        provider = _normalize_provider(order.provider)
        if provider != PAYMENT_PROVIDER_WECHAT_NATIVE:
            raise PreconditionFailure("membership refund status sync is only available for wechat_native")
        return self._query_wechat_refund(order, payment)

    def parse_refund_notification(
        self,
        provider: str,
        *,
        headers: Mapping[str, str],
        body_text: str,
    ) -> MembershipRemoteRefundStatus:
        normalized_provider = _normalize_provider(provider)
        if normalized_provider != PAYMENT_PROVIDER_WECHAT_NATIVE:
            raise PreconditionFailure("membership refund notification is unsupported for this provider")
        return self._parse_wechat_refund_notification(headers=headers, body_text=body_text)

    def request_commission_payout(self, withdrawal: CommissionWithdrawalLike) -> CommissionPayoutStatus:
        if manual_test_payment_enabled() and not current_wechat_payout_config().enabled:
            provider_transfer_no = f"manual_{withdrawal.withdrawal_id}"
            return CommissionPayoutStatus(
                withdrawal_id=withdrawal.withdrawal_id,
                provider_transfer_no=provider_transfer_no,
                remote_status="processing",
                failure_reason="",
                raw_payload_json=json.dumps(
                    {
                        "mode": "manual_test",
                        "withdrawalId": withdrawal.withdrawal_id,
                        "providerTransferNo": provider_transfer_no,
                        "outBillNo": getattr(withdrawal, "out_bill_no", ""),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                out_bill_no=getattr(withdrawal, "out_bill_no", ""),
                provider_state="PROCESSING",
                amount_cent=int(withdrawal.amount_cent),
                appid="manual_test",
            )
        return self._request_wechat_commission_payout(withdrawal)

    def build_wechat_payout_binding_authorization_url(self, *, state: str, return_url: str, channel: str) -> str:
        if str(channel or "").strip().lower() == PAYMENT_PROVIDER_MANUAL_TEST or manual_test_payment_enabled():
            return f"manual_test://wechat-payout-confirm?{urlencode({'state': state, 'returnUrl': return_url})}"
        config = current_wechat_payout_config()
        if not config.app_id:
            raise PreconditionFailure("wechat payout appid is not configured in this deployment")
        redirect_uri = str(return_url or "").strip()
        if not redirect_uri:
            raise PreconditionFailure("wechat binding returnUrl is required")
        query = urlencode(
            {
                "appid": config.app_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "snsapi_base",
                "state": str(state),
            }
        )
        return f"{config.oauth_authorize_url}?{query}#wechat_redirect"

    def resolve_wechat_payout_openid(self, *, authorization_code: str, channel: str) -> tuple[str, str]:
        code = str(authorization_code or "").strip()
        if not code:
            raise PreconditionFailure("wechat authorizationCode is required")
        config = current_wechat_payout_config()
        if str(channel or "").strip().lower() == PAYMENT_PROVIDER_MANUAL_TEST or (manual_test_payment_enabled() and not config.enabled):
            return code, config.app_id or "manual_test"
        if not config.app_id or not config.app_secret:
            raise PreconditionFailure("wechat payout OAuth appid/app secret is not configured")
        response = self._session.get(
            config.oauth_token_url,
            params={
                "appid": config.app_id,
                "secret": config.app_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
            timeout=current_wechat_native_payment_config().timeout_seconds,
        )
        if not response.ok:
            raise PreconditionFailure(f"wechat OAuth request failed with HTTP {response.status_code}: {(response.text or '')[:400]}")
        try:
            payload = response.json()
        except Exception as exc:
            raise PreconditionFailure("wechat OAuth returned a non-JSON response") from exc
        openid = str(payload.get("openid") or "").strip()
        if not openid:
            err = str(payload.get("errmsg") or payload.get("errcode") or "wechat OAuth did not return openid")
            raise PreconditionFailure(err)
        return openid, config.app_id

    def _create_wechat_native_payload(
        self,
        order: MembershipOrderLike,
        *,
        client_ip: str,
        public_origin: str | None,
    ) -> MembershipPaymentPayload:
        config = current_wechat_native_payment_config()
        if not config.enabled:
            raise PreconditionFailure("wechat_native payment is not configured in this deployment")
        notify_url = config.notify_url or self._build_default_wechat_notify_url(public_origin)
        description_suffix = "首单开通" if str(order.order_type) == "first_purchase" else "续费"
        wechat_out_trade_no = _wechat_out_trade_no(str(order.order_id))
        request_body: dict[str, object] = {
            "appid": config.app_id,
            "mchid": config.mch_id,
            "description": f"{config.description_prefix} {description_suffix}".strip()[:127],
            "out_trade_no": wechat_out_trade_no,
            "notify_url": notify_url,
            "amount": {
                "total": int(order.payable_amount_cent),
                "currency": "CNY",
            },
            "attach": "membership_v2",
        }
        if order.expired_at:
            request_body["time_expire"] = str(order.expired_at)
        if str(client_ip or "").strip():
            request_body["scene_info"] = {"payer_client_ip": str(client_ip).strip()}
        response_body = self._wechat_request_json("POST", "/v3/pay/transactions/native", request_body)
        code_url = str(response_body.get("code_url") or "").strip()
        if not code_url:
            raise PreconditionFailure("wechat_native payment did not return a code_url")
        return MembershipPaymentPayload(
            mode=PAYMENT_PROVIDER_WECHAT_NATIVE,
            provider=PAYMENT_PROVIDER_WECHAT_NATIVE,
            provider_label=_provider_label(PAYMENT_PROVIDER_WECHAT_NATIVE),
            instruction="请使用微信扫描二维码完成支付。支付成功后页面会自动刷新。",
            provider_trade_no_hint=wechat_out_trade_no,
            expires_at=order.expired_at,
            code_url=code_url,
            qr_image_data_url=self._build_qr_image_data_url(code_url),
            open_url=code_url,
            poll_interval_seconds=2,
            status_check_supported=True,
        )

    def _query_wechat_native_payment(self, order: MembershipOrderLike) -> MembershipRemotePaymentStatus:
        config = current_wechat_native_payment_config()
        if not config.enabled:
            raise PreconditionFailure("wechat_native payment is not configured in this deployment")
        wechat_out_trade_no = _wechat_out_trade_no(str(order.order_id))
        uri = f"/v3/pay/transactions/out-trade-no/{quote(wechat_out_trade_no, safe='')}?mchid={quote(config.mch_id, safe='')}"
        response_body = self._wechat_request_json("GET", uri)
        trade_state = str(response_body.get("trade_state") or "").strip().upper()
        transaction_id = str(response_body.get("transaction_id") or order.order_id).strip()
        amount = response_body.get("amount") if isinstance(response_body.get("amount"), dict) else {}
        payer = response_body.get("payer") if isinstance(response_body.get("payer"), dict) else {}
        return MembershipRemotePaymentStatus(
            provider=PAYMENT_PROVIDER_WECHAT_NATIVE,
            order_id=_local_order_id_from_wechat_out_trade_no(str(response_body.get("out_trade_no") or "")),
            provider_trade_no=transaction_id,
            remote_status=self._map_wechat_trade_state(trade_state),
            paid_at=_parse_iso_datetime(response_body.get("success_time")),
            amount_cent=None if not isinstance(amount, dict) else int(amount.get("total") or 0),
            payer_id=None if not isinstance(payer, dict) else str(payer.get("openid") or "").strip() or None,
            raw_payload_json=json.dumps(response_body, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        )

    def _parse_wechat_native_notification(
        self,
        *,
        headers: Mapping[str, str],
        body_text: str,
    ) -> MembershipRemotePaymentStatus:
        config = current_wechat_native_payment_config()
        if not config.enabled:
            raise PreconditionFailure("wechat_native payment is not configured in this deployment")
        self._verify_wechat_signature(headers=headers, body_text=body_text)
        try:
            envelope = json.loads(body_text)
        except Exception as exc:
            raise PreconditionFailure("wechat payment notification body must be valid JSON") from exc
        resource = envelope.get("resource")
        if not isinstance(resource, dict):
            raise PreconditionFailure("wechat payment notification is missing its encrypted resource")
        decrypted = self._decrypt_wechat_resource(resource)
        trade_state = str(decrypted.get("trade_state") or "").strip().upper()
        amount = decrypted.get("amount") if isinstance(decrypted.get("amount"), dict) else {}
        payer = decrypted.get("payer") if isinstance(decrypted.get("payer"), dict) else {}
        raw_payload_json = json.dumps(
            {"notification": envelope, "resource": decrypted},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return MembershipRemotePaymentStatus(
            provider=PAYMENT_PROVIDER_WECHAT_NATIVE,
            order_id=_local_order_id_from_wechat_out_trade_no(str(decrypted.get("out_trade_no") or "").strip()),
            provider_trade_no=str(decrypted.get("transaction_id") or "").strip(),
            remote_status=self._map_wechat_trade_state(trade_state),
            paid_at=_parse_iso_datetime(decrypted.get("success_time")),
            amount_cent=None if not isinstance(amount, dict) else int(amount.get("total") or 0),
            payer_id=None if not isinstance(payer, dict) else str(payer.get("openid") or "").strip() or None,
            raw_payload_json=raw_payload_json,
        )

    def _request_wechat_refund(
        self,
        order: MembershipOrderLike,
        payment: MembershipPaymentRecordLike,
        *,
        reason: str,
        public_origin: str | None,
    ) -> MembershipRemoteRefundStatus:
        config = current_wechat_native_payment_config()
        if not config.enabled:
            raise PreconditionFailure("wechat_native payment is not configured in this deployment")
        refund_out_trade_no = str(payment.refund_out_refund_no or f"mrefund_{order.order_id}").strip()
        if not refund_out_trade_no:
            raise PreconditionFailure("membership refund out_refund_no must be non-empty")
        notify_url = config.refund_notify_url or self._build_default_wechat_refund_notify_url(public_origin)
        request_body: dict[str, object] = {
            "out_refund_no": refund_out_trade_no,
            "reason": str(reason or "").strip()[:80],
            "notify_url": notify_url,
            "amount": {
                "refund": int(payment.amount_cent),
                "total": int(payment.amount_cent),
                "currency": "CNY",
            },
        }
        transaction_id = str(payment.provider_trade_no or "").strip()
        if transaction_id:
            request_body["transaction_id"] = transaction_id
        else:
            request_body["out_trade_no"] = _wechat_out_trade_no(str(order.order_id))
        response_body = self._wechat_request_json("POST", "/v3/refund/domestic/refunds", request_body)
        return self._wechat_refund_status_from_payload(
            order_id=_local_order_id_from_wechat_out_trade_no(str(response_body.get("out_trade_no") or "")),
            refund_out_trade_no=str(response_body.get("out_refund_no") or refund_out_trade_no),
            payload=response_body,
        )

    def _request_wechat_commission_payout(self, withdrawal: CommissionWithdrawalLike) -> CommissionPayoutStatus:
        config = current_wechat_payout_config()
        if not config.enabled:
            raise PreconditionFailure("wechat payout is not configured in this deployment")
        request_body: dict[str, object] = {
            "appid": config.app_id,
            "out_bill_no": str(withdrawal.out_bill_no),
            "transfer_scene_id": config.transfer_scene_id,
            "openid": str(withdrawal.wechat_open_id),
            "transfer_amount": int(withdrawal.amount_cent),
            "transfer_remark": config.transfer_remark[:32],
        }
        if config.user_recv_perception:
            request_body["user_recv_perception"] = config.user_recv_perception[:32]
        if config.notify_url:
            request_body["notify_url"] = config.notify_url
        if config.scene_report_infos:
            request_body["transfer_scene_report_infos"] = list(config.scene_report_infos)
        response_body = self._wechat_request_json("POST", "/v3/fund-app/mch-transfer/transfer-bills", request_body)
        return self._wechat_transfer_status_from_payload(
            withdrawal_id=str(withdrawal.withdrawal_id),
            payload=response_body,
        )

    def query_commission_payout(self, out_bill_no: str, *, withdrawal_id: str = "") -> CommissionPayoutStatus:
        config = current_wechat_payout_config()
        if not config.enabled:
            raise PreconditionFailure("wechat payout is not configured in this deployment")
        normalized_out_bill_no = str(out_bill_no or "").strip()
        if not normalized_out_bill_no:
            raise PreconditionFailure("wechat payout outBillNo must be non-empty")
        uri = f"/v3/fund-app/mch-transfer/transfer-bills/out-bill-no/{quote(normalized_out_bill_no, safe='')}"
        response_body = self._wechat_request_json("GET", uri)
        return self._wechat_transfer_status_from_payload(
            withdrawal_id=str(withdrawal_id or ""),
            payload=response_body,
        )

    def parse_transfer_notification(
        self,
        *,
        headers: Mapping[str, str],
        body_text: str,
    ) -> CommissionPayoutStatus:
        config = current_wechat_payout_config()
        if not config.enabled:
            raise PreconditionFailure("wechat payout is not configured in this deployment")
        self._verify_wechat_signature(headers=headers, body_text=body_text)
        try:
            envelope = json.loads(body_text)
        except Exception as exc:
            raise PreconditionFailure("wechat transfer notification body must be valid JSON") from exc
        resource = envelope.get("resource")
        if not isinstance(resource, dict):
            raise PreconditionFailure("wechat transfer notification is missing its encrypted resource")
        decrypted = self._decrypt_wechat_resource(resource)
        payload = dict(decrypted)
        payload["_raw_payload_json"] = json.dumps(
            {"notification": envelope, "resource": decrypted},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return self._wechat_transfer_status_from_payload(withdrawal_id="", payload=payload)

    def _query_wechat_refund(
        self,
        order: MembershipOrderLike,
        payment: MembershipPaymentRecordLike,
    ) -> MembershipRemoteRefundStatus:
        config = current_wechat_native_payment_config()
        if not config.enabled:
            raise PreconditionFailure("wechat_native payment is not configured in this deployment")
        refund_out_trade_no = str(payment.refund_out_refund_no or f"mrefund_{order.order_id}").strip()
        if not refund_out_trade_no:
            raise PreconditionFailure("membership refund out_refund_no must be non-empty")
        uri = f"/v3/refund/domestic/refunds/{quote(refund_out_trade_no, safe='')}"
        response_body = self._wechat_request_json("GET", uri)
        return self._wechat_refund_status_from_payload(
            order_id=_local_order_id_from_wechat_out_trade_no(str(response_body.get("out_trade_no") or "")),
            refund_out_trade_no=str(response_body.get("out_refund_no") or refund_out_trade_no),
            payload=response_body,
        )

    def _parse_wechat_refund_notification(
        self,
        *,
        headers: Mapping[str, str],
        body_text: str,
    ) -> MembershipRemoteRefundStatus:
        config = current_wechat_native_payment_config()
        if not config.enabled:
            raise PreconditionFailure("wechat_native payment is not configured in this deployment")
        self._verify_wechat_signature(headers=headers, body_text=body_text)
        try:
            envelope = json.loads(body_text)
        except Exception as exc:
            raise PreconditionFailure("wechat refund notification body must be valid JSON") from exc
        resource = envelope.get("resource")
        if not isinstance(resource, dict):
            raise PreconditionFailure("wechat refund notification is missing its encrypted resource")
        decrypted = self._decrypt_wechat_resource(resource)
        raw_payload_json = json.dumps(
            {"notification": envelope, "resource": decrypted},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        payload = dict(decrypted)
        payload["_raw_payload_json"] = raw_payload_json
        return self._wechat_refund_status_from_payload(
            order_id=_local_order_id_from_wechat_out_trade_no(str(decrypted.get("out_trade_no") or "").strip()),
            refund_out_trade_no=str(decrypted.get("out_refund_no") or "").strip(),
            payload=payload,
        )

    def _build_default_wechat_refund_notify_url(self, public_origin: str | None) -> str:
        origin = str(public_origin or "").strip().rstrip("/")
        if origin:
            return f"{origin}/api/payments/wechat/refund-notify"
        config = current_wechat_native_payment_config()
        if config.notify_url:
            parsed = urlsplit(config.notify_url)
            if parsed.scheme and parsed.netloc:
                return urlunsplit((parsed.scheme, parsed.netloc, "/api/payments/wechat/refund-notify", "", ""))
        raise PreconditionFailure(
            "LEARNINGPYRAMID_PUBLIC_ORIGIN, LEARNINGPYRAMID_WECHAT_PAY_REFUND_NOTIFY_URL, or a valid LEARNINGPYRAMID_WECHAT_PAY_NOTIFY_URL must be set before using wechat_native refunds"
        )

    def _build_default_wechat_notify_url(self, public_origin: str | None) -> str:
        origin = str(public_origin or "").strip().rstrip("/")
        if not origin:
            raise PreconditionFailure("LEARNINGPYRAMID_PUBLIC_ORIGIN or LEARNINGPYRAMID_WECHAT_PAY_NOTIFY_URL must be set before using wechat_native")
        return f"{origin}/api/payments/wechat/notify"

    def _wechat_request_json(self, method: str, uri: str, body: dict[str, object] | None = None) -> dict[str, object]:
        config = current_wechat_native_payment_config()
        if not config.enabled:
            raise PreconditionFailure("wechat_native payment is not configured in this deployment")
        resolved_method = str(method or "GET").strip().upper()
        resolved_uri = str(uri or "").strip()
        if not resolved_uri.startswith("/"):
            raise PreconditionFailure("wechat payment request uri must start with /")
        body_text = "" if body is None else json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        headers = {
            "Accept": "application/json",
            "Authorization": self._build_wechat_authorization(resolved_method, resolved_uri, body_text),
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        if config.wechatpay_public_key_id:
            headers["Wechatpay-Serial"] = config.wechatpay_public_key_id
        max_attempts = 2
        last_verify_error: PreconditionFailure | None = None
        last_verify_context = ""
        for attempt in range(1, max_attempts + 1):
            response = self._session.request(
                resolved_method,
                f"{config.api_base_url}{resolved_uri}",
                data=None if body is None else body_text.encode("utf-8"),
                headers=headers,
                timeout=config.timeout_seconds,
            )
            response_text = response.text or ""
            if not response.ok:
                raise PreconditionFailure(
                    f"wechat_native request failed with HTTP {response.status_code}: {response_text[:400] or 'empty response'}"
                )
            signature_header = str(response.headers.get("Wechatpay-Signature") or "").strip()
            if signature_header:
                try:
                    self._verify_wechat_signature(headers=response.headers, body_bytes=response.content)
                except PreconditionFailure as exc:
                    serial_header = str(response.headers.get("Wechatpay-Serial") or "").strip()
                    sign_type_header = str(response.headers.get("Wechatpay-Signature-Type") or "").strip()
                    is_sign_test = signature_header.startswith("WECHATPAY/SIGNTEST/")
                    last_verify_error = exc
                    last_verify_context = (
                        f"serial={serial_header or '(empty)'} "
                        f"sign_type={sign_type_header or '(empty)'} "
                        f"sign_test={is_sign_test}"
                    )
                    if attempt < max_attempts:
                        logger.warning(
                            "wechatpay_response_verify_retry attempt=%s method=%s uri=%s %s",
                            attempt,
                            resolved_method,
                            resolved_uri,
                            last_verify_context,
                        )
                        continue
                    logger.warning(
                        "wechatpay_response_verify_failed method=%s uri=%s %s",
                        resolved_method,
                        resolved_uri,
                        last_verify_context,
                    )
                    raise exc
            try:
                payload = response.json()
            except Exception as exc:
                raise PreconditionFailure("wechat_native returned a non-JSON response") from exc
            if not isinstance(payload, dict):
                raise PreconditionFailure("wechat_native returned an unexpected response payload")
            return payload
        raise PreconditionFailure("wechat_native request failed unexpectedly")

    def _build_wechat_authorization(self, method: str, uri: str, body_text: str) -> str:
        config = current_wechat_native_payment_config()
        nonce = uuid.uuid4().hex
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        message = f"{method}\n{uri}\n{timestamp}\n{nonce}\n{body_text}\n".encode("utf-8")
        signature = self._wechat_private_key().sign(message, padding.PKCS1v15(), hashes.SHA256())
        signature_b64 = base64.b64encode(signature).decode("utf-8")
        return (
            "WECHATPAY2-SHA256-RSA2048 "
            f'mchid="{config.mch_id}",'
            f'nonce_str="{nonce}",'
            f'timestamp="{timestamp}",'
            f'serial_no="{config.cert_serial_no}",'
            f'signature="{signature_b64}"'
        )

    def _verify_wechat_signature(
        self,
        *,
        headers: Mapping[str, str],
        body_text: str | None = None,
        body_bytes: bytes | None = None,
    ) -> None:
        timestamp = str(headers.get("Wechatpay-Timestamp") or headers.get("wechatpay-timestamp") or "").strip()
        nonce = str(headers.get("Wechatpay-Nonce") or headers.get("wechatpay-nonce") or "").strip()
        signature_b64 = str(headers.get("Wechatpay-Signature") or headers.get("wechatpay-signature") or "").strip()
        if not timestamp or not nonce or not signature_b64:
            raise PreconditionFailure("wechat payment signature headers are incomplete")
        if body_bytes is None:
            message_body = str(body_text or "").encode("utf-8")
        else:
            message_body = bytes(body_bytes)
        message = (
            timestamp.encode("utf-8")
            + b"\n"
            + nonce.encode("utf-8")
            + b"\n"
            + message_body
            + b"\n"
        )
        signature = base64.b64decode(signature_b64)
        try:
            self._get_wechat_public_key().verify(signature, message, padding.PKCS1v15(), hashes.SHA256())
        except Exception as exc:
            raise PreconditionFailure("wechat payment signature verification failed") from exc

    def _decrypt_wechat_resource(self, resource: Mapping[str, object]) -> dict[str, object]:
        config = current_wechat_native_payment_config()
        ciphertext = str(resource.get("ciphertext") or "").strip()
        nonce = str(resource.get("nonce") or "").strip()
        if not ciphertext or not nonce:
            raise PreconditionFailure("wechat payment notification resource is incomplete")
        associated_data = str(resource.get("associated_data") or "")
        try:
            plain_bytes = AESGCM(config.api_v3_key.encode("utf-8")).decrypt(
                nonce.encode("utf-8"),
                base64.b64decode(ciphertext),
                associated_data.encode("utf-8"),
            )
        except Exception as exc:
            raise PreconditionFailure("wechat payment notification decryption failed") from exc
        try:
            payload = json.loads(plain_bytes.decode("utf-8"))
        except Exception as exc:
            raise PreconditionFailure("wechat payment notification plaintext is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise PreconditionFailure("wechat payment notification plaintext is malformed")
        return payload

    def _wechat_private_key(self):
        if self._private_key is not None:
            return self._private_key
        config = current_wechat_native_payment_config()
        if config.private_key_pem_path is None or not config.private_key_pem_path.exists():
            raise PreconditionFailure("LEARNINGPYRAMID_WECHAT_PAY_PRIVATE_KEY_PEM_PATH does not point to an existing PEM file")
        self._private_key = serialization.load_pem_private_key(
            config.private_key_pem_path.read_bytes(),
            password=None,
        )
        return self._private_key

    def _get_wechat_public_key(self):
        if self._wechat_public_key_cache is not None:
            return self._wechat_public_key_cache
        config = current_wechat_native_payment_config()
        if config.wechatpay_public_key_pem_path is None or not config.wechatpay_public_key_pem_path.exists():
            raise PreconditionFailure("LEARNINGPYRAMID_WECHAT_PAY_PUBLIC_KEY_PEM_PATH does not point to an existing PEM file")
        self._wechat_public_key_cache = serialization.load_pem_public_key(config.wechatpay_public_key_pem_path.read_bytes())
        return self._wechat_public_key_cache

    @staticmethod
    def _build_qr_image_data_url(code_url: str) -> str:
        image = qrcode.make(code_url, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
        buffer = BytesIO()
        image.save(buffer)
        svg_bytes = buffer.getvalue()
        return f"data:image/svg+xml;base64,{base64.b64encode(svg_bytes).decode('ascii')}"

    @staticmethod
    def _wechat_refund_status_from_payload(
        *,
        order_id: str,
        refund_out_trade_no: str,
        payload: Mapping[str, object],
    ) -> MembershipRemoteRefundStatus:
        refund_amount = payload.get("amount")
        if not isinstance(refund_amount, dict):
            refund_amount = {}
        raw_payload_json = str(payload.get("_raw_payload_json") or "")
        if not raw_payload_json:
            raw_payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        status_value = str(payload.get("status") or payload.get("refund_status") or "").strip().upper()
        return MembershipRemoteRefundStatus(
            provider=PAYMENT_PROVIDER_WECHAT_NATIVE,
            order_id=str(order_id),
            refund_out_trade_no=str(refund_out_trade_no),
            provider_refund_no=None if not str(payload.get("refund_id") or "").strip() else str(payload.get("refund_id")).strip(),
            remote_status=MembershipPaymentService._map_wechat_refund_status(status_value),
            refunded_at=_parse_iso_datetime(payload.get("success_time")),
            refund_amount_cent=None if not isinstance(refund_amount, dict) else int(refund_amount.get("refund") or 0),
            raw_payload_json=raw_payload_json,
        )

    @staticmethod
    def _map_wechat_trade_state(trade_state: str) -> str:
        normalized_state = str(trade_state or "").strip().upper()
        if normalized_state == "SUCCESS":
            return "paid"
        if normalized_state in {"NOTPAY", "USERPAYING"}:
            return "pending"
        if normalized_state == "CLOSED":
            return "closed"
        if normalized_state in {"REFUND", "PARTIAL_REFUND"}:
            return "refunded"
        if normalized_state in {"PAYERROR", "REVOKED"}:
            return "failed"
        return "unknown"

    @staticmethod
    def _map_wechat_refund_status(status: str) -> str:
        normalized_status = str(status or "").strip().upper()
        if normalized_status == "SUCCESS":
            return "refunded"
        if normalized_status == "PROCESSING":
            return "refund_pending"
        if normalized_status in {"CLOSED", "ABNORMAL"}:
            return "failed"
        return "unknown"

    @staticmethod
    def _map_wechat_transfer_state(state: str) -> str:
        normalized_state = str(state or "").strip().upper()
        if normalized_state == "WAIT_USER_CONFIRM":
            return PAYOUT_STATUS_AWAITING_CONFIRMATION
        if normalized_state in {"ACCEPTED", "PROCESSING", "TRANSFERRING"}:
            return PAYOUT_STATUS_PROCESSING
        if normalized_state == "SUCCESS":
            return PAYOUT_STATUS_SUCCEEDED
        if normalized_state in {"FAIL", "FAILED"}:
            return PAYOUT_STATUS_FAILED
        if normalized_state in {"CANCELING", "CANCELLED", "CANCELED"}:
            return PAYOUT_STATUS_CANCELED
        return PAYOUT_STATUS_NEEDS_ATTENTION

    @staticmethod
    def _wechat_transfer_status_from_payload(
        *,
        withdrawal_id: str,
        payload: Mapping[str, object],
    ) -> CommissionPayoutStatus:
        state = str(payload.get("state") or payload.get("transfer_state") or payload.get("status") or "PROCESSING").strip().upper()
        mapped = MembershipPaymentService._map_wechat_transfer_state(state)
        transfer_bill_no = str(payload.get("transfer_bill_no") or payload.get("transfer_bill_no") or "").strip()
        out_bill_no = str(payload.get("out_bill_no") or "").strip()
        if not out_bill_no:
            raise PreconditionFailure("wechat transfer out_bill_no must be non-empty")
        package_info = str(payload.get("package_info") or "").strip() or None
        raw_payload_json = str(payload.get("_raw_payload_json") or "")
        if not raw_payload_json:
            raw_payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        amount_value = payload.get("transfer_amount")
        amount_cent: int | None = None
        if amount_value is not None:
            try:
                amount_cent = int(amount_value)
            except Exception:
                amount_cent = None
        appid = str(payload.get("appid") or "").strip() or None
        confirmation = None
        if mapped == PAYOUT_STATUS_AWAITING_CONFIRMATION and package_info:
            config = current_wechat_payout_config()
            confirmation = PayoutConfirmationPayload(
                mode="wechat_jsapi_requestMerchantTransfer",
                mch_id=config.mch_id,
                app_id=config.app_id,
                package_info=package_info,
            )
        failure_reason = ""
        if mapped in {PAYOUT_STATUS_FAILED, PAYOUT_STATUS_CANCELED, PAYOUT_STATUS_NEEDS_ATTENTION}:
            failure_reason = str(payload.get("fail_reason") or payload.get("reason") or payload.get("remark") or "").strip()
        return CommissionPayoutStatus(
            withdrawal_id=str(withdrawal_id),
            provider_transfer_no=transfer_bill_no or None,
            remote_status=mapped,
            failure_reason=failure_reason,
            raw_payload_json=raw_payload_json,
            out_bill_no=out_bill_no,
            provider_state=state,
            package_info=package_info,
            amount_cent=amount_cent,
            appid=appid,
            confirmation=confirmation,
        )
