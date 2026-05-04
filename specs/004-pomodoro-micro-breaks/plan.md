# Implementation Plan: Pomodoro Random Micro Breaks

**Branch**: `004-pomodoro-micro-breaks` | **Date**: 2026-05-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/004-pomodoro-micro-breaks/spec.md`

## Summary

Add an opt-in random micro break mode as part of Pomodoro settings. When a Pomodoro focus segment is active and the learner enters the workbench video player fullscreen, the player schedules a randomized reminder inside the configured interval. The reminder plays a short sound, pauses the video, shows a closed-eye rest countdown, then restores playback only if the video was playing before the reminder. The timer resets on fullscreen exit and never triggers during the final 3 minutes of a focus segment or during the existing 10-second Pomodoro transition prompt.

The implementation will extend existing Pomodoro settings and profile global-settings sync, add a focused frontend timer/controller around the video player fullscreen state, reuse the current Pomodoro audio unlock/sound path, and cover the behavior with source-level frontend assertions plus profile API persistence tests.

## Technical Context

**Language/Version**: TypeScript 5.9, React 18.3, Python 3.12, FastAPI 0.115, Pydantic 1.10  
**Primary Dependencies**: Zustand persist store, React Router, TanStack Query, Zod, FastAPI profile/global-settings endpoints, existing Pomodoro audio helpers  
**Storage**: Browser-local Zustand persistence for anonymous/offline settings; authenticated global settings persisted through `/api/profile/me/global-settings` and backend auth store  
**Testing**: `pytest` source/contract assertions, backend profile API tests, targeted frontend ESLint, `pnpm --dir frontend build`  
**Target Platform**: Browser web application served by the Python/FastAPI backend; fullscreen and Web Audio APIs available in modern desktop browsers  
**Project Type**: Web application with frontend Pomodoro/workbench UI and backend settings persistence  
**Performance Goals**: Micro break trigger and visible countdown appear within 1 second of the scheduled target; countdown ticks remain stable at 1-second cadence; no polling faster than 1 second while active  
**Constraints**: Feature remains opt-in; no micro break outside active Pomodoro focus fullscreen; no trigger in the final 3 minutes of focus; no overlap with existing 10-second Pomodoro transition prompt; canceled micro breaks must not auto-resume video  
**Scale/Scope**: Single learner browser session; one active fullscreen video player and at most one active micro break at a time

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution file is still in template form and does not define concrete gates. This plan applies the repository's active AGENTS guidance instead:

- Minimal necessary changes scoped to Pomodoro settings, Pomodoro settings sync, workbench video fullscreen behavior, tests, and user documentation.
- TDD-oriented implementation: add failing tests/source assertions before production changes.
- Preserve unrelated dirty worktree changes and avoid broad refactors.
- Update docs because user-visible settings and playback behavior change.

Gate status before Phase 0: PASS. No constitution violations or complexity exceptions.

## Project Structure

### Documentation (this feature)

```text
specs/004-pomodoro-micro-breaks/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── global-settings-pomodoro-micro-breaks.md
│   └── pomodoro-micro-break-ui.md
└── tasks.md
```

### Source Code (repository root)

```text
adapter/
├── routers/profile.py           # Read/write global Pomodoro settings payload
└── schemas.py                    # Request DTO validation for Pomodoro micro break settings

backend/system/
└── auth_store.py                 # Persist and normalize authenticated global settings

frontend/src/
├── ui/
│   ├── api/profile.ts            # Zod schema and update payload shape
│   ├── globalSettingsSync.ts     # Apply remote Pomodoro micro break settings to store
│   ├── pomodoroAudio.ts          # Reuse/add short reminder sound helper
│   └── store/pomodoroStore.ts    # Settings model, defaults, normalization, migration
├── views/pomodoro/
│   └── PomodoroSettingsPage.tsx  # Settings controls for enable/range/duration
└── views/workbench/components/
    └── VideoPane.tsx             # Fullscreen eligibility, timer, countdown, video pause/resume

docs/
└── learningpyramid-user-manual.md

tests/
├── test_frontend_fullscreen_capture.py
├── test_frontend_pomodoro_multi_plan.py
└── test_profile_api.py
```

**Structure Decision**: Extend the existing Pomodoro and workbench modules rather than introducing a separate feature area. Settings belong to the Pomodoro store/settings page; runtime behavior belongs in the video player because it owns fullscreen state and the video element; authenticated persistence follows the existing profile global-settings contract.

## Phase 0: Research Output

Research decisions are captured in [research.md](./research.md). All planning unknowns are resolved there, including settings persistence, timer ownership, random scheduling semantics, audio fallback, and validation ranges.

## Phase 1: Design & Contracts

Design artifacts:

- [data-model.md](./data-model.md): Pomodoro micro break settings, timer, and session state.
- [contracts/global-settings-pomodoro-micro-breaks.md](./contracts/global-settings-pomodoro-micro-breaks.md): profile global-settings payload contract.
- [contracts/pomodoro-micro-break-ui.md](./contracts/pomodoro-micro-break-ui.md): settings and fullscreen UI behavior contract.
- [quickstart.md](./quickstart.md): validation flow and commands.

## Post-Design Constitution Check

Gate status after Phase 1: PASS.

- No new dependencies required.
- No database schema migration is planned; settings are stored inside the existing global settings payload.
- Complexity remains localized to one persisted settings shape and one fullscreen timer/controller.
- Testing plan covers frontend behavior assertions, backend persistence, and build validation.

## Complexity Tracking

No constitution violations or complexity exceptions are required.
