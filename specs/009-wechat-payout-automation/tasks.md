# Tasks: WeChat Payout Automation

**Input**: Design documents from `/specs/009-wechat-payout-automation/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)
**Tests**: Included because this feature changes money-moving commission settlement, withdrawal reservation, WeChat payout, callback, reconciliation behavior, and verified receiving identity binding.

**Organization**: Tasks are grouped by user story so each story can be implemented and tested as an independent increment after the shared foundation is complete.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on incomplete tasks in the same phase
- **[Story]**: User story label for story-specific tasks only
- Every task includes an exact repository-relative file path

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish implementation boundaries, environment surfaces, and dependency choices before feature work.

- [X] T001 Review current commission ledger and payout identity implementation in `backend/system/membership_commission_store.py`
- [X] T002 [P] Review current WeChat Pay signing, notification, refund, and transfer helpers in `backend/system/membership_payment_service.py`
- [X] T003 [P] Review current membership payout routes and raw OpenID request handling in `adapter/routers/membership.py`
- [X] T004 [P] Review current membership withdrawal UI and binding state handling in `frontend/src/views/membership/MembershipPage.tsx`
- [X] T005 [P] Review current admin commission and withdrawal UI in `frontend/src/views/admin/AdminMembershipPage.tsx`
- [X] T006 Add project-local QR rendering dependency or documented QR rendering approach for the desktop binding modal in `frontend/package.json` and `frontend/pnpm-lock.yaml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add shared configuration, DTO shapes, storage primitives, and provider abstractions required by all user stories.

**Critical**: No user story implementation should begin until this phase is complete.

- [X] T007 Add WeChat payout and binding configuration fields for payout AppID, OAuth secret, public base URL, QR expiry, transfer scene, and provider mode in `backend/system/membership_payment_service.py`
- [X] T008 Document the new WeChat payout and desktop QR binding environment variables in `.env.selfhost.example`
- [X] T009 Add shared withdrawal status constants for `created`, `awaiting_confirmation`, `processing`, `succeeded`, `failed`, `canceled`, and `needs_attention` in `backend/system/membership_commission_store.py`
- [X] T010 Add shared binding status constants for `created`, `scanned`, `authorized`, `confirmed`, `bound`, `failed`, `canceled`, and `expired` in `backend/system/membership_commission_store.py`
- [X] T011 Add or migrate additive SQLite schema for payout identities, binding attempts, withdrawal provider events, reconciliation runs, and warnings in `backend/system/membership_commission_store.py`
- [X] T012 Add dataclasses for payout identity, binding attempt, payout provider event, reconciliation run, and reconciliation warning in `backend/system/membership_commission_store.py`
- [X] T013 Add shared masking, timestamp, idempotency-key, and provider-event helper methods in `backend/system/membership_commission_store.py`
- [X] T014 Add request/response schemas for binding start, binding poll, mobile binding completion, amount-only withdrawal creation, withdrawal sync, and admin resolution in `adapter/schemas.py`
- [X] T015 Add membership route DTO helpers for payout readiness, binding attempts, payout identities, withdrawal confirmation payloads, and withdrawal history in `adapter/routers/membership.py`
- [X] T016 Add admin route DTO helpers for payout identities, provider events, reconciliation runs, reconciliation warnings, and withdrawal sync results in `adapter/routers/admin.py`
- [X] T017 [P] Add frontend Zod schemas and API types for payout readiness, desktop QR binding attempts, binding poll results, and amount-only withdrawals in `frontend/src/ui/api/membership.ts`
- [X] T018 [P] Add frontend Zod schemas and API types for admin payout identities, transfer events, sync results, and reconciliation warnings in `frontend/src/ui/api/admin.ts`
- [X] T019 Confirm membership payment service and commission store dependencies are exposed to routers without circular imports in `adapter/deps.py`

**Checkpoint**: Foundation ready for independently testable user stories.

---

## Phase 3: User Story 1 - Bind WeChat Receiving Identity From Desktop Web (Priority: P1)

**Goal**: A desktop user can start binding, scan a short-lived QR code with mobile WeChat, confirm the LearningPyramid account being bound, and end with a verified masked WeChat receiving identity; unbound users cannot withdraw.

**Independent Test**: Use a desktop account without a bound identity, create a QR binding attempt, scan/open the mobile binding URL, complete or fail WeChat authorization and confirmation, and verify desktop readiness updates while full OpenID is never exposed.

