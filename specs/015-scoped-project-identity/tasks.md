# Tasks: Scoped Project Identity

**Input**: Design documents from `specs/015-scoped-project-identity/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/scoped-project-identity.md`, `quickstart.md`

**Tests**: Test tasks are included because the specification requires restart, identity, API, and recovery verification.

**Organization**: Tasks are grouped by user story so each increment can be implemented and tested independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other marked tasks in the same phase when they touch different files.
- **[Story]**: User story label from `spec.md`.
- Every task includes exact file paths.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the implementation workspace and current-change tracking before code edits.

- [X] T001 Create or overwrite `docs/current-change.md` with the scoped project identity implementation scope, root cause, planned files, behavior changes, and pollution-risk checklist.
- [X] T002 [P] Review `README.md`, `docs/data-model.md`, `docs/current-change.md`, `docs/architecture.md`, and `docs/deployment.md` if present, then record any identity-model conflicts in `docs/current-change.md`.
- [X] T003 [P] Review existing scoped identity tests in `tests/test_subject_material_atomicity.py` and `tests/test_scoped_project_api_boundaries.py` to identify assertions that must remain unchanged.
- [X] T004 [P] Review existing backend scoped route call sites in `adapter/routers/` and frontend scoped route call sites in `frontend/src/`, then list exact rename targets in `docs/current-change.md`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define the canonical identity vocabulary and persistence contract that all stories depend on.

**CRITICAL**: No user story implementation should begin until these tasks are complete.

- [X] T005 [P] Update `backend/models/study_material.py` to represent subject-scoped material identity as `scoped_project_id` and internal storage identity as `internal_project_id` without adding compatibility aliases.
- [X] T006 [P] Update `backend/models/subject_material_link.py` to use `scoped_project_id` for the subject-scoped material id.
- [X] T007 [P] Update `backend/models/project.py` comments or property names only where necessary so `internal_project_key` and `public_project_id` do not imply mixed identity semantics.
- [X] T008 Update JSON encode/decode identity fields in `backend/system/persistence_json.py` so persisted relationship payloads use the canonical names from `contracts/scoped-project-identity.md`.
- [X] T009 Add or update repository/persistence interfaces for subject-material relationships in `backend/repositories/persistence_interfaces.py`, `backend/repositories/postgres_persistence.py`, and `backend/repositories/sqlite_persistence.py`.
- [X] T010 Add the subject-material relationship store migration definition in `backend/system/postgres_schema.py` and the matching SQLite schema in `backend/system/persistence_store.py`.
- [X] T011 Update `docs/current-change.md` with the finalized identity vocabulary and note that no project-scoped table is being converted to composite keys.

**Checkpoint**: Canonical identity names and persistence surfaces are defined.

---

## Phase 3: User Story 1 - 学科工作台重启后可用 (Priority: P1) MVP

**Goal**: A newly created subject and its default material workspace survive service restart and reopen through `{subjectId, scopedProjectId}`.

**Independent Test**: Create a subject, open its default material workspace, reload from persistence, and confirm workspace APIs load without `project id is not a subject`.

### Tests for User Story 1

- [X] T012 [P] [US1] Add failing restart regression tests for subject creation and default material reload in `tests/test_subject_material_persistence.py`.
- [X] T013 [P] [US1] Add failing tests for resolving multiple materials under one subject after reload in `tests/test_subject_material_identity.py`.
- [X] T014 [P] [US1] Add failing API boundary tests for invalid scoped material ids returning not-found semantics in `tests/test_scoped_project_api_boundaries.py`.

### Implementation for User Story 1

- [X] T015 [US1] Persist subject-material relationships during `create_subject()` and `create_subject_material()` in `backend/system/api.py`.
- [X] T016 [US1] Implement relationship hydration for Postgres native load in `backend/system/postgres_store.py`.
- [X] T017 [US1] Implement relationship hydration for SQLite/native snapshot load in `backend/system/persistence_store.py`.
- [X] T018 [US1] Update `SystemAPI.resolve_scoped_project_internal_key()` and subject checks in `backend/system/api.py` to use durable relationships and keep subjects valid with zero materials.
- [X] T019 [US1] Update `adapter/scoped_projects.py` to return `ScopedProject.scoped_project_id` and `ScopedProject.internal_project_id` with no ambiguous `project_id` field.
- [X] T020 [US1] Update scoped route handlers in `adapter/routers/projects.py`, `adapter/routers/materials.py`, `adapter/routers/review.py`, `adapter/routers/learning_tasks.py`, `adapter/routers/layers.py`, `adapter/routers/media.py`, `adapter/routers/asr.py`, `adapter/routers/system.py`, `adapter/routers/push.py`, and `adapter/routers/validation.py` to use `scoped_project_id` when referencing the route identity.
- [X] T021 [US1] Update mapper output in `adapter/mappers.py` so subject material DTOs expose `scopedProjectId` for the subject-scoped identity and do not expose it as `projectId`.
- [X] T022 [US1] Run `python -m pytest tests/test_subject_material_persistence.py tests/test_subject_material_identity.py tests/test_scoped_project_api_boundaries.py` and record results in `docs/current-change.md`.

