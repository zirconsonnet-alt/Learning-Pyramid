from fastapi import APIRouter, Depends, Request

from adapter.auth import require_admin_user, require_super_admin_user
from adapter.deps import get_auth_store, get_membership_commission_store, get_membership_marketing_store, get_membership_payment_service, get_membership_store
from adapter.schemas import (
    AdminGrantMembershipMonthsRequest,
    AdminGrantMembershipCouponRequest,
    AdminRefundMembershipOrderRequest,
    AdminResolveCommissionWithdrawalRequest,
    AdminVoidMembershipCouponRequest,
    SyncCommissionWithdrawalRequest,
    UpdateUserRoleRequest,
    UpdateUserStatusRequest,
)
from backend.models.errors import NotFound, PreconditionFailure
from backend.system.http_runtime_config import current_http_runtime_config
from backend.system.auth_store import (
    AdminActionLog,
    AdminUser,
    AuthStore,
)
from backend.system.membership_marketing_store import (
    CouponRecord,
    InviteBinding,
    MembershipMarketingAdminOverview,
    MembershipMarketingStore,
)
from backend.system.membership_commission_store import (
    WITHDRAWAL_STATUS_AWAITING_CONFIRMATION,
    WITHDRAWAL_STATUS_CANCELED,
    WITHDRAWAL_STATUS_FAILED,
    WITHDRAWAL_STATUS_NEEDS_ATTENTION,
    WITHDRAWAL_STATUS_PROCESSING,
    WITHDRAWAL_STATUS_SUCCEEDED,
    CommissionAdminOverview,
    CommissionRecord,
    CommissionSettlementResult,
    MembershipCommissionStore,
    PayoutIdentity,
    PayoutProviderEvent,
    ReconciliationWarning,
    WithdrawalRequest,
)
from backend.system.membership_payment_service import MembershipPaymentService, MembershipRemotePaymentStatus
from backend.system.membership_store import (
    MembershipAdminOverview,
    MembershipGrantResult,
    MembershipOrderCloseResult,
    MembershipOrder,
    MembershipPaymentRecord,
    MembershipPaymentSyncResult,
    MembershipRefundResult,
    MembershipStore,
    MembershipSummary,
)

router = APIRouter()


def _admin_user_to_dto(user: AdminUser) -> dict[str, object]:
    return {
        "userId": user.user_id,
        "email": user.email,
        "createdAt": user.created_at,
        "publicUid": user.public_uid,
        "nickname": user.nickname,
        "bio": user.bio,
        "avatarUrl": None if not user.avatar_key else f"/api/profile/avatar/{user.user_id}?v={user.updated_at}",
        "status": user.status,
        "updatedAt": user.updated_at,
        "roles": list(user.roles),
    }


def _auth_user_to_admin_dto(user_id: str, auth_store: AuthStore) -> dict[str, object]:
    user = auth_store.get_user_by_id(user_id)
    return {
        "userId": user.user_id,
        "email": user.email,
        "createdAt": user.created_at,
        "publicUid": user.public_uid,
        "nickname": user.nickname,
        "bio": user.bio,
        "avatarUrl": None if not user.avatar_key else f"/api/profile/avatar/{user.user_id}?v={user.updated_at}",
        "status": user.status,
        "updatedAt": user.updated_at,
        "roles": list(auth_store.list_user_roles(user.user_id)),
    }


def _admin_action_log_to_dto(item: AdminActionLog) -> dict[str, object]:
    return {
        "logId": item.log_id,
        "actorUserId": item.actor_user_id,
        "actorPublicUid": item.actor_public_uid,
        "actorNickname": item.actor_nickname,
        "actorAvatarUrl": None if not item.actor_avatar_key else f"/api/profile/avatar/{item.actor_user_id}",
        "actionType": item.action_type,
        "targetKind": item.target_kind,
        "targetId": item.target_id,
        "summary": item.summary,
        "createdAt": item.created_at,
    }


def _admin_user_ref_to_dto(user_id: str, auth_store: AuthStore) -> dict[str, object]:
    try:
        user = auth_store.get_user_by_id(user_id)
        return {
            "userId": user.user_id,
            "email": user.email,
            "publicUid": user.public_uid,
            "nickname": user.nickname,
            "status": user.status,
        }
    except NotFound:
        return {
            "userId": str(user_id),
            "email": None,
            "publicUid": None,
            "nickname": None,
            "status": "missing",
        }


