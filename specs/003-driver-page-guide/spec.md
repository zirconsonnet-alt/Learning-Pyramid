# Feature Specification: Page Walkthrough Guide

**Feature Branch**: `003-driver-page-guide`
**Created**: 2026-05-03
**Status**: Draft
**Input**: User description: "用Driver.js 做页面引导功能，在用户指南里面把方法说明去掉，替换成一个引导按钮，点击引导将开始页面引导，然后引导时用的文案直接用系统使用说明里面的文字"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start guided walkthrough from user guide (Priority: P1)

A learner opens the in-product user guide and starts an interactive page walkthrough from the guide navigation instead of opening the separate method explanation document.

**Why this priority**: The guide should move new users from reading into guided action with one clear entry point, while reducing competing documentation choices inside the user guide.

**Independent Test**: Can be fully tested by opening the user guide, confirming the method explanation is no longer offered as a guide document, clicking the guide action, and verifying that the first walkthrough step appears.

**Acceptance Scenarios**:

1. **Given** a learner opens the user guide, **When** they view the guide navigation, **Then** they see the system usage instructions and a clear start-guidance action instead of a method explanation document entry.
2. **Given** a learner clicks the start-guidance action, **When** the walkthrough begins, **Then** the first step uses wording from the system usage instructions and points the learner toward the first-use path.
3. **Given** the walkthrough is running, **When** the learner completes the highlighted page action, uses fallback manual controls, or closes it, **Then** the page remains usable and the learner can restart guidance from the user guide.

---

### User Story 2 - Keep walkthrough copy aligned with system usage instructions (Priority: P2)

A maintainer updates the system usage instructions and expects the guided walkthrough wording to stay aligned without maintaining a separate rewritten copy of the same guidance.

**Why this priority**: The walkthrough should not create a second source of truth that can drift from the user manual.

**Independent Test**: Can be fully tested by changing a small piece of system usage instruction wording in a controlled review and confirming the corresponding walkthrough step shows the same updated wording.

**Acceptance Scenarios**:

1. **Given** a walkthrough step corresponds to a numbered system usage instruction, **When** the step is displayed, **Then** its visible guidance text comes from that instruction rather than separately authored copy.
2. **Given** a system usage instruction section is renamed or reordered, **When** the walkthrough mapping is reviewed, **Then** missing or stale step mappings are detectable before release.
3. **Given** the system usage instructions include long lists or formatted examples, **When** the walkthrough uses that content, **Then** the displayed step remains readable in a compact guidance overlay.

---

### User Story 3 - Handle unavailable tour targets gracefully (Priority: P3)

A learner may start guidance before creating data, before authorizing local content access, or from a route where a target control is not visible, and still receives useful guidance rather than a broken walkthrough.

**Why this priority**: The tour is mainly for first-time users, so it must tolerate incomplete setup states.

**Independent Test**: Can be fully tested by starting the walkthrough in a fresh account or empty project state and confirming each unavailable target either routes the learner to the right place, shows a clear fallback instruction, or skips safely.

**Acceptance Scenarios**:

1. **Given** a walkthrough target is not visible on the current page, **When** the step is reached, **Then** the learner sees clear guidance for how to reach that target or the step is skipped with an understandable explanation.
2. **Given** the learner closes the walkthrough mid-step, **When** they continue using the app, **Then** no page interaction remains blocked by the closed walkthrough.
3. **Given** a learner opens an old guide link that previously selected the method explanation, **When** the user guide loads, **Then** it resolves to a valid guide state instead of a blank or broken document.

### Edge Cases

- A bookmarked user guide URL still references the removed method explanation document.
- A walkthrough step points to a control that is hidden because the learner has not created a subject, selected a project, authorized a directory, or imported content yet.
- A learner starts the walkthrough on a narrow screen where highlighted controls or guidance text could crowd the page.
- The system usage instructions contain long numbered lists, code examples, or formatted text that is too large for a single overlay step.
- The learner refreshes, changes route, or closes the walkthrough before completing all steps.
- A manual section used by the walkthrough is deleted, renamed, or no longer describes a visible page area.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The user guide MUST no longer offer the method explanation as a selectable in-guide document.
- **FR-002**: The user guide MUST present a clear start-guidance action in the place where the method explanation entry was previously offered.
- **FR-003**: Users MUST be able to start the page walkthrough by activating the start-guidance action from the user guide.
- **FR-004**: The walkthrough MUST cover the primary first-use path described by the system usage instructions.
- **FR-005**: Each walkthrough step MUST use user-facing wording sourced from the corresponding system usage instruction content rather than independently rewritten guidance text.
- **FR-006**: The walkthrough MUST identify which system usage instruction section or step each walkthrough step is based on.
- **FR-007**: Actionable walkthrough steps MUST advance from the learner completing the highlighted page action; fallback or non-action steps MAY expose manual advance/back controls, and users MUST be able to close and restart the walkthrough without reloading the application.
- **FR-008**: The walkthrough MUST highlight or otherwise anchor guidance to the relevant visible page area or control when that target is available.
- **FR-009**: When a target page area or control is unavailable, the walkthrough MUST show a clear fallback, navigation hint, or safe skip behavior.
- **FR-010**: Existing system usage instruction reading behavior MUST remain available in the user guide.
- **FR-011**: Existing embedded live guide scenes in the system usage instructions MUST continue to render while the reading view is open.
- **FR-012**: Legacy links or query states that previously selected the method explanation MUST resolve to a valid user guide state.
- **FR-013**: The walkthrough MUST avoid showing private learner data, real local file paths, paid account data, or content from a learner's personal project as part of guided copy or examples.
- **FR-014**: The walkthrough MUST remain readable and operable across common desktop and mobile widths.

### Key Entities *(include if feature involves data)*

- **Guide Start Action**: The user-facing control in the user guide that starts the page walkthrough.
- **Walkthrough Step**: A single guided instruction with a source instruction reference, display text, target page area, and fallback behavior.
- **Instruction Source Reference**: The link between a walkthrough step and the system usage instruction section or numbered item that supplies its text.
- **Target Anchor**: The visible page area or control the walkthrough should highlight when available.
- **Unavailable Target Fallback**: The message or safe behavior shown when a target anchor cannot be displayed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time learner can start the guided walkthrough from the user guide with one click after opening the guide.
- **SC-002**: 100% of walkthrough steps have an identifiable source in the system usage instructions during release review.
- **SC-003**: At least 90% of the primary first-use path steps either highlight a visible target or provide a clear fallback instruction.
- **SC-004**: Users can close the walkthrough at any step and resume normal page interaction without refreshing the app.
- **SC-005**: The user guide renders successfully for legacy method-document links by resolving to a valid guide state.
- **SC-006**: The walkthrough remains readable on common desktop and mobile widths during manual review.

## Assumptions

- "系统使用说明" refers to the existing in-product guide document currently labeled "系统使用说明".
- "方法说明" should be removed from the in-product user guide navigation and content selection, but this does not require deleting the repository source document unless a later implementation task explicitly chooses to do so.
- The first walkthrough focuses on the same first-use path already described in the system usage instructions: creating a subject/project, binding and importing a content directory, using the workbench, entering recall points, and completing review.
- If a full manual section is too long for one overlay, the walkthrough may split that section into smaller steps as long as the displayed wording still comes from the source instruction text.
- The walkthrough should be available to anyone who can open the user guide and should not require real project data to display useful guidance.
