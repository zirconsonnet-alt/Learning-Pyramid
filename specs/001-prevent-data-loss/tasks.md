# Tasks: Prevent Server Data Loss

**Input**: Design documents from `/specs/001-prevent-data-loss/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included because the specification requires automated checks for deployment safety, backup integrity, restore validation, broken references, and user-facing unavailable states.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested independently.

## Phase 1: Setup

**Purpose**: Establish shared test fixtures and implementation locations for data-safety work.

- [X] T001 Create reusable hosted runtime fixture helpers in `tests/fixtures/data_safety_runtime.py`
- [X] T002 [P] Create data-safety test package marker in `tests/test_data_safety_status.py`
- [X] T003 [P] Create operator CLI test package marker in `tests/test_runtime_backup_restore.py`
- [X] T004 [P] Document implementation entry points in `specs/001-prevent-data-loss/quickstart.md`

---

## Phase 2: Foundational

**Purpose**: Shared data-safety primitives that block all user stories.

**Critical**: No user story implementation should begin until this phase is complete.

- [X] T005 Add failing unit tests for protected data class inventory in `tests/test_data_safety_status.py`
- [X] T006 Add failing unit tests for blocking/warning state aggregation in `tests/test_data_safety_status.py`
- [X] T007 Create data-safety domain models in `backend/system/data_safety.py`
- [X] T008 Implement protected production data inventory in `backend/system/data_safety.py`
- [X] T009 Implement data-safety status aggregation rules in `backend/system/data_safety.py`
- [X] T010 [P] Add audit event model and JSON persistence helpers in `backend/system/data_safety_audit.py`
- [X] T011 [P] Add data-safety configuration defaults in `backend/system/runtime_features.py`
- [X] T012 Wire data-safety status service into backend system API access in `backend/system/api.py`

**Checkpoint**: Data-safety state, protected data classes, and audit primitives exist and pass foundational tests.

---

## Phase 3: User Story 1 - Protect User Data During Operations (Priority: P1)

**Goal**: Prevent routine deploy, sync, restart, rebuild, and maintenance operations from deleting, shadowing, or hiding protected user data.

**Independent Test**: Seed a hosted-like environment with representative users, projects, recall points, media, review state, and membership records; run deploy/sync/restart-like checks; verify data remains accessible and unsafe operations are blocked before changes occur.

### Tests for User Story 1

- [X] T013 [P] [US1] Add failing compose persistence test for all protected filesystem roots in `tests/test_hosted_deployment_checks.py`
- [X] T014 [P] [US1] Add failing preflight blocker tests for missing, unreadable, unwritable, and empty-unexpected protected paths in `tests/test_hosted_deployment_checks.py`
- [X] T015 [P] [US1] Add failing sync-script safety tests for protected path delete rules in `tests/test_hosted_deployment_checks.py`
- [X] T016 [P] [US1] Add failing frontend/API unavailable-state test in `tests/test_data_safety_status.py`

### Implementation for User Story 1

- [X] T017 [US1] Extend hosted deployment checks with protected storage path validation in `backend/system/hosted_deployment_checks.py`
- [X] T018 [US1] Add preflight blocker output for missing, unreadable, unwritable, and empty-unexpected protected paths in `backend/system/hosted_deployment_checks.py`
- [X] T019 [US1] Protect runtime data paths from rsync delete behavior in `tools/sync_selfhost_server.ps1`
- [X] T020 [US1] Mirror protected path safeguards in shell sync workflow in `tools/sync_selfhost_server.sh`
- [X] T021 [US1] Add post-deploy representative data validation service in `backend/system/data_safety.py`
- [X] T022 [US1] Expose data-safety status endpoint in `adapter/routers/system.py`
- [X] T023 [US1] Add frontend API client for data-safety status in `frontend/src/ui/api/system.ts`
- [X] T024 [US1] Display inaccessible/degraded data state instead of silent empty state in `frontend/src/views/projects/ProjectsPage.tsx`
- [X] T025 [US1] Update self-host deployment safety documentation in `docs/self-host.md`

**Checkpoint**: MVP complete. Routine operations fail closed when protected data is at risk, and users do not see inaccessible existing data as an empty workspace.

---

## Phase 4: User Story 2 - Recover Quickly From Data Incidents (Priority: P2)

**Goal**: Produce complete verified backups, including uploaded media, and restore them into a usable environment with explicit operator confirmation and post-restore verification.

**Independent Test**: Create representative data, generate a verified backup, restore into a clean environment, and verify users, projects, media, membership state, and progress match the source.

### Tests for User Story 2

- [X] T026 [P] [US2] Add failing backup manifest and checksum tests in `tests/test_runtime_backup_restore.py`
- [X] T027 [P] [US2] Add failing media payload inclusion tests in `tests/test_runtime_backup_restore.py`
- [X] T028 [P] [US2] Add failing restore dry-run and explicit confirmation tests in `tests/test_runtime_backup_restore.py`
- [X] T029 [P] [US2] Add failing clean-environment restore integration test in `tests/test_runtime_backup_restore.py`

### Implementation for User Story 2

- [X] T030 [US2] Extend backup manifest schema and verification output in `tools/backup_runtime_bundle.py`
- [X] T031 [US2] Include uploaded media payloads and checksums in `tools/backup_runtime_bundle.py`
- [X] T032 [US2] Add `--verify-only` behavior for existing backup bundles in `tools/backup_runtime_bundle.py`
- [X] T033 [US2] Implement restore dry-run planning in `tools/restore_runtime_bundle.py`
- [X] T034 [US2] Require `--confirm-replace` for destructive restore application in `tools/restore_runtime_bundle.py`
- [X] T035 [US2] Restore media payloads through staging paths in `tools/restore_runtime_bundle.py`
- [X] T036 [US2] Run post-restore data-safety verification from `tools/restore_runtime_bundle.py`
- [X] T037 [US2] Record backup and restore audit events in `backend/system/data_safety_audit.py`
- [X] T038 [US2] Update backup and restore operator documentation in `docs/self-host.md`

**Checkpoint**: Operators can create verified full backups and restore them without guessing which files or records were included.

---

## Phase 5: User Story 3 - Detect and Explain Data Risk (Priority: P3)

**Goal**: Detect broken references, storage risks, stale backups, and unsafe overrides early, then explain findings to operators with audit history.

**Independent Test**: Introduce missing media files, orphaned media files, stale backup metadata, and an emergency override; verify findings and audit events include affected identifiers and recommended actions.

### Tests for User Story 3

- [X] T039 [P] [US3] Add failing broken media reference tests in `tests/test_data_safety_integrity.py`
- [X] T040 [P] [US3] Add failing orphaned media and inaccessible path tests in `tests/test_data_safety_integrity.py`
- [X] T041 [P] [US3] Add failing emergency override audit tests in `tests/test_data_safety_audit.py`
- [X] T042 [P] [US3] Add failing data-safety API contract tests in `tests/test_data_safety_status.py`

### Implementation for User Story 3

- [X] T043 [US3] Implement media reference scanner in `backend/system/data_safety.py`
- [X] T044 [US3] Implement integrity finding generation with affected project and asset ids in `backend/system/data_safety.py`
- [X] T045 [US3] Add `tools/check_data_safety.py` CLI for JSON integrity checks
- [X] T046 [US3] Implement emergency override validation and expiry handling in `backend/system/data_safety_audit.py`
- [X] T047 [US3] Add operator-facing latest backup and integrity summary to `adapter/routers/system.py`
- [X] T048 [US3] Add admin data-safety status panel in `frontend/src/views/admin/AdminPage.tsx`
- [X] T049 [US3] Document integrity findings and emergency overrides in `docs/self-host.md`

**Checkpoint**: Operators can see current data risk, broken references are reported with identifiers, and overrides are explicit and auditable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation, docs alignment, and release readiness.

- [X] T050 [P] Run hosted deployment safety tests and record command in `specs/001-prevent-data-loss/quickstart.md`
- [X] T051 [P] Run backup/restore tests and record command in `specs/001-prevent-data-loss/quickstart.md`
- [X] T052 [P] Run frontend build after UI changes and record command in `specs/001-prevent-data-loss/quickstart.md`
- [X] T053 Review README operator notes for data safety entry points in `README.md`
- [X] T054 Confirm no unresolved data-safety blockers before release in `specs/001-prevent-data-loss/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1): no dependencies.
- Foundational (Phase 2): depends on Setup and blocks all user stories.
- User Story 1 (Phase 3): depends on Foundational and is the MVP.
- User Story 2 (Phase 4): depends on Foundational; can run after or alongside US1 once shared primitives exist.
- User Story 3 (Phase 5): depends on Foundational; gains more value after US1/US2 but remains independently testable with fixtures.
- Polish (Phase 6): depends on selected user stories being complete.