def _admin_membership_order_to_dto(order: MembershipOrder, auth_store: AuthStore) -> dict[str, object]:
    return {
        "orderId": order.order_id,
        "user": _admin_user_ref_to_dto(order.user_id, auth_store),
        "planId": order.plan_id,
        "planName": order.plan_name,
        "orderType": order.order_type,
        "pricingVersion": order.pricing_version,
        "periodDays": order.period_days,
        "listAmountCent": order.list_amount_cent,
        "firstOrderDiscountCent": order.first_order_discount_cent,
        "couponDiscountCent": order.coupon_discount_cent,
        "payableAmountCent": order.payable_amount_cent,
        "couponId": order.coupon_id,
        "provider": order.provider,
        "providerTradeNo": order.provider_trade_no,
        "status": order.status,
        "clientIp": order.client_ip,
        "clientVersion": order.client_version,
        "createdAt": order.created_at,
        "paidAt": order.paid_at,
        "closedAt": order.closed_at,
        "refundedAt": order.refunded_at,
        "expiredAt": order.expired_at,
        "entitlementId": order.entitlement_id,
        "remark": order.remark,
    }


def _admin_membership_summary_to_dto(item: MembershipSummary, auth_store: AuthStore) -> dict[str, object]:
    user_ref = _admin_user_ref_to_dto(item.user_id, auth_store)
    return {
        "user": user_ref,
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


def _admin_membership_grant_to_dto(item: MembershipGrantResult, auth_store: AuthStore) -> dict[str, object]:
    return {
        "user": _admin_user_ref_to_dto(item.user_id, auth_store),
        "userId": item.user_id,
        "entitlementId": item.entitlement_id,
        "sourceRefId": item.source_ref_id,
        "months": item.months,
        "grantedDays": item.granted_days,
        "startAt": item.start_at,
        "endAt": item.end_at,
        "membership": _admin_membership_summary_to_dto(item.membership, auth_store),
    }


def _admin_membership_invite_to_dto(
    binding: InviteBinding,
    auth_store: AuthStore,
    membership_commission_store: MembershipCommissionStore | None = None,
) -> dict[str, object]:
    commission = None
    if membership_commission_store is not None and binding.reward_trigger_order_id:
        commission = membership_commission_store.get_commission_for_order(binding.reward_trigger_order_id)
    payload = {
        "invitee": _admin_user_ref_to_dto(binding.invitee_user_id, auth_store),
        "inviter": _admin_user_ref_to_dto(binding.inviter_user_id, auth_store),
        "inviteCode": binding.invite_code_snapshot,
        "status": binding.status,
        "boundAt": binding.bound_at,
        "rewardedAt": binding.rewarded_at,
        "rewardTriggerOrderId": binding.reward_trigger_order_id,
        "rewardCouponId": binding.reward_coupon_id,
        "discountCouponId": binding.discount_coupon_id,
    }
    if commission is not None:
        payload["commissionId"] = commission.commission_id
        payload["commissionAmountCent"] = commission.commission_amount_cent
        payload["commissionStatus"] = commission.status
        payload["refundWindowEndsAt"] = commission.refund_window_ends_at
    return payload


def _admin_coupon_to_dto(coupon: CouponRecord, auth_store: AuthStore) -> dict[str, object]:
    return {
        "couponId": coupon.coupon_id,
        "user": _admin_user_ref_to_dto(coupon.user_id, auth_store),
        "title": coupon.title,
        "couponType": coupon.coupon_type,
        "discountRate": coupon.discount_rate,
        "amountCent": coupon.amount_cent,
        "minSpendCent": coupon.min_spend_cent,
        "source": coupon.source,
        "status": coupon.status,
        "sourceInvitee": None if coupon.source_invitee_user_id is None else _admin_user_ref_to_dto(coupon.source_invitee_user_id, auth_store),
        "createdAt": coupon.created_at,
        "expiresAt": coupon.expires_at,
        "usedAt": coupon.used_at,
        "usedOrderId": coupon.used_order_id,
    }


def _admin_membership_payment_to_dto(payment: MembershipPaymentRecord) -> dict[str, object]:
    payment_callback_payload = str(payment.callback_payload_json or "").strip() or None
    refund_callback_payload = str(payment.refund_callback_payload_json or "").strip() or None
    provider_trade_no = str(payment.provider_trade_no or "").strip() or None
    provider_buyer_id = str(payment.provider_buyer_id or "").strip() or None
    return {
        "paymentId": payment.payment_id,
        "orderId": payment.order_id,
        "provider": payment.provider,
        "providerTradeNo": provider_trade_no,
        "providerBuyerId": provider_buyer_id,
        "amountCent": payment.amount_cent,
        "status": payment.status,
        "createdAt": payment.created_at,
        "confirmedAt": payment.confirmed_at,
        "refundOutRefundNo": payment.refund_out_refund_no,
        "refundRequestedAt": payment.refund_requested_at,
        "refundedAt": payment.refunded_at,
        "hasPaymentCallbackPayload": payment_callback_payload is not None,
        "paymentCallbackPayloadJson": payment_callback_payload,
        "hasRefundCallbackPayload": refund_callback_payload is not None,
        "refundCallbackPayloadJson": refund_callback_payload,
    }


def _admin_membership_order_operations_to_dto(
    order: MembershipOrder,
    *,
    payment: MembershipPaymentRecord | None,
) -> dict[str, object]:
    return {
        "hasPaymentRecord": payment is not None,
        "canSyncPayment": order.provider == "wechat_native" and order.status == "pending",
        "canCloseOrder": order.status == "pending",
        "canRequestRefund": order.status == "paid",
        "canSyncRefund": order.provider == "wechat_native" and order.status == "refund_pending",
    }


def _admin_membership_order_detail_to_dto(
    *,
    order: MembershipOrder,
    membership: MembershipSummary,
    payment: MembershipPaymentRecord | None,
    auth_store: AuthStore,
    membership_marketing_store: MembershipMarketingStore,
    membership_commission_store: MembershipCommissionStore,
) -> dict[str, object]:
    binding = membership_marketing_store.get_invite_binding(order.user_id)
    coupon = None if order.coupon_id is None else membership_marketing_store.get_coupon(order.coupon_id)
    reward_coupon = None
    if binding is not None and binding.reward_coupon_id:
        reward_coupon = membership_marketing_store.get_coupon(binding.reward_coupon_id)
    discount_coupon = None
    if binding is not None and binding.discount_coupon_id:
        discount_coupon = membership_marketing_store.get_coupon(binding.discount_coupon_id)
    commission = membership_commission_store.get_commission_for_order(order.order_id)
    reward_triggered_by_this_order = binding is not None and binding.reward_trigger_order_id == order.order_id and reward_coupon is not None
    return {
        "order": _admin_membership_order_to_dto(order, auth_store),
        "membership": _admin_membership_summary_to_dto(membership, auth_store),
        "payment": None if payment is None else _admin_membership_payment_to_dto(payment),
        "coupon": None if coupon is None else _admin_coupon_to_dto(coupon, auth_store),
        "invite": None
        if binding is None
        else {
            "binding": _admin_membership_invite_to_dto(binding, auth_store, membership_commission_store),
            "rewardTriggeredByThisOrder": reward_triggered_by_this_order,
            "rewardCoupon": None if reward_coupon is None else _admin_coupon_to_dto(reward_coupon, auth_store),
            "discountCoupon": None if discount_coupon is None else _admin_coupon_to_dto(discount_coupon, auth_store),
            "commission": None
            if commission is None
            else {
                "commissionId": commission.commission_id,
                "commissionAmountCent": commission.commission_amount_cent,
                "status": commission.status,
                "refundWindowEndsAt": commission.refund_window_ends_at,
            },
        },
        "operations": _admin_membership_order_operations_to_dto(order, payment=payment),
    }


def _admin_membership_refund_to_dto(item: MembershipRefundResult, auth_store: AuthStore) -> dict[str, object]:
    return {
        "order": _admin_membership_order_to_dto(item.order, auth_store),
        "membership": _admin_membership_summary_to_dto(item.membership, auth_store),
        "idempotent": item.idempotent,
        "restoredCouponId": item.restored_coupon_id,
        "restoredCouponStatus": item.restored_coupon_status,
        "revokedRewardCouponId": item.revoked_reward_coupon_id,
        "completed": item.completed,
        "refundRequestSubmitted": item.refund_request_submitted,
        "remoteStatus": item.remote_status,
        "providerRefundNo": item.provider_refund_no,
    }


def _admin_commission_to_dto(item: CommissionRecord, auth_store: AuthStore) -> dict[str, object]:
    return {
        "commissionId": item.commission_id,
        "inviter": _admin_user_ref_to_dto(item.inviter_user_id, auth_store),
        "invitee": _admin_user_ref_to_dto(item.invitee_user_id, auth_store),
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


def _admin_withdrawal_to_dto(item: WithdrawalRequest, auth_store: AuthStore) -> dict[str, object]:
    return {
        "withdrawalId": item.withdrawal_id,
        "user": _admin_user_ref_to_dto(item.user_id, auth_store),
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
        "failureReason": item.failure_reason,
        "createdAt": item.created_at,
        "reservedAt": item.reserved_at,
        "submittedAt": item.submitted_at,
        "confirmationRequestedAt": item.confirmation_requested_at,
        "completedAt": item.completed_at,
    }


def _admin_payout_identity_to_dto(item: PayoutIdentity, auth_store: AuthStore) -> dict[str, object]:
    return {
        "identityId": item.identity_id,
        "user": _admin_user_ref_to_dto(item.user_id, auth_store),
        "userId": item.user_id,
        "provider": item.provider,
        "appid": item.appid,
        "maskedLabel": item.masked_openid,
        "status": item.status,
        "verifiedAt": item.verified_at,
        "revokedAt": item.revoked_at,
        "latestWithdrawalConfirmationAttemptId": item.latest_binding_attempt_id,
        "failureReason": item.failure_reason,
        "createdAt": item.created_at,
        "updatedAt": item.updated_at,
    }


def _admin_provider_event_to_dto(item: PayoutProviderEvent) -> dict[str, object]:
    return {
        "eventId": item.event_id,
        "withdrawalId": item.withdrawal_id,
        "eventType": item.event_type,
        "provider": item.provider,
        "providerEventId": item.provider_event_id,
        "outBillNo": item.out_bill_no,
        "transferBillNo": item.transfer_bill_no,
        "providerState": item.provider_state,
        "mappedStatus": item.mapped_status,
        "rawPayloadJson": item.raw_payload_json,
        "signatureVerified": item.signature_verified,
        "createdAt": item.created_at,
    }


def _admin_reconciliation_warning_to_dto(item: ReconciliationWarning) -> dict[str, object]:
    return {
        "warningId": item.warning_id,
        "withdrawalId": item.withdrawal_id,
        "severity": item.severity,
        "reasonCode": item.reason_code,
        "message": item.message,
        "status": item.status,
        "createdAt": item.created_at,
        "resolvedAt": item.resolved_at,
    }


def _admin_membership_order_close_to_dto(
    item: MembershipOrderCloseResult,
    auth_store: AuthStore,
    *,
    payment: MembershipPaymentRecord | None,
) -> dict[str, object]:
    return {
        "order": _admin_membership_order_to_dto(item.order, auth_store),
        "membership": _admin_membership_summary_to_dto(item.membership, auth_store),
        "payment": None if payment is None else _admin_membership_payment_to_dto(payment),
        "operations": _admin_membership_order_operations_to_dto(item.order, payment=payment),
        "idempotent": item.idempotent,
    }


def _admin_membership_payment_sync_to_dto(
    item: MembershipPaymentSyncResult,
    auth_store: AuthStore,
    *,
    payment: MembershipPaymentRecord | None,
    remote_status: MembershipRemotePaymentStatus,
) -> dict[str, object]:
    return {
        "confirmed": item.confirmed,
        "idempotent": item.idempotent,
        "order": _admin_membership_order_to_dto(item.order, auth_store),
        "membership": _admin_membership_summary_to_dto(item.membership, auth_store),
        "payment": None if payment is None else _admin_membership_payment_to_dto(payment),
        "remote": {
            "provider": remote_status.provider,
            "orderId": remote_status.order_id,
            "providerTradeNo": remote_status.provider_trade_no,
            "remoteStatus": remote_status.remote_status,
            "paidAt": remote_status.paid_at,
            "amountCent": remote_status.amount_cent,
            "payerId": remote_status.payer_id,
        },
        "operations": _admin_membership_order_operations_to_dto(item.order, payment=payment),
    }


def _resolve_admin_user_search_ids(auth_store: AuthStore, search: str | None) -> set[str] | None:
    normalized_search = str(search or "").strip()
    if not normalized_search:
        return None
    matches = {user.user_id for user in auth_store.list_users(search=normalized_search, limit=200)}
    try:
        matches.add(auth_store.get_user_by_id(normalized_search).user_id)
    except NotFound:
        pass
    return matches


def _resolve_admin_target_user(auth_store: AuthStore, user_ref: str) -> AdminUser:
    normalized_user_ref = str(user_ref or "").strip()
    try:
        return auth_store.get_user_by_id(normalized_user_ref)
    except NotFound:
        return auth_store.get_user_by_public_uid(normalized_user_ref)


@router.get("/admin/overview")
def get_admin_overview(request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    require_admin_user(request, auth_store)
    return {"ok": True, "data": auth_store.get_admin_overview()}


@router.get("/admin/membership/overview")
def get_admin_membership_overview(
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_store: MembershipStore = Depends(get_membership_store),
    membership_marketing_store: MembershipMarketingStore = Depends(get_membership_marketing_store),
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
) -> dict:
    require_admin_user(request, auth_store)
    membership: MembershipAdminOverview = membership_store.get_admin_overview()
    marketing: MembershipMarketingAdminOverview = membership_marketing_store.get_admin_overview()
    commission: CommissionAdminOverview = membership_commission_store.get_admin_overview()
    return {
        "ok": True,
        "data": {
            "paidOrders": membership.paid_order_count,
            "activeMemberships": membership.active_membership_count,
            "totalPaidAmountCent": membership.total_paid_amount_cent,
            "firstPurchasePaidOrders": membership.first_purchase_paid_count,
            "renewalPaidOrders": membership.renewal_paid_count,
            "pendingOrders": membership.pending_order_count,
            "inviteBindings": marketing.invite_bindings_count,
            "rewardedInvites": marketing.rewarded_invite_count,
            "coupons": marketing.coupon_count,
            "availableCoupons": marketing.available_coupon_count,
            "usedCoupons": marketing.used_coupon_count,
            "pendingCommissionCent": commission.pending_commission_cent,
            "withdrawableCommissionCent": commission.withdrawable_commission_cent,
            "reservedWithdrawalCent": commission.reserved_withdrawal_cent,
            "paidOutCent": commission.paid_out_cent,
            "commissionRecords": commission.commission_record_count,
            "withdrawals": commission.withdrawal_count,
        },
    }


@router.get("/admin/membership/orders")
def list_admin_membership_orders(
    request: Request,
    userSearch: str | None = None,
    status: str | None = None,
    orderType: str | None = None,
    provider: str | None = None,
    limit: int = 100,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_store: MembershipStore = Depends(get_membership_store),
) -> dict:
    require_admin_user(request, auth_store)
    orders = membership_store.list_admin_orders(status=status, order_type=orderType, provider=provider, limit=limit)
    user_ids = _resolve_admin_user_search_ids(auth_store, userSearch)
    if user_ids is not None:
        orders = tuple(order for order in orders if order.user_id in user_ids)
    return {"ok": True, "data": [_admin_membership_order_to_dto(order, auth_store) for order in orders]}


@router.get("/admin/membership/orders/{orderId}")
def get_admin_membership_order_detail(
    orderId: str,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_store: MembershipStore = Depends(get_membership_store),
    membership_marketing_store: MembershipMarketingStore = Depends(get_membership_marketing_store),
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
) -> dict:
    require_admin_user(request, auth_store)
    order = membership_store.get_order(orderId)
    membership = membership_store.get_membership_summary(order.user_id)
    payment = membership_store.find_payment_for_order(order.order_id)
    return {
        "ok": True,
        "data": _admin_membership_order_detail_to_dto(
            order=order,
            membership=membership,
            payment=payment,
            auth_store=auth_store,
            membership_marketing_store=membership_marketing_store,
            membership_commission_store=membership_commission_store,
        ),
    }


@router.post("/admin/membership/grants")
def grant_admin_membership_months(
    req: AdminGrantMembershipMonthsRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_store: MembershipStore = Depends(get_membership_store),
) -> dict:
    actor = require_admin_user(request, auth_store)
    target = _resolve_admin_target_user(auth_store, req.userId)
    granted = membership_store.grant_membership_months(target.user_id, months=req.months)
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="membership.months_granted",
        target_kind="membership_entitlement",
        target_id=granted.entitlement_id,
        summary=f"Granted {req.months} month(s) of membership to user {target.public_uid}",
    )
    return {"ok": True, "data": _admin_membership_grant_to_dto(granted, auth_store)}


@router.post("/admin/membership/orders/{orderId}/sync-payment")
def sync_admin_membership_order_payment(
    orderId: str,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_store: MembershipStore = Depends(get_membership_store),
    membership_payment_service: MembershipPaymentService = Depends(get_membership_payment_service),
    membership_marketing_store: MembershipMarketingStore = Depends(get_membership_marketing_store),
) -> dict:
    actor = require_admin_user(request, auth_store)
    order = membership_store.get_order(orderId)
    if order.provider != "wechat_native":
        raise PreconditionFailure("membership payment status sync is only available for wechat_native")
    remote_status = membership_payment_service.query_payment_status(order)
    synced = membership_store.sync_provider_payment_status(order_id=orderId, remote_status=remote_status)
    order = synced.order
    payment = membership_store.find_payment_for_order(order.order_id)
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="membership.order_payment_synced",
        target_kind="membership_order",
        target_id=order.order_id,
        summary=f"Synced membership payment for order {order.order_id}, remote status {remote_status.remote_status}",
    )
    return {"ok": True, "data": _admin_membership_payment_sync_to_dto(synced, auth_store, payment=payment, remote_status=remote_status)}


@router.post("/admin/membership/orders/{orderId}/close")
def close_admin_membership_order(
    orderId: str,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_store: MembershipStore = Depends(get_membership_store),
) -> dict:
    actor = require_admin_user(request, auth_store)
    closed = membership_store.close_order(
        orderId,
        reason=f"admin {actor.user_id} closed pending membership order",
    )
    payment = membership_store.find_payment_for_order(closed.order.order_id)
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="membership.order_closed",
        target_kind="membership_order",
        target_id=closed.order.order_id,
        summary=f"Closed pending membership order {closed.order.order_id}",
    )
    return {"ok": True, "data": _admin_membership_order_close_to_dto(closed, auth_store, payment=payment)}


