# Data Model: Invite Discount And Commission

## Invite Binding

Represents the relationship between an inviter and an invitee.

**Attributes**:

- `inviteeUserId`: user who bound an invite code
- `inviterUserId`: user who owns the invite code
- `inviteCode`: invite code snapshot used at bind time
- `status`: `bound`, `discount_issued`, `commission_pending`, `commission_settled`, or historical `rewarded`
- `boundAt`: binding time
- `discountCouponId`: invitee-side 7.5-discount coupon created by the binding
- `commissionRecordId`: commission record created by a qualifying invited purchase, if any

**Validation rules**:

- A user can have at most one invite binding.
- A user cannot bind their own invite code.
- Binding must happen before the invitee's first successful membership order.
- New bindings create one invitee discount coupon and do not create an inviter 5 yuan coupon.
- Historical `rewarded` bindings remain readable for old 5 yuan coupon records.

## Invite Discount Coupon

Represents the 7.5-discount membership coupon granted to an invitee.

**Attributes**:

- `couponId`: unique coupon identifier
- `userId`: invitee who owns the coupon
- `title`: user-facing title, e.g. "邀请码 7.5 折券"
- `couponType`: `percent`
- `discountRate`: 75 percent of the applicable membership price
- `source`: `invite_discount`
- `sourceInviteeUserId`: invitee user id for traceability
- `status`: `available`, `reserved`, `used`, `revoked`, or `expired`
- `createdAt`, `expiresAt`, `usedAt`
- `usedOrderId`: order that consumed the coupon

**Validation rules**:

- The coupon applies only to membership orders.
- The coupon cannot reduce payable amount below zero.
- The actual discount amount is calculated during preview/order creation and snapshotted on the order.
- Each invite binding can create at most one invite discount coupon.

## Membership Price Snapshot

Represents the order-time pricing data for a membership order.

**Attributes**:

- `listAmountCent`: base monthly price; new orders use `2000`
- `firstOrderDiscountCent`: retained for historical compatibility, but not the primary new-invite discount
- `couponDiscountCent`: actual cent discount from the selected coupon
- `payableAmountCent`: actual successful payment amount used for commission threshold
- `couponId`: selected coupon, if any
- `pricingVersion`: value that distinguishes the new 20 yuan invite-commission pricing from historical pricing

**Validation rules**:

- New membership previews and orders use a 20 yuan base monthly price.
- A 7.5-discount coupon applied to a 20 yuan order yields 15 yuan payable.
- Commission threshold uses `payableAmountCent`, not `listAmountCent`.
- Historical orders keep their original price snapshots.

## Commission Record

Represents commission earned or blocked from a qualifying invited membership order.

**Attributes**:

- `commissionId`: unique commission record identifier
- `inviterUserId`: user who may receive commission
- `inviteeUserId`: invited user whose payment qualifies
- `sourceOrderId`: membership order that triggered the record
- `sourcePaymentAmountCent`: successful actual payment amount
- `thresholdAmountCent`: `1500`
- `commissionAmountCent`: fixed `500`
- `refundWindowEndsAt`: payment success time plus 24 hours
- `status`: `pending`, `settled`, `canceled`, or `reversed`
- `createdAt`, `settledAt`, `canceledAt`, `cancelReason`

**Validation rules**:

- A commission record is created only for invited membership orders with actual paid amount at least 15 yuan.
- Each source order can create at most one commission record.
- Each invite relationship can create at most one commission record unless recurring commission is explicitly added later.
- A pending record settles only after `refundWindowEndsAt`.
- A pending record is canceled if the order is refunded or enters refund-in-progress during the refund window.
- Repeated settlement evaluation is idempotent.

**State transitions**:

- Qualifying paid order -> `pending`
- `pending` + refund period passed + no refund started -> `settled`
- `pending` + refund/refund-in-progress inside refund period -> `canceled`
- `settled` + later exceptional reversal -> `reversed` only through explicit admin/support handling

## Commission Account

Represents a user's aggregate commission balances.

**Attributes**:

- `userId`: account owner
- `pendingCent`: commission waiting for refund-window clearance
- `withdrawableCent`: settled commission available for withdrawal
- `reservedCent`: amount reserved by pending withdrawal requests
- `paidOutCent`: amount successfully withdrawn
- `canceledCent`: amount canceled before settlement
- `updatedAt`: last balance update time

**Validation rules**:

- Balance changes are derived from commission and withdrawal ledger transitions.
- Withdrawable balance increases only when commission settles.
- Withdrawal reservation moves funds from withdrawable to reserved.
- Withdrawal success moves funds from reserved to paid out.
- Withdrawal failure moves funds from reserved back to withdrawable.
- No operation may make any balance bucket negative.

## Withdrawal Request

Represents a user's attempt to withdraw settled commission to WeChat Pay.

**Attributes**:

- `withdrawalId`: local withdrawal identifier
- `userId`: requester and commission account owner
- `amountCent`: requested withdrawal amount
- `targetType`: `wechat_pay`
- `wechatOpenId` or verified receiving identity reference
- `status`: `pending`, `processing`, `succeeded`, `failed`, or `canceled`
- `providerTransferNo`: provider transfer identifier, if submitted
- `failureReason`: user/admin-readable failure reason when failed
- `createdAt`, `submittedAt`, `completedAt`

**Validation rules**:

- User must have enough withdrawable balance.
- User must provide or have a verified user-owned WeChat Pay receiving identity.
- The amount is reserved before provider submission.
- Provider success finalizes the payout and increases paid-out balance.
- Provider failure releases the reserved amount back to withdrawable balance.
- Duplicate provider callbacks or sync results are idempotent.

## WeChat Pay Receiving Identity

Represents the payout target for withdrawals.

**Attributes**:

- `userId`: owner
- `openId` or provider receiving identifier
- `displayName` or masked label
- `verifiedAt`
- `status`: `active`, `invalid`, or `revoked`

**Validation rules**:

- Withdrawals can use only an active receiving identity owned by the requesting user.
- Invalid or missing receiving identity blocks withdrawal before funds are reserved.
