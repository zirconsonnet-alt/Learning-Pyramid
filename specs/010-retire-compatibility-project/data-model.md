# Data Model: Retire Compatibility Project

## Subject

Represents the top-level learning domain visible in the product.

Fields:

- `subjectId`: Stable subject identity.
- `title`: User-visible subject name.
- `state`: Subject lifecycle state.
- `createdAt`: Subject creation timestamp.
- `deletedAt`: Optional deletion timestamp.

Validation rules:

- `subjectId` must resolve for active subjects.
- A subject ID is not a project ID and must not be used for `/projects/{projectId}` API calls or `/p/{projectId}` routes.
- Current outward product contracts must not expose `compatibilityProjectId` or `subjectProjectId` for a subject.

## Study Material

Represents a material entry under a subject.

Fields:

- `subjectId`: Owning subject identity.
- `materialId`: Stable material identity within the subject.
- `materialType`: Course, book, or loose-points material category.
- `title`: User-visible material title.
- `createdAt`: Material creation timestamp.
- `projectId`: Optional material workbench project identity.

Validation rules:

- Every material belongs to exactly one subject.
- `projectId` must point to a material project. Historical records where `projectId` equals the subject-root anchor are migrated to an independent material project before normal product flows expose them.
- Current outward product contracts must not expose `compatibilityProjectId` for a material.

## Material Project

Represents the project/workbench scope associated with a study material.

Fields:

- `projectId`: Stable project identity.
- `subjectId`: Owning subject identity inferred through subject context.
- `materialId`: Associated study material identity.
- `projectScope`: Material-project scope rather than subject-root scope.

Validation rules:

- A material project must resolve back to one subject and one current material.
- Material-project flows such as Pomodoro binding, project settings, and workbench routing must treat this as a project-level target.

## Subject Context

Represents the resolved subject-aware navigation state for a current page.

Fields:

- `subject`: Current subject.
- `currentMaterial`: Material active for the current route/project scope.
- `materials`: All materials visible under the subject.
- `currentProjectId`: Current resolved route/project identity.

Validation rules:

- Subject context exists for material-project scope only.
- When the current route is a material project, `currentMaterial.projectId` must resolve the active project target.
- Subject pages use `subjectId` directly and do not resolve through a subject-root project.

## Historical Root-Backed Material

Fields:

- `subjectId`: Owning subject identity.
- `materialId`: Historical material identity.
- `projectId`: Historical value that equals `subjectId` before migration.

Validation rules:

- Historical root-backed materials are migrated to current subject/material/project identities without preserving old public entry points.
- Newly written records must not persist the retired field names.
- If a material record is missing `projectId`, the system must fail safely rather than silently inventing a new relationship.