@router.post("/admin/membership/orders/{orderId}/refund")
def refund_admin_membership_order(
    orderId: str,
    req: AdminRefundMembershipOrderRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_store: MembershipStore = Depends(get_membership_store),
    membership_payment_service: MembershipPaymentService = Depends(get_membership_payment_service),
) -> dict:
    actor = require_admin_user(request, auth_store)
    order = membership_store.get_order(orderId)
    reason = req.reason or ""
    if order.provider == "manual_test":
        refunded = membership_store.refund_order(orderId, reason=reason)
    elif order.provider == "wechat_native":
        payment = membership_store.get_payment_for_order(orderId)
        if order.status == "paid":
            membership_store.ensure_refund_can_start(order)
            remote_refund = membership_payment_service.request_refund(
                order,
                payment,
                reason=reason,
                public_origin=current_http_runtime_config().public_origin,
            )
            if remote_refund.remote_status == "refund_pending":
                refunded = membership_store.mark_refund_pending(
                    order_id=orderId,
                    provider=order.provider,
                    refund_out_refund_no=remote_refund.refund_out_trade_no,
                    refund_payload_json=remote_refund.raw_payload_json,
                    requested_at=remote_refund.refunded_at,
                )
            else:
                refunded = membership_store.sync_provider_refund(
                    order_id=orderId,
                    provider=order.provider,
                    refund_out_refund_no=remote_refund.refund_out_trade_no,
                    remote_status=remote_refund.remote_status,
                    refund_payload_json=remote_refund.raw_payload_json,
                    refunded_at=remote_refund.refunded_at,
                    reason=reason,
                )
        elif order.status == "refund_pending":
            remote_refund = membership_payment_service.query_refund_status(order, payment)
            refunded = membership_store.sync_provider_refund(
                order_id=orderId,
                provider=order.provider,
                refund_out_refund_no=remote_refund.refund_out_trade_no,
                remote_status=remote_refund.remote_status,
                refund_payload_json=remote_refund.raw_payload_json,
                refunded_at=remote_refund.refunded_at,
                reason=reason,
            )
        else:
            refunded = membership_store.refund_order(orderId, reason=reason)
    else:
        refunded = membership_store.refund_order(orderId, reason=reason)
    target_ref = _admin_user_ref_to_dto(refunded.order.user_id, auth_store)
    details: list[str] = [f"Handled membership refund for order {refunded.order.order_id} and user {target_ref['publicUid'] or refunded.order.user_id}"]
    if refunded.refund_request_submitted:
        details.append("submitted provider refund request")
    if refunded.remote_status:
        details.append(f"remote status {refunded.remote_status}")
    if refunded.restored_coupon_id:
        details.append(f"restored coupon {refunded.restored_coupon_id}")
    if refunded.revoked_reward_coupon_id:
        details.append(f"revoked reward coupon {refunded.revoked_reward_coupon_id}")
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="membership.order_refunded",
        target_kind="membership_order",
        target_id=refunded.order.order_id,
        summary=", ".join(details),
    )
    return {"ok": True, "data": _admin_membership_refund_to_dto(refunded, auth_store)}


