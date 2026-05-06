# Feature Specification: Retire Compatibility Project

**Feature Branch**: `[010-retire-compatibility-project]`  
**Created**: 2026-05-06  
**Status**: Draft  
**Input**: User description: "把 compatibilityProjectId / compatibility_project_id 从学科-项目模型中退休，改成 subjectProjectId 和 material.projectId，并保留旧数据读取兼容"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Understand Subject And Project Boundaries Clearly (Priority: P1)

As a learner managing subjects and projects, I want the product to present a subject as a subject and a project as a project, so that I can enter subject pages, project workbenches, settings, and statistics without relying on a misleading “compatibility project” concept.

**Why this priority**: This is the core business value of the change. If the model remains ambiguous, every downstream page continues to inherit the same conceptual bug.

**Independent Test**: Can be fully tested by creating a subject with multiple materials, then verifying that subject pages, project pages, and settings use clear subject and project identifiers while preserving current behavior.

**Acceptance Scenarios**:

1. **Given** a learner opens a subject dashboard, **When** the dashboard loads its subject and material data, **Then** the subject is represented by a subject-level identifier and each material-backed project is represented by a project-level identifier.
2. **Given** a learner opens a material project workbench from within a subject, **When** the navigation context resolves, **Then** the system identifies the subject root separately from the selected material project and does not rely on a field named `compatibilityProjectId`.

---

### User Story 2 - Existing Learning Data Continues To Open Correctly (Priority: P2)

As an existing user with previously stored subject and material data, I want my historical data to continue loading after the model cleanup, so that the naming refactor does not break access to my subjects, projects, or workbench state.

**Why this priority**: The product cannot safely retire the dirty concept if existing records become unreadable. Backward readability is essential for production safety.

**Independent Test**: Can be fully tested by loading historical records that were saved with the old field names and confirming they are interpreted into the new subject/project model without user intervention.

**Acceptance Scenarios**:

1. **Given** stored subject or material records created before the refactor, **When** the system reads them, **Then** the records are still understood and mapped into the new subject and project identifiers.
2. **Given** a user revisits an old subject after the refactor, **When** the subject context opens, **Then** the correct subject root and current material project are restored without requiring manual migration steps.

---

### User Story 3 - Follow-Up Features Stop Depending On The Dirty Concept (Priority: P3)

As a product maintainer, I want downstream flows such as Pomodoro binding, settings, and subject-level cleanup to use the cleaned model, so that future feature work no longer inherits the hidden ambiguity between subjects and projects.

**Why this priority**: The change only creates lasting value if dependent product flows also stop carrying the old abstraction.

**Independent Test**: Can be fully tested by exercising Pomodoro project selection, subject settings, project deletion, and subject deletion after the refactor and confirming all flows still work with the new field names.

**Acceptance Scenarios**:

1. **Given** a learner configures a Pomodoro plan, **When** they choose a project for a Pomodoro block, **Then** only true material projects are selectable and subject root identifiers are excluded through the new subject/project model.
2. **Given** a learner deletes a project or an entire subject, **When** the cleanup runs, **Then** the system removes the correct project scope and subject scope without depending on a compatibility-project field.

### Edge Cases

- What happens when a legacy subject contains only the historical default material whose project identity is the same as the subject root?
- How does the system handle records where the old compatibility field is missing, null, or inconsistent with the current subject-material relationship?
- What happens when a user opens a bookmarked route that previously relied on the old field name for subject or project resolution?
- How does the system behave when a subject is deleted after some of its child projects were already removed or are no longer accessible?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST represent each subject in outbound product contracts with a subject-level identifier named `subjectProjectId` instead of `compatibilityProjectId`.
- **FR-002**: The system MUST represent each study material’s associated workbench project in outbound product contracts with a project-level identifier named `projectId` instead of `compatibilityProjectId`.
- **FR-003**: The system MUST preserve the current user-facing ability to open subject dashboards, subject settings, project settings, and project workbenches after the identifier rename.
- **FR-004**: The system MUST continue to interpret previously stored subject and study material records that still use the retired compatibility field names.
- **FR-005**: The system MUST write newly saved study material records using the cleaned project field name rather than the retired compatibility field name.
- **FR-006**: The system MUST stop exposing the retired compatibility-project concept in current product contracts, application behavior, and user-facing documentation.
- **FR-007**: The system MUST continue to distinguish subject-root scope from material-project scope when resolving current subject context, including subject-level pages and material-level pages.
- **FR-008**: The system MUST preserve subject and project deletion behavior, including cleanup of related project scopes, after the model rename.
- **FR-009**: The system MUST preserve project-selection rules in Pomodoro and other project-bound flows so that subject roots are not treated as normal material projects.
- **FR-010**: The system MUST preserve subject-material relationships for course, book, and loose-points materials under the cleaned naming model.
- **FR-011**: The system MUST keep the current default-material behavior for existing subjects unless the user explicitly changes materials.
- **FR-012**: The system MUST provide enough contract clarity that downstream product features can determine whether they are working with a subject root or a material project without inferring from misleading field names.

### Key Entities *(include if feature involves data)*

- **Subject**: A top-level learning domain owned and named by the user. It has its own subject identity and a subject-root project anchor used for subject-level routes and settings.
- **Study Material**: A learning material entry under a subject, such as a course, book, or loose-points collection. It belongs to one subject and may map to a project workbench.
- **Material Project**: The workbench-bearing project associated with a study material. It is separate from the subject root even when historical data treated them as the same thing.
- **Subject Context**: The resolved view of a subject, including the subject itself, its materials, the current material, the current project scope, and whether the user is at the subject root.
- **Legacy Subject/Material Record**: Previously stored subject or material data created before the naming cleanup that still uses the retired compatibility field names and must remain readable.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of current subject and material product contracts in the affected flows expose `subjectProjectId` and `projectId` in place of `compatibilityProjectId`.
- **SC-002**: 100% of existing subject records and study material records used in regression tests continue to load successfully after the refactor without manual data repair.
- **SC-003**: Users can complete the core navigation flows of entering a subject, entering a material project, opening settings, and deleting a subject or project with no increase in failed flow outcomes compared with the pre-refactor baseline.
- **SC-004**: Pomodoro project selection and workbench gating continue to exclude subject roots and accept only valid material projects in all covered regression scenarios.
- **SC-005**: No user-facing copy or product-facing contract in the affected scope refers to a “compatibility project” after the feature is completed.

## Assumptions

- Existing subject-root behavior is still needed for current settings, statistics, and route resolution, so the cleanup renames and clarifies that root identity rather than removing the underlying root-project anchor in this phase.
- Historical persisted data may exist in local stores, exported backups, or database-backed environments and must remain readable without requiring a dedicated operator migration step before release.
- The feature scope is limited to retiring the dirty compatibility-project concept from contracts, naming, and dependent flows; it does not require introducing a brand-new persistence model for subjects in this phase.
- The currently implemented Pomodoro stopgap remains valid and should be preserved, with only the identifier source updated to the cleaned subject/project model.
