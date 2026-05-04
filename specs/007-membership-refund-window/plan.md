# Implementation Plan: Membership Refund Window

**Branch**: `007-membership-refund-window` | **Date**: 2026-05-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-membership-refund-window/spec.md`

## Summary

Membership refunds can only be newly initiated within 1 day, defined as 24 hours, from the order's successful payment time. The implementation will reuse existing membership order payment timestamps and refund states, add a single refund-window eligibility decision to the membership refund initiation path, and keep already-started provider refunds free to complete through callbacks or admin synchronization after the window has passed. The change is intentionally limited to refund eligibility; it must not alter pricing, membership durations, entitlement rollback, coupon restoration, reward reversal, or non-refund order handling.

## Technical Context

**Language/Version**: Python 3 with FastAPI backend; TypeScript with React 18/Vite frontend  
**Primary Dependencies**: FastAPI, Pydantic, existing membership payment service, React Router, TanStack Query, Zod  
**Storage**: Existing membership SQLite/Postgres-backed store; existing `membership_orders` and `membership_payments` timestamps; no new persistent tables planned  
**Testing**: pytest for backend/API behavior and repository static frontend tests if UI copy or contract references change; frontend build if frontend files change  
**Target Platform**: LearningPyramid web application in local and hosted modes  
**Project Type**: Web application with backend API plus browser frontend  
**Performance Goals**: Refund eligibility checks should be constant-time against the loaded order data and not add visible delay to admin refund actions  
**Constraints**: Use successful payment time as the only refund-window anchor; enforce a 24-hour boundary consistently; do not block provider refund callbacks or sync for refunds already accepted; avoid schema and dependency changes  
**Scale/Scope**: Membership refund initiation for `manual_test`, `wechat_native`, admin refund entry points, and any future member-facing refund initiation path that reuses the same store operation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution file currently contains placeholder headings and no concrete project principles, gates, or governance rules to evaluate. This plan follows the active `AGENTS.md` instructions instead: minimal necessary changes, no unrelated refactors, tests for behavior changes, and synchronized documentation when usage changes.

Pre-design gate result: PASS. No concrete constitution violation is identifiable.

## Project Structure

### Documentation (this feature)

```text
specs/007-membership-refund-window/
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
├── routers/
│   ├── admin.py         # admin refund initiation and refund-status sync entry point
│   └── membership.py    # payment/refund notifications; future member-facing refund entry points
└── schemas.py

backend/
└── system/
    ├── membership_store.py            # refund-window eligibility and refund state transitions
    └── membership_payment_service.py  # existing provider refund request/sync data

frontend/
└── src/
    ├── ui/
    │   ├── api/
    │   │   └── admin.ts               # only if response/UI contract typing changes
    │   └── queries/
    │       └── admin.ts               # only if mutation handling needs messaging changes
    └── views/
        └── admin/AdminMembershipPage.tsx # only if late-refund messaging or disabled state is surfaced

tests/
├── test_membership_api.py
├── test_admin_api.py
└── test_frontend_llm_settings_location.py # only if static frontend contract coverage is changed
```

**Structure Decision**: Use the existing web application layout. The core behavior belongs in `MembershipStore` so all refund initiation paths share the same rule. Router changes should stay thin and continue using existing refund result DTOs and error envelopes.

## Phase 0: Research

Research output is captured in [research.md](./research.md). Decisions:

- Use `paid_at` as the refund-window anchor and reject paid orders without a valid successful payment time.
- Treat the 1-day policy as 24 hours inclusive through the exact 24-hour timestamp, rejecting later attempts.
- Enforce the rule at refund initiation in the membership store, not only in admin routing.
- Allow `refund_pending` callbacks and provider sync to continue after the window expires.
- Avoid schema changes by deriving eligibility from existing order/payment timestamps.

## Phase 1: Design & Contracts

Design output is captured in:

- [data-model.md](./data-model.md)
- [contracts/membership-refund-window.md](./contracts/membership-refund-window.md)
- [quickstart.md](./quickstart.md)

Post-design constitution check: PASS. The placeholder constitution still has no concrete gate to evaluate; the design keeps the scope minimal, avoids new storage or dependencies, and includes tests for the refund policy change.

## Phase 2: Task Planning Preview

Task generation should prioritize:

1. Backend tests proving refund inside window succeeds and refund after 24 hours is rejected.
2. Backend tests proving in-flight `refund_pending` sync/notification can complete after the window passes.
3. Shared refund-window eligibility helper in `MembershipStore` and integration into `refund_order` and provider refund initiation.
4. Admin/API messaging and documentation updates for the 1-day refund policy.
5. Targeted regression verification for existing coupon, invite reward, and WeChat refund flows.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitution violations or complexity exceptions.
