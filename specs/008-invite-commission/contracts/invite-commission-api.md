# Contract: Invite Discount And Commission API

All endpoints continue using the existing response envelope:

```json
{ "ok": true, "data": {} }
```

Errors continue using the existing API error envelope and `PRECONDITION` for business-rule rejection.

## User Membership Summary

### `GET /api/membership/me`

Adds or updates price fields so new previews and displays reflect the new membership price:

```json
{
  "userId": "user_xxx",
  "currentStatus": "never_purchased",
  "isFirstOrderEligible": true,
  "baseMonthlyPriceCent": 2000,
  "firstOrderPriceCent": 2000,
  "renewalPriceCent": 2000,
  "currentPriceCent": 2000,
  "supportedPaymentProviders": ["wechat_native"]
}
```

## Invite Binding

### `POST /api/invites/bind`

Request:

```json
{
  "inviteCode": "LPAB12CD34"
}
```

Response:

```json
{
  "inviteeUserId": "user_invitee",
  "inviterUserId": "user_inviter",
  "inviteCode": "LPAB12CD34",
  "status": "discount_issued",
  "boundAt": "2026-05-05T10:00:00+00:00",
  "discountCouponId": "coupon_xxx",
  "rewardedAt": null,
  "rewardTriggerOrderId": null,
  "rewardCouponId": null
}
```

Business rules:

- A user can bind only one invite code.
- A user cannot bind their own invite code.
- Binding after the first successful membership order is rejected.
- New binding grants the invitee one 7.5-discount membership coupon.
- New binding does not grant the inviter a 5 yuan coupon.

## Coupons

### `GET /api/coupons/me?limit=20`

Invite discount coupon item:

```json
{
  "couponId": "coupon_xxx",
  "userId": "user_invitee",
  "title": "邀请码 7.5 折券",
  "couponType": "percent",
  "discountRate": 75,
  "amountCent": 0,
  "minSpendCent": 0,
  "source": "invite_discount",
  "status": "available",
  "sourceInviteeUserId": "user_invitee",
  "createdAt": "2026-05-05T10:00:00+00:00",
  "expiresAt": "2026-06-04T10:00:00+00:00",
  "usedAt": null,
  "usedOrderId": null
}
```

Historical old invite reward coupons may still appear with:

```json
{
  "couponType": "cash",
  "source": "invite_reward",
  "title": "邀请奖励 5 元券"
}
```

## Price Preview And Order Creation

### `POST /api/membership/orders/preview`

Request:

```json
{
  "couponId": "coupon_xxx"
}
```

Response when using invite discount:

```json
{
  "userId": "user_invitee",
  "orderType": "first_purchase",
  "periodDays": 30,
  "listAmountCent": 2000,
  "firstOrderDiscountCent": 0,
  "couponDiscountCent": 500,
  "payableAmountCent": 1500,
  "couponId": "coupon_xxx"
}
```

### `POST /api/membership/orders`

Uses the same pricing rules as preview. Order response keeps the order-time snapshot:

```json
{
  "order": {
    "orderId": "mord_xxx",
    "pricingVersion": "invite_commission_v1",
    "listAmountCent": 2000,
    "firstOrderDiscountCent": 0,
    "couponDiscountCent": 500,
    "payableAmountCent": 1500,
    "couponId": "coupon_xxx",
    "status": "pending"
  },
  "paymentPayload": {},
  "reusedExistingOrder": false
}
```

## Commission Summary

### `GET /api/commissions/me`

Response:

```json
{
  "account": {
    "userId": "user_inviter",
    "pendingCent": 500,
    "withdrawableCent": 1000,
    "reservedCent": 0,
    "paidOutCent": 500,
    "canceledCent": 0,
    "updatedAt": "2026-05-06T10:00:00+00:00"
  },
  "recentCommissions": [
    {
      "commissionId": "mcom_xxx",
      "inviteeUserId": "user_invitee",
      "sourceOrderId": "mord_xxx",
      "sourcePaymentAmountCent": 1500,
      "commissionAmountCent": 500,
      "refundWindowEndsAt": "2026-05-06T10:00:00+00:00",
      "status": "settled",
      "createdAt": "2026-05-05T10:00:00+00:00",
      "settledAt": "2026-05-06T10:01:00+00:00",
      "canceledAt": null,
      "cancelReason": ""
    }
  ]
}
```

## Withdrawal Request

### `POST /api/commissions/withdrawals`

Request:

```json
{
  "amountCent": 500,
  "wechatOpenId": "openid_xxx"
}
```

Response:

```json
{
  "withdrawalId": "mwd_xxx",
  "userId": "user_inviter",
  "amountCent": 500,
  "targetType": "wechat_pay",
  "wechatOpenIdMasked": "openid_***",
  "status": "processing",
  "providerTransferNo": "transfer_xxx",
  "failureReason": "",
  "createdAt": "2026-05-06T11:00:00+00:00",
  "submittedAt": "2026-05-06T11:00:01+00:00",
  "completedAt": null
}
```

Business rules:

- Reject if amount is greater than withdrawable balance.
- Reject if WeChat receiving identity is missing, invalid, or not owned by the user.
- Reserve balance before provider submission.
- Provider success moves reserved balance to paid-out.
- Provider failure returns reserved balance to withdrawable.

## Withdrawal History

### `GET /api/commissions/withdrawals?limit=20`

Returns current user's withdrawal records, newest first.

## Admin Commission Audit

### `GET /api/admin/membership/commissions?status=pending|settled|canceled|all&search=...&limit=50`

Returns commission records with inviter, invitee, source order, amount, refund-window deadline, and status.

### `GET /api/admin/membership/withdrawals?status=pending|processing|succeeded|failed|all&search=...&limit=50`

Returns withdrawal records with user, amount, target label, provider transfer number, status, timestamps, and failure reason.

### `POST /api/admin/membership/commissions/settle`

Runs an idempotent settlement pass for pending records whose refund windows have passed.

Response:

```json
{
  "settledCount": 3,
  "canceledCount": 1,
  "skippedCount": 12
}
```
