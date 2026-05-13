# Feature Specification: Backend Verification Gates

**Feature Branch**: `016-backend-verification-gates`  
**Created**: 2026-05-13  
**Status**: Draft  
**Input**: User description: "旧测试全绿却没有提前发现 `project id is not a subject`。为后端建立真实故障面的验收门禁：不能只靠普通单测，必须覆盖重启恢复、真实持久化、真实迁移、身份边界和可操作诊断，避免等用户实际使用时才发现后端问题。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 发布前发现重启恢复问题 (Priority: P1)

维护者在后端变更发布前，可以通过一条明确的验收流程验证关键业务对象在保存、重启和重新打开后仍然可用，不再因为内存态测试通过而遗漏恢复问题。

**Why this priority**: 线上故障来自重启后关系数据未恢复。最重要的价值是把这类问题提前拦在发布前，而不是等用户打开页面时才暴露。

**Independent Test**: 执行后端验收门禁，创建一个带材料的学科，保存状态，重启后端运行时，再用同一个学科工作台地址打开内容目录、复述点、任务队列和学习状态；验收必须在任一环节失败时阻止通过。

**Acceptance Scenarios**:

1. **Given** 一个新建学科及其默认材料，**When** 后端保存数据并重启运行时，**Then** 同一个学科材料工作台仍能打开并关联到原材料。
2. **Given** 一个变更影响学科、项目、材料、学习对象或队列的持久化，**When** 发布前验收运行，**Then** 验收必须经过保存和重启断点，而不是只复用同一个内存态实例。
3. **Given** 重启后对象关系缺失，**When** 验收流程运行，**Then** 它必须失败并指出缺失的是恢复关系、对象数据还是访问身份。

---

### User Story 2 - 发布前验证真实持久化和迁移路径 (Priority: P2)

维护者在后端变更发布前，可以用接近生产形态的数据存储执行迁移、启动、读写和数据检查，避免只在简化存储或模拟环境中通过。

**Why this priority**: 旧测试没有覆盖真实数据库迁移和类型约束，导致 schema 问题只能在真实运行时暴露。

**Independent Test**: 对任一影响持久化或数据模型的变更，验收必须在真实数据库实例上执行迁移、创建数据、重启读取和完整性检查；如果迁移、字段类型或必需列缺失，验收失败。

**Acceptance Scenarios**:

1. **Given** 一个空的真实数据库实例，**When** 当前后端版本初始化并运行验收，**Then** 所有必需结构可创建，核心读写路径可完成。
2. **Given** 一个旧版本形态的数据实例，**When** 当前后端版本升级并运行验收，**Then** 可恢复数据被恢复，不可恢复数据被明确报告。
3. **Given** 持久化结构存在类型不匹配或必需字段缺失，**When** 验收运行，**Then** 它必须失败并定位到具体结构或数据问题。

---

### User Story 3 - 身份边界和诊断成为验收对象 (Priority: P3)

维护者可以在发布前确认关键身份不会被混用，并且故障发生时诊断输出足以定位是输入身份、解析关系、内部对象还是权限问题。

**Why this priority**: `projectId` 同时表示不同身份时，即使功能暂时可用，也会让测试和排查都产生误导。

**Independent Test**: 验收流程检查关键业务路径的公开身份、内部身份、日志和错误语义；如果同一字段名在同一路径里混用不同身份，或错误语义无法区分身份不存在、关系缺失和权限失败，验收失败。

**Acceptance Scenarios**:

1. **Given** 一个从公开工作台地址进入的请求，**When** 后端解析身份，**Then** 诊断信息能区分公开身份、解析后的内部身份和所属业务对象。
2. **Given** 请求使用不属于当前业务范围的公开身份，**When** 后端拒绝请求，**Then** 错误语义必须是不存在或无权限，而不是错误地否认父级对象身份。
3. **Given** 代码或接口暴露同一字段名表示两种身份，**When** 验收检查运行，**Then** 它必须报告该边界歧义。

### Edge Cases

