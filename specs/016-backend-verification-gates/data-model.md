# Data Model: Backend Verification Gates

## Verification Gate

Represents the release-blocking check set for backend changes.

Fields:
- `gateName`: Human-readable gate name.
- `scope`: What kinds of changes require the gate.
- `requiredChecks`: The checks that must pass for the gate to pass.
- `optionalChecks`: Informational checks that do not block release.
- `reportFormat`: The structure of the output report.

Relationships:
- Includes one or more `Restart-Recovery Scenario` entries.
- Includes one or more `Persistent Storage Smoke` entries when storage is affected.

Validation:
- A gate that omits a required check is incomplete.
- A gate must not pass if any required check fails or is skipped without explicit justification.

## Restart-Recovery Scenario

Represents a workflow that proves the backend still works after runtime reconstruction.

Fields:
- `scenarioName`: Short label for the workflow.
- `createdData`: The user-visible data created before restart.
- `restartBoundary`: The point where the runtime is reconstructed.
- `postRestartAssertions`: The user-visible outcomes that must still hold.

Relationships:
- Feeds into `Validation Report`.

Validation:
- The scenario must include a persistence step and a post-restart reopen step.
- A scenario that never crosses a restart boundary does not qualify.

## Persistent Storage Smoke

Represents a verification run against production-shaped storage.

Fields:
- `storageShape`: Real storage or equivalent production-shaped environment.
- `migrationCoverage`: Which schema or data migrations are exercised.
- `readWriteCoverage`: Which writes and reloads are validated.
- `integrityCoverage`: Which integrity failures are expected and reported.

Relationships:
- Supports storage-affecting release decisions.

Validation:
- Must run against a real storage shape when persistence, schema, or migration changes are involved.
- Must fail on missing columns, type mismatches, or failed migrations.

## Identity Invariant

Represents a rule that keeps public workflow identity distinct from internal storage identity.

Fields:
- `publicIdentity`: The user-facing subject or workspace identity.
- `scopedIdentity`: The identity scoped to that subject or workspace.
- `internalIdentity`: The backend storage identity.

Relationships:
- Applies to routing, payloads, logs, and error messages.

Validation:
- A field name that can mean two different identities is a gate failure in covered workflows.
- Logs must make the identity boundary legible.

## Validation Report

Represents the artifact that tells maintainers what was actually checked.

Fields:
- `executedChecks`: Checks that ran.
- `skippedChecks`: Checks that were not run, with reasons.
- `failedChecks`: Checks that failed.
- `unresolvedRisks`: Known gaps or environment blockers.

Relationships:
- Summarizes the gate outcome.

Validation:
- A passing report must include executed and skipped checks.
- A report that hides skipped required checks is invalid.

## State Transitions

Gate evaluation:
1. Identify the scope of the change.
2. Select required checks.
3. Execute fast regressions.
4. Execute restart and storage smoke checks when required.
5. Record the report.
6. Pass or block release.

Failure reporting:
1. Detect missing coverage or broken invariants.
2. Attribute the failure to the failed boundary.
3. Block release with an actionable report.
