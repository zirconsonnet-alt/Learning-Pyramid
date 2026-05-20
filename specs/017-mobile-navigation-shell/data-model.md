# Data Model: Mobile Navigation Shell

This feature does not introduce persisted backend data. The model below describes mobile navigation state, route requirements, and UI-facing entities derived from existing subject/project data.

## Entity: LearningContext

**Purpose**: Represents the current mobile learning scope.

**Fields**:

- `subjectId`: Existing public subject identifier, optional until a subject exists or is selected.
- `subjectTitle`: Display title for the current subject, optional while loading or missing.
- `scopedProjectId`: Existing public scoped project identifier, optional until a project exists or is selected.
- `projectTitle`: Display title for the current project/material, optional while loading or missing.
- `projectType`: Existing project/material type when project data is available.
- `status`: One of `no-subject`, `subject-only`, `project`, `invalid`.

**Validation Rules**:

- `project` status requires both `subjectId` and `scopedProjectId`.
- `subject-only` status requires `subjectId` and must not expose project settings.
- `no-subject` status must not expose subject settings or project settings.
- `invalid` status occurs when route params point to a deleted or inaccessible subject/project and must guide users to the nearest valid context.

**State Transitions**:

- `no-subject` -> `subject-only`: user creates or selects a subject.
- `subject-only` -> `project`: user creates or selects a project under the subject.
- `project` -> `subject-only`: current project is deleted or becomes inaccessible while subject remains valid.
- `project` -> `no-subject`: current subject is deleted or becomes inaccessible.
- Any state -> `invalid`: route params cannot be resolved to accessible objects.

## Entity: NavigationDestination

**Purpose**: Defines each mobile destination's required context and ownership scope.

**Fields**:

- `id`: Stable destination identifier such as `learning`, `ai`, `review`, `structure`, `mine`, `subject-settings`, `project-settings`, `global-settings`.
- `label`: Concise display label.
- `scope`: One of `none`, `subject`, `project`, `account`, `system`.
- `requiresProjectContent`: Whether the destination needs project learning content beyond a project itself.
- `availability`: One of `available`, `empty`, `unavailable`, `forbidden`.
- `target`: Route or screen target expressed through existing mobile navigation.

**Validation Rules**:

- Project destinations require `LearningContext.status = project`.
- Subject settings require `LearningContext.status = subject-only` or `project`.
- Project settings require `LearningContext.status = project`.
- Account/system destinations must not require a selected project.
- Forbidden destinations must not be shown as available actions.

## Entity: ProjectShell

**Purpose**: Project-context container that owns top context and bottom task navigation.

**Fields**:

- `context`: Current `LearningContext` with status `project`.
- `activeDestinationId`: One of `learning`, `ai`, `review`, `structure`, `mine`.
- `contextMenuItems`: Subject/project switch and settings actions valid for the current context.
- `bottomDestinations`: Exactly five primary project shell destinations.

**Validation Rules**:

- Must render only when `LearningContext.status = project`.
- Must not contain more than five bottom destinations.
- Must keep current subject/project visible or one interaction away.
- Must not mutate learning data directly; destination screens keep their existing owners.

## Entity: ContextMenu

**Purpose**: Current object navigation and scoped management surface.

**Fields**:

- `subjectSummary`: Current subject label and actions.
- `projectSummary`: Current project label and actions.
- `managementItems`: Subject center, project center, and valid settings actions.

**Validation Rules**:

- No subject: show subject creation/selection actions only.
- Subject only: show subject switch and subject settings; do not show project settings.
- Project: show subject switch/settings and project switch/settings.

## Entity: MineArea

**Purpose**: Account and global/system mobile destination.

**Fields**:

- `accountItems`: Profile, friends, membership, sign out.
- `systemItems`: User guide, global settings, admin when allowed.
- `availabilityByItem`: Whether each item is available, unavailable, or forbidden.

**Validation Rules**:

- Must be reachable without selected subject/project for signed-in users.
- Must not present subject settings or project settings as primary Mine entries.
- Admin is shown only when the current user is allowed to access it.

## Entity: RouteRequirement

**Purpose**: Declarative requirement used by navigation guards and tests.

**Fields**:

- `routePattern`: Mobile route or logical destination.
- `requiredScope`: `none`, `subject`, `project`, `account`, or `system`.
- `missingSubjectTarget`: Destination for missing subject context.
- `missingProjectTarget`: Destination for missing project context.

**Validation Rules**:

- Missing subject for a project route must guide to subject creation or selection.
- Missing project for a project route with a valid subject must guide to that subject's project center.
- Guards must not silently choose a different project.
