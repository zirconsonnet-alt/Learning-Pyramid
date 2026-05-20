# Tasks: Mobile Navigation Shell

**Input**: Design documents from `specs/017-mobile-navigation-shell/`  
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/mobile-navigation-contract.md](./contracts/mobile-navigation-contract.md), [quickstart.md](./quickstart.md)

**Tests**: Included. The feature specification defines independently testable user journeys, and the implementation should follow test-first execution for each story.

**Organization**: Tasks are grouped by user story so each slice can be implemented and verified independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and does not depend on incomplete tasks.
- **[Story]**: User story label for story phases only.
- Every task includes an exact file path.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare implementation tracking and the mobile navigation work area.

- [X] T001 Replace the previous rolling task note with this feature scope in `docs/current-change.md`
- [X] T002 Create the navigation work area by adding `mobile/src/navigation/mobileNavigation.ts`
- [X] T003 [P] Create the first shell test file `mobile/__tests__/mobile-navigation-shell.test.tsx`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared navigation domain helpers and reusable screens that every story depends on.

**CRITICAL**: No user story implementation should begin until this phase is complete.

- [X] T004 Add failing unit tests for context status, destination requirements, settings visibility, and guard decisions in `mobile/__tests__/mobile-navigation-shell.test.tsx`
- [X] T005 Implement `LearningContext`, `NavigationDestination`, bottom destination constants, settings visibility helpers, and guard helpers in `mobile/src/navigation/mobileNavigation.ts`
- [X] T006 Add a concise reusable project destination empty/unavailable screen in `mobile/src/screens/ProjectDestinationPlaceholderScreen.tsx`
- [X] T007 Export shared navigation helpers and screen types from `mobile/src/navigation/mobileNavigation.ts`

**Checkpoint**: Navigation model is test-covered and ready for story implementation.

---

## Phase 3: User Story 1 - Start Without Learning Context (Priority: P1) MVP

**Goal**: Signed-in users without a complete learning context stay in subject/project setup and do not see project shell tabs before a valid project exists.

**Independent Test**: Sign in with no subjects, create/select a subject, then create/select a project; verify project shell navigation is absent until the project opens.

### Tests for User Story 1

> Write these tests first and confirm they fail before implementation.

- [X] T008 [US1] Add no-subject signed-in setup flow assertions in `mobile/__tests__/mobile-navigation-shell.test.tsx`
- [X] T009 [P] [US1] Add subject-only project center assertions in `mobile/__tests__/learning-navigation.test.tsx`
- [X] T010 [P] [US1] Add route-level no-project-shell assertions in `mobile/__tests__/project-route-workbench.test.tsx`

### Implementation for User Story 1

- [X] T011 [US1] Update empty and setup copy/actions for users with no subjects in `mobile/src/screens/SubjectsScreen.tsx`
- [X] T012 [US1] Update project center empty and creation states for subject-only users in `mobile/src/screens/SubjectMaterialsScreen.tsx`
- [X] T013 [US1] Preserve subject setup routing and prevent project shell rendering before project selection in `mobile/src/app/index.tsx`
- [X] T014 [US1] Preserve subject-only routing and route only scoped projects into the project route in `mobile/src/app/subject/[subjectId].tsx`

**Checkpoint**: User Story 1 is independently functional and testable as the MVP.

---

## Phase 4: User Story 2 - Navigate Inside a Project Context (Priority: P2)

**Goal**: Users inside a valid subject/project context see a project shell with current context and exactly five project destinations: Learning, AI, Review, Structure, Mine.

**Independent Test**: Open a project, confirm the top context identifies the current subject/project, switch all five destinations, and verify the scoped project identifiers remain stable.

### Tests for User Story 2

> Write these tests first and confirm they fail before implementation.

- [X] T015 [US2] Add project shell top-context and five-destination assertions in `mobile/__tests__/mobile-navigation-shell.test.tsx`
- [X] T016 [P] [US2] Add existing workbench-as-Learning assertions in `mobile/__tests__/project-route-workbench.test.tsx`
- [X] T017 [P] [US2] Add placeholder destination rendering assertions for AI, Review, and Structure in `mobile/__tests__/mobile-workbench-screen.test.tsx`

