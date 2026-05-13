# Research: Scoped Project Identity

## Decision: Keep internal global project identity

**Rationale**: Existing project-scoped learning data, queues, audit records, media bindings, permissions, and persistence indexes are built around a single internal project identity. Removing it would require a broad composite-key migration across most project tables and would raise risk beyond the current failure.

**Alternatives considered**:
- Replace all project-scoped tables with `{subjectId, scopedProjectId}` composite keys. Rejected because it is a large storage rewrite that is not necessary to fix the production failure.
- Treat the subject-scoped id as the internal id. Rejected because text collisions with historical global ids already exist and would keep the semantic confusion.

## Decision: Make subject-scoped material identity explicit

**Rationale**: The route identity `{subjectId, scopedProjectId}` is valuable and should remain the user-facing workspace address. The defect is that the same field name, `projectId`, currently appears in places where it might mean either an internal global project id or a subject-scoped material id.

**Alternatives considered**:
- Continue using `{subjectId, projectId}` everywhere. Rejected because it preserves the ambiguity that caused debugging confusion and can lead to wrong backend calls.
- Hide subject-scoped ids from the frontend. Rejected because subject workspaces naturally need stable subject-scoped addresses.

## Decision: Persist subject-material relationships as first-class relationship data

**Rationale**: The current Postgres native load path reconstructs active project payloads from sharded tables but does not restore `studyMaterials` and `subjectMaterialLink`. That means a subject can remain in `project_snapshots` while losing runtime subject identity after restart. Relationship data must be durable, loadable, and validated independently from in-memory snapshots.

**Alternatives considered**:
- Reconstruct relationships only from existing `project_snapshots.subject_id` and `scoped_project_id`. Rejected as the only source because it lacks all relationship semantics, such as material identity and material type, and would become a hidden inference path.
- Store only JSON snapshots again. Rejected because the current Postgres path intentionally uses sharded/indexed tables; adding relationship persistence should fit that model.

## Decision: Use deterministic migration and integrity checks, not request-time fallback

**Rationale**: Existing production data may be recoverable from material project metadata and configuration. Recovery should happen through an explicit migration or validation flow so bad records are surfaced. Runtime fallback would hide corruption and create a second behavior path.

**Alternatives considered**:
- Guess missing relationships whenever a request fails. Rejected because it is a fallback and could bind the wrong project.
- Delete orphan-looking projects. Rejected because those internal projects may hold the actual learning data.

## Decision: Keep workspace URLs stable while renaming internal contracts

**Rationale**: Users and existing links should still open `/subjects/{subjectId}/projects/{scopedProjectId}/...`. The cleanup should happen in route parameter names, DTOs, frontend state, and backend resolver APIs, not by breaking existing URLs.

**Alternatives considered**:
- Change URL shape immediately. Rejected because it is unnecessary for semantic cleanup and would add migration burden.
- Keep URL path but continue naming the parameter `projectId`. Rejected because the route parameter is subject-scoped, not internal.

## Decision: Add targeted regression coverage before implementation

**Rationale**: The failure is lifecycle-based: create subject, persist, reload, then open workspace. Unit-only checks of resolver functions would miss the restart/hydration defect.

**Alternatives considered**:
- Manual production verification only. Rejected because the defect is easy to reintroduce.
- Broad end-to-end browser test first. Rejected as the only guard because backend persistence behavior can be tested more directly and faster.