**Checkpoint**: User Story 1 works independently and fixes the restart failure for new data.

---

## Phase 4: User Story 2 - 身份语义清晰可排查 (Priority: P2)

**Goal**: API contracts, frontend route state, and diagnostics clearly distinguish `subjectId`, `scopedProjectId`, and `internalProjectId`.

**Independent Test**: Inspect API responses, frontend types, and logs for scoped workspace requests; no subject-material workflow uses one ambiguous field name for two identities.

### Tests for User Story 2

- [X] T023 [P] [US2] Add failing mapper/contract tests for `scopedProjectId` response fields in `tests/test_subject_material_identity.py`.
- [X] T024 [P] [US2] Add failing frontend type or unit tests for `ScopedProjectRef` and project path helpers in `frontend/tests/`.
- [X] T025 [P] [US2] Add failing backend diagnostic assertions for scoped resolution output in `tests/test_scoped_project_api_boundaries.py`.

### Implementation for User Story 2

- [X] T026 [US2] Rename frontend `ProjectScope` to `ScopedProjectRef` and `projectId` to `scopedProjectId` in `frontend/src/ui/api/projectScope.ts`.
- [X] T027 [US2] Update frontend path helpers in `frontend/src/ui/projectPaths.ts` to accept `scopedProjectId` while preserving existing URL shape.
- [X] T028 [US2] Update frontend query hooks in `frontend/src/ui/queries/` to pass `ScopedProjectRef` instead of `{ subjectId, projectId }`.
- [X] T029 [US2] Update scoped identity usage in `frontend/src/shell/` and `frontend/src/views/` so route params are normalized to `{ subjectId, scopedProjectId }` before API calls.
- [X] T030 [US2] Update virtual/demo data in `frontend/src/ui/guideWalkthrough/virtualStudyReviewProject.ts` to use `scopedProjectId` for subject material references.
- [X] T031 [US2] Add structured scoped-resolution diagnostic logging in `adapter/scoped_projects.py` or the approved backend boundary without logging sensitive user data.
- [X] T032 [US2] Run `pnpm --dir frontend test` and `pnpm --dir frontend build`, then record results in `docs/current-change.md`.

**Checkpoint**: User Story 2 works independently and removes identity naming ambiguity from the scoped workflow.

---

## Phase 5: User Story 3 - 既有线上数据可恢复 (Priority: P3)

**Goal**: Existing recoverable subject/material rows are migrated or validated deterministically without deleting internal projects or guessing at request time.

**Independent Test**: Run a production-shaped data recovery test where a subject row and an active material internal project row reconstruct one durable relationship, while incomplete rows report explicit integrity errors.

### Tests for User Story 3

- [X] T033 [P] [US3] Add failing recoverable-data migration tests in `tests/test_subject_material_persistence.py` using rows shaped like `subj_000003`, `scopedProjectId=proj_000001`, and `internalProjectId=proj_000099`.
- [X] T034 [P] [US3] Add failing integrity-error tests for missing subject, missing internal project, and deleted internal project cases in `tests/test_subject_material_persistence.py`.
- [X] T035 [P] [US3] Add failing tests proving a historical deleted global id with the same text as a scoped id is not used for resolution in `tests/test_subject_material_identity.py`.

### Implementation for User Story 3

- [X] T036 [US3] Implement deterministic relationship backfill or migration logic in `backend/system/postgres_store.py` and `backend/system/postgres_schema.py` for recoverable existing data.
- [X] T037 [US3] Implement explicit integrity validation/reporting for unrecoverable relationship records in `backend/system/api.py` or the persistence boundary selected by the implementation.
- [X] T038 [US3] Add a focused operator/developer validation command or script in `tools/` if integrity checks are not automatically surfaced during startup.
- [X] T039 [US3] Verify that subject/material deletion paths in `backend/system/api.py` and `adapter/routers/projects.py` remove or mark relationship records without deleting unrelated internal project data.
- [X] T040 [US3] Run `python -m pytest tests/test_subject_material_persistence.py tests/test_subject_material_identity.py tests/test_subject_material_atomicity.py` and record results in `docs/current-change.md`.

