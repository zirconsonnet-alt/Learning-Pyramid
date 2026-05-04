# Implementation Plan: Membership Feature Gating

**Branch**: `006-membership-feature-gating` | **Date**: 2026-05-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-membership-feature-gating/spec.md`

## Summary

Active members can use LLM configuration, AI Q&A, player AI Q&A, and Pomodoro; non-members cannot. The implementation will reuse the existing membership entitlement state, add a shared member-only access decision for protected backend operations, and add frontend gates that explain the restriction and link users to the membership center. The change is intentionally limited to the named features and must not alter pricing, membership lifecycle, or unrelated learning workflows.

## Technical Context

**Language/Version**: Python 3 with FastAPI backend; TypeScript with React 18/Vite frontend  
**Primary Dependencies**: FastAPI, Pydantic, React Router, TanStack Query, Zustand, Zod  
**Storage**: Existing membership SQLite/Postgres-backed store; existing auth/profile stores; no new persistent tables planned  
**Testing**: pytest for backend/API and repository static frontend tests; frontend build/lint where implementation scope requires  
**Target Platform**: LearningPyramid web application in local and hosted modes  
**Project Type**: Web application with backend API plus browser frontend  
**Performance Goals**: Membership access checks should complete quickly enough that protected pages and actions feel no slower than ordinary authenticated requests; non-member AI requests must be rejected before external or expensive AI work begins  
**Constraints**: Reuse current membership lifecycle, pricing, order, refund, and entitlement behavior; avoid schema or dependency changes; keep non-protected learning workflows available to non-members  
**Scale/Scope**: Four protected feature categories: LLM configuration, project/system AI Q&A, player AI Q&A that calls project LLM chat completion, and Pomodoro page/actions/settings

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution file currently contains placeholder headings and no concrete project principles, gates, or governance rules to evaluate. This plan follows the active `AGENTS.md` instructions instead: minimal necessary changes, no unrelated refactors, tests for behavior changes, and synchronized documentation when usage changes.

Pre-design gate result: PASS. No concrete constitution violation is identifiable.

## Project Structure

### Documentation (this feature)

```text
specs/006-membership-feature-gating/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
adapter/
├── deps.py
├── routers/
│   ├── profile.py       # user LLM configuration endpoints
│   └── system.py        # LLM, project AI, stream, debug, Pomodoro TTS endpoints
└── schemas.py

backend/
└── system/
    └── membership_store.py

frontend/
├── src/
│   ├── ui/
│   │   ├── api/
│   │   │   ├── http.ts
│   │   │   ├── membership.ts
│   │   │   ├── profile.ts
│   │   │   └── system.ts
│   │   └── queries/
│   │       └── membership.ts
│   └── views/
│       ├── ai/AiChatPage.tsx
│       ├── pomodoro/PomodoroPage.tsx
│       ├── pomodoro/PomodoroSettingsPage.tsx
│       ├── settings/GlobalSettingsPage.tsx
│       ├── settings/components/LlmSettingsCards.tsx
│       └── workbench/components/VideoPane.tsx

tests/
├── test_api_envelope.py
├── test_membership_api.py
├── test_frontend_llm_settings_location.py
└── test_frontend_pomodoro_multi_plan.py
```

**Structure Decision**: Use the existing web application layout. Backend changes belong in the API adapter layer and reuse the current `MembershipStore`; frontend changes belong in the existing pages and API/query helpers that already own LLM, AI chat, video AI chat, and Pomodoro experiences.

## Phase 0: Research

Research output is captured in [research.md](./research.md). Decisions:

- Use current active membership entitlement as the single source of truth.
- Enforce protected feature access in backend action endpoints and mirror it in frontend page/action gates.
- Preserve existing non-member access to unrelated pages and membership purchase/renewal flows.
- Treat stream endpoints and player AI calls as protected before expensive work starts.

## Phase 1: Design & Contracts

Design output is captured in:

- [data-model.md](./data-model.md)
- [contracts/member-feature-access.md](./contracts/member-feature-access.md)
- [quickstart.md](./quickstart.md)

Post-design constitution check: PASS. The placeholder constitution still has no concrete gate to evaluate; the design keeps the scope minimal, avoids new storage or dependencies, and includes tests for the permission change.

## Phase 2: Task Planning Preview

Task generation should prioritize:

1. Backend membership access helper and API tests.
2. Backend protection for LLM configuration, AI Q&A, stream/chat-completion/debug where applicable, and Pomodoro server-backed endpoints.
3. Frontend membership-aware gates and user-facing member-only messaging.
4. Frontend/static tests and targeted backend regression tests.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitution violations or complexity exceptions.
