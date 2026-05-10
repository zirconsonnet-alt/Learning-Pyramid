# Research: Backend Boundaries and Guards

## Decision: Treat this feature as governance and guard creation, not refactoring

**Rationale**: The immediate risk is semantic drift: multiple places can start owning scoped identity, authorization, or cross-project lifecycle behavior. Guarding the boundaries first creates a stable target for later extraction work.

**Alternatives considered**:
- Extract services immediately. Rejected because it would mix architecture clarification with behavior-preserving refactor risk.
- Only write documentation. Rejected because documentation alone does not catch new drift.

## Decision: Make transport-layer restrictions explicit

**Rationale**: Router modules should adapt requests and responses, but should not access storage internals or backend private helpers. This keeps HTTP concerns separate from domain behavior and avoids ad hoc bypasses.

**Alternatives considered**:
- Allow direct internals access for convenience. Rejected because it recreates unclear ownership.
- Move all route logic in one pass. Rejected as too broad for this feature.

## Decision: Keep scoped identity resolution centralized

**Rationale**: Public scoped project ids and storage-only project keys have different meanings. Centralizing the conversion prevents storage details from becoming public or authorization semantics.

**Alternatives considered**:
- Let each router resolve ids. Rejected because each router could drift.
- Store both identities as authorization facts. Rejected because storage-only keys must not be user ownership units.

## Decision: Define atomic cross-project lifecycle behavior as a named boundary

**Rationale**: Subject/material lifecycle operations span subject records, child projects, links, and generated ids. If these writes split across independent paths, failures can leave half-written state.

**Alternatives considered**:
- Rely on callers to sequence operations correctly. Rejected because failure handling becomes inconsistent.
- Keep only regression tests without an architectural rule. Rejected because new entrypoints may bypass the tested path.

## Decision: Guard checks should report reviewable findings

**Rationale**: Some boundary issues require human review, especially existing migration paths or deliberate privileged access. The guard output must include rule id, location, severity, and explanation so findings can be triaged without hiding risk.

**Alternatives considered**:
- Fail on every textual match. Rejected because this can block legitimate named boundary owners.
- Only warn informally. Rejected because findings need to be testable and enforceable.

## Current Repository Findings Requiring Later Decision

Command: `python tools/verify_backend_boundaries.py`

Findings recorded on 2026-05-10:

- `adapter/routers/friends.py:126` reports `BBG005` because a router comment names fallback behavior for historical study-day records.
- `adapter/routers/materials.py:39` reports `BBG001` because a router calls `api._instance_media_service()`.
- `adapter/routers/media.py:109` reports `BBG001` because a router calls `api._instance_media_service()`.
- `adapter/routers/media.py:118` and `adapter/routers/media.py:120` report `BBG001` because a router accesses `api.sys`.
- `adapter/routers/projects.py:200` reports `BBG002` because the scoped subject-context route does not use `resolve_scoped_project`.

These are recorded as existing boundary risks. This feature does not automatically fix them because doing so would change business-layer ownership and route behavior beyond guard creation.

## First Safe Extraction Candidate

Candidate: extract instance media playback/read behavior currently reached by `adapter/routers/materials.py` and `adapter/routers/media.py` into a public backend behavior method owned by `SystemAPI` or a named media boundary behind `SystemAPI`.

Responsibility:
- Resolve effective media source kind.
- Read project storage configuration through backend-owned session handling.
- Return enough data for routers to shape DTOs or `FileResponse` objects without accessing `api.sys` or private helpers.

Allowed dependencies:
- Backend model types.
- Existing project storage configuration repository through backend-owned session handling.
- Existing instance media service internals behind the public boundary.

Forbidden dependencies:
- Direct router access to `api.sys`.
- Direct router calls to private `SystemAPI` helpers.
- New fallback, shim, or compatibility behavior.

Non-goals:
- No user-visible media playback behavior change.
- No storage schema change.
- No route path change.
- No broad service extraction in this guard feature.
