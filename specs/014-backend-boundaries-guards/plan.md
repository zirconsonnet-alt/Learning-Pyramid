# Implementation Plan: Backend Boundaries and Guards

**Branch**: `014-backend-boundaries-guards` | **Date**: 2026-05-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/014-backend-boundaries-guards/spec.md`

## Summary

Create a backend architecture boundary design and lightweight guard suite that make responsibility ownership explicit before any broader refactor. The plan keeps existing behavior unchanged, documents the approved boundaries for transport adaptation, scoped identity, authorization ownership, atomic cross-project mutations, and migration risk, then adds guard checks that report drift with rule ids and locations.

## Technical Context

**Language/Version**: Python backend, TypeScript frontend present but out of implementation scope for this feature  
**Primary Dependencies**: FastAPI adapter layer, existing backend system/model modules, existing script-based verification pattern  
**Storage**: Existing in-memory snapshot abstraction with JSON, SQLite, and Postgres persistence paths; no storage schema change planned  
**Testing**: Python unittest for guard behavior and existing scoped project lifecycle checks; repository verification scripts for static guard checks  
**Target Platform**: Web application backend running through the existing adapter process  
**Project Type**: Existing web-service backend with HTTP adapter, application service facade, domain models, persistence stores, and verification scripts  
**Performance Goals**: Guard checks should complete in under 10 seconds on the current repository and should not run during normal request handling  
**Constraints**: No user-visible behavior change; no broad rewrite; no fallback, shim, legacy expansion, hidden global state, or duplicate behavior path  
**Scale/Scope**: Boundary documentation plus guard checks for the current backend modules, focused on scoped identity, auth ownership, cross-project atomicity, and router/backend boundary drift

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The repository constitution file is still a placeholder template, so the active gates come from `AGENTS.md` and the feature specification:

- **System cleanliness first**: Pass. This plan creates explicit rules and guards before any refactor.
- **Minimum necessary change**: Pass. Scope is documentation plus guard scripts/tests; no broad extraction in this phase.
- **No fallback/shim/legacy expansion**: Pass. Existing migration risks are documented as risks only.
- **No unconfirmed behavior changes**: Pass. Existing user-visible behavior remains the baseline.
- **Root-cause before modification**: Pass. The root risk is semantic drift caused by unclear ownership boundaries and duplicate write paths.
- **No Python future annotations**: Pass. Plan does not require adding `from __future__ import annotations`.

## Project Structure

### Documentation (this feature)

```text
specs/014-backend-boundaries-guards/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── backend-boundary-guards.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
AGENTS.md
adapter/
├── scoped_projects.py
└── routers/

backend/
├── models/
├── protocols/
├── repositories/
└── system/

tests/
├── test_backend_boundary_guards.py
├── test_scoped_project_api_boundaries.py
└── test_subject_material_atomicity.py

tools/
├── verify_backend_boundaries.py
└── verify_scoped_project_routes.py
```

**Structure Decision**: Keep the current backend layout. Add boundary documentation under this feature spec and add at most one focused guard script plus matching tests in the existing `tools/` and `tests/` locations. Do not extract services during this plan unless a guard cannot be made meaningful without a minimal cleanup.

## Complexity Tracking

No constitution violations are planned.
