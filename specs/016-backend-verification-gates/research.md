# Research: Backend Verification Gates

## Decision: Make restart-recovery a release-blocking check

**Rationale**: The failure that motivated this feature only appeared after data was saved, the runtime was reconstructed, and the same workspace was opened again. A gate that does not cross the restart boundary can still miss the defect entirely.

**Alternatives considered**:
- Keep relying on unit tests. Rejected because they can pass while the restart path remains broken.
- Rely on manual production smoke only. Rejected because it moves the discovery point too late.

## Decision: Require real persistent storage checks for storage-affecting changes

**Rationale**: The prior defect surfaced schema and migration issues that mock or in-memory checks did not expose. Real storage is the only reliable way to validate schema shape, required columns, and migration behavior.

**Alternatives considered**:
- Mock the storage boundary. Rejected because it hides migration and type problems.
- Use only fast JSON snapshots. Rejected because the production path already depends on a richer persistence model.

## Decision: Separate fast regression tests from release-blocking smoke checks

**Rationale**: Fast tests are still useful for local development, but they do not cover the failure surface of persistence + restart + migration. The plan needs both layers, with the smoke checks carrying release authority.

**Alternatives considered**:
- Merge everything into one giant suite. Rejected because it makes the gate too slow for routine development.
- Hide smoke checks behind optional ad hoc instructions. Rejected because release evidence must be explicit.

## Decision: Treat identity naming as part of the gate, not just a style issue

**Rationale**: The original defect was amplified by `projectId` meaning different things in different layers. Verification must fail when the boundary is ambiguous, because ambiguous naming can hide a real misbinding.

**Alternatives considered**:
- Leave identity naming to code review only. Rejected because review can miss one path while tests pass.
- Accept mixed naming as long as behavior works. Rejected because it keeps future maintenance risk high.

## Decision: Require actionable verification reports

**Rationale**: A validation pass that says only "tests green" does not tell maintainers whether restart recovery, storage migration, or diagnostics were actually checked. The report must list what ran, what was skipped, and what failed.

**Alternatives considered**:
- Use raw test logs only. Rejected because logs are too noisy for release decisions.
- Emit no report when passing. Rejected because missing coverage would remain invisible.
