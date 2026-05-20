# Contract: Mobile Navigation Shell

This contract describes observable mobile navigation behavior for implementation and tests. It is not a backend API contract.

## Scope Requirements

| Destination | Required Context | Primary Owner | Expected Missing-Context Behavior |
|-------------|------------------|---------------|-----------------------------------|
| Subject center | Signed-in user | Subject/global setup | Available without subject or project |
| Subject settings | Subject | Subject | Hidden or unavailable when no subject exists |
| Project center | Subject | Subject | Guide to subject creation/selection when no subject exists |
| Project shell | Project | Project | Guide to subject or project selection when context is missing |
| Learning | Project | Project | Guide to subject/project selection when context is missing |
| AI | Project | Project | Guide to subject/project selection when context is missing; show project-scoped unavailable state if not implemented |
| Review | Project | Project | Guide to subject/project selection when context is missing; show project-scoped empty state if no review work exists |
| Structure | Project | Project | Guide to subject/project selection when context is missing; show project-scoped empty state if no structure exists |
| Project settings | Project | Project | Hidden or unavailable until a concrete project exists |
| Mine | Signed-in user | Account/system | Available without subject or project |
| Global settings | Signed-in user | System | Available without subject or project |

## Project Shell Contract

When a valid subject and scoped project are active:

- The shell displays or exposes the current subject title and project title.
- The shell provides bottom destinations in this order unless implementation tasks explicitly document a different order:
  1. Learning
  2. AI
  3. Review
  4. Structure
  5. Mine
- The shell does not show more than five bottom destinations.
- Switching bottom destinations keeps the same `subjectId` and `scopedProjectId`.
- The Learning destination hosts the existing mobile workbench behavior.
- The AI, Review, and Structure destinations may be explicit project-scoped empty/unavailable screens if their full mobile features are outside the current implementation slice.
- Mine is reachable from the shell but remains account/system scoped; it must not become the owner of subject settings or project settings.

## Context Menu Contract

The top context control must adapt to the current state:

### No Subject

- Show an action to create or select a subject.
- Do not show subject settings.
- Do not show project settings.
- Do not show project center as a target for a missing subject.

### Subject Only

- Show current subject.
- Show switch subject.
- Show subject settings.
- Show create/select project.
- Do not show project settings.

### Project

- Show current subject and current project.
- Show switch subject.
- Show subject settings.
- Show switch project.
- Show project settings.
- Show subject center and project center as management destinations.

## Mine Contract

Mine must group only account and system-level destinations:

- Profile
- Friends
- Membership
- User guide
- Global settings
- Admin, when allowed
- Sign out

Mine must not list subject settings or project settings as primary entries. If implementation later adds contextual shortcuts to scoped settings, those shortcuts must remain visually and semantically tied to the active context control, not to the account/system list.

## Guard Contract

Project-scoped routes and destinations must use explicit context checks:

- Missing `subjectId`: guide to subject creation or selection.
- Missing `scopedProjectId` with valid `subjectId`: guide to that subject's project center.
- Invalid subject or project: stop showing stale object settings and guide to the nearest valid context.
- Guards must not silently select the first project or last project.
- Guards must not persist a global current project as the source of truth.

## Empty and Unavailable State Contract

- Empty states must be concise.
- Empty states must name the missing object or capability.
- Project-scoped empty states must preserve current subject/project context.
- Unavailable destinations must not claim that a feature is functional.
- Unavailable states are allowed for out-of-scope mobile capabilities only when they are explicit and testable.
