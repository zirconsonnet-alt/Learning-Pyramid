# Implementation Plan: Backend Verification Gates

**Branch**: `015-scoped-project-identity` | **Date**: 2026-05-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/016-backend-verification-gates/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Define a backend verification gate that blocks release unless persistence, restart-recovery, real storage migration, identity boundaries, and actionable diagnostics have been validated on the real failure surface. The implementation will layer targeted fast tests with explicit restart and storage smoke checks, then record what ran, what was skipped, and why.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python backend, TypeScript frontend, PowerShell operator scripts  
**Primary Dependencies**: Existing `SystemAPI`, FastAPI adapter layer, pytest/unittest, Playwright, PostgreSQL smoke path  
**Storage**: PostgreSQL for production-shaped persistence checks; repository-backed JSON/SQLite paths remain relevant for regression coverage  
**Testing**: pytest, unittest, Playwright, compile checks, backend boundary verification, storage smoke checks  
**Target Platform**: Existing web application on local development machines and CI  
**Project Type**: Web application with backend verification workflow  
**Performance Goals**: Standard gate path should complete quickly enough for routine pre-release use; real storage smoke must remain practical on a developer machine  
**Constraints**: No fallback, shim, legacy compatibility layer, or request-time repair solely to satisfy verification; no broad storage rewrite; no production credentials required for routine gating  
**Scale/Scope**: Backend release verification across persistence, restart recovery, identity boundaries, and diagnostics

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Root cause before modification: Pass. The gate exists to prevent symptom-only verification from masking restart and persistence defects.
- System cleanliness first: Pass. The feature adds explicit verification boundaries rather than a hidden compatibility path.
- No fallback/shim/legacy expansion: Pass. The gate must fail loudly on missing recovery or schema coverage.
- No unconfirmed broad storage rewrite: Pass. The feature verifies the existing model instead of converting all storage to composite keys.
- No hidden behavior change: Pass. The gate documents and checks behavior without changing runtime semantics.
- Documentation with code changes: Pass. Implementation tasks must update `docs/current-change.md` and durable docs when code changes land.
- No Python future annotations: Pass. No new `from __future__ import annotations` usage is introduced.

## Project Structure

### Documentation (this feature)

```text
specs/016-backend-verification-gates/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── models/
├── repositories/
└── system/

tests/
├── test_subject_material_persistence.py
├── test_subject_material_identity.py
├── test_postgres_subject_material_relationships.py
├── test_postgres_persistence_system_state.py
└── test_repair_subject_material_relationship_index.py

tools/
└── repair_subject_material_relationship_index.py

docs/
├── current-change.md
├── data-model.md
└── deployment.md
```

**Structure Decision**: Use the existing backend-centric web application layout. The verification gate lives across `tests/`, `tools/`, and the existing backend persistence and adapter boundaries. No new external contract directory is required because this feature defines an internal release-verification workflow rather than a public API.

## Complexity Tracking

No constitution violations require justification.
