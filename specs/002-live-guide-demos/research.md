# Research: Live Guide Demos

## Decision: Build inside the existing product guide

**Rationale**: The product already has an in-product guide page that renders repository Markdown. Keeping the first release inside that page gives users contextual help without adding a second documentation site, routing model, deployment target, or authoring workflow.

**Alternatives considered**:

- **External documentation site**: Better for public SEO and versioned docs, but heavier than the immediate need.
- **Storybook or Ladle as the primary guide**: Good for component review, but it would turn user documentation into a separate tool rather than a product guide.
- **Static screenshots**: Easiest to author initially, but fails the maintenance goal when UI changes.

## Decision: Use a Markdown directive instead of MDX

**Rationale**: The current guide source is plain Markdown and is imported as raw text. A small directive such as `:::guide-demo scene="..." state="..."` keeps the manual readable in plain Markdown, avoids a new MDX compilation pipeline, and gives the parser a stable content contract.

**Alternatives considered**:

- **MDX imports**: Powerful but requires a larger content pipeline change.
- **HTML comments or custom tags**: Less visible to authors and easier to mistype without obvious intent.
- **Image-like Markdown syntax**: Familiar, but overloaded and less able to carry state/highlight metadata clearly.

## Decision: Use a local scene registry

**Rationale**: A registry maps stable scene identifiers to controlled scene components, supported states, and fallback metadata. This makes unknown scenes detectable, keeps guide content decoupled from component imports, and lets maintainers add scenes without editing the guide renderer every time.

**Alternatives considered**:

- **Direct component imports from content**: Not available in plain Markdown and couples content to implementation files.
- **Route-level iframes**: More complex and likely to depend on app state, auth, or router setup.
- **Render full product pages**: Too fragile because production pages may depend on live data, permissions, and side effects.

## Decision: Use fixed fixture data with no side effects

**Rationale**: Guide scenes must render for users with no project, no local directory permission, and no private data. Fixed fixtures keep scenes stable, reviewable, privacy-safe, and independent of live application state.

**Alternatives considered**:

- **Real API data**: Can leak user data and makes the guide dependent on account state.
- **Mock API layer**: Useful later for complex flows, but unnecessary for the first release if scenes remain controlled and presentational.
- **Production page state snapshots**: Fragile and hard to maintain as flows evolve.

## Decision: Validate by content contract and frontend build checks

**Rationale**: The first release changes guide parsing/rendering and manual content, so validation should confirm that directive syntax is valid, every referenced scene/state exists, privacy-sensitive values are absent from fixtures, and the frontend still builds.

**Alternatives considered**:

- **Full visual regression suite immediately**: Valuable later, but heavier than needed for the first release.
- **Manual review only**: Necessary for copy/scene alignment, but insufficient for contract drift.
