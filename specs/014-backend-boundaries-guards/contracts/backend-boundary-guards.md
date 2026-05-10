# Contract: Backend Boundary Guards

## Purpose

The guard suite reports backend boundary drift in a deterministic, reviewable format. It is a developer-facing contract, not a runtime user interface.

## Guard Categories

### BBG001 Transport Boundary

Transport-layer code must not access backend storage internals or private backend helpers unless the path is an explicitly approved boundary owner.

Owner: Transport Boundary.

Allowed behavior:
- Adapt request parameters, request bodies, dependency injection values, and response DTOs.
- Call public `SystemAPI` methods.
- Use approved adapter boundary helpers, currently `adapter/scoped_projects.py`.

Forbidden behavior:
- Access `api.sys` from `adapter/routers/`.
- Call private `SystemAPI` helpers such as `api._instance_media_service()` from `adapter/routers/`.

Approved boundary-owner paths:
- `adapter/scoped_projects.py`: owns adapter dependency wiring for scoped project identity resolution.

Finding severity: high for storage mutation access, medium for read-only internals access.

### BBG002 Scoped Identity Boundary

Public scoped project ids must be resolved through the approved identity boundary before storage-only identities are used.

Owner: Identity Boundary.

Allowed behavior:
- Resolve public `{subjectId, projectId}` through `adapter.scoped_projects.resolve_scoped_project`.
- Pass `ScopedProject.internal_project_id` to backend behavior methods after resolution.

Forbidden behavior:
- Define scoped project routes under `/subjects/{subjectId}/projects/{projectId}` without the approved resolver dependency.
- Treat public `projectId` as a storage identity.

Finding severity: high when a scoped route bypasses approved resolution.

### BBG003 Authorization Ownership Boundary

User ownership must be assigned to subject-level resources, not storage-only project identities.

Owner: Authorization Boundary.

Allowed behavior:
- Store user ownership for subject ids.
- Remove related memberships after approved subject/material lifecycle methods complete.

Forbidden behavior:
- Call `auth_store.add_project_owner()` with an internal, child, material, or storage-only project id.

Finding severity: high.

### BBG004 Atomic Mutation Boundary

Cross-project lifecycle operations must go through the approved atomic behavior owner.

Owner: Atomic Mutation Boundary.

Allowed behavior:
- Keep subject/material lifecycle writes inside the approved `SystemAPI` lifecycle methods that publish related project state together.

Forbidden behavior:
- Delete or mutate child project state through an independent `delete_project()` path inside subject/material lifecycle handling.
- Open independent sessions for subject and material project writes when the lifecycle operation must be atomic.

Finding severity: high.

### BBG005 Migration Risk Containment

Existing migration or compatibility behavior must be documented and contained. New code must not expand it into fallback, shim, or legacy behavior.

Owner: Migration Risk Boundary.

Allowed behavior:
- Keep documented migration code inside an approved owner path.
- Document current risk as `requires-decision` when it cannot be fixed inside the guard feature.

Forbidden behavior:
- Add fallback, shim, or compatibility expansion outside an approved owner path.
- Treat existing migration behavior as a reusable pattern for new feature work.

Approved boundary-owner paths:
- `backend/system/api.py`: contains documented subject/material migration behavior and is guarded against cross-project atomicity bypasses by BBG004.

Finding severity: medium by default, high if it affects cross-project mutation or authorization.

## Finding Output

Each finding must contain:

```text
rule_id: BBG001
severity: high
path: adapter/routers/example.py
line: 12
message: Transport layer accesses backend storage internals directly.
evidence: api.sys
```

Output may be text or structured data, but it must preserve these fields.

## Exit Behavior

- No findings: command exits successfully.
- Findings present: command exits unsuccessfully unless explicitly run in report-only mode.
- Internal guard error: command exits unsuccessfully and reports the guard failure separately from boundary findings.
