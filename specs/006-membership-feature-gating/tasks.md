# Tasks: Membership Feature Gating

**Input**: Design documents from `/specs/006-membership-feature-gating/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/member-feature-access.md, quickstart.md

**Tests**: Included because the specification requires active-member and non-member acceptance coverage for each protected feature category.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase when files do not overlap
- **[Story]**: User story label for traceability
- Every task includes exact file paths

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm current feature context and existing test surfaces before changing behavior.

- [x] T001 Verify current Spec Kit context points to `specs/006-membership-feature-gating/plan.md` in `AGENTS.md`
- [x] T002 Review existing LLM endpoint tests and membership fixtures in `tests/test_api_envelope.py` and `tests/test_membership_api.py`
- [x] T003 [P] Review existing frontend LLM settings static tests in `tests/test_frontend_llm_settings_location.py`
- [x] T004 [P] Review existing frontend Pomodoro static tests in `tests/test_frontend_pomodoro_multi_plan.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the shared access contract needed before any protected feature can be gated.

**CRITICAL**: No user story work should begin until this phase is complete.

- [x] T005 Add shared member-only access helper using `MembershipStore.get_membership_summary(...).is_active` in `adapter/deps.py`
- [x] T006 Add stable member-only error code/message handling for forbidden protected features in `adapter/deps.py`
- [x] T007 [P] Add frontend helper for recognizing member-only API failures and membership-center path in `frontend/src/ui/api/http.ts`
- [x] T008 [P] Add reusable member-only blocked UI component or helper in `frontend/src/views/membership/membershipUi.tsx`

**Checkpoint**: Shared backend and frontend member-only primitives exist and can be reused by all user stories.

---

## Phase 3: User Story 1 - Members Use Member-Only Features (Priority: P1) MVP

**Goal**: Active members can use LLM configuration, AI Q&A, player AI Q&A, and Pomodoro normally.

**Independent Test**: Sign in as an active member and verify each protected feature behaves as it did before gating.

### Tests for User Story 1

- [x] T009 [P] [US1] Add active-member LLM configuration access tests in `tests/test_api_envelope.py`
- [x] T010 [P] [US1] Add active-member AI Q&A endpoint tests for system/project ask and chat-completions in `tests/test_api_envelope.py`
- [x] T011 [P] [US1] Add active-member Pomodoro server-backed helper test for TTS preview in `tests/test_api_envelope.py`
- [x] T012 [P] [US1] Add frontend static assertion that active-member LLM/Pomodoro gates render normal controls in `tests/test_frontend_llm_settings_location.py` and `tests/test_frontend_pomodoro_multi_plan.py`

### Implementation for User Story 1

- [x] T013 [US1] Apply member access check without blocking active members on `/profile/me/llm-settings` endpoints in `adapter/routers/profile.py`
- [x] T014 [US1] Apply member access check without blocking active members on `/system/llm/ask`, `/projects/{projectId}/llm/ask`, `/projects/{projectId}/llm/chat-completions`, and `/projects/{projectId}/llm/ask/stream` in `adapter/routers/system.py`
- [x] T015 [US1] Apply member access check without blocking active members on `/system/pomodoro/tts-preview` in `adapter/routers/system.py`
- [x] T016 [US1] Preserve active-member LLM settings controls and save behavior in `frontend/src/views/settings/GlobalSettingsPage.tsx` and `frontend/src/views/settings/components/LlmSettingsCards.tsx`
- [x] T017 [US1] Preserve active-member AI chat submit behavior in `frontend/src/views/ai/AiChatPage.tsx`
- [x] T018 [US1] Preserve active-member player AI Q&A behavior in `frontend/src/views/workbench/components/VideoPane.tsx`
- [x] T019 [US1] Preserve active-member Pomodoro page and settings behavior in `frontend/src/views/pomodoro/PomodoroPage.tsx` and `frontend/src/views/pomodoro/PomodoroSettingsPage.tsx`

**Checkpoint**: Active members can use all four protected feature categories, and existing behavior is not degraded.

---

## Phase 4: User Story 2 - Non-Members Are Blocked From Member-Only Features (Priority: P1)

**Goal**: Non-members cannot use protected AI or Pomodoro features and see a clear membership path.

**Independent Test**: Sign in as never-purchased and expired users, then verify each protected feature is blocked before protected work begins.

### Tests for User Story 2

