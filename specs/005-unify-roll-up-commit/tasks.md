# Tasks: Unified Roll-Up Commit

**Input**: Design documents from `specs/005-unify-roll-up-commit/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/roll-up-landing-behavior.md, quickstart.md

**Tests**: Included because the plan requires test-first regression coverage for duplicate parent prevention and shared roll-up landing behavior.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the current roll-up implementation and test surface before changing behavior.

- [X] T001 Inspect existing manual, threshold, and learning-object-isomorphic roll-up flow in `backend/system/api.py`
- [X] T002 Inspect existing roll-up behavior tests and helper patterns in `tests/test_spec_alignment.py`
- [X] T003 [P] Review behavioral contract in `specs/005-unify-roll-up-commit/contracts/roll-up-landing-behavior.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish shared helpers and regression harnesses that all user stories depend on.

**CRITICAL**: No user story implementation should begin until these tasks are complete.

- [X] T004 Add shared test helpers for manual-source learning-object roll-up fixtures in `tests/test_spec_alignment.py`
- [X] T005 Add helper assertions for parent duplication, source aggregation queue consumption, and upper-layer registration in `tests/test_spec_alignment.py`
- [X] T006 Identify the minimal helper extraction boundaries for queue-backed candidate selection and shared roll-up landing inside `backend/system/api.py`

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - Same Result After Candidate Selection (Priority: P1) MVP

**Goal**: Manual roll-up, threshold roll-up, and learning-object-isomorphic roll-up produce the same committed structure once candidates are selected.

**Independent Test**: Prepare equivalent lower-layer candidates, invoke each trigger mode, and compare parent creation, child attachment, queue consumption, upper-layer registration, and outcome reason.

### Tests for User Story 1

- [X] T007 [US1] Add failing regression test proving learning-object-isomorphic roll-up with covered source queue candidates consumes those candidates and registers one upper-layer parent in `tests/test_spec_alignment.py`
- [X] T008 [US1] Add failing comparison test for manual and threshold roll-up shared queue consumption and upper-layer registration behavior in `tests/test_spec_alignment.py`

### Implementation for User Story 1

- [X] T009 [US1] Implement source aggregation queue candidate filtering by covered learning-object instances in `backend/system/api.py`
- [X] T010 [US1] Update learning-object-isomorphic roll-up flow to require selected source queue candidates before creating or registering a parent in `backend/system/api.py`
- [X] T011 [US1] Route successful learning-object-isomorphic selections through the same queue consumption and upper-layer registration outcome as other roll-up triggers in `backend/system/api.py`
- [X] T012 [US1] Run `pytest tests/test_spec_alignment.py -k "isomorphic and consumes"` and fix any failures in `backend/system/api.py` or `tests/test_spec_alignment.py`

**Checkpoint**: User Story 1 should be independently functional and testable as the MVP.

---

## Phase 4: User Story 2 - Prevent Duplicate Parents For Existing Roll-Ups (Priority: P2)

**Goal**: Switching strategies after a successful roll-up does not create same-content duplicate parents, especially when manual roll-up already consumed a chapter's child candidates.

**Independent Test**: Manually roll up a chapter-like candidate set, confirm the source queue is consumed, switch to learning-object-isomorphic roll-up, and verify no second parent or duplicate registration appears.

### Tests for User Story 2

- [X] T013 [US2] Add failing regression test `test_learning_object_isomorphic_roll_up_does_not_duplicate_after_manual_roll_up` in `tests/test_spec_alignment.py`
- [X] T014 [US2] Add failing regression test proving learning-object-isomorphic roll-up with active recall points but empty source aggregation queue is a no-op in `tests/test_spec_alignment.py`

### Implementation for User Story 2

- [X] T015 [US2] Ensure learning-object-isomorphic roll-up returns no hierarchy-changing result when covered source queue candidates are absent in `backend/system/api.py`
- [X] T016 [US2] Prevent object-mirror parent creation before queue-backed candidate selection succeeds in `backend/system/api.py`
- [X] T017 [US2] Preserve recognition or no-op behavior for content already consumed by an existing committed parent in `backend/system/api.py`
- [X] T018 [US2] Run `pytest tests/test_spec_alignment.py -k "duplicate or empty source aggregation queue or manual_roll_up"` and fix any failures in `backend/system/api.py` or `tests/test_spec_alignment.py`

**Checkpoint**: User Stories 1 and 2 should both work independently.

