# Tasks: Page Walkthrough Guide

**Input**: Design documents from `/specs/003-driver-page-guide/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included because the plan requires static validation for dependency/configuration, guide document removal, source-copy references, target anchor coverage, fallback coverage, and manual alignment, plus frontend build/lint validation.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on another incomplete task.
- **[Story]**: Maps the task to a user story from `spec.md`.
- Every task includes exact file paths.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the dependency, module locations, and validation scaffold without changing guide behavior yet.

- [X] T001 Add the `driver.js` dependency to `frontend/package.json` and `frontend/pnpm-lock.yaml`
- [X] T002 Create placeholder walkthrough module exports in `frontend/src/ui/guideWalkthrough/guideWalkthroughCopy.ts`, `frontend/src/ui/guideWalkthrough/guideWalkthroughSteps.ts`, and `frontend/src/ui/guideWalkthrough/guideWalkthroughController.ts`
- [X] T003 [P] Create the targeted validation test scaffold in `tests/test_frontend_driver_page_guide.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the shared walkthrough contracts and lifecycle shell required by all user stories.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Add failing static tests for Driver.js dependency, module presence, step schema fields, and controller lifecycle symbols in `tests/test_frontend_driver_page_guide.py`
- [X] T005 Define `GuideWalkthroughStep`, source reference, target anchor, fallback, and session status types in `frontend/src/ui/guideWalkthrough/guideWalkthroughSteps.ts`
- [X] T006 Implement the Driver.js lifecycle controller skeleton with start, destroy, refresh, close cleanup, and no-op safe guards in `frontend/src/ui/guideWalkthrough/guideWalkthroughController.ts`
- [X] T007 Mount the walkthrough controller and import `driver.js/dist/driver.css` once in `frontend/src/shell/AppShell.tsx`
- [X] T008 [P] Add shared source-file constants for `docs/learningpyramid-user-manual.md` and exported manual Markdown access in `frontend/src/ui/guideWalkthrough/guideWalkthroughCopy.ts`

**Checkpoint**: The app can build a shell-level walkthrough controller and shared step contract, but no guide entry or product anchors are user-facing yet.

---

## Phase 3: User Story 1 - Start guided walkthrough from user guide (Priority: P1) MVP

**Goal**: A learner opens the user guide, sees system usage instructions plus a start-guidance action instead of the method explanation entry, and can start the first walkthrough step.

**Independent Test**: Open `/guide`, verify the method explanation document is no longer selectable, click the start-guidance action, confirm the first Driver.js popover appears, and close/restart it without reloading.

### Tests for User Story 1

- [X] T009 [US1] Add failing tests that `frontend/src/views/guide/GuidePage.tsx` removes the method document import, removes `slug: "method"`, and keeps the manual as the default document in `tests/test_frontend_driver_page_guide.py`
- [X] T010 [US1] Add failing tests that `frontend/src/views/guide/GuidePage.tsx` renders a start-guidance action wired to the walkthrough start API in `tests/test_frontend_driver_page_guide.py`
- [X] T011 [US1] Add failing tests for the first `create-subject` step source reference and initial Driver.js drive call in `tests/test_frontend_driver_page_guide.py`

### Implementation for User Story 1

- [X] T012 [US1] Remove the method guide raw import and method document definition from `frontend/src/views/guide/GuidePage.tsx`
- [X] T013 [US1] Render a `开始引导` action in the guide sidebar using existing `Button` styling in `frontend/src/views/guide/GuidePage.tsx`
- [X] T014 [US1] Wire the guide start action to the walkthrough start API while preserving the system manual as the active guide document in `frontend/src/views/guide/GuidePage.tsx`
- [X] T015 [US1] Implement the first `create-subject` walkthrough step and Driver.js `drive()` start behavior in `frontend/src/ui/guideWalkthrough/guideWalkthroughSteps.ts` and `frontend/src/ui/guideWalkthrough/guideWalkthroughController.ts`
- [X] T016 [P] [US1] Add `data-guide-tour="new-subject-button"` and `data-guide-tour="create-subject-submit"` anchors to the create-subject controls in `frontend/src/views/projects/ProjectsPage.tsx`
- [X] T017 [P] [US1] Add `data-guide-tour="subject-project-entry"` to the subject project entry action in `frontend/src/views/subjects/SubjectDashboardPage.tsx`

**Checkpoint**: User Story 1 is independently functional as an MVP from `/guide` through the first subject/project walkthrough entry.

---

## Phase 4: User Story 2 - Keep walkthrough copy aligned with system usage instructions (Priority: P2)

