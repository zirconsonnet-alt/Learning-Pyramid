# Quickstart: Backend Verification Gates

## Goal

Verify backend changes against the real failure surface before release, so a green unit suite cannot hide restart, migration, or identity-boundary defects.

## Prerequisites

- Repository dependencies installed.
- A local environment capable of running backend tests.
- A production-shaped storage target for persistence-affecting changes.

## Standard Gate

Run the backend verification gate after making changes that affect persistence, identity, startup, or diagnostics.

```powershell
python tools/verify_backend_release_gate.py --scope restart
python tools/verify_backend_release_gate.py --scope identity
python tools/verify_backend_release_gate.py --scope storage --postgres-dsn postgresql://user:pass@localhost:5432/learningpyramid_test
```

Expected outcome:
- Fast regression tests run first.
- Required restart-recovery checks run next.
- Required storage smoke checks run when persistence is affected.
- A report lists what ran, what was skipped, and why.

## Storage Smoke

For changes that touch schema, migration, or restart recovery:

1. Start an isolated storage instance.
2. Run the migration or initialization path.
3. Create a representative subject/workspace flow.
4. Restart the backend runtime.
5. Reopen the same workspace.
6. Confirm the same identity resolves and the same data is still available.
7. Confirm the report names any broken boundary instead of hiding it.

If no PostgreSQL DSN is available, the storage gate must fail with a skipped required check. That result is not a successful release gate.

## Identity Checks

For changes that touch routing, API payloads, or logs:

1. Verify public subject/workspace identity is distinct from internal storage identity.
2. Verify no covered workflow uses one field name for two different identities.
3. Verify failure output distinguishes not-found, no-access, and broken-relationship outcomes.
4. Verify at least one real scoped workspace mapping is checked; an empty identity report is a gate failure, not a pass.

## Release Readiness

Before marking a backend change ready:

1. Confirm all required checks ran.
2. Confirm no required smoke check was skipped without an explicit reason.
3. Confirm the validation report is saved or otherwise available to the release decision.
4. Confirm the gate would have caught the original restart regression.