@router.get("/admin/membership/invites")
def list_admin_membership_invites(
    request: Request,
    search: str | None = None,
    status: str | None = None,
    limit: int = 100,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_marketing_store: MembershipMarketingStore = Depends(get_membership_marketing_store),
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
) -> dict:
    require_admin_user(request, auth_store)
    invites = membership_marketing_store.list_admin_invites(status=status, limit=limit)
    user_ids = _resolve_admin_user_search_ids(auth_store, search)
    if user_ids is not None:
        invites = tuple(item for item in invites if item.inviter_user_id in user_ids or item.invitee_user_id in user_ids)
    return {"ok": True, "data": [_admin_membership_invite_to_dto(item, auth_store, membership_commission_store) for item in invites]}


@router.get("/admin/membership/coupons")
def list_admin_membership_coupons(
    request: Request,
    search: str | None = None,
    status: str | None = None,
    limit: int = 100,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_marketing_store: MembershipMarketingStore = Depends(get_membership_marketing_store),
) -> dict:
    require_admin_user(request, auth_store)
    coupons = membership_marketing_store.list_admin_coupons(status=status, limit=limit)
    user_ids = _resolve_admin_user_search_ids(auth_store, search)
    if user_ids is not None:
        coupons = tuple(
            item
            for item in coupons
            if item.user_id in user_ids or (item.source_invitee_user_id is not None and item.source_invitee_user_id in user_ids)
        )
    return {"ok": True, "data": [_admin_coupon_to_dto(item, auth_store) for item in coupons]}


