# Implementation Plan: Page Walkthrough Guide

**Branch**: `003-driver-page-guide` | **Date**: 2026-05-03 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-driver-page-guide/spec.md`

**Note**: This plan is filled in by the `/speckit-plan` workflow.

## Summary

Replace the secondary "方法说明" document entry in the in-product user guide with a "开始引导" action that launches an interactive product walkthrough. The walkthrough will be implemented in the existing React single-page app using Driver.js, will keep the system usage manual as the source of guide copy, and will rely on stable frontend tour anchors plus fallback steps when a target route or control is unavailable.

## Technical Context

**Language/Version**: TypeScript 5.9, React 18, Python test harness  
**Primary Dependencies**: Vite 6, React Router 7, lucide-react, existing UI utilities and theme classes, Driver.js for overlay/product-tour behavior  
**Storage**: N/A for persistent storage; walkthrough runtime state is in-memory and resets on page reload  
**Testing**: `python -m pytest tests/test_frontend_driver_page_guide.py`, `pnpm -C frontend build`, `pnpm -C frontend lint`, manual browser review of `/guide` walkthrough  
**Target Platform**: Browser-based in-product guide inside the existing Vite single-page app  
**Project Type**: Web application frontend feature with documentation content stored in repository Markdown  
**Performance Goals**: User guide remains responsive; walkthrough starts within one click and does not block normal page use after closing  
**Constraints**: No private learner data, paid account data, real local file paths, writes, imports, permission prompts, or network requests are performed by guide steps; guide copy must come from the system usage instructions rather than separate rewritten tour text  
**Scale/Scope**: First release covers the primary first-use path from subject creation through review readiness using the current system usage manual sections

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution file currently contains template placeholders and no enforceable project-specific gates. Applicable local workflow constraints come from `AGENTS.md`:

- Preserve minimal necessary change scope.
- Keep documentation updated when behavior or usage changes.
- Do not revert unrelated existing worktree changes.
- Add or update validation where the feature changes behavior.
- Report unrun checks explicitly.

**Initial Gate Status**: PASS. The feature is frontend-scoped and guide-scoped. It introduces one frontend dependency and touches existing guide/navigation surfaces, but does not require database, backend, deployment, authentication, or public API changes.

## Project Structure

### Documentation (this feature)

```text
specs/003-driver-page-guide/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── guide-start-action.md
│   └── walkthrough-step-map.md
└── tasks.md
```

### Source Code (repository root)

```text
docs/
└── learningpyramid-user-manual.md

frontend/
├── package.json
├── pnpm-lock.yaml
└── src/
    ├── shell/
    │   └── AppShell.tsx
    ├── ui/
    │   └── guideWalkthrough/
    │       ├── guideWalkthroughCopy.ts
    │       ├── guideWalkthroughController.ts
    │       └── guideWalkthroughSteps.ts
    └── views/
        ├── guide/
        │   └── GuidePage.tsx
        ├── projects/
        │   └── ProjectsPage.tsx
        ├── subjects/
        │   └── SubjectDashboardPage.tsx
        ├── settings/
        │   └── ProjectSettingsPage.tsx
        └── workbench/
            ├── WorkbenchPage.tsx
            └── components/
                ├── ComposePane.tsx
                ├── LearningObjectTree.tsx
                └── VideoPane.tsx

tests/
└── test_frontend_driver_page_guide.py
```

**Structure Decision**: Keep the walkthrough in the existing frontend application. `GuidePage.tsx` owns the visible guide start action and removal of the method document entry. A small `frontend/src/ui/guideWalkthrough/` module owns source-copy extraction, step definitions, and Driver.js lifecycle so the tour can survive route changes through `AppShell.tsx`. Target pages receive stable `data-guide-tour` anchors only where needed for the walkthrough.

## Phase 0: Research

See [research.md](./research.md).

Resolved decisions:

- Use Driver.js as requested for the product-tour overlay and controls.
- Keep the manual Markdown file as the single source of walkthrough copy.
- Add stable `data-guide-tour` target anchors rather than relying on translated button text or layout-specific selectors.
- Keep walkthrough runtime state client-only and in-memory.
- Provide centered fallback popovers or navigation hints when a target is unavailable.

## Phase 1: Design And Contracts

See [data-model.md](./data-model.md), [contracts/guide-start-action.md](./contracts/guide-start-action.md), [contracts/walkthrough-step-map.md](./contracts/walkthrough-step-map.md), and [quickstart.md](./quickstart.md).

Primary implementation slices:

- Guide entry: remove the method document from guide navigation and render a start-guidance button in the same sidebar area.
- Dependency and controller: add Driver.js, import its CSS once, and run the walkthrough from a persistent shell-level controller.
- Copy source: parse or reference `docs/learningpyramid-user-manual.md` so each step's title/description is derived from a manual section or numbered instruction.
- Target anchors: add stable tour anchors to the subject creation, project creation, project settings, directory import, workbench object tree/video, recall form, and review areas.
- Fallbacks: handle legacy `?doc=method`, missing project data, missing route context, and unavailable target elements without leaving the walkthrough stuck.
- Validation: add static tests for dependency/configuration, guide document removal, source-copy references, target anchor coverage, action-driven advancement, fallback coverage, and manual alignment; run frontend build/lint and manual browser review.

## Constitution Check

*Post-design re-check.*

**Post-Design Gate Status**: PASS. The design remains scoped to the frontend guide experience. The new dependency is justified by the explicit product-tour requirement and verified against official docs. No backend contract, database, auth, or deployment changes are introduced. Validation is planned for both source-copy contracts and frontend build behavior.

## Complexity Tracking

No constitution violations or intentional complexity exceptions.
