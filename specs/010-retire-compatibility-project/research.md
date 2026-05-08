# Research: Retire Compatibility Project

## Decision 1: Subject ids are not project ids

- **Decision**: Keep the existing subject storage anchor, but do not expose it as `subjectProjectId` and do not accept it on project/workbench APIs.
- **Rationale**: The product model is simpler and safer when subject routes consume `subjectId` and project routes consume only concrete material `projectId` values.
- **Alternatives considered**:
  - **Rename the subject root to `subjectProjectId`**: Rejected because it keeps the dual-purpose identity that caused the forked user experience.
  - **Delete the subject anchor storage in this feature**: Rejected because it expands the work into a broader persistence redesign that is not required to clean the public boundary.

## Decision 2: Historical root-backed materials are migrated, not supported as a mode

- **Decision**: When a subject contains a material whose `projectId` equals the subject id, the system creates an independent material project, moves the root learning data into that project, and rewrites the material link.
- **Rationale**: Migration removes the bad shape from active data. Keeping runtime branches for root-backed materials would preserve the problem.
- **Alternatives considered**:
  - **Keep accepting subject ids as project ids**: Rejected because it preserves the fork.
  - **Require a separate operator migration before release**: Rejected because normal subject access can perform the migration idempotently.

## Decision 3: Retired compatibility fields are not parsed

- **Decision**: Study material payload decoding requires current `projectId`; retired `compatibilityProjectId` and `compatibility_project_id` are not fallback keys.
- **Rationale**: The user explicitly rejected compatibility behavior. Current data must be current-shaped data.
- **Alternatives considered**:
  - **Read old fields silently**: Rejected because it allows stale snapshots to keep feeding the old model.
  - **Write both old and new fields**: Rejected because it keeps two contracts alive.

## Decision 4: Frontend state separates subjects from workbench projects

- **Decision**: Frontend selection state uses `selectedSubjectId` for subjects and `selectedWorkbenchProjectId` for concrete projects.
- **Rationale**: The store should mirror the product boundary and avoid any single selected project slot that can hold subject ids.
- **Alternatives considered**:
  - **Reuse `selectedProjectId` and validate at read time**: Rejected because it keeps the same ambiguity in persisted browser state.

## Decision 5: Pomodoro binds from the concrete project catalog

- **Decision**: Pomodoro binding and workbench gating use valid material projects from `/api/projects`; they do not build subject-root exclusion sets.
- **Rationale**: Once `/api/projects` no longer returns subjects, filtering subject roots in the frontend is unnecessary and error-prone.
- **Alternatives considered**:
  - **Keep subject-root filtering in Pomodoro**: Rejected because it implies subject roots remain project candidates.

## Decision 6: Documentation cleanup is part of the feature

- **Decision**: Remove retired compatibility-project and subject-root-project language from user-facing docs and current feature docs.
- **Rationale**: Keeping old wording would reintroduce the mental model this feature removes.
