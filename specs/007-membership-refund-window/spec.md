# Feature Specification: Membership Refund Window

**Feature Branch**: `007-membership-refund-window`  
**Created**: 2026-05-05  
**Status**: Draft  
**Input**: User description: "加一个退款期1天，过了退款期不能再申请退款"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Refund Within Window (Priority: P1)

As a member who just completed a paid membership order, I can still request a refund within one day of successful payment so that there is a clear, time-bounded refund policy.

**Why this priority**: This defines the core business rule change and preserves the primary refund path for eligible paid orders.

**Independent Test**: Can be fully tested by creating a paid membership order, submitting a refund request within 24 hours of payment, and confirming the refund flow proceeds normally.

**Acceptance Scenarios**:

1. **Given** a membership order has been successfully paid less than 24 hours ago, **When** an eligible refund request is submitted, **Then** the system accepts the refund request and continues the existing refund flow.
2. **Given** a membership order has been successfully paid less than 24 hours ago, **When** an administrator submits a refund request from the admin membership workspace, **Then** the request is accepted under the same refund-window rule.

---

### User Story 2 - Block Refund After Window (Priority: P1)

As an operator or member attempting to refund an older paid membership order, I am prevented from starting a new refund after the one-day refund period so that refund policy enforcement is consistent and predictable.

**Why this priority**: Without this rule, the new refund-period requirement is not actually enforced.

**Independent Test**: Can be fully tested by using a paid membership order whose payment time is more than 24 hours old and confirming that a new refund attempt is rejected with a clear reason.

**Acceptance Scenarios**:

1. **Given** a membership order was successfully paid more than 24 hours ago and no refund has already been started, **When** a refund request is submitted, **Then** the system rejects the request and explains that the refund period has expired.
2. **Given** a membership order is outside the refund window, **When** an administrator tries to initiate a refund from the admin membership workspace, **Then** the request is rejected with the same refund-window rule.

---

### User Story 3 - Continue In-Flight Refund Handling (Priority: P2)

As an operator handling payment-provider callbacks or status sync, I can continue processing a refund that was started in time even if the one-day window has passed since payment so that already-started refunds are not stranded mid-process.

**Why this priority**: The refund window should limit new refund initiation, not break completion of refunds that were already accepted.

**Independent Test**: Can be fully tested by starting a refund inside the one-day window, advancing time beyond the window, and confirming refund-status sync or callback completion still succeeds.

**Acceptance Scenarios**:

1. **Given** a refund was accepted within the one-day refund period and is waiting on provider completion, **When** the system later receives refund completion information after the window has passed, **Then** it continues the existing refund-completion flow normally.
2. **Given** a refund is already in a refund-in-progress state, **When** an operator synchronizes refund status after the one-day window has passed, **Then** the system updates the refund state instead of rejecting it as a late new request.

---

### Edge Cases

- A paid order exactly 24 hours after payment is treated consistently by one explicit boundary rule; the refund window includes times up to 24 hours from successful payment and rejects anything later.
- Orders that were never successfully paid cannot use the refund path and continue following their existing non-paid order handling.
- Orders already in a refund-in-progress or refunded state do not restart a new refund-window check as if they were fresh refund requests.
- If payment success time is missing or cannot be determined for a supposedly paid order, the system rejects starting a new refund rather than guessing eligibility.
- Refund-window enforcement applies equally to supported payment methods and to admin-initiated refund entry points.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define a membership refund period of 1 day starting from the successful payment time of a paid membership order.
- **FR-002**: The system MUST allow a new refund request to start only when the paid membership order is still within that 1-day refund period.
- **FR-003**: The system MUST reject any new refund request submitted after the 1-day refund period has expired.
- **FR-004**: The system MUST apply the same 1-day refund-period rule to every product entry point that can initiate a membership refund, including member-facing and admin-facing refund initiation flows.
- **FR-005**: The system MUST provide a clear human-readable reason when a refund request is rejected because the refund period has expired.
- **FR-006**: The system MUST continue processing refunds that were already accepted within the refund period, even if provider callbacks, reconciliation, or status synchronization happen after the 1-day window has passed.
- **FR-007**: The system MUST evaluate refund-window eligibility using the order's successful payment time, not the order creation time.
- **FR-008**: The system MUST treat orders without a valid successful payment time as ineligible for starting a new refund request.
- **FR-009**: The system MUST preserve all existing membership entitlement rollback, coupon restoration, reward reversal, and audit behavior for refunds that are still eligible and accepted.

### Key Entities *(include if feature involves data)*

- **Membership Refund Window**: The business rule that determines whether a new refund request may begin, based on the elapsed time since successful payment.
- **Membership Order**: A paid membership transaction whose payment-success time, refund state, and eligibility determine whether a refund can be initiated.
- **Refund Attempt**: A refund action that is either newly initiated and subject to the one-day rule, or already in progress and allowed to continue through completion.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of newly submitted refund requests for paid membership orders older than 24 hours are rejected before a new refund process begins.
- **SC-002**: 100% of newly submitted refund requests for paid membership orders within 24 hours of successful payment can proceed through the existing refund flow.
- **SC-003**: Operators can determine from the user-facing response in one step whether a refund was blocked specifically because the refund period expired.
- **SC-004**: Refunds that were accepted within the refund period continue to completion without being stranded by later callback or synchronization steps after the 24-hour threshold.

## Assumptions

- The one-day refund period means 24 consecutive hours from the order's successful payment time.
- The current membership product keeps its existing pricing, plans, entitlement duration, and refund side effects; this change only adds refund-window eligibility.
- Existing admin refund tools remain available, but they must obey the same refund-window rule when starting a new refund.
- Existing close-order, payment-sync, and non-paid order handling stay unchanged unless they directly initiate a refund.
