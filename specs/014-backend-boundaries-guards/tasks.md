# Tasks: Backend Boundaries and Guards

**Input**: Design documents from `specs/014-backend-boundaries-guards/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/backend-boundary-guards.md, quickstart.md

**Tests**: Included because the feature requires guard checks with representative violation coverage and existing regression verification.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other marked tasks in the same phase because it touches different files and has no dependency on unfinished tasks.
- **[Story]**: Maps tasks to user stories from `spec.md`.
- Every task includes an exact file path.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the feature-owned documentation and guard locations before story work begins.

- [X] T001 Create the backend boundary rule registry documentation in `specs/014-backend-boundaries-guards/contracts/backend-boundary-guards.md`
- [X] T002 Create the guard script shell with report-only and failing modes in `tools/verify_backend_boundaries.py`
- [X] T003 [P] Create the guard unit test module skeleton in `tests/test_backend_boundary_guards.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define shared guard data structures and test helpers required by every user story.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Define Boundary Rule and Guard Finding representations in `tools/verify_backend_boundaries.py`
- [X] T005 Define deterministic repository file scanning helpers in `tools/verify_backend_boundaries.py`
- [X] T006 [P] Add test helpers for temporary repository fixtures and guard execution in `tests/test_backend_boundary_guards.py`
- [X] T007 [P] Add quickstart verification command references in `specs/014-backend-boundaries-guards/quickstart.md`

**Checkpoint**: Guard infrastructure can scan files and return structured findings, even before individual rules are complete.

---

## Phase 3: User Story 1 - Understand Backend Boundaries (Priority: P1) MVP

**Goal**: Maintainers can classify backend changes into one owning boundary without reading unrelated modules.

**Independent Test**: Review `specs/014-backend-boundaries-guards/contracts/backend-boundary-guards.md` and confirm each named risk area has one owner, allowed behavior, forbidden behavior, and severity.

### Tests for User Story 1

- [X] T008 [P] [US1] Add tests that every boundary rule has an id, owner, severity, rationale, and forbidden patterns in `tests/test_backend_boundary_guards.py`
- [X] T009 [P] [US1] Add tests that every contract rule id appears in guard output metadata in `tests/test_backend_boundary_guards.py`

### Implementation for User Story 1

- [X] T010 [US1] Expand boundary contract with explicit owners for transport, identity, authorization, atomic mutation, and migration risk in `specs/014-backend-boundaries-guards/contracts/backend-boundary-guards.md`
- [X] T011 [US1] Encode BBG001 through BBG005 rule metadata in `tools/verify_backend_boundaries.py`
- [X] T012 [US1] Update `specs/014-backend-boundaries-guards/data-model.md` if rule fields change during implementation
- [X] T013 [US1] Run `python -m unittest tests.test_backend_boundary_guards -v` and document any rule coverage gaps in `specs/014-backend-boundaries-guards/quickstart.md`

**Checkpoint**: User Story 1 is complete when a maintainer can map each affected backend responsibility to exactly one boundary rule and the rule metadata tests pass.

---

## Phase 4: User Story 2 - Detect Boundary Drift Early (Priority: P2)

**Goal**: Guard checks report boundary violations before accidental forks become accepted patterns.

**Independent Test**: Introduce representative violations in temporary fixtures and confirm the guard reports rule id, path, line, severity, message, and evidence for each violation type.

### Tests for User Story 2

- [X] T014 [P] [US2] Add failing fixture tests for transport-layer internals access in `tests/test_backend_boundary_guards.py`
- [X] T015 [P] [US2] Add failing fixture tests for storage-only authorization ownership in `tests/test_backend_boundary_guards.py`
- [X] T016 [P] [US2] Add failing fixture tests for scoped identity bypass in `tests/test_backend_boundary_guards.py`
- [X] T017 [P] [US2] Add failing fixture tests for non-atomic cross-project mutation bypass in `tests/test_backend_boundary_guards.py`
- [X] T018 [P] [US2] Add failing fixture tests for fallback, shim, legacy, and compatibility expansion in `tests/test_backend_boundary_guards.py`

### Implementation for User Story 2

- [X] T019 [US2] Implement BBG001 transport boundary detection in `tools/verify_backend_boundaries.py`
- [X] T020 [US2] Implement BBG002 scoped identity boundary detection in `tools/verify_backend_boundaries.py`
- [X] T021 [US2] Implement BBG003 authorization ownership boundary detection in `tools/verify_backend_boundaries.py`
- [X] T022 [US2] Implement BBG004 atomic mutation boundary detection in `tools/verify_backend_boundaries.py`
- [X] T023 [US2] Implement BBG005 migration risk containment detection in `tools/verify_backend_boundaries.py`
- [X] T024 [US2] Add command-line output and exit behavior matching `specs/014-backend-boundaries-guards/contracts/backend-boundary-guards.md` in `tools/verify_backend_boundaries.py`
- [X] T025 [US2] Run `python tools/verify_backend_boundaries.py` against the current repository and record any existing findings that require later decision in `specs/014-backend-boundaries-guards/research.md`

