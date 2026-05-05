# Implementation Plan: WeChat Payout Automation

**Branch**: `009-wechat-payout-automation` | **Date**: 2026-05-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/009-wechat-payout-automation/spec.md`

## Summary

Make invite commission settlement and WeChat withdrawals unattended for a desktop web product. The implementation will keep the existing invite-commission business rules from `008-invite-commission` while adding verified WeChat receiving identities, a desktop QR binding flow that opens in mobile WeChat, scheduled/idempotent commission settlement, WeChat merchant transfer in user-confirmation mode, transfer result notification parsing, query-based reconciliation, and admin exception visibility. The current user-entered `wechatOpenId` withdrawal flow will be replaced by a bound receiving identity flow; manual admin resolution remains only for exceptions.

## Technical Context

**Language/Version**: Python 3 with FastAPI backend; TypeScript with React 18/Vite frontend  
**Primary Dependencies**: FastAPI, Pydantic, existing SQLite-backed membership stores, `requests`, `cryptography`, existing WeChat Pay v3 signing/decryption helpers, React Router, TanStack Query, Zod, existing QR rendering or QR image delivery approach selected during implementation  
**Storage**: Existing membership database with additive tables/columns for WeChat receiving identities, desktop/mobile binding attempts, withdrawal provider events, reconciliation warnings, and automated settlement metadata  
**Testing**: pytest for backend/store/API behavior; focused frontend contract/static tests and `npm run build` when frontend TypeScript changes  
**Target Platform**: LearningPyramid desktop web application in local, self-hosted, and hosted modes, plus a mobile WeChat binding/confirmation page opened from a desktop QR code; production requires public HTTPS callback/binding URLs  
**Project Type**: Web application with backend API, browser frontend, WeChat mobile handoff flow, and operational maintenance scripts  
**Performance Goals**: Settlement scan and withdrawal reconciliation process bounded batches in constant per-record work; user commission summary and binding polling remain fast enough for interactive page load; WeChat callback processing is idempotent and returns quickly after local state update  
**Constraints**: Preserve existing 7.5-discount coupon, 20 yuan price, fixed 5 yuan commission, 15 yuan paid threshold, and 24-hour refund window rules; do not accept raw OpenID entry as production withdrawal path; desktop binding QR codes are short-lived and one-purpose; mobile scan alone must not bind until the user confirms the account context; reserve balance before provider submission; never retry payout with a different merchant bill number until original result is known; all provider callbacks, binding completions, polling, and queries must be idempotent  
**Scale/Scope**: Current single monthly membership product, invite commission ledger, user commission page, desktop QR receiving identity binding, mobile WeChat binding confirmation page, admin membership page, merchant transfer payout, scheduled local settlement, and scheduled payout reconciliation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution file currently contains placeholder headings and no concrete enforceable gates. This plan follows the active `AGENTS.md` instructions instead: minimal necessary changes, no unrelated refactors, tests for money-moving behavior, synchronized documentation when usage or operations change, and no claims of unrun verification.

Pre-design gate result: PASS. No concrete constitution violation is identifiable.

## Project Structure

### Documentation (this feature)

```text
specs/009-wechat-payout-automation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── wechat-payout-automation-api.md
└── tasks.md             # Phase 2 output (/speckit-tasks command)
```

### Source Code (repository root)

```text
adapter/
├── deps.py                              # expose any new commission identity/reconciliation dependencies
├── schemas.py                           # binding, withdrawal, callback, admin DTO request schemas
└── routers/
    ├── membership.py                    # user binding, commission, withdrawal, WeChat payout notify endpoints
    └── admin.py                         # admin payout identity, reconciliation, withdrawal exception views/actions

backend/
└── system/
    ├── membership_commission_store.py   # receiving identities, desktop QR binding attempts, automated settlement, withdrawal ledger/events
    ├── membership_payment_service.py    # WeChat merchant transfer v3 request, callback parse, transfer query, OpenID resolution helpers
    └── membership_maintenance.py        # unattended settlement and payout reconciliation batch functions

tools/
├── settle_membership_commissions.py     # cron/scheduler entry for refund-window settlement
└── reconcile_commission_withdrawals.py  # cron/scheduler entry for WeChat payout result sync