@router.get("/admin/membership/commissions")
def list_admin_membership_commissions(
    request: Request,
    search: str | None = None,
    status: str | None = None,
    limit: int = 100,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
) -> dict:
    require_admin_user(request, auth_store)
    items = membership_commission_store.list_admin_commissions(status=status, limit=limit)
    user_ids = _resolve_admin_user_search_ids(auth_store, search)
    if user_ids is not None:
        items = tuple(item for item in items if item.inviter_user_id in user_ids or item.invitee_user_id in user_ids)
    return {"ok": True, "data": [_admin_commission_to_dto(item, auth_store) for item in items]}


@router.post("/admin/membership/commissions/settle")
def settle_admin_membership_commissions(
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
) -> dict:
    actor = require_admin_user(request, auth_store)
    result: CommissionSettlementResult = membership_commission_store.settle_due_commissions()
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="membership.commissions_settled",
        target_kind="membership_commission",
        target_id="batch",
        summary=f"Settled {result.settled_count} commissions, canceled {result.canceled_count}, skipped {result.skipped_count}",
    )
    return {
        "ok": True,
        "data": {
            "runId": result.run_id,
            "scannedCount": result.scanned_count,
            "settledCount": result.settled_count,
            "canceledCount": result.canceled_count,
            "skippedCount": result.skipped_count,
            "errorCount": result.error_count,
        },
    }