**Checkpoint**: User Story 2 is complete when representative violations are detected and current repository guard output is deterministic and reviewable.

---

## Phase 5: User Story 3 - Guide Incremental Refactoring (Priority: P3)

**Goal**: The boundary design identifies safe extraction candidates without requiring behavior changes or broad rewrite.

**Independent Test**: Select the first extraction candidate and confirm its responsibility, allowed dependencies, forbidden dependencies, and unchanged behavior requirements are documented.

### Tests for User Story 3

- [X] T026 [P] [US3] Add tests that guard findings can be run in report-only mode for existing risks in `tests/test_backend_boundary_guards.py`
- [X] T027 [P] [US3] Add tests that approved boundary-owner paths are not reported as transport violations in `tests/test_backend_boundary_guards.py`

### Implementation for User Story 3

- [X] T028 [US3] Document the first safe extraction candidate and non-goals in `specs/014-backend-boundaries-guards/research.md`
- [X] T029 [US3] Add approved boundary-owner allowlist entries required by the documented extraction candidate in `tools/verify_backend_boundaries.py`
- [X] T030 [US3] Update `specs/014-backend-boundaries-guards/contracts/backend-boundary-guards.md` with the approved boundary-owner allowlist rules
- [X] T031 [US3] Run `python -m unittest tests.test_backend_boundary_guards -v` and confirm report-only behavior does not hide new violations

**Checkpoint**: User Story 3 is complete when existing risks can be reported without blocking documentation work, while new unapproved drift remains detectable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate the feature end to end and keep the workspace clean.

- [X] T032 [P] Run `python -m unittest tests.test_backend_boundary_guards -v` and confirm all guard tests pass
- [X] T033 [P] Run `python -m unittest tests.test_subject_material_atomicity tests.test_scoped_project_api_boundaries -v` to preserve existing scoped project guarantees
- [X] T034 [P] Run `python tools/verify_scoped_project_routes.py` to preserve scoped route coverage
- [X] T035 Run `python tools/verify_backend_boundaries.py` and confirm output matches the contract
- [X] T036 Run `python -m compileall -q backend adapter tests tools` and remove generated `__pycache__` directories under `backend`, `adapter`, `tests`, and `tools`
- [X] T037 Run `rg -n "from __future__ import annotations" backend adapter tests tools` and confirm no matches
- [X] T038 Update `specs/014-backend-boundaries-guards/quickstart.md` with final verification results if command names or outputs changed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational.
- **User Story 2 (Phase 4)**: Depends on User Story 1 rule metadata.
- **User Story 3 (Phase 5)**: Depends on User Story 2 guard output behavior.
- **Polish (Phase 6)**: Depends on selected user stories being complete.

### User Story Dependencies

- **US1**: MVP. Must complete first because guard implementation depends on named boundary rules.
- **US2**: Depends on US1 rule metadata and contract clarity.
- **US3**: Depends on US2 because report-only mode and allowlists must be built on real findings.

### Parallel Opportunities

- T003 can run in parallel with T002 after T001 starts because it creates a separate test file.
- T006 and T007 can run in parallel with T004/T005 because they touch separate files.
- T008 and T009 can run in parallel because both add tests in the same file only if coordinated by separate test classes; otherwise run sequentially.
- T014 through T018 can run in parallel if each owns a separate test class or fixture section in `tests/test_backend_boundary_guards.py`.
- T032 through T034 can run in parallel after implementation is complete.

---

## Parallel Example: User Story 2

```text
Task: "T014 Add failing fixture tests for transport-layer internals access in tests/test_backend_boundary_guards.py"
Task: "T015 Add failing fixture tests for storage-only authorization ownership in tests/test_backend_boundary_guards.py"
Task: "T016 Add failing fixture tests for scoped identity bypass in tests/test_backend_boundary_guards.py"
Task: "T017 Add failing fixture tests for non-atomic cross-project mutation bypass in tests/test_backend_boundary_guards.py"
Task: "T018 Add failing fixture tests for fallback, shim, legacy, and compatibility expansion in tests/test_backend_boundary_guards.py"
```

---

## Implementation Strategy

### MVP First

1. Complete Setup and Foundational tasks.
2. Complete User Story 1.
3. Stop and validate that boundary ownership is explicit and test-covered.

### Incremental Delivery

1. Deliver US1 boundary clarity.
2. Add US2 guard detection and command behavior.
3. Add US3 report-only handling and extraction guidance.
4. Run Polish verification.

### Notes

- Do not implement service extraction in this feature unless a guard cannot be made meaningful without minimal cleanup.
- Do not change user-visible behavior.
- Do not add fallback, shim, legacy compatibility expansion, hidden global state, or duplicate behavior paths.
- Tests that describe new guard behavior should fail before corresponding guard implementation.
