# Data Model: Live Guide Demos

## Guide Document

Represents a user-facing manual page that contains ordinary instructional content and optional embedded live scene references.

**Fields**:

- `slug`: Stable document selector, such as `manual` or `method`.
- `label`: Display name in the guide navigation.
- `sourcePath`: Human-readable source label for maintainers.
- `blocks`: Ordered parsed content blocks.

**Validation Rules**:

- Existing heading, paragraph, list, rule, math, and code blocks remain valid.
- Guide demo blocks may appear only as standalone block-level content.
- A document can render even when it contains zero guide demo blocks.

## Markdown Block

Represents one parsed block in a guide document.

**Variants**:

- `heading`
- `paragraph`
- `list`
- `rule`
- `math`
- `code`
- `guideDemo`

**Validation Rules**:

- Existing block variants preserve their current behavior.
- `guideDemo` must include a scene identifier and state.
- Unknown `guideDemo` values render a fallback block rather than stopping the page.

## Guide Demo Block

Represents one embedded live scene request from the manual content.

**Fields**:

- `scene`: Stable scene identifier.
- `state`: Explicit example state for that scene.
- `highlight`: Optional guide-relevant visual target.
- `title`: Optional reader-facing scene title.
- `caption`: Optional reader-facing explanation.

**Relationships**:

- Resolves to one `Guide Scene Definition`.
- Selects one supported `Example State`.
- May activate one `Guide Highlight`.

**Validation Rules**:

- `scene` and `state` are required.
- `scene`, `state`, and `highlight` values use stable lowercase token names.
- `title` and `caption` are plain display text and must not contain private user data.

## Guide Scene Definition

Represents a controlled scene that the guide can render.

**Fields**:

- `scene`: Stable identifier.
- `label`: Maintainer-readable name.
- `description`: Purpose of the scene.
- `states`: Supported example states.
- `highlights`: Supported optional highlight targets.
- `render`: Scene renderer that receives the selected state and highlight.

**Relationships**:

- Owns one or more `Example State` values.
- Uses fixed fixture data.
- Returns a rendered guide scene or a scene-level fallback.

**Validation Rules**:

- Every referenced scene identifier in the manual exists in the registry.
- Every referenced state is listed for the target scene.
- Renderers do not perform writes, permission prompts, imports, purchases, or network requests.

## Example State

Represents a fixed product condition shown in the guide.

**Fields**:

- `state`: Stable state identifier.
- `description`: What the state demonstrates.
- `fixtureData`: Controlled sample content needed by the scene.

**Validation Rules**:

- Fixture data must be deterministic.
- Fixture data must not include real personal data, paid account data, private learning content, or real local file paths.
- Error and empty states must be renderable without depending on external failures.

## Scene Fallback

Represents the reader-facing output when a scene request cannot be resolved.

**Fields**:

- `reason`: Unknown scene, unsupported state, unsupported highlight, or render failure.
- `message`: Concise reader-facing explanation.
- `scene`: Original requested scene identifier.
- `state`: Original requested state.

**Validation Rules**:

- Fallback messages do not expose stack traces or implementation details.
- The surrounding guide page remains usable after a fallback.

## State Transitions

Guide scenes are presentational. They do not model live user state transitions. A user may scroll between scenes that represent different workflow states, but each state is independently selected by the guide document.
