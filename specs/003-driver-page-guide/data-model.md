# Data Model: Page Walkthrough Guide

## Guide Start Action

Represents the control displayed in the user guide sidebar to start the walkthrough.

**Fields**:

- `label`: visible button text, expected to communicate starting the guide.
- `placement`: guide sidebar area where the removed method document entry previously appeared.
- `enabled`: whether the action can start a walkthrough in the current browser.

**Validation Rules**:

- Must be visible when the user guide is open.
- Must not coexist with a selectable method explanation document entry.
- Must start a walkthrough without requiring existing project data.

## Walkthrough Step

Represents one product-tour step.

**Fields**:

- `id`: stable kebab-case identifier.
- `sourceRef`: reference to a system usage instruction heading and optional numbered item.
- `routeHint`: preferred route or route pattern for the target.
- `targetAnchor`: optional stable target anchor.
- `fallback`: unavailable-target fallback behavior.
- `popoverSide`: preferred display side when the target exists.

**Validation Rules**:

- `id` must be unique.
- `sourceRef` must resolve to existing system usage instruction content.
- Steps with `targetAnchor` must either have a matching frontend anchor or an explicit fallback.
- Display text must be derived from `sourceRef`.
- Steps must not contain private data or real local paths.

## Instruction Source Reference

Represents the link between a step and manual content.

**Fields**:

- `heading`: exact or normalized manual section title.
- `itemIndex`: optional 1-based numbered-list item index inside the section.
- `extractMode`: `heading`, `item`, `paragraph`, or `summary-from-items`.

**Validation Rules**:

- `heading` must resolve to a section in `docs/learningpyramid-user-manual.md`.
- If `itemIndex` is set, that numbered item must exist in the referenced section.
- Generated copy should preserve the source wording, with only trimming allowed for overlay readability.

## Target Anchor

Represents a page element that can be highlighted by the walkthrough.

**Fields**:

- `name`: value used by `data-guide-tour`.
- `routePattern`: route pattern where the anchor is expected.
- `requiredState`: optional UI state required for the anchor to be visible.

**Validation Rules**:

- Names must be stable kebab-case tokens.
- Anchor attributes must be placed on meaningful interactive controls or section containers.
- Anchors must not depend on generated IDs or display-only CSS selectors.

## Unavailable Target Fallback

Represents the behavior when a target anchor cannot be highlighted.

**Fields**:

- `mode`: `centered-popover`, `route-hint`, or `skip-with-explanation`.
- `sourceRef`: manual wording used for fallback copy.
- `nextAction`: optional route or instruction for the learner.

**Validation Rules**:

- Every missing-target case must leave the page interactive after close.
- Fallback copy must be derived from the system usage instructions.
- Fallbacks must not ask for destructive actions or require permission prompts during the walkthrough.

## Walkthrough Session

Represents in-memory tour runtime state.

**Fields**:

- `status`: `idle`, `running`, or `closed`.
- `activeStepId`: current step identifier when running.
- `startedFromGuide`: whether the session began from the user guide.

**State Transitions**:

- `idle -> running`: user activates the guide start action.
- `running -> running`: user advances, goes back, target refreshes, or route changes.
- `running -> closed`: user closes the walkthrough.
- `closed -> running`: user restarts from the guide.
- `closed -> idle`: controller cleanup completes.