---

## Phase 5: User Story 3 - Preserve Trigger-Specific Selection While Sharing Landing (Priority: P3)

**Goal**: Each trigger keeps its own selection rule and reason metadata while sharing the post-selection landing behavior.

**Independent Test**: Verify manual, threshold, and learning-object-isomorphic triggers select candidates according to their own rules, but all consume queue-backed candidates and register one parent through the shared outcome.

### Tests for User Story 3

- [X] T019 [US3] Add or update test coverage for trigger-specific aggregation event or audit reason preservation in `tests/test_spec_alignment.py`
- [X] T020 [US3] Add or update test coverage for review queue and actionable missing instance gates across all roll-up trigger modes in `tests/test_spec_alignment.py`

### Implementation for User Story 3

- [X] T021 [US3] Preserve manual roll-up title and manual reason behavior while using shared landing constraints in `backend/system/api.py`
- [X] T022 [US3] Preserve threshold eligibility and threshold reason behavior while using shared landing constraints in `backend/system/api.py`
- [X] T023 [US3] Preserve learning-object-isomorphic deterministic selection and label or binding metadata only after queue-backed selection succeeds in `backend/system/api.py`
- [X] T024 [US3] Run `pytest tests/test_spec_alignment.py -k "roll_up or isomorphic or missing instances"` and fix any failures in `backend/system/api.py` or `tests/test_spec_alignment.py`

**Checkpoint**: All user stories should now be independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the full feature, update normative docs only if behavior wording changed, and prepare for implementation completion.

- [X] T025 [P] Update roll-up behavior documentation in `docs/spec.md` if implementation changes normative wording for 4.4 roll-up or learning-object-isomorphic behavior
- [X] T026 Run quickstart validation from `specs/005-unify-roll-up-commit/quickstart.md`
- [X] T027 Run full focused regression suite with `pytest tests/test_spec_alignment.py`
- [X] T028 [P] Review `backend/system/api.py` for unrelated refactors or behavior drift and keep only changes needed by this feature
- [X] T029 Record any residual verification notes in `specs/005-unify-roll-up-commit/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion - blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational and is the MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational and benefits from US1 shared candidate/landing behavior.
- **User Story 3 (Phase 5)**: Depends on Foundational and should run after US1/US2 if implementation centralizes shared behavior there.
- **Polish (Phase 6)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: MVP; establishes queue-backed isomorphic success path and shared landing outcome.
- **US2 (P2)**: Can start after Foundational but is safest after US1 because it relies on queue-backed no-op behavior.
- **US3 (P3)**: Can start after Foundational but should validate after US1/US2 to avoid reason metadata masking core behavior regressions.

### Within Each User Story

- Write tests first and confirm they fail before implementation.
- Implement the smallest backend behavior needed for that story.
- Run that story's targeted pytest command before moving to the next story.

### Parallel Opportunities

- T003 can run in parallel with T001 and T002.
- T025 and T028 can run in parallel during polish because they touch separate files.
- Once T004-T006 are complete, T013/T014 and T019/T020 can be drafted in parallel with T007/T008, but backend implementation tasks in `backend/system/api.py` should be serialized to avoid conflicting edits.

---

## Parallel Example: User Story 2

```text
Task: "Add failing regression test test_learning_object_isomorphic_roll_up_does_not_duplicate_after_manual_roll_up in tests/test_spec_alignment.py"
Task: "Add failing regression test proving learning-object-isomorphic roll-up with active recall points but empty source aggregation queue is a no-op in tests/test_spec_alignment.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 setup.
2. Complete Phase 2 foundational helpers and extraction boundary analysis.
3. Complete Phase 3 to make successful isomorphic roll-up queue-backed and landing-compatible.
4. Stop and validate with the US1 targeted pytest command.

### Incremental Delivery

1. US1: queue-backed success path and shared landing outcome.
2. US2: duplicate prevention and no-op behavior when source queue candidates are absent.
3. US3: reason metadata and trigger-specific selection preservation.
4. Polish: docs check, quickstart validation, full `tests/test_spec_alignment.py`.

### Coordination Notes

- Treat `backend/system/api.py` as a single-writer file during implementation.
- Keep `tests/test_spec_alignment.py` additions focused and avoid broad fixture rewrites.
- Do not introduce public API, schema, dependency, or frontend changes unless implementation uncovers a hard requirement.
