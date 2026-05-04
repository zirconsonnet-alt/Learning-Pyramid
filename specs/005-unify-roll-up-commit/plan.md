# Implementation Plan: Unified Roll-Up Commit

**Branch**: `005-unify-roll-up-commit` | **Date**: 2026-05-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/005-unify-roll-up-commit/spec.md`

## Summary

Unify the post-selection roll-up landing behavior across manual roll-up, threshold roll-up, and learning-object-isomorphic roll-up. After any trigger selects candidates, the system must consume source aggregation queue candidates, attach them under a single upper-layer parent, register that parent once to the next layer, and record the trigger reason without changing the core hierarchy result.

The key correction is for learning-object-isomorphic roll-up: it must no longer create or register object-mirror parents from learning-object structure or recall point coverage alone. It must first select currently consumable candidates from the relevant source layer `AggregationQueue`; if manual or threshold roll-up already consumed those candidates, the isomorphic scan becomes a no-op for that object and cannot create a duplicate "Chapter 1" style parent.

## Technical Context

**Language/Version**: Python 3.12 backend; TypeScript/React frontend exists but this feature is backend scheduling behavior only  
**Primary Dependencies**: In-process domain services and repositories in `backend/system/api.py`; existing model enums and repositories for layers, aggregation queues, learning objects, learning task nodes, registrations, and events  
**Storage**: Existing JSON/SQLite/Postgres persistence through repository abstractions; no schema migration planned  
**Testing**: `pytest`, focused on `tests/test_spec_alignment.py`; optional targeted persistence regression if behavior touches stored entity shapes  
**Target Platform**: Browser web application served by FastAPI, but runtime behavior is server-side project orchestration  
**Project Type**: Web application with backend domain orchestration and frontend consumers  
**Performance Goals**: Keep each idle orchestration scan bounded by current project learning-object nodes and current aggregation queue size; no new background scans beyond existing idle driver loop  
**Constraints**: No public API changes, no dependency changes, no database schema changes, preserve review-priority and actionable-missing-instance gates, preserve no-Tick-in-same-transaction roll-up constraints  
**Scale/Scope**: One project mutation session at a time; affects roll-up behavior for COURSE/BOOK projects using manual, threshold, or learning-object-isomorphic strategies

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution file is still in template form and does not define concrete gates. This plan applies the repository's active AGENTS guidance instead:

- Minimal necessary changes scoped to backend roll-up orchestration and focused tests.
- Preserve unrelated dirty worktree changes and avoid broad refactors.
- Use tests to capture the duplicate-node regression before implementation.
- Do not change public interfaces, persistence schema, dependencies, build configuration, or frontend behavior unless implementation evidence requires it.

Gate status before Phase 0: PASS. No constitution violations or complexity exceptions.

## Project Structure

### Documentation (this feature)

```text
specs/005-unify-roll-up-commit/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── roll-up-landing-behavior.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── system/
│   └── api.py                    # Roll-up selection, landing, idle orchestration driver
└── models/
    ├── aggregation_queue.py      # Existing queue semantics; no shape change planned
    ├── aggregation_event.py      # Existing event reason semantics; no shape change planned
    └── learning_task_node.py     # Existing parent/child and object-mirror fields

tests/
└── test_spec_alignment.py        # Regression and contract tests for unified roll-up behavior

docs/
└── spec.md                       # Update only if implementation changes normative system behavior documentation
```

**Structure Decision**: Keep the work inside the existing backend orchestration surface. The feature changes internal domain behavior, so no adapter/router/frontend files are expected. Tests belong in `tests/test_spec_alignment.py` because existing roll-up strategy and aggregation behavior coverage already lives there.

## Phase 0: Research Output

Research decisions are captured in [research.md](./research.md). Planning unknowns are resolved there, including how to make isomorphic selection queue-backed, how to share landing without breaking Phase A/Phase B transaction boundaries, and how to preserve idempotency when a prior manual parent already consumed the candidates.

## Phase 1: Design & Contracts

Design artifacts:

- [data-model.md](./data-model.md): roll-up trigger, selected candidate set, roll-up parent, source aggregation queue, upper-layer registration, and outcome record.
- [contracts/roll-up-landing-behavior.md](./contracts/roll-up-landing-behavior.md): behavioral contract for all trigger modes after candidate selection.
- [quickstart.md](./quickstart.md): validation scenarios and targeted test commands.

## Post-Design Constitution Check

Gate status after Phase 1: PASS.

- No new dependencies required.
- No public API or persistence schema changes planned.
- Testing plan directly covers the duplicate parent regression and existing threshold/manual behavior.
- Complexity remains localized to one backend orchestration module plus focused tests.

## Complexity Tracking

No constitution violations or complexity exceptions are required.
