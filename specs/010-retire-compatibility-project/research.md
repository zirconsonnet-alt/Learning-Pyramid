# Research: Retire Compatibility Project

## Decision 1: Keep the subject-root project anchor, but retire the dirty field names

- **Decision**: Preserve the existing subject-root project anchor used by current subject settings/statistics/routing behavior, but rename its outward contract to `subjectProjectId` and stop describing it as a “compatibility project”.
- **Rationale**: The current system uses the subject root as a real operational anchor. Removing it in the same change would turn a contract cleanup into a much larger architecture rewrite with higher risk across settings, deletion, and route resolution.
- **Alternatives considered**:
  - **Delete the subject-root anchor entirely in this feature**: Rejected because it expands scope into persistence and routing architecture redesign.
  - **Keep the old field names and only hide them in select UI screens**: Rejected because the ambiguity would remain in the API and downstream code.

## Decision 2: Backward compatibility is read-only for retired field names

- **Decision**: Previously stored subject/material records that still contain `compatibilityProjectId` or `compatibility_project_id` remain readable, but newly written records stop emitting those field names.
- **Rationale**: This preserves user data and exported/local state safety without letting the dirty field survive indefinitely in new writes.
- **Alternatives considered**:
  - **Require an operator migration before release**: Rejected because this feature explicitly needs safe rollout across existing records.
  - **Continue writing both old and new field names forever**: Rejected because it prolongs the dirty contract instead of retiring it.

## Decision 3: No SQL schema migration is required for this phase

- **Decision**: Treat this feature as a payload and DTO rename rather than a relational schema redesign.
- **Rationale**: The field is currently encoded within stored project/material payloads and adapter DTOs. The main compatibility burden is in read/write serialization and frontend/backend contract usage, not in creating or altering relational tables.
- **Alternatives considered**:
  - **Introduce a dedicated subject table/model now**: Rejected because it exceeds the scope needed to retire the dirty concept safely.
  - **Rename storage structures across every persistence layer as a breaking migration**: Rejected because backward readability is a hard requirement.

## Decision 4: The frontend must switch atomically with the backend contract

- **Decision**: Update frontend contract consumers in the same implementation wave as backend DTO changes.
- **Rationale**: The project frontend currently reads `compatibilityProjectId` directly in subject pages, settings, AppShell, and Pomodoro logic. Updating only one side would immediately break navigation and filtering behavior.
- **Alternatives considered**:
  - **Backend alias period while frontend lags behind**: Rejected because it leaves two overlapping contracts alive and weakens the retirement goal.
  - **Frontend-only remapping without backend change**: Rejected because the dirty contract would still leak outward.

## Decision 5: Pomodoro continues filtering subject roots, but from `subjectProjectId`

- **Decision**: Preserve the existing Pomodoro safeguard that excludes subject-root entries from bindable workbench projects, but derive the exclusion set from `subjectProjectId`.
- **Rationale**: The user already approved this stopgap behavior. The refactor should keep the behavior while switching it to the cleaned model.
- **Alternatives considered**:
  - **Drop the Pomodoro safeguard during the rename**: Rejected because it would reintroduce a broken user path.
  - **Infer subject roots indirectly from route shape or project type alone**: Rejected because the plan needs an explicit and stable contract.

## Decision 6: Documentation cleanup is part of the feature, not a follow-up

- **Decision**: Remove the retired compatibility-project language from user-facing docs in the same feature.
- **Rationale**: The product concept is being retired, so docs that still teach it would undermine the contract cleanup and confuse maintainers and users.
- **Alternatives considered**:
  - **Leave docs unchanged until after implementation**: Rejected because this repository requires docs to stay synchronized when usage or contract meaning changes.
