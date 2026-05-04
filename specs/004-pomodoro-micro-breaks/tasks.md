# Tasks: Pomodoro Random Micro Breaks

**Input**: Design documents from `/specs/004-pomodoro-micro-breaks/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included because the plan and AGENTS guidance require TDD-oriented implementation, profile settings contract coverage, source-level frontend behavior assertions, targeted lint/build validation, and manual fullscreen validation.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently after shared foundations are complete.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on another incomplete task.
- **[Story]**: Maps the task to a user story from `spec.md`.
- Every task includes exact file paths.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare targeted test scaffolds and source references before changing Pomodoro behavior.

- [X] T001 Add shared micro break source-file constants to `tests/test_frontend_pomodoro_multi_plan.py` and `tests/test_frontend_fullscreen_capture.py`
- [X] T002 [P] Add backend micro break payload helper constants to `tests/test_profile_api.py`
- [X] T003 [P] Add quickstart validation command notes for this task sequence to `specs/004-pomodoro-micro-breaks/quickstart.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the shared settings model and global-settings contract required by all user stories.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Add failing frontend store assertions for `RandomMicroBreakSettings`, defaults, normalization, store version migration, and `setMicroBreakSettings` in `tests/test_frontend_pomodoro_multi_plan.py`
- [X] T005 Add failing frontend sync assertions for `pomodoro.microBreaks` Zod schema and bootstrap sync in `tests/test_frontend_pomodoro_multi_plan.py`
- [X] T006 Add failing backend profile API tests for default `microBreaks`, valid persistence, invalid interval ordering, and invalid bounds in `tests/test_profile_api.py`
- [X] T007 Add `RandomMicroBreakSettings` types, defaults, normalizers, store fields, setters, and persisted version migration in `frontend/src/ui/store/pomodoroStore.ts`
- [X] T008 Extend the frontend global settings schema and update payload with `pomodoro.microBreaks` in `frontend/src/ui/api/profile.ts`
- [X] T009 Wire remote `pomodoro.microBreaks` snapshots into the Pomodoro store in `frontend/src/ui/globalSettingsSync.ts`
- [X] T010 Extend backend request validation for `pomodoro.microBreaks` in `adapter/schemas.py`
- [X] T011 Normalize, persist, and return `pomodoro.microBreaks` in `backend/system/auth_store.py` and `adapter/routers/profile.py`

**Checkpoint**: Shared settings can be stored locally, synced through global settings, and validated by backend/profile tests.

---

## Phase 3: User Story 1 - Enable Random Micro Breaks During Pomodoro Fullscreen Study (Priority: P1) MVP

**Goal**: A learner in an active Pomodoro focus segment enters video fullscreen, receives a random micro break reminder, rests through a countdown, and returns to the previous playback state.

**Independent Test**: Enable random micro breaks, start an active Pomodoro focus segment, enter video fullscreen, and verify reminder sound, pause, countdown overlay, and conditional playback resume.

### Tests for User Story 1

- [X] T012 [US1] Add failing source assertions for Pomodoro focus fullscreen eligibility, randomized target scheduling, and countdown state in `tests/test_frontend_fullscreen_capture.py`
- [X] T013 [US1] Add failing source assertions for reminder sound helper usage, pre-break playback capture, video pause, and conditional resume in `tests/test_frontend_fullscreen_capture.py`
- [X] T014 [P] [US1] Add failing source assertions for the micro break reminder sound helper export in `tests/test_frontend_pomodoro_multi_plan.py`

### Implementation for User Story 1

- [X] T015 [US1] Add a dedicated `playPomodoroMicroBreakReminderSound` helper that reuses the existing audio unlock path in `frontend/src/ui/pomodoroAudio.ts`
- [X] T016 [US1] Import Pomodoro micro break settings, Pomodoro snapshot data, and reminder sound helper into `frontend/src/views/workbench/components/VideoPane.tsx`
- [X] T017 [US1] Implement fullscreen Pomodoro focus eligibility and segment identity derivation in `frontend/src/views/workbench/components/VideoPane.tsx`
- [X] T018 [US1] Implement randomized target scheduling, scheduled/resting state, and one-second countdown ticking in `frontend/src/views/workbench/components/VideoPane.tsx`
- [X] T019 [US1] Implement pre-break playback capture, video pause, countdown completion, and conditional video resume in `frontend/src/views/workbench/components/VideoPane.tsx`
- [X] T020 [US1] Render the fullscreen closed-eye micro break overlay and countdown in `frontend/src/views/workbench/components/VideoPane.tsx`

**Checkpoint**: User Story 1 is independently functional as the MVP when settings already exist and are enabled.

---

## Phase 4: User Story 2 - Configure Micro Break Preferences In Pomodoro Settings (Priority: P2)

