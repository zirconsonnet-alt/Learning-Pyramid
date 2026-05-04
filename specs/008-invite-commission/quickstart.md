# Quickstart: Invite Discount And Commission

## Preconditions

- Hosted auth and membership flows are enabled in the same way as current membership tests.
- WeChat membership payment configuration is available for real payout verification, or `manual_test` is enabled for local non-provider flow checks.
- At least two users exist: an inviter and an invitee.
- The invitee has no previous successful membership order.

## 1. Verify Invitee Discount Coupon

1. Sign in as the inviter and copy their invite code.
2. Register or sign in as a new invitee.
3. Bind the inviter's invite code during registration or through the membership invite binding entry.
4. Open the invitee's coupons.
5. Confirm exactly one available "邀请码 7.5 折券" appears.
6. Confirm the inviter did not receive a new "邀请奖励 5 元券".

Expected result: the reward value is now on the invitee as a 7.5-discount coupon.

## 2. Verify 20 Yuan Pricing And 15 Yuan Payable Amount

1. As the invitee, open membership purchase.
2. Confirm base monthly price is 20 yuan.
3. Select the 7.5-discount coupon.
4. Confirm price preview shows:
   - list amount: 20 yuan
   - coupon discount: 5 yuan
   - payable amount: 15 yuan
5. Create the order and confirm the order snapshot matches the preview.

Expected result: applying the invite discount coupon to a 20 yuan order makes the payable amount exactly 15 yuan.

## 3. Verify Pending Commission Before Refund Window Ends

1. Complete payment for the invitee order.
2. Open the inviter's commission summary.
3. Confirm a 5 yuan commission record exists in pending state.
4. Confirm inviter withdrawable balance has not increased yet.

Expected result: commission exists but is not withdrawable during the 24-hour refund window.

## 4. Verify Refund Blocks Commission

1. Create another invited order that pays at least 15 yuan.
2. Start refund inside the 24-hour refund window.
3. Run or wait for commission settlement evaluation.
4. Check inviter commission summary.

Expected result: the pending commission is canceled or remains non-withdrawable, and no 5 yuan is added to withdrawable balance.

## 5. Verify Settlement After Refund Window

1. Create an invited order with actual paid amount at least 15 yuan.
2. Do not refund it.
3. Move time past the 24-hour refund window in test, or wait in a staging environment.
4. Run commission settlement evaluation.
5. Open inviter commission summary.

Expected result: the commission record moves to settled and inviter withdrawable balance increases by 5 yuan exactly once.

## 6. Verify Withdrawal To WeChat Pay

1. Ensure inviter has at least 5 yuan withdrawable commission.
2. Ensure inviter has a valid user-owned WeChat Pay receiving identity.
3. Submit a 5 yuan withdrawal.
4. Confirm 5 yuan moves from withdrawable to reserved/processing.
5. Simulate or receive provider success.
6. Confirm 5 yuan moves from reserved to paid-out and withdrawal status becomes succeeded.

Expected result: local balances match provider payout status.

## 7. Verify Withdrawal Failure Recovery

1. Ensure inviter has at least 5 yuan withdrawable commission.
2. Submit a withdrawal using a provider failure test path.
3. Confirm amount is reserved while processing.
4. Simulate or receive provider failure.
5. Confirm amount returns to withdrawable balance and withdrawal status shows failed with a reason.

Expected result: failed payout does not lose user balance.

## 8. Verify Admin Audit

1. Open admin membership overview.
2. Confirm invite bindings, invite discount coupons, commission records, and withdrawals can be listed.
3. Search by inviter, invitee, and source order.
4. Confirm each commission can be traced to inviter, invitee, order, paid amount, refund-window deadline, and status.
5. Confirm each withdrawal can be traced to user, amount, target, provider transfer number, status, and failure reason.

Expected result: support and finance can explain every reward and payout.

## Regression Checks

- Existing old "邀请奖励 5 元券" records remain visible in coupon/admin history.
- Existing membership refund-window tests still pass.
- Non-invited membership orders use the new 20 yuan base price and do not create commission.
- Re-running settlement does not double-settle commission.
- Repeating a provider withdrawal callback or sync result does not double-change balances.
