# Quickstart: Membership Refund Window

## Goal

Verify that membership refunds can be newly initiated within 24 hours of successful payment, cannot be newly initiated afterward, and already-started provider refunds can still finish after the window.

## Suggested Verification Flow

1. Start the backend and frontend using the project's normal local development flow.
2. Sign in with an admin account and a test member account.
3. Create and pay a membership order for the member using the existing manual or mocked payment flow.
4. Within 24 hours of the order's successful payment time, initiate a refund from the admin membership order detail flow.
5. Confirm the refund is accepted and the existing refund side effects still occur: membership entitlement rollback, coupon restoration if applicable, invite reward reversal if applicable, and audit logging.
6. Create and pay another membership order.
7. Move the effective current time to later than 24 hours after that order's successful payment time.
8. Try to initiate a new refund for the older paid order.
9. Confirm the request is rejected before any provider refund begins, the order remains paid, and the error explains that the refund period expired.
10. For a provider-backed order, initiate refund inside the 24-hour window and leave it in a refund-in-progress state.
11. Move the effective current time beyond 24 hours after successful payment.
12. Synchronize provider refund status or process a refund callback and confirm completion still succeeds.

## Backend Test Targets

- Paid membership order within 24 hours can be refunded.
- Paid membership order at exactly 24 hours can be refunded.
- Paid membership order later than 24 hours cannot start a new refund.
- Late refund rejection happens before a provider refund request is submitted.
- Paid order missing successful payment time cannot start a new refund.
- `refund_pending` provider sync can complete after the 24-hour refund window.
- Existing coupon restoration and invite reward rollback tests still pass for eligible refunds.

## Frontend/Admin Verification Targets

- Admin refund action surfaces a clear expired-window error when the backend rejects a late refund.
- Admin order state remains unchanged after a late rejected refund.
- Existing successful refund feedback remains unchanged for eligible refunds.
