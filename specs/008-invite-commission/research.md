# Research: Invite Discount And Commission

## Decision: Replace New Inviter Coupon Rewards With Invitee Discount Coupons

**Rationale**: The requested change explicitly moves value from "inviter receives a 5 yuan coupon" to "invitee receives a 7.5-discount coupon after binding an invite code." Keeping this behavior at invite binding time gives the invited user immediate motivation to buy membership and preserves existing registration-time and manual invite binding flows.

**Alternatives considered**:

- Grant the 7.5-discount coupon only after registration but not manual binding: rejected because the existing product supports pre-first-order manual binding and the spec keeps that entry point.
- Grant the discount only at checkout without creating a coupon record: rejected because current UI and admin flows already expose coupons, and a coupon record gives users and admins a clear audit trail.
- Continue also issuing the inviter 5 yuan coupon: rejected because the feature is a mechanism replacement, not an additive promotion.

## Decision: Use 20 Yuan As The New Monthly Base Price And Remove The Old First-Order Price As The Primary Discount

**Rationale**: The current code uses a 19.9 yuan base price and a 14.9 yuan first-order price. The new feature says "会员初始价格改成20元" and pairs a 7.5-discount coupon with a 15 yuan commission threshold. A 20 yuan base price with a 7.5-discount coupon naturally produces a 15 yuan paid order and keeps the threshold testable.

**Alternatives considered**:

- Keep 19.9 yuan base price and round the discount: rejected because it would produce awkward payable amounts and conflict with the explicit 20 yuan price.
- Keep a separate automatic first-order discount: rejected for this feature because it would stack unpredictably with the new invite discount and make the 15 yuan threshold ambiguous.
- Make 20 yuan apply only to invited users: rejected because the wording says membership initial price changes, and price previews/orders should be consistent.

## Decision: Model 7.5 Discount As A Percentage Coupon With Order-Time Cent Snapshot

**Rationale**: Existing coupons are cash amount coupons. The new coupon is a percentage discount, so it needs a distinguishable coupon type or equivalent fields while preserving the final `couponDiscountCent` snapshot on membership orders. Snapshotting the actual discount in cents avoids future price changes altering historical orders.

**Alternatives considered**:

- Store the coupon as a fixed 5 yuan discount for the current 20 yuan price: rejected because it would misrepresent the requested 7.5-discount coupon and would break if membership price changes.
- Replace all coupons with percentage-only coupons: rejected because admin-granted and historical cash coupons should remain readable and usable according to their own semantics.
- Store only display text and calculate from the title: rejected because pricing rules must be explicit and testable.

## Decision: Create Pending Commission On Qualifying Payment, Settle After Refund Window

**Rationale**: Commission depends on a successful invited-user payment reaching 15 yuan and surviving the refund period. Creating a pending record at payment confirmation captures the source order and refund deadline early, while delaying withdrawable balance movement until the existing 24-hour refund window has passed.

**Alternatives considered**:

- Settle immediately on payment and reverse later if refunded: rejected because it can create withdrawable funds before refund risk ends.
- Create records only when a scheduled settlement scan runs: rejected because missing pending state makes admin support and user expectation tracking weaker.
- Evaluate threshold on list price: rejected because the user specified "付费达到15元", which is actual payment, not list price.

## Decision: Fixed 5 Yuan Commission Per Qualifying Order

**Rationale**: The user selected `Q1: A`, so each qualifying invited membership order settles a fixed 5 yuan commission. Fixed amount is simple to explain, easy to reconcile, and close to the old 5 yuan reward mental model while changing the reward from coupon to cash commission.

**Alternatives considered**:

- 20% of paid amount: rejected by user selection and would pay 3 yuan on a 15 yuan discounted order.
- Fixed 3 yuan: rejected by user selection and would reduce invite incentive.
- Tiered commission: rejected for this iteration because no tier rules were requested.

## Decision: Keep Commission Accounting Separate From Coupon Reward History

**Rationale**: Existing tables and DTOs are built around invite bindings, coupons, and `invite_reward_records`. Commission introduces cash balance states, settlement deadlines, withdrawal reservations, provider transfer status, and payout reconciliation. A dedicated ledger/account model makes these invariants explicit and lets old 5 yuan coupon records remain visible without being migrated into cash balances.

**Alternatives considered**:

- Reuse `invite_reward_records` for commission: rejected because its columns and semantics are coupon-specific.
- Add balance columns directly to user profiles: rejected because ledger-level traceability is required for support, audit, and idempotency.
- Store only withdrawal totals: rejected because pending, canceled, reserved, and paid-out transitions must be explainable.

## Decision: Use WeChat Pay Transfer/Payout Adapter With Local Reservation

**Rationale**: Withdrawals to WeChat Pay are external money movement and must not be represented as an immediate local balance change only. The local system should validate ownership/eligibility, reserve funds, create an idempotent withdrawal request, submit through the WeChat payout capability configured for the merchant, and reconcile provider success or failure.

**Alternatives considered**:

- Mark withdrawals successful locally without provider confirmation: rejected because money may not have moved.
- Require manual admin payout only: rejected because the feature asks users to withdraw to their own WeChat Pay.
- Directly reuse membership refund APIs for payout: rejected because refund and merchant-to-user payout have different provider semantics and reconciliation requirements.
