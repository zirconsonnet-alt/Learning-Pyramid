# Implementation Plan: Live Guide Demos

**Branch**: `002-live-guide-demos` | **Date**: 2026-05-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-live-guide-demos/spec.md`

**Note**: This plan is filled in by the `/speckit-plan` workflow.

## Summary

Add live, controlled product scenes to the existing in-product user guide so key manual steps can show the current UI without static screenshots. The implementation will keep the existing Markdown manual as the narrative source, extend the guide parser with a small directive block for embedded scenes, and render those directives through a local scene registry backed by fixed fixture data.

## Technical Context

**Language/Version**: TypeScript 5.9, React 18, Python test harness
**Primary Dependencies**: Vite 6, React Router 7, KaTeX, lucide-react, existing UI utilities and theme classes
**Storage**: N/A for the feature; guide scenes use in-memory fixture data only
**Testing**: `pnpm -C frontend build`, `pnpm --filter frontend lint` or `pnpm -C frontend lint`, targeted Python static tests for guide content/parser contracts
**Target Platform**: Browser-based in-product guide inside the existing Vite single-page app
**Project Type**: Web application with documentation content stored in repository Markdown
**Performance Goals**: Guide page remains responsive with embedded scenes; scenes do not trigger network or local filesystem access
**Constraints**: No production data, personal data, paid account data, real local file paths, writes, imports, permission prompts, or network requests in guide scenes
**Scale/Scope**: First release covers at least three high-value onboarding or learning workflows from the existing user manual

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution file currently contains template placeholders and no enforceable project-specific gates. Applicable local workflow constraints come from `AGENTS.md`:

- Preserve minimal necessary change scope.
- Keep documentation updated when behavior or usage changes.
- Do not revert unrelated existing worktree changes.
- Add or update validation where the feature changes behavior.
- Report unrun checks explicitly.

**Initial Gate Status**: PASS. The planned feature is additive, scoped to the existing guide/manual surface, and does not require database, deployment, dependency, or public API changes.

## Project Structure

### Documentation (this feature)

```text
specs/002-live-guide-demos/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── guide-demo-block.md
│   └── guide-scene-registry.md
└── tasks.md
```

### Source Code (repository root)

```text
docs/
└── learningpyramid-user-manual.md

frontend/
├── package.json
└── src/
    └── views/
        └── guide/
            ├── GuidePage.tsx
            └── demos/
                ├── GuideDemoFrame.tsx
                ├── guideSceneRegistry.tsx
                ├── guideSceneFixtures.ts
                ├── SubjectProjectGuideDemo.tsx
                ├── ProjectDirectoryGuideDemo.tsx
                └── WorkbenchRecallGuideDemo.tsx

tests/
└── test_frontend_live_guide_demos.py
```

**Structure Decision**: Keep the feature in the existing in-product guide rather than adding a separate documentation app. `GuidePage.tsx` remains the integration point; demo components live under `frontend/src/views/guide/demos/`; the existing manual in `docs/learningpyramid-user-manual.md` receives embedded scene directives for the first guided workflows.

## Phase 0: Research

See [research.md](./research.md).

Resolved decisions:

- Use the existing in-product guide instead of Docusaurus, Nextra, or Storybook for the first release.
- Use a small Markdown directive contract instead of adopting MDX.
- Render scenes via a local registry of controlled React components with fixed fixtures.
- Provide explicit fallback behavior for unknown scene IDs and unsupported states.

## Phase 1: Design And Contracts

See [data-model.md](./data-model.md), [contracts/guide-demo-block.md](./contracts/guide-demo-block.md), [contracts/guide-scene-registry.md](./contracts/guide-scene-registry.md), and [quickstart.md](./quickstart.md).

Primary implementation slices:

- Parser: add a `guideDemo` Markdown block type while preserving all existing block behavior.
- Renderer: render `guideDemo` blocks through a contained demo frame with title, optional caption, highlight, and fallback states.
- Demo library: add at least three controlled scenes for the first-use path.
- Manual update: insert scene directives into the onboarding sections of the existing user manual.
- Validation: add static coverage tests for directive parsing, registry coverage, privacy-safe fixture constraints, and fallback behavior; run frontend build/lint.

## Constitution Check

*Post-design re-check.*

**Post-Design Gate Status**: PASS. The design remains additive and scoped to the guide/manual files. No new dependency, persistence layer, authentication flow, deployment configuration, or backend contract is introduced. Validation is planned for both content contract and frontend build behavior.

## Complexity Tracking

No constitution violations or intentional complexity exceptions.
