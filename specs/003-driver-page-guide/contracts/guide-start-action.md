# Contract: Guide Start Action

## Purpose

Define the user-guide sidebar behavior after replacing the method explanation entry with a walkthrough start action.

## Required Behavior

- The guide document list contains the system usage instructions as the readable guide document.
- The guide document list does not contain a selectable method explanation document.
- The sidebar presents a button-like action labeled for starting guidance.
- Activating the action starts the walkthrough from the beginning.
- `?doc=manual`, no `doc` query, and legacy `?doc=method` all resolve to a valid guide state.
- The official community and feedback block remains available.

## Acceptance Checks

- Static validation confirms `GuidePage.tsx` no longer imports `docs/plm-method-guide.md?raw`.
- Static validation confirms no `slug: "method"` guide document remains.
- Static validation confirms a start-guidance action calls the walkthrough start API.
- Manual browser review confirms the start action is visible in the guide sidebar on desktop and mobile widths.

## Out Of Scope

- Deleting `docs/plm-method-guide.md` from the repository.
- Moving the user manual to a new documentation system.
- Persisting tour progress between browser reloads.
