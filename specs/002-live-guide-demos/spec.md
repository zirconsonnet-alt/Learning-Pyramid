# Feature Specification: Live Guide Demos

**Feature Branch**: `002-live-guide-demos`
**Created**: 2026-05-03
**Status**: Draft
**Input**: User description: "Choose方案 A: build an in-product Live Guide that embeds controlled, live product scenes into the existing user manual instead of maintaining static screenshots."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Learn core flows with live product scenes (Priority: P1)

A new learner opens the in-product user guide and follows the main onboarding path with embedded product scenes that show the relevant interface state beside the instructions.

**Why this priority**: The current guide explains the flow in text, but users still need to mentally map the instructions to the interface. Live scenes reduce confusion without requiring manually maintained screenshots.

**Independent Test**: Can be fully tested by opening the user guide, reading the first-use flow, and verifying that each key step has a matching rendered product scene that explains what the user should look for.

**Acceptance Scenarios**:

1. **Given** the user is reading the guide section for creating a subject or project, **When** they reach a step that references a visible interface area, **Then** the guide shows a stable live scene for that interface state.
2. **Given** the guide describes a project setup step, **When** the step depends on a selected state or highlighted action, **Then** the scene clearly emphasizes the relevant area without requiring a static screenshot.
3. **Given** a guide page contains both normal text and live scenes, **When** the user scrolls through the page, **Then** the content remains readable and the scenes fit the guide layout on common desktop and mobile widths.

---

### User Story 2 - Maintain guide scenes as the product evolves (Priority: P2)

A product maintainer updates a visible product workflow and can update the guide by adjusting reusable guide scenes and their fixed example states instead of replacing image files.

**Why this priority**: The feature is valuable only if it lowers long-term guide maintenance as the interface changes.

**Independent Test**: Can be fully tested by changing a product label or scene state in a controlled environment and verifying that the guide scene reflects the current product presentation without updating an image asset.

**Acceptance Scenarios**:

1. **Given** a guide scene is reused by multiple guide sections, **When** its displayed product state is adjusted, **Then** all guide locations using that scene show the updated state consistently.
2. **Given** a guide scene uses fixed example data, **When** the guide is opened without a real learner project or local files, **Then** the scene still renders predictably.
3. **Given** a guide scene is unavailable or misconfigured, **When** the guide is rendered, **Then** the user sees a clear fallback in the guide rather than a broken page.

---

### User Story 3 - Review guide coverage before release (Priority: P3)

A release reviewer can check whether the live guide scenes still match the written instructions before publishing a new version.

**Why this priority**: Live scenes stay visually current, but written instructions can still become stale. Review support helps catch mismatches.

**Independent Test**: Can be fully tested by reviewing the guide with representative scenes and confirming that each embedded scene has an identifiable purpose, state, and related guide step.

**Acceptance Scenarios**:

1. **Given** a reviewer opens the guide, **When** they inspect a guide scene, **Then** they can identify which guide step the scene supports.
2. **Given** written copy names an action or label, **When** the associated scene is displayed, **Then** the reviewer can verify whether the wording still matches the visible interface.
3. **Given** a guide scene represents an error or empty state, **When** the reviewer checks it, **Then** the expected state is visible without needing real user data.

### Edge Cases

- The guide references an unknown scene identifier.
- A scene state is valid but contains long labels or dense content that could overflow the guide layout.
- A scene is useful on desktop but too crowded on narrow screens.
- A written instruction names a visible control that has been renamed in the product.
- A guide scene requires example data that is incomplete or inconsistent.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow user guide content to include embedded live product scenes at specific points in the guide.
- **FR-002**: The system MUST preserve normal guide reading behavior for existing text, headings, lists, code examples, and mathematical content.
- **FR-003**: Each embedded scene MUST be selectable by a stable scene identifier and an explicit example state.
- **FR-004**: Each embedded scene MUST use fixed example data so that it does not depend on a real learner account, project, permission grant, local file, or network request.
- **FR-005**: Each embedded scene MUST be able to emphasize the guide-relevant area or action when the guide step needs visual focus.
- **FR-006**: The guide MUST provide a clear fallback when a scene identifier or scene state cannot be resolved.
- **FR-007**: The guide MUST keep embedded scenes visually contained within the reading layout across common desktop and mobile widths.
- **FR-008**: The first release of this feature MUST cover at least three high-value onboarding or learning workflows from the existing user manual.
- **FR-009**: Maintainers MUST be able to add a new guide scene without editing unrelated guide sections.
- **FR-010**: The guide MUST support review of scene coverage by making each embedded scene's purpose and state traceable from the guide content.
- **FR-011**: The feature MUST avoid showing real personal data, paid account data, private learning content, or real local file paths in guide scenes.
- **FR-012**: Existing guide links and navigation behavior MUST continue to work for readers who do not interact with embedded scenes.

### Key Entities *(include if feature involves data)*

- **Guide Document**: A user-facing manual page that contains instructional text and references to embedded product scenes.
- **Guide Scene**: A rendered product example associated with a stable identifier, a purpose, and one or more example states.
- **Example State**: A named, fixed product condition such as empty project, setup prompt, validation error, imported content, or recall point editing.
- **Guide Highlight**: A visual emphasis on the part of a scene that matters for the current instruction.
- **Scene Fallback**: A reader-friendly message shown when a referenced scene or state cannot be displayed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time user can complete the documented first-use path from subject creation through first recall point submission with guide support in under 20 minutes during a guided usability check.
- **SC-002**: At least 80% of the existing user manual's top onboarding steps that refer to visible interface locations are supported by a live scene in the first release.
- **SC-003**: A maintainer can update a displayed guide scene after a visible interface wording change in under 10 minutes without replacing image assets.
- **SC-004**: The guide renders successfully for a reader with no existing project, no local directory permission, and no authenticated private data.
- **SC-005**: During release review, 100% of embedded scenes either render their intended state or show an intentional fallback.

## Assumptions

- The first version focuses on the existing in-product guide rather than a separate public documentation site.
- The existing Markdown user manual remains the source of guide narrative for the first version.
- Guide scenes are illustrative and controlled; they do not perform real writes, imports, purchases, or permission grants.
- The first scene set prioritizes onboarding and core learning workflows: creating a subject/project, binding a local content directory, importing content, using the workbench, and entering recall points.
- Public marketing documentation, search engine indexing, and versioned external docs are outside the first version.
