# Tasks: Study Metrics Rework

**Input**: Design documents from `specs/011-study-metrics-rework/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Required by the plan and AGENTS guidance because this feature changes metric behavior, sync contracts, and user-facing UI.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently after the shared foundation is complete.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other marked tasks in the same phase because it touches different files or only adds tests.
- **[Story]**: User-story label for story phases only.
- Every task names the exact file path(s) it touches.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the test harness and lock the intended metric vocabulary before implementation.

- [X] T001 Create frontend metric assertion test scaffold with shared path constants in `tests/test_frontend_workbench_metrics.py`
- [X] T002 [P] Add study metric sync contract fixture helpers to `tests/test_profile_api.py`
- [X] T003 [P] Add metric vocabulary documentation anchors to `docs/learningpyramid-user-manual.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Build the shared metric model, persistence shape, and sync contract that all user stories depend on.

**CRITICAL**: No user story work can begin until this phase is complete.

### Tests

- [X] T004 [P] Add failing range-normalization and partition invariant assertions in `tests/test_frontend_workbench_metrics.py`
- [X] T005 [P] Add failing new study-metrics sync schema assertions in `tests/test_profile_api.py`
- [X] T006 [P] Add failing backend legacy-read compatibility assertions in `tests/test_profile_api.py`

### Implementation

- [X] T007 Replace legacy daily metric types with web-presence/category interval types in `frontend/src/ui/store/workbenchDailyStats.ts`
- [X] T008 Implement local-date splitting, range normalization, category overlap resolution, and `webPresenceMs = videoMs + recallEntryMs + reviewMs + aiQaMs + distractionMs` summary generation in `frontend/src/ui/store/workbenchDailyStats.ts`
- [X] T009 Update web presence tracker to record objective presence ranges without using effective-study fallback in `frontend/src/ui/store/studyPresenceStore.ts`
- [X] T010 Update frontend profile metric schemas with `schemaVersion`, `webPresenceMs`, `presenceRanges`, `recallEntryMs`, `recallEntryRanges`, `distractionMs`, and partition completeness fields in `frontend/src/ui/api/profile.ts`
- [X] T011 Update study metric snapshot sync to list and merge the new web-presence metric entries in `frontend/src/ui/studyMetricsSync.ts`
- [X] T012 Update request DTOs for the new study metric fields while retaining legacy optional fields in `adapter/schemas.py`
- [X] T013 Update profile study metric DTO mapping and sync input construction for new fields in `adapter/routers/profile.py`
- [X] T014 Extend hosted study metric dataclasses, merge logic, and SQLite legacy-read handling for new fields in `backend/system/auth_store.py`
- [X] T015 Extend PostgreSQL hosted study metric schema and merge logic for new fields in `backend/system/postgres_schema.py` and `backend/system/auth_store.py`

**Checkpoint**: The project can store, normalize, sync, and reload complete web-presence metric partitions, while legacy records remain readable but incomplete.

---

## Phase 3: User Story 1 - Read Objective Workbench Study Time (Priority: P1) MVP

**Goal**: The workbench status card shows only objective web presence and its category partition, with no synthetic effective-learning or focus-rate rows.

**Independent Test**: Spend time in the workbench across video, recall entry, review, AI Q&A, and inactive web presence; the expanded card shows only the six new rows and their total partition is exact.

### Tests for User Story 1

- [X] T016 [P] [US1] Add failing workbench card label assertions for new rows and removed legacy rows in `tests/test_frontend_workbench_metrics.py`
- [X] T017 [P] [US1] Add failing source assertions that Pomodoro-only time cannot raise workbench web presence in `tests/test_frontend_workbench_metrics.py`
- [X] T018 [P] [US1] Add failing recorder assertions for video, recall entry, review, and AI Q&A category names in `tests/test_frontend_workbench_metrics.py`

### Implementation for User Story 1

- [X] T019 [US1] Update workbench card state loading from daily effective stats to web metric summaries in `frontend/src/views/workbench/WorkbenchPage.tsx`
- [X] T020 [US1] Replace the collapsed workbench card headline and expanded rows with `网页驻留`, `视频观看`, `复述点录入`, `复习用时`, `AI 问答`, and `走神时间` in `frontend/src/views/workbench/WorkbenchPage.tsx`
- [X] T021 [US1] Remove legacy workbench card rows for effective learning, learning stay, focus rate, content contact, recall construction, and recall counts from `frontend/src/views/workbench/WorkbenchPage.tsx`
- [X] T022 [US1] Record actual wall-clock video playback as the `video` category only while playing and web-present in `frontend/src/views/workbench/components/VideoPane.tsx`
- [X] T023 [US1] Record recall point entry windows as the `recallEntry` category in `frontend/src/views/workbench/components/ComposePane.tsx`
- [X] T024 [US1] Record embedded player recall draft activity as the `recallEntry` category in `frontend/src/views/workbench/components/VideoPane.tsx`
- [X] T025 [US1] Record review operation windows as the `review` category in `frontend/src/views/workbench/components/ReviewPane.tsx`
- [X] T026 [US1] Record full-screen AI Q&A windows as the `aiQa` category in `frontend/src/views/ai/AiChatPage.tsx`
- [X] T027 [US1] Update profile/friends/admin metric consumers to avoid assuming `effectiveMs` is the workbench card headline in `frontend/src/views/profile/ProfilePage.tsx`, `frontend/src/views/friends/FriendsPage.tsx`, and `frontend/src/views/admin/AdminPage.tsx`

