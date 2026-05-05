# Feature Specification: WeChat Payout Automation

**Feature Branch**: `009-wechat-payout-automation`  
**Created**: 2026-05-05  
**Status**: Draft  
**Input**: User description: "把无人值守佣金结算、微信收款身份绑定、新版微信商家转账提现、转账确认、回调或查单自动回写做成规格；没有绑定收款方式的用户不能直接提现。补充：产品主场景是电脑 Web 应用，用户首次提现前应在电脑端扫码，用本人手机微信完成收款账号绑定，之后提现不再填写 UID/OpenID。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bind WeChat Receiving Identity From Desktop Web (Priority: P1)

As an inviter who uses the desktop web application and wants to withdraw commission, I can click a bind action, scan a short-lived QR code with my own WeChat, confirm the account being bound, and complete an official WeChat authorization flow so that the platform knows where future payouts should be sent without requiring me to manually type a sensitive identifier.

**Why this priority**: A payout cannot be sent safely or correctly unless the user has first proven ownership of a receiving identity.

**Independent Test**: Can be fully tested by using a desktop account without a bound receiving identity, starting the binding flow, scanning the displayed QR code with WeChat, confirming the binding on the mobile WeChat page, and confirming that the desktop membership or invite area now shows the identity as bound and ready for withdrawals.

**Acceptance Scenarios**:

1. **Given** a logged-in desktop user has no bound WeChat receiving identity, **When** they open the commission withdrawal area, **Then** the primary action prompts them to bind WeChat before withdrawal can be requested.
2. **Given** an unbound desktop user starts binding, **When** the binding attempt is created, **Then** the desktop page shows a QR code that can be scanned with WeChat and clearly states that the scan binds the user's WeChat as the commission withdrawal account.
3. **Given** a user scans the QR code in WeChat, **When** the mobile binding page opens, **Then** the page identifies the LearningPyramid account being bound and asks the user to confirm before the identity can become active.
4. **Given** a user completes the WeChat authorization and confirmation flow successfully, **When** the platform receives the authorization result, **Then** the platform records a verified receiving identity for that logged-in desktop user and the desktop page updates to bound.
5. **Given** a user already has a verified WeChat receiving identity, **When** they view the commission withdrawal area, **Then** the platform shows that withdrawals can use the bound identity without exposing the full sensitive identifier.
6. **Given** authorization fails, is canceled, expires, is reused, or belongs to an invalid binding attempt, **When** the binding flow ends, **Then** no receiving identity is activated for withdrawal and the desktop page offers a safe retry.

---

### User Story 2 - Automatically Settle Eligible Commission (Priority: P1)

As an inviter, I do not need an administrator to manually settle commission after the refund window; eligible pending commission becomes withdrawable automatically after refund risk has passed.

**Why this priority**: This turns the existing commission ledger from an admin-triggered accounting step into a user-trustworthy reward system.

**Independent Test**: Can be fully tested by creating a qualifying invited membership payment, waiting until its refund window has passed without refund, and confirming the inviter's withdrawable balance increases without any admin settlement action.

**Acceptance Scenarios**:

1. **Given** an invited user's qualifying membership payment created a pending fixed 5 yuan commission, **When** the 24-hour refund window has passed without refund activity, **Then** the system settles that commission to the inviter's withdrawable balance automatically.
2. **Given** a qualifying payment is still inside the 24-hour refund window, **When** automatic settlement runs, **Then** the commission remains pending and withdrawable balance does not increase.
3. **Given** a qualifying payment was refunded or entered refund-in-progress inside the refund window, **When** automatic settlement runs, **Then** the pending commission is canceled or kept from becoming withdrawable.
4. **Given** automatic settlement evaluates the same commission more than once, **When** the commission was already settled or canceled, **Then** the inviter's balance is not changed a second time.

---

### User Story 3 - Request WeChat Withdrawal (Priority: P2)

As an inviter with withdrawable commission and a bound WeChat receiving identity, I can request a withdrawal and confirm receipt in WeChat so that my valid commission can be paid to my own WeChat account.

**Why this priority**: Withdrawable commission only creates real value when users can receive funds through a safe, provider-confirmed payout flow.

