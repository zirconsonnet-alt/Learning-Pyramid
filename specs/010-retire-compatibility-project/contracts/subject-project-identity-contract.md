# Contract: Subject And Material Project Identity

## Scope

This contract defines how subject-root identity and material-project identity are represented after retiring the compatibility-project concept.

## Subject Contract

Each subject contract must include:

- `subjectId`
- `subjectProjectId`
- `title`
- `state`
- `createdAt`
- `deletedAt`

Rules:

- The subject contract must not include `compatibilityProjectId`.
- `subjectProjectId` identifies the subject-root anchor used for subject-level routes and settings.
- Consumers must treat `subjectProjectId` as a subject-root identity, not as a normal material project selection.

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
- Legacy default-material behavior where the material points at the subject-root anchor remains valid, but the contract still exposes that relationship through `projectId`.

## Subject Context Contract

Each subject context contract must include:

- `subject`
- `currentMaterial`
- `materials`
- `isSubjectRoot`
- `currentProjectId`
- `subjectProjectId`

Rules:

- Subject context must always allow consumers to answer two questions directly:
  1. What subject is this route operating under?
  2. Is the current scope the subject root or a material project?
- Consumers must not infer those answers from a compatibility-project field or from ambiguous identifier reuse alone.

## Backward Compatibility Contract

- Previously stored records that still carry `compatibilityProjectId` or `compatibility_project_id` must remain readable.
- Current product contracts must expose only `subjectProjectId` and `projectId`.
- Newly written records must persist the cleaned field names only.

## Behavioral Guarantees

- Subject dashboards continue to open from `subjectId` and resolve the subject-root anchor via `subjectProjectId`.
- Material workbench and settings flows continue to open from `projectId`.
- Subject deletion removes the subject root and all related material projects in the same scope as before.
- Material deletion removes only the targeted material project scope and keeps the remaining subject intact.
- Pomodoro project selection and workbench gating continue to exclude subject roots from normal project choices.
