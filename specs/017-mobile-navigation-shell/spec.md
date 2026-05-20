# Feature Specification: Mobile Navigation Shell

**Feature Branch**: `017-mobile-navigation-shell`  
**Created**: 2026-05-20  
**Status**: Draft  
**Input**: User description: "移动端导航结构按学科、项目、账号、全局作用域分层：无上下文先进入学科/项目初始化；有项目后使用项目 Shell，顶部显示当前学科和项目上下文，底部提供学习、AI、复习、结构、我的任务入口；学科设置和项目设置跟随当前对象；我的只承载账号与系统级入口。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start Without Learning Context (Priority: P1)

A signed-in user with no learning context must land in a clear setup flow instead of an empty project workspace or a full project tab bar. The user can create or select a subject first, then create or select a project, then enter the project workspace.

**Why this priority**: New users cannot use project-level learning features until a subject and project exist. This flow prevents dead tabs, unclear empty pages, and accidental reliance on an implicit current project.

**Independent Test**: Can be fully tested with an account that has no subjects by signing in, creating a subject, creating a project, and reaching the project workspace without seeing project-level bottom tabs before a project exists.

**Acceptance Scenarios**:

1. **Given** a signed-in user has no subjects, **When** the mobile app opens, **Then** the user sees the subject center or start-learning state with a primary action to create or select a subject.
2. **Given** a signed-in user has a subject but no project under that subject, **When** the user opens that subject, **Then** the user sees the project center with a primary action to create or select a project.
3. **Given** a signed-in user creates or selects a project, **When** the project opens, **Then** the app enters the project workspace and may show project-level task navigation.

---

### User Story 2 - Navigate Inside a Project Context (Priority: P2)

A user who has selected a subject and project must see a project shell that keeps the current subject/project visible and gives direct access to high-frequency project tasks: learning, AI, review, structure, and account/system area.

**Why this priority**: The product has many routes, but mobile space cannot expose them all. Project users need fast task switching without losing the subject/project context.

**Independent Test**: Can be fully tested with an account that has at least one subject and project by opening the project and switching between the five project shell destinations while the current context remains visible.

**Acceptance Scenarios**:

1. **Given** a user is inside a project, **When** the project shell renders, **Then** the top context area identifies the current subject and project.
2. **Given** a user is inside a project, **When** the user uses the bottom task navigation, **Then** the destinations are Learning, AI, Review, Structure, and Mine.
3. **Given** a project-level destination is not yet available or has no content, **When** the user opens it, **Then** the app shows a clear project-scoped empty or unavailable state without changing the current subject/project.

---

### User Story 3 - Manage Scoped Settings from the Right Context (Priority: P3)

A user must access subject settings from subject context and project settings from project context. Account and system destinations must remain separate from scoped settings.

**Why this priority**: Subject settings and project settings configure different domain objects. Placing them under a generic account area would obscure which object is being changed.

**Independent Test**: Can be tested by opening states with no subject, with a subject only, and with a subject plus project, then verifying which settings entries are visible and where they lead.

**Acceptance Scenarios**:

1. **Given** no subject is selected, **When** the context controls open, **Then** subject settings and project settings are not offered.
2. **Given** a subject is selected but no project is selected, **When** the context controls open, **Then** subject settings are available and project settings are not offered.
3. **Given** a subject and project are selected, **When** the context controls open, **Then** subject settings and project settings are available and each clearly targets the current object.
4. **Given** the user opens Mine, **When** system and account entries are listed, **Then** subject settings and project settings are not presented as primary Mine entries.

---

### User Story 4 - Reach Account and System Routes Without Polluting Learning Navigation (Priority: P4)

A signed-in user must be able to reach account and system-level routes from Mine while project learning routes remain focused on the current project.

**Why this priority**: The desktop app has global, account, subject, and project routes. Mobile navigation must preserve those scopes while keeping project tasks usable.

**Independent Test**: Can be tested by opening Mine from any available state and confirming account/system entries are reachable without needing a selected project.

**Acceptance Scenarios**:

1. **Given** a signed-in user has no subject or project, **When** the user opens account/system navigation, **Then** profile, friends, membership, guide, global settings, admin if allowed, and sign out can be reached according to user permissions.
2. **Given** a signed-in user is inside a project, **When** the user opens Mine, **Then** account and system routes are available without replacing subject/project settings as their owner-specific entry points.

