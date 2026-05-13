# Implementation Plan: Scoped Project Identity

**Branch**: `015-scoped-project-identity` | **Date**: 2026-05-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/015-scoped-project-identity/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Repair the subject/material project identity model without converting all project-scoped storage to composite keys. The backend keeps a global internal project identity for storage, while subject workspaces use the explicit pair `{subjectId, scopedProjectId}`. The plan fixes the Postgres restart failure by making subject-material relationships durable, then cleans API, DTO, frontend state, and diagnostics so `projectId` no longer carries two meanings.

## Technical Context

**Language/Version**: Python backend, TypeScript frontend  
**Primary Dependencies**: FastAPI adapter layer, existing `SystemAPI`, React frontend, existing project persistence repositories  
**Storage**: PostgreSQL self-host path is the immediate production target; JSON/SQLite snapshot paths remain part of the repository model and must stay coherent  
**Testing**: Python pytest/unittest for backend persistence/API behavior; frontend type/unit checks for scoped identity call sites where needed  
**Target Platform**: Existing web application deployed through the self-host backend and built frontend  
**Project Type**: Web application with HTTP backend, project persistence layer, and browser frontend  
**Performance Goals**: Scoped identity resolution should remain a single indexed relationship lookup or equivalent in normal request handling  
**Constraints**: No runtime fallback, shim, or legacy compatibility path; no broad conversion of project-scoped storage tables to composite keys; preserve existing subject workspace URLs  
**Scale/Scope**: Subject/material lifecycle, scoped workspace routes, persistence hydration, DTO naming, frontend route state, and focused tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The repository constitution file is still a placeholder template, so the active gates come from `AGENTS.md` and the feature specification:

- **Root cause before modification**: Pass. The production failure is traced to subject-material relationship data not being restored after service restart.
- **System cleanliness first**: Pass. The plan separates internal storage identity from subject-scoped route identity instead of adding another compatibility path.
- **No fallback/shim/legacy expansion**: Pass. Existing data recovery is planned as deterministic migration/validation, not request-time fallback.
- **No unconfirmed broad storage rewrite**: Pass. The plan keeps internal project identity and avoids converting all project-scoped tables to composite keys.
- **No hidden behavior change**: Pass. Existing subject workspace URLs remain valid, but code contracts rename the ambiguous identity.
- **Documentation with code changes**: Pass for planning. Implementation tasks must update `docs/current-change.md` and durable data/API docs.
- **No Python future annotations**: Pass. No `from __future__ import annotations` is planned.

## Project Structure

### Documentation (this feature)

```text
specs/015-scoped-project-identity/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── scoped-project-identity.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
adapter/
├── scoped_projects.py
└── routers/
    └── projects.py

backend/
├── models/
├── repositories/
└── system/
    ├── api.py
    ├── persistence_json.py
    ├── persistence_store.py
    ├── postgres_schema.py
    └── postgres_store.py

frontend/
├── src/
│   ├── shell/
│   ├── ui/
│   └── views/
└── tests/

tests/
├── test_subject_material_identity.py
├── test_scoped_project_api_boundaries.py
└── test_subject_material_persistence.py

docs/
├── current-change.md
└── data-model.md
```

**Structure Decision**: Keep the existing web application layout. Backend changes stay inside the current `SystemAPI`, persistence, repository, adapter, and model boundaries. Frontend changes are limited to scoped identity naming and call sites for subject workspace navigation. No new service layer or full storage-key rewrite is planned.

## Complexity Tracking

No constitution violations are planned.