**Independent Test**: Can be fully tested by giving a user a verified receiving identity and withdrawable balance, submitting a withdrawal request, completing the WeChat confirmation step, and verifying that the requested amount is reserved while payout is pending.

**Acceptance Scenarios**:

1. **Given** a user has withdrawable commission and a verified WeChat receiving identity, **When** they submit a valid withdrawal amount, **Then** the platform creates a withdrawal request and reserves the requested balance so it cannot be withdrawn again.
2. **Given** a user submits a withdrawal request, **When** WeChat requires the user to confirm receipt, **Then** the platform provides the information needed for the user to complete confirmation in WeChat.
3. **Given** a user has no verified WeChat receiving identity, **When** they attempt withdrawal, **Then** the withdrawal is rejected before any balance is reserved and the user is guided to bind WeChat.
4. **Given** a user requests more than their withdrawable balance or below the allowed minimum amount, **When** they submit the withdrawal, **Then** the withdrawal is rejected with a clear reason and no balance is reserved.

---

### User Story 4 - Automatically Reconcile Payout Results (Priority: P2)

As a user and administrator, I can rely on withdrawal status updating automatically after WeChat finishes processing so that balances and records do not depend on manual admin updates.

**Why this priority**: Payouts involve external processing; automatic reconciliation prevents stuck records and incorrect available balances.

**Independent Test**: Can be fully tested by submitting withdrawal requests that end in success, failure, cancellation, and timeout-like states, then verifying that each result updates the user's balance and withdrawal history correctly without manual admin status changes.

**Acceptance Scenarios**:

1. **Given** a payout succeeds, **When** the platform receives or discovers the final success result, **Then** the withdrawal is marked succeeded and the reserved balance becomes paid out.
2. **Given** a payout fails, expires, or is rejected, **When** the platform receives or discovers the final failure result, **Then** the withdrawal is marked failed and the reserved balance returns to withdrawable balance.
3. **Given** the same payout result is received or discovered more than once, **When** the platform processes the duplicate result, **Then** balances and withdrawal status remain correct and are not applied twice.
4. **Given** a withdrawal remains processing beyond the expected confirmation or provider processing window, **When** reconciliation evaluates it, **Then** the platform refreshes its status or flags it for admin attention.

---

### User Story 5 - Admin Monitors Automated Settlement And Payouts (Priority: P3)

As an administrator, I can inspect automatic commission settlement, receiving identity status, withdrawal requests, payout results, and reconciliation warnings so that finance and support teams can explain every balance change.

**Why this priority**: Automation reduces manual work, but money movement still needs traceability and operational visibility.

**Independent Test**: Can be fully tested by generating pending, settled, canceled, processing, succeeded, failed, and warning records, then confirming the admin view can trace each record back to the user, invite relationship, membership order, and payout attempt.

**Acceptance Scenarios**:

1. **Given** commission was automatically settled or canceled, **When** an admin reviews commission records, **Then** the record shows the source order, refund-window deadline, outcome, and automation timestamp.
2. **Given** a user has bound or failed to bind a WeChat receiving identity, **When** an admin reviews payout readiness, **Then** the user identity status is visible without revealing unnecessary sensitive data.
3. **Given** a withdrawal has any final or processing status, **When** an admin reviews withdrawal records, **Then** the request amount, reserved amount, provider result, user confirmation state, timestamps, and failure reason if any are visible.
4. **Given** an automated reconciliation warning exists, **When** an admin reviews operations, **Then** the warning identifies the affected withdrawal and the recommended next action.

### Edge Cases

