# Feature Specification: Invite Discount And Commission

**Feature Branch**: `008-invite-commission`  
**Created**: 2026-05-05  
**Status**: Draft  
**Input**: User description: "现在是邀请用户的5元券，这个机制改掉，改成绑定邀请码得7.5折券，会员初始价格改成20元，然后建立佣金机制，所邀请的用户付费达到15元，并且在退款期内没有退款，则在退款期过后结算到用户账户，用户可以提现到自己的微信支付"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Invitee Gets Discount Coupon (Priority: P1)

As a new or not-yet-purchased user who binds an invite code, I receive a 7.5-discount membership coupon so that binding an invite code immediately gives me a clear purchase benefit.

**Why this priority**: This replaces the current invite reward model and directly affects the purchase price that invited users see.

**Independent Test**: Can be fully tested by registering or binding with a valid invite code before the first paid membership order, opening membership purchase, and verifying that a 7.5-discount coupon is available and can reduce the new 20 yuan membership price to 15 yuan.

**Acceptance Scenarios**:

1. **Given** a user has not purchased membership and has no existing invite binding, **When** they bind a valid invite code, **Then** the system records the invite relationship and grants that user one available 7.5-discount membership coupon.
2. **Given** an invited user has an available 7.5-discount coupon and the membership monthly price is 20 yuan, **When** they preview or create a membership order with that coupon, **Then** the payable amount is 15 yuan.
3. **Given** a user has already bound an invite code, **When** they try to bind another invite code, **Then** the system rejects the second binding and does not grant another invite discount coupon.

---

### User Story 2 - Replace Inviter Coupon Reward With Commission (Priority: P1)

As an inviter, I earn commission from invited users who complete enough paid membership spend and do not refund during the refund period, so that invitation rewards become cash-settled rather than coupon-based.

**Why this priority**: This is the core business model change: the inviter no longer receives a 5 yuan coupon when an invitee purchases; the inviter earns a cash commission after refund risk has passed.

**Independent Test**: Can be fully tested by inviting a user, having that user pay at least 15 yuan for membership, waiting until the one-day refund period passes without refund, and confirming that commission is settled to the inviter's account.

**Acceptance Scenarios**:

1. **Given** an invited user successfully pays at least 15 yuan for membership, **When** the one-day refund period has not yet passed, **Then** the inviter's commission remains pending and withdrawable balance does not increase.
2. **Given** an invited user successfully pays at least 15 yuan for membership and no refund is started within the one-day refund period, **When** the refund period passes, **Then** the system settles commission to the inviter's account.
3. **Given** an invited user's qualifying membership order is refunded or enters refund-in-progress during the refund period, **When** commission settlement is evaluated, **Then** no commission is settled for that order.
4. **Given** an invited user pays less than 15 yuan in a membership order, **When** commission settlement is evaluated, **Then** the order does not trigger inviter commission.

---

### User Story 3 - Inviter Withdraws To WeChat Pay (Priority: P2)

As an inviter with settled commission, I can request withdrawal to my own WeChat Pay account so that invitation earnings can leave the platform.

**Why this priority**: Settlement creates user value only if users can access their earnings. This depends on the commission balance from User Story 2.

**Independent Test**: Can be fully tested by giving a user settled withdrawable commission, binding or confirming their WeChat Pay receiving identity, submitting a withdrawal request, and verifying the withdrawal status and balance updates.

**Acceptance Scenarios**:

1. **Given** a user has settled withdrawable commission, **When** they submit a valid withdrawal request to their WeChat Pay account, **Then** the system creates a withdrawal request and reserves the requested amount from withdrawable balance.
2. **Given** a withdrawal succeeds, **When** the result is recorded, **Then** the user's reserved amount becomes paid out and the withdrawal record shows success.
3. **Given** a withdrawal fails or is rejected, **When** the result is recorded, **Then** the reserved amount is returned to the user's withdrawable balance and the withdrawal record shows the failure reason.

---

### User Story 4 - Admin Audits Invite Revenue And Payouts (Priority: P3)

