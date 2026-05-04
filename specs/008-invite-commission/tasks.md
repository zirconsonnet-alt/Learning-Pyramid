# Tasks: Invite Discount And Commission

**Input**: Design documents from `/specs/008-invite-commission/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: This feature changes pricing, invite rewards, commission settlement, and payout behavior, so targeted backend/API regression tests are required before and alongside implementation. Frontend static contract coverage should be updated when user/admin API schemas or copy expectations change.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this belongs to (e.g. `[US1]`, `[US2]`)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Refresh the active feature context and confirm the invite discount / commission artifacts are the implementation target.

- [x] T001 Confirm `.specify/feature.json` points to `specs/008-invite-commission` in `.specify/feature.json`
- [x] T002 Review `specs/008-invite-commission/spec.md`, `specs/008-invite-commission/plan.md`, `specs/008-invite-commission/research.md`, `specs/008-invite-commission/data-model.md`, `specs/008-invite-commission/contracts/invite-commission-api.md`, and `specs/008-invite-commission/quickstart.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish shared pricing, coupon-type, commission ledger, withdrawal, and DTO primitives required by all stories.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Add additive commission ledger, commission account, withdrawal request, and payout identity storage scaffolding in `backend/system/membership_commission_store.py`
- [x] T004 [P] Extend invite/coupon storage types for invite discount coupons and historical compatibility in `backend/system/membership_marketing_store.py`
- [x] T005 [P] Add shared request/response schemas for commission and withdrawal flows in `adapter/schemas.py`
- [x] T006 [P] Wire new store/service dependencies into `adapter/deps.py`
- [x] T007 [P] Extend membership and admin API client schemas for commission, withdrawal, and invite discount coupon contracts in `frontend/src/ui/api/membership.ts` and `frontend/src/ui/api/admin.ts`
- [x] T008 [P] Add shared backend time-control and payout test helpers for commission settlement and withdrawal flows in `tests/test_membership_api.py` and `tests/test_admin_api.py`

**Checkpoint**: Shared pricing, invite discount coupon model, commission ledger, and withdrawal scaffolding are ready for story-specific work.

---

## Phase 3: User Story 1 - Invitee Gets Discount Coupon (Priority: P1) 🎯 MVP

**Goal**: A user who binds an invite code receives one 7.5-discount membership coupon, and membership pricing changes to 20 yuan so the coupon reduces payable amount to 15 yuan.

**Independent Test**: Register or bind with a valid invite code before first paid order, verify one invite discount coupon is issued, confirm no new inviter 5 yuan coupon is created, and verify preview/order pricing is 20 yuan base with 15 yuan payable when the coupon is used.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T009 [P] [US1] Add invite binding, invite discount coupon issuance, and duplicate-binding regression tests in `tests/test_membership_api.py`
- [x] T010 [P] [US1] Add admin visibility coverage for invite discount coupons and no-new-inviter-reward behavior in `tests/test_admin_api.py`
- [x] T011 [P] [US1] Update frontend membership/admin schema or copy regression coverage for invite discount coupon and 20 yuan pricing references in `tests/test_frontend_llm_settings_location.py`

### Implementation for User Story 1

- [x] T012 [US1] Replace 19.9/14.9 first-order pricing with 20 yuan pricing snapshots in `backend/system/membership_store.py`
- [x] T013 [US1] Implement invite discount coupon issuance, coupon typing, and coupon discount resolution for 7.5-discount coupons in `backend/system/membership_marketing_store.py`
- [x] T014 [US1] Update membership invite and coupon DTOs to expose invite discount coupon fields in `adapter/routers/membership.py`
- [x] T015 [US1] Update admin invite and coupon DTOs to expose invite discount coupon fields in `adapter/routers/admin.py`
- [x] T016 [US1] Update membership client queries and purchase/profile UI to show 20 yuan pricing and invite discount coupon messaging in `frontend/src/ui/queries/membership.ts`, `frontend/src/views/membership/MembershipPage.tsx`, `frontend/src/views/membership/components/MembershipPurchaseDialog.tsx`, `frontend/src/views/membership/components/MembershipProfilePanel.tsx`, and `frontend/src/views/membership/membershipUi.tsx`

**Checkpoint**: Invite discount coupon issuance and 20 yuan membership pricing are independently functional.

---