frontend/
└── src/
    ├── ui/
    │   ├── api/
    │   │   ├── membership.ts            # receiving identity, QR binding, polling, and withdrawal contracts
    │   │   └── admin.ts                 # admin audit/reconciliation contracts
    │   └── queries/
    │       ├── membership.ts
    │       └── admin.ts
    └── views/
        ├── membership/
        │   ├── MembershipPage.tsx
        │   └── components/
        │       └── MembershipProfilePanel.tsx
        └── admin/AdminMembershipPage.tsx

tests/
├── test_membership_api.py               # user binding, QR polling, withdrawal, callback API behavior
├── test_admin_api.py                    # admin visibility and exception handling
├── test_membership_payment_service.py   # merchant transfer request/query/callback mapping and identity resolution
├── test_membership_maintenance.py       # unattended settlement and reconciliation batches
└── test_sqlite_store.py                 # additive schema and ledger invariants if needed

docs/
└── membership-selfhost-launch-checklist.md or README.md
                                         # deployment cron, QR binding URL, and WeChat merchant transfer prerequisites
```

**Structure Decision**: Extend the current membership/payment modules rather than creating a separate payout subsystem. The existing store already owns commission records and withdrawal state; the payment service already owns WeChat signing, verification, and AES-GCM resource decryption; the maintenance module already has a reconciliation pattern for pending WeChat payments. This keeps the change additive and localized while replacing the unsafe user-entered OpenID withdrawal path with a desktop QR binding flow.

## Phase 0: Research

Research output is captured in [research.md](./research.md). Decisions:

- Use verified WeChat receiving identities derived from WeChat authorization, not user-entered raw OpenID.
- Use a desktop QR handoff as the primary production binding path: desktop creates a short-lived binding attempt, the user scans with mobile WeChat, the mobile page confirms the LearningPyramid account, and the backend resolves the OpenID server-side.
- Replace the current legacy batch transfer path for production commission payout with WeChat Pay merchant transfer user-confirmation mode.
- Treat `WAIT_USER_CONFIRM` as a local awaiting-confirmation state and return confirmation parameters to the frontend.
- Treat frontend `requestMerchantTransfer` success as "confirmation UI returned", not final payout success.
- Use WeChat transfer notifications as the primary final-state input and merchant-bill query as the reconciliation fallback.
- Make automatic settlement a local idempotent maintenance batch that can be run by cron or a scheduler every few minutes.
- Keep manual admin resolution only for exception states that notification/query cannot resolve safely.

## Phase 1: Design & Contracts

Design output is captured in:

- [data-model.md](./data-model.md)
- [contracts/wechat-payout-automation-api.md](./contracts/wechat-payout-automation-api.md)
- [quickstart.md](./quickstart.md)

Post-design constitution check: PASS. The placeholder constitution still has no concrete gate to evaluate; the design uses additive storage, preserves existing invite business rules, requires idempotent ledger transitions, makes desktop QR binding explicit, and includes backend/API/maintenance verification for every money-moving state transition.

## Phase 2: Task Planning Preview

Task generation should prioritize:

1. Backend store tests for desktop QR binding attempts, expiry, scan/confirm lifecycle, active identity replacement, masked display, and withdrawal rejection when unbound.
2. Backend store tests for automatic settlement idempotency, refund-window blocking, existing pending commission inclusion, and canceled/refunded commission behavior.
3. Payment service tests for OpenID resolution, new merchant transfer request mapping, `WAIT_USER_CONFIRM`, terminal success/failure mapping, duplicate notification parsing, and merchant-bill query mapping.
4. Withdrawal ledger tests for reserve-before-submit, awaiting-confirmation, processing, success, failure, cancellation, and exactly-once balance transitions.
5. Maintenance tests for commission settlement batch and payout reconciliation batch summaries.
6. Router/schema changes for desktop QR binding creation/polling, mobile WeChat binding completion, user withdrawal, transfer notification, admin audit, and admin exception endpoints.
7. Frontend API/query/schema changes and membership/admin UI updates for unbound/binding/expired/ready identity, QR modal, mobile confirmation handoff, withdrawal confirmation, status history, and exception warnings.
8. Operational scripts and documentation for cron/scheduler setup, public HTTPS notify URLs, public HTTPS binding URLs, transfer scene configuration, and local `manual_test` behavior.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitution violations or complexity exceptions.