- 验收环境无法启动真实数据库时，验收结果必须明确标记为未完成，而不是通过。
- 变更只影响纯计算逻辑且不触碰持久化、身份、迁移或发布路径时，可以不运行真实数据库验收，但必须有明确的范围判定。
- 旧数据存在可恢复和不可恢复记录混合时，验收必须同时证明可恢复记录可用、不可恢复记录被报告。
- 诊断输出必须足够定位问题，但不能泄露用户内容、私密文本或凭据。
- 验收命令本身缺失、不可执行或只运行了空测试集时，必须视为验收失败。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST define a backend verification gate for changes that affect persistence, identity resolution, migrations, deployment startup, or core learning data access.
- **FR-002**: The verification gate MUST include at least one restart-recovery scenario where data is created, persisted, the backend runtime is reconstructed, and the same user-visible workflow is opened again.
- **FR-003**: The verification gate MUST include real persistent storage validation for storage-affecting changes, including initialization, migration, write, restart read, and integrity reporting.
- **FR-004**: The verification gate MUST fail when the required persistent storage validation cannot run, unless the change is explicitly classified as outside persistence, identity, migration, startup, and core learning data scope.
- **FR-005**: The verification gate MUST distinguish normal unit or component tests from release-blocking smoke checks that cross process and storage boundaries.
- **FR-006**: The verification gate MUST verify identity invariants for user-visible workspace identities and internal storage identities on every covered workflow.
- **FR-007**: The verification gate MUST treat ambiguous identity naming in covered backend routes, contracts, diagnostic output, or persistence boundaries as a failure.
- **FR-008**: The verification gate MUST require actionable diagnostics for failed identity or recovery checks, including which object, relationship, storage structure, or permission boundary failed.
- **FR-009**: The verification gate MUST fail if a configured test command is missing, runs zero meaningful checks, or exits successfully while skipping a required scenario.
- **FR-010**: The verification gate MUST provide a documented operator command or checklist that maintainers can run before release without relying on private production credentials.
- **FR-011**: The verification gate MUST record what was actually run and what was not run, so "all tests pass" cannot hide missing smoke coverage.
- **FR-012**: The verification gate MUST avoid adding fallback, shim, legacy compatibility, or request-time repair behavior solely to make validation pass.

### Key Entities *(include if feature involves data)*

- **Verification Gate**: A release-blocking validation set that proves critical backend behavior across persistence, restart, identity, and diagnostics.
- **Restart-Recovery Scenario**: A workflow that creates user-visible data, persists it, reconstructs the backend runtime, and verifies the same workflow still works.
- **Persistent Storage Smoke**: A validation run against a real storage instance or equivalent production-shaped store, including initialization and migration.
- **Identity Invariant**: A rule that keeps public workflow identity distinct from internal storage identity throughout routing, storage, logs, and errors.
- **Validation Report**: A concise record of required checks, commands run, skipped checks, failures, and unresolved risks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every backend change touching persistence, identity, migration, startup, or core learning data, the required gate either passes all restart and storage checks or blocks release with a specific failure.
- **SC-002**: A deliberately broken restart-recovery relationship is detected by the gate before any user-facing workflow is manually exercised.
- **SC-003**: A deliberately broken storage schema or migration is detected by the gate during validation, with the failing structure named in the report.
- **SC-004**: Validation reports always list required checks, executed checks, skipped checks, and unresolved risks; missing required checks cannot be summarized as "all tests pass".
- **SC-005**: Covered identity workflows expose no ambiguous field name that can mean both public workflow identity and internal storage identity.
- **SC-006**: Maintainers can run the documented backend verification gate on a development machine without production credentials.

## Assumptions

- The target users are project maintainers preparing backend changes for local verification or release.
- The project will continue to keep fast unit tests, but those tests are not sufficient as release evidence for persistence or identity changes.
- Development machines can create an isolated local storage instance or use an equivalent non-production store for smoke validation.
- Production credentials are not required for routine verification gates.
- Some narrowly scoped changes may not require real storage smoke, but the exemption must be explicit and visible in the validation report.
