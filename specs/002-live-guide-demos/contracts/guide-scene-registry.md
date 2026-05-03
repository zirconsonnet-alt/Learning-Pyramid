# Contract: Guide Scene Registry

## Purpose

Provide a single registry that maps Markdown scene references to controlled guide scene renderers.

## Registry Entry

Each scene entry provides:

- `scene`: Stable identifier used by guide Markdown.
- `label`: Maintainer-readable name.
- `description`: What workflow step the scene supports.
- `states`: Supported state identifiers.
- `highlights`: Supported highlight identifiers.
- `render`: Renderer for the selected state and optional highlight.

## Resolution Behavior

Given a guide demo block:

1. Look up the `scene` identifier.
2. Verify that the requested `state` is supported.
3. Verify that the optional `highlight` is supported.
4. Render the scene with fixed fixture data.
5. Return a fallback block if the scene or state cannot be resolved.

## Required First-Release Scene Coverage

The first release must include at least three of the following high-value workflows:

- Subject and project creation.
- Project settings local content directory binding.
- Content directory import result.
- Workbench object tree and video selection.
- Recall point entry and submission.

## Registry Validation Rules

- Every scene identifier referenced by the manual exists in the registry.
- Every referenced state exists for its scene.
- Every referenced highlight exists for its scene or is explicitly allowed to degrade.
- Registry fixtures are deterministic and privacy-safe.
- Scene renderers are presentational and do not perform real side effects.

## Fallback Contract

Fallback output includes:

- Requested scene identifier.
- Requested state.
- Short reader-facing message that the guide scene is temporarily unavailable.
- Optional maintainer hint in non-disruptive text.

Fallback output excludes:

- Stack traces.
- Private runtime data.
- Internal-only file paths beyond guide source references useful to maintainers.
