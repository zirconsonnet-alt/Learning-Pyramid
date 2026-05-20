# Research: Mobile Navigation Shell

## Decision 1: Keep setup flow stack-based until a valid project exists

**Decision**: Users without a complete learning context stay in the current signed-in setup flow: subject center first, then project center, then project workspace. The five-destination project shell appears only after a valid subject and scoped project exist.

**Rationale**: The product model requires subject and project context before project learning routes make sense. Showing project tabs to a new user would create repeated empty states and make the app depend on an implicit current project, which violates the scoped identity boundary.

**Alternatives considered**:

- Always show the five tabs after login. Rejected because most destinations would be unavailable for new users and would add context guards as the primary interaction.
- Hide all navigation until onboarding completes. Rejected because subject and project centers are already valid signed-in experiences and should remain reachable.

## Decision 2: Introduce a project shell around existing project workspace

**Decision**: Wrap the existing project route/workbench with a project shell that owns top context display and bottom task navigation.

**Rationale**: Current mobile project route already loads the scoped project workbench and uses `{subjectId, scopedProjectId}`. A wrapper preserves that work while adding mobile navigation hierarchy. It avoids moving workbench behavior into global layout or duplicating project data flow.

**Alternatives considered**:

- Replace the root `Stack` with global tabs. Rejected because iOS/Android navigation still needs stack behavior for subject/project setup and settings routes.
- Move task switching into the workbench screen body only. Rejected because the spec requires project-level navigation, and burying it in the workbench content would make AI, Review, Structure, and Mine feel secondary.

## Decision 3: Use explicit navigation-domain model instead of hidden current project state

**Decision**: Define a small mobile navigation model that derives state from route params and loaded subject/project data: no-context, subject-only, and project-context.

**Rationale**: The existing backend boundary uses public scoped project identity. A hidden global current project would be hard to invalidate when subjects/projects are deleted and would blur deep-link behavior.

**Alternatives considered**:

- Persist a global "last project" and route every tab through it. Rejected because it creates implicit state and makes invalid/deleted contexts harder to reason about.
- Pass only project id and infer subject. Rejected because mobile must preserve the public `{subjectId, scopedProjectId}` relationship.

## Decision 4: Keep object settings with their owner scope

**Decision**: Subject settings are shown only from subject context. Project settings are shown only from project context. Mine contains account and global/system destinations only.

**Rationale**: Subject settings and project settings mutate different objects. Placing them in Mine would force users to infer which object is affected and could produce ambiguous settings screens.

**Alternatives considered**:

- Put every setting under Mine. Rejected because it mixes account, global, subject, and project ownership.
- Put subject settings in the project overflow menu. Rejected as a primary route because project overflow is too low-level for subject-wide changes; it may only appear as a contextual shortcut if the current subject is obvious.

## Decision 5: Use placeholders only as explicit unavailable states for not-yet-implemented destinations

**Decision**: If AI, Structure, Mine subroutes, or project settings are not fully implemented during the first implementation slice, they may render explicit "not yet available in mobile" or empty states scoped to the current project or account.

**Rationale**: The specification is about navigation and information architecture. It should not smuggle in new AI, account, membership, admin, or project settings capabilities. Explicit unavailable states are acceptable when they are the feature's truthful behavior and not a compatibility workaround.

**Alternatives considered**:

- Implement full AI, membership, friends, guide, admin, and project settings features as part of this navigation feature. Rejected because it expands scope across multiple product domains.
- Hide not-yet-implemented destinations from the shell. Rejected for primary project destinations because the shell contract needs stable task navigation; each destination must still be honest about availability.

## Decision 6: No backend or storage changes

**Decision**: Do not add backend endpoints, database fields, client persistence, or deployment configuration.

**Rationale**: Existing subject, material/project, profile/global settings, and project-scoped APIs already support the navigation context. This feature reorganizes mobile reachability and presentation.

**Alternatives considered**:

- Add a backend "current context" profile preference. Rejected because the spec explicitly avoids hidden global current project semantics and no confirmed cross-device current-context behavior exists.
- Add mobile-specific project shell API. Rejected because it would duplicate existing subject/project data and create a mobile protocol branch.
