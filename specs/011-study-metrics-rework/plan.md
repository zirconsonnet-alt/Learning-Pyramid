# Implementation Plan: Study Metrics Rework

**Branch**: `011-study-metrics-rework` | **Date**: 2026-05-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/011-study-metrics-rework/spec.md`

## Summary

Rework the workbench and Pomodoro study metrics around one objective invariant: web presence is the total, and video watching, recall point entry, review time, AI Q&A, and distraction are a complete mutually exclusive partition of that web presence. Remove the current workbench card rows that synthesize "effective learning", "learning stay", and "objective focus rate" from overlapping signals. Pomodoro remains a scheduler only: it does not alter the base metric definitions, but its statistics slice the same web-presence partition by plan and by numbered Pomodoro, then add absence time and derived rates.

The implementation will replace the current overlapping frontend daily stats/presence stores with a project daily web-metric store that records ranges and resolves overlaps into one category per moment, update hosted sync contracts to carry the new ranges, stop Pomodoro completion from writing whole scheduled focus blocks into workbench effective time, and extend the Pomodoro statistics panel with per-plan/per-Pomodoro breakdowns and pie-style visualizations.

## Technical Context

**Language/Version**: TypeScript 5.9, React 18.3, Python 3.12, FastAPI 0.115, Pydantic 1.10  
**Primary Dependencies**: Zustand/localStorage-style browser stores, React Router, TanStack Query, Zod, existing profile study-metrics sync endpoint, existing Pomodoro schedule/snapshot helpers  
**Storage**: Browser localStorage for local metric ranges; authenticated hosted sync through `user_project_daily_study_stats`; SQLite/PostgreSQL-backed auth store for hosted users  
**Testing**: `pytest` source/contract assertions, profile API tests for sync shape and merge behavior, targeted frontend build via `pnpm --dir frontend build`  
**Target Platform**: Browser web application served by the Python/FastAPI backend; desktop and modern browser page visibility/interactivity signals  
**Project Type**: Web application with frontend workbench/Pomodoro UI and backend profile metric sync  
**Performance Goals**: Metric refresh remains near-real-time at the current card cadence; range normalization for a day remains fast for normal single-user study volume; Pomodoro statistics render without visible delay for one day's plans  
**Constraints**: No fabricated historical category detail; no Pomodoro-derived workbench web presence; visible category totals must equal web presence; no database-breaking migration without legacy read fallback  
**Scale/Scope**: Single learner project/day summaries, friend/profile/admin totals that may continue using available synced aggregate metrics, one active browser session as the primary recording source

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The repository constitution file is still in template form and does not define concrete gates. This plan applies the active `AGENTS.md` workflow rules as project gates:

- Minimal necessary changes scoped to metric recording, workbench card display, Pomodoro statistics, hosted sync contracts, tests, and user documentation.
- Because this affects multiple modules and a hosted sync contract, implementation must proceed from this plan rather than a silent local patch.
- Feature work must include tests or source assertions for the invariant and Pomodoro slicing behavior.
- User-facing metric labels and manual text must be updated with the new definitions.
- Existing unrelated worktree changes must be preserved.

Gate status before Phase 0: PASS. No constitution violations or complexity exceptions.

## Project Structure

### Documentation (this feature)

```text
specs/011-study-metrics-rework/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── study-metrics-sync.md
│   ├── workbench-status-card.md
│   └── pomodoro-statistics.md
└── tasks.md
```

### Source Code (repository root)

```text
adapter/
├── schemas.py                    # Study metric sync request fields
└── routers/profile.py            # Study metric DTO mapping and sync endpoint

backend/system/
├── auth_store.py                 # Hosted study metric persistence, range merge, legacy read
└── postgres_schema.py            # PostgreSQL schema additions if sync contract persists new ranges

frontend/src/
├── ui/
│   ├── api/profile.ts            # Zod schema for study metric sync
│   ├── studyMetricsSync.ts       # Sync local metric snapshots to hosted profile
│   └── store/
│       ├── workbenchDailyStats.ts    # Replace/retire overlapping effective/action stats API
│       ├── studyPresenceStore.ts     # Fold into objective web presence tracking or reduce to recorder helper
│       └── pomodoroActivityStore.ts  # Stop writing scheduled focus as workbench effective time; retain records as schedule markers
├── views/
│   ├── workbench/
│   │   ├── WorkbenchPage.tsx         # Work status card labels and values
│   │   └── components/
│   │       ├── VideoPane.tsx         # Video playback and embedded AI/compose activity windows
│   │       ├── ComposePane.tsx       # Recall point entry activity window
│   │       └── ReviewPane.tsx        # Review activity window
│   ├── ai/
│   │   └── AiChatPage.tsx            # Full-screen AI Q&A activity window
│   └── pomodoro/
│       └── PomodoroPage.tsx          # Per-plan/per-Pomodoro statistics and visual breakdown

docs/
└── learningpyramid-user-manual.md

tests/
├── test_frontend_pomodoro_multi_plan.py
├── test_frontend_workbench_metrics.py
├── test_profile_api.py
└── test_admin_api.py
```

**Structure Decision**: Evolve the existing workbench/Pomodoro/profile-sync modules because they already own the relevant UI and persistence surfaces. Introduce a clearer metric model inside the existing frontend store layer before touching UI labels, then adapt backend sync only as needed for cross-device and hosted profile behavior.

## Phase 0: Research Output

Research decisions are captured in [research.md](./research.md). All planning unknowns are resolved there, including overlap resolution, Pomodoro slicing, hosted sync migration, historical data handling, and the meaning of effective learning rate.

## Phase 1: Design & Contracts

Design artifacts:

- [data-model.md](./data-model.md): web presence/category intervals, daily summaries, Pomodoro summaries, and legacy metric handling.
- [contracts/study-metrics-sync.md](./contracts/study-metrics-sync.md): hosted sync request/response expectations for new metric ranges.
- [contracts/workbench-status-card.md](./contracts/workbench-status-card.md): workbench card display contract and invariant.
- [contracts/pomodoro-statistics.md](./contracts/pomodoro-statistics.md): per-plan/per-Pomodoro statistics and visual breakdown contract.
- [quickstart.md](./quickstart.md): validation flow and commands.

## Post-Design Constitution Check

Gate status after Phase 1: PASS.

- The plan is intentionally cross-module because the existing bug spans recording, display, Pomodoro, sync, and docs.
- No new runtime dependency is required for charting; the visual breakdown can be built with existing CSS/React primitives unless implementation later proves otherwise.
- Backend storage changes are limited to hosted metric sync compatibility and must retain legacy read behavior.
- Testing plan covers the arithmetic invariant, the Pomodoro no-web-presence case, API sync shape, and documentation labels.

## Complexity Tracking

No constitution violations or complexity exceptions are required.