### Tests for User Story 1

- [X] T020 [P] [US1] Add store tests for desktop QR binding creation, scan marking, expiry, cancellation, reuse rejection, and state validation in `tests/test_sqlite_store.py`
- [X] T021 [P] [US1] Add store tests for active payout identity creation, replacement, masking, and lookup by owner in `tests/test_sqlite_store.py`
- [X] T022 [P] [US1] Add payment service tests for OAuth authorization URL generation, code-to-OpenID resolution, appid mismatch rejection, and `manual_test` identity resolution in `tests/test_membership_payment_service.py`
- [X] T023 [P] [US1] Add API tests for payout readiness, desktop QR binding creation, desktop polling, mobile binding completion, invalid state, expired attempt, reused attempt, and unbound withdrawal rejection in `tests/test_membership_api.py`
- [X] T024 [P] [US1] Add frontend contract/static tests for payout identity DTO parsing, QR binding DTO parsing, and no production raw OpenID field usage in `tests/test_frontend_llm_settings_location.py`

### Implementation for User Story 1

- [X] T025 [US1] Implement desktop QR binding attempt creation with unguessable state, mobile binding URL, QR expiry, and owner snapshot in `backend/system/membership_commission_store.py`
- [X] T026 [US1] Implement binding attempt lookup, owner-scoped polling, scan marking, expiry transition, cancellation, and reuse rejection in `backend/system/membership_commission_store.py`
- [X] T027 [US1] Implement mobile confirmation and active identity replacement so scan alone never activates a receiving identity in `backend/system/membership_commission_store.py`
- [X] T028 [US1] Implement WeChat OAuth authorization URL generation for payout binding and server-side code-to-OpenID resolution in `backend/system/membership_payment_service.py`
- [X] T029 [US1] Implement `manual_test` binding path that exercises the same store transitions without exposing it as the production path in `backend/system/membership_payment_service.py`
- [X] T030 [US1] Implement `GET /api/commissions/payout-identity` and payout readiness inclusion in `GET /api/commissions/me` in `adapter/routers/membership.py`
- [X] T031 [US1] Implement `POST /api/commissions/payout-identity/wechat/binding-attempts` returning `qrCodePayload`, `mobileBindingUrl`, `pollAfterMs`, and `expiresAt` in `adapter/routers/membership.py`
- [X] T032 [US1] Implement owner-scoped `GET /api/commissions/payout-identity/wechat/binding-attempts/{bindingAttemptId}` polling in `adapter/routers/membership.py`
- [X] T033 [US1] Implement mobile `GET /api/commissions/payout-identity/wechat/mobile-bind` scan entry that validates attempt/state and redirects or presents the WeChat authorization step in `adapter/routers/membership.py`
- [X] T034 [US1] Implement `POST /api/commissions/payout-identity/wechat/bind` so mobile confirmation validates attempt/state/code/account context without relying on the desktop browser session in `adapter/routers/membership.py`
- [X] T035 [US1] Reject production withdrawal requests before reservation when no active payout identity exists in `adapter/routers/membership.py`
- [X] T036 [US1] Remove production `wechatOpenId` acceptance from withdrawal schema while retaining only explicitly isolated `manual_test` compatibility in `adapter/schemas.py`
- [X] T037 [US1] Add payout identity, QR binding start, QR binding poll, and mobile bind API functions in `frontend/src/ui/api/membership.ts`
- [X] T038 [US1] Add payout identity, QR binding start, QR binding poll, and mobile bind React Query hooks in `frontend/src/ui/queries/membership.ts`
- [X] T039 [US1] Add desktop QR binding modal with expiry countdown, polling, retry, scanned, failed, and ready states in `frontend/src/views/membership/MembershipPage.tsx`
- [X] T040 [US1] Add mobile WeChat binding confirmation page showing the LearningPyramid account and confirm/cancel states in `frontend/src/views/membership/WechatPayoutBindingPage.tsx`
- [X] T041 [US1] Register the mobile WeChat binding confirmation route in `frontend/src/router.tsx`
- [X] T042 [US1] Update membership profile panel copy to show masked WeChat binding state and remove manual OpenID guidance in `frontend/src/views/membership/components/MembershipProfilePanel.tsx`

**Checkpoint**: US1 works independently; a desktop user can bind safely through QR + mobile WeChat confirmation, and unbound withdrawal is blocked before funds are reserved.

