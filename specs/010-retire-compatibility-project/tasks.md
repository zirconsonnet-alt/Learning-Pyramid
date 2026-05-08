# Tasks: Retire Compatibility Project

**Input**: Design documents from `/specs/010-retire-compatibility-project/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included because the feature changes public product contracts, persistence compatibility, and frontend routing behavior.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Each task includes exact file paths

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm current feature context and protect existing dirty worktree edits before contract work starts.

- [x] T001 Inspect current dirty worktree and note files already modified before implementation in `AGENTS.md`
- [x] T002 Review current subject/material references to `compatibilityProjectId` and `compatibility_project_id` in `backend/`, `adapter/`, `frontend/src/`, and `tests/`
- [x] T003 [P] Review current Pomodoro stopgap edits in `frontend/src/views/pomodoro/PomodoroPage.tsx` and `frontend/src/views/pomodoro/PomodoroWorkbenchGate.tsx`
- [x] T004 [P] Review current subject/project docs wording in `docs/learningpyramid-user-manual.md` and `docs/how-to-create-subject-project.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Lock the new contract first so user stories can be implemented against failing tests.

**CRITICAL**: No user story implementation should begin until these contract tests are updated and fail against the old implementation.

- [x] T005 Update subject create/list expectations from `compatibilityProjectId` to `subjectProjectId` in `tests/test_subjects_api.py`
- [x] T006 Update subject material expectations from `compatibilityProjectId` to `projectId` in `tests/test_subjects_api.py`
- [x] T007 [P] Add or update a static frontend guard rejecting `compatibilityProjectId` in subject/project consumers in `tests/test_frontend_llm_settings_location.py`
- [x] T008 Run `python -m pytest tests/test_subjects_api.py tests/test_frontend_llm_settings_location.py -q` and confirm the new contract tests fail before implementation

**Checkpoint**: Contract failure is visible and implementation can proceed.

---

## Phase 3: User Story 1 - Understand Subject And Project Boundaries Clearly (Priority: P1) MVP

**Goal**: Current subject and material contracts use clear `subjectProjectId` and `projectId` names, and the core subject/project navigation surfaces consume those names.

**Independent Test**: Create a subject with multiple materials, then verify subject pages, project pages, and settings use clear subject/project identifiers while preserving current behavior.

### Tests for User Story 1

- [x] T009 [P] [US1] Add negative assertions that subject responses omit `compatibilityProjectId` in `tests/test_subjects_api.py`
- [x] T010 [P] [US1] Add negative assertions that study material responses omit `compatibilityProjectId` in `tests/test_subjects_api.py`
- [x] T011 [P] [US1] Update frontend contract/static tests for `SubjectSchema`, `StudyMaterialSchema`, `ProjectsPage`, `SubjectDashboardPage`, and `AppShell` in `tests/test_frontend_llm_settings_location.py`

### Implementation for User Story 1

- [x] T012 [US1] Rename the study material domain field from `compatibility_project_id` to `project_id` in `backend/models/study_material.py`
- [x] T013 [US1] Update subject/material construction and lookup reads from `compatibility_project_id` to `project_id` in `backend/system/api.py`
- [x] T014 [US1] Rename material project local variables and helper names away from compatibility terminology in `backend/system/api.py`
- [x] T015 [US1] Emit `subjectProjectId` for subjects and `projectId` for study materials in `adapter/mappers.py`
- [x] T016 [US1] Return `subjectProjectId` from subject creation and use `item.project_id` for material ownership cleanup in `adapter/routers/projects.py`
- [x] T017 [US1] Update `SubjectSchema`, `StudyMaterialSchema`, and `CreateSubjectResultSchema` in `frontend/src/ui/api/subjects.ts`
- [x] T018 [US1] Replace subject list and create-subject consumers with `subject.subjectProjectId` and `res.subjectProjectId` in `frontend/src/views/projects/ProjectsPage.tsx`
- [x] T019 [US1] Replace subject dashboard material project consumers with `material.projectId` and `subject.subjectProjectId` in `frontend/src/views/subjects/SubjectDashboardPage.tsx`
- [x] T020 [US1] Replace route subject lookup and current material project resolution with `subjectProjectId` and `currentMaterial.projectId` in `frontend/src/shell/AppShell.tsx`
- [x] T021 [US1] Run `python -m pytest tests/test_subjects_api.py tests/test_frontend_llm_settings_location.py -q` and confirm User Story 1 contract tests pass

**Checkpoint**: User Story 1 should be functional and testable independently.

---

