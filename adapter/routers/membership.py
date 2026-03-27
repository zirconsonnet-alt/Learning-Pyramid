from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from adapter.auth import require_request_auth_user
from adapter.deps import get_auth_store, get_membership_marketing_store, get_membership_payment_service, get_membership_store
from adapter.schemas import (
    BindInviteCodeRequest,
    ConfirmMembershipPaymentRequest,
    CreateMembershipOrderRequest,
    PreviewMembershipOrderRequest,
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
from backend.system.membership_payment_service import (
    MembershipPaymentPayload,
    MembershipPaymentService,
    MembershipRemotePaymentStatus,
    PAYMENT_PROVIDER_MANUAL_TEST,
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
    }


def _coupon_to_dto(item: CouponRecord) -> dict[str, object]:
    return {
        "couponId": item.coupon_id,
        "userId": item.user_id,
        "title": item.title,
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


def _resolve_coupon_aware_preview(
    *,
    user_id: str,
    coupon_id: str | None,
    membership_store: MembershipStore,
    membership_marketing_store: MembershipMarketingStore,
) -> MembershipOrderPreview:
    base_preview = membership_store.preview_order(user_id)
    resolved_coupon_id, coupon_discount_cent = membership_marketing_store.resolve_coupon_discount(
        user_id,
        coupon_id=coupon_id,
        order_amount_cent=base_preview.payable_amount_cent,
    )
    return membership_store.preview_order(
        user_id,
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
        coupon_id=req.couponId,
        membership_store=membership_store,
        membership_marketing_store=membership_marketing_store,
    )
    created = membership_store.create_order(
        user.user_id,
        provider=req.provider,
        client_ip=client_ip,
        client_version=client_version,
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
    remote_status = membership_payment_service.parse_payment_notification(
        "wechat_native",
        headers=request.headers,
        body_text=body_text,
    )
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
    remote_status = membership_payment_service.parse_refund_notification(
        "wechat_native",
        headers=request.headers,
        body_text=body_text,
    )
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
    return {"ok": True, "data": _invite_binding_to_dto(binding)}


@router.get("/invites/me")
def get_my_invite_summary(
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_marketing_store: MembershipMarketingStore = Depends(get_membership_marketing_store),
) -> dict:
    user = require_request_auth_user(request)
    summary = membership_marketing_store.get_invite_summary(user.user_id, invite_code=user.public_uid)
    recent_invites = membership_marketing_store.list_recent_invites(user.user_id, limit=10)
    payload = _invite_summary_to_dto(summary)
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