- [x] T020 [P] [US2] Add non-member LLM configuration rejection tests in `tests/test_api_envelope.py`
- [x] T021 [P] [US2] Add non-member system/project LLM ask, chat-completions, and stream rejection tests in `tests/test_api_envelope.py`
- [x] T022 [P] [US2] Add non-member Pomodoro TTS preview rejection test in `tests/test_api_envelope.py`
- [x] T023 [P] [US2] Add frontend static tests for member-only LLM settings messaging and membership link in `tests/test_frontend_llm_settings_location.py`
- [x] T024 [P] [US2] Add frontend static tests for member-only AI chat, player AI, and Pomodoro messaging in `tests/test_frontend_pomodoro_multi_plan.py`

### Implementation for User Story 2

- [x] T025 [US2] Block non-members from reading or updating user LLM settings with the shared member-only error in `adapter/routers/profile.py`
- [x] T026 [US2] Block non-members from all LLM ask/chat/stream actions before calling LLM services in `adapter/routers/system.py`
- [x] T027 [US2] Block non-members from Pomodoro TTS preview before external TTS work starts in `adapter/routers/system.py`
- [x] T028 [US2] Gate LLM settings UI for non-members with member-only explanation and `/membership` action in `frontend/src/views/settings/GlobalSettingsPage.tsx`
- [x] T029 [US2] Gate AI chat page submit controls for non-members with member-only explanation and `/membership` action in `frontend/src/views/ai/AiChatPage.tsx`
- [x] T030 [US2] Gate player AI Q&A controls for non-members with member-only explanation and `/membership` action in `frontend/src/views/workbench/components/VideoPane.tsx`
- [x] T031 [US2] Gate Pomodoro page and settings for non-members with member-only explanation and `/membership` action in `frontend/src/views/pomodoro/PomodoroPage.tsx` and `frontend/src/views/pomodoro/PomodoroSettingsPage.tsx`

**Checkpoint**: Non-members are blocked from all protected feature categories, cannot bypass via direct API calls, and can reach membership center.

---

## Phase 5: User Story 3 - Membership Changes Take Effect Quickly (Priority: P2)

**Goal**: Access follows current membership state after purchase, renewal, expiration, refund, or revocation.

**Independent Test**: Change a user's membership state through existing membership flows and verify protected access changes on the next attempt.

### Tests for User Story 3

- [x] T032 [P] [US3] Add purchase-to-active access transition test for a protected LLM endpoint in `tests/test_membership_api.py`
- [x] T033 [P] [US3] Add refund-or-expiration-to-blocked access transition test for a protected LLM endpoint in `tests/test_membership_api.py`
- [x] T034 [P] [US3] Add frontend cache invalidation/static coverage for membership summary refresh after membership mutations in `tests/test_frontend_llm_settings_location.py`

### Implementation for User Story 3

- [x] T035 [US3] Ensure protected backend access checks query current membership summary on each protected request in `adapter/deps.py`
- [x] T036 [US3] Invalidate or refetch membership summary after membership purchase, sync, close, and refund mutations in `frontend/src/ui/queries/membership.ts`
- [x] T037 [US3] Make protected frontend gates fail closed while membership status is loading or errored in `frontend/src/views/settings/GlobalSettingsPage.tsx`, `frontend/src/views/ai/AiChatPage.tsx`, `frontend/src/views/workbench/components/VideoPane.tsx`, `frontend/src/views/pomodoro/PomodoroPage.tsx`, and `frontend/src/views/pomodoro/PomodoroSettingsPage.tsx`

**Checkpoint**: Membership lifecycle changes are reflected on the next protected feature attempt.

---

## Phase 6: User Story 4 - Existing Ungated Learning Workflows Continue Working (Priority: P3)

**Goal**: Non-members can still use unrelated learning, project, review, profile, and membership-management workflows.

**Independent Test**: Sign in as a non-member and verify unprotected flows still load and operate without member-only blocks.

### Tests for User Story 4

- [x] T038 [P] [US4] Add regression tests proving non-member project and review endpoints remain available in `tests/test_api_envelope.py`
- [x] T039 [P] [US4] Add frontend static regression checks that member-only blocker is limited to protected pages/components in `tests/test_frontend_llm_settings_location.py` and `tests/test_frontend_pomodoro_multi_plan.py`

### Implementation for User Story 4

