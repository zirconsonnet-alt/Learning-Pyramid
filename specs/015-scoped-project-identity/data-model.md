# Data Model: Scoped Project Identity

## Subject

Represents a learning subject such as "高等数学".

Fields:
- `subjectId`: Stable subject identity.
- `title`: Subject title.
- `state`: Active or deleted.
- `projectSequence`: Next or current subject-scoped material sequence.

Relationships:
- Owns zero or more `SubjectMaterialRelationship` records.

Validation:
- A subject with zero materials is still a valid subject.
- A deleted subject must not resolve active material workspaces.

## Subject-Scoped Material Project Identity

Represents the material project identifier meaningful only inside one subject.

Fields:
- `subjectId`: Owning subject identity.
- `scopedProjectId`: Material workspace identity scoped to the subject.

Relationships:
- Resolves to exactly one `InternalProjectIdentity` while active.

Validation:
- The pair `{subjectId, scopedProjectId}` must be unique.
- The same `scopedProjectId` may appear under different subjects.
- A `scopedProjectId` must not be treated as an internal project identity.

## Internal Project Identity

Represents the backend storage key for project-scoped data.

Fields:
- `internalProjectId`: Stable backend storage identity.
- `title`: Material project title.
- `state`: Active or deleted.

Relationships:
- Owns learning objects, recall points, review queues, media bindings, audit records, and other project-scoped records.
- May be referenced by one active `SubjectMaterialRelationship`.

Validation:
- Project-scoped storage APIs operate on `internalProjectId`.
- Internal ids are not the route identity for subject material workspaces.

## Subject Material Relationship

Connects a subject-scoped material identity to an internal project identity.

Fields:
- `subjectId`: Owning subject.
- `materialId`: Stable material relationship id.
- `materialType`: Course, book, loose points, or other supported material type.
- `title`: User-visible material title.
- `scopedProjectId`: Subject-scoped material project identity.
- `internalProjectId`: Internal project identity containing project-scoped data.
- `createdAt`: Relationship creation time.
- `state`: Active or deleted, following subject/material lifecycle semantics.

Relationships:
- Belongs to one `Subject`.
- Points to one `InternalProjectIdentity`.

Validation:
- Active relationships must point to active internal projects.
- Relationship persistence must survive service restart.
- Missing internal projects or missing subject records are integrity errors.
- Existing recoverable rows may be migrated only through deterministic migration logic.

## Scoped Workspace Request

Represents a request to open or operate on a subject material workspace.

Fields:
- `subjectId`: Subject identity from the workspace address.
- `scopedProjectId`: Subject-scoped material project identity from the workspace address.

Resolution:
- The backend resolves this request to `internalProjectId`.
- Authorization checks apply to the subject and the resolved material relationship before project-scoped data access.

Validation:
- Unknown subject returns a not-found or access-control result.
- Unknown scoped material under an existing subject returns not-found.
- A scoped material belonging to another subject must not resolve.

## State Transitions

Subject creation:
1. Create active subject.
2. Create default material relationship with first subject-scoped id.
3. Create internal project for material data.
4. Persist all three facts atomically.

Material creation:
1. Validate active subject.
2. Allocate next subject-scoped id.
3. Create internal project.
4. Persist relationship and internal project atomically.

Service restart:
1. Load subjects.
2. Load subject-material relationships.
3. Hydrate runtime subject/material structures.
4. Report integrity errors for unrecoverable broken relationships.

Material workspace access:
1. Receive `{subjectId, scopedProjectId}`.
2. Resolve to `internalProjectId`.
3. Authorize subject/material access.
4. Read or mutate project-scoped data by `internalProjectId`.
