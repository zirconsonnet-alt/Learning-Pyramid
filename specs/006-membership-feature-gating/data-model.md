# Data Model: Membership Feature Gating

## Membership Entitlement

Represents whether a signed-in user currently has active membership access.

**Existing attributes used by this feature**:

- `userId`: user whose access is being evaluated
- `currentStatus`: `active`, `expired`, or `never_purchased`
- `currentStartsAt`: active or latest entitlement start time when available
- `currentEndsAt`: active or latest entitlement end time when available
- `isActive`: true only when the current entitlement is active

**Validation rules**:

- Access is allowed only when `isActive` is true.
- Users with `never_purchased`, `expired`, pending-order-only, closed-order-only, or refunded-order-only states are non-members.
- Entitlement changes from purchase, renewal, expiration, refund, or revocation must be reflected on the next protected feature attempt.

## Protected Feature

Represents a product capability that requires active membership.

**Values**:

- `llm_configuration`: LLM configuration viewing and updates
- `ai_qa`: AI Q&A from project/system chat entry points
- `player_ai_qa`: AI Q&A launched from the media/player experience
- `pomodoro`: Pomodoro page, settings, quick-start, schedule, and server-backed Pomodoro helpers

**Validation rules**:

- Each protected feature must have a visible frontend gate for non-members.
- Each protected feature that performs backend work must have backend enforcement before protected work begins.
- Protected feature list is closed for this feature; unrelated learning flows remain ungated.

## Access Decision

Represents the result of evaluating a user's current membership against a protected feature.

**Attributes**:

- `allowed`: boolean
- `feature`: protected feature being evaluated
- `reason`: human-readable reason when blocked
- `membershipPath`: path or destination for opening membership center when blocked

**State transitions**:

- `blocked` -> `allowed`: user gains active membership through successful purchase or renewal.
- `allowed` -> `blocked`: membership expires, is refunded, or entitlement is revoked.
- `blocked` remains `blocked`: membership status cannot be confirmed.

**Validation rules**:

- Blocked decisions must not start compute-heavy, billable, or state-changing protected work.
- Blocked decisions must be understandable to users and offer a path to membership center.