**Checkpoint**: User Story 1 is fully functional and testable independently: the workbench card is truthful, objective, and no longer displays the bad `max(presence, effective)` behavior.

---

## Phase 4: User Story 2 - Distinguish Distraction From Active Learning States (Priority: P2)

**Goal**: Distraction time is the web-present remainder outside video, recall entry, review, and AI Q&A, and time stops accumulating when the learner is not web-present.

**Independent Test**: Stay on the page without active study actions and see distraction increase; start an active category and see distraction stop; hide or leave the page and see no web metric increase.

### Tests for User Story 2

- [X] T028 [P] [US2] Add failing distraction remainder assertions in `tests/test_frontend_workbench_metrics.py`
- [X] T029 [P] [US2] Add failing paused-video and hidden-page source assertions in `tests/test_frontend_workbench_metrics.py`
- [X] T030 [P] [US2] Add failing overlap-priority assertions for foreground category resolution in `tests/test_frontend_workbench_metrics.py`

### Implementation for User Story 2

- [X] T031 [US2] Derive `distractionMs` from web presence minus resolved active category ranges in `frontend/src/ui/store/workbenchDailyStats.ts`
- [X] T032 [US2] Ensure hidden tabs, invisible documents, and inactive presence windows stop adding web presence in `frontend/src/ui/store/studyPresenceStore.ts`
- [X] T033 [US2] Ensure open-but-paused videos do not record `video` category time in `frontend/src/views/workbench/components/VideoPane.tsx`
- [X] T034 [US2] Add foreground category source tracking so overlapping windows resolve consistently in `frontend/src/ui/store/workbenchDailyStats.ts`
- [X] T035 [US2] Refresh the workbench card every second from the derived summary rather than summing raw category counters in `frontend/src/views/workbench/WorkbenchPage.tsx`

**Checkpoint**: User Story 2 is independently verifiable: idle web-present time becomes distraction, active windows replace distraction, and no hidden/off-page time is counted.

---

## Phase 5: User Story 3 - Inspect Pomodoro Learning By Plan And Pomodoro (Priority: P3)

**Goal**: Pomodoro statistics slice the same objective metric partition by plan and numbered Pomodoro, then show absence time, attendance rate, effective learning rate, and a visual breakdown.

**Independent Test**: Run or simulate a Pomodoro focus segment with partial web presence; the Pomodoro statistics panel shows per-plan and per-Pomodoro category values, absence time, and derived rates, while the workbench card remains independent of Pomodoro scheduled time.

### Tests for User Story 3

- [X] T036 [P] [US3] Add failing assertion that Pomodoro completion no longer calls `recordEffectiveStudyActivity` in `tests/test_frontend_pomodoro_multi_plan.py`
- [X] T037 [P] [US3] Add failing per-plan and per-Pomodoro statistics source assertions in `tests/test_frontend_pomodoro_multi_plan.py`
- [X] T038 [P] [US3] Add failing pie/donut visual breakdown source assertions in `tests/test_frontend_pomodoro_multi_plan.py`
- [X] T039 [P] [US3] Add failing absence and effective-learning-rate formula assertions in `tests/test_frontend_pomodoro_multi_plan.py`

### Implementation for User Story 3

- [X] T040 [US3] Stop writing completed scheduled focus blocks into workbench effective study metrics in `frontend/src/ui/store/pomodoroActivityStore.ts`
- [X] T041 [US3] Keep Pomodoro activity records as schedule markers with plan, numbered Pomodoro, project, start, end, and completion metadata in `frontend/src/ui/store/pomodoroActivityStore.ts`
- [X] T042 [US3] Add helpers to slice web metric summaries by arbitrary time range and Pomodoro focus segment in `frontend/src/ui/store/workbenchDailyStats.ts`
- [X] T043 [US3] Build per-plan and per-numbered-Pomodoro metric summaries from Pomodoro schedule snapshots and sliced web metrics in `frontend/src/views/pomodoro/PomodoroPage.tsx`
- [X] T044 [US3] Calculate `absenceMs`, `attendanceRate`, `activeLearningMs`, and `effectiveLearningRate` for Pomodoro statistics in `frontend/src/views/pomodoro/PomodoroPage.tsx`
- [X] T045 [US3] Replace the current simple Pomodoro completion statistics panel with per-plan/per-Pomodoro rows in `frontend/src/views/pomodoro/PomodoroPage.tsx`
- [X] T046 [US3] Add pie-style or donut-style scheduled-focus breakdown for active categories, distraction, and absence in `frontend/src/views/pomodoro/PomodoroPage.tsx`
- [X] T047 [US3] Mark in-progress Pomodoro statistics as incomplete and exclude them from final completed counts in `frontend/src/views/pomodoro/PomodoroPage.tsx`

