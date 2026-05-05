# Data Model: WeChat Payout Automation

## WeChat Receiving Identity

Represents a verified payout target owned by a LearningPyramid user.

**Attributes**:

- `identityId`: unique identity identifier
- `userId`: owner user id
- `provider`: `wechat_pay`
- `appid`: WeChat AppID context used to obtain the payee OpenID
- `openid`: backend-only payee identifier used for WeChat merchant transfer
- `maskedOpenid`: display-safe label such as `oABC123***`
- `status`: `active`, `revoked`, `invalid`, or `replaced`
- `verifiedAt`: time the identity became usable for withdrawals
- `revokedAt`: time the identity was deactivated, if any
- `latestBindingAttemptId`: last binding attempt that affected this identity
- `failureReason`: latest provider/user-readable failure reason, if invalid
- `createdAt`, `updatedAt`

**Validation rules**:

- A withdrawal can use only an `active` identity owned by the requesting user.
- The production API never accepts raw OpenID as a withdrawal request field.
- Replacing an identity requires a new successful binding attempt.
- User/admin DTOs return only masked identity labels.
- The `appid` must match the merchant transfer AppID context configured for payout.

## Binding Attempt

Represents one attempt to bind a user's WeChat receiving identity.

**Attributes**:

- `bindingAttemptId`: unique attempt identifier
- `userId`: account attempting binding
- `provider`: `wechat_pay`
- `channel`: `desktop_qr_official_account_h5`, `official_account_h5`, `mini_program`, `app`, or `manual_test`
- `state`: anti-forgery state or nonce generated before authorization
- `status`: `created`, `scanned`, `authorized`, `confirmed`, `bound`, `failed`, `canceled`, or `expired`
- `desktopReturnUrl`: desktop page that should be refreshed or updated after binding completes
- `mobileBindingUrl`: short-lived URL encoded into the desktop QR code
- `qrExpiresAt`: time when the desktop QR code stops being valid
- `scannedAt`: time a mobile WeChat client opened the binding URL, if any
- `confirmedAt`: time the user confirmed the LearningPyramid account on the mobile binding page, if any
- `authorizationCodeHash`: optional hash/reference of the received one-time authorization code
- `resolvedOpenid`: backend-only OpenID resolved from the provider
- `identityId`: created or updated identity, if binding succeeds
- `failureReason`: failure or cancellation reason
- `createdAt`, `authorizedAt`, `completedAt`, `expiresAt`

**Validation rules**:

- Desktop binding attempts must be short-lived and single-purpose.
- Opening or scanning a QR code does not activate a receiving identity by itself.
- The mobile binding page must identify the LearningPyramid account being bound before confirmation.
- Authorization state must match the logged-in user before binding is completed.
- An authorization code can be consumed only once.
- A failed/canceled/expired attempt cannot activate an identity.
- A successful attempt deactivates any previous active identity for the same user/provider context.
- Polling a binding attempt can reveal only the current user's own attempt status and masked final identity.

**State transitions**:

- Start binding -> `created`
- Mobile WeChat opens QR link -> `scanned`
- Provider callback/code accepted -> `authorized`
- User confirms platform account on mobile page -> `confirmed`
- OpenID resolved and identity saved -> `bound`
- User cancels, provider rejects, state mismatch, code invalid, or account context mismatch -> `failed` or `canceled`
- Attempt passes expiry without completion -> `expired`

## Commission Record

Represents invite commission from the existing `008-invite-commission` feature, extended with automation metadata.

**Attributes**:

- Existing fields: `commissionId`, `inviterUserId`, `inviteeUserId`, `sourceOrderId`, `sourcePaymentAmountCent`, `thresholdAmountCent`, `commissionAmountCent`, `refundWindowEndsAt`, `status`, timestamps, and cancel reason
- `settlementMode`: `manual`, `automatic`, or `migration`
- `lastSettlementCheckedAt`: latest time automation evaluated the record
- `settlementRunId`: maintenance run that settled or canceled the record, if any
- `settlementFailureReason`: error or warning from the latest failed automated evaluation, if any

**Validation rules**:

- Existing eligibility remains unchanged: invited membership payment, actual paid amount at least 1500 cents, no refund started inside the 24-hour window, fixed 500-cent commission.
- Pending records whose refund window has passed are eligible for automatic evaluation.
- Settled/canceled/reversed records are not changed by normal automatic settlement.
- Repeated automatic evaluation must not increase balances more than once.

**State transitions**:

- `pending` + refund window passed + no refund/refund-pending -> `settled`
- `pending` + refund/refund-pending inside refund window -> `canceled`
- `settled` + explicit support correction -> `reversed`