---

## Phase 4: User Story 2 - Automatically Settle Eligible Commission (Priority: P1)

**Goal**: Eligible invite commission becomes withdrawable automatically after the 24-hour refund window without admin settlement.

**Independent Test**: Create eligible pending commission records, run the maintenance batch, and verify settled/canceled/skipped outcomes are idempotent and do not require the admin settlement endpoint.

### Tests for User Story 2

- [X] T043 [P] [US2] Add store tests for automatic settlement idempotency, refund-window blocking, refunded cancellation, existing pending inclusion, and already-settled skips in `tests/test_sqlite_store.py`
- [X] T044 [P] [US2] Add maintenance tests for settlement run summaries, per-record errors, bounded limits, and repeat safety in `tests/test_membership_maintenance.py`
- [X] T045 [P] [US2] Add admin API regression tests proving manual settlement remains idempotent and returns the new run summary shape in `tests/test_admin_api.py`

### Implementation for User Story 2

- [X] T046 [US2] Extend commission records with settlement mode, last checked timestamp, settlement run id, and failure reason using migration-safe defaults in `backend/system/membership_commission_store.py`
- [X] T047 [US2] Implement automatic settlement evaluation preserving fixed 5 yuan commission, 15 yuan paid threshold, and 24-hour refund-window rules in `backend/system/membership_commission_store.py`
- [X] T048 [US2] Implement settlement run recording with scanned, settled, canceled, skipped, and error counts in `backend/system/membership_commission_store.py`
- [X] T049 [US2] Implement `settle_due_membership_commissions` with bounded limit and per-record error isolation in `backend/system/membership_maintenance.py`
- [X] T050 [US2] Add `tools/settle_membership_commissions.py` CLI entrypoint with JSON summary output in `tools/settle_membership_commissions.py`
- [X] T051 [US2] Update admin manual settlement endpoint to call the same idempotent settlement service and return run summary fields in `adapter/routers/admin.py`
- [X] T052 [US2] Update admin API types for settlement run summaries in `frontend/src/ui/api/admin.ts`
- [X] T053 [US2] Update admin membership UI to display automatic settlement metadata and latest run summary fields in `frontend/src/views/admin/AdminMembershipPage.tsx`

**Checkpoint**: US2 works independently; valid commission becomes withdrawable after the refund window and repeated settlement runs do not double-credit balances.

---

## Phase 5: User Story 3 - Request WeChat Withdrawal (Priority: P2)

**Goal**: Users with withdrawable commission and a verified WeChat receiving identity can request withdrawal, reserve balance, and complete WeChat user confirmation when required.

**Independent Test**: Give a user a verified identity and withdrawable balance, submit a valid withdrawal, verify balance reservation and `awaiting_confirmation` or `processing` state, and verify missing/invalid amount cases are rejected with no reservation.

### Tests for User Story 3

- [X] T054 [P] [US3] Add withdrawal ledger tests for identity-required validation, amount limits, reservation, stable merchant bill numbers, and no double reservation in `tests/test_sqlite_store.py`
- [X] T055 [P] [US3] Add payment service tests for merchant transfer request mapping, `WAIT_USER_CONFIRM`, accepted state, provider failure mapping, and unknown-result handling in `tests/test_membership_payment_service.py`
- [X] T056 [P] [US3] Add API tests for amount-only withdrawal creation, confirmation payload response, provider submission failure recovery, and no `wechatOpenId` request field in `tests/test_membership_api.py`
- [X] T057 [P] [US3] Add frontend contract/static tests for amount-only withdrawal request and confirmation response DTO parsing in `tests/test_frontend_llm_settings_location.py`

### Implementation for User Story 3