**Checkpoint**: User Story 3 is independently verifiable: Pomodoro statistics explain planned versus actual study time without changing the workbench metric definitions.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, compatibility review, and final verification.

- [X] T048 [P] Update user manual metric definitions and Pomodoro statistics explanation in `docs/learningpyramid-user-manual.md`
- [X] T049 [P] Update any affected source assertions for admin/profile/friend aggregate labels in `tests/test_admin_api.py` and `tests/test_frontend_friends_page_ui.py`
- [X] T050 Re-run frontend metric and Pomodoro source tests with `pytest tests/test_frontend_workbench_metrics.py tests/test_frontend_pomodoro_multi_plan.py`
- [X] T051 Re-run profile/admin API compatibility tests with `pytest tests/test_profile_api.py tests/test_admin_api.py`
- [X] T052 Run frontend production build validation with `pnpm --dir frontend build`
- [ ] T053 Perform quickstart manual validation from `specs/011-study-metrics-rework/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion and is the MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational completion; can be implemented after or alongside US1, but final UX validation is clearer after US1 card rows exist.
- **User Story 3 (Phase 5)**: Depends on Foundational completion and uses the same metric store; it can proceed once slicing helpers from T042 are planned against the store API.
- **Polish (Phase 6)**: Depends on the desired user stories being complete.

### User Story Dependencies

- **US1**: No dependency on US2 or US3 after Foundation; delivers the truthful workbench card MVP.
- **US2**: Builds on the same metric summary API as US1; independently proves the distraction remainder behavior.
- **US3**: Builds on the same metric summary API and Pomodoro schedule records; independently proves Pomodoro plan/segment statistics.

### Parallel Opportunities

- T001-T003 can start together if separated by file ownership.
- T004-T006 can be written in parallel before implementation.
- T010-T015 touch frontend API, adapter, and backend storage and can be split between frontend/backend owners after T007-T009 define the shared field names.
- US1 recorder tasks T022-T026 touch separate components and can run in parallel after T019-T021 establish the card summary API.
- US2 tests T028-T030 can run in parallel; implementation T031-T034 should be coordinated because they share the summary model.
- US3 tests T036-T039 can run in parallel; T045-T047 can be split after T043-T044 produce the summary data.

---

## Parallel Example: User Story 1

```text
Task: "T022 [US1] Record actual wall-clock video playback as the video category in frontend/src/views/workbench/components/VideoPane.tsx"
Task: "T023 [US1] Record recall point entry windows in frontend/src/views/workbench/components/ComposePane.tsx"
Task: "T025 [US1] Record review operation windows in frontend/src/views/workbench/components/ReviewPane.tsx"
Task: "T026 [US1] Record full-screen AI Q&A windows in frontend/src/views/ai/AiChatPage.tsx"
```

## Parallel Example: User Story 3

```text
Task: "T036 [US3] Add Pomodoro completion source assertion in tests/test_frontend_pomodoro_multi_plan.py"
Task: "T037 [US3] Add per-plan/per-Pomodoro statistics assertions in tests/test_frontend_pomodoro_multi_plan.py"
Task: "T038 [US3] Add pie/donut visual assertions in tests/test_frontend_pomodoro_multi_plan.py"
Task: "T039 [US3] Add formula assertions in tests/test_frontend_pomodoro_multi_plan.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 setup.
2. Complete Phase 2 foundation.
3. Complete Phase 3 User Story 1.
4. Stop and validate `pytest tests/test_frontend_workbench_metrics.py`.
5. Manually verify the workbench card no longer shows synthetic effective-learning/focus rows.

### Incremental Delivery

1. Foundation: shared metric model and sync contract.
2. US1: truthful workbench card.
3. US2: robust distraction and overlap semantics.
4. US3: Pomodoro plan/segment statistics.
5. Polish: docs, compatibility assertions, build, and manual quickstart.

### Notes

- Write test tasks first and confirm they fail before implementing each story.
- Do not reintroduce a card-level `max(presence, effective)` fallback.
- Do not let completed Pomodoro scheduled focus time create web presence.
- Preserve legacy metric readability without pretending old data has a complete web-presence partition.