## Phase 4: User Story 2 - Replace Inviter Coupon Reward With Commission (Priority: P1)

**Goal**: Qualifying invited paid orders create pending commission and settle exactly 5 yuan to the inviter only after the 24-hour refund window passes without refund.

**Independent Test**: Complete an invited membership order with actual paid amount at least 15 yuan, verify pending commission before the refund window ends, then verify exactly one 5 yuan settlement after the window, with refund-window cancellation blocking settlement.

### Tests for User Story 2 ⚠️

- [x] T017 [P] [US2] Add pending commission creation, threshold, refund-window cancellation, and idempotent settlement regression tests in `tests/test_membership_api.py`
- [x] T018 [P] [US2] Add admin commission audit and settlement endpoint coverage in `tests/test_admin_api.py`
- [x] T019 [P] [US2] Update frontend static contract coverage for commission summary/list payloads in `tests/test_frontend_llm_settings_location.py`

### Implementation for User Story 2

- [x] T020 [US2] Implement commission record creation, settlement, cancellation, and balance ledger transitions in `backend/system/membership_commission_store.py`
- [x] T021 [US2] Replace inviter-side new reward coupon issuance with commission creation hooks and refund rollback integration in `backend/system/membership_store.py`
- [x] T022 [US2] Preserve historical old-model invite reward coupon reads while stopping new inviter 5 yuan coupon issuance in `backend/system/membership_marketing_store.py`
- [x] T023 [US2] Add user-facing commission summary and commission history endpoints in `adapter/routers/membership.py`
- [x] T024 [US2] Add admin commission list and manual settlement endpoints in `adapter/routers/admin.py`
- [x] T025 [US2] Update membership client schemas, queries, and UI surfaces for commission balances/history in `frontend/src/ui/api/membership.ts`, `frontend/src/ui/queries/membership.ts`, `frontend/src/views/membership/MembershipPage.tsx`, and `frontend/src/views/membership/components/MembershipProfilePanel.tsx`

**Checkpoint**: New invited orders create pending commission and settle exactly once after the refund window.

---

## Phase 5: User Story 3 - Inviter Withdraws To WeChat Pay (Priority: P2)

**Goal**: Users with settled commission can withdraw to their own WeChat Pay account, with correct reservation, success, and failure balance handling.

**Independent Test**: Give a user withdrawable commission, submit a withdrawal to WeChat Pay, confirm reserved balance while pending, then verify success moves funds to paid-out and failure returns funds to withdrawable.

### Tests for User Story 3 ⚠️

- [x] T026 [P] [US3] Add withdrawal request, insufficient balance, missing payout identity, success, failure, and idempotent provider-result regression tests in `tests/test_membership_api.py`
- [x] T027 [P] [US3] Add admin withdrawal audit coverage in `tests/test_admin_api.py`
- [x] T028 [P] [US3] Update frontend static contract coverage for withdrawal payloads and statuses in `tests/test_frontend_llm_settings_location.py`

### Implementation for User Story 3

- [x] T029 [US3] Implement withdrawal request, reservation, payout result reconciliation, and WeChat payout identity handling in `backend/system/membership_commission_store.py`
- [x] T030 [US3] Extend WeChat payment service integration for commission payouts or shared payout request signing in `backend/system/membership_payment_service.py`
- [x] T031 [US3] Add user withdrawal request and withdrawal history endpoints in `adapter/routers/membership.py`
- [x] T032 [US3] Update membership API clients, queries, and user UI for withdrawal submission and status history in `frontend/src/ui/api/membership.ts`, `frontend/src/ui/queries/membership.ts`, `frontend/src/views/membership/MembershipPage.tsx`, and `frontend/src/views/membership/components/MembershipProfilePanel.tsx`

**Checkpoint**: Withdrawable commission can move through pending, succeeded, and failed payout states without balance drift.

---

## Phase 6: User Story 4 - Admin Audits Invite Revenue And Payouts (Priority: P3)

**Goal**: Administrators can inspect invite bindings, invite discount coupons, commission records, and withdrawal records for support and finance workflows.

**Independent Test**: Generate invite binding, discount coupon, pending/settled commission, and withdrawal records, then verify admin lists and detail views can trace inviter, invitee, order, payout target, and statuses.

### Tests for User Story 4 ⚠️