@router.get("/admin/membership/payout-identities")
def list_admin_membership_payout_identities(
    request: Request,
    search: str | None = None,
    status: str | None = None,
    limit: int = 100,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
) -> dict:
    require_admin_user(request, auth_store)
    user_ids = _resolve_admin_user_search_ids(auth_store, search)
    items = membership_commission_store.list_admin_payout_identities(status=status, search_user_ids=user_ids, limit=limit)
    return {"ok": True, "data": [_admin_payout_identity_to_dto(item, auth_store) for item in items]}


@router.get("/admin/membership/withdrawals/events")
def list_admin_membership_withdrawal_events(
    request: Request,
    withdrawalId: str | None = None,
    limit: int = 100,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
) -> dict:
    require_admin_user(request, auth_store)
    items = membership_commission_store.list_payout_provider_events(withdrawal_id=withdrawalId, limit=limit)
    return {"ok": True, "data": [_admin_provider_event_to_dto(item) for item in items]}


@router.get("/admin/membership/withdrawals/warnings")
def list_admin_membership_withdrawal_warnings(
    request: Request,
    status: str | None = None,
    limit: int = 100,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
) -> dict:
    require_admin_user(request, auth_store)
    items = membership_commission_store.list_reconciliation_warnings(status=status, limit=limit)
    return {"ok": True, "data": [_admin_reconciliation_warning_to_dto(item) for item in items]}


