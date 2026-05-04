# Contract: Membership Refund Window

## Scope

This contract describes externally visible behavior for membership refund initiation and refund completion after adding the 1-day refund period.

## Refund Initiation

### Applies To

- Admin membership order refund action.
- Any member-facing refund action that starts a new refund request.
- Any future refund initiation path that operates on paid membership orders.

### Eligible Request

**Given** a membership order is paid  
**And** the order has a valid successful payment time  
**And** the request is made no later than 24 hours after successful payment  
**When** a refund is initiated  
**Then** the existing refund flow proceeds normally.

Expected result:

- Manual/test refunds may complete immediately.
- Provider-backed refunds may enter a refund-in-progress state or complete immediately depending on provider result.
- Existing membership entitlement rollback, coupon restoration, invite reward reversal, and audit behavior are preserved when the refund completes.

### Expired Request

**Given** a membership order is paid  
**And** the request is made later than 24 hours after successful payment  
**When** a refund is initiated  
**Then** the request is rejected before a new refund begins.

Expected result:

- No provider refund request is submitted.
- The membership order remains in its prior state.
- The response explains that the membership refund period has expired.

## In-Flight Refund Completion

### Provider Sync Or Callback After Window

**Given** a membership order is already in a refund-in-progress state  
**And** the 24-hour refund window has passed  
**When** a provider callback or status sync reports refund success, pending, or failure  
**Then** the system continues the existing refund sync behavior instead of rejecting the update as late.

Expected result:

- Success finalizes the refund and applies existing rollback side effects.
- Pending keeps the refund in progress.
- Failure restores or keeps the order as paid according to existing provider-sync behavior.

## Error Messaging

Late new refund attempts must produce a clear user-facing reason equivalent to:

```text
Membership refund period has expired.
```

The exact localization and envelope format should follow the existing application error conventions.

## Boundary Rule

The refund window is valid through the instant exactly 24 hours after successful payment. Requests after that instant are late.
