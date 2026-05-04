# Quickstart: Membership Feature Gating

## Goal

Verify that active members can use LLM configuration, AI Q&A, player AI Q&A, and Pomodoro, while non-members cannot.

## Suggested Verification Flow

1. Start the backend and frontend using the project's normal local development flow.
2. Sign in as a user with no active membership.
3. Open global settings and verify the LLM configuration area is blocked with a member-only explanation and a membership-center action.
4. Open a project AI chat page and verify submitting AI Q&A is blocked before any answer begins.
5. Open a workbench video/player with player AI Q&A available and verify the player AI action is blocked.
6. Open Pomodoro and Pomodoro settings and verify Pomodoro use is blocked with the same member-only explanation.
7. Confirm unrelated project, profile, review, and membership center flows still work for the non-member.
8. Make the same user an active member through an existing successful membership purchase or test entitlement flow.
9. Repeat the protected feature checks and verify all four protected feature categories work normally.
10. Expire or refund the membership through existing membership/admin flows and verify protected features are blocked again on the next attempt.

## Backend Test Targets

- Non-member LLM configuration access is rejected.
- Non-member general/project LLM ask, chat-completion, and stream access is rejected before LLM work starts.
- Active member LLM actions continue to succeed under existing mocked LLM tests.
- Non-member server-backed Pomodoro helpers are rejected.
- Existing membership purchase, refund, and unrelated project tests continue to pass.

## Frontend Test Targets

- LLM settings remain located in global settings but render as member-only for non-members.
- AI chat page and player AI entry points show member-only messaging for non-members.
- Pomodoro page and settings render member-only messaging for non-members.
- Membership center link/action is present in each blocked experience.
