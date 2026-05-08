# Implementation Plan: Retire Compatibility Project

**Branch**: `010-retire-compatibility-project` | **Date**: 2026-05-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/010-retire-compatibility-project/spec.md`

## Summary

Retire `compatibilityProjectId` / `compatibility_project_id` and the later `subjectProjectId` stopgap as product-facing concepts. A subject response exposes only `subjectId`; each study material exposes its own material `projectId`. Subject ids are rejected on project routes, historical root-backed materials are migrated into independent material projects, and retired compatibility payload fields are not parsed.

## Technical Context

**Language/Version**: Python 3.12 backend; TypeScript/React 18 frontend  
**Primary Dependencies**: FastAPI, Pydantic, existing backend domain services in `backend/system/api.py`, existing JSON/SQLite/Postgres persistence abstractions, React Router, TanStack Query, Zod, Zustand, ESLint, Vite  
**Storage**: Existing JSON payload persistence plus SQLite/Postgres-backed project stores; no new database tables are planned, but persisted study-material payloads must use `projectId` and historical root-backed materials are migrated into independent child projects
**Testing**: `pytest` for API and regression tests, focused static/frontend tests, `npx eslint`, `npm run build`  
**Target Platform**: LearningPyramid web application across local, self-hosted, and hosted runtime modes  
**Project Type**: Web application with backend API/domain logic and browser frontend  
**Performance Goals**: Subject dashboard, subject context, and Pomodoro gating continue to resolve in the same interactive page-load envelope as before the cleanup; migration should be idempotent and happen during normal subject/material listing
**Constraints**: Do not delete learning data as part of this feature; subject roots remain subject anchors but are not project/workbench entries; do not preserve retired compatibility field parsing; keep changes scoped to identity boundaries and dependent flows; avoid unrelated refactors while working in a dirty git tree
**Scale/Scope**: Subject list, subject creation, subject materials, subject context, project settings, AppShell route resolution, Pomodoro filtering/gating, persistence payload encoding/decoding, and related regression tests/docs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The repository constitution file is still an unfilled template, so no enforceable project-specific gates can be derived from it. This plan therefore uses the active `AGENTS.md` rules as the effective gate:

- Keep the implementation to the minimum necessary change set for the subject/project identity cleanup.
- Do not delete data or perform unrelated cleanup.
- Update docs and tests for every contract or behavior change.
- Preserve existing dirty worktree changes unless they directly intersect the feature.
- Do not claim verification that has not been run.

Pre-design gate result: PASS. The feature is a bounded identity cleanup with explicit migration requirements and no unavoidable constitution conflict.

## Project Structure

### Documentation (this feature)

```text
specs/010-retire-compatibility-project/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── subject-project-identity-contract.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── models/
│   └── study_material.py                  # rename material project field in the domain model
└── system/
    ├── api.py                            # subject/material creation, context resolution, delete flows
    └── persistence_json.py               # current projectId payload read/write behavior

adapter/
├── mappers.py                            # outbound DTO field names
└── routers/
    └── projects.py                       # subject/material endpoints and auth cleanup paths

frontend/
└── src/
    ├── shell/
    │   └── AppShell.tsx                  # route-scoped subject/project resolution
    ├── ui/
    │   ├── api/
    │   │   └── subjects.ts               # Zod subject/material contract
    │   └── queries/
    │       └── subjects.ts               # query invalidation remains but consumes updated DTOs
    └── views/
        ├── projects/ProjectsPage.tsx     # subject list and subject entry behavior
        ├── subjects/SubjectDashboardPage.tsx
        ├── settings/ProjectSettingsPage.tsx
        └── pomodoro/
            ├── PomodoroPage.tsx
            └── PomodoroWorkbenchGate.tsx

tests/
├── test_subjects_api.py                  # subject/material contract regression
├── test_frontend_llm_settings_location.py
├── test_frontend_pomodoro_multi_plan.py
├── test_frontend_subject_project_copy.py
└── test_frontend_project_settings_layout.py

docs/
├── learningpyramid-user-manual.md
└── how-to-create-subject-project.md
```

**Structure Decision**: Keep the refactor inside the existing subject/material vertical slice instead of introducing a new subject persistence model. The backend still uses the current subject-root anchor for subject ownership and settings, but that root is no longer exposed or accepted as a workbench project. Materials carry the project ids that workbench, Pomodoro, AI, and project settings consume.

## Phase 0: Research

Research output is captured in [research.md](./research.md). The planning unknowns resolved there are:

- Whether the feature should delete the underlying subject-root anchor or stop exposing it as a project.
- How existing root-backed materials should be migrated without preserving compatibility fields.
- Whether this refactor requires SQL schema changes.
- How to keep Pomodoro and subject/project deletion semantics stable while renaming the contracts.

## Phase 1: Design & Contracts

Design output is captured in:

- [data-model.md](./data-model.md)
- [contracts/subject-project-identity-contract.md](./contracts/subject-project-identity-contract.md)
- [quickstart.md](./quickstart.md)

`AGENTS.md` is also updated so its active Spec Kit pointer references this plan.

## Post-Design Constitution Check

Post-design gate result: PASS.

- No new dependency or deployment requirement is introduced.
- No mandatory SQL schema migration is planned.
- The design keeps data deletion out of scope and limits the work to identity boundaries, migration, and dependent flows.
- The verification plan covers migration safety and user-facing subject/project flows.

## Phase 2: Task Planning Preview

Task generation should prioritize:

1. Contract tests that lock subject DTOs to `subjectId` only and material DTOs to `projectId`.
2. Backend domain and persistence updates so study materials require `projectId`, root-backed materials migrate to child projects, and subject ids are rejected on project routes.
3. Adapter mapper/router updates for subject-only and material-project-only contracts plus auth cleanup behavior.
4. Frontend subject/material schema updates and route-resolution changes in `AppShell`, `ProjectsPage`, and `SubjectDashboardPage`.
5. Settings and Pomodoro flow updates that use the concrete project catalog instead of subject-root filters.
6. Static regression tests and docs cleanup to prevent the retired concept from reappearing.
7. Final verification across pytest, focused frontend/static tests, eslint, and production build.

## Complexity Tracking

No constitution violations or complexity exceptions are required.
