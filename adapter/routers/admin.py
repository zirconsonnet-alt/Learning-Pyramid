from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from adapter.auth import require_admin_user, require_super_admin_user
from adapter.deps import get_auth_store, get_membership_marketing_store, get_membership_payment_service, get_membership_store
from adapter.schemas import (
    AdminGrantMembershipCouponRequest,
    AdminRefundMembershipOrderRequest,
    AdminVoidMembershipCouponRequest,
    UpdateStudyGroupStatusRequest,
    UpdateUserRoleRequest,
    UpdateUserStatusRequest,
)
from backend.models.errors import NotFound, PreconditionFailure
from backend.system.http_runtime_config import current_http_runtime_config
from backend.system.auth_store import (
    AdminActionLog,
    AdminStudyGroupComment,
    AdminStudyGroupPost,
    AdminUser,
    AdminUserStudyGroup,
    AuthStore,
    StudyGroup,
    StudyGroupJoinRequest,
    StudyGroupMember,
    StudyGroupPost,
    StudyGroupPostComment,
)
from backend.system.membership_marketing_store import (
    CouponRecord,
    InviteBinding,
    MembershipMarketingAdminOverview,
    MembershipMarketingStore,
)
from backend.system.membership_payment_service import MembershipPaymentService, MembershipRemotePaymentStatus
from backend.system.membership_store import (
    MembershipAdminOverview,
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


def _group_to_dto(group: StudyGroup) -> dict[str, object]:
    return {
        "groupId": group.group_id,
        "name": group.name,
        "description": group.description,
        "visibility": group.visibility,
        "joinPolicy": group.join_policy,
        "status": group.status,
        "ownerUserId": group.owner_user_id,
        "ownerPublicUid": group.owner_public_uid,
        "ownerNickname": group.owner_nickname,
        "avatarUrl": None if not group.avatar_key else f"/api/study-groups/{group.group_id}/avatar?v={group.updated_at}",
        "createdAt": group.created_at,
        "updatedAt": group.updated_at,
        "memberCount": group.member_count,
        "memberRole": group.member_role,
        "joinRequestStatus": group.join_request_status,
    }


def _admin_user_group_to_dto(group: AdminUserStudyGroup) -> dict[str, object]:
    return {
        "groupId": group.group_id,
        "name": group.name,
        "description": group.description,
        "visibility": group.visibility,
        "joinPolicy": group.join_policy,
        "status": group.status,
        "ownerUserId": group.owner_user_id,
        "ownerPublicUid": group.owner_public_uid,
        "ownerNickname": group.owner_nickname,
        "avatarUrl": None if not group.avatar_key else f"/api/study-groups/{group.group_id}/avatar?v={group.updated_at}",
        "createdAt": group.created_at,
        "updatedAt": group.updated_at,
        "memberCount": group.member_count,
        "memberRole": group.member_role,
        "joinedAt": group.joined_at,
    }


def _group_member_to_dto(member: StudyGroupMember) -> dict[str, object]:
    return {
        "userId": member.user_id,
        "publicUid": member.public_uid,
        "nickname": member.nickname,
        "avatarUrl": None if not member.avatar_key else f"/api/profile/avatar/{member.user_id}",
        "role": member.role,
        "joinedAt": member.joined_at,
    }


def _group_post_to_dto(post: StudyGroupPost) -> dict[str, object]:
    return {
        "postId": post.post_id,
        "groupId": post.group_id,
        "authorUserId": post.author_user_id,
        "authorPublicUid": post.author_public_uid,
        "authorNickname": post.author_nickname,
        "authorAvatarUrl": None if not post.author_avatar_key else f"/api/profile/avatar/{post.author_user_id}",
        "kind": post.kind,
        "content": post.content,
        "createdAt": post.created_at,
        "updatedAt": post.updated_at,
    }


def _group_comment_to_dto(comment: StudyGroupPostComment) -> dict[str, object]:
    return {
        "commentId": comment.comment_id,
        "groupId": comment.group_id,
        "postId": comment.post_id,
        "authorUserId": comment.author_user_id,
        "authorPublicUid": comment.author_public_uid,
        "authorNickname": comment.author_nickname,
        "authorAvatarUrl": None if not comment.author_avatar_key else f"/api/profile/avatar/{comment.author_user_id}",
        "content": comment.content,
        "createdAt": comment.created_at,
        "updatedAt": comment.updated_at,
    }


def _group_join_request_to_dto(item: StudyGroupJoinRequest) -> dict[str, object]:
    return {
        "requestId": item.request_id,
        "groupId": item.group_id,
        "requesterUserId": item.requester_user_id,
        "requesterPublicUid": item.requester_public_uid,
        "requesterNickname": item.requester_nickname,
        "requesterAvatarUrl": None if not item.requester_avatar_key else f"/api/profile/avatar/{item.requester_user_id}",
        "message": item.message,
        "status": item.status,
        "createdAt": item.created_at,
        "reviewedAt": item.reviewed_at,
        "reviewedByUserId": item.reviewed_by_user_id,
    }


def _admin_post_to_dto(post: AdminStudyGroupPost) -> dict[str, object]:
    return {
        "postId": post.post_id,
        "groupId": post.group_id,
        "groupName": post.group_name,
        "authorUserId": post.author_user_id,
        "authorPublicUid": post.author_public_uid,
        "authorNickname": post.author_nickname,
        "authorAvatarUrl": None if not post.author_avatar_key else f"/api/profile/avatar/{post.author_user_id}",
        "kind": post.kind,
        "content": post.content,
        "createdAt": post.created_at,
        "updatedAt": post.updated_at,
        "commentCount": post.comment_count,
    }


def _admin_comment_to_dto(comment: AdminStudyGroupComment) -> dict[str, object]:
    return {
        "commentId": comment.comment_id,
        "groupId": comment.group_id,
        "groupName": comment.group_name,
        "postId": comment.post_id,
        "postKind": comment.post_kind,
        "postExcerpt": comment.post_excerpt,
        "authorUserId": comment.author_user_id,
        "authorPublicUid": comment.author_public_uid,
        "authorNickname": comment.author_nickname,
        "authorAvatarUrl": None if not comment.author_avatar_key else f"/api/profile/avatar/{comment.author_user_id}",
        "content": comment.content,
        "createdAt": comment.created_at,
        "updatedAt": comment.updated_at,
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


def _admin_membership_invite_to_dto(binding: InviteBinding, auth_store: AuthStore) -> dict[str, object]:
    return {
        "invitee": _admin_user_ref_to_dto(binding.invitee_user_id, auth_store),
        "inviter": _admin_user_ref_to_dto(binding.inviter_user_id, auth_store),
        "inviteCode": binding.invite_code_snapshot,
        "status": binding.status,
        "boundAt": binding.bound_at,
        "rewardedAt": binding.rewarded_at,
        "rewardTriggerOrderId": binding.reward_trigger_order_id,
        "rewardCouponId": binding.reward_coupon_id,
    }


def _admin_coupon_to_dto(coupon: CouponRecord, auth_store: AuthStore) -> dict[str, object]:
    return {
        "couponId": coupon.coupon_id,
        "user": _admin_user_ref_to_dto(coupon.user_id, auth_store),
        "title": coupon.title,
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
) -> dict[str, object]:
    binding = membership_marketing_store.get_invite_binding(order.user_id)
    coupon = None if order.coupon_id is None else membership_marketing_store.get_coupon(order.coupon_id)
    reward_coupon = None
    if binding is not None and binding.reward_coupon_id:
        reward_coupon = membership_marketing_store.get_coupon(binding.reward_coupon_id)
    reward_triggered_by_this_order = binding is not None and binding.reward_trigger_order_id == order.order_id
    return {
        "order": _admin_membership_order_to_dto(order, auth_store),
        "membership": _admin_membership_summary_to_dto(membership, auth_store),
        "payment": None if payment is None else _admin_membership_payment_to_dto(payment),
        "coupon": None if coupon is None else _admin_coupon_to_dto(coupon, auth_store),
        "invite": None
        if binding is None
        else {
            "binding": _admin_membership_invite_to_dto(binding, auth_store),
            "rewardTriggeredByThisOrder": reward_triggered_by_this_order,
            "rewardCoupon": None if reward_coupon is None else _admin_coupon_to_dto(reward_coupon, auth_store),
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
) -> dict:
    require_admin_user(request, auth_store)
    membership: MembershipAdminOverview = membership_store.get_admin_overview()
    marketing: MembershipMarketingAdminOverview = membership_marketing_store.get_admin_overview()
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
        ),
    }


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
) -> dict:
    require_admin_user(request, auth_store)
    invites = membership_marketing_store.list_admin_invites(status=status, limit=limit)
    user_ids = _resolve_admin_user_search_ids(auth_store, search)
    if user_ids is not None:
        invites = tuple(item for item in invites if item.inviter_user_id in user_ids or item.invitee_user_id in user_ids)
    return {"ok": True, "data": [_admin_membership_invite_to_dto(item, auth_store) for item in invites]}


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
    groups = auth_store.list_admin_user_study_groups(userId, limit=200)
    return {
        "ok": True,
        "data": {
            **_auth_user_to_admin_dto(user.user_id, auth_store),
            "groups": [_admin_user_group_to_dto(group) for group in groups],
        },
    }


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