## Commission Account

Represents aggregate balances derived from commission and withdrawal ledger state.

**Attributes**:

- `userId`
- `pendingCent`
- `withdrawableCent`
- `reservedCent`
- `paidOutCent`
- `canceledCent`
- `correctionCent`
- `updatedAt`

**Validation rules**:

- No bucket can become negative.
- Withdrawal reservation moves funds from withdrawable to reserved.
- Withdrawal success moves funds from reserved to paid out.
- Withdrawal failure/cancellation/expiry moves funds from reserved back to withdrawable.
- Computed or stored totals must be reconcilable from commission and withdrawal records.

## Withdrawal Request

Represents a user request to withdraw commission to a bound WeChat receiving identity.

**Attributes**:

- `withdrawalId`: local withdrawal identifier
- `userId`: requester
- `amountCent`: requested amount
- `targetType`: `wechat_pay`
- `identityId`: active receiving identity snapshot used for payout
- `identityMaskedLabel`: display-safe target label
- `status`: `created`, `awaiting_confirmation`, `processing`, `succeeded`, `failed`, `canceled`, or `needs_attention`
- `outBillNo`: stable merchant bill number for WeChat transfer
- `transferBillNo`: WeChat transfer bill number, if returned
- `packageInfo`: confirmation package returned when the user must confirm receipt
- `providerState`: latest raw provider state mapped into local status
- `failureReason`: user/admin-readable failure reason
- `createdAt`, `reservedAt`, `submittedAt`, `confirmationRequestedAt`, `completedAt`, `updatedAt`

**Validation rules**:

- User must have an active WeChat receiving identity.
- Requested amount must be positive, meet configured minimum payout amount, and not exceed withdrawable balance.
- Balance is reserved before provider submission.
- `outBillNo` remains stable until the original provider result is known.
- A terminal withdrawal cannot move to another terminal state unless an explicit correction flow is recorded.

**State transitions**:

- Accepted request + balance reserved -> `created`
- Provider returns `WAIT_USER_CONFIRM` -> `awaiting_confirmation`
- Provider returns accepted/processing state or user confirmation has been requested -> `processing`
- Provider final success -> `succeeded`
- Provider final failure/cancel/expiry or local provider submission failure -> `failed` or `canceled`
- Reconciliation cannot safely determine outcome -> `needs_attention`

## Payout Provider Event

Represents each provider request, notification, query, or local mapping event for a withdrawal.

**Attributes**:

- `eventId`
- `withdrawalId`
- `eventType`: `create_request`, `create_response`, `notify`, `query`, `manual_resolution`, or `error`
- `provider`: `wechat_pay` or `manual_test`
- `providerEventId`: notification id, transfer bill number, or query correlation id
- `outBillNo`
- `transferBillNo`
- `providerState`
- `mappedStatus`
- `rawPayloadJson`
- `signatureVerified`: whether provider signature verification succeeded for notifications/responses that include signatures
- `createdAt`

**Validation rules**:

- Duplicate provider notifications and repeated query results are accepted but applied idempotently.
- Raw payload storage must avoid unnecessary exposure in user-facing DTOs.
- Provider events are append-only except for retention or redaction maintenance.

## Reconciliation Run

Represents a maintenance batch for automatic settlement or payout status sync.

**Attributes**:

- `runId`
- `runType`: `commission_settlement` or `withdrawal_reconciliation`
- `startedAt`, `finishedAt`
- `limit`
- `scannedCount`
- `settledCount`
- `canceledCount`
- `succeededCount`
- `failedCount`
- `needsAttentionCount`
- `errorCount`
- `summaryJson`

**Validation rules**:

- A run can be repeated safely.
- Per-record failures do not abort the whole batch unless configuration or storage is unavailable.
- Summary output is suitable for cron logs and admin diagnostics.

## Reconciliation Warning

Represents an unresolved operational issue that needs admin/finance review.

**Attributes**:

- `warningId`
- `withdrawalId`
- `severity`: `info`, `warning`, or `critical`
- `reasonCode`: `stale_processing`, `provider_unknown`, `signature_error`, `amount_mismatch`, `identity_mismatch`, or `manual_review_required`
- `message`
- `status`: `open`, `acknowledged`, or `resolved`
- `createdAt`, `resolvedAt`

**Validation rules**:

- Warnings do not move money by themselves.
- Resolving a warning requires either a provider-confirmed terminal state or an explicit admin exception action.
- Admin views must allow tracing warnings back to the withdrawal and user.
