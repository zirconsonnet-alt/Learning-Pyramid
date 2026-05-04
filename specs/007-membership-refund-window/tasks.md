# Tasks: Membership Refund Window

**Input**: Design documents from `/specs/007-membership-refund-window/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: This feature changes refund policy behavior and should be implemented with targeted backend/API regression tests before and alongside implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g. US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Refresh feature context and ensure the new refund-window spec is the active implementation target.

- [x] T001 Confirm `.specify/feature.json` still points to `specs/007-membership-refund-window` in `.specify/feature.json`
- [x] T002 Review active refund-window design artifacts in `specs/007-membership-refund-window/spec.md`, `specs/007-membership-refund-window/plan.md`, and `specs/007-membership-refund-window/contracts/membership-refund-window.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish shared refund-window policy helpers and shared expectations before any story-specific refund path changes.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Add shared refund-window constants and eligibility helper logic in `backend/system/membership_store.py`
- [x] T004 [P] Add shared backend regression fixtures/helpers for time-controlled refund policy tests in `tests/test_membership_api.py`
- [x] T005 [P] Add admin/API-level late-refund assertion helpers or shared expectations in `tests/test_admin_api.py`

**Checkpoint**: Refund-window policy primitives and shared test scaffolding are ready; user story implementation can now begin.

---

## Phase 3: User Story 1 - Refund Within Window (Priority: P1) 🎯 MVP

**Goal**: Paid membership orders inside 24 hours of successful payment can still start and complete refunds under the existing flow.

**Independent Test**: Create a paid membership order inside the 24-hour window, initiate refund, and verify refund completion plus existing side effects still work.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T006 [P] [US1] Add manual/provider refund-within-window regression tests in `tests/test_membership_api.py`
- [x] T007 [P] [US1] Add admin refund-within-window API coverage in `tests/test_admin_api.py`

### Implementation for User Story 1

- [x] T008 [US1] Apply refund-window eligibility to new refund initiation in `backend/system/membership_store.py`
- [x] T009 [US1] Route admin refund initiation through the updated shared store policy in `adapter/routers/admin.py`
- [x] T010 [US1] Preserve existing admin refund success handling and user-visible success feedback in `frontend/src/views/admin/AdminMembershipPage.tsx`

**Checkpoint**: Refunds inside the 24-hour window remain fully functional and independently verifiable.

---

## Phase 4: User Story 2 - Block Refund After Window (Priority: P1)

**Goal**: New refund attempts for paid membership orders older than 24 hours are rejected with a clear reason before any new refund starts.

**Independent Test**: Use a paid membership order older than 24 hours, try to refund it, and confirm rejection plus unchanged order state.

### Tests for User Story 2 ⚠️

- [x] T011 [P] [US2] Add late-refund rejection and exact-24-hour boundary tests in `tests/test_membership_api.py`
- [x] T012 [P] [US2] Add admin late-refund rejection API coverage in `tests/test_admin_api.py`
- [x] T013 [P] [US2] Add static frontend/admin late-refund messaging coverage if copy changes in `tests/test_frontend_llm_settings_location.py`

### Implementation for User Story 2

- [x] T014 [US2] Return a clear expired-window error for late new refund attempts in `backend/system/membership_store.py`
- [x] T015 [US2] Ensure late admin refund requests stop before provider refund submission in `adapter/routers/admin.py`
- [x] T016 [US2] Surface expired refund-window errors cleanly in the admin membership workflow in `frontend/src/views/admin/AdminMembershipPage.tsx`

**Checkpoint**: Late new refunds are blocked consistently and explain why they were rejected.

---

## Phase 5: User Story 3 - Continue In-Flight Refund Handling (Priority: P2)

**Goal**: Refunds started in time can still synchronize or complete after the 24-hour window has passed.

**Independent Test**: Initiate a provider-backed refund inside the window, advance time beyond 24 hours, then sync or notify success and confirm completion still succeeds.

### Tests for User Story 3 ⚠️

- [x] T017 [P] [US3] Add `refund_pending` post-window sync and callback coverage in `tests/test_membership_api.py`
- [x] T018 [P] [US3] Add admin refund-sync-after-window coverage for WeChat flows in `tests/test_admin_api.py`

### Implementation for User Story 3

- [x] T019 [US3] Limit refund-window checks to new initiation while preserving `refund_pending` completion paths in `backend/system/membership_store.py`
- [x] T020 [US3] Keep refund notification and admin sync flows using in-flight completion behavior in `adapter/routers/membership.py` and `adapter/routers/admin.py`

**Checkpoint**: Already-started refunds are not stranded after the refund window expires.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Finish documentation and full verification for the refund-window policy.

- [x] T021 [P] Update refund policy documentation in `docs/membership-subscription-invite-plan.md` and `docs/membership-selfhost-launch-checklist.md`
- [x] T022 Run targeted backend regression suite for refund policy in `tests/test_membership_api.py` and `tests/test_admin_api.py`
- [ ] T023 Run quickstart verification steps from `specs/007-membership-refund-window/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion; blocks all user stories
- **User Stories (Phase 3+)**: Depend on Foundational completion
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Starts after Foundational; establishes the shared 24-hour initiation behavior
- **User Story 2 (P1)**: Starts after Foundational and depends on US1 refund initiation path being in place
- **User Story 3 (P2)**: Starts after Foundational and depends on the shared refund-window policy from US1; should preserve behavior introduced in US1 while excluding in-flight sync/callbacks from US2 blocking

### Within Each User Story

- Tests MUST be written and fail before implementation
- Store policy changes before router behavior changes
- Router behavior before admin UX/message adjustments
- Story verification before moving to the next dependent story

### Parallel Opportunities

- T004 and T005 can run in parallel after T003
- T006 and T007 can run in parallel within US1
- T011, T012, and T013 can run in parallel within US2
- T017 and T018 can run in parallel within US3
- T021 can run in parallel with verification preparation once implementation stabilizes

---

## Parallel Example: User Story 2

```bash
# Launch all User Story 2 tests together:
Task: "T011 [P] [US2] Add late-refund rejection and exact-24-hour boundary tests in tests/test_membership_api.py"
Task: "T012 [P] [US2] Add admin late-refund rejection API coverage in tests/test_admin_api.py"
Task: "T013 [P] [US2] Add static frontend/admin late-refund messaging coverage if copy changes in tests/test_frontend_llm_settings_location.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Confirm in-window refunds still work for manual and provider-backed paths

### Incremental Delivery

1. Add US1 to preserve valid refund behavior
2. Add US2 to block late new refunds
3. Add US3 to guarantee late sync/callback completion for already-started refunds
4. Finish with documentation and quickstart verification

### Parallel Team Strategy

With multiple developers after Foundational is complete:

1. Developer A: US1 backend policy and regression tests
2. Developer B: US2 admin/API rejection handling and messaging
3. Developer C: US3 provider sync/callback preservation and WeChat regression coverage

---

## Notes

- [P] tasks target different files or non-overlapping changes
- [US1], [US2], and [US3] map directly to the refund-window user stories in `spec.md`
- Keep changes scoped to refund initiation policy; do not refactor unrelated membership purchase or gating behavior
- Reuse existing error envelope and audit logging conventions