As an administrator, I can inspect invite bindings, discount coupons, commission settlement, and withdrawals so that customer support and financial reconciliation can explain each reward and payout.

**Why this priority**: Commission and withdrawal flows affect money movement and need administrative traceability, but user purchase and settlement behavior can be validated first.

**Independent Test**: Can be fully tested by generating invited purchase, pending commission, settled commission, and withdrawal records, then confirming administrators can find the related users, orders, statuses, and amounts.

**Acceptance Scenarios**:

1. **Given** an invitee binds an invite code and receives a discount coupon, **When** an administrator views invite records, **Then** the binding and coupon are visible with their current statuses.
2. **Given** a qualifying invitee order is pending settlement or settled, **When** an administrator views commission records, **Then** the inviter, invitee, order, payable amount, refund-window deadline, commission amount, and status are visible.
3. **Given** a user submits a withdrawal, **When** an administrator views withdrawal records, **Then** the request amount, target WeChat identity, status, timestamps, and failure reason if any are visible.

### Edge Cases

- Existing invite reward coupons issued under the old 5 yuan inviter-coupon mechanism remain historically visible, but new invite events after this feature uses the new invitee-discount and inviter-commission mechanism.
- A user can bind only one inviter, and one invite relationship can grant only one invitee discount coupon.
- The 7.5-discount coupon is usable for membership orders only and should not reduce the payable amount below zero.
- The commission threshold is evaluated using actual successful membership payment amount after discounts, not the list price.
- An order paid exactly 15 yuan qualifies for commission threshold evaluation.
- Commission is not settled while the order is still inside the one-day refund period.
- If a refund is started inside the refund period but completes after the refund period, commission remains blocked for that order.
- If settlement evaluation runs more than once for the same qualifying order, the inviter receives commission only once.
- If a user tries to withdraw more than their withdrawable balance, the withdrawal request is rejected.
- If the user's WeChat Pay receiving identity is missing, invalid, or not owned by the user, withdrawal is rejected before funds are reserved.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST replace the current new invite reward behavior so that new invite bindings grant the invited user a 7.5-discount membership coupon instead of granting the inviter a 5 yuan coupon.
- **FR-002**: The system MUST set the membership monthly base price used for new orders and price previews to 20 yuan.
- **FR-003**: The system MUST calculate a 7.5-discount coupon against the membership order amount so that a 20 yuan membership order becomes 15 yuan when the coupon is applied.
- **FR-004**: The system MUST grant at most one invite discount coupon for a user who successfully binds an invite code.
- **FR-005**: The system MUST prevent users from binding their own invite code.
- **FR-006**: The system MUST preserve existing invite-code binding entry points, including registration-time binding and pre-first-order manual binding, while changing the reward outcome.
- **FR-007**: The system MUST stop issuing new inviter-side 5 yuan invite reward coupons after this feature takes effect.
- **FR-008**: The system MUST keep historical old-model coupons and invite records readable for users and administrators.
- **FR-009**: The system MUST create a pending commission record when an invited user's successful membership payment reaches at least 15 yuan and the invite relationship has not already generated commission for that qualifying order.
- **FR-010**: The system MUST base the 15 yuan commission threshold on the actual paid amount after discounts and coupons.
- **FR-011**: The system MUST keep commission pending until the one-day refund period for the qualifying order has passed.
- **FR-012**: The system MUST settle pending commission to the inviter's account only when the qualifying order has not been refunded and no refund has been started inside the refund period.
- **FR-013**: The system MUST void or cancel pending commission for a qualifying order if that order is refunded or enters refund-in-progress during the refund period.
- **FR-014**: The system MUST ensure that each qualifying invitee order can settle commission at most once.
- **FR-015**: The system MUST track commission account balances separately as pending, withdrawable, reserved-for-withdrawal, paid-out, and canceled amounts.
- **FR-016**: The system MUST allow users with withdrawable commission balance to submit withdrawal requests to their own WeChat Pay account.
- **FR-017**: The system MUST reject withdrawal requests that exceed the user's withdrawable balance.
- **FR-018**: The system MUST reserve the withdrawal amount while a withdrawal request is pending so that the same balance cannot be withdrawn twice.
- **FR-019**: The system MUST return reserved funds to withdrawable balance if a withdrawal fails or is rejected.
- **FR-020**: The system MUST record a clear status history for commission settlement and withdrawal records for user support and admin reconciliation.
- **FR-021**: The system MUST expose user-facing views of invite discount coupon status, commission balance, commission history, and withdrawal history.
- **FR-022**: The system MUST expose admin-facing views of invite bindings, invite discount coupons, commission records, and withdrawal records.
- **FR-023**: The system MUST keep all monetary amounts in yuan-equivalent values precise to cents for display and calculation.
- **FR-024**: The system MUST settle a fixed 5 yuan commission for each qualifying invitee membership order that reaches the commission threshold and passes the refund window without refund.

