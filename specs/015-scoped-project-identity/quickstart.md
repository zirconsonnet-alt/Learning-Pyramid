# Quickstart: Scoped Project Identity

## Goal

Verify that subject material workspaces survive service restart and that code distinguishes internal project identity from subject-scoped material identity.

## Prerequisites

- Python dependencies installed.
- Frontend dependencies installed if frontend identity call sites are changed.
- PostgreSQL-backed self-host configuration available for the persistence regression path.

## Backend Verification

Run focused backend tests after implementation:

```powershell
python -m pytest tests/test_subject_material_persistence.py tests/test_subject_material_identity.py tests/test_scoped_project_api_boundaries.py
```

Expected result:
- Subject creation creates a subject, a relationship, and an internal material project.
- Reloading from persistence keeps the subject recognizable.
- `{subjectId, scopedProjectId}` resolves to the same internal project after restart.
- Invalid scoped ids do not resolve through global project ids.

## Frontend Verification

Run the frontend checks after identity state names are updated:

```powershell
pnpm --dir frontend test
pnpm --dir frontend build
```

Expected result:
- Workbench navigation uses `subjectId` and `scopedProjectId`.
- API helpers no longer model scoped workspace refs as `{ subjectId, projectId }`.

## Manual Smoke Test

1. Create a new subject.
2. Open its default material workspace.
3. Confirm content directory and work status load.
4. Restart the backend service.
5. Reopen the same workspace URL.
6. Confirm the page does not show `PRECONDITION: project id is not a subject`.
7. Confirm backend logs show subject id, scoped project id, and resolved internal project id for the scoped workspace request.

## Data Recovery Check

For existing production-like data:

1. Run the planned relationship integrity check.
2. Confirm recoverable subject-material rows are migrated deterministically.
3. Confirm unrecoverable rows are reported with subject id, scoped project id, and internal project id when available.
4. Do not delete internal project records unless an explicit integrity report proves they are unrelated to any active material data.

## Documentation Check

Before completion, update:

- `docs/current-change.md`
- `docs/data-model.md`
- Any module/API documentation that still names a subject-scoped material identity as `projectId`
