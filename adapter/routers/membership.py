import hashlib
import hmac
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, RedirectResponse

from adapter.auth import require_request_auth_user
from adapter.deps import get_auth_store, get_membership_commission_store, get_membership_marketing_store, get_membership_payment_service, get_membership_store
from adapter.schemas import (
    BindInviteCodeRequest,
    CompleteWeChatWithdrawalConfirmationAttemptRequest,
    ConfirmMembershipPaymentRequest,
    CreateCommissionWithdrawalRequest,
    CreateMembershipOrderRequest,
    PreviewMembershipOrderRequest,
    StartWeChatWithdrawalConfirmationAttemptRequest,
)
from backend.models.errors import NotFound, PreconditionFailure
from backend.system.auth_store import AuthStore
from backend.system.http_runtime_config import current_http_runtime_config
from backend.system.membership_marketing_store import (
    CouponRecord,
    InviteBinding,
    InviteReferralRecord,
    InviteSummary,
    MembershipMarketingStore,
)
from backend.system.membership_commission_store import (
    BINDING_STATUS_AUTHORIZED,
    BINDING_STATUS_BOUND,
    BINDING_STATUS_CONFIRMED,
    BINDING_STATUS_CREATED,
    BINDING_STATUS_SCANNED,
    WITHDRAWAL_STATUS_AWAITING_CONFIRMATION,
    WITHDRAWAL_STATUS_CANCELED,
    WITHDRAWAL_STATUS_FAILED,
    WITHDRAWAL_STATUS_NEEDS_ATTENTION,
    WITHDRAWAL_STATUS_PROCESSING,
    WITHDRAWAL_STATUS_SUCCEEDED,
    CommissionAccountSummary,
    CommissionRecord,
    MembershipCommissionStore,
    PayoutBindingAttempt,
    PayoutIdentity,
    WithdrawalRequest,
    _utc_now as commission_utc_now,
)
from backend.system.membership_payment_service import (
    MembershipPaymentPayload,
    MembershipPaymentService,
    MembershipRemotePaymentStatus,
    PAYMENT_PROVIDER_MANUAL_TEST,
    PayoutConfirmationPayload,
    current_wechat_payout_config,
)
from backend.system.membership_store import (
    MembershipOrderCloseResult,
    MembershipCreateOrderResult,
    MembershipOrder,
    MembershipOrderPreview,
    MembershipPaymentConfirmation,
    MembershipPaymentSyncResult,
    MembershipStore,
    MembershipSummary,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _membership_summary_to_dto(item: MembershipSummary) -> dict[str, object]:
    return {
        "userId": item.user_id,
        "currentStatus": item.current_status,
        "currentStartsAt": item.current_starts_at,
        "currentEndsAt": item.current_ends_at,
        "isActive": item.is_active,
        "isFirstOrderEligible": item.is_first_order_eligible,
        "baseMonthlyPriceCent": item.base_monthly_price_cent,
        "firstOrderPriceCent": item.first_order_price_cent,
        "renewalPriceCent": item.renewal_price_cent,
        "currentPriceCent": item.current_price_cent,
        "supportedPaymentProviders": list(item.supported_payment_providers),
    }


def _membership_preview_to_dto(item: MembershipOrderPreview) -> dict[str, object]:
    return {
        "userId": item.user_id,
        "planId": item.plan_id,
        "planName": item.plan_name,
        "orderType": item.order_type,
        "periodDays": item.period_days,
        "listAmountCent": item.list_amount_cent,
        "firstOrderDiscountCent": item.first_order_discount_cent,
        "couponDiscountCent": item.coupon_discount_cent,
        "payableAmountCent": item.payable_amount_cent,
        "couponId": item.coupon_id,
    }


def _membership_order_to_dto(item: MembershipOrder) -> dict[str, object]:
    return {
        "orderId": item.order_id,
        "userId": item.user_id,
        "planId": item.plan_id,
        "planName": item.plan_name,
        "orderType": item.order_type,
        "pricingVersion": item.pricing_version,
        "periodDays": item.period_days,
        "listAmountCent": item.list_amount_cent,
        "firstOrderDiscountCent": item.first_order_discount_cent,
        "couponDiscountCent": item.coupon_discount_cent,
        "payableAmountCent": item.payable_amount_cent,
        "couponId": item.coupon_id,
        "provider": item.provider,
        "providerTradeNo": item.provider_trade_no,
        "status": item.status,
        "clientIp": item.client_ip,
        "clientVersion": item.client_version,
        "createdAt": item.created_at,
        "paidAt": item.paid_at,
        "closedAt": item.closed_at,
        "refundedAt": item.refunded_at,
        "expiredAt": item.expired_at,
        "entitlementId": item.entitlement_id,
        "remark": item.remark,
    }


def _membership_create_order_to_dto(item: MembershipCreateOrderResult) -> dict[str, object]:
    return {
        "order": _membership_order_to_dto(item.order),
        "reusedExistingOrder": item.reused_existing_order,
    }


def _membership_payment_payload_to_dto(item: MembershipPaymentPayload) -> dict[str, object]:
    return {
        "mode": item.mode,
        "provider": item.provider,
        "providerLabel": item.provider_label,
        "instruction": item.instruction,
        "providerTradeNoHint": item.provider_trade_no_hint,
        "expiresAt": item.expires_at,
        "codeUrl": item.code_url,
        "qrImageDataUrl": item.qr_image_data_url,
        "openUrl": item.open_url,
        "pollIntervalSeconds": item.poll_interval_seconds,
        "statusCheckSupported": item.status_check_supported,
    }


def _membership_payment_confirmation_to_dto(item: MembershipPaymentConfirmation) -> dict[str, object]:
    return {
        "order": _membership_order_to_dto(item.order),
        "membership": _membership_summary_to_dto(item.membership),
        "paymentId": item.payment_id,
        "idempotent": item.idempotent,
    }


def _membership_order_close_to_dto(item: MembershipOrderCloseResult) -> dict[str, object]:
    return {
        "order": _membership_order_to_dto(item.order),
        "membership": _membership_summary_to_dto(item.membership),
        "idempotent": item.idempotent,
    }


def _membership_remote_payment_status_to_dto(item: MembershipRemotePaymentStatus) -> dict[str, object]:
    return {
        "provider": item.provider,
        "orderId": item.order_id,
        "providerTradeNo": item.provider_trade_no,
        "remoteStatus": item.remote_status,
        "paidAt": item.paid_at,
        "amountCent": item.amount_cent,
        "payerId": item.payer_id,
    }


def _membership_payment_sync_to_dto(item: MembershipPaymentSyncResult, *, remote_status: MembershipRemotePaymentStatus) -> dict[str, object]:
    payload = {
        "confirmed": item.confirmed,
        "idempotent": item.idempotent,
        "order": _membership_order_to_dto(item.order),
        "membership": _membership_summary_to_dto(item.membership),
        "remote": _membership_remote_payment_status_to_dto(remote_status),
    }
    if item.payment_id:
        payload["paymentId"] = item.payment_id
    return payload


def _invite_binding_to_dto(item: InviteBinding) -> dict[str, object]:
    return {
        "inviteeUserId": item.invitee_user_id,
        "inviterUserId": item.inviter_user_id,
        "inviteCode": item.invite_code_snapshot,
        "status": item.status,
        "boundAt": item.bound_at,
        "rewardedAt": item.rewarded_at,
        "rewardTriggerOrderId": item.reward_trigger_order_id,
        "rewardCouponId": item.reward_coupon_id,
        "discountCouponId": item.discount_coupon_id,
    }


def _invite_summary_to_dto(item: InviteSummary) -> dict[str, object]:
    return {
        "userId": item.user_id,
        "inviteCode": item.invite_code,
        "boundInviterUserId": item.bound_inviter_user_id,
        "boundInviteCode": item.bound_invite_code,
        "bindingStatus": item.binding_status,
        "boundAt": item.bound_at,
        "totalInvitedUsers": item.total_invited_users,
        "rewardedInviteCount": item.rewarded_invite_count,
        "availableCouponCount": item.available_coupon_count,
        "pendingCommissionCent": item.pending_commission_cent,
        "withdrawableCommissionCent": item.withdrawable_commission_cent,
    }


def _invite_referral_to_dto(item: InviteReferralRecord, auth_store: AuthStore) -> dict[str, object]:
    invitee_public_uid = None
    invitee_nickname = None
    try:
        invitee = auth_store.get_user_by_id(item.invitee_user_id)
        invitee_public_uid = invitee.public_uid
        invitee_nickname = invitee.nickname
    except NotFound:
        pass
    return {
        "inviteeUserId": item.invitee_user_id,
        "inviteePublicUid": invitee_public_uid,
        "inviteeNickname": invitee_nickname,
        "status": item.status,
        "boundAt": item.bound_at,
        "rewardedAt": item.rewarded_at,
        "rewardTriggerOrderId": item.reward_trigger_order_id,
        "rewardCouponId": item.reward_coupon_id,
        "discountCouponId": item.discount_coupon_id,
        "commissionAmountCent": item.commission_amount_cent,
    }


def _coupon_to_dto(item: CouponRecord) -> dict[str, object]:
    return {
        "couponId": item.coupon_id,
        "userId": item.user_id,
        "title": item.title,
        "couponType": item.coupon_type,
        "discountRate": item.discount_rate,
        "amountCent": item.amount_cent,
        "minSpendCent": item.min_spend_cent,
        "source": item.source,
        "status": item.status,
        "sourceInviteeUserId": item.source_invitee_user_id,
        "createdAt": item.created_at,
        "expiresAt": item.expires_at,
        "usedAt": item.used_at,
        "usedOrderId": item.used_order_id,
    }


def _commission_account_to_dto(item: CommissionAccountSummary) -> dict[str, object]:
    return {
        "userId": item.user_id,
        "pendingCent": item.pending_cent,
        "withdrawableCent": item.withdrawable_cent,
        "reservedCent": item.reserved_cent,
        "paidOutCent": item.paid_out_cent,
        "canceledCent": item.canceled_cent,
        "updatedAt": item.updated_at,
    }


def _commission_record_to_dto(item: CommissionRecord) -> dict[str, object]:
    return {
        "commissionId": item.commission_id,
        "inviteeUserId": item.invitee_user_id,
        "sourceOrderId": item.source_order_id,
        "sourcePaymentAmountCent": item.source_payment_amount_cent,
        "thresholdAmountCent": item.threshold_amount_cent,
        "commissionAmountCent": item.commission_amount_cent,
        "refundWindowEndsAt": item.refund_window_ends_at,
        "status": item.status,
        "createdAt": item.created_at,
        "settledAt": item.settled_at,
        "canceledAt": item.canceled_at,
        "cancelReason": item.cancel_reason,
        "settlementMode": item.settlement_mode,
        "lastSettlementCheckedAt": item.last_settlement_checked_at,
        "settlementRunId": item.settlement_run_id,
        "settlementFailureReason": item.settlement_failure_reason,
    }


def _mask_wechat_open_id(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= 6:
        return f"{text[:1]}***"
    return f"{text[:7]}***"


def _payout_binding_account_label(auth_store: AuthStore, user_id: str) -> str:
    try:
        user = auth_store.get_user_by_id(user_id)
    except NotFound:
        return "当前 LearningPyramid 账号"
    nickname = str(getattr(user, "nickname", "") or "").strip()
    public_uid = str(getattr(user, "public_uid", "") or "").strip()
    if nickname and public_uid:
        return f"{nickname}（{public_uid}）"
    if nickname:
        return nickname
    if public_uid:
        return public_uid
    return "当前 LearningPyramid 账号"


def _public_origin_from_request(request: Request | None = None) -> str:
    public_origin = (current_http_runtime_config().public_origin or "").rstrip("/")
    if public_origin:
        return public_origin
    if request is None:
        return ""
    return str(request.base_url).rstrip("/")


def _transfer_confirmation_secret() -> str:
    return str(
        os.getenv("LEARNINGPYRAMID_WECHAT_PAY_TRANSFER_CONFIRMATION_SECRET")
        or os.getenv("LEARNINGPYRAMID_MEDIA_ACCESS_TOKEN_SECRET")
        or os.getenv("LEARNINGPYRAMID_TOKEN_ENCRYPTION_KEY")
        or ""
    ).strip()


def _transfer_confirmation_token(item: WithdrawalRequest) -> str:
    secret = _transfer_confirmation_secret()
    if not secret:
        return ""
    message = "|".join(
        (
            item.withdrawal_id,
            item.user_id,
            item.out_bill_no,
            str(item.amount_cent),
            item.created_at,
        )
    )
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def _verify_transfer_confirmation_token(item: WithdrawalRequest, token: str) -> bool:
    expected = _transfer_confirmation_token(item)
    return bool(expected and hmac.compare_digest(expected, str(token or "").strip()))


def _transfer_confirmation_url(item: WithdrawalRequest, request: Request | None = None) -> str | None:
    token = _transfer_confirmation_token(item)
    if item.status != WITHDRAWAL_STATUS_AWAITING_CONFIRMATION or not item.package_info or not token:
        return None
    base = _public_origin_from_request(request)
    path = "/membership/wechat-payout-confirm"
    query = urlencode({"withdrawal": item.withdrawal_id, "token": token})
    return f"{base}{path}?{query}" if base else f"{path}?{query}"


def _withdrawal_can_confirm(item: WithdrawalRequest) -> bool:
    if item.status != WITHDRAWAL_STATUS_AWAITING_CONFIRMATION or not item.package_info:
        return False
    if not item.confirmation_requested_at:
        return True
    try:
        requested_at = datetime.fromisoformat(item.confirmation_requested_at)
    except Exception:
        return True
    if requested_at.tzinfo is None:
        requested_at = requested_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - requested_at <= timedelta(hours=24)


def _withdrawal_to_dto(item: WithdrawalRequest) -> dict[str, object]:
    confirmation = None
    if _withdrawal_can_confirm(item):
        payout_config = current_wechat_payout_config()
        if payout_config.enabled:
            confirmation = _payout_confirmation_to_dto(
                PayoutConfirmationPayload(
                    mode="wechat_jsapi_requestMerchantTransfer",
                    mch_id=payout_config.mch_id,
                    app_id=payout_config.app_id,
                    package_info=item.package_info,
                )
            )
    return {
        "withdrawalId": item.withdrawal_id,
        "userId": item.user_id,
        "amountCent": item.amount_cent,
        "targetType": item.target_type,
        "wechatOpenIdMasked": _mask_wechat_open_id(item.wechat_open_id),
        "identityId": item.identity_id,
        "identityMaskedLabel": item.identity_masked_label or _mask_wechat_open_id(item.wechat_open_id),
        "status": item.status,
        "providerTransferNo": item.provider_transfer_no,
        "outBillNo": item.out_bill_no,
        "transferBillNo": item.transfer_bill_no or item.provider_transfer_no,
        "providerState": item.provider_state,
        "confirmation": confirmation,
        "confirmationUrl": _transfer_confirmation_url(item),
        "failureReason": item.failure_reason,
        "createdAt": item.created_at,
        "reservedAt": item.reserved_at,
        "submittedAt": item.submitted_at,
        "confirmationRequestedAt": item.confirmation_requested_at,
        "completedAt": item.completed_at,
    }


def _payout_confirmation_to_dto(item: PayoutConfirmationPayload | None) -> dict[str, object] | None:
    if item is None:
        return None
    return {
        "mode": item.mode,
        "mchId": item.mch_id,
        "appId": item.app_id,
        "packageInfo": item.package_info,
    }


def _withdrawal_confirmation_attempt_to_dto(item: PayoutBindingAttempt) -> dict[str, object]:
    next_action = "wait_for_scan"
    if item.status == "scanned":
        next_action = "authorize_and_withdraw"
    elif item.status == "bound":
        next_action = "confirm_withdrawal"
    elif item.status in {"failed", "expired", "canceled"}:
        next_action = "retry_withdrawal_confirmation"
    elif item.amount_cent > 0:
        next_action = "scan_to_withdraw"
    return {
        "withdrawalConfirmationAttemptId": item.binding_attempt_id,
        "provider": item.provider,
        "channel": item.channel,
        "status": item.status,
        "amountCent": item.amount_cent,
        "withdrawalId": item.withdrawal_id,
        "state": item.state,
        "desktopReturnUrl": item.desktop_return_url,
        "mobileConfirmationUrl": item.mobile_binding_url,
        "qrCodePayload": item.mobile_binding_url,
        "pollAfterMs": 2000,
        "qrExpiresAt": item.qr_expires_at,
        "scannedAt": item.scanned_at,
        "confirmedAt": item.confirmed_at,
        "nextAction": next_action,
        "createdAt": item.created_at,
        "completedAt": item.completed_at,
        "expiresAt": item.expires_at,
        "failureReason": item.failure_reason,
    }


def _payout_identity_to_dto(item: PayoutIdentity) -> dict[str, object]:
    return {
        "identityId": item.identity_id,
        "provider": item.provider,
        "status": item.status,
        "maskedLabel": item.masked_openid,
        "verifiedAt": item.verified_at,
        "failureReason": item.failure_reason,
    }


def _payout_readiness_to_dto(
    *,
    identity: PayoutIdentity | None,
    latest_attempt: PayoutBindingAttempt | None,
    provider_available: bool = True,
) -> dict[str, object]:
    if not provider_available:
        status = "provider_unavailable"
        next_action = "wait"
    elif identity is not None:
        status = "ready"
        next_action = "withdraw"
    elif latest_attempt is not None and latest_attempt.status in {"created", "scanned", "authorized", "confirmed"}:
        status = "awaiting_withdrawal_confirmation"
        next_action = "wait_for_mobile_confirmation"
    elif latest_attempt is not None and latest_attempt.status in {"failed", "expired", "canceled"}:
        status = "invalid"
        next_action = "retry_withdrawal_confirmation"
    else:
        status = "unbound"
        next_action = "start_withdrawal_confirmation"
    payload = {
        "provider": "wechat_pay",
        "status": status,
        "identityId": None if identity is None else identity.identity_id,
        "maskedLabel": None if identity is None else identity.masked_openid,
        "verifiedAt": None if identity is None else identity.verified_at,
        "nextAction": next_action,
        "latestWithdrawalConfirmationAttempt": None if latest_attempt is None else _withdrawal_confirmation_attempt_to_dto(latest_attempt),
    }
    return payload


def _apply_commission_payout_result(
    *,
    withdrawal: WithdrawalRequest,
    payout,
    membership_commission_store: MembershipCommissionStore,
) -> WithdrawalRequest:
    if payout.remote_status == "succeeded":
        return membership_commission_store.mark_withdrawal_succeeded(
            withdrawal.withdrawal_id,
            provider_transfer_no=payout.provider_transfer_no,
        )
    if payout.remote_status == "failed":
        return membership_commission_store.mark_withdrawal_failed(
            withdrawal.withdrawal_id,
            provider_transfer_no=payout.provider_transfer_no,
            failure_reason=payout.failure_reason or "wechat payout failed",
        )
    if payout.remote_status == WITHDRAWAL_STATUS_AWAITING_CONFIRMATION:
        return membership_commission_store.mark_withdrawal_awaiting_confirmation(
            withdrawal.withdrawal_id,
            transfer_bill_no=payout.provider_transfer_no,
            provider_state=payout.provider_state,
            package_info=payout.package_info or "",
            raw_payload_json=payout.raw_payload_json,
        )
    if payout.remote_status in {WITHDRAWAL_STATUS_CANCELED, WITHDRAWAL_STATUS_NEEDS_ATTENTION}:
        return membership_commission_store.apply_withdrawal_provider_result(
            out_bill_no=withdrawal.out_bill_no,
            provider_state=payout.provider_state,
            mapped_status=payout.remote_status,
            transfer_bill_no=payout.provider_transfer_no,
            amount_cent=payout.amount_cent,
            appid=payout.appid,
            raw_payload_json=payout.raw_payload_json,
            provider_event_id=payout.provider_transfer_no or withdrawal.out_bill_no,
            event_type="create_response",
            failure_reason=payout.failure_reason,
            signature_verified=False,
        )
    return membership_commission_store.mark_withdrawal_processing(
        withdrawal.withdrawal_id,
        provider_transfer_no=payout.provider_transfer_no,
        provider_state=payout.provider_state or WITHDRAWAL_STATUS_PROCESSING,
        raw_payload_json=payout.raw_payload_json,
    )


def _desktop_withdrawal_confirmation_url(return_url: str, *, confirmation_attempt_id: str, state: str) -> str:
    base = str(return_url or "").strip().split("#", 1)[0]
    if "?" in base:
        base = base.split("?", 1)[0]
    base = base.rstrip("/") or "/membership"
    return f"{base}/wechat-payout-confirm?attempt={confirmation_attempt_id}&state={state}"


def _mobile_withdrawal_confirmation_entry_url(return_url: str, *, confirmation_attempt_id: str, state: str) -> str:
    parsed = urlsplit(str(return_url or "").strip())
    if parsed.scheme and parsed.netloc:
        origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")
    else:
        origin = current_http_runtime_config().public_origin.rstrip("/")
    path = "/api/commissions/payout-identity/wechat/withdrawal-confirmation/mobile"
    query = urlencode({"attempt": confirmation_attempt_id, "state": state})
    return f"{origin}{path}?{query}" if origin else f"{path}?{query}"


def _mobile_withdrawal_confirmation_redirect_url(return_url: str, *, confirmation_attempt_id: str, state: str, code: str) -> str:
    base = _desktop_withdrawal_confirmation_url(return_url, confirmation_attempt_id=confirmation_attempt_id, state=state)
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}{urlencode({'code': code})}"


def _resolve_coupon_aware_preview(
    *,
    user_id: str,
    plan_id: str | None,
    coupon_id: str | None,
    membership_store: MembershipStore,
    membership_marketing_store: MembershipMarketingStore,
) -> MembershipOrderPreview:
    base_preview = membership_store.preview_order(user_id, plan_id=plan_id)
    resolved_coupon_id, coupon_discount_cent = membership_marketing_store.resolve_coupon_discount(
        user_id,
        coupon_id=coupon_id,
        order_amount_cent=base_preview.payable_amount_cent,
    )
    return membership_store.preview_order(
        user_id,
        plan_id=plan_id,
        coupon_discount_cent=coupon_discount_cent,
        coupon_id=resolved_coupon_id,
    )


@router.get("/membership/me")
def get_my_membership(request: Request, membership_store: MembershipStore = Depends(get_membership_store)) -> dict:
    user = require_request_auth_user(request)
    return {"ok": True, "data": _membership_summary_to_dto(membership_store.get_membership_summary(user.user_id))}


@router.get("/membership/orders")
def list_my_membership_orders(
    request: Request,
    limit: int = 20,
    membership_store: MembershipStore = Depends(get_membership_store),
) -> dict:
    user = require_request_auth_user(request)
    orders = membership_store.list_orders(user.user_id, limit=limit)
    return {"ok": True, "data": [_membership_order_to_dto(order) for order in orders]}


@router.post("/membership/orders/preview")
def preview_membership_order(
    request: Request,
    req: PreviewMembershipOrderRequest | None = None,
    membership_store: MembershipStore = Depends(get_membership_store),
    membership_marketing_store: MembershipMarketingStore = Depends(get_membership_marketing_store),
) -> dict:
    user = require_request_auth_user(request)
    preview = _resolve_coupon_aware_preview(
        user_id=user.user_id,
        plan_id=None if req is None else req.planId,
        coupon_id=None if req is None else req.couponId,
        membership_store=membership_store,
        membership_marketing_store=membership_marketing_store,
    )
    return {"ok": True, "data": _membership_preview_to_dto(preview)}


@router.post("/membership/orders")
def create_membership_order(
    req: CreateMembershipOrderRequest,
    request: Request,
    membership_store: MembershipStore = Depends(get_membership_store),
    membership_marketing_store: MembershipMarketingStore = Depends(get_membership_marketing_store),
    membership_payment_service: MembershipPaymentService = Depends(get_membership_payment_service),
) -> dict:
    user = require_request_auth_user(request)
    client_ip = request.client.host if request.client and request.client.host else ""
    client_version = str(request.headers.get("User-Agent", "")).strip()
    preview = _resolve_coupon_aware_preview(
        user_id=user.user_id,
        plan_id=req.planId,
        coupon_id=req.couponId,
        membership_store=membership_store,
        membership_marketing_store=membership_marketing_store,
    )
    created = membership_store.create_order(
        user.user_id,
        provider=req.provider,
        client_ip=client_ip,
        client_version=client_version,
        plan_id=preview.plan_id,
        coupon_id=preview.coupon_id,
        coupon_discount_cent=preview.coupon_discount_cent,
    )
    payment_payload = membership_payment_service.create_payment_payload(
        created.order,
        client_ip=client_ip,
        public_origin=current_http_runtime_config().public_origin,
    )
    payload = _membership_create_order_to_dto(created)
    payload["paymentPayload"] = _membership_payment_payload_to_dto(payment_payload)
    return {"ok": True, "data": payload}


@router.post("/payments/membership/callback/{provider}")
def confirm_membership_payment(
    provider: str,
    req: ConfirmMembershipPaymentRequest,
    request: Request,
    membership_store: MembershipStore = Depends(get_membership_store),
) -> dict:
    normalized_provider = str(provider or "").strip().lower()
    if normalized_provider != PAYMENT_PROVIDER_MANUAL_TEST:
        raise PreconditionFailure("membership payment callback is only available for manual_test")
    user = require_request_auth_user(request)
    confirmed = membership_store.confirm_payment(
        user.user_id,
        provider=normalized_provider,
        order_id=req.orderId,
        provider_trade_no=req.providerTradeNo,
    )
    return {"ok": True, "data": _membership_payment_confirmation_to_dto(confirmed)}


@router.post("/membership/orders/{orderId}/sync-payment")
def sync_membership_payment_status(
    orderId: str,
    request: Request,
    membership_store: MembershipStore = Depends(get_membership_store),
    membership_payment_service: MembershipPaymentService = Depends(get_membership_payment_service),
) -> dict:
    user = require_request_auth_user(request)
    order = membership_store.get_order_for_user(user.user_id, orderId)
    remote_status = membership_payment_service.query_payment_status(order)
    synced = membership_store.sync_provider_payment_status(order_id=orderId, remote_status=remote_status)
    return {"ok": True, "data": _membership_payment_sync_to_dto(synced, remote_status=remote_status)}


@router.post("/membership/orders/{orderId}/close")
def close_membership_order(
    orderId: str,
    request: Request,
    membership_store: MembershipStore = Depends(get_membership_store),
) -> dict:
    user = require_request_auth_user(request)
    closed = membership_store.close_order_for_user(
        user.user_id,
        orderId,
        reason="user closed pending membership order",
    )
    return {"ok": True, "data": _membership_order_close_to_dto(closed)}


@router.post("/payments/wechat/notify")
async def receive_wechat_payment_notification(
    request: Request,
    membership_store: MembershipStore = Depends(get_membership_store),
    membership_payment_service: MembershipPaymentService = Depends(get_membership_payment_service),
) -> PlainTextResponse:
    body_text = (await request.body()).decode("utf-8")
    try:
        remote_status = membership_payment_service.parse_payment_notification(
            "wechat_native",
            headers=request.headers,
            body_text=body_text,
        )
    except Exception:
        logger.exception("failed to parse wechat payment notification")
        raise
    if remote_status.remote_status == "paid":
        membership_store.confirm_provider_payment(
            order_id=remote_status.order_id,
            provider=remote_status.provider,
            provider_trade_no=remote_status.provider_trade_no,
            amount_cent=remote_status.amount_cent,
            paid_at=remote_status.paid_at,
            payer_id=remote_status.payer_id,
            callback_payload_json=remote_status.raw_payload_json,
        )
    return PlainTextResponse("success")


@router.post("/payments/wechat/refund-notify")
async def receive_wechat_refund_notification(
    request: Request,
    membership_store: MembershipStore = Depends(get_membership_store),
    membership_payment_service: MembershipPaymentService = Depends(get_membership_payment_service),
) -> PlainTextResponse:
    body_text = (await request.body()).decode("utf-8")
    try:
        remote_status = membership_payment_service.parse_refund_notification(
            "wechat_native",
            headers=request.headers,
            body_text=body_text,
        )
    except Exception:
        logger.exception("failed to parse wechat refund notification")
        raise
    membership_store.sync_provider_refund(
        order_id=remote_status.order_id,
        provider=remote_status.provider,
        refund_out_refund_no=remote_status.refund_out_trade_no,
        remote_status=remote_status.remote_status,
        refund_payload_json=remote_status.raw_payload_json,
        refunded_at=remote_status.refunded_at,
        reason="wechat refund notification",
    )
    return PlainTextResponse("success")


@router.post("/invites/bind")
def bind_invite_code(
    req: BindInviteCodeRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_marketing_store: MembershipMarketingStore = Depends(get_membership_marketing_store),
) -> dict:
    user = require_request_auth_user(request)
    inviter = auth_store.get_user_by_public_uid(req.inviteCode)
    binding = membership_marketing_store.bind_invite_code(
        user.user_id,
        inviter_user_id=inviter.user_id,
        invite_code_snapshot=inviter.public_uid,
    )
    auth_store.create_friendship(user.user_id, inviter.user_id)
    return {"ok": True, "data": _invite_binding_to_dto(binding)}


@router.get("/invites/me")
def get_my_invite_summary(
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_marketing_store: MembershipMarketingStore = Depends(get_membership_marketing_store),
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
) -> dict:
    user = require_request_auth_user(request)
    summary = membership_marketing_store.get_invite_summary(user.user_id, invite_code=user.public_uid)
    recent_invites = membership_marketing_store.list_recent_invites(user.user_id, limit=10)
    payload = _invite_summary_to_dto(summary)
    account = membership_commission_store.get_user_account(user.user_id)
    payload["pendingCommissionCent"] = account.pending_cent
    payload["withdrawableCommissionCent"] = account.withdrawable_cent
    payload["recentInvites"] = [_invite_referral_to_dto(item, auth_store) for item in recent_invites]
    return {"ok": True, "data": payload}


@router.get("/coupons/me")
def list_my_coupons(
    request: Request,
    limit: int = 20,
    membership_marketing_store: MembershipMarketingStore = Depends(get_membership_marketing_store),
) -> dict:
    user = require_request_auth_user(request)
    coupons = membership_marketing_store.list_coupons(user.user_id, limit=limit)
    return {"ok": True, "data": [_coupon_to_dto(item) for item in coupons]}


@router.get("/commissions/me")
def get_my_commissions(
    request: Request,
    limit: int = 20,
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
) -> dict:
    user = require_request_auth_user(request)
    account = membership_commission_store.get_user_account(user.user_id)
    recent = membership_commission_store.list_user_commissions(user.user_id, limit=limit)
    identity = membership_commission_store.get_active_payout_identity(user.user_id)
    latest_attempt = membership_commission_store.get_latest_payout_binding_attempt(user.user_id)
    return {
        "ok": True,
        "data": {
            "account": _commission_account_to_dto(account),
            "payoutReadiness": _payout_readiness_to_dto(identity=identity, latest_attempt=latest_attempt),
            "recentCommissions": [_commission_record_to_dto(item) for item in recent],
        },
    }


@router.get("/commissions/payout-identity")
def get_my_payout_identity(
    request: Request,
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
) -> dict:
    user = require_request_auth_user(request)
    identity = membership_commission_store.get_active_payout_identity(user.user_id)
    latest_attempt = membership_commission_store.get_latest_payout_binding_attempt(user.user_id)
    return {"ok": True, "data": _payout_readiness_to_dto(identity=identity, latest_attempt=latest_attempt)}


@router.post("/commissions/payout-identity/wechat/withdrawal-confirmation-attempts")
def start_my_wechat_withdrawal_confirmation_attempt(
    req: StartWeChatWithdrawalConfirmationAttemptRequest,
    request: Request,
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
    membership_payment_service: MembershipPaymentService = Depends(get_membership_payment_service),
) -> dict:
    user = require_request_auth_user(request)
    now = commission_utc_now()
    state = uuid.uuid4().hex
    payout_config = membership_payment_service.current_wechat_payout_config()
    attempt = membership_commission_store.create_payout_binding_attempt(
        user.user_id,
        channel=req.channel,
        state=state,
        expires_at=(now + timedelta(minutes=payout_config.binding_qr_ttl_minutes)).isoformat(),
        amount_cent=req.amountCent,
        desktop_return_url=req.returnUrl,
    )
    mobile_binding_url = _mobile_withdrawal_confirmation_entry_url(req.returnUrl, confirmation_attempt_id=attempt.binding_attempt_id, state=attempt.state)
    attempt = membership_commission_store.update_payout_binding_attempt_urls(
        attempt.binding_attempt_id,
        desktop_return_url=req.returnUrl,
        mobile_binding_url=mobile_binding_url,
    )
    authorization_url = membership_payment_service.build_wechat_payout_binding_authorization_url(
        state=attempt.state,
        return_url=attempt.mobile_binding_url or req.returnUrl,
        channel=attempt.channel,
    )
    payload = _withdrawal_confirmation_attempt_to_dto(attempt)
    payload["authorizationUrl"] = authorization_url
    return {"ok": True, "data": payload}


@router.get("/commissions/payout-identity/wechat/withdrawal-confirmation-attempts/{withdrawalConfirmationAttemptId}")
def poll_my_wechat_withdrawal_confirmation_attempt(
    withdrawalConfirmationAttemptId: str,
    request: Request,
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
) -> dict:
    user = require_request_auth_user(request)
    attempt = membership_commission_store.get_payout_binding_attempt(withdrawalConfirmationAttemptId)
    if attempt is None:
        raise NotFound("withdrawal confirmation attempt")
    if attempt.user_id != user.user_id:
        raise NotFound("withdrawal confirmation attempt")
    identity = membership_commission_store.get_active_payout_identity(user.user_id)
    payload = _withdrawal_confirmation_attempt_to_dto(attempt)
    if identity is not None and identity.latest_binding_attempt_id == attempt.binding_attempt_id:
        payload["identityId"] = identity.identity_id
        payload["maskedLabel"] = identity.masked_openid
        payload["verifiedAt"] = identity.verified_at
        if not attempt.withdrawal_id:
            payload["nextAction"] = "withdraw"
    if attempt.withdrawal_id:
        withdrawal = membership_commission_store.get_withdrawal_request(attempt.withdrawal_id)
        if withdrawal is not None:
            payload["withdrawal"] = _withdrawal_to_dto(withdrawal)
    return {"ok": True, "data": payload}


@router.get("/commissions/payout-identity/wechat/withdrawal-confirmation/mobile")
def open_wechat_withdrawal_confirmation_mobile_entry(
    attempt: str,
    state: str,
    code: str | None = None,
    response: str | None = None,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
    membership_payment_service: MembershipPaymentService = Depends(get_membership_payment_service),
):
    scanned = membership_commission_store.mark_payout_binding_attempt_scanned(attempt, state=state)
    account_label = _payout_binding_account_label(auth_store, scanned.user_id)
    wants_json = str(response or "").strip().lower() == "json"
    if code:
        if wants_json:
            payload = _withdrawal_confirmation_attempt_to_dto(scanned)
            payload["learningPyramidAccountLabel"] = account_label
            payload["learningPyramidUserId"] = scanned.user_id
            payload["confirmedLearningPyramidUserId"] = scanned.user_id
            return {"ok": True, "data": payload}
        return RedirectResponse(
            _mobile_withdrawal_confirmation_redirect_url(
                scanned.desktop_return_url,
                confirmation_attempt_id=scanned.binding_attempt_id,
                state=scanned.state,
                code=code,
            ),
            status_code=302,
        )
    authorization_url = membership_payment_service.build_wechat_payout_binding_authorization_url(
        state=scanned.state,
        return_url=scanned.mobile_binding_url or scanned.desktop_return_url,
        channel=scanned.channel,
    )
    if not wants_json and authorization_url.lower().startswith(("http://", "https://")):
        return RedirectResponse(authorization_url, status_code=302)
    payload = _withdrawal_confirmation_attempt_to_dto(scanned)
    payload["learningPyramidAccountLabel"] = account_label
    payload["learningPyramidUserId"] = scanned.user_id
    payload["confirmedLearningPyramidUserId"] = scanned.user_id
    payload["authorizationUrl"] = authorization_url
    return {"ok": True, "data": payload}


@router.post("/commissions/payout-identity/wechat/withdrawal-confirmation/complete")
def complete_my_wechat_withdrawal_confirmation_attempt(
    req: CompleteWeChatWithdrawalConfirmationAttemptRequest,
    request: Request,
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
    membership_payment_service: MembershipPaymentService = Depends(get_membership_payment_service),
) -> dict:
    attempt = membership_commission_store.get_payout_binding_attempt(req.withdrawalConfirmationAttemptId)
    if attempt is None:
        raise NotFound("withdrawal confirmation attempt")
    if attempt.amount_cent <= 0:
        raise PreconditionFailure("wechat payout confirmation requires a positive withdrawal amount")

    confirmed_user_id = str(req.confirmedLearningPyramidUserId or "").strip()
    if str(req.state or "") != attempt.state:
        raise PreconditionFailure("withdrawal confirmation state is invalid")
    if confirmed_user_id and confirmed_user_id != attempt.user_id:
        raise PreconditionFailure("confirmed account does not match withdrawal confirmation attempt")
    if not confirmed_user_id:
        user = require_request_auth_user(request)
        user_id = user.user_id
        if attempt.user_id != user_id:
            raise NotFound("withdrawal confirmation attempt")
    else:
        user_id = attempt.user_id

    if attempt.status == BINDING_STATUS_BOUND:
        if not attempt.identity_id:
            raise PreconditionFailure("withdrawal confirmation attempt has already been consumed")
        identity = membership_commission_store.get_payout_identity(attempt.identity_id)
        if identity is None or identity.user_id != attempt.user_id:
            raise NotFound("payout identity")
        if attempt.withdrawal_id:
            withdrawal = membership_commission_store.get_withdrawal_request(attempt.withdrawal_id)
            return {
                "ok": True,
                "data": {
                    "identity": _payout_identity_to_dto(identity),
                    "withdrawal": None if withdrawal is None else _withdrawal_to_dto(withdrawal),
                },
            }
        raise PreconditionFailure("wechat payout confirmation requires a withdrawal")

    if attempt.status not in {
        BINDING_STATUS_CREATED,
        BINDING_STATUS_SCANNED,
        BINDING_STATUS_AUTHORIZED,
        BINDING_STATUS_CONFIRMED,
    }:
        raise PreconditionFailure("withdrawal confirmation attempt has already been consumed")
    if attempt.channel == "desktop_qr_official_account_h5":
        if not confirmed_user_id:
            raise PreconditionFailure("confirmed account is required for desktop QR withdrawal confirmation")
        if attempt.status == BINDING_STATUS_CREATED:
            raise PreconditionFailure("withdrawal confirmation attempt must be scanned before confirmation")

    openid, appid = membership_payment_service.resolve_wechat_payout_openid(
        authorization_code=req.authorizationCode,
        channel=attempt.channel,
    )
    identity = membership_commission_store.complete_payout_binding_attempt(
        user_id,
        binding_attempt_id=req.withdrawalConfirmationAttemptId,
        authorization_code=req.authorizationCode,
        state=req.state,
        openid=openid,
        appid=appid,
        confirmed_learning_pyramid_user_id=req.confirmedLearningPyramidUserId,
    )
    withdrawal = membership_commission_store.create_withdrawal_request(
        user_id,
        amount_cent=attempt.amount_cent,
        identity_id=identity.identity_id,
    )
    try:
        payout = membership_payment_service.request_commission_payout(withdrawal)
    except Exception as exc:
        membership_commission_store.mark_withdrawal_failed(withdrawal.withdrawal_id, failure_reason=str(exc))
        raise
    withdrawal = _apply_commission_payout_result(
        withdrawal=withdrawal,
        payout=payout,
        membership_commission_store=membership_commission_store,
    )
    membership_commission_store.attach_withdrawal_to_binding_attempt(
        req.withdrawalConfirmationAttemptId,
        withdrawal_id=withdrawal.withdrawal_id,
    )
    withdrawal_payload = _withdrawal_to_dto(withdrawal)
    withdrawal_payload["confirmation"] = _payout_confirmation_to_dto(payout.confirmation)
    return {
        "ok": True,
        "data": {
            "identity": _payout_identity_to_dto(identity),
            "withdrawal": withdrawal_payload,
        },
    }


@router.post("/commissions/withdrawals")
def request_my_commission_withdrawal(
    req: CreateCommissionWithdrawalRequest,
    request: Request,
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
    membership_payment_service: MembershipPaymentService = Depends(get_membership_payment_service),
) -> dict:
    user = require_request_auth_user(request)
    withdrawal = membership_commission_store.create_withdrawal_request(
        user.user_id,
        amount_cent=req.amountCent,
    )
    try:
        payout = membership_payment_service.request_commission_payout(withdrawal)
    except Exception as exc:
        membership_commission_store.mark_withdrawal_failed(withdrawal.withdrawal_id, failure_reason=str(exc))
        raise
    withdrawal = _apply_commission_payout_result(
        withdrawal=withdrawal,
        payout=payout,
        membership_commission_store=membership_commission_store,
    )
    payload = _withdrawal_to_dto(withdrawal)
    payload["confirmation"] = _payout_confirmation_to_dto(payout.confirmation)
    return {"ok": True, "data": payload}


@router.get("/commissions/withdrawals")
def list_my_commission_withdrawals(
    request: Request,
    limit: int = 20,
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
) -> dict:
    user = require_request_auth_user(request)
    items = membership_commission_store.list_user_withdrawals(user.user_id, limit=limit)
    return {"ok": True, "data": [_withdrawal_to_dto(item) for item in items]}


@router.get("/commissions/withdrawals/{withdrawal_id}/wechat-confirmation")
def get_wechat_transfer_confirmation(
    withdrawal_id: str,
    token: str,
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
) -> dict:
    withdrawal = membership_commission_store.get_withdrawal_request(withdrawal_id)
    if withdrawal is None or not _verify_transfer_confirmation_token(withdrawal, token):
        raise NotFound("commission withdrawal")
    if not _withdrawal_can_confirm(withdrawal):
        raise PreconditionFailure("wechat transfer confirmation is unavailable")
    payload = _withdrawal_to_dto(withdrawal)
    return {
        "ok": True,
        "data": {
            "withdrawalId": payload["withdrawalId"],
            "amountCent": payload["amountCent"],
            "identityMaskedLabel": payload["identityMaskedLabel"],
            "status": payload["status"],
            "providerState": payload["providerState"],
            "confirmation": payload["confirmation"],
        },
    }


@router.post("/commissions/withdrawals/{withdrawal_id}/wechat-confirmation/started")
def mark_wechat_transfer_confirmation_started(
    withdrawal_id: str,
    token: str,
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
) -> dict:
    withdrawal = membership_commission_store.get_withdrawal_request(withdrawal_id)
    if withdrawal is None or not _verify_transfer_confirmation_token(withdrawal, token):
        raise NotFound("commission withdrawal")
    if withdrawal.status == WITHDRAWAL_STATUS_AWAITING_CONFIRMATION:
        if not _withdrawal_can_confirm(withdrawal):
            raise PreconditionFailure("wechat transfer confirmation is unavailable")
        withdrawal = membership_commission_store.mark_withdrawal_processing(
            withdrawal.withdrawal_id,
            provider_transfer_no=withdrawal.provider_transfer_no or withdrawal.transfer_bill_no,
            provider_state="USER_CONFIRMED",
            raw_payload_json='{"source":"wechat_jsapi_requestMerchantTransfer"}',
        )
    return {"ok": True, "data": _withdrawal_to_dto(withdrawal)}


@router.post("/payments/wechat/transfer-notify")
async def receive_wechat_transfer_notification(
    request: Request,
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
    membership_payment_service: MembershipPaymentService = Depends(get_membership_payment_service),
) -> PlainTextResponse:
    body_text = (await request.body()).decode("utf-8")
    try:
        remote_status = membership_payment_service.parse_transfer_notification(
            headers=request.headers,
            body_text=body_text,
        )
    except Exception:
        logger.exception("failed to parse wechat transfer notification")
        raise
    out_bill_no = remote_status.out_bill_no
    if out_bill_no:
        membership_commission_store.apply_withdrawal_provider_result(
            out_bill_no=out_bill_no,
            provider_state=remote_status.provider_state,
            mapped_status=remote_status.remote_status,
            transfer_bill_no=remote_status.provider_transfer_no,
            amount_cent=remote_status.amount_cent,
            appid=remote_status.appid,
            raw_payload_json=remote_status.raw_payload_json,
            provider_event_id=remote_status.provider_transfer_no or out_bill_no,
            event_type="notify",
            failure_reason=remote_status.failure_reason,
            signature_verified=True,
        )
    return PlainTextResponse("success")
