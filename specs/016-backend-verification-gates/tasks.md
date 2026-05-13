# Tasks: Backend Verification Gates

**Input**: Design documents from `/specs/016-backend-verification-gates/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md

**Tests**: Included, because the specification explicitly requires independent verification for each user story.

**Organization**: Tasks are grouped by user story so each gate slice can be implemented and verified independently.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the shared gate scaffolding used by all stories.

- [X] T001 [P] Create the shared backend verification gate module skeleton in `backend/system/backend_verification_gate.py`
- [X] T002 [P] Create the CLI wrapper skeleton in `tools/verify_backend_release_gate.py`
- [X] T003 [P] Create reusable gate test helpers in `tests/backend_verification_gate_support.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core gate primitives that every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Implement gate scope selection, required-check registration, and validation report structures in `backend/system/backend_verification_gate.py`
- [X] T005 Implement child-check execution, skipped-check accounting, report rendering, and exit-code policy in `backend/system/backend_verification_gate.py`

**Checkpoint**: The gate can represent required vs skipped checks and fail correctly before user-story-specific checks are added.

---

## Phase 3: User Story 1 - 发布前发现重启恢复问题 (Priority: P1) 🎯 MVP

**Goal**: Block release unless the gate proves a subject/material workflow survives save, restart, and reopen.

**Independent Test**: Run the gate against a created subject with default material, restart the backend runtime, and reopen the same workspace URL; the gate must pass only if the post-restart workspace still resolves.

### Tests for User Story 1

- [X] T006 [P] [US1] Add failing restart-recovery gate tests in `tests/test_backend_verification_gate_restart.py`

### Implementation for User Story 1

- [X] T007 [US1] Implement the restart-recovery smoke scenario and post-restart reopen assertions in `backend/system/backend_verification_gate.py`
- [X] T008 [US1] Wire the restart-recovery check into `tools/verify_backend_release_gate.py`

**Checkpoint**: User Story 1 should be independently testable as a release-blocking restart gate.

---

## Phase 4: User Story 2 - 发布前验证真实持久化和迁移路径 (Priority: P2)

**Goal**: Require real storage and migration coverage for persistence-affecting backend changes.

**Independent Test**: Run the gate against a real local PostgreSQL instance and confirm it fails on missing schema, type mismatch, failed migration, or missing recovery data instead of passing on a mock-only path.

### Tests for User Story 2

- [X] T009 [P] [US2] Add failing real-storage and migration gate tests in `tests/test_backend_verification_gate_storage.py`

### Implementation for User Story 2

- [X] T010 [US2] Implement real-storage smoke, migration validation, and integrity failure reporting in `backend/system/backend_verification_gate.py`
- [X] T011 [US2] Wire storage and migration checks into `tools/verify_backend_release_gate.py` using `tools/apply_postgres_migrations.py` and `tools/repair_subject_material_relationship_index.py`

**Checkpoint**: User Story 1 and User Story 2 should both be independently verifiable, and storage-affecting changes should now require real persistence coverage.

---

## Phase 5: User Story 3 - 身份边界和诊断成为验收对象 (Priority: P3)

**Goal**: Make ambiguous identity naming and weak diagnostics a gate failure.

**Independent Test**: Run the gate against a scoped workspace request and confirm the report distinguishes public identity, scoped identity, internal identity, and the specific failure kind.

### Tests for User Story 3

- [X] T012 [P] [US3] Add failing identity-boundary and diagnostic-report tests in `tests/test_backend_verification_gate_identity.py`

### Implementation for User Story 3

- [X] T013 [US3] Implement identity invariant checks and actionable diagnostic fields in `backend/system/backend_verification_gate.py`
- [X] T014 [US3] Wire scoped identity boundary and diagnostics checks into `tools/verify_backend_release_gate.py` using `tools/verify_scoped_project_ids.py`, `tools/verify_scoped_project_routes.py`, and `tools/verify_backend_boundaries.py`

**Checkpoint**: All three user stories should now be independently verifiable, and the gate should reject ambiguous identity/reporting behavior.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, operator workflow, and final verification.

- [X] T015 [P] Update `docs/deployment.md` and `docs/current-change.md` with the final gate command, required checks, and report semantics
- [X] T016 [P] Validate `specs/016-backend-verification-gates/quickstart.md` against the implemented gate and record any mismatches in `docs/current-change.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - blocks all user stories
- **User Stories (Phase 3+)**: Depend on the Foundational phase
- **Polish (Phase 6)**: Depends on the desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Starts after Foundational; this is the MVP gate slice.
- **User Story 2 (P2)**: Starts after Foundational; extends the same release gate with real storage and migration coverage.
- **User Story 3 (P3)**: Starts after Foundational; extends the same release gate with identity and diagnostics coverage.

### Within Each User Story

- Tests must be written before implementation.
- Gate primitives before story-specific wiring.
- Story-specific wiring before documentation updates.
- Story complete before moving to the next priority slice.

### Parallel Opportunities

- Setup tasks T001-T003 can run in parallel because they touch different files.
- Story-specific test files T006, T009, and T012 can be prepared in parallel after the foundation is ready.
- Polish tasks T015 and T016 can run in parallel once the gate is implemented.

---

## Parallel Example: User Story 1

```bash
Task: "Add failing restart-recovery gate tests in tests/test_backend_verification_gate_restart.py"
Task: "Implement the restart-recovery smoke scenario and post-restart reopen assertions in backend/system/backend_verification_gate.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. Stop and validate the restart-recovery gate independently

### Incremental Delivery

1. Complete Setup + Foundational → shared gate primitives ready
2. Add User Story 1 → verify restart-recovery coverage
3. Add User Story 2 → verify real storage and migration coverage
4. Add User Story 3 → verify identity and diagnostic coverage
5. Finish with documentation and quickstart validation

### Parallel Team Strategy

With multiple developers:

1. One developer builds the shared gate primitives.
2. Another prepares the restart-recovery tests.
3. After the foundation is done, one developer can own each story slice.