- [x] T033 [P] [US4] Add end-to-end admin overview/list/detail coverage for invite discount, commission, and withdrawal audit flows in `tests/test_admin_api.py`
- [x] T034 [P] [US4] Update frontend static contract coverage for new admin list/detail payload shapes in `tests/test_frontend_llm_settings_location.py`

### Implementation for User Story 4

- [x] T035 [US4] Extend admin overview aggregates for commission and withdrawal counts/amounts in `backend/system/membership_commission_store.py` and `adapter/routers/admin.py`
- [x] T036 [US4] Add admin DTOs, filters, and list endpoints for withdrawals and richer invite/commission audit output in `adapter/routers/admin.py` and `frontend/src/ui/api/admin.ts`
- [x] T037 [US4] Update admin queries and membership admin page to surface invite discount, commission, and withdrawal audit data in `frontend/src/ui/queries/admin.ts` and `frontend/src/views/admin/AdminMembershipPage.tsx`

**Checkpoint**: Admin workflows can explain each invite discount, commission settlement, and payout.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Finish documentation and end-to-end verification for the invite discount / commission feature.

- [x] T038 [P] Update pricing, invite reward, commission settlement, and withdrawal documentation in `docs/membership-subscription-invite-plan.md`, `docs/membership-selfhost-launch-checklist.md`, and related membership docs that mention invite reward coupons or first-order pricing
- [x] T039 Run targeted backend and contract regression suites for invite discount, commission, and withdrawal flows in `tests/test_membership_api.py`, `tests/test_admin_api.py`, and `tests/test_frontend_llm_settings_location.py`
- [x] T040 Run quickstart verification from `specs/008-invite-commission/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion; blocks all user stories
- **User Stories (Phase 3+)**: Depend on Foundational completion
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Starts after Foundational; establishes the new 20 yuan price and invitee discount coupon behavior
- **User Story 2 (P1)**: Starts after Foundational and depends on US1 pricing/coupon behavior because commission qualification uses actual paid amount after the invite discount
- **User Story 3 (P2)**: Starts after Foundational and depends on US2 commission settlement/balance behavior
- **User Story 4 (P3)**: Starts after Foundational and depends on US1-US3 data being available for audit

### Within Each User Story

- Tests MUST be written and fail before implementation
- Shared store changes before router behavior changes
- Router behavior before frontend/admin UX adjustments
- Story verification before moving to the next dependent story

### Parallel Opportunities

- T004-T008 can run in parallel after T003
- T009-T011 can run in parallel within US1
- T017-T019 can run in parallel within US2
- T026-T028 can run in parallel within US3
- T033-T034 can run in parallel within US4
- T038 can run in parallel with final verification preparation once implementation stabilizes

---

## Parallel Example: User Story 2

```bash
# Launch all User Story 2 tests together:
Task: "T017 [P] [US2] Add pending commission creation, threshold, refund-window cancellation, and idempotent settlement regression tests in tests/test_membership_api.py"
Task: "T018 [P] [US2] Add admin commission audit and settlement endpoint coverage in tests/test_admin_api.py"
Task: "T019 [P] [US2] Update frontend static contract coverage for commission summary/list payloads in tests/test_frontend_llm_settings_location.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Confirm invitee discount coupon issuance and 20 yuan pricing work independently

### Incremental Delivery

1. Deliver US1 to establish the new invite discount and pricing model
2. Deliver US2 to replace inviter coupon rewards with fixed 5 yuan commission settlement
3. Deliver US3 to let inviters withdraw settled commission to WeChat Pay
4. Deliver US4 for admin traceability and finance/support workflows
5. Finish with docs and quickstart verification

### Parallel Team Strategy

With multiple developers after Foundational is complete:

1. Developer A: US1 pricing and invite discount coupon flow
2. Developer B: US2 commission ledger and settlement logic
3. Developer C: US3 payout/withdrawal flow after US2 ledger contracts stabilize
4. Developer D: US4 admin audit surfaces after backend contracts land

---

## Notes

- [P] tasks target different files or non-overlapping changes
- `[US1]` through `[US4]` map directly to the invite discount / commission user stories in `spec.md`
- Keep the old inviter 5 yuan coupon history readable, but do not issue new inviter-side reward coupons once the new feature is active
- Reuse the existing refund-window policy from `specs/007-membership-refund-window/plan.md` for commission settlement gating instead of inventing a second refund clock