- [X] T058 [US3] Refactor withdrawal creation to require an active payout identity snapshot and stable merchant bill number in `backend/system/membership_commission_store.py`
- [X] T059 [US3] Implement withdrawal reservation, provider submission event recording, awaiting-confirmation, processing, and submission-failure transitions in `backend/system/membership_commission_store.py`
- [X] T060 [US3] Replace legacy batch transfer payout request with WeChat merchant transfer bill request in `backend/system/membership_payment_service.py`
- [X] T061 [US3] Map WeChat merchant transfer response states and confirmation `package_info` into local payout status in `backend/system/membership_payment_service.py`
- [X] T062 [US3] Ensure provider submission unknown results keep the original merchant bill number for later query reconciliation in `backend/system/membership_payment_service.py`
- [X] T063 [US3] Update user withdrawal endpoint to reserve balance before provider submission and return confirmation payload when required in `adapter/routers/membership.py`
- [X] T064 [US3] Update frontend withdrawal API and mutation to send only `amountCent` and parse confirmation payloads in `frontend/src/ui/api/membership.ts`
- [X] T065 [US3] Update withdrawal mutation hooks for amount-only withdrawal and follow-up status invalidation in `frontend/src/ui/queries/membership.ts`
- [X] T066 [US3] Update membership withdrawal UI to remove OpenID input, show active masked identity, and disable withdrawal when payout readiness is not ready in `frontend/src/views/membership/MembershipPage.tsx`
- [X] T067 [US3] Add WeChat confirmation handling that calls `requestMerchantTransfer` only when confirmation data is returned and does not treat JSAPI return as final success in `frontend/src/views/membership/MembershipPage.tsx`
- [X] T068 [US3] Add unsupported WeChat client, provider unavailable, cancellation, and confirmation timeout messages in `frontend/src/views/membership/MembershipPage.tsx`

**Checkpoint**: US3 works independently; valid withdrawals reserve funds and enter the correct WeChat confirmation or processing state.

---

## Phase 6: User Story 4 - Automatically Reconcile Payout Results (Priority: P2)

**Goal**: Withdrawal results update automatically from WeChat transfer notifications or merchant-bill queries, with exactly-once balance transitions.

**Independent Test**: Submit withdrawals ending in success, failure, duplicate notification, no notification, and stale processing states, then verify automatic status changes and balance recovery.

### Tests for User Story 4

- [X] T069 [P] [US4] Add payment service tests for transfer notification signature/decryption mapping and merchant-bill query mapping in `tests/test_membership_payment_service.py`
- [X] T070 [P] [US4] Add store tests for succeeded, failed, canceled, expired, duplicate result, unknown result, and needs-attention withdrawal transitions in `tests/test_sqlite_store.py`
- [X] T071 [P] [US4] Add API tests for transfer notify endpoint idempotency and amount/appid/outBillNo mismatch rejection in `tests/test_membership_api.py`
- [X] T072 [P] [US4] Add maintenance tests for withdrawal reconciliation summaries, stale processing warnings, provider query errors, and repeat safety in `tests/test_membership_maintenance.py`

### Implementation for User Story 4

- [X] T073 [US4] Implement merchant transfer notification parsing, signature verification integration, decryption, and provider status mapping in `backend/system/membership_payment_service.py`
- [X] T074 [US4] Implement merchant transfer query by local merchant bill number and response status mapping in `backend/system/membership_payment_service.py`
- [X] T075 [US4] Implement idempotent withdrawal result application for success, failure, cancellation, expiry, and unknown states in `backend/system/membership_commission_store.py`
- [X] T076 [US4] Implement payout provider event append-only recording and duplicate-provider-event handling in `backend/system/membership_commission_store.py`
- [X] T077 [US4] Add public WeChat transfer notification endpoint that verifies, maps, and applies provider results idempotently in `adapter/routers/membership.py`
- [X] T078 [US4] Implement `reconcile_commission_withdrawals` with query fallback, stable out bill number use, and warning generation in `backend/system/membership_maintenance.py`
- [X] T079 [US4] Add `tools/reconcile_commission_withdrawals.py` CLI entrypoint with JSON summary output in `tools/reconcile_commission_withdrawals.py`
- [X] T080 [US4] Update user withdrawal history DTOs for awaiting confirmation, processing, succeeded, failed, canceled, and needs-attention states in `adapter/routers/membership.py`
- [X] T081 [US4] Update membership withdrawal history UI for automatic refresh, final-state display, failure recovery, and needs-attention messages in `frontend/src/views/membership/MembershipPage.tsx`

**Checkpoint**: US4 works independently; provider results are synchronized automatically and duplicate/out-of-order events do not double-change balances.

---

## Phase 7: User Story 5 - Admin Monitors Automated Settlement And Payouts (Priority: P3)

**Goal**: Admins can audit payout identities, settlement runs, withdrawal provider events, reconciliation warnings, and manual exception actions without seeing unnecessary raw OpenID data.

