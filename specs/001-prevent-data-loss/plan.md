# Implementation Plan: Prevent Server Data Loss

**Branch**: `001-prevent-data-loss` | **Date**: 2026-05-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-prevent-data-loss/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Guarantee that production user data survives deployment, restart, rebuild, sync, backup, restore, and maintenance operations. The implementation will make protected data explicit, include uploaded media in verified backups, add preflight/postflight deployment gates, expose data-safety status and integrity findings, and require explicit confirmed recovery paths instead of silently showing empty or partial data.

## Technical Context

**Language/Version**: Python 3.12 backend/tools; TypeScript + React frontend; PowerShell/Bash deployment scripts  
**Primary Dependencies**: FastAPI/Uvicorn, Pydantic, PostgreSQL/SQLite runtime stores, React/Vite, pytest  
**Storage**: Hosted/self-hosted database stores plus filesystem project roots containing uploaded media assets; self-host compose currently binds `./data/selfhost` to both `/data` and `/app/data`  
**Testing**: `python -m pytest`, focused deployment/config tests, frontend `pnpm build` where UI/API contracts are touched  
**Target Platform**: Self-hosted Linux Docker/Compose deployment and local Windows development tools  
**Project Type**: Web application with FastAPI backend, React frontend, deployment/maintenance scripts  
**Performance Goals**: Data-safety checks complete fast enough for every deploy; standard backup/restore workflow can meet the spec target of recovery within 30 minutes for normal hosted data volumes  
**Constraints**: No production data path may be deleted, shadowed, or replaced without verified backup plus explicit operator confirmation; missing/inaccessible protected storage must block risky operations; UI must distinguish empty data from inaccessible data  
**Scale/Scope**: Current self-hosted production instance plus future hosted instances with multiple users, projects, recall points, media assets, auth records, and audit history

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution is currently a placeholder with no formal project-specific gates. Active gates are derived from AGENTS.md and this feature's safety requirements:

- Minimal, scoped implementation: changes should target data inventory, backup/restore, deployment checks, status reporting, and integrity checks only.
- Documentation must be updated for any changed backup, restore, deployment, or operator workflow.
- Tests are required for safety-critical behavior: backup media inclusion, restore validation, deployment blockers, and broken-reference detection.
- Destructive or potentially destructive operations require explicit confirmation, a verified backup, and audit trail.
- Any unresolved production data integrity blocker prevents release.

Status: PASS before Phase 0. Re-check after Phase 1: PASS; no constitution violations introduced by the design.

## Project Structure

### Documentation (this feature)

```text
specs/001-prevent-data-loss/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── system/
│   ├── auth_store.py
│   ├── hosted_deployment_checks.py
│   ├── persistence_store.py
│   └── persistence_json.py
├── models/
│   ├── project_config.py
│   ├── recall_point.py
│   └── study_material.py
└── ...

frontend/
├── src/
│   ├── ui/
│   │   ├── api/
│   │   └── queries/
│   ├── components/
│   └── views/
└── ...

tools/
├── backup_runtime_bundle.py
├── restore_runtime_bundle.py
├── sync_selfhost_server.ps1
└── sync_selfhost_server.sh

tests/
├── test_hosted_deployment_checks.py
└── ...

docs/
├── self-host.md
└── ...

docker-compose.selfhost.yml
```

**Structure Decision**: Implement as a cross-cutting backend/tools/deployment safety feature. Backend exposes data-safety status and integrity results, tools own backup/restore behavior, deployment scripts and hosted checks enforce preflight/postflight gates, frontend only surfaces existing API status where needed.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitution violations.

## Phase Plan

### Phase 0: Research

Complete. Decisions are recorded in [research.md](./research.md).

### Phase 1: Design

Complete. Data model, operator contracts, and validation quickstart are recorded in:

- [data-model.md](./data-model.md)
- [contracts/operator-data-safety.md](./contracts/operator-data-safety.md)
- [contracts/deployment-safety.md](./contracts/deployment-safety.md)
- [quickstart.md](./quickstart.md)

### Phase 2: Tasks

Not generated by `/speckit-plan`. Run `/speckit-tasks` after reviewing this plan.