### User Story Dependencies

- US1 Protect User Data During Operations: no dependency on US2 or US3 after foundation.
- US2 Recover Quickly From Data Incidents: no dependency on US1 UI work; depends only on shared models/audit primitives.
- US3 Detect and Explain Data Risk: no dependency on US2 restore implementation; can use fixtures to validate integrity findings.

### Within Each User Story

- Write failing tests before implementation.
- Implement backend/domain services before API and CLI integrations.
- Implement API before frontend consumers.
- Update docs in the same story when operator workflow changes.

---

## Parallel Opportunities

- Setup tasks T002, T003, and T004 can run in parallel after T001 is planned.
- Foundational tasks T010 and T011 can run in parallel with domain model implementation after T007.
- US1 tests T013 through T016 can run in parallel.
- US2 tests T026 through T029 can run in parallel.
- US3 tests T039 through T042 can run in parallel.
- US2 backup implementation and US3 integrity scanner can be developed in parallel after T005 through T012 are complete.
- Frontend tasks T023, T024, and T048 can run after their corresponding API contract tasks are defined.

## Parallel Example: User Story 1

```text
Task: "T013 [P] [US1] Add failing compose persistence test for all protected filesystem roots in tests/test_hosted_deployment_checks.py"
Task: "T014 [P] [US1] Add failing preflight blocker tests for missing, unreadable, unwritable, and empty-unexpected protected paths in tests/test_hosted_deployment_checks.py"
Task: "T016 [P] [US1] Add failing frontend/API unavailable-state test in tests/test_data_safety_status.py"
```

