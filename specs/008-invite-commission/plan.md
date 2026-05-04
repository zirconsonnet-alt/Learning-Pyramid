# Implementation Plan: Invite Discount And Commission

**Branch**: `008-invite-commission` | **Date**: 2026-05-05 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-invite-commission/spec.md`

## Summary

Replace the current invite reward model where inviters receive a 5 yuan coupon. New invite bindings should grant the invitee a 7.5-discount membership coupon, change the monthly membership base price to 20 yuan, and create a fixed 5 yuan inviter commission after an invited user's actual membership payment reaches 15 yuan and passes the existing 24-hour refund window without refund. The implementation will extend the existing membership, marketing, admin, and payment-provider patterns with a commission ledger and WeChat Pay withdrawal flow while keeping old 5 yuan coupon records readable as historical data.

## Technical Context

**Language/Version**: Python 3 with FastAPI backend; TypeScript with React 18/Vite frontend  
**Primary Dependencies**: FastAPI, Pydantic, existing membership store/payment service, existing WeChat Pay v3 payment integration, React Router, TanStack Query, Zod  
**Storage**: Existing membership SQLite-backed store file, with additive tables/columns for discount coupons, commission ledger, commission accounts, withdrawal requests, and WeChat payout status  
**Testing**: pytest for backend/API behavior; Zod/static frontend contract tests and frontend build when frontend TypeScript changes  
**Target Platform**: LearningPyramid web application in local and hosted modes  
**Project Type**: Web application with backend API plus browser frontend  
**Performance Goals**: Price preview and invite binding remain single-user constant-time operations; commission settlement scans only eligible pending records and is idempotent; admin lists stay bounded by existing pagination/limit patterns  
**Constraints**: Preserve existing invite binding entry points; preserve historical old-model coupons; avoid issuing new inviter-side 5 yuan coupons; commission cannot become withdrawable until the 24-hour refund window passes; WeChat payout must be status-tracked and idempotent  
**Scale/Scope**: Membership purchase, invite binding, coupon listing, commission settlement, withdrawal request, admin membership audit, and WeChat payout integration for the current single monthly membership product

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution file currently contains placeholder headings and no concrete project principles, gates, or governance rules to evaluate. This plan follows the active `AGENTS.md` instructions instead: minimal necessary changes, no unrelated refactors, tests for behavior changes, and synchronized documentation when usage or money movement changes.

Pre-design gate result: PASS. No concrete constitution violation is identifiable.

## Project Structure

### Documentation (this feature)

```text
specs/008-invite-commission/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── invite-commission-api.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
adapter/
├── deps.py                              # expose any new commission/payout store or service dependency
├── routers/
│   ├── membership.py                    # user invite, coupon, commission, withdrawal endpoints
│   └── admin.py                         # admin commission and withdrawal audit endpoints
└── schemas.py                           # withdrawal request and admin filters

backend/
└── system/
    ├── membership_store.py              # 20 yuan pricing, order success hooks, refund interactions
    ├── membership_marketing_store.py    # invite discount coupon issuance and historical coupon behavior
    ├── membership_payment_service.py    # WeChat payout adapter or shared WeChat request signing reuse
    └── membership_commission_store.py   # commission ledger, account balances, settlement, withdrawals

frontend/
└── src/
    ├── ui/
    │   ├── api/
    │   │   ├── membership.ts            # user commission/withdrawal contracts
    │   │   └── admin.ts                 # admin commission/withdrawal contracts
    │   └── queries/
    │       ├── membership.ts
    │       └── admin.ts
    └── views/
        ├── membership/
        │   ├── MembershipPage.tsx
        │   ├── membershipUi.tsx
        │   └── components/
        │       ├── MembershipProfilePanel.tsx
        │       └── MembershipPurchaseDialog.tsx
        └── admin/AdminMembershipPage.tsx

tests/
├── test_membership_api.py
├── test_admin_api.py
└── test_frontend_llm_settings_location.py # extend or add static frontend contract coverage if appropriate
```

**Structure Decision**: Use the existing web application layout and keep money-related state changes in backend stores. The existing marketing store remains responsible for invite bindings and coupon eligibility. A dedicated commission store keeps settlement and withdrawal accounting separate from coupon reward history, making balance invariants easier to test and preventing the old invite coupon model from leaking into new cash settlement behavior.

## Phase 0: Research

Research output is captured in [research.md](./research.md). Decisions:

- Replace new invite rewards with invitee-side percentage discount coupons while preserving old coupon records.
- Set membership base price to 2000 cents and remove the old first-order discount as the default pricing mechanism for this feature.
- Represent the 7.5-discount coupon as a coupon type/source that can calculate percentage discount, with order-time snapshots preserving the actual discount in cents.
- Create pending commission on qualifying paid orders, settle fixed 500-cent commission only after the 24-hour refund window, and cancel if refund starts in the window.
- Keep commission ledger/account balances separate from coupon tables and make all settlement and withdrawal operations idempotent.
- Use a WeChat Pay transfer/payout adapter for withdrawals, with local request reservation before provider submission and reconciliation after provider result.

## Phase 1: Design & Contracts

Design output is captured in:

- [data-model.md](./data-model.md)
- [contracts/invite-commission-api.md](./contracts/invite-commission-api.md)
- [quickstart.md](./quickstart.md)

Post-design constitution check: PASS. The placeholder constitution still has no concrete gate to evaluate; the design uses additive storage, keeps old records readable, isolates new commission accounting, and includes backend/API verification for each money-moving state transition.

## Phase 2: Task Planning Preview

Task generation should prioritize:

1. Backend tests for 20 yuan base price, invitee 7.5-discount coupon issuance, and no new inviter 5 yuan coupon issuance.
2. Backend tests for pending commission creation, refund-window blocking, fixed 5 yuan settlement, and idempotent repeated settlement.
3. Backend tests for withdrawal reservation, success, failure, insufficient balance, and missing WeChat identity.
4. Additive store schema and DTO work for discount coupon type/source, commission records/accounts, and withdrawal requests.
5. Router and admin contract updates for user-facing commission/withdrawal views and admin audit lists.
6. Frontend API/schema/query updates and membership/admin UI copy updates replacing "5 元券" messaging.
7. Documentation updates for pricing, invite discount, commission settlement, and WeChat withdrawal operations.
8. Targeted regression verification for existing membership purchase, refund window, old coupon history, and admin membership flows.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitution violations or complexity exceptions.