**Goal**: Maintainers can update `docs/learningpyramid-user-manual.md` and have walkthrough copy stay traceable to that manual instead of duplicated tour prose.

**Independent Test**: Change a controlled manual item, run the static guide walkthrough tests, and verify the corresponding step source reference resolves without adding separate popover body text.

### Tests for User Story 2

- [X] T018 [US2] Add failing tests that every walkthrough `sourceRef.heading` and `itemIndex` resolves in `docs/learningpyramid-user-manual.md` in `tests/test_frontend_driver_page_guide.py`
- [X] T019 [US2] Add failing tests that walkthrough steps do not contain independently authored popover body strings in `frontend/src/ui/guideWalkthrough/guideWalkthroughSteps.ts` via `tests/test_frontend_driver_page_guide.py`
- [X] T020 [US2] Add failing tests that all first-release step IDs from `specs/003-driver-page-guide/contracts/walkthrough-step-map.md` exist in `frontend/src/ui/guideWalkthrough/guideWalkthroughSteps.ts` in `tests/test_frontend_driver_page_guide.py`

### Implementation for User Story 2

- [X] T021 [US2] Implement manual heading, ordered-list item, paragraph, and summary extraction in `frontend/src/ui/guideWalkthrough/guideWalkthroughCopy.ts`
- [X] T022 [US2] Add all first-release source-referenced walkthrough steps from `contracts/walkthrough-step-map.md` to `frontend/src/ui/guideWalkthrough/guideWalkthroughSteps.ts`
- [X] T023 [US2] Resolve Driver.js popover titles and descriptions from manual source references in `frontend/src/ui/guideWalkthrough/guideWalkthroughController.ts`
- [X] T024 [US2] Add source-reference maintainer metadata exports for release review in `frontend/src/ui/guideWalkthrough/guideWalkthroughSteps.ts`

**Checkpoint**: User Story 2 is independently functional: the step map is complete and walkthrough copy is derived from the system usage instructions.

---

## Phase 5: User Story 3 - Handle unavailable tour targets gracefully (Priority: P3)

**Goal**: The walkthrough remains useful when targets are hidden, the user has no setup data, the route changes, or an old method-document guide link is opened.

**Independent Test**: Start the walkthrough in a fresh or empty state, visit `/guide?doc=method`, advance through steps whose targets are missing, and confirm the tour shows route hints or centered fallback guidance without trapping page interaction after close.

### Tests for User Story 3

- [X] T025 [US3] Add failing tests for legacy `?doc=method` fallback behavior in `frontend/src/views/guide/GuidePage.tsx` via `tests/test_frontend_driver_page_guide.py`
- [X] T026 [US3] Add failing tests that every step with a `targetAnchor` has either a matching `data-guide-tour` anchor or an explicit fallback mode in `tests/test_frontend_driver_page_guide.py`
- [X] T027 [US3] Add failing tests for controller missing-target fallback, route-hint, safe skip, and close cleanup symbols in `frontend/src/ui/guideWalkthrough/guideWalkthroughController.ts` via `tests/test_frontend_driver_page_guide.py`

### Implementation for User Story 3

- [X] T028 [US3] Resolve legacy guide query states such as `?doc=method` to the default manual state in `frontend/src/views/guide/GuidePage.tsx`
- [X] T029 [US3] Add `guideTourAnchor` support to nav item definitions and render `data-guide-tour` attributes from nav entries in `frontend/src/shell/navItems.ts` and `frontend/src/shell/MainNav.tsx`
- [X] T030 [US3] Add `project-settings-nav` and `workbench-nav` guide tour anchors to the project navigation entries in `frontend/src/shell/navItems.ts`
- [X] T031 [P] [US3] Add `data-guide-tour="authorize-directory-button"` and `data-guide-tour="import-directory-button"` anchors to the directory actions in `frontend/src/views/settings/ProjectSettingsPage.tsx`
- [X] T032 [P] [US3] Add `data-guide-tour="learning-object-tree"` to the object tree container in `frontend/src/views/workbench/components/LearningObjectTree.tsx`
- [X] T033 [P] [US3] Add `data-guide-tour="add-recall-point-button"` and `data-guide-tour="submit-learning-button"` anchors to recall composition controls in `frontend/src/views/workbench/components/ComposePane.tsx`
- [X] T034 [P] [US3] Add `data-guide-tour="review-pane"` to the review area in `frontend/src/views/workbench/components/ReviewPane.tsx`
- [X] T035 [US3] Implement target lookup, route hint handling, centered fallback steps, safe skip behavior, and close cleanup in `frontend/src/ui/guideWalkthrough/guideWalkthroughController.ts`

