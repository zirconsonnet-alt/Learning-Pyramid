# Data Model: Membership Refund Window

## Membership Order

Represents a paid membership transaction whose refund eligibility is evaluated.

**Existing attributes used by this feature**:

- `orderId`: unique membership order identifier
- `userId`: owner of the membership order
- `provider`: payment provider used for the order
- `status`: current order state, including `paid`, `refund_pending`, and `refunded`
- `paidAt`: successful payment timestamp used to anchor the refund window
- `refundedAt`: timestamp when refund completion is recorded
- `entitlementId`: membership entitlement affected by refund rollback

**Validation rules**:

- New refund initiation is allowed only when `status` is `paid` and `paidAt` is present and within the 24-hour refund window.
- Orders whose only state is `pending`, `closed`, `expired`, or otherwise not paid cannot start the refund flow.
- Orders with missing or invalid `paidAt` cannot start a new refund.
- Orders already `refund_pending` are in-flight refunds and are handled by refund synchronization/completion rules rather than new initiation rules.
- Orders already `refunded` remain idempotent when finalization is repeated.

## Membership Refund Window

Represents the business rule that determines whether a new refund request may begin.

**Attributes**:

- `startsAt`: the order's successful payment timestamp
- `endsAt`: `startsAt` plus 24 hours
- `isEligible`: true when the current request time is less than or equal to `endsAt`
- `expiredReason`: clear reason shown when a new refund is rejected after the window

**Validation rules**:

- The boundary is inclusive at exactly 24 hours after successful payment.
- Times are compared as absolute instants, not local calendar dates.
- The window applies equally to all supported payment providers and admin/member initiation paths.

## Refund Attempt

Represents an action involving refund initiation or refund completion.

**Attributes**:

- `orderId`: target membership order
- `attemptType`: `new_initiation`, `provider_status_sync`, or `provider_callback`
- `requestedAt`: time the action is evaluated
- `providerRefundNo`: provider refund identifier when available
- `result`: accepted, rejected as window expired, completed, pending, failed, or idempotent

**State transitions**:

- `paid` -> `refund_pending`: provider-backed refund is initiated within the 24-hour window and waits for provider completion.
- `paid` -> `refunded`: manual or immediately completed refund is initiated within the 24-hour window.
- `paid` -> rejected: new refund initiation happens after the 24-hour window.
- `refund_pending` -> `refunded`: provider sync or callback reports success, even after the 24-hour window.
- `refund_pending` -> `paid`: provider sync reports refund failure.
- `refunded` -> `refunded`: repeat finalization remains idempotent.

**Validation rules**:

- New refund initiation uses refund-window eligibility.
- Provider sync and callback completion do not use refund-window eligibility because they continue an already accepted refund.
- Accepted refunds preserve existing entitlement rollback, coupon restoration, reward reversal, and audit behavior.