**Independent Test**: Generate bound/unbound identities, settled/canceled commission, succeeded/failed/stale withdrawals, and warnings; verify admin can trace each record to source user, order, bill, and provider event.

### Tests for User Story 5

- [X] T082 [P] [US5] Add admin API tests for payout identity list, withdrawal sync, provider events, reconciliation warnings, and manual exception resolution in `tests/test_admin_api.py`
- [X] T083 [P] [US5] Add frontend contract/static tests for admin payout identity, withdrawal event, warning, and sync DTO parsing in `tests/test_frontend_llm_settings_location.py`

### Implementation for User Story 5

- [X] T084 [US5] Add admin store queries for payout identities, binding attempts, provider events, reconciliation runs, and warnings in `backend/system/membership_commission_store.py`
- [X] T085 [US5] Add admin payout identity list endpoint with masked labels and latest binding outcome in `adapter/routers/admin.py`
- [X] T086 [US5] Add admin withdrawal sync endpoint using merchant-bill query and idempotent result application in `adapter/routers/admin.py`
- [X] T087 [US5] Extend admin withdrawal list endpoint with identity label, out bill number, transfer bill number, provider state, provider event count, and warning fields in `adapter/routers/admin.py`
- [X] T088 [US5] Record admin action logs for forced sync, warning acknowledgement, and manual exception resolution in `adapter/routers/admin.py`
- [X] T089 [US5] Add frontend admin API functions for payout identities, withdrawal sync, provider events, reconciliation warnings, and manual resolution in `frontend/src/ui/api/admin.ts`
- [X] T090 [US5] Add admin query hooks for payout identities, withdrawal sync, provider events, reconciliation warnings, and manual resolution in `frontend/src/ui/queries/admin.ts`
- [X] T091 [US5] Update admin membership UI to show payout identities, automated settlement metadata, transfer events, warnings, sync actions, and masked identity labels in `frontend/src/views/admin/AdminMembershipPage.tsx`

**Checkpoint**: US5 works independently; finance/support can trace automated settlement and payout records without querying raw database state.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, regression checks, and final verification across all stories.

- [X] T092 [P] Update production/self-host WeChat payout prerequisites, public binding URL, callback URL, and transfer scene notes in `README.md`
- [X] T093 [P] Update scheduler examples for `tools/settle_membership_commissions.py` and `tools/reconcile_commission_withdrawals.py` in `docs/membership-selfhost-launch-checklist.md`
- [X] T094 [P] Update local/staging frontend verification notes for desktop QR binding and WeChat confirmation in `frontend/README.md`
- [X] T095 Run backend focused tests for membership API, admin API, payment service, maintenance, and SQLite store in `tests/test_membership_api.py`, `tests/test_admin_api.py`, `tests/test_membership_payment_service.py`, `tests/test_membership_maintenance.py`, and `tests/test_sqlite_store.py`
- [X] T096 Run frontend build and static contract checks for membership/admin UI changes using `frontend/package.json`
- [ ] T097 Run quickstart validation scenarios and update any discovered gaps in `specs/009-wechat-payout-automation/quickstart.md`
- [X] T098 Review all money-moving transitions for idempotency and no raw OpenID display in `backend/system/membership_commission_store.py`
- [X] T099 Review user-facing copy for desktop QR binding, withdrawal confirmation, failure recovery, and admin warnings in `frontend/src/views/membership/MembershipPage.tsx` and `frontend/src/views/admin/AdminMembershipPage.tsx`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; can start immediately.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **US1 Desktop QR Binding (Phase 3)**: Depends on Foundational; required before production withdrawal.
- **US2 Automatic Settlement (Phase 4)**: Depends on Foundational; can run in parallel with US1 after shared foundations.
- **US3 Withdrawal Request (Phase 5)**: Depends on US1 for verified receiving identity and on US2 for practical withdrawable balance.
- **US4 Reconciliation (Phase 6)**: Depends on US3 withdrawal state and provider bill fields.
- **US5 Admin Monitoring (Phase 7)**: Depends on records and events produced by US1 through US4.
- **Polish (Phase 8)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Independent after Foundational; MVP for safe payout readiness and desktop QR binding.
- **US2 (P1)**: Independent after Foundational; MVP for unattended commission availability.
- **US3 (P2)**: Requires US1 identity binding and benefits from US2 settled balance.
- **US4 (P2)**: Requires US3 withdrawal/provider records.
- **US5 (P3)**: Requires audit data created by US1 through US4.