- Users without a verified WeChat receiving identity cannot withdraw, even if they have withdrawable commission.
- Users must not manually submit or edit raw WeChat receiving identifiers as the production payout path.
- Desktop users must be able to start binding without already being inside WeChat; the normal path is scanning a platform-generated binding QR code with mobile WeChat.
- Binding QR codes may expire, be scanned more than once, or be opened after cancellation; these attempts must not activate a receiving identity.
- The mobile WeChat binding page must make clear which platform account will receive the binding before the user confirms.
- A receiving identity can be replaced only through a fresh successful authorization flow.
- A receiving identity must be associated with the platform's payout-capable WeChat application context.
- Automatic settlement must preserve the existing invite commission rules: fixed 5 yuan commission, actual paid amount of at least 15 yuan, and 24-hour refund-window protection.
- Commission generated before this feature that is still pending should become eligible for automatic settlement if it satisfies the same refund-window and refund-status rules.
- Commission already settled, canceled, reversed, or paid out must not be modified by automatic settlement except through explicitly tracked correction flows.
- Withdrawal requests must remain traceable even if WeChat confirmation is abandoned by the user.
- Withdrawal failure after balance reservation must return the reserved amount exactly once.
- Provider notifications and provider status checks may arrive in different orders; the final withdrawal state must remain correct and auditable.
- If the external payout channel is unavailable, users should see a clear temporary-unavailable state and balances must remain intact.
- Admins may still need a manual exception workflow for disputed payout records, but normal success and failure paths should not require manual intervention.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST require a verified WeChat receiving identity before a user can request commission withdrawal.
- **FR-002**: The system MUST provide a user-facing WeChat binding flow that obtains the receiving identity through WeChat authorization rather than user-entered raw identifiers, with a desktop web primary path that uses a short-lived QR code opened in WeChat.
- **FR-003**: The system MUST show unbound desktop users a clear "bind WeChat before withdrawing" state in the commission withdrawal area and provide a retryable binding QR code when binding is available.
- **FR-004**: The system MUST store the user's receiving identity status, provider context, verification time, and latest binding outcome for payout readiness checks.
- **FR-005**: The system MUST protect the full receiving identity from unnecessary display in user-facing and admin-facing views.
- **FR-006**: The system MUST allow users to replace a receiving identity only after completing a new successful WeChat authorization flow.
- **FR-007**: The system MUST automatically evaluate pending invite commission after the existing 24-hour refund window.
- **FR-008**: The system MUST settle eligible pending commission to withdrawable balance without requiring an administrator to call a settlement action.
- **FR-009**: The system MUST keep the existing commission eligibility rules unchanged: invited membership payment, actual paid amount of at least 15 yuan, no refund started inside the refund window, and fixed 5 yuan commission per qualifying order.
- **FR-010**: The system MUST prevent automatic settlement from increasing a user's balance more than once for the same qualifying commission record.
- **FR-011**: The system MUST cancel or block commission from becoming withdrawable when the source payment is refunded or enters refund-in-progress during the refund window.
- **FR-012**: The system MUST include pending commission created before this automation feature in automatic settlement evaluation when those records are still valid and unsettled.
- **FR-013**: The system MUST allow a user with withdrawable balance and a verified WeChat receiving identity to submit a withdrawal request.
- **FR-014**: The system MUST validate withdrawal amount against available withdrawable balance, minimum payout amount, and provider availability before reserving funds.
- **FR-015**: The system MUST reserve the requested withdrawal amount immediately after accepting a withdrawal request so the same balance cannot be withdrawn twice.
- **FR-016**: The system MUST initiate a WeChat payout request only after the local withdrawal record and reserved balance are created successfully.
- **FR-017**: The system MUST support the WeChat user confirmation step required before a transfer can complete when that step is required by the payout channel.
- **FR-018**: The system MUST present the user's withdrawal request status as created, awaiting confirmation, processing, succeeded, failed, canceled, or needs admin attention.
- **FR-019**: The system MUST automatically update withdrawal status from WeChat payout notifications when final or intermediate results are received.
- **FR-020**: The system MUST automatically reconcile processing withdrawals by checking their current provider state when no timely notification has completed them.
- **FR-021**: The system MUST mark successful withdrawals as paid out and move the reserved amount to paid-out balance exactly once.
- **FR-022**: The system MUST return reserved funds to withdrawable balance exactly once when a withdrawal fails, expires, or is canceled before successful payout.
- **FR-023**: The system MUST process duplicate, delayed, or out-of-order payout results without double-changing balances.
- **FR-024**: The system MUST retain a complete audit trail for receiving identity binding attempts, automatic settlement decisions, withdrawal requests, provider results, and reconciliation actions.
- **FR-025**: The system MUST provide admin visibility into automated settlement outcomes, withdrawal status, provider result details, and records needing attention.
- **FR-026**: The system MUST clearly distinguish ordinary user-action failures from operational failures that require admin or finance intervention.
- **FR-027**: The system MUST keep all commission and withdrawal amounts precise to cents in calculation, storage, and display.
- **FR-028**: The system MUST avoid changing invite discount coupon behavior, membership price behavior, and fixed 5 yuan commission calculation except where required for unattended settlement and withdrawal automation.
- **FR-029**: The system MUST require the mobile WeChat binding confirmation page to identify the LearningPyramid account being bound before a receiving identity can become active.
- **FR-030**: The system MUST reject expired, canceled, reused, or invalid binding attempts without activating or replacing a receiving identity.