### Key Entities *(include if feature involves data)*

- **Invite Binding**: The relationship between an inviter and an invitee, including the invite code used, binding time, binding source, and whether it has already produced discount or commission outcomes.
- **Invite Discount Coupon**: A 7.5-discount membership coupon granted to an invitee after a successful invite-code binding.
- **Membership Price Snapshot**: The order-time record of membership base price, discount coupon, payable amount, and payment status.
- **Commission Record**: A record connecting inviter, invitee, qualifying membership order, paid amount, refund-window deadline, fixed 5 yuan commission amount, and status such as pending, settled, canceled, or reversed.
- **Commission Account**: The inviter's monetary balance summary, including pending, withdrawable, reserved, paid-out, and canceled amounts.
- **Withdrawal Request**: A user's request to withdraw settled commission to their own WeChat Pay account, including amount, target identity, status, timestamps, and failure reason.
- **WeChat Pay Receiving Identity**: The verified WeChat Pay identity or payout target that proves where a user's withdrawal should be sent.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of new successful invite-code bindings for users without a prior binding grant exactly one 7.5-discount membership coupon to the invitee.
- **SC-002**: 100% of new membership price previews and orders use 20 yuan as the base monthly price after this feature takes effect.
- **SC-003**: 100% of invited users applying the 7.5-discount coupon to a 20 yuan membership order see a payable amount of 15 yuan.
- **SC-004**: 0 new inviter-side 5 yuan invite reward coupons are issued after this feature takes effect.
- **SC-005**: 100% of qualifying invited orders with actual paid amount of at least 15 yuan remain pending until the one-day refund period passes.
- **SC-006**: 100% of qualifying invited orders that are refunded or enter refund-in-progress inside the refund period do not increase inviter withdrawable commission.
- **SC-007**: 100% of qualifying invited orders that pass the refund period without refund settle commission to the inviter exactly once.
- **SC-008**: Users can view current commission balance and submit a valid WeChat Pay withdrawal request in no more than three user actions from the membership or invite area.
- **SC-009**: Administrators can trace any settled commission or withdrawal request back to inviter, invitee, and source membership order in one admin workflow.

## Assumptions

- "会员初始价格改成20元" means the monthly membership base price for new price previews and orders becomes 20 yuan.
- "7.5折券" means a percentage discount coupon that charges 75% of the applicable membership price before any other coupon-like discount.
- The 15 yuan threshold is evaluated against actual successful membership payment amount after discount, so a 20 yuan order using the 7.5-discount coupon qualifies at exactly 15 yuan.
- The inviter commission for each qualifying order is a fixed 5 yuan amount.
- The refund period is the existing one-day membership refund period, defined as 24 hours from successful payment time.
- Commission is generated for membership payments only, not for other future paid products.
- Each invite relationship can produce commission from at most one qualifying membership order unless a later clarification explicitly asks for recurring commission.
- Withdrawal to WeChat Pay requires a user-owned WeChat Pay receiving identity; detailed identity verification and payout provider requirements will be planned after the business rules are confirmed.
- Existing old-model coupons and invite records are not migrated into commission automatically unless separately requested.
