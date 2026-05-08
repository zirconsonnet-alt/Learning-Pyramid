# Contract: Subject And Material Project Identity

## Scope

This contract defines the clean subject/project identity boundary after retiring the compatibility-project concept and the later subject-root project leak.

## Subject Contract

Each subject contract must include:

- `subjectId`
- `title`
- `state`
- `createdAt`
- `deletedAt`

Rules:

- The subject contract must not include `compatibilityProjectId`.
- The subject contract must not include `subjectProjectId`.
- Consumers must treat `subjectId` as a subject identity only. It must not be used as a project route or workbench target.

## Study Material Contract

Each study material contract must include:

- `subjectId`
- `materialId`
- `materialType`
- `title`
- `createdAt`
- `projectId`

Rules:

- The study material contract must not include `compatibilityProjectId`.
- `projectId` identifies the workbench-bearing project associated with the material.
- `projectId` must not equal the owning `subjectId`. Historical root-backed material rows are migrated to independent material projects before normal product flows expose them.

## Subject Context Contract

Each subject context contract must include:

- `subject`
- `currentMaterial`
- `materials`
- `currentProjectId`

Rules:

- Subject context must always allow consumers to answer two questions directly:
  1. What subject is this route operating under?
  2. Which material project is currently active?
- Subject context is available only for material project routes. Subject routes use `subjectId` directly.

## Historical Data Migration Contract

- Previously stored material records that point at a subject root are migrated to independent material projects.
- Persisted study-material payloads must use `projectId`; retired `compatibilityProjectId` / `compatibility_project_id` keys are not fallback inputs.
- Newly written records must persist only the current material-project identity.

## Behavioral Guarantees

- Subject dashboards and subject settings open from `subjectId`.
- Material workbench and settings flows continue to open from `projectId`.
- Subject deletion removes the subject root and all related material projects in the same scope as before.
- Material deletion removes only the targeted material project scope and keeps the remaining subject intact.
- Pomodoro project selection, workbench gating, and AI context use only material project IDs. Subject roots are not normal project choices.