- [x] T040 [US4] Audit router changes to ensure only profile LLM, system/project LLM, and Pomodoro helper endpoints use member-only checks in `adapter/routers/profile.py` and `adapter/routers/system.py`
- [x] T041 [US4] Audit frontend gates to ensure project dashboards, normal workbench views, profile, review recommendations, and membership center are not blocked in `frontend/src/router.tsx`, `frontend/src/views/workbench/WorkbenchPage.tsx`, and `frontend/src/views/profile/ProfilePage.tsx`

**Checkpoint**: Unprotected workflows remain available to non-members while protected features stay blocked.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, verification, and final consistency checks.

- [x] T042 [P] Update membership documentation to state AI and Pomodoro are member-only in `docs/membership-subscription-invite-plan.md`
- [x] T043 [P] Update self-host launch checklist with member-only AI/Pomodoro verification in `docs/membership-selfhost-launch-checklist.md`
- [x] T044 Run backend targeted tests `pytest tests/test_api_envelope.py tests/test_membership_api.py`
- [x] T045 Run frontend static tests `pytest tests/test_frontend_llm_settings_location.py tests/test_frontend_pomodoro_multi_plan.py`
- [x] T046 Run frontend build or lint from `frontend/package.json` as appropriate for the touched TSX files
- [x] T047 Execute quickstart verification steps from `specs/006-membership-feature-gating/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **US1 and US2 (P1)**: Depend on Foundational. They touch overlapping files, so implement sequentially or coordinate carefully.
- **US3 (P2)**: Depends on US1 and US2 because it verifies state transitions across the same gates.
- **US4 (P3)**: Depends on US2 because it verifies the block is scoped to protected features.
- **Polish**: Depends on all desired user stories.

### User Story Dependencies

- **US1**: Foundation only; validates active members retain access.
- **US2**: Foundation only; validates non-members are blocked.
- **US3**: Requires backend and frontend gates from US1/US2.
- **US4**: Requires backend and frontend gates from US2.

### Within Each User Story

- Tests should be added before implementation and should fail before the relevant gate is implemented.
- Backend tests and frontend static tests can usually be written in parallel when they touch different files.
- Backend gates should land before frontend UX is considered authoritative.
- Frontend gates should reuse the shared member-only UI/helper from Phase 2.

---

## Parallel Execution Examples

### User Story 1

```text
Task: "T009 [US1] Add active-member LLM configuration access tests in tests/test_api_envelope.py"
Task: "T011 [US1] Add active-member Pomodoro server-backed helper test for TTS preview in tests/test_api_envelope.py"
Task: "T012 [US1] Add frontend static assertion that active-member LLM/Pomodoro gates render normal controls in tests/test_frontend_llm_settings_location.py and tests/test_frontend_pomodoro_multi_plan.py"
```

### User Story 2

```text
Task: "T020 [US2] Add non-member LLM configuration rejection tests in tests/test_api_envelope.py"
Task: "T023 [US2] Add frontend static tests for member-only LLM settings messaging and membership link in tests/test_frontend_llm_settings_location.py"
Task: "T024 [US2] Add frontend static tests for member-only AI chat, player AI, and Pomodoro messaging in tests/test_frontend_pomodoro_multi_plan.py"
```

### User Story 3

```text
Task: "T032 [US3] Add purchase-to-active access transition test for a protected LLM endpoint in tests/test_membership_api.py"
Task: "T033 [US3] Add refund-or-expiration-to-blocked access transition test for a protected LLM endpoint in tests/test_membership_api.py"
Task: "T034 [US3] Add frontend cache invalidation/static coverage for membership summary refresh after membership mutations in tests/test_frontend_llm_settings_location.py"
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete US1 and US2 together as the real MVP because the membership distinction requires both active-member allow and non-member block behavior.
3. Run targeted backend and frontend tests for protected features.
4. Validate manually with the quickstart non-member and active-member flows.

### Incremental Delivery

1. Establish shared member-only access primitives.
2. Protect LLM configuration and AI Q&A first.
3. Add player AI Q&A and Pomodoro gates.
4. Add membership lifecycle transition coverage.
5. Confirm unrelated workflows remain available.

### Risk Notes

- Backend stream endpoints must reject non-members before emitting successful stream events.
- Pomodoro is mostly frontend-local, so frontend gating is required in addition to protecting server-backed Pomodoro helpers.
- Frontend membership summary loading or error states must fail closed for protected features without blocking unrelated navigation.
