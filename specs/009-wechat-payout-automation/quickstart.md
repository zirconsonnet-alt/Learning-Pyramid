# Quickstart: WeChat Payout Automation

## Preconditions

- The invite commission behavior from `specs/008-invite-commission` is present: 20 yuan membership price, 7.5-discount invite coupon, 15 yuan paid threshold, fixed 5 yuan commission, and 24-hour refund window.
- WeChat Pay merchant transfer capability is enabled for the merchant account in the intended payout scene.
- Production/staging has public HTTPS URLs for payment, refund, merchant transfer notifications, and mobile WeChat binding entrypoints.
- WeChat Pay credentials and public key/certificate configuration are available.
- A WeChat application identity that can support the authorization flow for payout OpenID resolution is available and associated with the payout merchant context.
- At least two users exist: an inviter and an invitee.
- Local verification can use `manual_test` for deterministic ledger behavior, while production withdrawal readiness requires a real bound WeChat receiving identity.

## 1. Verify Unbound Users Cannot Withdraw

1. Sign in as an inviter with at least 5 yuan withdrawable commission.
2. Ensure the inviter has no active WeChat receiving identity.
3. Open the commission withdrawal area.
4. Try to submit a withdrawal.

Expected result: the UI prompts the user to bind WeChat first, the API rejects withdrawal before funds are reserved, and the withdrawable balance remains unchanged.

## 2. Verify WeChat Receiving Identity Binding

1. Sign in on the desktop web app as an inviter without a bound WeChat receiving identity.
2. Start the WeChat binding flow from the commission withdrawal area.
3. Confirm that the desktop page displays a QR code and an expiry notice.
4. Scan the QR code with the user's own mobile WeChat.
5. On the mobile WeChat binding page, confirm that the page identifies the LearningPyramid account being bound.
6. Complete WeChat authorization and confirm the binding.
7. Return to the desktop membership or invite page, or wait for desktop polling to update.

Expected result: payout readiness becomes `ready`, a masked WeChat identity label is displayed, no full OpenID is shown in the browser, and the user did not enter UID/OpenID manually.

## 3. Verify Expired Or Reused Binding QR Is Safe

1. Start a desktop QR binding attempt.
2. Let the QR code pass its expiry time, or complete one binding and then try to open the same QR link again.
3. Check the desktop binding status and mobile binding page.

Expected result: the attempt is shown as expired or invalid, no receiving identity is activated or replaced, and the desktop page offers a fresh retry.

## 4. Verify Automatic Settlement After Refund Window

1. Create an invited membership order that pays at least 15 yuan.
2. Confirm a 5 yuan commission record exists in `pending`.
3. Move test time past the 24-hour refund window or use a fixture that creates an eligible pending record.
4. Run:

```powershell
python tools/settle_membership_commissions.py --limit 200
```

5. Open the inviter's commission summary.

Expected result: the pending commission becomes settled, withdrawable balance increases by exactly 5 yuan, and re-running the script does not change the balance again.

## 5. Verify Refund Blocks Automatic Settlement

1. Create a qualifying invited membership payment.
2. Start a refund or mark refund-in-progress inside the 24-hour refund window.
3. Move time past the refund window.
4. Run the settlement script.

Expected result: the commission is canceled or kept non-withdrawable, and withdrawable balance does not increase.

## 6. Verify Withdrawal Request And User Confirmation

1. Ensure the inviter has an active WeChat receiving identity and at least 5 yuan withdrawable commission.
2. Submit a 5 yuan withdrawal.
3. If the response contains WeChat confirmation data, invoke `requestMerchantTransfer` in the supported WeChat client.
4. Return to the app and check withdrawal history.

Expected result: the withdrawal enters `awaiting_confirmation` or `processing`, the requested amount moves from withdrawable to reserved, and the UI does not show the withdrawal as succeeded until provider final state is received.

## 7. Verify Transfer Notification Success

1. Submit a withdrawal in staging with a real WeChat transfer result, or use a signed/decrypted test fixture in automated tests.
2. Deliver a terminal success transfer notification to `/api/payments/wechat/transfer-notify`.
3. Repeat the same notification.

Expected result: the withdrawal becomes `succeeded`, reserved balance moves to paid out exactly once, duplicate notification returns success without a second balance change.

## 8. Verify Transfer Failure Recovery

1. Submit a withdrawal that receives a provider failure, cancellation, or expiry result.
2. Deliver the notification or use provider query reconciliation.
3. Check the user's commission summary and withdrawal history.

Expected result: the withdrawal becomes `failed` or `canceled`, reserved balance returns to withdrawable exactly once, and the failure reason is visible.

## 9. Verify Query Reconciliation

1. Create a withdrawal that remains `awaiting_confirmation` or `processing`.
2. Do not deliver a notification.
3. Run:

```powershell
python tools/reconcile_commission_withdrawals.py --min-age-minutes 2 --limit 100
```

4. Check the withdrawal status.

Expected result: the script queries WeChat by merchant bill number, applies terminal states when known, keeps non-terminal records pending, and flags unresolved stale records for admin attention when needed.

## 10. Verify Admin Audit

1. Open admin membership pages.
2. Review payout identities, commission records, withdrawal records, provider events, and reconciliation warnings.
3. Search by inviter, invitee, source order, withdrawal id, or merchant bill number.

Expected result: admins can trace every commission balance change and withdrawal status change to the source order, receiving identity, provider bill, notification/query event, and any manual exception action.

## 11. Suggested Deployment Schedule

For unattended operation, run both scripts from the deployment scheduler:

```text
*/5 * * * * python tools/settle_membership_commissions.py --limit 200
*/5 * * * * python tools/reconcile_commission_withdrawals.py --min-age-minutes 2 --limit 100
```

Expected result: valid commission becomes withdrawable shortly after the refund window, and provider transfer results are synchronized without admin action.

## Regression Checks

- Existing invite discount coupon behavior remains unchanged.
- Existing 20 yuan membership price and 15 yuan discounted payable amount remain unchanged.
- Existing fixed 5 yuan commission amount remains unchanged.
- Existing payment and refund notifications still pass signature/decryption checks.
- Existing admin manual settlement endpoint remains idempotent.
- Current manual admin withdrawal resolution remains available for exception records only.
- Binding QR expiry, cancellation, and reuse never create or replace a receiving identity.
- Re-running settlement, notification handling, or reconciliation never double-changes balances.

## Implementation Validation Notes

- Automated coverage exercises desktop QR binding attempts, expiry/reuse rejection, manual-test identity binding, settlement, withdrawal reservation, merchant transfer response/query mapping, duplicate provider events, and admin audit DTOs.
- Live WeChat OAuth and merchant transfer confirmation still require staging merchant credentials, a configured transfer scene, and public HTTPS callback URLs before production launch.