@router.post("/admin/membership/withdrawals/warnings/{warningId}/ack")
def acknowledge_admin_membership_withdrawal_warning(
    warningId: str,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
) -> dict:
    actor = require_admin_user(request, auth_store)
    warning = membership_commission_store.resolve_reconciliation_warning(warningId)
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="membership.withdrawal_warning_acknowledged",
        target_kind="membership_withdrawal_warning",
        target_id=warning.warning_id,
        summary=f"Acknowledged withdrawal warning {warning.warning_id} for {warning.withdrawal_id}",
    )
    return {"ok": True, "data": _admin_reconciliation_warning_to_dto(warning)}


@router.get("/admin/membership/withdrawals")
def list_admin_membership_withdrawals(
    request: Request,
    search: str | None = None,
    status: str | None = None,
    limit: int = 100,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
) -> dict:
    require_admin_user(request, auth_store)
    items = membership_commission_store.list_admin_withdrawals(status=status, limit=limit)
    user_ids = _resolve_admin_user_search_ids(auth_store, search)
    if user_ids is not None:
        items = tuple(item for item in items if item.user_id in user_ids)
    return {"ok": True, "data": [_admin_withdrawal_to_dto(item, auth_store) for item in items]}


@router.post("/admin/membership/withdrawals/{withdrawalId}/resolve")
def resolve_admin_membership_withdrawal(
    withdrawalId: str,
    req: AdminResolveCommissionWithdrawalRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
) -> dict:
    actor = require_admin_user(request, auth_store)
    normalized_status = str(req.status or "").strip().lower()
    if normalized_status == "succeeded":
        item = membership_commission_store.mark_withdrawal_succeeded(
            withdrawalId,
            provider_transfer_no=req.providerTransferNo,
        )
    elif normalized_status == "failed":
        item = membership_commission_store.mark_withdrawal_failed(
            withdrawalId,
            provider_transfer_no=req.providerTransferNo,
            failure_reason=req.failureReason or "wechat payout failed",
        )
    else:
        raise PreconditionFailure("withdrawal resolve status must be succeeded or failed")
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="membership.withdrawal_resolved",
        target_kind="membership_withdrawal",
        target_id=item.withdrawal_id,
        summary=f"Marked withdrawal {item.withdrawal_id} as {item.status}",
    )
    return {"ok": True, "data": _admin_withdrawal_to_dto(item, auth_store)}


@router.post("/admin/membership/withdrawals/{withdrawalId}/sync")
def sync_admin_membership_withdrawal(
    withdrawalId: str,
    request: Request,
    req: SyncCommissionWithdrawalRequest | None = None,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_commission_store: MembershipCommissionStore = Depends(get_membership_commission_store),
    membership_payment_service: MembershipPaymentService = Depends(get_membership_payment_service),
) -> dict:
    actor = require_admin_user(request, auth_store)
    withdrawal = membership_commission_store.get_withdrawal_request(withdrawalId)
    if withdrawal is None:
        raise NotFound("withdrawal request")
    remote = membership_payment_service.query_commission_payout(withdrawal.out_bill_no, withdrawal_id=withdrawal.withdrawal_id)
    if remote.remote_status in {
        WITHDRAWAL_STATUS_SUCCEEDED,
        WITHDRAWAL_STATUS_FAILED,
        WITHDRAWAL_STATUS_CANCELED,
        WITHDRAWAL_STATUS_NEEDS_ATTENTION,
        WITHDRAWAL_STATUS_AWAITING_CONFIRMATION,
        WITHDRAWAL_STATUS_PROCESSING,
    }:
        updated = membership_commission_store.apply_withdrawal_provider_result(
            out_bill_no=withdrawal.out_bill_no,
            provider_state=remote.provider_state,
            mapped_status=remote.remote_status,
            transfer_bill_no=remote.provider_transfer_no,
            amount_cent=remote.amount_cent,
            appid=remote.appid,
            raw_payload_json=remote.raw_payload_json,
            provider_event_id=remote.provider_transfer_no or withdrawal.out_bill_no,
            event_type="query",
            failure_reason=remote.failure_reason,
            signature_verified=True,
        )
    else:
        updated = withdrawal
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="membership.withdrawal_synced",
        target_kind="membership_withdrawal",
        target_id=updated.withdrawal_id,
        summary=f"Synced withdrawal {updated.withdrawal_id}, {withdrawal.status} -> {updated.status}",
    )
    return {
        "ok": True,
        "data": {
            "withdrawalId": updated.withdrawal_id,
            "previousStatus": withdrawal.status,
            "currentStatus": updated.status,
            "providerState": remote.provider_state,
            "action": f"marked_{updated.status}" if updated.status != withdrawal.status else f"kept_{updated.status}",
            "withdrawal": _admin_withdrawal_to_dto(updated, auth_store),
        },
    }


