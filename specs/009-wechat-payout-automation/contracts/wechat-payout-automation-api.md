# Contract: WeChat Payout Automation API

All JSON endpoints continue using the existing response envelope:

```json
{ "ok": true, "data": {} }
```

Business-rule rejections continue using the existing error envelope with `PRECONDITION` where appropriate. Production user withdrawal requests no longer accept `wechatOpenId`.

## User Commission Summary

### `GET /api/commissions/me`

Adds payout readiness to the existing commission response.

```json
{
  "account": {
    "userId": "user_inviter",
    "pendingCent": 500,
    "withdrawableCent": 1000,
    "reservedCent": 0,
    "paidOutCent": 500,
    "canceledCent": 0,
    "updatedAt": "2026-05-06T10:00:00+00:00"
  },
  "payoutReadiness": {
    "provider": "wechat_pay",
    "status": "ready",
    "identityId": "wpid_xxx",
    "maskedLabel": "oABC123***",
    "verifiedAt": "2026-05-06T09:00:00+00:00",
    "nextAction": "withdraw"
  },
  "recentCommissions": []
}
```

Readiness statuses:

- `unbound`: user must bind WeChat before withdrawal
- `binding`: binding attempt is in progress
- `ready`: active identity exists
- `invalid`: latest identity cannot be used
- `provider_unavailable`: payout channel is not configured or temporarily unavailable

## WeChat Receiving Identity

### `GET /api/commissions/payout-identity`

Returns the current user's payout identity status.

```json
{
  "provider": "wechat_pay",
  "status": "ready",
  "identityId": "wpid_xxx",
  "maskedLabel": "oABC123***",
  "verifiedAt": "2026-05-06T09:00:00+00:00",
    "latestBindingAttempt": {
    "bindingAttemptId": "wpbind_xxx",
    "status": "bound",
    "channel": "desktop_qr_official_account_h5",
    "createdAt": "2026-05-06T08:59:00+00:00",
    "completedAt": "2026-05-06T09:00:00+00:00",
    "failureReason": ""
  }
}
```

### `POST /api/commissions/payout-identity/wechat/binding-attempts`

Starts a binding attempt and returns the provider-specific next step.

Request:

```json
{
  "channel": "desktop_qr_official_account_h5",
  "returnUrl": "https://example.com/membership"
}
```

Response:

```json
{
  "bindingAttemptId": "wpbind_xxx",
  "provider": "wechat_pay",
  "channel": "desktop_qr_official_account_h5",
  "status": "created",
  "mobileBindingUrl": "https://example.com/api/commissions/payout-identity/wechat/mobile-bind?attempt=wpbind_xxx&state=state_xxx",
  "qrCodePayload": "https://example.com/api/commissions/payout-identity/wechat/mobile-bind?attempt=wpbind_xxx&state=state_xxx",
  "pollAfterMs": 2000,
  "expiresAt": "2026-05-06T09:10:00+00:00"
}
```

Business rules:

- The returned state/attempt belongs to the logged-in user.
- The desktop web client renders `qrCodePayload` as the binding QR code.
- The QR code opens a mobile WeChat binding page and does not transfer money.
- A new attempt does not revoke the current active identity until completion succeeds.
- Expired, canceled, reused, or invalid attempts cannot activate an identity.

### `GET /api/commissions/payout-identity/wechat/binding-attempts/{bindingAttemptId}`

Polls a desktop QR binding attempt owned by the current user.

Response while waiting:

```json
{
  "bindingAttemptId": "wpbind_xxx",
  "provider": "wechat_pay",
  "channel": "desktop_qr_official_account_h5",
  "status": "scanned",
  "maskedLabel": "",
  "expiresAt": "2026-05-06T09:10:00+00:00",
  "failureReason": "",
  "nextAction": "wait_for_mobile_confirmation"
}
```

Response after success:

```json
{
  "bindingAttemptId": "wpbind_xxx",
  "provider": "wechat_pay",
  "channel": "desktop_qr_official_account_h5",
  "status": "bound",
  "identityId": "wpid_xxx",
  "maskedLabel": "oABC123***",
  "verifiedAt": "2026-05-06T09:00:00+00:00",
  "nextAction": "withdraw"
}
```

Business rules:

- Reject polling for attempts that belong to another logged-in user.
- Return an expired status when the QR has passed expiry without binding.
- Return only masked identity labels.

### `GET /api/commissions/payout-identity/wechat/mobile-bind?attempt=...&state=...`

Mobile WeChat entrypoint opened by the desktop QR code. It validates that the attempt is still usable, marks it scanned, and presents or redirects into the WeChat authorization/confirmation flow.

Business rules:

- Reject missing, expired, canceled, reused, or invalid attempts.
- Show the LearningPyramid account being bound before the user confirms.
- Do not activate a receiving identity until authorization and explicit mobile confirmation complete.

### `POST /api/commissions/payout-identity/wechat/bind`

Completes binding from the mobile WeChat confirmation page with a provider authorization code or mini-program login code. The raw OpenID is resolved server-side and is never supplied by the user.

Request:

```json
{
  "bindingAttemptId": "wpbind_xxx",
  "authorizationCode": "wechat_code_xxx",
  "state": "state_xxx",
  "confirmedLearningPyramidUserId": "user_inviter"
}
```

Response:

```json
{
  "identityId": "wpid_xxx",
  "provider": "wechat_pay",
  "status": "active",
  "maskedLabel": "oABC123***",
  "verifiedAt": "2026-05-06T09:00:00+00:00"
}
```

Business rules:

- Reject when the attempt is missing, expired, already consumed, or belongs to another user.
- Reject when state validation fails.
- Reject when the mobile confirmation does not match the LearningPyramid account that created the desktop QR attempt.
- Replace any previous active identity only after this binding succeeds.

## Withdrawal Request

### `POST /api/commissions/withdrawals`

Request:

```json
{
  "amountCent": 500
}
```

Response when WeChat requires user confirmation:

```json
{
  "withdrawalId": "mwd_xxx",
  "userId": "user_inviter",
  "amountCent": 500,
  "targetType": "wechat_pay",
  "identityId": "wpid_xxx",
  "identityMaskedLabel": "oABC123***",
  "status": "awaiting_confirmation",
  "outBillNo": "LPWD202605060001",
  "transferBillNo": "1330000071100999991182020050700019480001",
  "confirmation": {
    "mode": "wechat_jsapi_requestMerchantTransfer",
    "mchId": "1900000001",
    "appId": "wx123",
    "packageInfo": "affffddafdfafddffda=="
  },
  "createdAt": "2026-05-06T11:00:00+00:00",
  "submittedAt": "2026-05-06T11:00:01+00:00",
  "completedAt": null,
  "failureReason": ""
}
```

Response when the provider accepts without immediate confirmation package:

```json
{
  "withdrawalId": "mwd_xxx",
  "status": "processing",
  "confirmation": null
}
```

Business rules:

- Reject if the user has no active WeChat receiving identity.
- Reject if `amountCent` exceeds withdrawable balance or configured limits.
- Reserve local balance before provider submission.
- Use a stable merchant bill number for the withdrawal.
- If provider submission fails with an unknown result, keep the original bill number and reconcile before retrying with a new one.

### `GET /api/commissions/withdrawals?limit=20`

Returns current user's withdrawal records, newest first.

```json
[
  {
    "withdrawalId": "mwd_xxx",
    "amountCent": 500,
    "targetType": "wechat_pay",
    "identityMaskedLabel": "oABC123***",
    "status": "succeeded",
    "outBillNo": "LPWD202605060001",
    "transferBillNo": "1330000071100999991182020050700019480001",
    "failureReason": "",
    "createdAt": "2026-05-06T11:00:00+00:00",
    "submittedAt": "2026-05-06T11:00:01+00:00",
    "completedAt": "2026-05-06T11:02:00+00:00"
  }
]
```

## WeChat Transfer Notification

### `POST /api/payments/wechat/transfer-notify`

Public HTTPS endpoint used by WeChat Pay merchant transfer notification. The backend verifies the WeChat signature, decrypts the encrypted resource, maps provider status, and applies local state idempotently.

Response body:

```text
success
```

Business rules:

- Duplicate notifications must return success after confirming the local record is already processed.
- Terminal provider success moves reserved balance to paid out exactly once.
- Terminal provider failure/cancel returns reserved balance to withdrawable exactly once.
- Amount, AppID, merchant id, and merchant bill number must match local expectations before money state changes.

## Admin Settlement And Payout Operations

### `POST /api/admin/membership/commissions/settle`

Existing endpoint remains available as an idempotent manual trigger, but unattended operation should use the maintenance script/scheduler.

Response:

```json
{
  "runId": "run_xxx",
  "settledCount": 3,
  "canceledCount": 1,
  "skippedCount": 12,
  "errorCount": 0
}
```

### `GET /api/admin/membership/payout-identities?status=active|invalid|all&search=...&limit=50`

Returns masked payout readiness records for support and finance.

### `GET /api/admin/membership/withdrawals?status=awaiting_confirmation|processing|succeeded|failed|needs_attention|all&search=...&limit=50`

Extends the existing admin withdrawal list with identity, merchant bill, transfer bill, provider state, and warning fields.

### `POST /api/admin/membership/withdrawals/{withdrawalId}/sync`

Forces a provider query for one withdrawal and applies the result idempotently.

Response:

```json
{
  "withdrawalId": "mwd_xxx",
  "previousStatus": "processing",
  "currentStatus": "succeeded",
  "providerState": "SUCCESS",
  "action": "marked_succeeded"
}
```

### `POST /api/admin/membership/withdrawals/{withdrawalId}/resolve`

Manual exception action remains available only for records that cannot be resolved automatically.

Request:

```json
{
  "status": "succeeded",
  "providerTransferNo": "1330000071100999991182020050700019480001",
  "failureReason": ""
}
```

Business rules:

- Requires admin privileges.
- Records an admin action log.
- Cannot override an already-terminal provider-confirmed state without an explicit correction path.

## Maintenance Script Contracts

### `tools/settle_membership_commissions.py`

Suggested CLI:

```powershell
python tools/settle_membership_commissions.py --limit 200 --indent 2
```

Summary shape:

```json
{
  "runType": "commission_settlement",
  "startedAt": "2026-05-06T12:00:00+00:00",
  "finishedAt": "2026-05-06T12:00:01+00:00",
  "scannedCount": 20,
  "settledCount": 18,
  "canceledCount": 2,
  "skippedCount": 0,
  "errorCount": 0
}
```

### `tools/reconcile_commission_withdrawals.py`

Suggested CLI:

```powershell
python tools/reconcile_commission_withdrawals.py --min-age-minutes 2 --limit 100 --indent 2
```

Summary shape:

```json
{
  "runType": "withdrawal_reconciliation",
  "provider": "wechat_pay",
  "startedAt": "2026-05-06T12:00:00+00:00",
  "finishedAt": "2026-05-06T12:00:02+00:00",
  "scannedCount": 10,
  "succeededCount": 7,
  "failedCount": 1,
  "pendingCount": 1,
  "needsAttentionCount": 1,
  "errorCount": 0
}
```
