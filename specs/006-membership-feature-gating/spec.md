# Feature Specification: Membership Feature Gating

**Feature Branch**: `006-membership-feature-gating`  
**Created**: 2026-05-05  
**Status**: Draft  
**Input**: User description: "会员可以用AI功能{配置LLM，AI问答，播放器AI问答}和番茄钟功能，非会员不可以。这就是区别。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Members Use Member-Only Features (Priority: P1)

As an active member, I can access the AI-related features and Pomodoro features that are included in my membership so that paying for membership gives me a clear, usable benefit.

**Why this priority**: This is the core value of the feature. Without active members being able to use the gated features, membership has no practical benefit.

**Independent Test**: Can be fully tested by signing in as a user with active membership and opening each protected feature: LLM configuration, AI Q&A, player AI Q&A, and Pomodoro.

**Acceptance Scenarios**:

1. **Given** a signed-in user has an active membership, **When** they open LLM configuration, **Then** they can view and change LLM-related settings normally.
2. **Given** a signed-in user has an active membership, **When** they open AI Q&A from a project, **Then** they can ask questions and receive answers normally.
3. **Given** a signed-in user has an active membership, **When** they open AI Q&A from the media player, **Then** they can use player-context AI Q&A normally.
4. **Given** a signed-in user has an active membership, **When** they open Pomodoro, **Then** they can use the Pomodoro workflow normally.

---

### User Story 2 - Non-Members Are Blocked From Member-Only Features (Priority: P1)

As a signed-in non-member, I am blocked from using member-only AI and Pomodoro features and shown a clear path to membership so that I understand why the feature is unavailable.

**Why this priority**: The requested business distinction is that non-members cannot use these features. This must be enforced consistently, not only described.

**Independent Test**: Can be fully tested by signing in as a user who has never purchased membership or whose membership has expired, then attempting to use each protected feature.

**Acceptance Scenarios**:

1. **Given** a signed-in user has never purchased membership, **When** they open LLM configuration, **Then** they cannot view or change LLM-related settings and are told the feature is member-only.
2. **Given** a signed-in user has an expired membership, **When** they try to use AI Q&A, **Then** the question is not accepted and they are told membership is required.
3. **Given** a signed-in user has no active membership, **When** they try to use player AI Q&A, **Then** the AI interaction is blocked before a paid or compute-heavy action begins.
4. **Given** a signed-in user has no active membership, **When** they open Pomodoro, **Then** they cannot start or continue Pomodoro usage and are shown a way to open the membership center.

---

### User Story 3 - Membership Changes Take Effect Quickly (Priority: P2)

As a user who buys, renews, expires, or refunds membership, my access to member-only features follows my current membership state so that permissions match the paid entitlement.

**Why this priority**: Membership gating must stay aligned with the existing membership lifecycle; otherwise paid users may be blocked or refunded users may keep access.

**Independent Test**: Can be fully tested by changing a user's membership status through existing membership flows and re-checking access to the protected feature set.

**Acceptance Scenarios**:

1. **Given** a non-member completes a successful membership purchase, **When** they next try a member-only feature, **Then** access is allowed.
2. **Given** a member's membership expires, **When** they next try a member-only feature, **Then** access is blocked.
3. **Given** a member's order is refunded and the entitlement is revoked, **When** they next try a member-only feature, **Then** access is blocked.

---

### User Story 4 - Existing Ungated Learning Workflows Continue Working (Priority: P3)

As a signed-in non-member, I can still use learning workflows that are not part of the member-only feature list so that the change is limited to the intended distinction.

**Why this priority**: The feature should enforce the requested membership difference without unexpectedly reducing access to unrelated parts of the product.

**Independent Test**: Can be tested by signing in as a non-member and using regular project, subject, review, and profile flows that do not invoke AI Q&A, LLM configuration, player AI Q&A, or Pomodoro.

**Acceptance Scenarios**:

1. **Given** a signed-in non-member, **When** they open project dashboards, learning materials, normal workbench views, review recommendations, profile, or membership center, **Then** those unrelated flows remain available.
2. **Given** a signed-in non-member, **When** they interact with a feature outside the protected list, **Then** they are not shown a member-only block unless that interaction starts one of the protected capabilities.

### Edge Cases

- A user with an expired membership but a past paid order is treated as a non-member for protected feature access.
- A user with a pending, closed, refunded, or failed membership order is treated as a non-member unless they also have another active entitlement.
- A membership purchase, renewal, refund, or expiration that changes entitlement state is reflected on the next protected feature attempt.
- If membership status cannot be loaded, protected features fail closed with a clear retry or membership-center message rather than allowing non-member access.
- Direct access to protected features is blocked even if the user bypasses navigation or opens a saved URL.
- Unauthenticated users continue to follow the existing sign-in requirements before membership-specific eligibility is evaluated.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define LLM configuration, AI Q&A, player AI Q&A, and Pomodoro as member-only features.
- **FR-002**: The system MUST allow users with active membership to use all member-only features without new limitations introduced by this feature.
- **FR-003**: The system MUST prevent users without active membership from using LLM configuration.
- **FR-004**: The system MUST prevent users without active membership from using AI Q&A.
- **FR-005**: The system MUST prevent users without active membership from using player AI Q&A.
- **FR-006**: The system MUST prevent users without active membership from using Pomodoro.
- **FR-007**: The system MUST enforce membership access at the point where a protected action would be performed, not only by hiding entry points.
- **FR-008**: The system MUST show non-members a clear, human-readable explanation that the blocked feature requires active membership.
- **FR-009**: The system MUST provide non-members a clear path to open the membership center from blocked member-only feature experiences.
- **FR-010**: The system MUST treat never-purchased, expired, pending-order-only, closed-order-only, and refunded-order-only users as non-members for protected feature access.
- **FR-011**: The system MUST base access on the current active membership entitlement, including changes caused by successful purchase, renewal, expiration, refund, or entitlement revocation.
- **FR-012**: The system MUST keep unrelated learning, project, profile, review, settings unrelated to LLM configuration, and membership-management workflows available to non-members.
- **FR-013**: The system MUST avoid starting compute-heavy, billable, or state-changing protected work for a non-member after determining that membership is inactive.
- **FR-014**: The system MUST present a consistent member-only message across the protected feature set so users understand that the same membership rule applies.

### Key Entities

- **Membership Entitlement**: Represents whether a signed-in user currently has active membership access, including start time, end time, and active or expired state.
- **Protected Feature**: One of the product capabilities that requires active membership: LLM configuration, AI Q&A, player AI Q&A, and Pomodoro.
- **Access Decision**: The user-facing result of evaluating a signed-in user's current membership entitlement for a protected feature: allowed for active members, blocked for non-members.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of protected feature attempts by active members succeed at the same user-visible level as before this change.
- **SC-002**: 100% of protected feature attempts by non-members are blocked before the protected capability is used.
- **SC-003**: Non-members attempting a protected feature can identify why it is blocked and reach the membership center in no more than two user actions.
- **SC-004**: At least one active-member and one non-member acceptance test exists for each protected feature category before release.
- **SC-005**: Existing non-protected core learning flows continue to pass their current acceptance checks after the membership gating change.

## Assumptions

- "会员" means a signed-in user with an active membership entitlement, not merely a user who has ever paid in the past.
- "非会员" includes users who have never purchased membership, users with expired membership, and users whose only relevant orders are pending, closed, refunded, or otherwise inactive.
- The existing membership center remains the place where non-members can buy or renew membership.
- The protected feature list for this change is limited to LLM configuration, AI Q&A, player AI Q&A, and Pomodoro.
- Existing sign-in and account status rules remain in force and are evaluated before membership eligibility.
- This specification does not introduce new pricing, plans, quotas, coupons, or membership duration rules.