**Goal**: A learner can enable random micro breaks and edit interval/duration values from the Pomodoro settings page, with values preserved for future Pomodoro sessions.

**Independent Test**: Open Pomodoro settings, enable random micro breaks, save valid interval and duration values, reload settings, and confirm the next fullscreen focus session uses those values.

### Tests for User Story 2

- [X] T021 [US2] Add failing source assertions for Pomodoro settings page toggle, min interval input, max interval input, duration input, validation feedback, save, and reset in `tests/test_frontend_pomodoro_multi_plan.py`
- [X] T022 [US2] Add failing source assertions that Pomodoro overview and global settings persistence payloads preserve `microBreaks` in `tests/test_frontend_pomodoro_multi_plan.py`

### Implementation for User Story 2

- [X] T023 [US2] Add micro break drafts, input controls, validation messages, and reset behavior to `frontend/src/views/pomodoro/PomodoroSettingsPage.tsx`
- [X] T024 [US2] Include `microBreaks` in Pomodoro settings save payloads and store updates in `frontend/src/views/pomodoro/PomodoroSettingsPage.tsx`
- [X] T025 [US2] Preserve `microBreaks` when saving Pomodoro schedule or toggle changes from `frontend/src/views/pomodoro/PomodoroPage.tsx`
- [X] T026 [US2] Preserve `microBreaks` in global settings persistence from `frontend/src/views/settings/GlobalSettingsPage.tsx`
- [X] T027 [US2] Document the random micro break setting, defaults, and Pomodoro-only behavior in `docs/learningpyramid-user-manual.md`

**Checkpoint**: User Story 2 is independently functional: settings can be configured, validated, saved, reset, and reused.

---

## Phase 5: User Story 3 - Avoid End-Of-Study Conflicts And Fullscreen Resets (Priority: P3)

**Goal**: Random micro breaks never conflict with Pomodoro ending prompts and always reset or cancel cleanly when fullscreen or Pomodoro state changes.

**Independent Test**: Enter fullscreen with 3 minutes or less remaining, verify no micro break triggers, verify the existing 10-second prompt still appears, exit/re-enter fullscreen to confirm timer reset, and cancel an active break without auto-resume.

### Tests for User Story 3

- [X] T028 [US3] Add failing source assertions for final 3-minute forbidden-window calculations and skipped scheduling in `tests/test_frontend_fullscreen_capture.py`
- [X] T029 [US3] Add failing source assertions that micro break overlay logic does not replace the existing 10-second Pomodoro transition preview overlays in `tests/test_frontend_fullscreen_capture.py`
- [X] T030 [US3] Add failing source assertions for fullscreen exit, Pomodoro ineligible state, route/unmount cleanup, and canceled-break no-resume behavior in `tests/test_frontend_fullscreen_capture.py`

### Implementation for User Story 3

- [X] T031 [US3] Add final 3-minute forbidden-boundary checks and skip-rather-than-clamp scheduling behavior in `frontend/src/views/workbench/components/VideoPane.tsx`
- [X] T032 [US3] Preserve existing 10-second focus/break transition preview rendering while adding micro break overlay priority in `frontend/src/views/workbench/components/VideoPane.tsx`
- [X] T033 [US3] Cancel pending and active micro breaks on fullscreen exit, Pomodoro phase/status changes, video unavailability, settings disable, and component unmount in `frontend/src/views/workbench/components/VideoPane.tsx`
- [X] T034 [US3] Ensure completed micro breaks schedule a next randomized interval only when still eligible and before the forbidden window in `frontend/src/views/workbench/components/VideoPane.tsx`

**Checkpoint**: User Story 3 is independently functional: end-of-study conflicts and cancellation paths behave safely.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and release-readiness checks across all selected stories.