## Phase 4: User Story 2 - Existing Learning Data Continues To Open Correctly (Priority: P2)

**Goal**: Historical records with retired compatibility fields still load, while newly written study material records use the cleaned field names.

**Independent Test**: Load historical records saved with old field names and confirm they map into the new subject/project model without manual migration.

### Tests for User Story 2

- [x] T022 [P] [US2] Add JSON persistence regression for decoding old `compatibilityProjectId` material payloads in `tests/test_runtime_backup_restore.py`
- [x] T023 [P] [US2] Add persistence regression that newly encoded study materials write `projectId` and omit `compatibilityProjectId` in `tests/test_runtime_backup_restore.py`
- [x] T024 [P] [US2] Add subject-context regression covering a legacy root-backed material whose project identity equals the subject root in `tests/test_subjects_api.py`

### Implementation for User Story 2

- [x] T025 [US2] Update `_encode_study_material` to write `projectId` in `backend/system/persistence_json.py`
- [x] T026 [US2] Update `_decode_study_material` to read `projectId` first and fall back to old `compatibilityProjectId` in `backend/system/persistence_json.py`
- [x] T027 [US2] Ensure legacy root-backed materials are migrated to child material projects in `backend/system/api.py`
- [x] T028 [US2] Ensure subject context resolves migrated materials and child-material routes using `StudyMaterial.project_id` in `backend/system/api.py`
- [x] T029 [US2] Run `python -m pytest tests/test_subjects_api.py tests/test_runtime_backup_restore.py -q` and confirm legacy readability and new-write behavior pass

**Checkpoint**: User Story 2 should preserve old data access without reintroducing old outward contracts.

---

## Phase 5: User Story 3 - Follow-Up Features Stop Depending On The Dirty Concept (Priority: P3)

**Goal**: Settings, deletion, Pomodoro binding/gating, static guards, and docs no longer depend on the retired compatibility-project concept.

**Independent Test**: Exercise Pomodoro project selection, subject settings, project deletion, and subject deletion after the refactor and confirm all flows still work with the new field names.

### Tests for User Story 3

- [x] T030 [P] [US3] Update Pomodoro project filtering expectations from subject compatibility ids to `subjectProjectId` in `tests/test_frontend_pomodoro_multi_plan.py`
- [x] T031 [P] [US3] Update project settings copy/layout static expectations for clean subject/project wording in `tests/test_frontend_project_settings_layout.py`
- [x] T032 [P] [US3] Update subject/project copy static expectations to avoid compatibility-project wording in `tests/test_frontend_subject_project_copy.py`
- [x] T033 [P] [US3] Add backend/source static guard for retired field names outside persistence fallback in `tests/test_spec_alignment.py`

### Implementation for User Story 3

- [x] T034 [US3] Replace source course material filtering and delete-current-material checks with `material.projectId` in `frontend/src/views/settings/ProjectSettingsPage.tsx`
- [x] T035 [US3] Replace subject deletion local-state cleanup ids with `material.projectId` in `frontend/src/views/settings/ProjectSettingsPage.tsx`
- [x] T036 [US3] Replace subject-root Pomodoro exclusion set with `subject.subjectProjectId` in `frontend/src/views/pomodoro/PomodoroPage.tsx`
- [x] T037 [US3] Replace Pomodoro workbench gate subject-root exclusion set with `subject.subjectProjectId` in `frontend/src/views/pomodoro/PomodoroWorkbenchGate.tsx`
- [x] T038 [US3] Remove compatibility-project wording from user-facing docs in `docs/learningpyramid-user-manual.md`
- [x] T039 [US3] Remove compatibility-project wording from subject/project guide docs in `docs/how-to-create-subject-project.md`
- [x] T040 [US3] Run `python -m pytest tests/test_frontend_pomodoro_multi_plan.py tests/test_frontend_project_settings_layout.py tests/test_frontend_subject_project_copy.py tests/test_spec_alignment.py -q` and confirm dependent-flow tests pass

**Checkpoint**: All dependent flows should use the clean subject/project model.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verify the whole refactor and remove remaining dirty concept leaks.