**Checkpoint**: User Story 3 works independently and existing recoverable data has a safe upgrade path.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final documentation, full verification, and deployment readiness.

- [X] T041 [P] Update `docs/data-model.md` with the final internal/scoped identity model and relationship persistence rules.
- [X] T042 [P] Update any affected API or module documentation under `docs/` so subject-scoped material identity is not documented as global `projectId`.
- [X] T043 Run repository-wide searches for ambiguous scoped identity names in `backend/`, `adapter/`, `frontend/src/`, `tests/`, and `docs/`, then resolve only in-scope findings.
- [X] T044 Run backend verification with `python -m pytest tests/test_subject_material_persistence.py tests/test_subject_material_identity.py tests/test_scoped_project_api_boundaries.py tests/test_subject_material_atomicity.py`.
- [X] T045 Run frontend verification with `pnpm --dir frontend test` and `pnpm --dir frontend build`.
- [X] T046 Run the manual smoke test from `specs/015-scoped-project-identity/quickstart.md` against a local or staging Postgres-backed environment.
- [X] T047 Finalize `docs/current-change.md` with modified files, behavior changes, test results, unresolved risks, and pollution-risk checklist.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational and is the MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational; can begin after the canonical backend/DTO contract from US1 is clear.
- **User Story 3 (Phase 5)**: Depends on Foundational; should run after US1 persistence behavior exists.
- **Polish (Phase 6)**: Depends on all selected user stories.

### User Story Dependencies

- **US1**: Required first for production failure repair.
- **US2**: Can proceed after foundational identity names are established, but final frontend/API contract should align with US1 DTOs.
- **US3**: Depends on US1 relationship persistence so migration targets the final durable model.

### Within Each User Story

- Test tasks must be written and fail before implementation tasks.
- Model and persistence changes precede API/adapter changes.
- API/adapter changes precede frontend call-site cleanup.
- Each checkpoint must be validated before moving to the next story unless the user explicitly chooses a broader batch.

---

## Parallel Opportunities

- Setup review tasks T002, T003, and T004 can run in parallel.
- Foundational model/interface tasks T005, T006, and T007 can run in parallel.
- US1 tests T012, T013, and T014 can run in parallel.
- US2 tests T023, T024, and T025 can run in parallel.
- US3 tests T033, T034, and T035 can run in parallel.
- Documentation tasks T041 and T042 can run in parallel after implementation stabilizes.

---

## Parallel Example: User Story 1

```text
Task: "T012 [US1] Add failing restart regression tests in tests/test_subject_material_persistence.py"
Task: "T013 [US1] Add failing multi-material reload tests in tests/test_subject_material_identity.py"
Task: "T014 [US1] Add failing invalid scoped material API tests in tests/test_scoped_project_api_boundaries.py"
```

---

## Parallel Example: User Story 2

```text
Task: "T023 [US2] Add mapper/contract tests in tests/test_subject_material_identity.py"
Task: "T024 [US2] Add frontend ScopedProjectRef tests in frontend/tests/"
Task: "T025 [US2] Add diagnostic assertions in tests/test_scoped_project_api_boundaries.py"
```

---

## Parallel Example: User Story 3

```text
Task: "T033 [US3] Add recoverable-data migration tests in tests/test_subject_material_persistence.py"
Task: "T034 [US3] Add integrity-error tests in tests/test_subject_material_persistence.py"
Task: "T035 [US3] Add deleted-global-id collision tests in tests/test_subject_material_identity.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Write failing US1 tests.
3. Implement durable subject-material persistence and hydration.
4. Validate US1 with the focused backend test command.
5. Stop and confirm the restart failure is fixed before broader naming cleanup.

### Incremental Delivery

1. Deliver US1 to restore the broken subject workspace flow.
2. Deliver US2 to remove identity naming ambiguity across API/frontend/diagnostics.
3. Deliver US3 to recover and validate existing production-shaped data.
4. Complete documentation and full verification.

### Guardrails

- Do not add request-time fallback to guess subject-material relationships.
- Do not delete internal project rows unless a deterministic integrity report proves they are unrelated.
- Do not convert all project-scoped storage tables to composite keys in this feature.
- Do not keep compatibility aliases for ambiguous identity names unless the user explicitly approves a compatibility strategy.
- Update `docs/current-change.md` whenever code is changed during implementation.
