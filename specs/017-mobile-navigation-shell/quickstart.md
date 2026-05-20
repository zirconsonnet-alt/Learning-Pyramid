# Quickstart: Mobile Navigation Shell

This quickstart is for the implementation phase after `/speckit-tasks`.

## Preconditions

- Current feature pointer: `.specify/feature.json` -> `specs/017-mobile-navigation-shell`
- Current branch: `017-mobile-navigation-shell`
- Mobile dependencies installed:

```powershell
pnpm --dir mobile install
```

## Read First

1. `specs/017-mobile-navigation-shell/spec.md`
2. `specs/017-mobile-navigation-shell/plan.md`
3. `specs/017-mobile-navigation-shell/contracts/mobile-navigation-contract.md`
4. `docs/mobile-client.md`
5. `docs/current-change.md`

## Implementation Boundaries

- Do not add backend endpoints, database fields, deployment settings, or mobile-only auth protocol.
- Do not introduce a hidden global current project.
- Do not reuse React DOM Web/Tauri components from `frontend/`.
- Do not move scoped project identity away from `{subjectId, scopedProjectId}`.
- Do not place subject settings or project settings as primary Mine entries.
- Do update `docs/current-change.md` when code changes begin.
- Do update `docs/mobile-client.md` when behavior is implemented.

## Expected Implementation Slices

1. Add navigation-domain helpers for context status, destination requirements, and guard decisions.
2. Add tests for no-subject, subject-only, and project-context navigation behavior.
3. Add project shell UI around the existing project workbench.
4. Add concise project-scoped placeholder or empty destinations for AI, Review, Structure, and Mine where full features are out of scope.
5. Add top context control with scoped settings visibility rules.
6. Add Mine account/system grouping without subject/project settings.
7. Update mobile documentation and current change note.

## Validation Commands

```powershell
pnpm --dir mobile test
pnpm --dir mobile typecheck
```

If a device or emulator is available, run a manual smoke check:

```powershell
pnpm --dir mobile start
```

Smoke paths:

- Sign in with no subjects: verify subject setup and no project shell tabs.
- Create/select subject with no projects: verify project setup and subject settings availability.
- Create/select project: verify top context and five project shell destinations.
- Open context menu in each state: verify scoped settings visibility.
- Open Mine: verify account/system items and absence of subject/project settings as primary entries.
