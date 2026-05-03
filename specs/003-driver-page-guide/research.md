# Research: Page Walkthrough Guide

## Decision: Use Driver.js for the page walkthrough overlay

**Rationale**: The feature request explicitly asks for Driver.js. Official Driver.js documentation shows the package can be installed with `pnpm install driver.js`, imported as `driver` from `driver.js`, and initialized with a `steps` array for product tours. Its API supports `drive`, step movement, `refresh`, `setSteps`, `isActive`, and `destroy`, which covers start, next/previous, route refresh, restart, and cleanup needs.

**Alternatives considered**:

- Build a custom overlay: rejected because it would reimplement product-tour behavior, focus handling, popover positioning, and cleanup.
- React-only tour libraries: rejected because the user named Driver.js and the current app can use a vanilla DOM-targeted library through a thin React controller.

**References**:

- https://driverjs.com/docs/installation
- https://driverjs.com/docs/basic-usage
- https://driverjs.com/docs/configuration
- https://driverjs.com/docs/api

## Decision: Store walkthrough state in a persistent shell-level controller

**Rationale**: The guide button lives in `GuidePage.tsx`, while many target controls live on `/projects`, `/subjects/:id`, `/p/:projectId/settings`, and `/p/:projectId/workbench`. A controller mounted under `AppShell.tsx` can keep Driver.js lifecycle state alive across route transitions and can destroy the tour cleanly when the user closes it.

**Alternatives considered**:

- Keep all walkthrough logic inside `GuidePage.tsx`: rejected because the component unmounts when navigating away from `/guide`.
- Store progress persistently: rejected for the first release because the requirements only need start, close, restart, and safe fallback behavior within the current session.

## Decision: Use manual-derived copy instead of separate tour prose

**Rationale**: FR-005 requires each step to use wording sourced from the system usage instructions. The current user manual is already imported as raw Markdown, and the live-guide feature already parses guide content. A source-reference contract can map each tour step to a manual heading and numbered item, then derive the popover title and description from those source blocks.

**Alternatives considered**:

- Duplicate the manual text into the tour step array: rejected because it creates a second source of truth.
- Use the live guide demo captions as tour copy: rejected because those captions summarize scenes and do not cover every target step.

## Decision: Add explicit `data-guide-tour` anchors to target controls

**Rationale**: Stable data attributes make tour targeting robust against Chinese text changes, icon changes, layout rearrangement, and visual styling changes. Static tests can verify that every step target has a matching anchor.

**Alternatives considered**:

- Target by visible text: rejected because text is also the content source and can change as the manual changes.
- Target by generated CSS class names or nested layout selectors: rejected because the UI uses utility classes that are not a durable semantic contract.

## Decision: Use centered fallback steps and navigation hints for unavailable targets

**Rationale**: First-time users may have no subject, no project, no directory authorization, or no imported content. Driver.js supports steps without a target element, which can show guidance even when no anchor is present. The implementation should route to the best known page when possible, then show a fallback popover if the exact target remains unavailable.

**Alternatives considered**:

- Require users to prepare sample data before starting the tour: rejected because the tour is intended for first use.
- Silently skip missing targets: rejected because missing targets are often the moment when users most need guidance.