**Checkpoint**: User Story 3 is independently functional: unavailable targets and legacy guide links degrade safely.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and release-readiness checks across all stories.

- [X] T036 Run `python -m pytest tests/test_frontend_driver_page_guide.py` and fix any guide walkthrough contract failures in `tests/test_frontend_driver_page_guide.py`
- [X] T037 Run `pnpm -C frontend build` and fix any TypeScript/build failures in `frontend/src/ui/guideWalkthrough/guideWalkthroughController.ts` and `frontend/src/views/guide/GuidePage.tsx`
- [X] T038 Run `pnpm -C frontend lint` and fix any lint failures in `frontend/src/ui/guideWalkthrough/guideWalkthroughSteps.ts` and `frontend/src/shell/AppShell.tsx`

  Note: The full lint command was run and remains blocked by unrelated pre-existing lint errors outside the walkthrough/AppShell scope. Targeted ESLint for the walkthrough modules, AppShell, GuidePage, and navigation files passes.
- [X] T039 Manually review `/guide`, `/guide?doc=method`, and the walkthrough at desktop and narrow widths, then record follow-up notes in `specs/003-driver-page-guide/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational; recommended MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational and can run after US1 start wiring exists.
- **User Story 3 (Phase 5)**: Depends on Foundational and benefits from US1/US2 step wiring, but fallback work is separately testable.
- **Polish (Phase 6)**: Depends on the selected completed user stories.

### User Story Dependencies

- **US1**: No dependency on other user stories after Foundational.
- **US2**: Depends on the shared step contract and can validate source-copy alignment independently of fallback behavior.
- **US3**: Depends on the shared controller and step map; adds fallback behavior and remaining target anchors.

### Within Each User Story

- Tests are written before implementation tasks.
- Source-copy parsing must exist before generated popover text is wired into Driver.js.
- Target anchors should be added before static anchor coverage is expected to pass.
- Controller fallback behavior should be implemented after all planned fallback modes are represented in the step map.

## Parallel Opportunities

- T003 can run in parallel with T001 and T002.
- T006 and T008 can run in parallel after T005 because they touch different walkthrough modules.
- T016 and T017 can run in parallel because they touch separate view files.
- T018, T019, and T020 can be authored together before US2 implementation.
- T031, T032, T033, and T034 can run in parallel because they touch separate target view files.
- Final build, lint, and targeted Python tests should run after implementation converges.

## Parallel Example: User Story 3

```text
Task: "Add data-guide-tour=\"authorize-directory-button\" and data-guide-tour=\"import-directory-button\" anchors to the directory actions in frontend/src/views/settings/ProjectSettingsPage.tsx"
Task: "Add data-guide-tour=\"learning-object-tree\" to the object tree container in frontend/src/views/workbench/components/LearningObjectTree.tsx"
Task: "Add data-guide-tour=\"add-recall-point-button\" and data-guide-tour=\"submit-learning-button\" anchors to recall composition controls in frontend/src/views/workbench/components/ComposePane.tsx"
Task: "Add data-guide-tour=\"review-pane\" to the review area in frontend/src/views/workbench/components/ReviewPane.tsx"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 for User Story 1.
3. Run the targeted guide walkthrough tests for US1.
4. Demo `/guide` with the method document removed and the first walkthrough step starting from the guide button.

### Incremental Delivery

1. Deliver dependency, controller shell, and step contracts.
2. Add the user guide start action and first-step Driver.js tour.
3. Expand the step map so tour text is derived from the system usage instructions.
4. Add target anchors and missing-target fallbacks for the full first-use path.
5. Run polish validation and record any residual manual-review risks.

### Parallel Team Strategy

1. One person completes setup and the shared walkthrough controller.
2. One person wires the guide entry and subject/project anchors for US1.
3. One person implements manual source-copy resolution and step map coverage for US2.
4. One person adds route/target fallback anchors and behavior for US3.
5. Final validation runs after the selected story phases converge.

## Notes

- Keep the walkthrough presentational: it must not create subjects, authorize directories, import content, submit learning, or trigger network writes on behalf of the user.
- Do not delete `docs/plm-method-guide.md`; remove it only from the in-product guide navigation unless a later requirement explicitly asks to delete the file.
- Keep all walkthrough copy traceable to `docs/learningpyramid-user-manual.md`.
- Avoid targeting translated button text or Tailwind class selectors; use stable `data-guide-tour` anchors.
- Stop at each checkpoint if the user wants to review the increment before continuing.
