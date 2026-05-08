# Feature Specification: Retire Compatibility Project

**Feature Branch**: `[010-retire-compatibility-project]`  
**Created**: 2026-05-06  
**Status**: Draft  
**Input**: User description: "把 compatibilityProjectId / compatibility_project_id 从学科-项目模型中退休；学科 ID 只表示学科，项目 ID 只表示学科内具体项目，不保留历史兼容，已有根项目材料迁移为独立项目。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Understand Subject And Project Boundaries Clearly (Priority: P1)

As a learner managing subjects and projects, I want the product to present a subject as a subject and a project as a project, so that I can enter subject pages, project workbenches, settings, and statistics without relying on a misleading “compatibility project” concept.

**Why this priority**: This is the core business value of the change. If the model remains ambiguous, every downstream page continues to inherit the same conceptual bug.

**Independent Test**: Can be fully tested by creating a subject with multiple materials, then verifying that subject pages use `subjectId`, project pages/settings use material `projectId`, and subject ids are rejected on project routes.

**Acceptance Scenarios**:

1. **Given** a learner opens a subject dashboard, **When** the dashboard loads its subject and material data, **Then** the subject is represented by a subject-level identifier and each material-backed project is represented by a project-level identifier.
2. **Given** a learner opens a material project workbench from within a subject, **When** the navigation context resolves, **Then** the system identifies the subject through the material-project link and does not expose `compatibilityProjectId` or `subjectProjectId`.

---

### User Story 2 - Existing Learning Data Is Migrated Cleanly (Priority: P2)

As an existing user with previously stored subject and material data, I want historical root-backed materials to become independent material projects, so that the cleanup removes the forked identity model instead of preserving it.

**Why this priority**: The product cannot safely retire the dirty concept if existing records remain root-backed. Migration is required for production safety.

**Independent Test**: Can be fully tested by loading historical records where a material project id equals the subject id and confirming subject/material listing migrates it into a new child project id.

**Acceptance Scenarios**:

1. **Given** a stored subject has a root-backed material, **When** the subject list or material list is opened, **Then** the material is migrated to an independent material project.
2. **Given** a user revisits an old subject after migration, **When** the subject context opens for the material project, **Then** the context resolves through the material project and the subject id itself is rejected as a project id.

---

### User Story 3 - Follow-Up Features Stop Depending On The Dirty Concept (Priority: P3)

As a product maintainer, I want downstream flows such as Pomodoro binding, settings, and subject-level cleanup to use the cleaned model, so that future feature work no longer inherits the hidden ambiguity between subjects and projects.

**Why this priority**: The change only creates lasting value if dependent product flows also stop carrying the old abstraction.

**Independent Test**: Can be fully tested by exercising Pomodoro project selection, subject settings, project deletion, and subject deletion after the refactor and confirming all flows still work with the new field names.

**Acceptance Scenarios**:

1. **Given** a learner configures a Pomodoro plan, **When** they choose a project for a Pomodoro block, **Then** only true material projects are selectable from the project catalog.
2. **Given** a learner deletes a project or an entire subject, **When** the cleanup runs, **Then** the system removes the correct project scope and subject scope without depending on a compatibility-project or subject-root-project field.

### Edge Cases

- What happens when a legacy subject contains only a historical root-backed material whose project identity is the same as the subject root?
- How does the system handle records whose material payload lacks a current `projectId`?
- What happens when a user opens a bookmarked route that previously relied on the old field name for subject or project resolution?
- How does the system behave when a subject is deleted after some of its child projects were already removed or are no longer accessible?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST represent each subject in outbound product contracts with `subjectId` only; it MUST NOT expose `subjectProjectId` or `compatibilityProjectId`.
- **FR-002**: The system MUST represent each study material’s associated workbench project in outbound product contracts with a project-level identifier named `projectId` instead of `compatibilityProjectId`.
- **FR-003**: The system MUST preserve the current user-facing ability to open subject dashboards, subject settings, project settings, and project workbenches after the identifier rename.
- **FR-004**: The system MUST NOT parse retired compatibility field names as current material project identifiers.
- **FR-005**: The system MUST read and write study material records using `projectId`.
- **FR-006**: The system MUST stop exposing the retired compatibility-project concept in current product contracts, application behavior, and user-facing documentation.
- **FR-007**: The system MUST reject subject ids on project APIs and resolve subject context only from material project ids.
- **FR-008**: The system MUST preserve subject and project deletion behavior, including cleanup of related project scopes, after the model rename.
- **FR-009**: The system MUST preserve project-selection rules in Pomodoro and other project-bound flows by using only material projects from the project catalog.
- **FR-010**: The system MUST preserve subject-material relationships for course, book, and loose-points materials under the cleaned naming model.
- **FR-011**: The system MUST migrate historical root-backed materials into independent material projects so subject roots are no longer treated as learning projects.
- **FR-012**: The system MUST provide enough contract clarity that downstream product features work with either a subject id or a material project id, never a dual-purpose subject-root project id.

### Key Entities *(include if feature involves data)*

- **Subject**: A top-level learning domain owned and named by the user. It has its own subject identity; that identity is not a workbench project id.
- **Study Material**: A learning material entry under a subject, such as a course, book, or loose-points collection. It belongs to one subject and may map to a project workbench.
- **Material Project**: The workbench-bearing project associated with a study material. It is separate from the subject root even when historical data treated them as the same thing.
- **Subject Context**: The resolved view of a material project, including the subject itself, its materials, the current material, and the current project scope.
- **Historical Root-Backed Material**: Previously stored subject material whose project id equals the subject id and must be migrated into an independent material project.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of current subject contracts in the affected flows expose `subjectId` without `subjectProjectId` or `compatibilityProjectId`, and material contracts expose `projectId`.
- **SC-002**: 100% of historical root-backed material records used in regression tests migrate to independent material project ids without manual data repair.
- **SC-003**: Users can complete the core navigation flows of entering a subject, entering a material project, opening settings, and deleting a subject or project with no increase in failed flow outcomes compared with the pre-refactor baseline.
- **SC-004**: Pomodoro project selection and workbench gating accept only valid material projects in all covered regression scenarios.
- **SC-005**: No user-facing copy or product-facing contract in the affected scope refers to a “compatibility project” after the feature is completed.

## Assumptions

- Subject ownership can continue to be stored in the existing project-store infrastructure, but that storage detail is not exposed as a workbench project contract.
- Historical root-backed materials may exist in local stores, exported backups, or database-backed environments and must be migrated during normal subject/material access.
- The feature scope is limited to retiring the dirty compatibility-project and subject-root-project concepts from contracts, route behavior, storage parsing, and dependent flows.
- Pomodoro binding should use concrete material project ids from the project catalog instead of filtering out subject roots.
