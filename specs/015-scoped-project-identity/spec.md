# Feature Specification: Scoped Project Identity

**Feature Branch**: `015-scoped-project-identity`  
**Created**: 2026-05-12  
**Status**: Draft  
**Input**: User description: "按照保留后端全局内部项目 ID、保留学科内项目编号但清理命名边界的方向，修复学科项目身份模型。当前线上出现 `PRECONDITION: project id is not a subject`，原因是重启后学科与材料项目关系没有恢复，且 `projectId` 同时表示内部项目 ID 和学科内项目编号。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 学科工作台重启后可用 (Priority: P1)

用户创建学科并进入该学科下的材料工作台后，即使服务重启，工作台仍能通过学科 ID 和学科内项目编号打开内容目录、复述点、任务队列和学习状态。

**Why this priority**: 当前线上故障直接阻断工作台使用，必须先恢复学科材料关系的可靠持久化。

**Independent Test**: 创建一个学科，进入默认材料工作台，重启服务后再次访问同一个工作台地址，页面可以加载材料目录和学习状态，不出现“project id is not a subject”。

**Acceptance Scenarios**:

1. **Given** 已创建学科和默认材料，**When** 服务重启后用户打开该材料工作台，**Then** 系统能识别该学科并加载对应材料项目。
2. **Given** 学科下存在多个材料项目，**When** 用户分别打开每个材料工作台，**Then** 每个学科内项目编号都能解析到正确的内部项目。
3. **Given** 用户访问不存在或不属于该学科的学科内项目编号，**When** 页面请求材料数据，**Then** 系统返回明确的不存在或无权限结果，而不是把学科误判为非学科。

---

### User Story 2 - 身份语义清晰可排查 (Priority: P2)

开发者和维护者在代码、接口响应、日志和前端状态中能够清楚区分内部项目 ID、学科 ID 和学科内项目编号，不再把不同语义都命名为 `projectId`。

**Why this priority**: 当前命名混淆导致排查困难，并让前端和后端都可能把学科内编号当成内部项目 ID 使用。

**Independent Test**: 检查学科材料相关 API、前端路由状态和日志字段，同一个字段名不再同时表示内部项目 ID 和学科内项目编号。

**Acceptance Scenarios**:

1. **Given** API 返回学科材料信息，**When** 维护者查看响应，**Then** 能明确看到学科 ID、学科内项目编号和内部项目 ID 的不同含义。
2. **Given** 前端从 URL 进入材料工作台，**When** 它发起工作台请求，**Then** 请求语义明确表达“学科 ID + 学科内项目编号”，而不是伪装成全局项目 ID。
3. **Given** 后端日志记录一次学科内项目解析，**When** 维护者查看日志，**Then** 能看出输入的学科内编号和解析后的内部项目 ID。

---

### User Story 3 - 既有线上数据可恢复 (Priority: P3)

现有线上学科和材料项目数据在模型修复后仍可使用，已创建的学科路径和学习数据不会因为身份命名清理而丢失。

**Why this priority**: 当前已有线上数据，例如一个学科下的材料项目映射到内部项目，修复必须保护这些数据。

**Independent Test**: 使用线上同形态数据进行恢复演练，确认学科、材料、内容目录、复述点、任务队列和学习记录仍关联到同一个材料项目。

**Acceptance Scenarios**:

1. **Given** 数据库中存在学科记录和材料项目记录，**When** 系统升级并重启，**Then** 学科材料关系被恢复为可查询状态。
2. **Given** 历史数据中存在已删除的全局项目 ID 与当前学科内编号同名，**When** 解析学科材料工作台，**Then** 系统只按学科范围解析该编号，不误用已删除的全局项目。
3. **Given** 恢复过程发现关系不完整，**When** 系统启动或执行数据检查，**Then** 它报告可操作的数据问题，而不是静默产生错误映射。

### Edge Cases

- 学科存在但没有任何材料项目时，系统应明确表示空材料列表，而不是否认该学科身份。
- 学科内项目编号与某个历史全局项目 ID 文本相同，也必须按学科范围解析。
- 材料项目存在内部项目 ID，但学科侧缺少对应材料关系时，系统应将其识别为数据不一致。
- 学科侧存在材料关系，但内部项目缺失或已删除时，系统应将其识别为数据不一致。
- 用户无权访问学科或材料项目时，错误语义应为无权限，而不是身份类型错误。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST persist enough subject-material relationship data so a subject remains recognizable after service restart, including subjects with zero materials and subjects with one or more materials.
- **FR-002**: System MUST preserve the distinction between subject identity, subject-scoped material project identity, and internal project identity in stored data, API contracts, frontend state, and diagnostic output.
- **FR-003**: System MUST resolve a material workspace by the pair of subject identity and subject-scoped material project identity before accessing project-scoped learning data.
- **FR-004**: System MUST NOT treat a subject-scoped material project identity as an internal global project identity.
- **FR-005**: System MUST keep existing subject workspace URLs usable when they identify a material by subject identity and subject-scoped material project identity.
- **FR-006**: System MUST reject requests where the subject-scoped material project identity does not belong to the provided subject.
- **FR-007**: System MUST provide a deterministic recovery path for existing records where subject-material relationships can be reconstructed from stored subject and material project metadata.
- **FR-008**: System MUST surface unrecoverable relationship inconsistencies as explicit data integrity errors during validation or startup checks.
- **FR-009**: System MUST keep internal project identity available for backend storage, learning data, audit logs, queues, media bindings, and project-scoped records.
- **FR-010**: System MUST update user-facing or developer-facing names that currently imply the wrong identity semantics.
- **FR-011**: System MUST verify that creating a new subject, adding a material, restarting the service, and opening the material workspace works end to end.
- **FR-012**: System MUST verify that existing active material project data remains associated with the same material after the identity repair.

### Key Entities *(include if feature involves data)*

- **Subject**: A learning subject such as "高等数学"; it owns a collection of material projects.
- **Subject-Scoped Material Project Identity**: The material project identifier meaningful only inside one subject; it is paired with a subject identity to address a material workspace.
- **Internal Project Identity**: The backend storage identity for project-scoped learning data, queues, media, audit records, permissions, and indexes.
- **Subject Material Relationship**: The relationship connecting one subject, one subject-scoped material project identity, and one internal project identity.
- **Material Workspace**: The user-facing workspace reached from a subject and a subject-scoped material project identity.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a service restart, 100% of newly created subjects with default materials can reopen their material workspace without a subject identity error.
- **SC-002**: Existing recoverable subject-material records remain accessible after upgrade, with no loss of learning objects, recall points, review queues, or media bindings.
- **SC-003**: A request for a material identity outside its subject returns a clear not-found or access-control outcome in all covered API paths.
- **SC-004**: Code and API review finds no remaining subject-material workflow where a single ambiguous field name is used for both internal project identity and subject-scoped material identity.
- **SC-005**: Diagnostic output for a subject-scoped workspace request includes enough information to identify the subject identity, subject-scoped material identity, and resolved internal project identity.

## Assumptions

- Backend storage keeps a global internal project identity because project-scoped tables, queues, media bindings, audit records, and learning data already depend on it.
- The feature does not require converting all project-scoped storage tables to composite keys.
- Existing workspace URLs based on subject identity plus subject-scoped material project identity should continue to work.
- The current production failure is caused by subject-material relationship data not being restored after restart, not by a user navigation mistake.
- Unrecoverable corrupted data should be reported rather than silently guessed.