- [X] T035 Run `python -m pytest tests/test_frontend_pomodoro_multi_plan.py tests/test_frontend_fullscreen_capture.py tests/test_profile_api.py` and fix failures in `tests/test_frontend_pomodoro_multi_plan.py`, `tests/test_frontend_fullscreen_capture.py`, or `tests/test_profile_api.py`
- [X] T036 Run targeted ESLint for touched frontend files and fix failures in `frontend/src/views/pomodoro/PomodoroSettingsPage.tsx`, `frontend/src/views/workbench/components/VideoPane.tsx`, `frontend/src/ui/store/pomodoroStore.ts`, `frontend/src/ui/pomodoroAudio.ts`, `frontend/src/ui/api/profile.ts`, and `frontend/src/ui/globalSettingsSync.ts`
- [X] T037 Run `pnpm --dir frontend build` and fix build failures in `frontend/src/ui/store/pomodoroStore.ts`, `frontend/src/views/pomodoro/PomodoroSettingsPage.tsx`, or `frontend/src/views/workbench/components/VideoPane.tsx`
- [ ] T038 Manually validate the quickstart flow and end-of-study conflict checks, then record any residual notes in `specs/004-pomodoro-micro-breaks/quickstart.md`
- [X] T039 Review `git diff --stat` and confirm no unrelated guide, Pomodoro, or playback changes were reverted in `specs/004-pomodoro-micro-breaks/tasks.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational; recommended MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational and can run independently of US1 runtime if settings persistence is being built first.
- **User Story 3 (Phase 5)**: Depends on Foundational and the US1 timer shell in `VideoPane.tsx`.
- **Polish (Phase 6)**: Depends on the selected completed user stories.

### User Story Dependencies

- **US1**: No dependency on other user stories after Foundational.
- **US2**: No dependency on US1 after Foundational; it configures the settings consumed by US1.
- **US3**: Depends on US1's runtime controller because conflict and cancellation rules refine scheduling behavior.

### Within Each User Story

- Tests are written before implementation tasks.
- Settings model and contract tasks precede UI/runtime usage.
- Audio helper precedes reminder playback usage.
- Scheduling state precedes pause/resume and overlay rendering.
- Cancellation and forbidden-window checks precede final manual validation.

## Parallel Opportunities

- T002 and T003 can run in parallel with T001.
- T008, T009, and T010 can run in parallel after T007 defines the frontend settings shape.
- T014 can run in parallel with T012 and T013 because it touches a different test file.
- T025, T026, and T027 can run in parallel after T023-T024 because they touch separate files.
- US3 implementation should be sequential because the conflict and cancellation tasks converge on `frontend/src/views/workbench/components/VideoPane.tsx`.
- T035, T036, and T037 should run after implementation converges; T038 is manual and follows those checks.

## Parallel Example: User Story 1

```text
Task: "Add failing source assertions for Pomodoro focus fullscreen eligibility, randomized target scheduling, and countdown state in tests/test_frontend_fullscreen_capture.py"
Task: "Add failing source assertions for the micro break reminder sound helper export in tests/test_frontend_pomodoro_multi_plan.py"
```

## Parallel Example: User Story 2

```text
Task: "Preserve microBreaks when saving Pomodoro schedule or toggle changes from frontend/src/views/pomodoro/PomodoroPage.tsx"
Task: "Preserve microBreaks in global settings persistence from frontend/src/views/settings/GlobalSettingsPage.tsx"
Task: "Document the random micro break setting, defaults, and Pomodoro-only behavior in docs/learningpyramid-user-manual.md"
```

## Sequencing Note: User Story 3

```text
Task: "Add final 3-minute forbidden-boundary checks and skip-rather-than-clamp scheduling behavior in frontend/src/views/workbench/components/VideoPane.tsx"
Task: "Preserve existing 10-second focus/break transition preview rendering while adding micro break overlay priority in frontend/src/views/workbench/components/VideoPane.tsx"
Task: "Cancel pending and active micro breaks on fullscreen exit, Pomodoro phase/status changes, video unavailability, settings disable, and component unmount in frontend/src/views/workbench/components/VideoPane.tsx"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 for User Story 1.
3. Run targeted tests covering `tests/test_frontend_fullscreen_capture.py`, `tests/test_frontend_pomodoro_multi_plan.py`, and `tests/test_profile_api.py`.
4. Demo an active Pomodoro focus fullscreen session where a random reminder pauses video, shows countdown, and restores playback.

### Incremental Delivery

1. Deliver shared settings model and global-settings persistence.
2. Add fullscreen runtime reminder behavior for US1 and validate the MVP.
3. Add Pomodoro settings controls for US2 and validate configuration persistence.
4. Add conflict/cancellation hardening for US3 and validate final 3-minute and fullscreen reset flows.
5. Run polish validation and document any residual manual verification risks.

### Parallel Team Strategy

1. One person completes shared settings and backend contract tasks.
2. One person builds the fullscreen runtime controller in `VideoPane.tsx`.
3. One person builds Pomodoro settings UI and persistence preservation.
4. One person writes/maintains source assertions and profile API tests.
5. Final validation runs after selected story phases converge.

## Notes

- Keep random micro breaks Pomodoro-only; do not trigger from normal non-Pomodoro fullscreen playback.
- Do not add new dependencies or a new endpoint.
- Do not store ephemeral fullscreen timer/session state in the persistent Pomodoro store.
- Canceled micro breaks must never auto-resume video.
- Preserve existing Pomodoro transition sound and 10-second prompt behavior.
- Be careful with the dirty worktree; do not revert unrelated guide, settings, or previous Pomodoro changes.