- [x] T041 [P] Run source scan `rg -n "compatibilityProjectId|compatibility_project_id|compatible project|兼容项目" backend adapter frontend/src tests docs -S` and confirm only allowed legacy-read fallback and explicit guard tests remain
- [x] T042 [P] Run focused backend validation `python -m pytest tests/test_subjects_api.py tests/test_sqlite_store.py tests/test_runtime_backup_restore.py -q`
- [x] T043 [P] Run focused frontend/static validation `python -m pytest tests/test_frontend_pomodoro_multi_plan.py tests/test_frontend_llm_settings_location.py tests/test_frontend_subject_project_copy.py tests/test_frontend_project_settings_layout.py -q`
- [x] T044 Run targeted frontend lint from `frontend/` with `npx eslint src/ui/api/subjects.ts src/shell/AppShell.tsx src/views/projects/ProjectsPage.tsx src/views/subjects/SubjectDashboardPage.tsx src/views/settings/ProjectSettingsPage.tsx src/views/pomodoro/PomodoroPage.tsx src/views/pomodoro/PomodoroWorkbenchGate.tsx`
- [x] T045 Run frontend production build from `frontend/` with `npm run build`
- [x] T046 Update implementation notes or quickstart validation results in `specs/010-retire-compatibility-project/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; can start immediately.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user-story implementation.
- **User Story 1 (Phase 3)**: Depends on Foundational; MVP for the cleaned subject/project contract.
- **User Story 2 (Phase 4)**: Depends on User Story 1 domain/DTO rename so legacy reads map into the new field names.
- **User Story 3 (Phase 5)**: Depends on User Story 1 frontend contract updates; can overlap with User Story 2 after the new field names exist.
- **Polish (Phase 6)**: Depends on all desired user stories.

### User Story Dependencies

- **US1 (P1)**: No dependency on other stories after Foundational.
- **US2 (P2)**: Requires the `StudyMaterial.project_id` model shape from US1.
- **US3 (P3)**: Requires `Subject.subjectProjectId` and `StudyMaterial.projectId` frontend schemas from US1.

### Parallel Opportunities

- T003 and T004 can run in parallel during setup.
- T007 can run in parallel with T005/T006 because it targets frontend static coverage.
- T009, T010, and T011 can run in parallel before US1 implementation.
- T022, T023, and T024 can run in parallel before US2 implementation.
- T030, T031, T032, and T033 can run in parallel before US3 implementation.
- T041, T042, and T043 can run in parallel during final verification.

---

## Parallel Example: User Story 1

```text
Task: "T009 [P] [US1] Add negative assertions that subject responses omit compatibilityProjectId in tests/test_subjects_api.py"
Task: "T010 [P] [US1] Add negative assertions that study material responses omit compatibilityProjectId in tests/test_subjects_api.py"
Task: "T011 [P] [US1] Update frontend contract/static tests for SubjectSchema, StudyMaterialSchema, ProjectsPage, SubjectDashboardPage, and AppShell in tests/test_frontend_llm_settings_location.py"
```

## Parallel Example: User Story 2

```text
Task: "T022 [P] [US2] Add JSON persistence regression for decoding old compatibilityProjectId material payloads in tests/test_runtime_backup_restore.py"
Task: "T023 [P] [US2] Add persistence regression that newly encoded study materials write projectId and omit compatibilityProjectId in tests/test_runtime_backup_restore.py"
Task: "T024 [P] [US2] Add subject-context regression covering a legacy root-backed material whose project identity equals the subject root in tests/test_subjects_api.py"
```

## Parallel Example: User Story 3

```text
Task: "T030 [P] [US3] Update Pomodoro project filtering expectations from subject compatibility ids to subjectProjectId in tests/test_frontend_pomodoro_multi_plan.py"
Task: "T031 [P] [US3] Update project settings copy/layout static expectations for clean subject/project wording in tests/test_frontend_project_settings_layout.py"
Task: "T032 [P] [US3] Update subject/project copy static expectations to avoid compatibility-project wording in tests/test_frontend_subject_project_copy.py"
Task: "T033 [P] [US3] Add backend/source static guard for retired field names outside persistence fallback in tests/test_spec_alignment.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup and Foundational phases.
2. Implement US1 contract rename across backend DTOs and core frontend subject/project consumers.
3. Stop and validate with `tests/test_subjects_api.py` and `tests/test_frontend_llm_settings_location.py`.

### Incremental Delivery

1. US1 delivers clean current contracts and core navigation consumption.
2. US2 adds historical data safety.
3. US3 updates dependent flows and documentation.
4. Polish verifies the refactor end to end.

### Notes

- Write or update tests before each story implementation and verify they fail against the old behavior when practical.
- Keep `persistence_json.py` as the only production location allowed to mention the retired field name for backward-read fallback.
- Preserve existing Pomodoro stopgap behavior while changing the subject-root identifier source.
- Do not delete subject/project data as part of this feature.