### Implementation for User Story 2

- [X] T018 [US2] Implement the project shell container and bottom task navigation in `mobile/src/navigation/ProjectShell.tsx`
- [X] T019 [US2] Wrap the existing project workbench in the project shell in `mobile/src/app/project/[subjectId]/[scopedProjectId].tsx`
- [X] T020 [US2] Render the Learning destination with the existing `MobileWorkbenchScreen` in `mobile/src/app/project/[subjectId]/[scopedProjectId].tsx`
- [X] T021 [US2] Render explicit project-scoped AI, Review, and Structure unavailable/empty destinations in `mobile/src/app/project/[subjectId]/[scopedProjectId].tsx`
- [X] T022 [US2] Keep current project identifiers stable across destination changes in `mobile/src/navigation/ProjectShell.tsx`

**Checkpoint**: User Story 2 is independently functional and can be demoed inside any valid project.

---

## Phase 5: User Story 3 - Manage Scoped Settings from the Right Context (Priority: P3)

**Goal**: Subject settings and project settings appear only in the correct object context and never as primary Mine entries.

**Independent Test**: Open no-subject, subject-only, and project states; verify subject settings and project settings visibility rules and routes.

### Tests for User Story 3

> Write these tests first and confirm they fail before implementation.

- [X] T023 [US3] Add context menu visibility tests for no-subject, subject-only, and project states in `mobile/__tests__/mobile-navigation-shell.test.tsx`
- [X] T024 [P] [US3] Add subject settings route assertions in `mobile/__tests__/learning-navigation.test.tsx`
- [X] T025 [P] [US3] Add project settings route assertions in `mobile/__tests__/root-layout.test.tsx`

### Implementation for User Story 3

- [X] T026 [US3] Implement scoped context controls and menu item derivation in `mobile/src/navigation/ContextMenu.tsx`
- [X] T027 [US3] Attach project-state context controls to the project shell in `mobile/src/navigation/ProjectShell.tsx`
- [X] T028 [US3] Attach no-subject and subject-only context controls to `mobile/src/screens/SubjectsScreen.tsx`
- [X] T029 [US3] Attach subject-only context controls to `mobile/src/screens/SubjectMaterialsScreen.tsx`
- [X] T030 [US3] Create a project settings placeholder screen in `mobile/src/screens/ProjectSettingsScreen.tsx`
- [X] T031 [US3] Add the mobile project settings route in `mobile/src/app/project-settings/[subjectId]/[scopedProjectId].tsx`
- [X] T032 [US3] Register the project settings stack entry in `mobile/src/app/_layout.tsx`

**Checkpoint**: User Story 3 is independently functional across all context states.

---

## Phase 6: User Story 4 - Reach Account and System Routes Without Polluting Learning Navigation (Priority: P4)

**Goal**: Users can reach account and system destinations from Mine while subject/project settings remain owned by context controls.

**Independent Test**: Open Mine with and without project context; verify account/system entries exist, subject/project settings are absent as primary entries, and global settings/sign out remain available.

### Tests for User Story 4

> Write these tests first and confirm they fail before implementation.

- [X] T033 [US4] Add Mine grouping and scoped-settings absence tests in `mobile/__tests__/mine-screen.test.tsx`
- [X] T034 [P] [US4] Add Mine destination assertions from the project shell in `mobile/__tests__/mobile-navigation-shell.test.tsx`
- [X] T035 [P] [US4] Add Mine route registration assertions in `mobile/__tests__/root-layout.test.tsx`

### Implementation for User Story 4

- [X] T036 [US4] Implement account/system grouping in `mobile/src/screens/MineScreen.tsx`
- [X] T037 [US4] Add the global Mine route in `mobile/src/app/mine.tsx`
- [X] T038 [US4] Register the Mine stack entry in `mobile/src/app/_layout.tsx`
- [X] T039 [US4] Add Mine entry points from setup states in `mobile/src/screens/SubjectsScreen.tsx`
- [X] T040 [US4] Add Mine entry points from subject-only project center in `mobile/src/screens/SubjectMaterialsScreen.tsx`
- [X] T041 [US4] Render Mine as the fifth project shell destination in `mobile/src/navigation/ProjectShell.tsx`

