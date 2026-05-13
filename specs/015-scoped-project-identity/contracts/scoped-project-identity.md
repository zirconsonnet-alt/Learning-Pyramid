# Contract: Scoped Project Identity

## Purpose

Subject material workspaces are addressed by `{subjectId, scopedProjectId}` and resolved by the backend to an internal project identity. Contracts must keep those identities distinct.

## Identity Terms

- `subjectId`: The subject identity.
- `scopedProjectId`: The material workspace identity scoped to one subject.
- `internalProjectId`: The backend storage identity for project-scoped data.
- `materialId`: The relationship identity for a subject material entry.

Forbidden contract usage:
- Do not use `projectId` for subject-scoped material identity.
- Do not expose a subject-scoped route parameter as an internal project identity.
- Do not resolve a scoped workspace by internal project identity alone.

## Subject Materials

### List Subject Materials

Request:

```text
GET /api/subjects/{subjectId}/materials
```

Response item shape:

```json
{
  "subjectId": "subj_000003",
  "materialId": "mat_course_000001",
  "materialType": "COURSE",
  "title": "网课材料",
  "scopedProjectId": "proj_000001",
  "createdAt": "2026-05-12T09:35:15Z"
}
```

Rules:
- `scopedProjectId` is scoped to the subject in the request.
- The response must not name this value `projectId`.
- Normal user-facing responses do not need to expose `internalProjectId`.

## Scoped Workspace Routes

All subject material workspace routes use the same identity boundary:

```text
/api/subjects/{subjectId}/projects/{scopedProjectId}/...
```

Rules:
- The path shape may stay unchanged for URL compatibility.
- Route code and generated types should name the second parameter `scopedProjectId`.
- Before accessing project-scoped storage, the backend resolves `{subjectId, scopedProjectId}` to `internalProjectId`.

Resolution result:

```json
{
  "subjectId": "subj_000003",
  "scopedProjectId": "proj_000001",
  "internalProjectId": "proj_000099"
}
```

Rules:
- This resolution result is a backend boundary object or diagnostic record.
- If exposed to a client, it must be clearly marked as diagnostic or developer-facing.

## Error Semantics

Unknown subject:

```json
{
  "error": "subject not found"
}
```

Unknown scoped project under an existing subject:

```json
{
  "error": "subject material not found"
}
```

Scoped project belongs to another subject:

```json
{
  "error": "subject material not found"
}
```

Data integrity failure:

```json
{
  "error": "subject material relationship is inconsistent"
}
```

Rules:
- A valid subject with missing material relationship data must not be reported as "project id is not a subject".
- Authorization failures keep the existing authorization status semantics.

## Persistence Integrity Contract

Every active subject material relationship must satisfy:

```text
subject exists and is active
scopedProjectId is unique inside subject
internalProjectId exists and is active
material relationship contains materialId, materialType, title, createdAt
```

Startup or validation may fail fast or report explicit integrity errors for unrecoverable records. It must not silently bind a scoped identity to a guessed internal project.

## Frontend State Contract

Frontend route and API state should use:

```ts
type ScopedProjectRef = {
  subjectId: string
  scopedProjectId: string
}
```

Rules:
- Frontend code must not store this as `{ subjectId, projectId }`.
- Frontend code must not assume `scopedProjectId` is usable for project-scoped backend storage APIs outside the scoped route boundary.