@router.get("/admin/groups")
def list_groups(
    request: Request,
    search: str | None = None,
    status: str | None = None,
    limit: int = 100,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    require_admin_user(request, auth_store)
    groups = auth_store.list_all_study_groups(search=search, status=status, limit=limit)
    return {"ok": True, "data": [_group_to_dto(group) for group in groups]}


@router.get("/admin/groups/{groupId}")
def get_group_detail(groupId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    actor = require_admin_user(request, auth_store)
    group = auth_store.get_study_group(groupId, viewer_user_id=actor.user_id)
    members = auth_store.list_study_group_members(groupId)
    join_requests = auth_store.list_study_group_join_requests(groupId, status=None, limit=200)
    posts = auth_store.list_study_group_posts(groupId, limit=200)
    comments = auth_store.list_study_group_post_comments(groupId, limit=400)
    return {
        "ok": True,
        "data": {
            **_group_to_dto(group),
            "members": [_group_member_to_dto(member) for member in members],
            "joinRequests": [_group_join_request_to_dto(item) for item in join_requests],
            "posts": [_group_post_to_dto(post) for post in posts],
            "comments": [_group_comment_to_dto(comment) for comment in comments],
        },
    }


@router.patch("/admin/groups/{groupId}/status")
def update_group_status(
    groupId: str,
    req: UpdateStudyGroupStatusRequest,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    actor = require_admin_user(request, auth_store)
    group = auth_store.set_study_group_status(groupId, status=req.status)
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="group.status_updated",
        target_kind="study_group",
        target_id=group.group_id,
        summary=f"Set study group {group.name} status to {group.status}",
    )
    return {"ok": True, "data": _group_to_dto(group)}


@router.get("/admin/activity")
@router.get("/admin/audit-logs")
def list_admin_activity(request: Request, limit: int = 50, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    require_admin_user(request, auth_store)
    logs = auth_store.list_admin_action_logs(limit=limit)
    return {"ok": True, "data": [_admin_action_log_to_dto(item) for item in logs]}


@router.get("/admin/content/posts")
def list_admin_posts(
    request: Request,
    search: str | None = None,
    limit: int = 100,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    require_admin_user(request, auth_store)
    posts = auth_store.list_admin_study_group_posts(search=search, limit=limit)
    return {"ok": True, "data": [_admin_post_to_dto(post) for post in posts]}


@router.get("/admin/content/comments")
def list_admin_comments(
    request: Request,
    search: str | None = None,
    limit: int = 100,
    auth_store: AuthStore = Depends(get_auth_store),
) -> dict:
    require_admin_user(request, auth_store)
    comments = auth_store.list_admin_study_group_comments(search=search, limit=limit)
    return {"ok": True, "data": [_admin_comment_to_dto(comment) for comment in comments]}


@router.delete("/admin/content/posts/{postId}")
def delete_admin_post(postId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    actor = require_admin_user(request, auth_store)
    deleted = auth_store.delete_admin_study_group_post(postId)
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="content.post_deleted",
        target_kind="study_group_post",
        target_id=deleted.post_id,
        summary=f"Deleted post in {deleted.group_name} by {deleted.author_public_uid}",
    )
    return {"ok": True, "data": _admin_post_to_dto(deleted)}


@router.delete("/admin/content/comments/{commentId}")
def delete_admin_comment(commentId: str, request: Request, auth_store: AuthStore = Depends(get_auth_store)) -> dict:
    actor = require_admin_user(request, auth_store)
    deleted = auth_store.delete_admin_study_group_comment(commentId)
    auth_store.record_admin_action(
        actor_user_id=actor.user_id,
        action_type="content.comment_deleted",
        target_kind="study_group_comment",
        target_id=deleted.comment_id,
        summary=f"Deleted comment in {deleted.group_name} by {deleted.author_public_uid}",
    )
    return {"ok": True, "data": _admin_comment_to_dto(deleted)}
