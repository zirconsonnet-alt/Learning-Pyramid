# Contract: Member-Only Feature Access

This contract describes expected behavior for protected feature access. It does not prescribe internal implementation.

## Protected Features

The following feature categories require active membership:

- LLM configuration
- AI Q&A
- Player AI Q&A
- Pomodoro

## Access Outcomes

### Active Member

**Given** the signed-in user has active membership  
**When** they use any protected feature  
**Then** the feature behaves as it did before membership gating and does not add extra limits.

### Non-Member

**Given** the signed-in user has no active membership  
**When** they use any protected feature  
**Then** the system blocks the feature, explains that active membership is required, and provides a path to the membership center.

### Unknown Membership State

**Given** the signed-in user's membership state cannot be confirmed  
**When** they use any protected feature  
**Then** the system blocks the protected action and shows a retry or membership-center path.

## Backend Behavior

Backend protected actions must reject non-members before starting protected work. This includes:

- LLM settings reads and writes that expose or update member-only configuration
- General LLM ask actions
- Project LLM ask actions
- Project LLM chat-completion actions used by player AI Q&A
- Project LLM streaming actions
- Server-backed Pomodoro helpers such as TTS preview

Expected blocked response characteristics:

- Indicates a forbidden/precondition-style failure.
- Includes a stable machine-readable code or category that the frontend can recognize.
- Includes a human-readable message equivalent to "This feature requires active membership."
- Does not include secret LLM configuration values or partial AI output.

## Frontend Behavior

Frontend protected surfaces must:

- Check membership status before enabling protected interaction.
- Show a consistent member-only message for non-members.
- Offer a membership-center action reachable in no more than two user actions.
- Keep unrelated non-protected navigation and learning workflows available.

Protected surfaces include:

- Global settings LLM configuration area
- Project AI chat page
- Player AI chat controls inside the workbench video/player area
- Pomodoro page and Pomodoro settings page

## Regression Expectations

- Non-members can still open project dashboards, learning material views, normal workbench views that do not invoke player AI, review recommendations, profile, and membership center.
- Active members can use the protected features with the same visible behavior as before.
- Membership lifecycle changes are reflected on the next protected feature attempt.
