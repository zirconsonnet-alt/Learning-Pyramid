# Quickstart: Page Walkthrough Guide

## Implement The Guide Entry

1. Remove the method document import and document definition from `frontend/src/views/guide/GuidePage.tsx`.
2. Keep the system usage instructions as the default readable guide document.
3. Add a start-guidance action in the guide sidebar where the method document entry used to compete for attention.
4. Treat legacy `?doc=method` as the default guide state.

## Build The Walkthrough Controller

1. Add `driver.js` to `frontend/package.json` and `frontend/pnpm-lock.yaml`.
2. Import `driver.js/dist/driver.css` once from the walkthrough controller or a shell-level module.
3. Mount the controller from `frontend/src/shell/AppShell.tsx` so it can survive route changes after starting from `/guide`.
4. Expose a small start API that `GuidePage.tsx` can call.
5. Destroy the Driver.js instance on close and on component cleanup.

## Keep Copy Sourced From The Manual

1. Use `docs/learningpyramid-user-manual.md` as the only source of step wording.
2. Define each step with a `sourceRef` that points to a manual heading and optional numbered item.
3. Resolve popover title and description from the source reference at runtime or build-time.
4. Trim only for overlay readability; do not rewrite the instruction in a separate tour string.
5. Add validation that every step source reference resolves.

## Add Stable Targets

Use `data-guide-tour` anchors for tour targets. First-release anchors:

- `new-subject-button`
- `create-subject-submit`
- `subject-project-entry`
- `project-settings-nav`
- `authorize-directory-button`
- `import-directory-button`
- `workbench-nav`
- `learning-object-tree`
- `add-recall-point-button`
- `submit-learning-button`
- `review-pane`

## Validate

Run:

```powershell
python -m pytest tests/test_frontend_driver_page_guide.py
pnpm -C frontend build
pnpm -C frontend lint
```

Manual review:

1. Open `/guide`.
2. Confirm the method explanation document is gone.
3. Click the start-guidance action.
4. Move forward and backward through the walkthrough.
5. Close the walkthrough and confirm the page is usable without refresh.
6. Open `/guide?doc=method` and confirm it resolves to a valid guide state.
7. Repeat at desktop and narrow widths.

## Release Review

- Confirm each walkthrough step has a valid manual source reference.
- Confirm each visible target highlights the intended page area.
- Confirm missing-target fallbacks are understandable in a fresh or empty account state.
- Confirm no step shows private learner data, real local paths, paid account data, or personal project content.

## Local Review Notes

- 2026-05-03: Verified `/guide`, `/guide?doc=method`, and the walkthrough start action at 1366x768 and 390x844 using the Vite dev server plus a local mock API for read-only system/project endpoints. The method document entry stayed hidden, legacy `?doc=method` resolved back to the manual, `开始引导` routed to `/projects`, the first Driver.js popover used the manual item text, and closing the popover removed the overlay without console errors.
