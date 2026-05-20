# Implementation Plan: Mobile Navigation Shell

**Branch**: `017-mobile-navigation-shell` | **Date**: 2026-05-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/017-mobile-navigation-shell/spec.md`

**Note**: This plan is produced by the `/speckit-plan` workflow and stops before task generation or implementation.

## Summary

Add a scoped mobile navigation shell for LearningPyramid's existing Expo mobile app. The implementation will preserve the current signed-in setup flow for users without a complete learning context, introduce a project shell only when a valid subject and scoped project exist, keep subject/project context visible in that shell, expose exactly five project-level task destinations, and keep subject settings, project settings, account routes, and global/system routes in their correct ownership scopes.

The technical approach is local to `mobile/`: define a small navigation-domain model, add shell UI components that wrap the existing workbench, route project tabs through existing scoped project parameters, provide empty/unavailable screens for destinations not yet implemented, and update mobile tests plus mobile documentation. No backend protocol, database, deployment, or Web/Tauri component reuse is planned.

## Technical Context

**Language/Version**: TypeScript 5.9.2 with React 19.2.0 and React Native 0.83.6  
**Primary Dependencies**: Expo 55, Expo Router, React Navigation bottom tabs, TanStack Query, existing mobile API client and authentication provider  
**Storage**: N/A for this feature; navigation derives from route params and already-loaded subject/project data, with no new persisted client state  
**Testing**: `jest-expo`, `@testing-library/react-native`, `pnpm --dir mobile test`, `pnpm --dir mobile typecheck`  
**Target Platform**: Android and iPhone Expo-managed React Native app  
**Project Type**: Mobile app feature inside the existing `mobile/` client  
**Performance Goals**: Project shell must not add extra blocking network requests beyond the minimum data needed to identify current subject/project; tab changes should preserve already-mounted project context where practical  
**Constraints**: Preserve scoped project identity; do not introduce mobile-only backend protocol; do not rely on a hidden global current project; keep UI concise and avoid decorative containers; keep Web/Tauri frontend boundaries separate  
**Scale/Scope**: Mobile navigation and information architecture for the existing signed-in app, covering no-context setup, subject/project context controls, five project task destinations, and Mine account/system routing

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The repository constitution file still contains placeholders and does not define enforceable gates. This plan therefore applies the active project rules from `AGENTS.md` and the current mobile client boundary documents:

- **Clean architecture boundary**: PASS. Scope is limited to `mobile/` navigation and docs; no backend, database, protocol, deployment, or Web/Tauri component changes.
- **No fallback/shim/legacy path**: PASS. The plan uses explicit route/context requirements and empty states instead of compatibility branches or hidden globals.
- **No unconfirmed product expansion**: PASS. AI, membership, friends, guide, admin, and project settings can be reachable placeholders or existing routes only where confirmed; new feature behavior for those destinations is out of scope.
- **Scoped identity preservation**: PASS. All project destinations continue to require `{subjectId, scopedProjectId}` and must not persist or infer internal project ids.
- **UI restraint**: PASS. Shell elements are limited to top context, bottom task navigation, concise empty states, and existing screens.
- **Documentation sync**: PASS. Implementation phase must update `docs/current-change.md` and `docs/mobile-client.md` with the final behavior.

Post-design re-check: PASS. The Phase 0/1 design artifacts keep the same boundaries and introduce no gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/017-mobile-navigation-shell/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── mobile-navigation-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
mobile/
├── src/
│   ├── app/
│   │   ├── _layout.tsx
│   │   ├── index.tsx
│   │   ├── project/[subjectId]/[scopedProjectId].tsx
│   │   ├── subject/[subjectId].tsx
│   │   └── subject/[subjectId]/settings.tsx
│   ├── components/
│   │   ├── AppButton.tsx
│   │   ├── EmptyState.tsx
│   │   └── Screen.tsx
│   ├── navigation/
│   │   ├── mobileNavigation.ts
│   │   ├── ProjectShell.tsx
│   │   └── ContextMenu.tsx
│   ├── screens/
│   │   ├── MobileWorkbenchScreen.tsx
│   │   ├── SubjectsScreen.tsx
│   │   ├── SubjectMaterialsScreen.tsx
│   │   ├── SubjectSettingsScreen.tsx
│   │   ├── ProjectSettingsScreen.tsx
│   │   ├── MineScreen.tsx
│   │   └── ProjectDestinationPlaceholderScreen.tsx
│   └── routing/
│       └── params.ts
├── __tests__/
│   ├── mobile-navigation-shell.test.tsx
│   ├── learning-navigation.test.tsx
│   ├── project-route-workbench.test.tsx
│   └── root-layout.test.tsx
└── package.json

docs/
├── current-change.md
└── mobile-client.md
```

**Structure Decision**: Use the existing `mobile/` Expo-managed app. Add a narrow `mobile/src/navigation/` layer for navigation-domain decisions and shell components, then keep user-facing screens under `mobile/src/screens/`. Do not create shared packages, backend endpoints, or Web/Tauri dependencies for this feature.

## Complexity Tracking

No constitution or project-rule violations are introduced, so no complexity exceptions are needed.