### Key Entities *(include if feature involves data)*

- **WeChat Receiving Identity**: A verified payout target owned by a user, including provider context, masked display value, verification status, binding timestamps, and latest failure reason if any.
- **Binding Attempt**: A traceable attempt to connect a user's account with a WeChat receiving identity, including start time, QR scan or authorization state, completion status, expiry, and outcome.
- **Commission Record**: The existing invite commission record that may be pending, settled, canceled, reversed, or paid out; this feature adds automated settlement decision tracking.
- **Commission Account**: The user's commission balance summary, including pending, withdrawable, reserved, paid-out, canceled, and correction amounts.
- **Withdrawal Request**: A user-initiated request to transfer withdrawable commission to WeChat, including requested amount, receiving identity, status, confirmation state, provider result, and timestamps.
- **Payout Result**: A provider-side status update or reconciliation result associated with a withdrawal request.
- **Reconciliation Warning**: An operational record for withdrawals that cannot be resolved automatically within the expected window or need finance review.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of withdrawal attempts by users without a verified WeChat receiving identity are blocked before funds are reserved.
- **SC-002**: At least 95% of desktop users who scan the binding QR code and complete WeChat authorization successfully see their withdrawal readiness update within 10 seconds.
- **SC-003**: 100% of valid pending commission records that pass the 24-hour refund window without refund become withdrawable without admin settlement action.
- **SC-004**: 0 commission records are settled more than once when automatic settlement evaluates the same record repeatedly.
- **SC-005**: 100% of accepted withdrawal requests reserve the requested amount before payout initiation.
- **SC-006**: 100% of successful payouts move reserved balance to paid-out balance exactly once.
- **SC-007**: 100% of failed, expired, or canceled payouts return reserved balance to withdrawable balance exactly once.
- **SC-008**: At least 99% of payout results reach a final user-visible status within 30 minutes of provider completion.
- **SC-009**: Administrators can trace any commission balance change or withdrawal status change to its source event in one admin workflow.
- **SC-010**: User support tickets about "commission passed the refund window but is not withdrawable" decrease by at least 80% after the automation is enabled.
- **SC-011**: 100% of expired, canceled, reused, or invalid binding attempts fail without activating or replacing a WeChat receiving identity.

## Assumptions

- This feature builds on the existing invite commission model from `specs/008-invite-commission`: invited users can receive a 7.5-discount coupon, monthly membership base price is 20 yuan, qualifying paid amount is at least 15 yuan, and inviter commission is fixed at 5 yuan.
- The refund protection window remains the existing 24-hour window after successful membership payment.
- "无人值守" means normal commission settlement and payout result updates do not require an admin button or manual status edit.
- The platform has or will obtain the necessary WeChat merchant payout capability and configured payout scene for commission-like payments.
- The primary production user surface is the desktop web application; mobile WeChat is used only when the user scans a binding or confirmation prompt that must run inside WeChat.
- The platform has or will obtain a WeChat application identity that can support the official authorization flow required to resolve the receiving identity for payout.
- Binding QR codes are short-lived, single-purpose entry points for proving WeChat identity; they are not payment collection codes and do not transfer money.
- The production user experience does not allow manually typed raw WeChat receiving identifiers as the primary payout binding method.
- A withdrawal may require the user to complete a WeChat-side confirmation step before funds are paid.
- Existing pending commission records should be handled by the new automation if they satisfy the same eligibility rules.
- Manual admin intervention remains available only for exceptions, disputes, or records that automated reconciliation cannot safely resolve.