### Within Each User Story

- Tests should be written first and fail before implementation.
- Store/schema tasks precede service methods.
- Service/provider methods precede router endpoints.
- Router contracts precede frontend API/query updates.
- API/query updates precede UI updates.
- Story checkpoint should pass before moving to the next priority in a sequential implementation.

---

## Parallel Opportunities

- Setup reviews T002 through T005 can run in parallel.
- Foundational frontend type tasks T017 and T018 can run in parallel with backend DTO helper tasks after shared schema decisions.
- US1 tests T020 through T024 can run in parallel before US1 implementation.
- US2 tests T043 through T045 can run in parallel before US2 implementation.
- US3 tests T054 through T057 can run in parallel before US3 implementation.
- US4 tests T069 through T072 can run in parallel before US4 implementation.
- US5 tests T082 and T083 can run in parallel before US5 implementation.
- Documentation tasks T092 through T094 can run in parallel after implementation decisions are final.

## Parallel Example: User Story 1

```text
Task: "T020 [US1] Add store tests for desktop QR binding creation, scan marking, expiry, cancellation, reuse rejection, and state validation in tests/test_sqlite_store.py"
Task: "T022 [US1] Add payment service tests for OAuth authorization URL generation, code-to-OpenID resolution, appid mismatch rejection, and manual_test identity resolution in tests/test_membership_payment_service.py"
Task: "T023 [US1] Add API tests for payout readiness, desktop QR binding creation, desktop polling, mobile binding completion, invalid state, expired attempt, reused attempt, and unbound withdrawal rejection in tests/test_membership_api.py"
Task: "T024 [US1] Add frontend contract/static tests for payout identity DTO parsing, QR binding DTO parsing, and no production raw OpenID field usage in tests/test_frontend_llm_settings_location.py"
```

## Parallel Example: User Story 2

```text
Task: "T043 [US2] Add store tests for automatic settlement idempotency, refund-window blocking, refunded cancellation, existing pending inclusion, and already-settled skips in tests/test_sqlite_store.py"
Task: "T044 [US2] Add maintenance tests for settlement run summaries, per-record errors, bounded limits, and repeat safety in tests/test_membership_maintenance.py"
Task: "T045 [US2] Add admin API regression tests proving manual settlement remains idempotent and returns the new run summary shape in tests/test_admin_api.py"
```

## Parallel Example: User Story 4

```text
Task: "T069 [US4] Add payment service tests for transfer notification signature/decryption mapping and merchant-bill query mapping in tests/test_membership_payment_service.py"
Task: "T070 [US4] Add store tests for succeeded, failed, canceled, expired, duplicate result, unknown result, and needs-attention withdrawal transitions in tests/test_sqlite_store.py"
Task: "T072 [US4] Add maintenance tests for withdrawal reconciliation summaries, stale processing warnings, provider query errors, and repeat safety in tests/test_membership_maintenance.py"
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete US1 so users can bind WeChat payout identity from desktop web and unbound withdrawals are blocked.
3. Complete US2 so commission becomes withdrawable without admin settlement.
4. Stop and validate both P1 stories independently before implementing payout transfer.

### Incremental Delivery

1. Deliver US1 + US2 as the operational foundation.
2. Add US3 to create real withdrawal requests and WeChat confirmation.
3. Add US4 to make payout result updates unattended.
4. Add US5 to expose admin audit and exception handling.
5. Finish documentation, cron setup, and regression validation.

### Parallel Team Strategy

1. Complete Setup and Foundational work together.
2. After Phase 2, one worker can implement US1 while another implements US2 because both are P1 and touch mostly distinct behavior.
3. After US1 and US2, implement US3 before US4.
4. Start US5 after provider events, reconciliation warnings, and settlement run records exist.

---

## Notes

- Do not implement production withdrawal with manually entered UID/OpenID.
- The desktop QR code is only an identity-binding handoff; it is not a collection code and must not move money.
- The mobile WeChat page must show the LearningPyramid account being bound before confirmation.
- Mobile binding completion should validate the short-lived attempt/state and WeChat authorization result; it should not assume the mobile browser shares the desktop login session.
- Preserve existing invite coupon, membership price, paid threshold, fixed 5 yuan commission, and 24-hour refund-window rules.
- Never retry a payout with a different merchant bill number until the original result is known.