### Edge Cases

- If the user reaches a project-level route without a selected or valid subject, the app must redirect or guide the user to subject creation or selection.
- If the user reaches a project-level route with a subject but without a selected or valid project, the app must redirect or guide the user to project creation or selection within that subject.
- If the current subject or project is deleted while the user is inside the project shell, the shell must stop showing stale object settings and guide the user back to the nearest valid context.
- If a destination requires project content but the project has no content, the destination must show a project-scoped empty state and keep the current project context.
- If the user lacks permission for an admin route, the admin entry must not be shown as an available destination.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The mobile app MUST classify navigation destinations by scope: no-context, subject-scoped, project-scoped, account-scoped, and global/system-scoped.
- **FR-002**: The mobile app MUST start signed-in users without any subject in a subject creation or selection experience, not in a project workspace.
- **FR-003**: The mobile app MUST start signed-in users who have a selected subject but no selected project in a project creation or selection experience for that subject.
- **FR-004**: The mobile app MUST show project-level task navigation only after a valid subject and project context exists.
- **FR-005**: Project-level task navigation MUST include Learning, AI, Review, Structure, and Mine as the primary mobile destinations once a project context exists.
- **FR-006**: The current subject and current project MUST remain visible or immediately inspectable while the user is inside a project context.
- **FR-007**: The context controls MUST let users switch subject and project from the current learning context.
- **FR-008**: Subject settings MUST only be offered when a concrete subject exists and MUST clearly target that subject.
- **FR-009**: Project settings MUST only be offered when a concrete project exists and MUST clearly target that project.
- **FR-010**: Mine MUST contain account and system-level destinations, including profile, friends, membership, user guide, global settings, allowed admin entry, and sign out.
- **FR-011**: Mine MUST NOT present subject settings or project settings as primary account/system entries.
- **FR-012**: Project-scoped destinations opened without valid context MUST guide the user to the minimum missing context rather than showing a broken or ambiguous page.
- **FR-013**: Unavailable or empty project destinations MUST explain the missing project-scoped content or capability without changing the selected subject/project.
- **FR-014**: Navigation labels and empty states MUST be concise and must not add explanatory decoration beyond what is needed to complete the task.
- **FR-015**: The mobile navigation model MUST preserve the existing subject-to-project identity relationship and must not introduce a hidden global current project that bypasses explicit context selection.

### Key Entities *(include if feature involves data)*

- **Learning Context**: The currently selected subject and, when available, project. It determines which project-level destinations and object settings are valid.
- **Subject**: A long-lived learning domain. It owns project lists and subject settings.
- **Project**: A subject-scoped learning workspace. It owns project learning tasks, AI context, review, structure, and project settings.
- **Navigation Destination**: A user-reachable route or screen categorized by required context scope.
- **Mine Area**: The account and system-level mobile area available to signed-in users.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new signed-in user with no subjects can reach subject creation or selection within one primary action from app launch.
- **SC-002**: A user with one existing subject and no projects can reach project creation or selection within one primary action after opening that subject.
- **SC-003**: A user with a valid project can switch among Learning, AI, Review, Structure, and Mine without first returning to the subject center.
- **SC-004**: In usability review, all scoped settings entries can be correctly identified as subject-level, project-level, or system/account-level without relying on implementation knowledge.
- **SC-005**: No project-scoped route displays an ambiguous empty page when subject or project context is missing; each such route guides to the missing context.
- **SC-006**: The mobile primary navigation exposes no more than five project-level bottom destinations in the project shell.

## Assumptions

- Existing sign-in and signed-out behavior remains unchanged.
- Existing subject and project concepts remain the source of learning context.
- Existing global settings, user guide, account, membership, friends, admin, and sign-out semantics remain owned by account or system scope.
- Admin entry visibility depends on the user's existing permissions.
- This specification defines navigation behavior and information architecture only; it does not require new learning, AI, review, structure, account, membership, or admin capabilities beyond routing and reachable states.
- The first implementation may preserve the current stack-based subject and project setup flow before introducing the project shell for users with a valid project.
