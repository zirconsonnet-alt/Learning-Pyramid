# Tasks: Retire Compatibility Project

## Contract And Regression Tests

- [x] Assert subject create/list responses expose `subjectId` only and omit `subjectProjectId` / `compatibilityProjectId`.
- [x] Assert study material responses expose `projectId` and omit compatibility fields.
- [x] Assert subject ids are rejected on project APIs with `PRECONDITION`.
- [x] Assert historical root-backed materials migrate to independent material projects during normal subject/material access.
- [x] Assert study material decoding requires current `projectId` and does not fall back to retired compatibility fields.
- [x] Add frontend static guards for removed subject-root project fields, stale selected-project state, and Pomodoro subject-root filters.

## Backend

- [x] Remove `subjectProjectId` / `isSubjectRoot` from outbound DTOs.
- [x] Return only `subjectId` from subject creation.
- [x] Filter subject roots out of `/api/projects`.
- [x] Reject subject ids on `/api/projects/{projectId}` routes.
- [x] Migrate root-backed subject materials into independent child projects.
- [x] Grant hosted material-project access through the owning subject relationship.
- [x] Require `projectId` when decoding study material payloads.

## Frontend

- [x] Split app store state into `selectedSubjectId` and `selectedWorkbenchProjectId`.
- [x] Remove frontend schemas and consumers for `subjectProjectId`, `isSubjectRoot`, and compatibility fields.
- [x] Route subject settings through `/subjects/:subjectId/settings`.
- [x] Route project settings through `/p/:projectId/settings`.
- [x] Use concrete material project ids for workbench, settings, AI context, and Pomodoro binding.
- [x] Aggregate subject-card activity from material projects instead of querying audit logs with a subject id.

## Documentation And Validation

- [x] Update user-facing Pomodoro and manual documentation to describe subject ids and concrete project ids cleanly.
- [x] Update current feature contracts/data model/research/quickstart to remove compatibility-read language.
- [x] Run focused backend/frontend regression tests.
- [x] Run targeted ESLint.
- [x] Run frontend production build.
