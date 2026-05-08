# Data Model: Retire Compatibility Project

## Subject

Represents the top-level learning domain visible in the product.

Fields:

- `subjectId`: Stable subject identity.
- `subjectProjectId`: Subject-root project anchor used for subject-level routes, settings, and statistics.
- `title`: User-visible subject name.
- `state`: Subject lifecycle state.
- `createdAt`: Subject creation timestamp.
- `deletedAt`: Optional deletion timestamp.

Validation rules:

- `subjectId` and `subjectProjectId` must both resolve for active subjects.
- The subject-root anchor remains a subject-level concept, not a normal material project choice.
- Current outward product contracts must not expose `compatibilityProjectId` for a subject.

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
- `isSubjectRoot`: Whether the current route is operating at the subject-root scope.
- `currentProjectId`: Current resolved route/project identity.
- `subjectProjectId`: Current subject-root anchor identity.

Validation rules:

- Subject context must always distinguish subject-root scope from material-project scope explicitly.
- When the current route is a material project, `currentMaterial.projectId` must resolve the active project target.
- When the current route is the subject root, the context may identify the first available material for navigation, but that material must still be an independent material project.

## Legacy Subject/Material Record

Represents persisted pre-refactor data that still uses the retired field names.

Fields:

- `legacySubjectProjectField`: Historical subject-level compatibility field name if present.
- `legacyMaterialProjectField`: Historical material-level compatibility field name if present.
- `currentResolvedProjectId`: Cleaned project identity obtained during read.

Validation rules:

- Legacy records must remain readable without user intervention.
- Newly written records must not persist the retired field names.
- If a legacy record is missing or has an inconsistent retired field, the system must fail safely rather than silently inventing a new relationship.
