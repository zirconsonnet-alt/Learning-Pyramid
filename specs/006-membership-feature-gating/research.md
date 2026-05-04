# Research: Membership Feature Gating

## Decision: Use Active Membership Entitlement As Access Source

**Rationale**: The membership store already derives `isActive` from active entitlement rows and handles expiration, refunds, and entitlement rebuilds. The spec defines membership as current active entitlement, so reusing that source avoids duplicate state and prevents drift from the payment/order lifecycle.

**Alternatives considered**:

- Use any historical paid order: rejected because expired and refunded users must be non-members.
- Add a new role or account flag: rejected because it would duplicate membership state and require extra lifecycle synchronization.

## Decision: Add A Shared Backend Member-Only Access Check

**Rationale**: The protected features include compute-heavy and externally billed LLM calls, so the system must reject non-members before the protected action starts. A shared access check in the adapter/API boundary keeps the rule consistent across profile LLM settings, system/project LLM endpoints, stream endpoints, and server-backed Pomodoro helpers.

**Alternatives considered**:

- Frontend-only gating: rejected because direct requests or saved URLs could bypass it.
- Inline checks in every endpoint: acceptable for tiny scope but more error-prone; a shared helper keeps behavior and error messages aligned.

## Decision: Mirror Backend Gating In Frontend Pages And Actions

**Rationale**: Users should understand why a feature is unavailable before they hit an action error. Frontend gates on LLM configuration, AI chat, player AI chat, and Pomodoro can show the same member-only explanation and a link to membership center while backend enforcement remains authoritative.

**Alternatives considered**:

- Only disable buttons: rejected because direct route access and deep page states would remain confusing.
- Redirect every non-member automatically: rejected because a clear blocker with context is less surprising and can still link to membership center.

## Decision: Treat Player AI Q&A As A Project AI Protected Action

**Rationale**: Player AI Q&A calls the existing project LLM chat-completion path through the course agent. Protecting project LLM chat-completion covers the player AI path and also prevents equivalent direct use of the same protected capability.

**Alternatives considered**:

- Add a separate player-only backend concept: rejected because the existing call path is already project LLM Q&A and does not need a new backend entity.

## Decision: Protect Pomodoro UI And Server-Backed Pomodoro Helpers

**Rationale**: Pomodoro is mostly frontend state, so the primary user gate must be in the Pomodoro pages and settings. Any server-backed Pomodoro feature, such as TTS preview, should also be protected so non-members cannot use associated paid or external services.

**Alternatives considered**:

- Backend-only Pomodoro protection: rejected because most Pomodoro behavior is browser-local and would remain usable.
- Remove or clear non-member Pomodoro state: rejected because the spec only blocks use; it does not require deleting a user's existing timer configuration.

## Decision: Fail Closed When Membership Status Cannot Be Confirmed

**Rationale**: The spec requires protected features to fail closed if membership cannot be loaded. This avoids accidental access during membership-store or network failures while giving users a retry/membership-center path.

**Alternatives considered**:

- Allow access when membership check fails: rejected because it violates the non-member protection requirement.
- Hide all protected feature navigation until status loads: useful as a UX detail, but not enough on its own for action-level enforcement.