## Parallel Example: User Story 2

```text
Task: "T026 [P] [US2] Add failing backup manifest and checksum tests in tests/test_runtime_backup_restore.py"
Task: "T027 [P] [US2] Add failing media payload inclusion tests in tests/test_runtime_backup_restore.py"
Task: "T028 [P] [US2] Add failing restore dry-run and explicit confirmation tests in tests/test_runtime_backup_restore.py"
```

## Parallel Example: User Story 3

```text
Task: "T039 [P] [US3] Add failing broken media reference tests in tests/test_data_safety_integrity.py"
Task: "T041 [P] [US3] Add failing emergency override audit tests in tests/test_data_safety_audit.py"
Task: "T042 [P] [US3] Add failing data-safety API contract tests in tests/test_data_safety_status.py"
```

---

## Implementation Strategy

### MVP First: User Story 1

1. Complete Setup and Foundational phases.
2. Complete US1 tests and implementation.
3. Validate deployment/storage blockers and user-facing unavailable state.
4. Deploy only after protected data checks pass.

### Incremental Delivery

1. Deliver US1 to prevent new operational data loss.
2. Deliver US2 to make recovery complete and verified.
3. Deliver US3 to improve early detection, auditability, and operator explanation.
4. Finish polish validation and documentation updates.

### Release Gate

No hosted production deployment should proceed with unresolved blocking integrity findings, missing protected storage, stale required backup, or unaudited destructive override.

---

## Notes

- `[P]` marks tasks that can be worked on in parallel because they use different files or do not depend on an incomplete task.
- `[US1]`, `[US2]`, and `[US3]` map directly to the prioritized user stories in [spec.md](./spec.md).
- Tests are intentionally first because this feature is safety-critical and the specification requires automated checks.
