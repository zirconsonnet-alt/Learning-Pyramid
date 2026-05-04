# Research: Membership Refund Window

## Decision: Use Successful Payment Time As The Refund-Window Anchor

**Rationale**: The feature defines refund eligibility relative to when the membership order was actually paid, not when it was created. Existing paid orders already carry a `paid_at` value, and provider confirmations also supply payment success time. Using this timestamp aligns the business rule with the user's paid entitlement and avoids penalizing users for time spent in pending payment.

**Alternatives considered**:

- Use order creation time: rejected because pending orders may be created well before payment and would shorten the actual refund period.
- Use entitlement start time: rejected because renewals may start in the future when a member already has active time remaining.
- Use latest payment row creation time: rejected because it is an operational record and may not equal provider-confirmed success time.

## Decision: Interpret 1 Day As 24 Hours Inclusive At The Boundary

**Rationale**: A precise 24-hour rule is testable and avoids ambiguity across dates and time zones. The refund remains eligible at exactly 24 hours after successful payment and becomes ineligible immediately after that instant.

**Alternatives considered**:

- Calendar-day refund period ending at local midnight: rejected because users who pay late in the day would receive a shorter refund period.
- Date-only comparison: rejected because it is ambiguous across time zones and hard to verify consistently.
- Exclusive 24-hour boundary: rejected because "within 1 day" is more naturally represented as allowing the exact endpoint.

## Decision: Enforce Eligibility In The Membership Store

**Rationale**: The admin router currently initiates refunds for manual and provider-backed orders, while future member-facing refund endpoints may reuse the same store operations. Placing the rule in the membership store makes it authoritative and prevents bypass through another refund initiation path.

**Alternatives considered**:

- Admin-router-only enforcement: rejected because it would not protect other initiation paths and would duplicate policy logic.
- Payment-service-only enforcement: rejected because manual/test refunds and local state transitions also need the same rule.

## Decision: Check Only New Refund Initiation, Not In-Flight Completion

**Rationale**: The spec explicitly requires accepted refunds to continue through callbacks, reconciliation, and sync after the window passes. The rule should block starting a new refund for paid orders outside the window, while `refund_pending` orders can still synchronize to `refunded` or recover to `paid` if the provider reports failure.

**Alternatives considered**:

- Recheck the window on every refund sync: rejected because provider processing can legitimately complete after the user's eligible request time.
- Freeze late `refund_pending` orders: rejected because it strands accepted refunds and conflicts with payment-provider workflows.

## Decision: Avoid New Persistent Fields

**Rationale**: Eligibility can be derived from existing `paid_at`, `status`, and payment refund request fields. Adding a `refund_deadline` column would duplicate derived state and require migration for little value in this narrow feature.

**Alternatives considered**:

- Store `refund_deadline_at`: rejected because it can drift if historical payment data is corrected and would require schema changes.
- Store per-order refund policy snapshot: rejected for this single-plan membership model; policy versioning can be revisited when multiple plans or legal terms require it.