@router.post("/admin/membership/coupons/grant")
def grant_admin_membership_coupon(
    req: AdminGrantMembershipCouponRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_marketing_store: MembershipMarketingStore = Depends(get_membership_marketing_store),
) -> dict:
    actor = require_admin_user(request, auth_store)
    target = _resolve_admin_target_user(auth_store, req.userId)
    coupon = membership_marketing_store.grant_coupon(
        target.user_id,
        amount_cent=req.amountCent,
        title=req.title,
        expires_in_days=req.expiresInDays,
        min_spend_cent=req.minSpendCent,
    )
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="membership.coupon_granted",
        target_kind="membership_coupon",
        target_id=coupon.coupon_id,
        summary=f"Granted coupon {coupon.title} to user {target.public_uid}",
    )
    return {"ok": True, "data": _admin_coupon_to_dto(coupon, auth_store)}


@router.post("/admin/membership/coupons/{couponId}/void")
def void_admin_membership_coupon(
    couponId: str,
    req: AdminVoidMembershipCouponRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    membership_marketing_store: MembershipMarketingStore = Depends(get_membership_marketing_store),
) -> dict:
    actor = require_admin_user(request, auth_store)
    coupon = membership_marketing_store.void_coupon(couponId, reason=req.reason or "")
    target_ref = _admin_user_ref_to_dto(coupon.user_id, auth_store)
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="membership.coupon_voided",
        target_kind="membership_coupon",
        target_id=coupon.coupon_id,
        summary=f"Voided coupon {coupon.title or coupon.coupon_id} for user {target_ref['publicUid'] or coupon.user_id}",
    )
    return {"ok": True, "data": _admin_coupon_to_dto(coupon, auth_store)}


@router.get("/admin/users")
def list_users(
    request: Request,
    search: str | None = None,
    status: str | None = None,
    role: str | None = None,
    limit: int = 100,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    require_admin_user(request, auth_store)
    users = auth_store.list_users(search=search, status=status, role=role, limit=limit)
    return {"ok": True, "data": [_admin_user_to_dto(user) for user in users]}


@router.get("/admin/users/{userId}")
def get_user_detail(userId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    require_admin_user(request, auth_store)
    user = auth_store.get_user_by_id(userId)
    return {"ok": True, "data": _auth_user_to_admin_dto(user.user_id, auth_store)}


@router.patch("/admin/users/{userId}/status")
def update_user_status(
    userId: str,
    req: UpdateUserStatusRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    actor = require_admin_user(request, auth_store)
    updated = auth_store.set_user_status(userId, status=req.status)
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="user.status_updated",
        target_kind="user",
        target_id=updated.user_id,
        summary=f"Set user {updated.public_uid} status to {updated.status}",
    )
    return {"ok": True, "data": _auth_user_to_admin_dto(updated.user_id, auth_store)}


@router.patch("/admin/users/{userId}/roles")
def update_user_role(
    userId: str,
    req: UpdateUserRoleRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    actor = require_super_admin_user(request, auth_store)
    auth_store.set_user_global_role(userId, role=req.role, enabled=req.enabled, granted_by_user_id=actor.user_id)
    target_user = auth_store.get_user_by_id(userId)
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="user.role_updated",
        target_kind="user",
        target_id=target_user.user_id,
        summary=f"{'Granted' if req.enabled else 'Revoked'} {req.role} for user {target_user.public_uid}",
    )
    return {"ok": True, "data": _auth_user_to_admin_dto(userId, auth_store)}


@router.get("/admin/activity")
@router.get("/admin/audit-logs")
def list_admin_activity(request: Request, limit: int = 50, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    require_admin_user(request, auth_store)
    logs = auth_store.list_admin_action_logs(limit=limit)
    return {"ok": True, "data": [_admin_action_log_to_dto(item) for item in logs]}