**Checkpoint**: User Story 4 is independently functional without changing scoped settings ownership.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, and final cleanup across all implemented stories.

- [X] T042 [P] Update implemented mobile navigation behavior and unsupported destination boundaries in `docs/mobile-client.md`
- [X] T043 Update changed files, behavior semantics, validation results, risks, and pollution check in `docs/current-change.md`
- [X] T044 Run `pnpm --dir mobile test` and record the result in `docs/current-change.md`
- [X] T045 Run `pnpm --dir mobile typecheck` and record the result in `docs/current-change.md`
- [X] T046 Run the smoke paths from `specs/017-mobile-navigation-shell/quickstart.md` when a device or emulator is available and record the result in `docs/current-change.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational and is the MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational and can be implemented after US1 or in parallel once setup flow behavior is protected by tests.
- **User Story 3 (Phase 5)**: Depends on Foundational and benefits from US2 shell structure.
- **User Story 4 (Phase 6)**: Depends on Foundational and can be implemented after the shell shape exists.
- **Polish (Phase 7)**: Depends on all selected user stories.

### User Story Dependencies

- **US1 (P1)**: No dependency on other stories after Foundational.
- **US2 (P2)**: Needs Foundational helpers; independent from US3/US4.
- **US3 (P3)**: Uses Foundational helpers and ProjectShell integration; no backend dependency.
- **US4 (P4)**: Uses ProjectShell integration and existing auth/global settings routes; no backend dependency.

### Within Each User Story

- Tests first; confirm failure before implementation.
- Navigation model/helper changes before UI integration.
- UI shell or screen implementation before route registration.
- Route registration before final story verification.
- Story checkpoint before moving to the next priority unless intentionally parallelizing.

### Parallel Opportunities

- T003 can run in parallel with T002.
- T009 and T010 can run in parallel after T008 because they touch different test files.
- T016 and T017 can run in parallel after T015 because they touch different test files.
- T024 and T025 can run in parallel after T023 because they touch different test files.
- T034 and T035 can run in parallel after T033 because they touch different test files.
- T042 can run in parallel with validation commands once behavior is implemented; T043 must be finalized after validation results are known.

---

## Parallel Example: User Story 2

```text
Task: "T016 [P] [US2] Add existing workbench-as-Learning assertions in mobile/__tests__/project-route-workbench.test.tsx"
Task: "T017 [P] [US2] Add placeholder destination rendering assertions for AI, Review, and Structure in mobile/__tests__/mobile-workbench-screen.test.tsx"
```

After those tests exist, implementation can continue through `ProjectShell.tsx` and the project route integration.

## Parallel Example: User Story 3

```text
Task: "T024 [P] [US3] Add subject settings route assertions in mobile/__tests__/learning-navigation.test.tsx"
Task: "T025 [P] [US3] Add project settings route assertions in mobile/__tests__/root-layout.test.tsx"
```

Both tests are independent of the context menu implementation file and can be prepared alongside the primary context-menu test.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 only.
3. Validate that signed-in users without a project remain in setup states and do not see project shell tabs.
4. Stop and review before adding the project shell.

### Incremental Delivery

1. US1: Protect no-context setup behavior.
2. US2: Add project shell and five project destinations.
3. US3: Add scoped settings ownership and context controls.
4. US4: Add Mine account/system grouping.
5. Polish: Update docs and run verification.

### Parallel Team Strategy

Once Phase 2 is done:

- Developer A can implement US1 setup behavior.
- Developer B can implement US2 shell and project destinations.
- Developer C can implement US3/US4 screens and tests, avoiding `ProjectShell.tsx` conflicts until shell integration is ready.

---

## Notes

- Keep every project-scoped route on `{subjectId, scopedProjectId}`.
- Do not introduce persisted global current project state.
- Do not add backend endpoints, database fields, deployment changes, or mobile-only auth protocol.
- Do not reuse React DOM components from `frontend/`.
- Do not move subject settings or project settings into Mine as primary entries.
- If a task requires fallback, shim, broad route migration, or changed backend semantics, stop and ask for confirmation.
