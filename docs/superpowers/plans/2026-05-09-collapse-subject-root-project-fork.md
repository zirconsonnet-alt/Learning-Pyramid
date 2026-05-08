# Collapse Subject Root Project Fork Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Keep the checklist updated as each item lands.

**Goal:** Eliminate the historical fork where a subject-root project ID can be used as a learning-material/workbench project ID. After this work, subject IDs are exposed only as subject IDs; user-facing study, workbench, Pomodoro, guide, and AI-question flows bind only to concrete material/workbench projects.

**Architecture:** Keep two explicit identities:

- `subjectId`: subject identity for subject routes, subject settings, ownership, and subject-level metadata.
- `materialProjectId` / `workbenchProjectId`: concrete learning project used by workbench, Pomodoro, AI context capture, guide walkthroughs, and project-bound history.

Legacy rows where a material points at the subject root must be migrated to child material projects. Unknown or subject-root Pomodoro bindings must be cleared; never silently bind to the subject root.

**Tech Stack:** FastAPI backend, Python tests, React/TypeScript frontend, Vitest/static pytest frontend guards, current deployment scripts.

## Current Evidence

- `frontend/src/views/pomodoro/PomodoroPage.tsx`, `frontend/src/shell/AppShell.tsx`, and `frontend/src/views/pomodoro/PomodoroWorkbenchGate.tsx` previously needed defensive filtering to stop subject roots from being treated as accessible workbench projects. The clean implementation removes the need for frontend subject-root filtering by keeping roots out of the project catalog.
- Frontend static tests now assert quick Pomodoro starts from `selectedWorkbenchProjectId` and that subject-root filters / `subjectProjectId` consumers are absent.
- `specs/010-retire-compatibility-project/contracts/subject-project-identity-contract.md` now requires every exposed study material to have a concrete child `projectId`.
- Backend tests in `tests/test_subjects_api.py` prove the desired behavior: new subject materials do not use `legacy_main`, do not reuse the subject root project ID, and hosted historical root-backed materials migrate to child projects.

## Implementation Tasks

- [x] 1. Update stale contract and regression tests to define the new invariant.

  Files:

  - `specs/010-retire-compatibility-project/contracts/subject-project-identity-contract.md`
  - `specs/010-retire-compatibility-project/data-model.md`
  - `tests/test_frontend_pomodoro_multi_plan.py`

  Required changes:

  - Replace compatibility text that allows material `projectId === subjectId` with the rule: every exposed study material must have a concrete child `projectId`.
  - Update the Pomodoro static tests so quick Pomodoro binds through `selectedWorkbenchProjectId`, not raw `selectedProjectId`.
  - Update subject-material selection tests so frontend code no longer references `subjectProjectId` or subject-root filters.
  - Assert that the project catalog itself is clean and Pomodoro no longer needs a subject-root exclusion set.

  Verification:

  ```powershell
  python -m pytest tests/test_frontend_pomodoro_multi_plan.py -q
  ```

- [x] 2. Strengthen backend identity invariants.

  Files:

  - `backend/system/api.py`
  - `tests/test_subjects_api.py`

  Required changes:

  - Ensure every subject-material read path calls the independence/migration helper before returning materials.
  - Remove or quarantine synthetic `legacy_main` fallback output from public subject-material responses.
  - Keep subject roots out of `/api/projects`.
  - Reject `/api/projects/{subjectId}/...` access when the ID is a subject ID.
  - Add/keep tests that prove:
    - newly created subjects expose only child material project IDs;
    - legacy root-backed material rows are migrated to child project IDs on read;
    - deleting the first child material does not delete the subject root;
    - hosted users receive access to migrated child project IDs;
    - no public subject-material response contains `projectId == subjectProjectId`.

  Verification:

  ```powershell
  python -m pytest tests/test_subjects_api.py -q
  ```

- [x] 3. Separate frontend subject selection from workbench project selection.

  Files:

  - `frontend/src/ui/store/appStore.ts`
  - `frontend/src/views/projects/ProjectsPage.tsx`
  - `frontend/src/views/subjects/SubjectDashboardPage.tsx`
  - `frontend/src/shell/AppShell.tsx`
  - `frontend/src/guideWalkthrough/guideWalkthroughController.ts`
  - `frontend/src/guideWalkthrough/virtualStudyReviewProject.ts`
  - existing Pomodoro files touched by the prior hotfix

  Required changes:

  - Add an explicit workbench-project state path, `selectedWorkbenchProjectId`, and stop reading legacy `selectedProjectId`.
  - Make subject cards and subject-dashboard navigation set only subject selection, not workbench project selection.
  - Make material cards and workbench entry set only concrete material/workbench project IDs.
  - Make workbench, Pomodoro, AI popup context, and guide flows read from the concrete workbench-project state only.
  - Move subject settings to `/subjects/:subjectId/settings`; project settings remain `/p/:projectId/settings`.

  Verification:

  ```powershell
  python -m pytest tests/test_frontend_pomodoro_project_binding.py tests/test_frontend_pomodoro_multi_plan.py tests/test_frontend_driver_page_guide.py -q
  npx eslint src/shell/AppShell.tsx src/views/pomodoro/PomodoroPage.tsx src/views/pomodoro/PomodoroWorkbenchGate.tsx src/views/projects/ProjectsPage.tsx src/views/subjects/SubjectDashboardPage.tsx
  ```

- [x] 4. Migrate historical root-backed data automatically and document the new invariant.

  Files:

  - `backend/system/api.py`
  - `backend/system/persistence_json.py`
  - `docs/how-to-use-pomodoro.md`
  - `docs/learningpyramid-user-manual.md`

  Required changes:

  - Root-backed materials are migrated to independent material projects during normal subject/material access.
  - Subject roots are filtered out of `/api/projects` and rejected on `/api/projects/{projectId}`.
  - Hosted child project access is granted through the owning subject.
  - Study material payload decoding requires current `projectId`; retired compatibility keys are not accepted.
  - Documentation states that workbenches and Pomodoro bind only to concrete material projects.

- [ ] 5. Full verification, commit, push, and deploy.

  Required commands:

  ```powershell
  python -m pytest tests/test_subjects_api.py tests/test_frontend_pomodoro_project_binding.py tests/test_frontend_pomodoro_multi_plan.py tests/test_frontend_driver_page_guide.py -q
  npm run build
  ```

  Deployment:

  - Commit the invariant, frontend separation, docs, and migration behavior together or in clearly ordered commits.
  - Push the branch.
  - Deploy only after the build and targeted tests pass.
  - After deployment, smoke-check:
    - account 312 can open a newly created material project;
    - `/pomodoro` no longer routes to `/p/proj_000046/workbench` or any unknown/subject-root project;
    - the workbench AI popup still receives the concrete project context.

## Risks

- Changing frontend state keys strands old localStorage values by design; old ambiguous keys are ignored.
- Server data may contain unknown project IDs from old clients. Unknown IDs should be treated as invalid, not guessed.
- Excluding subject roots from project lists affects consumers that treated subjects as projects. This is intentional for the clean identity boundary.
