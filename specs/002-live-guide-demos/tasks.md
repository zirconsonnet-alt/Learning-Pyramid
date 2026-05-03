# Tasks: Live Guide Demos

**Input**: Design documents from `/specs/002-live-guide-demos/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included because the plan and project workflow require validation for guide parsing, registry coverage, privacy-safe fixtures, and frontend build behavior.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on another incomplete task.
- **[Story]**: Maps the task to a user story from `spec.md`.
- Every task includes exact file paths.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the feature files without changing runtime behavior yet.

- [X] T001 Create the guide demo file structure with placeholder exports in `frontend/src/views/guide/demos/GuideDemoFrame.tsx`, `frontend/src/views/guide/demos/guideSceneRegistry.tsx`, and `frontend/src/views/guide/demos/guideSceneFixtures.ts`
- [X] T002 Create the targeted validation test file and helper scaffolding in `tests/test_frontend_live_guide_demos.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add parser, registry, fallback, and rendering infrastructure required by all user stories.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Add failing parser contract tests for valid directives, invalid directives, caption bodies, and code-fence exclusion in `tests/test_frontend_live_guide_demos.py`
- [X] T004 Extend the guide Markdown block model and parser with a `guideDemo` block variant in `frontend/src/views/guide/GuidePage.tsx`
- [X] T005 Implement quoted attribute parsing and invalid-directive fallback data for `guide-demo` blocks in `frontend/src/views/guide/GuidePage.tsx`
- [X] T006 Implement the guide scene registry types, resolver, unknown-scene fallback, and unsupported-state fallback in `frontend/src/views/guide/demos/guideSceneRegistry.tsx`
- [X] T007 Implement the reusable contained demo shell, title, caption, and reader-friendly fallback UI in `frontend/src/views/guide/demos/GuideDemoFrame.tsx`
- [X] T008 Wire `MarkdownContent` to render `guideDemo` blocks through the registry and demo frame in `frontend/src/views/guide/GuidePage.tsx`
- [X] T009 Add deterministic shared fixture data constants with no real local paths or private content in `frontend/src/views/guide/demos/guideSceneFixtures.ts`

**Checkpoint**: The guide can parse demo blocks and render either a registered scene or a fallback without breaking existing Markdown content.

---

## Phase 3: User Story 1 - Learn core flows with live product scenes (Priority: P1) MVP

**Goal**: A new learner can read the in-product manual and see live controlled scenes for the most important onboarding and learning steps.

**Independent Test**: Open the guide manual and verify that the first-use flow includes matching live scenes for subject/project creation, project directory setup, and recall point entry while existing text content still renders.

### Tests for User Story 1

- [X] T010 [US1] Add failing tests that require at least three onboarding `guide-demo` blocks in `docs/learningpyramid-user-manual.md` and matching registry entries in `tests/test_frontend_live_guide_demos.py`

### Implementation for User Story 1

- [X] T011 [P] [US1] Implement the subject/project creation guide scene states and highlight targets in `frontend/src/views/guide/demos/SubjectProjectGuideDemo.tsx`
- [X] T012 [P] [US1] Implement the project directory binding guide scene states and highlight targets in `frontend/src/views/guide/demos/ProjectDirectoryGuideDemo.tsx`
- [X] T013 [P] [US1] Implement the workbench recall point guide scene states and highlight targets in `frontend/src/views/guide/demos/WorkbenchRecallGuideDemo.tsx`
- [X] T014 [US1] Register the first-release scene identifiers, states, highlights, labels, and descriptions in `frontend/src/views/guide/demos/guideSceneRegistry.tsx`
- [X] T015 [US1] Insert `guide-demo` blocks for subject/project creation, local directory binding, and recall point entry into `docs/learningpyramid-user-manual.md`
- [X] T016 [US1] Tune the demo frame spacing and responsive containment for desktop and narrow guide layouts in `frontend/src/views/guide/demos/GuideDemoFrame.tsx`

**Checkpoint**: User Story 1 is independently functional and can be demonstrated from the existing `/guide` manual.

---

## Phase 4: User Story 2 - Maintain guide scenes as the product evolves (Priority: P2)

**Goal**: A maintainer can add or update guide scenes safely through the registry and fixtures instead of replacing screenshots or touching unrelated guide sections.

**Independent Test**: Add or rename a controlled scene state in the registry and verify that manual references, fixture privacy checks, and fallback behavior make the maintenance outcome clear.

### Tests for User Story 2

- [X] T017 [US2] Add failing tests for manual-to-registry coverage, unsupported states, unsupported highlights, and privacy-safe fixture values in `tests/test_frontend_live_guide_demos.py`

### Implementation for User Story 2

- [X] T018 [US2] Add registry validation helpers for scene identifiers, supported states, supported highlights, and graceful highlight degradation in `frontend/src/views/guide/demos/guideSceneRegistry.tsx`
- [X] T019 [US2] Add maintainer-readable fallback details for unknown scene, unsupported state, and unsupported highlight cases in `frontend/src/views/guide/demos/GuideDemoFrame.tsx`
- [X] T020 [US2] Consolidate all first-release sample values into privacy-safe fixture objects in `frontend/src/views/guide/demos/guideSceneFixtures.ts`
- [X] T021 [US2] Add authoring notes for new guide scenes and fixture privacy rules to `specs/002-live-guide-demos/quickstart.md`

**Checkpoint**: Maintainers can update scenes through one registry and one fixture layer, and contract tests catch missing or unsafe references.

---

## Phase 5: User Story 3 - Review guide coverage before release (Priority: P3)

**Goal**: A release reviewer can verify which guide step each scene supports and whether the visible scene still matches the written instruction.

**Independent Test**: Review the guide and confirm every embedded scene exposes a reader-facing title or caption, has registry metadata, and can be traced back to a guide step.

### Tests for User Story 3

- [X] T022 [US3] Add failing tests for scene title/caption presence and registry metadata completeness in `tests/test_frontend_live_guide_demos.py`

### Implementation for User Story 3

- [X] T023 [US3] Render scene title, caption, and state label consistently for review in `frontend/src/views/guide/demos/GuideDemoFrame.tsx`
- [X] T024 [US3] Add complete labels, descriptions, and state descriptions for registered scenes in `frontend/src/views/guide/demos/guideSceneRegistry.tsx`
- [X] T025 [US3] Add reviewer-friendly captions to all first-release guide demo blocks in `docs/learningpyramid-user-manual.md`
- [X] T026 [US3] Document release-review steps for scene/text alignment in `specs/002-live-guide-demos/quickstart.md`

**Checkpoint**: Release reviewers can inspect each live guide scene and verify it still supports the adjacent written instructions.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup across all stories.

- [X] T027 Run `python -m pytest tests/test_frontend_live_guide_demos.py` and fix any guide contract failures in `tests/test_frontend_live_guide_demos.py`
- [X] T028 Run `pnpm -C frontend build` and fix any TypeScript or build failures in `frontend/src/views/guide/GuidePage.tsx` and `frontend/src/views/guide/demos/guideSceneRegistry.tsx`
- [ ] T029 Run `pnpm -C frontend lint` and fix any lint failures in `frontend/src/views/guide/GuidePage.tsx` and `frontend/src/views/guide/demos/GuideDemoFrame.tsx`
- [ ] T030 Manually review `/guide` at desktop and narrow widths and record any follow-up notes in `specs/002-live-guide-demos/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational; recommended MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational; can run after or alongside US1 once registry shape exists.
- **User Story 3 (Phase 5)**: Depends on Foundational; benefits from US1/US2 scene content but remains independently testable through metadata and captions.
- **Polish (Phase 6)**: Depends on the selected completed user stories.

### User Story Dependencies

- **US1**: No dependency on other user stories.
- **US2**: No dependency on US3; may reuse scenes delivered by US1.
- **US3**: No dependency on new product behavior; reviews and metadata can be added once scenes exist.

### Within Each User Story

- Tests are written before implementation tasks.
- Scene components can be built in parallel after the foundational registry contract exists.
- Registry updates happen after scene components exist.
- Manual content updates happen after scene identifiers and supported states are known.

## Parallel Opportunities

- T011, T012, and T013 can run in parallel because they create separate scene component files.
- US2 fixture cleanup in T020 can proceed in parallel with US2 fallback UI work in T019 after T017 is written.
- US3 metadata work in T024 can proceed in parallel with US3 frame rendering work in T023 after T022 is written.
- Final build, lint, and targeted Python tests should run after implementation converges, but failures can be fixed independently by file area.

## Parallel Example: User Story 1

```text
Task: "Implement the subject/project creation guide scene states and highlight targets in frontend/src/views/guide/demos/SubjectProjectGuideDemo.tsx"
Task: "Implement the project directory binding guide scene states and highlight targets in frontend/src/views/guide/demos/ProjectDirectoryGuideDemo.tsx"
Task: "Implement the workbench recall point guide scene states and highlight targets in frontend/src/views/guide/demos/WorkbenchRecallGuideDemo.tsx"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 for User Story 1.
3. Run the targeted guide demo tests and frontend build.
4. Demo `/guide` with three live onboarding scenes.

### Incremental Delivery

1. Deliver parser, registry, fallback, and fixtures.
2. Add the first three live scenes and manual directives.
3. Add maintainer validation and privacy checks.
4. Add reviewer metadata and release-review instructions.
5. Run polish validation and record any residual risks.

### Parallel Team Strategy

1. One person completes parser/registry foundation.
2. Three people can create the first scene components in parallel.
3. Another person can add static tests and manual directives after the scene identifiers stabilize.
4. Final validation runs after merge of the selected story phases.

## Notes

- Keep guide scenes presentational: no writes, imports, purchases, permission prompts, network requests, or real local file paths.
- Do not introduce Docusaurus, Nextra, Storybook, Ladle, MDX, or a new documentation build pipeline in this feature.
- Preserve existing guide rendering for headings, paragraphs, lists, rules, math, code, links, and navigation.
- Stop at each checkpoint if the user wants to review the increment before continuing.
