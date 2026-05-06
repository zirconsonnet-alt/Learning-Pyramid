<a id="plm"></a>

# PLM（Pyramid Learning Method）形式化定义集

<a id="toc"></a>

## 目录

- [0a. 符号与约定](#toc-0a)
- [0b. 事务与一致性公理](#toc-0b)
- [1. 静态对象模型（Engineering Spec）](#toc-1)
- [2. 事务协议（Transaction Protocols）](#toc-2)
- [3. 运行时调度原语（Runtime Scheduling Primitives）](#toc-3)
- [4. PLM 系统编排与聚合（System Orchestration \& Aggregation）](#toc-4)

---

<a id="toc-0a"></a>

## 0a. 符号与约定

0a.1 对列表 A 的长度记为 |A|。
0a.2 “序列”指有序列表；“队列”指先进先出列表。
0a.3 “层”记为 L；上层为 L+1，下层为 L-1。
0a.4 下文的 `layer_index` 是层的自然编号：`layer_index = 0` 对应最低层 `L0`；上层为 `layer_index+1`。
0a.5 “ID”均指系统内可稳定引用的唯一 ID 符。
0a.6 下文对象的“属性”分为核心属性与派生属性：核心属性用于对象的稳定引用与一致性要求；派生属性由核心属性解析、探测或映射得到，可缓存且允许滞后。
0a.7 凡出现对某仓库对象的 ID 引用，均要求在该对象提交生效时可在对应仓库解析到；若引用对象与被引用对象在同一次提交中一并提交，则视为可解析。

0a.8 语义类型约定：本规格书出现的 `xxxId` / `Enum` / `Scalar` 均为语义类型别名（底层实现可为 `str`/`int`/`datetime` 等）；字段类型一律使用语义类型，不再写裸 `ID`，也不在同一语义处混写 `str` 与 `xxxId`。

0a.9 ID 的规范文本与排序语义（强约束）

为避免“按 ID 升序/字典序排序”在不同底层类型（`str`/`int`/包装类型等）下产生可观察差异，本规格对所有 `xxxId` 的排序与比较口径写死如下：

* 规范文本：对任意 `xxxId` 值 `x`，其规范文本定义为 `id_canonical_text(x) -> str`。
  * `id_canonical_text(x)` 必须为**跨平台一致**、**不依赖 locale** 的确定性映射。
  * 实现必须保证：同一逻辑 ID 在系统内任意位置持久化/传输/日志展示/比较时使用同一规范文本（可通过“底层即用 str 存储”或“提供显式转换函数”实现）。
  * 强约束（写死；避免实现分叉）：若 `xxxId` 的底层承载为字符串，则该字符串本身即为规范文本；实现不得在 `id_canonical_text` 中做 Unicode 归一化、大小写折叠或 locale 相关转换。若实现采用 UUID/十六进制文本承载，则写入时必须规范化为小写，`id_canonical_text` 返回该小写文本。
* 排序语义：文中凡出现“按 `xxx_id` 升序”“按 `node_id` 字典序升序”等表述，均等价于：
  * 按 `id_canonical_text(xxx_id)` 的 **Unicode code point** 字典序升序排序。
  * 不做大小写折叠、不做自然数值排序、不使用 locale 相关 collation。
* `all()` 返回顺序（强约束）：凡出现 `all() -> Sequence[...]` 且未另行写死排序规则时，必须按该仓库主键 `id_canonical_text(primary_id)` 的 Unicode code point 字典序升序返回全量（见上文排序语义）。

0a.9a PurePath 的规范文本与排序语义（强约束）

为避免“按路径字典序排序”在不同实现下产生可观察差异，本规格对所有 `PurePath` 的排序与比较口径写死如下：

* 规范文本：对任意 `PurePath` 值 `p`，其规范文本定义为 `path_canonical_text(p) -> str`，且写死为：  
  - `path_canonical_text(p) := p.as_posix()`  
* 排序语义：文中凡出现“按 `relative_path` 升序”“按路径字典序升序”等表述，均等价于：  
  - 按 `path_canonical_text(p)` 的 **Unicode code point** 字典序升序排序；不做大小写折叠、不做自然数值排序、不使用 locale 相关 collation。

0a.10 Timestamp（时间戳）语义（强约束）

为避免 `created_at/executed_at` 等时间字段在不同实现间出现可观察差异，本规格写死 `Timestamp` 的来源与语义如下：

* 时区与表示：
  * `Timestamp` 必须为 UTC 时区语义的时间戳（不得使用本地时区）。
  * 实现可使用底层 `datetime`/`int`/`str` 等承载，但其语义必须等价于 UTC 时间点。
* 来源（强约束）：
  * 所有 `Timestamp` 值必须由系统时钟生成；系统对外接口不得接收调用方提供的 `Timestamp` 作为事实输入。
* 精度（强约束；写死）：
  * `Timestamp` 的最小精度为毫秒（ms）。实现可在内部以更高精度采样，但对外可观察值必须按毫秒语义一致解释。
* 单调性与相等（强约束）：
  * 不要求单调递增（允许回拨或相等）。
  * 在同一 mutation session 内生成的多个 `Timestamp` 允许相等。

0a.11 项目作用域唯一性约定（强约束）

* 除 `Project.project_id` 外，本规格中所有“`xxx_id` 唯一”“索引不变式：ID 唯一”等表述，默认均指在单个 `project_id` 作用域内唯一。
* `Project.project_id` 为系统级唯一标识。



0a.12 RichContent（富内容）语义（强约束）

为支持在 `RecallPoint` 等对象中同时承载“文本 + 图片”等富媒体内容，本规格定义以下值对象与语义类型：

* `MediaAssetId`：项目内可解析的富媒体资产 ID（见 1.9 MediaAsset）。
* `ContentBlockKind = {TEXT, IMAGE}`。
* `ContentBlock`：二元值对象（Value Object），满足以下其一：
  * `kind == TEXT` 且 `text: str` 非空（去除首尾空白后必须非空）；
  * `kind == IMAGE` 且 `asset_id: MediaAssetId` 非空。
* `RichContent = Tuple[ContentBlock, ...]`：有序序列；顺序为权威展示顺序。

写前条件（强约束；写死以避免实现分叉）
* 任一 `RichContent` 不得为空 Tuple。
* 任一 `ContentBlock(kind=TEXT)` 的 `text` 去除首尾空白后必须非空。
* 任一 `ContentBlock(kind=IMAGE)` 的 `asset_id` 必须能在 `MediaAssetRepository` 中解析到；若不可解析必须视为写前条件失败（`PreconditionFailure`，0b.5）。

非目标
* 富媒体二进制内容的可达性/完整性不得进入系统级 `commit()` 的提交期强制集合（0b.7.1/0b.7.2）；如需校验只能通过显式校验接口扩展实现。

本规格出现的常用语义类型（非穷尽，但应覆盖全文使用）：

* ID 类（`xxxId` 或同类标识符）：`ProjectId`、`InstanceId`、`LearningObjectNodeId`、`RecallPointId`、`LearningTaskId`、`LearningTaskNodeId`、`RangeId`（实现可复用旧 `FocusSetId` 的底层类型）、`ReviewTaskId`、`ConvergenceId`、`ConvergenceRuleId`、`ReviewChainId`、`ReviewTaskQueueId`、`LayerId`、`DimensionId`、`JudgementOptionId`、`AggregationEventId`（4.4.5）、`MediaAssetId`、`AsrArtifactId`、`TempContextFragmentId`、`QASessionId`、`CandidateRecallPointId`、`MemoryCanvasId`、`MemoryCanvasVersionId`、`CanvasEdgeId`、`StoryArtifactId`。
* 枚举类（`Enum`）：`ProjectState`、`ProjectType`、`RecallPointState`、`LayerMode`、`ContentBlockKind`、`ReviewChainTemplateItemKind`。
  * 增补：`InstancePresence`、`FsSyncPolicy`、`MaterialSourceKind`、`ClientRuntimeKind`、`RuntimeCapability`、`CandidateRecallPointState`。
* 标量/值域类（`Scalar`）：`PurePath`、`Timestamp`、`LabelVector = {0,1}^{|D|}`（判别映射的值域；等价表示为长度为 `|D|` 的 0/1 向量）、`RichContent`、`ContentBlock`、`ReviewChainTemplate`、`ReviewChainTemplateItem`、`LayerConfig`。
* 校验结果类（`Result`）：`ValidationResult`、`ValidationCode`（0b.7.2/0b.7.3）。

枚举/常量取值清单：

* `ProjectState = {ACTIVE, DELETED}`
* `ProjectType = {COURSE, BOOK, LOOSE_POINTS}`
* `RecallPointState = {ACTIVE, DELETED}`
* `ReviewTaskState = {PENDING, DONE}`（3.1）
* `ConvergenceState = {IN_PROGRESS, TERMINATED}`（3.2）
* `ReviewChainState = {IN_PROGRESS, TERMINATED}`（3.3）
* `AggregationCycleState = {CLEARING, ROLL_UP, DONE}`（4.4.3）
* `LayerMode = {AUTO_TICK_ON_ENTRY, MANUAL_TICK_ON_ENTRY}`（4.2.4）
* `GLOBAL_QUEUE: ReviewTaskQueueId`（系统常量；3.4.2 / 4.1.2）
* `ValidationCode = {OK, NOT_FOUND, UNREACHABLE, INVALID_INPUT}`（0b.7.2/0b.7.3）
* `ContentBlockKind = {TEXT, IMAGE}`（0a.12）
* `ReviewChainTemplateItemKind = {CONVERGENCE, REVIEW_TASK}`（1.0.5 / 4.3.2）
* `AuditEventKind = {PROJECT_CREATED, PROJECT_DELETED, EDIT_PROJECT, ADD_INSTANCE, ADD_LEARNING_OBJECT_LEAF, ADD_LEARNING_OBJECT_CONTAINER, SYNC_LEARNING_OBJECTS_FROM_FS, SET_PROJECT_MATERIAL_SOURCE_BINDING, BIND_NATIVE_LOCAL_ROOT, BULK_REMAP_RECALL_POINTS_INSTANCE, SUBMIT_LEARNING_TASK, EDIT_RECALL_POINT, DELETE_RECALL_POINT, EDIT_LEARNING_TASK, EDIT_PROJECT_CONFIG, EXECUTOR_COMMIT_REVIEW_TASK, MANUAL_ROLL_UP, REQUEST_ASR, EXTRACT_TEMP_CONTEXT_FRAGMENT, REQUEST_LOCAL_LLM, CREATE_QA_SESSION, GENERATE_CANDIDATE_RECALL_POINT, ACCEPT_CANDIDATE_RECALL_POINT, REJECT_CANDIDATE_RECALL_POINT, CREATE_MEMORY_CANVAS, SAVE_MEMORY_CANVAS_VERSION, SET_CANVAS_EDGES, GENERATE_STORY_ARTIFACT}`（4.6；最小集合；实现可在保持兼容前提下增补，但不得改变既有值语义）
* `AuditResultCode = {OK}`（1.8 / 4.6；本规格仅强制记录成功提交的审计事件）
* `SessionMode = {READ_ONLY, READ_WRITE}`（0b.1.6）

* `InstancePresence = {PRESENT, MISSING}`（1.1.1）
* `FsSyncPolicy = {DISABLED, STARTUP_SYNC, MANUAL_SYNC}`（1.0.4 / 0b.1.5b / 4.5）
* `MaterialSourceKind = {SERVER_FS, BROWSER_LOCAL, NATIVE_LOCAL, MANUAL}`（1.0.4a / 0b.1.5b / 4.5）
* `ClientRuntimeKind = {MOBILE_WEB, DESKTOP_WEB, DESKTOP_NATIVE}`（0b.1.6 / 1.0.5 / 2 / 4.5）
* `RuntimeCapability = {VIDEO_PLAYBACK, LIGHT_REVIEW, NATIVE_FS_BINDING, LOCAL_ASR, LOCAL_LLM_QA, LOCAL_RECOMMENDER, MEMORY_CANVAS_EDIT, STORY_GENERATION}`（0b.1.6 / 1.0.5 / 2 / 4.5；兼容说明：`LOCAL_LLM_QA` / `LOCAL_ASR` 保留旧名，其语义分别为“当前运行时可通过已配置 LLM 服务完成问答”与“当前运行时可通过已配置 ASR 服务完成转写”，二者都不要求模型部署在用户本机；但现行产品的播放器字幕与 LLM 补充上下文主路径不得再依赖 `LOCAL_ASR`，而应优先检查视频同目录同名字幕文件）
* `CandidateRecallPointState = {PENDING, ACCEPTED, REJECTED}`（1.11c / 2.12 / 2.13 / 2.14）

---

<a id="toc-0b"></a>

## 0b. 事务与一致性公理

0b.0 适用范围（强约束）

本规格的第 0a 章（符号与约定）与第 0b 章（事务与一致性公理）为全局公理层，对全文所有章节、所有仓库与协议默认生效。  
后续章节中若未显式重复描述，则视为自动继承本两章的定义、语义与约束。  
任何后续章节不得与本两章冲突；若出现冲突，以第 0b 章为准（第 0a 章提供符号解释）。  

项目作用域继承声明（强约束）  
除 `ProjectRepository` 外，全文所有仓库与协议默认在 `session.project_id` 作用域内定义与执行；后续章节若未显式写出 `project_id`，均视为由 `MutationSession.project_id` 隐式确定。

0b.1 修改会话（mutation session）/提交（commit）：系统采用“显式会话 + 显式提交”的事务模型（强约束：系统级事务）。

强约束（必须写死；用于消除实现分叉）  
* mutation session/`commit()` 的作用域为**系统级事务**：一次 mutation session 覆盖本系统内所有仓库/子系统的写入暂存（staged），`commit()`/`rollback()` 对整组变更一次性生效或一次性回滚。  
* 各仓库不得提供“独立于系统事务”的 `commit()` 语义；仓库仅作为同一系统级 mutation session 的参与者。  

0b.1.1 仓库接口与会话上下文的绑定口径（强约束；用于避免实现分叉）

强制形态（必须写死；用于消除实现分叉）
* 所有仓库读写接口必须**显式接收** `session: MutationSession` 参数；任何不携带 `session` 的仓库读写接口不得存在。
* 禁止使用线程局部变量 / 全局上下文 / 隐式“当前 session”绑定来传递会话；仓库不得通过隐式上下文推断 `session`。
* 所有仓库写操作（例如 `add/update/replace/push_up/...`）必须在某个**系统级** mutation session 上下文中执行；写入进入该会话的 staged 暂存区，并受本章提交/回滚语义约束。  
* 仓库读操作也必须显式携带 `session` 执行；其可见性/隔离级别必须严格遵循 0b.2。
* 任何实现不得在读路径或写路径引入隐式修复、隐式校验或隐式提交；所有状态改变必须通过显式写入接口并受同一事务语义约束（见 0b.1.1 / 0b.1.2）。
* 唯一例外（强约束）：`System.begin_session(...)` 在创建 `MutationSession` 之前执行的“项目存在性/状态检查”（见 0b.1.6）不属于仓库读写接口调用，不受“仓库接口必须显式接收 session”约束。除该检查外，系统内任何仓库读写接口仍必须显式接收 `session: MutationSession`，不得使用隐式上下文。

0b.1.1a 可观测性旁路输出（Observability Side-Channel）例外（强约束）

为满足审计/调试/运维观测需求，系统允许在任意入口路径（含 READ_ONLY 与失败路径）输出仅用于可观测性的旁路日志/指标（例如 stdout、文件 append、外部 log sink/metrics sink）。其语义写死如下：

* 旁路输出不属于任何仓库对象：不得写入任一可枚举事实源仓库，不进入 0b.1 的系统级事务覆盖范围，不参与 staged/commit/rollback。
* 旁路输出不得影响业务语义：不得改变任何业务事实对象的语义、门禁结果或调度推进结果；其失败不得改变对外返回值或错误语义。
* 旁路输出必须 best-effort：允许丢失；READ_ONLY 入口不得因旁路输出而阻塞或升级为写事务。
* 说明（边界澄清）：4.6 `AuditLogEvent` 属于持久化审计对象，必须遵循系统级事务语义与 READ_ONLY 不可写约束；不得将其实现为旁路输出的替代品，也不得在 READ_ONLY 路径中“偷偷落库”。

工程承载形态（强约束；用于避免 API 层形态分叉）

- “显式接收 `session: MutationSession` 参数”的工程实现可以采用以下任一等价承载形态：
  - 过程内调用：以函数/方法参数显式传递 `session` 对象或 `session_id`（可解析到唯一 `MutationSession`）。
  - HTTP API：允许使用请求头（例如 `X-Session-Id`）携带 `session_id` 作为显式 session 参数的承载；该 header 的语义与函数参数 `session_id` 等价，不得引入任何“隐式当前会话”或线程/协程本地上下文。
- 约束：凡通过 `session_id` 承载 session 的对外入口，必须在该入口执行的第一时间解析并绑定到唯一 `MutationSession`；若不可解析或不唯一则拒绝。
- 约束：`session_id` 承载形态不得改变任何事务语义（0b.1.2/0b.1.3）与关闭态语义（0b.1.4）。

0b.1.2 会话与回滚语义（强约束）

* 仓库允许在一次 mutation session 内执行多次写操作（写入进入会话暂存区，staged）。
* 会话内中间态允许暂时不满足跨节点结构约束。
* `commit()` 时对整组变更后的最终态一次性校验；若校验失败则整组变更不生效（回滚到会话开始前状态）。
* 回滚语义：`rollback()` 使会话内所有 staged 写入失效，对外可见状态恢复为会话开始前的已提交状态。
* 系统不得在读路径触发隐式修复；所有“修复/纠错”必须由显式写入接口产生，并受同一事务语义约束。

0b.1.3 会话状态机（强约束；用于上层协议可控与重试语义统一）
会话状态 `SessionState ∈ {OPEN, COMMITTED, ROLLED_BACK, FAILED}`，其语义与转移为：

* 初始：`OPEN`
* `commit()` 成功：`OPEN -> COMMITTED`，并立即进入关闭态（等价 closed）。
* `rollback()` 成功：`OPEN -> ROLLED_BACK`，并立即进入关闭态（等价 closed）。
* `commit()` 失败（任意异常导致提交未生效）：`OPEN -> FAILED`，并立即进入关闭态（等价 closed）。

  * 强制：FAILED 后不得继续在该会话上执行任何读写或再次 commit/rollback；若需要重试必须开启新会话。
  * 说明：此规则的目的，是避免“失败后仍可继续操作”的不确定性，确保协议可重复执行与易推理。

0b.1.4 关闭态上的非法调用（强约束）

* 在 `COMMITTED/ROLLED_BACK/FAILED` 状态上再次调用 `commit()` 或 `rollback()`，必须抛 `SessionClosedError`。
* 在关闭态（`COMMITTED/ROLLED_BACK/FAILED`）上，禁止一切读写操作；任何仓库读写调用与任何会话内读写调用必须抛 `SessionClosedError`。

0b.1.5 系统引导（Bootstrap）（强约束；用于消除“首次提交悖论”）

为保证 0b.7.1 中提交期强制集合在第一次对外可写事务上即可被一致强制，本规格写死系统必须存在一个确定的 bootstrap 阶段，其语义如下：

* 系统必须在对外提供任何可写接口之前完成 bootstrap。
* bootstrap 的最小产物（强约束）：
  * 用于提交期强制校验的事实源仓库（至少包含：`ReviewTaskQueueRepository`、`LayerRepository`、`EntryRegistryRepository`、`ReviewTaskRepository`、`ReviewChainRepository`、`LearningTaskNodeRepository`）必须已可用（允许为空集合，但不得“不存在/不可枚举”）。
* bootstrap 的执行方式（强约束；写死可测试口径）：
  * bootstrap 必须通过一次系统内部 mutation session + `commit()` 完成并成功；该内部提交不得依赖用户输入。
  * 若 bootstrap 未完成或失败，系统不得对外开放任何可写入口；不得允许用户触发 mutation session。

0b.1.5a 项目引导（Project Bootstrap）（强约束）

* 系统必须提供项目创建流程；每个新建 `Project(project_id)` 在创建成功的同一系统事务内必须完成该项目的 bootstrap。
* 项目 bootstrap 的最小产物（强约束）：
  * 在 `project_id` 作用域内持久化且仅持久化一条 `ReviewTaskQueue` 记录，满足 `queue_id == GLOBAL_QUEUE`。
  * 在 `project_id` 作用域内持久化且仅持久化一条 `ProjectStorageConfig` 记录，且 `project_root` 非空、`learning_object_root` 非空（见 1.0.4）。
  * 在 `project_id` 作用域内持久化且仅持久化一条 `ProjectMaterialSourceBinding` 记录；其默认值必须写死为 `source_kind == SERVER_FS`，但若 `create_project(...)` 显式指定初始材料源类型，则必须写入该显式值（见 1.0.4a / 4.5）。
* 在 `project_id` 作用域内持久化且仅持久化一条 `ProjectConfig` 记录（见 1.0.5）；其默认值必须写死为：  
  - `project_type == COURSE`，但若 `create_project(...)` 显式指定 `initial_project_type`，则必须写入该显式值；并且：
    - 当 `project_type == BOOK` 时，`ProjectMaterialSourceBinding.source_kind` 必须为 `MANUAL`；
    - 当 `project_type == LOOSE_POINTS` 时，`ProjectMaterialSourceBinding.source_kind` 必须为 `MANUAL`；
  - `layer_index = 0` 的 `review_chain_template == [CONVERGENCE]`（等价于 4.3.2 的默认行为）；  
  - `layer_index = 0` 的 `aggregation_threshold == (K_node=10, K_point=200)`（用于初始化 Layer 的控制字段；聚合时读取 Layer 当前值，见 4.4.2）。  
  - `layer_index = 0` 的 `threshold_roll_up_enabled == true`（达到阈值时默认允许自动上推，见 4.4.2）。  
  - `push_config.min_recall_points_to_enable == 0`、`push_config.max_history_len == 20`、`push_config.recommended_batch_size == 20`、`push_config.forgetting_curve_decay_per_day == 0.20`（见 1.0.5）。  
* `NativeRuntimeConfig / LocalModelConfig` 不属于项目 bootstrap 最小产物；其属于调用端运行时配置，不得持久化进 `ProjectConfig`，也不得作为 `create_project(...)` 成功提交的前置条件。
  * 在 `project_id` 下初始化且仅初始化 `layer_index = 0` 的 `Layer`（4.2.5）；其默认值必须写死为：  
    - `layer_mode = AUTO_TICK_ON_ENTRY`  
    - `orchestrator_managed_review_chain_ids = ()`（空 Tuple）  
    - `K_node = 10, K_point = 200`（与 1.0.5 的默认阈值一致）  
    - `aggregation_cycle_state = DONE`（若实现持久化该字段；若未持久化则可视为派生初态，但对外可观察行为必须一致）  
  * 在 `project_id` 下初始化且仅初始化 `layer_index = 0` 的 `AggregationQueue`（4.4.1），其初态必须为：  
    - `node_ids = ()`  
    - `head_index = 0`
* 若项目 bootstrap 失败，则 `Project` 不得进入 `ACTIVE` 的已提交状态（项目创建整体回滚）。

0b.1.5b 项目材料源同步/导入（Project Material Source Sync / Import）（强约束）

目的  
当项目启用“材料源同步/导入”能力时，系统必须将该项目当前 `ProjectMaterialSourceBinding` 指向的权威材料源视为 `LearningObjectNode` 树与 `Instance` 集合的唯一结构事实源。0b.1.5b 协议负责把材料源快照归一化为相对路径集合，并据此原子重建学习对象树、创建新增 `Instance`、以及将未再出现的 `Instance` 标记为 `MISSING`。  
当 `source_kind == MANUAL` 时，本协议不适用；该项目的 `LearningObjectNode/Instance` 仅通过 4.5 的显式手工写入口维护，系统不得为其假定任何文件系统或浏览器目录快照。  

术语（强约束）  
- `source_kind == SERVER_FS`：权威材料源为服务端本地目录 `resolve(project_root / learning_object_root)`。  
- `source_kind == BROWSER_LOCAL`：权威材料源为“当前浏览器中已授权并绑定到该项目的本地目录快照”；服务端不得持久化该本地目录的绝对路径，只能接收其显示标签 `source_root_label/root_title` 与一组相对文件路径作为显式导入输入。  
- `source_kind == NATIVE_LOCAL`：权威材料源为 `DESKTOP_NATIVE` 运行时已稳定绑定的本地目录快照；系统可持久化其 `source_root_label`，但不得把绝对路径、操作系统目录句柄或 Native 专有授权令牌写入 `ProjectConfig` 或其他项目事实；这些仅属于 `NativeRuntimeConfig`。  
- `source_kind == MANUAL`：权威材料集合与学习对象树由显式手工写入口维护；`material_id`/`relative_path` 可为项目内稳定的虚拟标识，不要求对应任何可达本地文件。  
- 下文凡称“项目启用 0b.1.5b 协议”，均指：`ProjectMaterialSourceBinding.source_kind` 指向的权威材料源处于启用状态；其中 `SERVER_FS` 的启用条件为 `ProjectStorageConfig.fs_sync_policy != DISABLED`，`BROWSER_LOCAL` 仅允许通过显式导入入口触发，`NATIVE_LOCAL` 仅允许通过 `DESKTOP_NATIVE` 运行时显式绑定/同步入口触发，`MANUAL` 永远不构成“启用 0b.1.5b 协议”。  

一致性与原子性（强约束）  
- 同步/导入必须通过一次系统内部 `MutationSession(project_id, READ_WRITE)` + 单次 `commit()` 原子完成；任一步失败则整体回滚，对外不可见（0b.1.2）。  
- 同步/导入不得触发任何调度推进副作用：不得调用 Task Register / Orchestrator Tick / ReviewChain Step / Convergence Step，且不得创建/入队任何 `ReviewTask`（4.5 的 `SCHEDULING_EFFECT = NONE`）。  
- 同步/导入属于“显式协议写入”，并非 0b.7.1 的提交期强制校验扩展；系统级 `commit()` 的强制集合闭包保持不变（0b.7.1）。  

触发策略（写死）  
- 当 `source_kind == SERVER_FS` 时：  
  - 若 `ProjectStorageConfig.fs_sync_policy == DISABLED`：系统不得执行任何自动同步；`LearningObjectNode/Instance` 仅通过显式写入口变更。  
  - 若 `ProjectStorageConfig.fs_sync_policy == STARTUP_SYNC`：系统在对外开放该项目任何 `READ_WRITE` 写入口之前，必须对该项目执行一次同步（可与系统 bootstrap 同阶段）。  
  - 若 `ProjectStorageConfig.fs_sync_policy == MANUAL_SYNC`：系统启动时不得自动同步，但必须提供 4.5 的 `sync_learning_objects_from_fs(...)` 对外入口供用户显式触发。  
- 当 `source_kind == BROWSER_LOCAL` 时：  
  - 系统启动时不得把服务端 `project_root / learning_object_root` 误当作该项目的权威材料源做隐式扫描。  
  - 系统启动时不得因为“浏览器本地目录尚未重新授权/当前无导入输入”而拒绝项目进入可读写就绪态；若此前已有已提交导入结果，则必须继续把该结果视为当前已提交事实。  
  - 系统必须仅通过 4.5 的 `import_learning_objects_from_browser_scan(...)` 对外入口接收浏览器侧显式导入输入；不得为 `BROWSER_LOCAL` 提供启动期自动同步。  
- 当 `source_kind == NATIVE_LOCAL` 时：  
  - 系统启动时不得把服务端 `project_root / learning_object_root` 误当作该项目的权威材料源做隐式扫描。  
  - 系统不得要求 `MOBILE_WEB` / `DESKTOP_WEB` 提供 Native 目录绑定能力；对非 `DESKTOP_NATIVE` 运行时只能读取既有已提交事实。  
  - 系统必须仅通过 4.5 的 `sync_learning_objects_from_native_scan(...)` 或把 `source_kind` 显式切换为 `NATIVE_LOCAL` 的入口接收 Native 目录快照；不得为 `NATIVE_LOCAL` 提供服务端启动期自动同步。  
- 当 `source_kind == MANUAL` 时：  
  - 系统不得执行任何自动同步或隐式导入。  
  - 系统不得把 `project_root / learning_object_root`、浏览器授权目录、或其他外部目录误当作该项目的权威材料源。  
  - 已提交的 `LearningObjectNode/Instance` 必须持续作为当前事实，直到用户通过 4.5 的显式手工写入口修改它们。  

`SERVER_FS` 输入语义（强约束）  
- 扫描根目录 `abs_root := resolve(project_root / learning_object_root)`；其中 `project_root` 来自 `ProjectStorageConfig.project_root`（1.0.4）。  
- `learning_object_root` 必须位于 `project_root` 下，且不得包含 `..` 语义（1.0.4）。  
- 对 `STARTUP_SYNC` 项目，系统在尝试同步前必须先判定 `abs_root` 的根目录状态：  
  - 若 `abs_root` 不存在：必须拒绝该项目进入“可提供 READ_WRITE 写入口”的就绪态，并返回 `NotFound`（或实现定义的等价明确错误）；不得将其视为空目录，不得隐式创建目录，不得跳过同步。  
  - 若 `abs_root` 存在但不是目录：必须拒绝同步并返回 `PreconditionFailure`（或实现定义的等价明确错误），且不得产生任何 staged 写入。  
  - 若访问 `abs_root` 发生权限/I/O 错误：必须拒绝同步并返回明确错误，且不得产生任何 staged 写入。  
- 上述口径同样适用于对外入口 `sync_learning_objects_from_fs(project_id)`；实现不得对 `STARTUP/MANUAL` 两条路径采用不同根目录判定语义。  
- 必须忽略（不纳入同构判定、不生成节点、不生成 `Instance`）所有以 `.` 开头的文件或目录条目（例如 `.DS_Store`、`.git/` 等）。  
- 空目录处理（强约束）：必须将空目录纳入扫描并生成对应的 `LearningObjectContainer`（其 `children` 允许为空）。  
- 符号链接/快捷方式（强约束）：扫描若遇到符号链接条目（无论指向文件或目录），必须拒绝同步并返回错误，且不得产生任何 staged 写入（0b.5）。建议错误名：`UnsupportedFilesystemEntryError`（实现可复用 `DirectoryStructureCorruptedError`，但必须在错误摘要中指明“符号链接不受支持”与具体路径）。  
- 非普通文件/目录（设备文件、管道等）：必须拒绝同步并返回错误，且不得产生任何 staged 写入（0b.5），并在错误摘要中列出条目路径与类型。  
- 目录树与 `LearningObjectNode` 树必须严格同构：每个目录对应一个 `LearningObjectContainer(relative_path=dir_rel_path)`；每个文件对应一个 `LearningObjectLeaf(relative_path=file_rel_path)`；层级关系与直接孩子集合必须严格对应“文件系统直接子条目”。  

`BROWSER_LOCAL` 输入语义（强约束）  
- 4.5 的显式导入入口必须接收：  
  - `root_title: Optional[str]`：当前浏览器已授权目录的显示名；仅用于 UI/审计摘要。  
  - `relative_file_paths: Sequence[PurePath | str]`：相对当前浏览器已授权目录根的文件路径集合。  
- 对任一 `relative_file_paths[i]`，系统必须先执行以下规范化，再进入导入协议：  
  - 将 `\` 统一替换为 `/`；  
  - 拒绝空串、绝对路径、盘符路径；  
  - 以 `PurePosixPath` 解析；  
  - 规范化后必须仍为非空相对路径，且任一路径组件不得为 `""`、 `"."` 或 `".."`；  
  - 最小实现仅允许受支持的媒体文件扩展名：`.mp4`、`.mov`、`.mkv`、`.webm`、`.mp3`、`.wav`、`.m4a`、`.aac`、`.flac`、`.ogg`、`.opus`。  
- 规范化后的 `relative_file_paths` 必须按集合语义去重；完全重复的相对路径不得生成重复节点或重复 `Instance`。  
- `relative_file_paths` 为空时，导入入口必须拒绝执行并返回明确的 `PreconditionFailure`；最小实现不得把“空导入”解释为清空项目材料树。  
- `BROWSER_LOCAL` 的目录集合定义为：所有文件路径的父目录闭包再加根目录 `.`；最小实现中，未被任何文件覆盖到的空目录不属于权威结构源。  
- `BROWSER_LOCAL` 的权威 `LearningObjectNode` 树按直接目录结构构造：  
  - 每个目录 `dir_rel_path` 生成一个 `LearningObjectContainer(relative_path=dir_rel_path)`；  
  - 目录的直接子目录与直接文件都直接挂在该目录容器之下；  
  - 根容器的 `title` 必须取 `root_title.strip()`，若为空则回退为 `"已授权目录"`；非根目录容器的 `title` 必须等于目录名。  
- 顺序口径（强约束；按最小实现写死）：  
  - 对任一目录容器，其 `children` 必须按直接孩子 `relative_path.as_posix()` 的 Unicode code point 字典序升序排列。  

`NATIVE_LOCAL` 输入语义（强约束）  
- 4.5 的 Native 同步入口必须接收：  
  - `root_title: Optional[str]`：Native 运行时当前稳定绑定目录的显示名；仅用于 UI 与审计摘要。  
  - `relative_file_paths: Sequence[PurePath | str]`：相对该 Native 目录根的文件路径集合。  
- `relative_file_paths` 的规范化、去重、扩展名限制、路径文本规则、大小写冲突处理、ID 生成与 `BROWSER_LOCAL` 完全一致；实现不得对 `NATIVE_LOCAL` 另起一套路径语义。  
- `NATIVE_LOCAL` 不要求用户在每次会话中重新授权同一稳定目录；但“稳定目录绑定”本身只属于 `DESKTOP_NATIVE` 运行时配置，不得被写入 `ProjectConfig`。  
- `NATIVE_LOCAL` 的权威 `LearningObjectNode` 树采用与 `BROWSER_LOCAL` 相同的“目录容器 + 直接孩子”口径；实现不得在同一项目中对这两类本地目录快照采用不同的树形派生规则。  

路径文本与跨平台一致性（强约束；写死）  
- 对任意材料源输入得到的 `rel_path`，其权威路径文本均定义为 `rel_path.as_posix()`；系统不得对路径做 Unicode `NFC/NFD` 归一化或 locale 相关变换（按 Unicode code point 原样处理）。  
- 大小写语义（强约束）：路径比较按 code point 区分大小写；若底层材料源或输入清单导致出现“仅大小写不同但不可共存/不可区分”的冲突，同步阶段必须拒绝并返回冲突列表（不产生任何写入）。  

ID 生成（强约束；用于稳定引用）  
- 定义（强约束；写死以避免实现分叉）  
  - 令 `path_text(rel_path) := rel_path.as_posix()`。  
  - 令 `fs_hash32(rel_path) := sha256(path_text(rel_path).encode('utf-8')).hexdigest()[:32]`。  
    - 约束：`hexdigest()` 必须为小写十六进制；截断长度必须固定为 32。  
  - `id_from_rel_path(rel_path) := InstanceId('instfs_' + fs_hash32(rel_path))`。  
- `node_id_from_rel_path(rel_path, kind)`：  
    - 若 `kind == LEAF`：`LearningObjectNodeId('lonfs_leaf_' + fs_hash32(rel_path))`；  
    - 若 `kind == DIR`：`LearningObjectNodeId('lonfs_dir_' + fs_hash32(rel_path))`。  
- 对任一同步得到的文件 `rel_path`，其 `instance_id` 必须等于 `id_from_rel_path(rel_path)`。  
- 对任一同步得到的目录/文件 `rel_path`，其 `node_id` 必须等于 `node_id_from_rel_path(rel_path, kind)`。  
- 强约束：在启用 0b.1.5b 同步协议的项目内，系统不得允许用户通过 `add_learning_object_leaf/container` 任意指定 `node_id`；相关入口必须拒绝或仅作为调试入口存在且默认关闭（4.5）。  

同步写入产物（同一 commit 生效）  
(1) `Instance` 同步（文件 -> Instance）  
- 对每个同步得到的文件条目 `rel_path`：  
  - 若 `Instance(instance_id=id_from_rel_path(rel_path))` 不存在则创建；其 `material_id` 必须等于 `rel_path`（`PurePath`）。  
  - 将其 `presence := PRESENT`，并写入 `last_seen_at := now_utc_ms()`。  
- 对任何“本次未出现在权威材料源快照里，但已存在于 InstanceRepository”的 `Instance`：不得删除；必须将其 `presence := MISSING`（并可选择不更新 `last_seen_at`）。  
- 实现可保留“当前材料文件暂不可访问 / 权限受限 / 运行时暂不可播放”等运行时状态，但这些状态不得反写为 `presence == MISSING`；`MISSING` 仅表示“最近一次成功同步/导入的权威材料源快照中已不存在该路径”。  

实现形态约束（强约束；写死以避免分叉）  
- 系统必须以幂等方式写入 `Instance` 同步产物；推荐以以下等价接口承载（实现可不同名，但语义必须等价且可测试）：  
  - `InstanceRepository.upsert_from_fs(session: MutationSession, instance_id: InstanceId, material_id: PurePath, presence: InstancePresence, last_seen_at: Optional[Timestamp]) -> None`  
    - 对同步得到的文件：必须写入（或覆盖保持一致）`material_id == rel_path`、`presence := PRESENT`、`last_seen_at := now_utc_ms()`。  
    - 对已存在但未再出现：必须写入 `presence := MISSING`；`last_seen_at` 不得更新（保持既有值或为 `None`）。  
- 任一 I/O 错误或结构损坏导致同步失败时：上述任何 staged 写入必须为无（0b.5）。  

(2) `LearningObjectNode` 同步（目录树 -> LearningObjectNode 树）  
- 系统必须以“全量替换”方式写入 `LearningObjectNode` 集合：以 0b.1.5b 协议产出的权威结构结果重建该项目在 `LearningObjectNodeRepository` 下的全部节点（见 1.2.2 `replace_all_from_fs`），确保最终态满足 1.2.3 的树一致性校验。  
- `LearningObjectLeaf.instance_id` 必须等于其对应文件条目的 `instance_id`。  
- `SERVER_FS` 生成的 `Container.children` 顺序写死为：按 `child.relative_path.as_posix()` 的 Unicode code point 字典序升序排列（跨平台一致；见 0a.9a）。  
- `BROWSER_LOCAL` 生成的 `Container.children` 顺序写死为：按直接孩子 `relative_path.as_posix()` 的 Unicode code point 字典序升序排列。  

失败语义（强约束）  
- 目录结构损坏：必须拒绝同步且不产生任何写入（0b.5）。  
- 其他 I/O 错误、权限失败、非法导入输入或材料源不可达：必须拒绝同步/导入且不产生任何写入；系统可返回错误摘要，但不得留下部分更新。  

0b.1.6 会话创建入口（强约束；用于消除 API 形态分叉）

本规格写死系统对外开启会话的唯一入口为：

- `System.begin_session(project_id: ProjectId, mode: SessionMode) -> MutationSession`

并补充强约束（写死；用于消除实现分叉）：
* `MutationSession` 必须绑定只读字段 `project_id: ProjectId`。
* `MutationSession` 还必须绑定只读字段 `runtime_kind: ClientRuntimeKind` 与 `runtime_capabilities: FrozenSet[RuntimeCapability]`；二者来自当前调用端运行时上下文，只用于门禁与能力判定，不属于任何项目持久化事实。
* `System.begin_session(project_id, mode)` 在返回 session 之前，必须先在系统内部已提交基线视图下完成项目存在性检查：判定 `project_id` 对应的 `Project` 可解析且 `state == ACTIVE`；否则必须抛 `NotFound`。
  * 该检查是 `begin_session` 的系统级引导检查（bootstrap/readiness check），不得通过任何“要求显式 session 参数”的仓库接口执行。
  * 强约束：该检查只读取已提交状态（baseline），不得观察任何未提交写入，不得产生任何 staged 写入，不得触发隐式修复或隐式校验。
  * 强约束：完成该检查后，`System.begin_session(...)` 才可创建并返回 `MutationSession`。返回的 `MutationSession.project_id` 必须等于调用参数 `project_id`。
* 所有仓库读写、查询、提交期强制校验、显式校验，均只允许访问 `session.project_id` 作用域内的数据；不得跨项目读写或跨项目解析引用。

其中 `SessionMode = {READ_ONLY, READ_WRITE}`。

READ_WRITE（读写会话；强约束）
* `System.begin_session(project_id, READ_WRITE)` 必须尝试获取全局写锁。
  * 若当前已存在 `OPEN` 的 READ_WRITE 会话：必须立即抛 `ConcurrencyConflictError`，且不得产生任何写入。
* single-writer 只约束 READ_WRITE：任意时刻最多存在一个 `OPEN` 的 READ_WRITE 会话（见 0b.4）。
* READ_WRITE 会话允许 staged 写入与 `commit()/rollback()`（见 0b.1.2/0b.1.3）。
* 写锁释放（强约束）：READ_WRITE 会话在进入关闭态（`COMMITTED/ROLLED_BACK/FAILED`）时必须释放全局写锁。

READ_ONLY（只读会话；强约束）
* `System.begin_session(project_id, READ_ONLY)` 不得获取全局写锁，且不得因存在 `OPEN` 的 READ_WRITE 会话而抛 `ConcurrencyConflictError`。
* `System.begin_session(project_id, READ_ONLY)` 不得因写锁/写会话而阻塞；其返回不得等待 READ_WRITE 会话结束。
* READ_ONLY 会话不得产生任何 staged 写入：
  * 任一仓库写接口在 READ_ONLY session 上被调用时，必须抛 `PreconditionFailure`，且不得产生任何 staged 写入；会话必须保持 `OPEN`。
* READ_ONLY 会话的关闭：
  * 调用 `rollback()` 必须将其置为 `ROLLED_BACK` 并进入关闭态。
  * 调用 `commit()` 必须抛 `PreconditionFailure`；该失败属于 `commit()` 失败路径，因此会话进入 `FAILED` 并进入关闭态（见 0b.1.3）。

读视图与 baseline/overlay 的 API 形态（强约束；写死）
* 本规格不提供“单独的 baseline read API”或“单独的 overlay read API”；两者通过同一组仓库读接口实现。
* baseline vs overlay 的判定口径写死如下：
  * READ_ONLY 会话：所有读均为 baseline read（只观察已提交基线）。
  * READ_WRITE 会话：读视图为 overlay read（固定已提交基线 + 本会话 staged；read-your-writes）。当本会话尚无 staged 写入时，该 overlay 视图与 baseline 视图等价。

0b.2 读视图语义：对外可见性 vs 会话内自洽（强约束；用于消除歧义）
本规格区分两类读取（均必须显式携带 `session: MutationSession`，见 0b.1.1）：

(1) 基线读（baseline read；无 staged）

* 读取仅能观察到“已提交状态”（已提交基线）。
* 不观察到任何并发事务的未提交写入。
* 不触发隐式修复。

(2) 会话内叠加读（in-session overlay read；含 staged）

* 会话内读必须一致：基于一个固定的“已提交基线”并叠加本会话 staged 写入（read-your-writes），且不观察到其他并发提交。
* 等价表述：会话内读视图 = 固定的已提交基线 + 本会话 staged 写入。
* 不承诺 MVCC/快照实现机制；实现可用锁等手段达成，但对外可观察语义必须满足上述一致性。
* 注：该条款不改变对外可见性：对外仍然只有 commit 后的状态可见。

补充：`System.begin_session(...)` 的项目存在性检查使用“系统内部基线读”（等价于 baseline read 语义），但该读取不通过仓库接口暴露给上层。

0b.3 一致读 + 写入的 TOCTOU 约束（强约束）

* 若某系统协议要求“先判定门禁/前置条件、再推进并写入”，则判定与推进写入必须在同一系统事务内、基于同一会话内一致读视图完成。
* 禁止实现为“先读判定、后另起事务写入”的两段式，以避免 TOCTOU（time-of-check-to-time-of-use）竞态。

0b.4 并发冲突与扩展边界（强约束的最小声明）

* 强约束：系统级写事务串行化（single-writer）。任意时刻最多存在一个 `OPEN` 且可写的 mutation session（或一个持有写锁的会话）。
* 若并发尝试开启第二个写会话：必须立即拒绝并抛 `ConcurrencyConflictError`。
* 在 single-writer 模型下，仓库可提供 `update/replace`，且不要求版本/CAS；其行为在串行写事务序列下定义。
* 强约束（写死系统边界）：系统写入仅允许**单进程单实例**持有写锁并执行写事务；不得存在跨进程/分布式写入路径。

0b.4a 写锁承载形态与崩溃语义（强约束；写死）
- 写锁为进程内互斥（in-process mutex）语义；在 0b.4 的“单进程单实例”边界下不引入跨进程/分布式锁。
- 进程崩溃会导致写锁自然释放；系统不提供跨进程恢复或“续租”语义。
- 系统不提供 mutation session 的超时自动回收/自动 rollback；调用方必须显式 `commit()` 或 `rollback()` 关闭会话。若调用方遗失会话引用，唯一恢复手段为重启该系统进程（运维手段），不得在运行中隐式回收以避免引入不可见副作用。


0b.5 术语（与本章事务模型对齐；用于消除“必须在 session 之前”歧义）

* 协议前置条件失败（precondition failure）：在执行某个写入协议/写接口时，若其前置条件不满足，则必须在产生任何写入之前拒绝执行，并返回失败原因。

  * “不产生任何写入”包括：不得留下任何 staged 写入、不得改变任何仓库状态、不得产生任何**系统内可枚举**副作用（例如入队/登记/审计事件追加）。可观测性旁路输出见 0b.1.1a，不视为系统写入。
  * 强制（执行点写死）：协议/写接口的前置条件判定必须在**mutation session 内**完成，且必须在产生任何 staged 写入之前完成；任一前置条件失败必须抛 `PreconditionFailure` 且不得产生任何 staged 写入（0b.5）。
  * 会话状态：发生 `PreconditionFailure` 时，session 必须保持 `OPEN`，调用方可以在同一 session 内继续执行其他操作。

* 提交期校验失败（commit-time validation failure）：进入 mutation session 并产生 staged 写入，但在 `commit()` 的强制校验阶段失败；`commit()` 失败并回滚，最终对外不可见。

  * 与 0b.1.3 对齐：`commit()` 失败后会话进入 `FAILED` 并关闭，不允许继续复用该会话。

0b.6 统一错误语义最小集合（强约束；用于避免实现分叉）

为避免“抛明确错误”在工程上退化为口头承诺，本规格定义以下最小错误集合。实现可在此基础上扩展更细分错误，但不得以通用 `RuntimeError/Exception` 等替代这些语义类别。

* `NotFound`

  * 发生点：读接口（例如 `get`）在目标 ID 不存在时。
  * staged 写入：无。
  * 调用方行为（强约束）：调用方必须将其视为失败并停止本次路径；若业务需要重试，必须在修正输入或外部状态变化后重试（不得由实现隐式重试）。

* `PreconditionFailure`（语义等价于 0b.5 的 precondition failure）

  * 发生点：写接口/协议的写前检查失败（例如主键已存在、写前置条件不满足）。
  * staged 写入：必须为无（拒绝时不产生任何写入；0b.5）。
  * 会话语义（强约束）：发生 `PreconditionFailure` 时，该写操作失败且不产生任何 staged 写入；session 必须保持 `OPEN`，调用方可继续在同一 session 内执行其他操作。

* `CommitTimeValidationFailure`（语义等价于 0b.5 的 commit-time validation failure）

  * 发生点：`commit()` 的强制校验阶段（且只允许 0b.7.1 集合）。
  * staged 写入：允许在失败前存在；但 `commit()` 失败后必须整体回滚，对外不可见（0b.1.2）。
  * 可重试：必须新开 session 重试（0b.1.3：FAILED 后会话关闭，不可复用）。

* `StructuralInconsistencyError`

  * 发生点：树形仓库的结构查询在 mutation session 内读取到的结构尚未满足其提交期结构约束时（例如双向一致/单父/无环）。
  * staged 写入：可有（该错误用于“会话内读 + staged 写入”下的结构不一致表达）。
  * 会话语义（强约束）：发生 `StructuralInconsistencyError` 时，结构查询失败且不得返回部分结果；调用方必须在同一 session 内通过后续写操作修复结构后方可再次调用查询；实现不得自动修复。

* `ConcurrencyConflictError`

  * 发生点：并发尝试开启第二个 `OPEN` 的 mutation session（违反 0b.4 single-writer）而被拒绝。
  * staged 写入：必须为无（冲突检测失败时不得写入）。
  * 调用方行为（强约束）：调用方必须等待先前写会话结束（`COMMITTED/ROLLED_BACK/FAILED`）后，使用新 session 重试。

* `SessionClosedError`

  * 发生点：对处于关闭态（`COMMITTED/ROLLED_BACK/FAILED`）的会话再次调用 `commit()` 或 `rollback()`；或在关闭态对任意仓库执行任何读写操作（见 0b.1.4）。
  * staged 写入：无（会话已关闭不得接受写入）。
  * 调用方行为（强约束）：必须新开 session 后重试；不得复用已关闭会话。

* `DirectoryStructureCorruptedError`（目录结构损坏；强约束）

  * 发生点：执行 0b.1.5b 材料源同步协议时，发现不受支持的目录条目（如符号链接、快捷方式、设备文件等），或发现目录树无法与 `LearningObjectNode` 树严格同构。
  * staged 写入：必须为无（拒绝时不产生任何写入；0b.5）。
  * 调用方行为（强约束）：调用方必须将其视为“用户需修复目录结构”的失败，并向用户提供损坏路径与混杂条目列表；修复后可重试同步。

0b.7 提交期强制/显式校验口径（全局强约束；适用于系统级 `commit()`）

0b.7.1 提交期强制集合（必须写死，所有实现一致）

定义  
本小节所述“提交期强制校验”指：**系统级** `commit()` 在“整组变更生效之前”对最终态执行的一次性校验。  
除以下条目外，系统与各仓库在系统级 `commit()` 不得引入任何额外校验。

读取视图口径（强约束；必须写死；用于消除实现分叉）
* 提交期强制校验必须对“本次提交后的最终态”执行。
* 校验读取视图必须等价于本会话的 overlay 视图：固定已提交基线 + 本会话 staged（见 0b.2 的会话内叠加读）。
  * 等价实现口径：`commit()` 在执行提交期强制校验时，调用任一仓库读接口必须传入同一 `session: MutationSession`，并以该 session 的 read-your-writes 视图读取（不得只读已提交基线）。
* 作用域约束（强约束）：系统级 `commit()` 的提交期强制校验仅对 `session.project_id` 作用域内“本次提交后的最终态”执行；不得扫描、枚举或校验其他 `project_id` 的数据。

* 事务语义与回滚：0b.1
* 仓库内结构校验（对象模型的一致性最终态）：  
  * 树结构一致性：1.2.3、1.6.3（含无环/双向一致/单父；其中 1.6.3 仍含同质）  
  * 任务内去重：1.5.3  
  * RangeSnapshot 内容寻址唯一性：1.7.3  
* 系统级不变量（跨仓库/跨子系统的已提交状态一致性）：  
  * 项目内全局队列单例与 Q1/Q2：4.1.2  
  * 链存在性与登记约束：4.1.4  

0b.7.2 非强制项的统一处理（必须写死）：凡不在 0b.7.1 列表中的“跨仓库引用存在性/可达性/可解析性/外部资源可用性”等校验，一律不得在 `commit()` 期间强制；只能通过显式校验接口执行，并以独立结果（状态/事件/报告）对外呈现。

显式校验接口集合（强约束；名字、输入输出写死）

类型定义（强约束）
- `ValidationResult`
  - 字段：
    - `code: ValidationCode`
    - `message: str`
  - 语义：
    - `code == OK` 表示通过；其余表示失败。
- `ValidationCode = {OK, NOT_FOUND, UNREACHABLE, INVALID_INPUT}`

系统必须提供的显式校验接口（强约束；不得更名，不得缺失）
- `validate_material_reachable(session: MutationSession, instance_id: InstanceId) -> ValidationResult`
  - 失败码集合：
    - `NOT_FOUND`：`InstanceRepository.get(session, instance_id)` 不可解析。
    - `UNREACHABLE`：材料当前不可达（具体探测由实现决定，但不得改写既有已提交事实）；这包括文件缺失、权限受限、或运行时打开失败等情况。
- `validate_recall_point_ids_resolvable(session: MutationSession, range_id: RangeId) -> ValidationResult`
  - 失败码集合：
    - `NOT_FOUND`：`RangeSnapshotRepository.get(session, range_id)` 不可解析，或其 `recall_point_ids` 中存在不可在 `RecallPointRepository.get(session, ...)` 解析的 ID。

0b.7.3 显式校验的隔离性（强约束）
* 显式校验结果不得反向改变既有已提交事实；不得触发隐式修复；不得在读路径自动触发。
* 显式校验不得在 `commit()` 期间被隐式调用或隐式门禁化；任何需要“阻止某类业务接口继续执行”的门禁，只能在对应业务接口层显式调用上述校验接口并检查其 `ValidationResult` 后实现（不得把门禁塞回 `commit()`）。

---

<a id="toc-1"></a>

## 1. 静态对象模型（Engineering Spec）

本章定义 PLM 的核心数据对象及其最小一致性要求。对象的“正确性推断”不在系统职责内；系统只负责存储、索引与基本结构约束。

继承声明（强约束；仅声明）  
本章所有仓库与对象默认继承第 0a 章与第 0b 章的全局约束，特别包括：会话/提交/回滚语义、读视图语义、TOCTOU 约束、并发冲突口径、错误语义最小集合，以及提交期强制校验闭包。除非本章显式收窄接口或增加更强的写前条件，否则不得引入与全局公理层不一致的新语义。  
（权威指向：提交期强制集合闭包见 0b.7.1；错误语义最小集合见 0b.6。）  

仓库接口与 mutation session 的关系（强约束）  
- 本章出现的各仓库写接口（例如 `add/update/intern/push_up`）必须在 mutation session 内执行，并受 staged/commit/rollback 语义约束。  
- 本章出现的各仓库读接口与 Queries 必须显式携带 `session: MutationSession` 执行；当该 session 无 staged 写入时为基线读（只观察已提交状态），当该 session 含 staged 写入时为会话内叠加读（已提交基线 + staged，read-your-writes）（见 0b.2）。  
- 工程形态必须为“显式 session 参数”；不得使用隐式绑定当前 session 的实现形态（见 0b.1.1）。  
- 本章所有仓库对象的主键/索引/引用解析默认受 `session.project_id` 作用域约束；同名 ID 在不同项目之间互不冲突、互不可见。

本章目录：

- [1.0 Project（项目）](#toc-1-0)
  - [1.0.1 数据模型](#toc-1-0-1)
  - [1.0.2 仓库接口](#toc-1-0-2)
  - [1.0.3 一致性与校验](#toc-1-0-3)
  - [1.0.4 ProjectStorageConfig（项目存储配置）](#toc-1-0-4)
  - [1.0.4a ProjectMaterialSourceBinding（项目材料源绑定）](#toc-1-0-4a)
  - [1.0.5 ProjectConfig（项目配置）](#toc-1-0-5)
- [1.1 Instance（实例）](#toc-1-1)
  - [1.1.1 数据模型](#toc-1-1-1)
  - [1.1.2 仓库接口](#toc-1-1-2)
  - [1.1.3 一致性与校验](#toc-1-1-3)
- [1.2 LearningObjectNode（学习对象节点）](#toc-1-2)
  - [1.2.1 数据模型](#toc-1-2-1)
  - [1.2.2 仓库接口](#toc-1-2-2)
  - [1.2.3 一致性与校验](#toc-1-2-3)
- [1.3 Anchor（锚点）](#toc-1-3)
  - [1.3.1 数据模型](#toc-1-3-1)
- [1.4 RecallPoint（复述点）](#toc-1-4)
  - [1.4.1 数据模型](#toc-1-4-1)
  - [1.4.2 仓库接口](#toc-1-4-2)
  - [1.4.3 一致性与校验](#toc-1-4-3)
- [1.5 LearningTask（学习任务）](#toc-1-5)
  - [1.5.1 数据模型](#toc-1-5-1)
  - [1.5.2 仓库接口](#toc-1-5-2)
  - [1.5.3 一致性与校验](#toc-1-5-3)
- [1.6 LearningTaskNode（学习任务节点）](#toc-1-6)
  - [1.6.1 数据模型](#toc-1-6-1)
  - [1.6.2 仓库接口](#toc-1-6-2)
  - [1.6.3 一致性与校验](#toc-1-6-3)
- [1.7 RangeSnapshot（范围快照池）](#toc-1-7)
  - [1.7.1 数据模型](#toc-1-7-1)
  - [1.7.2 仓库接口](#toc-1-7-2)
  - [1.7.3 一致性与校验](#toc-1-7-3)
- [1.8 AuditLogEvent（运行日志/审计事件）](#toc-1-8)
- [1.9 MediaAsset（项目富媒体资产）](#toc-1-9)
- [1.11 AsrArtifact（ASR 转写产物）](#toc-1-11)
- [1.11a TempContextFragment（临时上下文片段）](#toc-1-11a)
- [1.11b QASession（LLM 问答会话）](#toc-1-11b)
- [1.11c CandidateRecallPoint（候选复述点）](#toc-1-11c)
- [1.11d MemoryCanvas（记忆画布）](#toc-1-11d)
- [1.11e MemoryCanvasVersion（记忆画布版本）](#toc-1-11e)
- [1.11f CanvasEdge（画布连线）](#toc-1-11f)
- [1.11g StoryArtifact（故事化产物）](#toc-1-11g)
- [1.12 RecallPointReviewRecord（复述点复习记录）](#toc-1-12)
- [1.13 AggregationQueue（聚合队列，Layer-owned State）](#toc-1-13)
- [1.14 AggregationEvent（聚合事件记录）](#toc-1-14)


<a id="toc-1-0"></a>

### 1.0 Project（项目）

<a id="toc-1-0-1"></a>

#### 1.0.1 数据模型

存储字段

* `project_id: ProjectId`
* `title: str`
* `state: ProjectState`（`ACTIVE | DELETED`）
* `created_at: Timestamp`
* `deleted_at: Optional[Timestamp]`

<a id="toc-1-0-2"></a>

#### 1.0.2 仓库接口

* `ProjectRepository.add(session: MutationSession, project: Project) -> None`
  * 新增；若 `project_id` 已存在，抛 `PreconditionFailure`。
* `ProjectRepository.update(session: MutationSession, project: Project) -> None`
  * 更新既有项目；最小实现只允许改写 `title`，`project_id/created_at/state/deleted_at` 必须保持与更新前已提交值一致；若项目不存在，抛 `NotFound`。
* `ProjectRepository.get(session: MutationSession, project_id: ProjectId) -> Project`
  * 不存在抛 `NotFound`。
* `ProjectRepository.maybe_get(session: MutationSession, project_id: ProjectId) -> Optional[Project]`
* `ProjectRepository.all(session: MutationSession) -> Sequence[Project]`
  * 按 `id_canonical_text(project_id)` 升序返回全量（见 0a.9）。
* `ProjectRepository.mark_deleted(session: MutationSession, project_id: ProjectId, deleted_at: Timestamp) -> None`
  * 可选：若实现采用软删除，可通过该接口标记删除时间与状态；若实现采用物理删除可不提供该接口。

说明（强约束）：`ProjectRepository` 不提供不带 `session` 的读接口；项目在 `System.begin_session(...)` 前的存在性检查由系统内部基线检查路径完成（见 0b.1.6），不属于仓库接口。

<a id="toc-1-0-3"></a>

#### 1.0.3 一致性与校验

* `project_id` 系统级唯一（见 0a.11）。
* 写前条件：`title` 非空。
* `state == DELETED` 的项目不得再开启会话（由 `System.begin_session` 保证）。



<a id="toc-1-0-4"></a>

#### 1.0.4 ProjectStorageConfig（项目存储配置）

用途  
在 `project_id` 作用域内持久化“服务器侧项目工作目录（project_root）”，用于约束：本项目的数据库文件、富媒体资产、项目配置，以及当 `source_kind == SERVER_FS` 时的服务端材料目录，均位于同一服务器工作目录树内。该配置仅记录路径事实，不做可达性探测。

存储字段  
- `project_id: ProjectId`
- `project_root: PurePath`
  - 语义：服务器侧项目工作目录根路径（POSIX 语义 `PurePath`）。  
  - 写入规范化（强约束）：对输入字符串先执行 `\ -> /` 分隔符归一，再以 `PurePosixPath` 解析并存储；不得做可达性探测、外部访问或隐式修复。

- `learning_object_root: PurePath`
  - 语义：当 `source_kind == SERVER_FS` 时，学习对象（材料）目录的扫描根路径；**相对 `project_root` 的相对路径**（POSIX 语义 `PurePath`）。
  - 写入规范化（强约束）：同 `project_root`，先 `\ -> /`，再以 `PurePosixPath` 解析并存储。
  - 强约束：规范化后不得包含 `..` 路径穿越语义；解析 `project_root / learning_object_root` 必须仍位于 `project_root` 目录树内。
- `fs_sync_policy: FsSyncPolicy`
  - 语义：`SERVER_FS` 材料源的同步策略（见 0b.1.5b）。
  - 默认值（强约束）：`STARTUP_SYNC`。

- `updated_at: Timestamp`
  - 语义：最后更新时间戳；必须由系统时钟生成（0a.10）。

仓库接口  
- 关联仓库：`ProjectStorageConfigRepository`

写接口  
- `set(session: MutationSession, config: ProjectStorageConfig) -> None`
  - 语义：upsert；若已存在则覆盖更新（覆盖 `project_root/learning_object_root/fs_sync_policy/updated_at`）。  
  - 写前条件（强约束；0b.5）：  
    - `config.project_id == session.project_id`（不得跨项目写入）。  
    - `project_root` 非空（去除首尾空白后必须非空）。
    - `learning_object_root` 非空（去除首尾空白后必须非空）。
    - `learning_object_root` 必须为相对路径；规范化后不得包含 `..`；解析后必须位于 `project_root` 下。
    - `fs_sync_policy` 必须为 `FsSyncPolicy` 枚举值之一。
  

读接口  
- `get(session: MutationSession) -> ProjectStorageConfig`
  - 不存在则抛 `NotFound`（但对 `state == ACTIVE` 的项目按 0b.1.5a 应不发生）。  

一致性与校验  
- 索引不变式：同一 `project_id` 作用域内必须且只能存在一条 `ProjectStorageConfig` 记录（由项目 bootstrap 最小产物保证，0b.1.5a）。  

<a id="toc-1-0-4a"></a>

#### 1.0.4a ProjectMaterialSourceBinding（项目材料源绑定）

用途  
在 `project_id` 作用域内持久化“当前权威材料源如何生成 `Instance/LearningObjectNode`”这一控制事实。当前最小实现中，该对象允许在 `SERVER_FS`、`BROWSER_LOCAL`、`NATIVE_LOCAL` 与 `MANUAL` 四种材料管理模式之间切换，并通过统一控制面约束 0b.1.5b 协议采用哪一条材料导入路径，或明确声明该项目完全由手工材料事实维护。

存储字段  
- `project_id: ProjectId`
- `source_kind: MaterialSourceKind`
  - 语义：当前权威材料源类型；最小实现中取值必须为 `SERVER_FS`、`BROWSER_LOCAL`、`NATIVE_LOCAL` 或 `MANUAL`。
  - 语义补充：当 `source_kind == MANUAL` 时，`Instance/LearningObjectNode` 不由 0b.1.5b 的快照同步维护，而只由 4.5 的显式写入口维护。
- `source_root_label: Optional[str]`
  - 语义：材料源根目录的展示标签；可用于 UI 展示或审计摘要。
  - 语义补充：当 `source_kind == NATIVE_LOCAL` 时，该字段仅表示已绑定根目录的稳定显示名；绝对路径与 Native 目录句柄不在项目事实层持久化。
  - 强约束：该字段不得参与路径规范化、排序、ID 生成或同构判定。
- `updated_at: Timestamp`
  - 语义：最后更新时间戳；必须由系统时钟生成（0a.10）。

仓库接口  
- 关联仓库：`ProjectMaterialSourceBindingRepository`

写接口  
- `set(session: MutationSession, binding: ProjectMaterialSourceBinding) -> None`
  - 语义：upsert；若已存在则覆盖更新（覆盖 `source_kind/source_root_label/updated_at`）。
  - 写前条件（强约束；0b.5）：
    - `binding.project_id == session.project_id`（不得跨项目写入）。
    - `binding.source_kind ∈ {SERVER_FS, BROWSER_LOCAL, NATIVE_LOCAL, MANUAL}`。

读接口  
- `get(session: MutationSession) -> ProjectMaterialSourceBinding`
  - 不存在则抛 `NotFound`（但对 `state == ACTIVE` 的项目按 0b.1.5a 应不发生）。

一致性与校验  
- 索引不变式：同一 `project_id` 作用域内必须且只能存在一条 `ProjectMaterialSourceBinding` 记录（由项目 bootstrap 最小产物保证，0b.1.5a）。
- 更新该绑定不得隐式重建 `Instance/LearningObjectNode`；既有已提交树与实例集合必须保持不变，直到下一次显式成功导入、同步完成，或在 `source_kind == MANUAL` 下收到新的显式手工写入。
- 当 `source_kind == NATIVE_LOCAL` 时，绑定更新只改变“下一次 Native 同步/导入读取哪类权威材料源”的控制事实；它本身不得要求系统立刻验证本地目录可达性。

<a id="toc-1-0-5"></a>

#### 1.0.5 ProjectConfig（项目配置）

用途  
在 `project_id` 作用域内持久化项目配置（控制面），用于：  
- 为每层提供“复习链初始化模板”（4.3.2 Task Register 的初始 ReviewChain.queue 构造规则）。  
- 为每层提供“聚合阈值默认值”和“阈值自动上推开关”，并支持在 Layer 已存在时立即更新其阈值控制字段（使更新对未来立即生效）。  

重要声明（强约束；写死）  
- 配置更新为**未来生效**：不得追溯改写任何已提交的结构事实（见本节“Non-retroactive guarantee”）。  
- 聚合触发判定（4.4.2）读取的是 `Layer` 当前持有的 `(K_node, K_point)` 控制字段，以及该层配置的 `threshold_roll_up_enabled`；两者都必须来自持久化事实，且行为必须可重放。  
- 配置可写范围最小版（强约束；写死）：本规格的最小对外入口集合（4.5）必须允许分别编辑 `layer_configs`（通过 `set_layer_config` 合并语义）与 `push_config`（通过 `set_review_recommendation_config` 合并语义）。`push_config` 仍属于项目级配置事实，必须在项目 bootstrap 时写入默认值（见 0b.1.5a / 4.5 `create_project`）；`NativeRuntimeConfig / LocalModelConfig` 属于运行时层，不得写入 `ProjectConfig`，也不得通过项目级入口共享给其他端。
- `project_type` 是项目级业务规则源（强约束；写死）：
  - `COURSE`：项目必须使用学习对象树与实例；复述点必须绑定可解析锚点。
  - `BOOK`：项目必须使用学习对象树与实例；复述点必须绑定不可解析的文本锚点。
  - `LOOSE_POINTS`：项目不得使用学习对象树与实例；复述点不得绑定锚点。

存储字段（最小）
- `project_id: ProjectId`
- `project_type: ProjectType`
  - 默认值（强约束；写死）：`COURSE`。
- `layer_configs: Map[int, LayerConfig]`
  - Key：`layer_index`（见 0a.4）；必须满足 `layer_index >= 0`。  
  - 语义：每层的控制面配置（阈值自动上推开关 + 阈值 + 初始链模板）。  
  - 读取回退（强约束；写死）：若 `layer_configs` 不包含某 `layer_index`，则该层配置读取必须回退为系统默认 `LayerConfig`（其值等于本节写死的 `layer_index == 0` 默认值）。  
  - 强约束（写死默认值；用于跨实现一致）：`layer_configs` 必须至少包含 `layer_index == 0` 的一条配置，其默认值必须满足：  
    - `review_chain_template == [CONVERGENCE]`  
    - `aggregation_threshold == (K_node=10, K_point=200)`  
    - `threshold_roll_up_enabled == true`
- `push_config: RecallPointPushConfig`
  - 默认值（强约束；写死）：  
    - `min_recall_points_to_enable = 0`
    - `max_history_len = 20`
    - `recommended_batch_size = 20`
    - `forgetting_curve_decay_per_day = 0.20`
- `updated_at: Timestamp`
  - 语义：最后更新时间戳；必须由系统时钟生成（0a.10）。

LayerConfig（值对象；最小）
- `review_chain_template: ReviewChainTemplate`
- `aggregation_threshold: (K_node: int, K_point: int)`
- `threshold_roll_up_enabled: bool`
  - 语义：控制该层是否允许“达到阈值即自动进入聚合周期”（4.4.2）。`false` 仅禁止阈值自动上推；不得影响 4.4.5 的手动上推入口，也不得回滚已开始的聚合周期。

ReviewChainTemplate（值对象；最小）
- `items: Tuple[ReviewChainTemplateItem, ...]`（非空；顺序为权威解释顺序）

ReviewChainTemplateItemKind（枚举）
- `{CONVERGENCE, REVIEW_TASK}`

ReviewChainTemplateItem（值对象；最小）
- `kind: ReviewChainTemplateItemKind`
- `count: Optional[int]`
  - 仅当 `kind == REVIEW_TASK` 时允许出现；表示该位置需要实例化 `count` 个 ReviewTask；默认 `count == 1`。

写前条件（强约束；写死以避免实现分叉）
- `config.project_id == session.project_id`（不得跨项目写入）。
- `config.project_type ∈ {COURSE, BOOK, LOOSE_POINTS}`。
- 对任一 `layer_index, layer_cfg in layer_configs`：`layer_index >= 0`。
- 对任一 `layer_cfg.review_chain_template`：
  - `items` 非空。
  - `items` 至少包含 1 个 `CONVERGENCE`（否则系统无法产生可持续推进的收敛段；避免与 4.3.6 失配）。
  - 对任一 `item`：
    - `item.kind == CONVERGENCE`：`item.count` 必须为 `None` 或省略。  
    - `item.kind == REVIEW_TASK`：`item.count` 缺省视为 `1`，且必须满足 `count >= 1`。  
- `K_node >= 1` 且 `K_point >= 1`。
- `threshold_roll_up_enabled` 必须为布尔值。
- `push_config: RecallPointPushConfig`
  - 语义：复述点推荐/压缩感/漂移视图的只读配置。强约束：该配置只影响只读视图判断，不得改写任何既有结构事实（LearningTask/LearningTaskNode/队列/链等）。

相关运行时配置（强约束；非项目事实，不进入仓库存储）
- `NativeRuntimeConfig`
  - `runtime_kind: ClientRuntimeKind`
  - `capabilities: FrozenSet[RuntimeCapability]`
  - `local_models: LocalModelConfig`
  - 语义：由当前调用端运行时提供；可随设备与安装环境变化。它不是 `ProjectConfig` 字段，不参与 bootstrap，也不参与 `ProjectConfigRepository.set/get`。`local_models` 为兼容旧命名，内部条目既可指向本机/局域网服务，也可指向远程 HTTPS 模型服务。
- `LocalModelConfig`
  - `asr: Optional[LocalServiceConfig]`
  - `llm_qa: Optional[LocalServiceConfig]`
  - `recommender: Optional[LocalServiceConfig]`
  - `story_generator: Optional[LocalServiceConfig]`
  - 语义：仅当对应 `RuntimeCapability` 存在时可被使用。兼容旧命名，这些条目允许指向本地或远程服务；`asr` / `llm_qa` / `story_generator` 都不要求模型部署在用户本机，只要求当前运行时存在可用服务配置与鉴权信息。在 Hosted / Web 形态下，服务配置既可来自部署级环境或管理员维护的回退配置，也可来自当前登录用户保存在服务端的账号级配置；系统只允许在受信任的服务端边界使用这些密钥，不得把它们写入项目事实。
- `LocalServiceConfig`
  - `base_url: str`
    - 语义：模型服务基址（例如 `http://127.0.0.1:12345`、局域网地址或公网 HTTPS 端点）。
    - 写前条件：必须为非空字符串；不得包含尾随空白。
  - `model_name: Optional[str]`
    - 语义：可选模型标识；仅用于运行时调用与日志摘要，不得进入项目级审计 payload 的敏感字段。
  - `api_key: Optional[str]`
    - 语义：可选鉴权字段；可来自部署级配置或当前用户显式提供的密钥。系统必须仅在受信任的服务端边界使用该值；不得将其写入 `ProjectConfig`、项目级审计 payload、标准导出结果，也不得要求浏览器直接持有第三方模型服务的持久凭据。

- `RecallPointPushConfig`
  - `min_recall_points_to_enable: int`
    - 语义：当项目内 ACTIVE 复述点总数 `|{rp ∈ RecallPointRepository.all(session) | rp.state == ACTIVE}|` 小于该阈值时，系统必须禁用 4.7 的推荐复习列表，并返回空列表；该门槛只影响只读推荐视图，不得影响正式 `ReviewTask` 调度。
  - `max_history_len: int`
    - 语义：参与遗忘曲线加权计算的最大历史条目数（见 4.7.2）；超出则仅保留最近 `max_history_len` 条记录。
  - `recommended_batch_size: int`
    - 语义：只读推荐复习页每批默认展示的复述点数量；用户点击“继续推荐”后，系统必须返回后续批次，而不得推进任何正式复习状态。
  - `forgetting_curve_decay_per_day: float`
    - 语义：遗忘曲线指数衰减参数 `λ`（按“天”为单位）；用于把历史复习记录映射为当前记忆强度与复习推荐指数。必须满足 `λ > 0`。



仓库接口  
- 关联仓库：`ProjectConfigRepository`

写接口  
- `set(session: MutationSession, config: ProjectConfig) -> None`
  - 语义：upsert；若已存在则**覆盖更新完整 ProjectConfig 对象**，即覆盖 `project_type / layer_configs / push_config / updated_at`。  
  - 强约束：实现不得把该接口解释为“仅更新 `layer_configs`”；若系统仅希望更新层配置，必须通过 4.5 的 `set_layer_config(...)` 入口执行，而非改变本仓库接口语义。  

读接口  
- `get(session: MutationSession) -> ProjectConfig`
  - 不存在则抛 `NotFound`（但对 `state == ACTIVE` 的项目按 0b.1.5a 应不发生）。  

一致性与校验  
- 索引不变式：同一 `project_id` 作用域内必须且只能存在一条 `ProjectConfig` 记录（由项目 bootstrap 最小产物保证，0b.1.5a）。  

Non-retroactive guarantee（强约束；可测试口径）
- 任一配置更新（例如 4.5 的 `set_layer_config(...)` / `set_review_recommendation_config(...)`）不得对以下已提交对象做任何改写、重建或重排：  
  - 任一既有 `ReviewChain.queue/head_index/state`  
  - 任一既有 `Convergence.seed_range_id/review_task_ids/state`  
  - 任一既有 `ReviewTask.input_range_id/state/executed_at/result_range_id`  
  - 任一既有 `LearningTaskNode` 树结构（`parent_id/children` 等）  
- 配置更新只允许影响：  
  - 后续新创建的 `entry_node` 的 Task Register（4.3.2）：初始链队列按该层最新 `review_chain_template` 构建。  
  - 后续聚合触发判断与行为（4.4.2）：通过更新 Layer 当前 `(K_node, K_point)` 控制字段立即生效。  

<a id="toc-1-1"></a>

### 1.1 Instance（实例）

<a id="toc-1-1-1"></a>

#### 1.1.1 数据模型

用途  
表示一份可被系统稳定引用的最小材料单位。该材料既可以对应可访问的数字文件，也可以对应手工登记的非文件材料（如书本、纸质讲义、题册等）。

存储字段  
- `project_id: ProjectId`
- `instance_id: InstanceId`
  - 语义：实例唯一标识
- `material_id: PurePath`
  - 语义：项目内稳定的材料定位/标识
  - 约束（强约束）：当项目启用 0b.1.5b 的同步/导入协议时，`material_id` 必须等于该材料相对当前权威材料源根路径的相对路径（`PurePath`；POSIX 语义），由 0b.1.5b 协议产生。
  - 语义补充：当当前 `ProjectMaterialSourceBinding.source_kind == MANUAL` 时，`material_id` 允许仅作为项目内稳定的虚拟标识使用；它必须保持 POSIX 文本规范化，但不要求映射到任何可达本地文件路径。
  - 写入：若 `material_id` 输入为 `str`，实现必须以**稳定且跨平台一致**的规则转换为 `PurePath`（强约束：必须使用 POSIX 语义的 `PurePosixPath` 作为唯一规范化实现）：
    - 先执行字符串归一化：将 `\` 统一替换为 `/`（仅做分隔符归一，不做可达性探测与外部访问）。
    - 再以 `PurePosixPath(normalized)` 构造并存储为 `PurePath`。
    - 禁止在写入期做可达性探测、外部访问或隐式修复。

- `presence: InstancePresence`
  - 语义：该材料在“最近一次成功提交的权威材料源快照”中的存在性标记（`PRESENT | MISSING`）；当当前 `source_kind == MANUAL` 时，该字段只表示该 `Instance` 记录当前仍被项目保留。
  - 写入来源（强约束）：当项目启用 0b.1.5b 的同步/导入协议时，该字段仅允许由 0b.1.5b 协议写入；当当前 `source_kind == MANUAL` 时，显式手工写入口创建的新 `Instance` 必须写入默认值 `PRESENT`，系统不得因为缺少本地文件而隐式改写为 `MISSING`。
  - 默认值（强约束）：`PRESENT`（新建 Instance 时）。
- `last_seen_at: Optional[Timestamp]`
  - 语义：最近一次在同步扫描中被观测到的时间戳；当 `presence == MISSING` 时允许为 `None` 或保留旧值。对于手工材料，允许始终为 `None`。
  - 写入来源（强约束）：当项目启用 0b.1.5b 的同步/导入协议时，同步/导入协议负责维护；对手工材料，该字段允许保持 `None` 且不得成为写前条件失败原因。


派生字段  
- `material_display_name: str`
  - 计算：若 `material_id` 可解释为路径，则取路径的文件名；否则回退为 `material_id.as_posix()`。

<a id="toc-1-1-2"></a>

#### 1.1.2 仓库接口

仓库
- 关联仓库：`InstanceRepository`  

写接口
- `add(session: MutationSession, instance: Instance) -> None`
  - 新增；若 `instance_id` 已存在，抛 `PreconditionFailure`。  

读接口 
- `get(session: MutationSession, instance_id: InstanceId) -> Instance`
  - 不存在则抛 `NotFound`。
- `maybe_get(session: MutationSession, instance_id: InstanceId) -> Optional[Instance]`
  - 不存在返回 `None`。  
- `all(session: MutationSession) -> Sequence[Instance]`
  - 按 `id_canonical_text(instance_id)` 的 Unicode code point 升序返回全量（见 0a.9）。

<a id="toc-1-1-3"></a>

#### 1.1.3 一致性与校验

一致性与校验  
- 索引不变式
  - `instance_id` 在 `InstanceRepository` 内唯一。  
- 提交与回滚：
  - 提交失败必须整体回滚且对外不可见；提交失败后会话进入失败关闭态，不得复用。  
  - 本仓库不新增跨对象结构强制校验（仅维护索引不变式）。  
  - 引用可解析性与存在性：  
  - `material_id` 的可达性不得进入 0b.7.1 的系统级提交期强制集合。  
  - 当项目启用 0b.1.5b 的同步/导入协议时：  
    - `presence`（`PRESENT/MISSING`）只表达“最近一次成功同步/导入的权威材料源快照中该路径是否存在”；0b.1.5b 协议负责更新该字段。  
    - 文件暂不可访问、权限受限、或当前运行时暂不可播放，均不得写成 `MISSING`；这些只属于 `validate_material_reachable(...) == UNREACHABLE` 的运行时可达性语义。  
    - 丢失材料不得导致 Instance 被删除（否则会破坏 RecallPoint 强引用）；只能标记为 `MISSING`，并由用户手动迁移相关 RecallPoint 的 `anchor.instance_id`。  
  - 当当前 `ProjectMaterialSourceBinding.source_kind == MANUAL` 时：  
    - 系统不得因为 `material_id` 无法映射到本地文件、或当前设备上不存在对应材料，而把该 `Instance` 视为无效。  
    - 对纸质/外部材料，`RecallPoint.anchor.instance_id` 仍可合法强引用此类 `Instance`。  
  - `validate_material_reachable(session, instance_id)` 仍为系统必备显式校验接口：其实现应至少满足：当 `presence == MISSING` 时返回 `UNREACHABLE`；其余探测细节由实现决定，但不得改写既有已提交事实。对于手工材料，实现不得仅因“无本地文件可探测”而返回 `UNREACHABLE`。  
  - 系统不得在读路径触发隐式校验或隐式修复。

---

<a id="toc-1-2"></a>

### 1.2 LearningObjectNode（学习对象节点）

<a id="toc-1-2-1"></a>

#### 1.2.1 数据模型

用途  
材料结构树中的节点。每个叶子节点绑定一份具体材料实例，用于承载后续“锚点/复述点”的落点；每个容器节点不绑定实例，仅负责组织子节点与顺序。

对象类型  
- `LearningObjectLeaf`（叶子）  
- `LearningObjectContainer`（容器）

存储字段（Leaf）  
- 结构字段  
  - `project_id: ProjectId`
  - `node_id: LearningObjectNodeId`
  - `relative_path: PurePath`
    - 语义：相对当前权威材料源根路径的相对路径（POSIX 语义）。
    - 当项目启用 0b.1.5b 的同步/导入协议时，该字段为权威结构源，用于目录树同构（0b.1.5b）。  
  - `source: Enum{FILESYSTEM, MANUAL}`
    - 语义：该节点的写入来源。  
    - 强约束：当项目启用 0b.1.5b 的同步/导入协议时，该字段必须为 `FILESYSTEM`；此处 `FILESYSTEM` 表示“由当前权威材料源同步/导入协议生成”，可来自 `SERVER_FS`、`BROWSER_LOCAL` 或 `NATIVE_LOCAL`。  
    - 强约束：当通过 4.5 的 `add_learning_object_leaf/container` 手工写入口创建/修改节点（且仅允许在项目未启用 0b.1.5b 同步协议时）时，创建的新节点必须写入 `MANUAL`。

  - `parent_id: Optional[LearningObjectNodeId]`
    - 根节点为 `None`,若非 None，则 parent 必须解析为 Container  
    - 叶子节点通过 `parent_id` 参与树结构。
  - `instance_id: InstanceId`
    - 叶子节点必须且只能绑定一个 `instance_id`。  
- 描述字段  
  - `title: str`

存储字段（Container）

- 结构字段  
  - `source: Enum{FILESYSTEM, MANUAL}`
    - 语义：同上（Leaf）。强约束同上：项目启用 0b.1.5b 同步协议时 `source == FILESYSTEM`；手工入口创建的新节点必须写入 `MANUAL`。  

  - `project_id: ProjectId`
  - `node_id: LearningObjectNodeId`  
  - `relative_path: PurePath`
    - 语义：相对当前权威材料源根路径的相对路径（POSIX 语义）。
  - `parent_id: Optional[LearningObjectNodeId]`（根节点为 `None`）  
  - `children: Sequence[LearningObjectNodeId]`（有序；顺序即遍历顺序）
- 描述字段  
  - `title: str`

语义  
- 叶子节点必须且只能绑定一个 `instance_id`。
- 当项目启用 0b.1.5b 的同步/导入协议时：`LearningObjectNode` 树必须与当前权威材料源定义的权威结构严格同构（0b.1.5b）；`SERVER_FS`、`BROWSER_LOCAL` 与 `NATIVE_LOCAL` 均采用“目录容器 + 直接孩子集合”的同构口径。  
- 容器节点不绑定 `instance_id`。  
- `children` 定义该容器的直接子节点 `node_id` 有序序列；任何遍历/聚合均以该顺序为准。  
- `children` 的顺序是权威事实源（authoritative order）；对已提交状态，该顺序必须保持稳定。  
- `children` 中不允许出现重复的 `child_id`（同一容器内也不允许）。  
- `children` 允许为空序列；此时该容器的覆盖实例序列为空（见下文派生定义）。  
- 当项目未启用 0b.1.5b 协议时，空容器可作为稳定的手工挂载点/纲目节点存在；其本身不绑定 `Instance`，但可用于组织书本、章节、题册等非文件材料。
- 同一容器允许同时包含叶子与容器子节点；Leaf/Container 的判定以 `LearningObjectNodeRepository` 中对 `child_id` 的解析结果之对象类型为准；无法解析视为校验失败（提交期；见 1.2.3）。

森林语义（最小增补）

* 学习对象结构允许为森林：可存在多个根节点，根节点定义为 `parent_id = None` 的节点。
* 结构的全局遍历入口定义为根节点序列 `root_node_id_sequence`：

  * `root_node_id_sequence = [node_id | parent_id(node_id) is None]`，并按 `node_id` 的字典序升序排序。
    * 排序口径：按 `id_canonical_text(node_id)` 的 Unicode code point 字典序升序（见 0a.9）。
  * 该序列的顺序为全局权威顺序（authoritative order）；对已提交状态必须保持稳定。
* 全局覆盖实例序列定义为：

  * `covered_instance_id_sequence(forest) = concat(covered_instance_id_sequence(root_id) for root_id in root_node_id_sequence in order)`

派生定义 
- `path_ids(node_id) -> Sequence[LearningObjectNodeId]`
  - 从当前节点沿 `parent_id` 链回溯至根，得到路径上的 `node_id` 序列；**顺序固定为 root → … → self**（包含 self）。
  - 其中 root 指沿 `parent_id` 回溯时遇到的第一个 `parent_id = None` 的节点。
- `depth(node_id) -> int`
  - 节点在树中的深度，由 `parent_id` 链长度得到（根深度为 0 的话，则为回溯边数）。
- `covered_instance_id_sequence(leaf_id) -> Sequence[InstanceId]`
  - 叶子节点覆盖实例序列定义为 `[instance_id]`。
- `covered_instance_id_sequence(container_id) -> Sequence[InstanceId]`
  - 覆盖实例序列定义为：按 `children` 的顺序对每个子节点递归取其覆盖实例序列，并依次拼接：  
    - `covered_instance_id_sequence(container_id) = concat(covered_instance_id_sequence(child_id) for child_id in children in order)`

<a id="toc-1-2-2"></a>

#### 1.2.2 仓库接口

仓库 
- 关联仓库：`LearningObjectNodeRepository`  

对象集合  
- 同仓库同时存放 `LearningObjectLeaf` 与 `LearningObjectContainer`，同一 `node_id` 命名空间。

写接口  
- `add(session: MutationSession, node: LearningObjectLeaf | LearningObjectContainer) -> None`：新增；`node_id` 已存在则抛`PreconditionFailure`。

- `replace_all_from_fs(session: MutationSession, nodes: Sequence[LearningObjectLeaf | LearningObjectContainer]) -> None`
  - 语义：以 0b.1.5b 协议产出的权威结构结果为输入，对本项目作用域内 `LearningObjectNode` 集合执行**全量替换**（清空旧集合并写入新集合）。
  - 触发源（强约束）：仅允许由 0b.1.5b 的同步/导入协议，以及 4.5 的 `sync_learning_objects_from_fs` / `import_learning_objects_from_browser_scan` 对外入口调用；不得在其他入口隐式调用。
  - 原子性（强约束）：实现必须保证替换在同一 mutation session 中 staged 完整可提交；不得对外暴露部分替换中间态。


Queries  
- `path_ids(session: MutationSession, node_id: LearningObjectNodeId) -> Sequence[LearningObjectNodeId]`  
  - Postcondition：满足 1.2 的 `path_ids` 派生定义。  
  - 顺序约定：**root → self**。  
- `depth(session: MutationSession, node_id: LearningObjectNodeId) -> int`  
  - Postcondition：满足 1.2 的 `depth` 派生定义（root 深度为 0）。  
- `covered_instance_id_sequence(session: MutationSession, node_id: LearningObjectNodeId) -> Sequence[InstanceId]`  
  - Postcondition：若为 Leaf，返回 `[instance_id]`；若为 Container，满足 1.2 的拼接定义。

Queries 失败语义（强约束；用于实现一致性）
- 若 `node_id` 不存在：必须抛 `NotFound`。
- 在 mutation session 内，若会话内读视图（in-session：一致读视图 + 本会话 staged 写入）所呈现的结构尚未满足 1.2.3 的提交期约束（例如双向一致/单父/同质/无环等），则上述结构查询必须抛 `StructuralInconsistencyError`（0b.6）；不得返回“尽力而为”的部分结果，不得在读路径触发隐式修复或隐式校验。

<a id="toc-1-2-3"></a>

#### 1.2.3 一致性与校验

索引不变式 
- `node_id` 唯一。  
- `InstanceId` 唯一绑定（写接口前置条件；非提交期强制项）：  
  - 同一仓库内，一个 `InstanceId` 值最多被一个 `LearningObjectLeaf.instance_id` 绑定。  
  - 该前置条件的判定必须基于本会话内一致读视图（in-session：一致读视图 + 本会话 staged 写入），且**必须包含本会话的 staged 写入**（read-your-writes）。  
    - 例如：同一 session 内先 `add leaf(A, instance=x)` 再 `add leaf(B, instance=x)` 时，第二次 `add` 必须触发 `PreconditionFailure`，不得推迟到 `commit()`。  
  - 若写操作将导致同一 `InstanceId` 值被多个 Leaf 绑定，则该写操作必须抛 `PreconditionFailure`（失败不产生任何写入，见 0b.5）；该约束不得推迟到提交期强制校验。  

提交（commit）时校验  
- 双向一致（Bidirectional consistency）：  
  - 对任一 Container `p`，对任一 `child_id ∈ p.children`，必须满足 `child.parent_id == p.node_id`（无法解析 `child_id` 视为该项失败）；  
  - 对任一节点 `n`，若 `n.parent_id = p`，则必须满足 `n ∈ p.children`。  
- 子列表不重复（No duplicate children）：对任一 Container `p`，`p.children` 不得包含重复 `child_id`。  
- 单父（No multiple parents）：任何 `node_id` 不得同时出现在两个不同 Container 的 `children` 中。  
- 无环（Cycle-free）：基于 `children`（权威遍历顺序）检测可达环；由于双向一致，该结果等价于 `parent_id` 回溯无环。  
  - 检测范围为仓库内全体节点构成的有向图（由 Container.children 诱导的边）；允许存在多个根（`parent_id = None`）。  
  - 实现不得对已提交状态做隐式修复。  
- 本仓库提供的结构 Query（见 1.2.2）之语义以 Container.children 为权威，并且只对已通过本节校验的已提交状态定义；实现不得提供指针不一致容错。  
- 类型约束：对任一节点 `n`，若 `n.parent_id = p`，则 `p` 必须解析为 Container。  
- 绑定约束（Instance binding）：Leaf 必须且只能绑定一个 `instance_id`；Container 不得绑定 `instance_id`。

一致性与校验  
- Failure：
  - （同步门禁）当项目启用 0b.1.5b 的协议时，若权威材料源输入导致同一路径同时被解释为目录与文件，或包含不受支持的目录条目，则系统必须在同步/导入协议阶段拒绝执行并返回“目录结构损坏”，且不得产生任何 staged 写入（0b.1.5b）。
  - 若检测到结构不一致（断引用、单父冲突、父子不一致等），则 `commit()` 必须失败并整体回滚，对外不可见。  
- Query 前置条件
  - 只对“已提交且通过 commit 校验”的状态定义。

---

<a id="toc-1-3"></a>

### 1.3 Anchor（锚点）

<a id="toc-1-3-1"></a>

#### 1.3.1 数据模型

用途
定位到某实例材料内部的一个位置，用于把复述点锚定在材料上。该位置既可以是系统可理解的位置编码，也可以是不透明的人类文本锚点。

字段
* `instance_id: InstanceId`
* `position: str`（位置编码或不透明文本锚点；格式由材料类型决定）

派生字段
* `anchor_repr(anchor) -> str := f"{instance_id}:{position}"`

聚合与持久化边界
* `Anchor` 为值对象（Value Object），不拥有独立 `Id`，且不存在独立仓库。
* `Anchor` 只能作为其他可提交对象的内嵌字段被持久化（例如 `RecallPoint.anchor`）；对 `Anchor` 的任何状态改变必须通过其宿主对象的写接口发生，并受同一系统级 mutation session/commit/rollback 语义约束（0b.1）。

写前条件
* 在任何写接口接收/写入包含 `Anchor` 的宿主对象时（例如 `RecallPointRepository.add/update/...`），实现必须在产生任何 staged 写入之前检查：

  * `instance_id` 非空；
  * `position` 非空。
* 任一写前条件失败：必须抛 `PreconditionFailure`，且失败不产生任何写入（0b.5）。

项目类型约束（强约束；写死）
* 当 `ProjectConfig.project_type == COURSE` 时：
  - `Anchor` 必须存在；
  - `position` 必须是系统可解析的位置编码；最小实现中必须满足 `position == "t=<非负整数毫秒>"`。
* 当 `ProjectConfig.project_type == BOOK` 时：
  - `Anchor` 必须存在；
  - `position` 必须是不可解析的人类文本锚点；最小实现中不得接受 `t=<...>` 这种 COURSE 时间编码。
* 当 `ProjectConfig.project_type == LOOSE_POINTS` 时：
  - `Anchor` 不得出现；宿主对象必须以“无锚点”形式写入。

非目标

* `position` 的规范格式不在本 domain 强制；上层可定义 UI 规范化或显式校验接口，但不得把该类校验并入系统级 `commit()` 强制集合（0b.7.1/0b.7.2）。
* `position` 允许是不透明的人类文本，例如 `第123页 第4题`、`p.56 #2`、`Chapter 3 Example 1`；系统必须按原样持久化与展示，不得要求其可被语义解析。

---

<a id="toc-1-4"></a>

### 1.4 RecallPoint（复述点）

<a id="toc-1-4-1"></a>

#### 1.4.1 数据模型

用途  
最小可复习条目：问题 + 答案 + 可选锚点。系统只记录，不判断对错；锚点是否存在由 `ProjectConfig.project_type` 决定。

存储字段  
- `project_id: ProjectId`
- `recall_point_id: RecallPointId`  
- `created_at: Timestamp`
  - 语义：创建时间戳（UTC；系统生成，见 0a.10）。
- `state: RecallPointState`
  - 语义：复述点当前状态；默认值必须为 `ACTIVE`。
- `deleted_at: Optional[Timestamp]`
  - 语义：逻辑删除（墓碑删除）时间戳；`state == ACTIVE` 时必须为 `None`，`state == DELETED` 时必须非空。
- `question: RichContent`  
- `answer: RichContent`  
- `references: Tuple[RecallPointId, ...]`
  - 语义：该复述点指向其他复述点的有序引用列表；表示一组独立于 `question/answer` 文本之外的关系边。允许为空 Tuple。
  - 约束：每个被引用 ID 必须指向同项目内可解析且 `state == ACTIVE` 的既有 RecallPoint；不得包含重复 ID；不得包含自身 ID。
- `insights: Tuple[RichContent, ...]`
  - 语义：感悟列表（append-only；顺序稳定）；允许为空 Tuple。
- `anchor: Optional[Anchor]`
  - 语义：仅当项目类型要求绑定锚点时存在；是否允许为空由 1.4.3 的项目类型规则决定。

派生字段  
- `str(recall_point)`：简单的 Q/A 可读表示

<a id="toc-1-4-2"></a>

#### 1.4.2 仓库接口

仓库

关联仓库  
- `RecallPointRepository`

写接口  
- `add(session: MutationSession, rp: RecallPoint) -> None`
  - 新增；若 `recall_point_id` 已存在，必须抛 `PreconditionFailure`（0b.5）。  
  - 写前检查：必须满足 1.4.3 的 Write-time preconditions（其中 Anchor 的前置条件见 1.3.1）；若 `anchor != None`，则额外写前条件（强引用）：`InstanceRepository` 可解析 `anchor.instance_id`；失败为 `PreconditionFailure` 且不产生任何写入（0b.5）。  
- `update(session: MutationSession, rp: RecallPoint) -> None`
  - 允许更新既有 RecallPoint。可更新字段为 `question`、`answer`、`anchor`；`references` 在本最小规格中视为创建时确定，`update` 不得改写其内容；`insights` 不可通过 `update` 覆盖、删除或重排（只允许通过 `append_insight` 追加，既有顺序保持稳定）。`recall_point_id` 不可变。
  - 强约束：`state/deleted_at` 不可通过 `update` 修改；墓碑删除只能通过 `mark_deleted(...)` 发生。  
  - NotFound：若 `recall_point_id` 不存在，必须抛 `NotFound`。
  - 写前检查：必须满足 1.4.3 的 Write-time preconditions（其中 Anchor 的前置条件见 1.3.1）；若 `anchor != None`，则额外写前条件（强引用）：`InstanceRepository` 可解析 `anchor.instance_id`，且目标 RecallPoint 当前 `state == ACTIVE`；失败为 `PreconditionFailure` 且不产生任何写入（0b.5）。
  - 并发写口径继承 0b.4（single-writer），因此 update 不需要版本/CAS；其行为在串行写事务序列下定义。

- `append_insight(session: MutationSession, recall_point_id: RecallPointId, insight: RichContent) -> None`
  - 语义：将 `insight` 追加到目标 RecallPoint 的 `insights` 尾部（append-only；顺序稳定）。  
  - NotFound：若 `recall_point_id` 不存在，必须抛 `NotFound`。  
  - 写前检查（强约束；0b.5）：  
    - 目标 RecallPoint 当前 `state == ACTIVE`；若为 `DELETED`，必须抛 `PreconditionFailure`。  
    - `insight` 必须满足 0a.12 的 RichContent 写前条件。  
    - 若 `insight` 含 `IMAGE` 内容块，则其 `asset_id` 必须能在 `MediaAssetRepository` 中解析到；否则必须抛 `PreconditionFailure`，且不产生任何 staged 写入。  

- `mark_deleted(session: MutationSession, recall_point_id: RecallPointId, deleted_at: Timestamp) -> None`
  - 语义：将目标 RecallPoint 标记为逻辑删除（墓碑删除）；提交生效后对象仍必须可解析。
  - NotFound：若 `recall_point_id` 不存在，必须抛 `NotFound`。
  - 幂等语义（强约束）：若目标已处于 `DELETED`，允许幂等返回成功，且不得改写任何字段。



读接口  
- `get(session: MutationSession, recall_point_id: RecallPointId) -> RecallPoint`：不存在则抛 `NotFound`；`DELETED` 的墓碑对象仍必须返回。  
- `maybe_get(session: MutationSession, recall_point_id: RecallPointId) -> Optional[RecallPoint]`  
- `all(session: MutationSession) -> Sequence[RecallPoint]`
  - 语义：返回该项目内全部已提交 RecallPoint（包含 `ACTIVE` 与 `DELETED`）；墓碑对象不得在仓库层被隐式隐藏。

<a id="toc-1-4-3"></a>

#### 1.4.3 一致性与校验

索引不变式  
- `recall_point_id` 唯一。  

写前条件  
- `recall_point_id` 非空。  
- `state == ACTIVE`。  
- `deleted_at is None`。  
- `question` 必须为合法 RichContent（0a.12；不得为空）。  
- `answer` 必须为合法 RichContent（0a.12；不得为空）。  
- `references` 中每个 `RecallPointId` 都必须非空、不得重复、不得等于自身 `recall_point_id`。
- 项目类型规则（强约束；写死）：
  - 当 `ProjectConfig.project_type == COURSE` 时：`anchor` 必须存在，且必须满足 1.3.1 的 COURSE 锚点规则。
  - 当 `ProjectConfig.project_type == BOOK` 时：`anchor` 必须存在，且必须满足 1.3.1 的 BOOK 锚点规则。
  - 当 `ProjectConfig.project_type == LOOSE_POINTS` 时：`anchor is None`。

提交期强制校验  
- 无（不新增提交期强制项）。  

失败语义  
- `commit()` 失败：必须整体回滚且对外不可见；会话进入失败关闭态，不得复用。  
- `get`：不存在抛 `NotFound`。  
- `add`：ID 已存在为 `PreconditionFailure`（且不产生任何写入）。  
- `update`：ID 不存在抛 `NotFound`；目标为 `DELETED` 时抛 `PreconditionFailure`。  
- `append_insight`：目标为 `DELETED` 时抛 `PreconditionFailure`。  

跨仓库可解析性（强引用；提交生效必须可解析）

- 强约束：若 `RecallPoint.anchor != None`，则 `RecallPoint.anchor.instance_id` 为强引用。任何已提交状态中，该 `anchor.instance_id` 都必须能在 `InstanceRepository` 中解析到。
- 强约束：`RecallPoint.references` 中每个 `RecallPointId` 都是对同项目既有 RecallPoint 的强引用；任何写入成功后的已提交状态中，这些 ID 都必须能在 `RecallPointRepository` 中解析到，且目标 `state == ACTIVE`。
- Enforcement 点（强约束）：该可解析性必须作为 `RecallPointRepository.add/update` 的写前条件检查（precondition failure，0b.5）执行：
  - 仅当 `anchor != None` 时，在 mutation session 内、在产生任何 staged 写入之前，调用 `InstanceRepository.get(session, anchor.instance_id)`；若 `NotFound`，对外统一映射为 `PreconditionFailure`。
  - 该检查必须在 `session.project_id` 作用域内执行；不得解析到其他项目的 `Instance`。
  - 对 `references` 中的每个 ID，必须在 mutation session 内、在产生任何 staged 写入之前调用 `RecallPointRepository.get(session, reference_id)`；若 `NotFound` 或目标 `state != ACTIVE`，对外统一映射为 `PreconditionFailure`。
- 非目标：不在系统级 `commit()`（0b.7.1）追加额外强制校验；该约束仅由写接口前置条件保证。

更新语义（强约束）  
- RecallPoint 更新只改变该 RecallPoint 的内容事实；系统不对其他对象做隐式级联修改或重排。任何引用该 `recall_point_id` 的 `LearningTask.recall_point_ids`、RangeSnapshot 快照、既有 ReviewTask 的 `input_range_id`/`result_range_id` 均不因 RecallPoint 更新而变化。  

删除语义（强约束；墓碑删除）
- `RecallPoint` 的删除必须为逻辑删除（墓碑删除），不得物理删除单条记录；项目删除（4.1.7）是唯一允许清除墓碑对象的路径。
- `mark_deleted(...)` 成功提交后，目标 RecallPoint 必须满足：`state == DELETED` 且 `deleted_at` 为调用时提供的系统时间戳；其 `question/answer/insights/anchor/created_at` 保持既有已提交值不变。
- `DELETED` 的 RecallPoint 仍必须可通过 `get/maybe_get/all` 解析，以维持既有 `LearningTask`、`RangeSnapshot`、`ReviewTask`、`RecallPointReviewRecord`、`AsrArtifact` 等历史引用的完整性。
- 非追溯性（强约束）：删除不得追溯改写任何既有 `LearningTask.recall_point_ids`、`RangeSnapshot.recall_point_ids`、既有 `ReviewTask.input_range_id/result_range_id`，也不得取消、重排或缩短任何已创建但尚未执行的 `ReviewTask` 输入范围；这些对象仍按其历史已提交事实继续存在。
- 自删除提交生效起，该 RecallPoint 不得再进入任何新的 `LearningTask.recall_point_ids`、任何新的 `covered_rp_ids(...)`、任何新的 `seed_range_id` / `result_range_id`、任何新的聚合上推范围、任何推荐候选，以及任何节点作用域的“当前内容”导出结果。

---

<a id="toc-1-5"></a>

### 1.5 LearningTask（学习任务）

<a id="toc-1-5-1"></a>

#### 1.5.1 数据模型

用途  
表达一个复习范围：一组复述点 ID 的有序序列。序列顺序即遍历顺序。

存储字段  
- 结构字段  
  - `project_id: ProjectId`
  - `learning_task_id: LearningTaskId`  
  - `recall_point_ids: Tuple[RecallPointId, ...]`（非空，且顺序有意义）
- 描述字段  
  - `title: str`

派生字段  
- `size: int = len(recall_point_ids)`  
- `covered_instance_id_set(task, recall_points_repo) -> Set[InstanceId]`
  - 语义：遍历 `recall_point_ids`，对其中 `anchor != None` 的项取其 `anchor.instance_id` 去重。
  - 历史视角（强约束）：该派生量按 `LearningTask.recall_point_ids` 的已提交存储内容解释，不做 `ACTIVE/DELETED` 过滤；若其中某个 `RecallPointId` 仍可解析到墓碑对象，且其 `anchor != None`，则其 `anchor.instance_id` 仍计入本派生量。
  - 说明：若需要“当前内容视角”的范围派生，必须使用 1.6.1 的 `covered_rp_ids(...)` 及其下游派生；实现不得把本派生量隐式解释为当前内容视图。

<a id="toc-1-5-2"></a>

#### 1.5.2 仓库接口

仓库

关联仓库  
- `LearningTaskRepository`

写接口  
- `add(session: MutationSession, task: LearningTask) -> None`
  - 新增；若 `learning_task_id` 已存在，必须抛 `PreconditionFailure`（0b.5）。  
  - 写前检查：必须满足 1.5.3 的 `add` 写前条件；失败为 `PreconditionFailure` 且不产生任何写入。  
- `update(session: MutationSession, task: LearningTask) -> None`
  - 语义：更新既有 LearningTask。最小允许更新字段为 `title`；`learning_task_id` 与 `recall_point_ids` 在本最小规格中视为不可变。  
  - NotFound：若 `learning_task_id` 不存在，必须抛 `NotFound`。  
  - 写前检查：必须满足 1.5.3 的 `update(title-only)` 写前条件；失败为 `PreconditionFailure` 且不产生任何写入。  

读接口  
- `get(session: MutationSession, learning_task_id: LearningTaskId) -> LearningTask`  
- `maybe_get(session: MutationSession, learning_task_id: LearningTaskId) -> Optional[LearningTask]`  
- `all(session: MutationSession) -> Sequence[LearningTask]`

Queries（常用派生查询的仓库承诺）  
- `covered_instance_id_set(session: MutationSession, learning_task_id: LearningTaskId, recall_points_repo: RecallPointRepository) -> Set[InstanceId]`  
  - Postcondition：按历史视角遍历任务的 `recall_point_ids`，对其中 `anchor != None` 的 RecallPoint（包含可解析墓碑对象）取其 `anchor.instance_id` 去重。  

<a id="toc-1-5-3"></a>

#### 1.5.3 一致性与校验

索引不变式  
- `learning_task_id` 唯一。  

`add` 写前条件  
- `learning_task_id` 非空。  
- `recall_point_ids` 非空。  
- `recall_point_ids` 中每个 `RecallPointId` 必须可解析，且其 `RecallPoint.state == ACTIVE`。  
- `title` 非空（去除首尾空白后必须非空）。  

`update(title-only)` 写前条件  
- `learning_task_id` 非空。  
- `title` 非空（去除首尾空白后必须非空）。  
- `recall_point_ids` 必须与更新前已提交值完全一致；实现不得在该入口中改写、重排、过滤或重新绑定既有 `recall_point_ids`。  
- 强约束：由于本入口不允许改写 `recall_point_ids`，实现不得因其中历史上已存在但当前 `state == DELETED` 的 RecallPoint 而拒绝 title-only 更新。  

提交期强制校验  
- 任务内去重（commit 强制）：`recall_point_ids` 中不得出现重复 `RecallPointId`；否则 `commit()` 必须失败并整体回滚，对外不可见。  

失败语义  
- `commit()` 失败：必须整体回滚且对外不可见；会话进入失败关闭态，不得复用。  
- `get`：不存在抛 `NotFound`。  
- `add`：ID 已存在为 `PreconditionFailure`（且不产生任何写入）。  
- `covered_instance_id_set`：若某 `RecallPointId` 不可解析，必须抛 `NotFound`。  

非目标  
- 不在本节提升任何跨仓库引用可解析性为提交期强制。  

---

<a id="toc-1-6"></a>

### 1.6 LearningTaskNode（学习任务节点）

<a id="toc-1-6-1"></a>

#### 1.6.1 数据模型

用途  
描述“复习范围结构树”。叶子节点绑定一个学习任务；容器节点不绑定学习任务，只维护 `children` 与顺序；可调度入口由 `node_id` 标识。

对象类型  
- `LearningTaskLeaf`（叶子）  
- `LearningTaskContainer`（容器）

存储字段（Leaf）  
- 结构字段  
  - `project_id: ProjectId`
  - `node_id: LearningTaskNodeId`  
  - `parent_id: Optional[LearningTaskNodeId]`  
  - `bound_learning_task_id: LearningTaskId`
- 描述字段  
  - `title: str`

存储字段（Container）  
- 结构字段  
  - `project_id: ProjectId`
  - `node_id: LearningTaskNodeId`  
  - `parent_id: Optional[LearningTaskNodeId]`  
  - `children: Sequence[LearningTaskNodeId]`  
- 描述字段  
  - `title: str`

语义  
- 叶子节点绑定且仅绑定一个学习任务。  
- 容器节点不绑定学习任务，只维护 `children` 与顺序；可调度入口由 `node_id` 标识。  
- 容器的子节点应保持同质：要么全叶子，要么全容器（不混杂）。

派生：covered_rp_ids(node)

定义  
给定任一 `node: LearningTaskNodeId`，其覆盖复述点序列定义为：
- 若 `node` 为叶子节点：返回其 `bound_learning_task_id` 对应 LearningTask 的 `recall_point_ids` 中所有满足 `RecallPoint.state == ACTIVE` 的 ID 子序列（保持原顺序）。
- 若 `node` 为容器节点：按 `children` 的顺序进行 DFS 遍历，拼接各子节点的 ACTIVE 复述点子序列，得到一个有序序列。

序列稳定性（必须写死的规则）  
- 遍历顺序以 `LearningTaskNodeRepository` 中的 `children` 顺序为权威。  
- 去重策略（强约束）：必须**不去重**（完全保留序列语义），以保证 seed_range 与 RangeSnapshot 的 `intern`（内容寻址）语义稳定。  
- ACTIVE 过滤（强约束）：`covered_rp_ids(...)` 是“当前内容视角”派生结果；历史上仍存在于 `LearningTask.recall_point_ids` 中、但当前已 `DELETED` 的 RecallPoint，必须在该派生结果中被过滤掉。  
- 与 4.1.6 的关系（语义联动）：若系统强制 4.1.6“复述点归属唯一”，则不同 LearningTask 之间不会共享同一 `RecallPointId`，因此 `covered_rp_ids` 在“不去重”策略下天然不引入跨任务重复；若 4.1.6 不强制，则不同叶子任务可能引用相同 `RecallPointId`，从而 `covered_rp_ids` 可能出现重复 ID，并导致 RangeSnapshot `intern` 的命中与快照规模发生显著变化（潜在膨胀）。  

<a id="toc-1-6-2"></a>

#### 1.6.2 仓库接口

仓库

关联仓库  
- `LearningTaskNodeRepository`

对象集合  
- 同仓库存放 `LearningTaskLeaf` 与 `LearningTaskContainer`（同一 `node_id` 命名空间）。

写接口  
- `add(session: MutationSession, node: LearningTaskLeaf | LearningTaskContainer) -> None`
  - 新增；若 `node_id` 已存在，必须抛 `PreconditionFailure`（0b.5）。
  - 写前条件（强约束；0b.5）：若 `node` 为 Leaf，则必须满足 `LearningTaskRepository.get(session, node.bound_learning_task_id)` 可解析；若不可解析（`NotFound`），对外必须映射为 `PreconditionFailure`，且失败不得产生任何 staged 写入。
  
- 结构化操作：`push_up(session: MutationSession, candidate_child_ids: Tuple[LearningTaskNodeId, ...], title: str, new_parent_id: Optional[LearningTaskNodeId], grand_parent_id: Optional[LearningTaskNodeId]) -> LearningTaskNodeId`
  - 语义：把一组候选子节点提升为新容器并重挂到祖父（若提供）。  
  - 事务与 TOCTOU（强约束，0b.3）：`push_up` 必须在一次系统事务 / mutation session 内完成其前置条件判定与结构重挂写入，不得拆成两段式。  
  - 保证：对涉及的 parent/children 指针做一致的重挂；不对学习任务语义做推断。  

读接口  
- `get(session: MutationSession, node_id: LearningTaskNodeId) -> LearningTaskLeaf | LearningTaskContainer`  
- `maybe_get(session: MutationSession, node_id: LearningTaskNodeId) -> Optional[...]`  
- `all(session: MutationSession) -> Sequence[...]`

结构 Queries（强约束）  
- `path_ids/depth/covered_rp_ids` 等结构查询，其语义与失败语义必须与 1.2.2 的对应条款一致，并以本仓库的 1.6.3 树一致性约束作为“结构一致”的判定基准：  
  - 若 `node_id` 不存在：必须抛 `NotFound`。  
  - 在 mutation session 内，若会话内读视图（in-session：一致读视图 + 本会话 staged 写入）所呈现的结构尚未满足 1.6.3 的提交期树一致性约束，则结构查询必须抛 `StructuralInconsistencyError`；不得返回部分结果，不得在读路径触发隐式修复或隐式校验。  

<a id="toc-1-6-3"></a>

#### 1.6.3 一致性与校验

索引不变式  
- `node_id` 唯一。  
- `LearningTaskId` 绑定唯一性（强约束）：同一 `LearningTaskNodeRepository` 内，一个 `LearningTaskId` 必须且只能绑定一个 Leaf 节点。  

写前条件  
- `node_id` 非空。  
- `bound_learning_task_id` 非空（仅 Leaf）。  
- 绑定唯一性（写前条件；强约束）：对 Leaf 节点的 `add(session, node)`，若将导致同一 `bound_learning_task_id` 被多个 Leaf 绑定，则该 `add` 必须在产生任何 staged 写入之前抛 `PreconditionFailure`；不得推迟到 `commit()`。  

提交期强制校验  
- 树一致性（commit 强制）：  
  - 引用存在性：对任一 Container，`children` 中每个 `child_id` 必须可解析。  
  - 双向一致：  
    - 对任一 Container `p`，对任一 `child_id ∈ p.children`，必须满足 `child.parent_id == p.node_id`；  
    - 对任一节点 `n`，若 `n.parent_id = p`，则必须满足 `n ∈ p.children`。  
  - 单父：任何节点不得同时出现在两个不同容器的 `children` 中。  
  - 同质性：同一容器的子节点必须同质（全 Leaf 或全 Container；混杂视为结构不一致）。  
  - 无环：禁止 `parent_id` 回溯成环，且 `children` 引用图中禁止可达环。  

失败语义  
- 强制校验失败：`commit()` 必须失败并回滚（0b.1.2）。  
- `get`：不存在抛 `NotFound`。  
- `add`：ID 已存在为 `PreconditionFailure`（且不产生任何写入）。  
- Query 前置条件：默认只对已提交且通过校验的状态定义。  

---

<a id="toc-1-7"></a>

### 1.7 RangeSnapshot（范围快照池）

<a id="toc-1-7-1"></a>

#### 1.7.1 数据模型

用途  
不可变的 RecallPointId 有序序列快照（去重快照池中的一个快照）。用于：
- 复习输入范围（ReviewTask.input_range_id）的去重存储；
- 复习结果范围（ReviewTask.result_range_id）的去重存储；
- 聚合父节点“覆盖范围”的去重存储（covered_rp_ids -> intern）。

重要声明（强约束）
- `RangeSnapshot` 是历史快照池，不因 RecallPoint 后续被墓碑删除而自动改写。
- `RangeSnapshot.recall_point_ids` 中出现 `DELETED` 的 RecallPointId 仍视为合法历史引用；其可解析性口径仅要求该 ID 仍能在 `RecallPointRepository` 中解析到墓碑对象。

存储字段  
- 结构字段  
  - `project_id: ProjectId`
  - `range_id: RangeId`  
  - `recall_point_ids: Tuple[RecallPointId, ...]`（非空；有序）

<a id="toc-1-7-2"></a>

#### 1.7.2 仓库接口

仓库

关联仓库  
- `RangeSnapshotRepository`

写接口  
- `add(session: MutationSession, snapshot: RangeSnapshot) -> None`
  - 新增；若 `range_id` 已存在，必须抛 `PreconditionFailure`（0b.5）。  
  - 写前检查：必须满足 1.7.3 的 Write-time preconditions；失败为 `PreconditionFailure` 且不产生任何写入。  

读接口  
- `get(session: MutationSession, range_id: RangeId) -> RangeSnapshot`  
- `maybe_get(session: MutationSession, range_id: RangeId) -> Optional[RangeSnapshot]`  
- `all(session: MutationSession) -> Sequence[RangeSnapshot]`

Queries  
- `intern(session: MutationSession, recall_point_ids: Tuple[RecallPointId, ...]) -> RangeId`  
  - 语义：对给定有序序列进行内容寻址去重；若已存在等价快照则返回既有 `range_id`，否则创建新快照并返回其 `range_id`。  
  - 等价快照（equivalent snapshot）定义：当且仅当 `recall_point_ids` 元组完全相同（长度、元素、顺序均一致）。  
  - 并发与重试语义（强约束；用于避免实现分叉）：  
    - `intern` 属于典型 TOCTOU 场景；实现必须保证不会产生“同一 tuple 对应多个 range_id”的已提交状态（见 1.7.3 内容寻址唯一性）。  
    - 说明（与系统边界对齐；强约束）：在 0b.4 所定义的“单进程单实例 + single-writer”边界下，`intern` 不得因并发写入竞争产生提交期唯一性冲突；若发生则视为实现违反 0b.4 或底层存储损坏。  

<a id="toc-1-7-3"></a>

#### 1.7.3 一致性与校验

索引不变式  
- `range_id` 唯一。  
- `recall_point_ids` 为不可变有序序列（Tuple）；顺序稳定。  

写前条件  
- `range_id` 非空。  
- `recall_point_ids` 非空。  
- `add`：`range_id` 不得已存在；否则为 `PreconditionFailure`（且不产生任何写入）。  
- `intern`：输入为有序 Tuple（长度、元素、顺序均有意义）；等价快照定义见 1.7.2。  

提交期强制校验  
- 内容寻址唯一性（commit 强制；仓库内部一致性）：  
  - 仓库中不得存在两个不同的 `range_id` 对应完全相同的 `recall_point_ids` 元组（长度、元素、顺序均一致）；否则 `commit()` 必须失败并回滚（0b.1.2）。  
- 跨仓库引用可解析性（禁止进入提交期强制）：不得在 `commit()` 强制检查 `recall_point_ids` 在 `RecallPointRepository` 可解析。  

失败语义  
- `commit()` 失败：必须整体回滚且对外不可见；会话进入失败关闭态，不得复用。  
- `get`：不存在抛 `NotFound`。  
- `add`：ID 已存在为 `PreconditionFailure`（且不产生任何写入）。  

显式校验接口 / 非目标  
- `recall_point_ids` 的可解析性校验必须通过显式校验接口 `validate_recall_point_ids_resolvable(session, range_id) -> ValidationResult` 完成；该校验不得在读路径或 `commit()` 中隐式触发，且不得改写既有已提交事实。  
- 强约束：对 `validate_recall_point_ids_resolvable(...)` 而言，`DELETED` 的 RecallPoint 仍视为 `resolvable`；只有“无法解析到任何 RecallPoint 对象”才构成 `NOT_FOUND`。  

---



---

<a id="toc-1-8"></a>

### 1.8 AuditLogEvent（运行日志/审计事件）

定位（强约束；纯审计）
- 本对象用于记录系统对外入口（4.5）的“成功提交动作”的运行日志/审计轨迹。
- 该对象为**纯审计**：任何系统协议/门禁/派生计算不得读取或依赖 AuditLogEvent 的存在与内容；不得将其作为业务事实输入（见 4.6）。
- 该对象不进入 0b.7.1 的提交期强制集合（不得扩大闭包）。

<a id="toc-1-8-1"></a>

#### 1.8.1 数据模型

存储字段
- `project_id: ProjectId`
- `event_id: str`
  - 语义：项目内唯一事件 ID（实现可用 UUID）。
- `occurred_at: Timestamp`
  - 语义：事件发生时间戳（UTC；系统生成，见 0a.10）。
- `kind: AuditEventKind`
  - 语义：事件类型枚举（见 0a 常量清单）。
- `api_name: str`
  - 语义：触发该事件的系统对外入口名；必须等于 4.5 白名单入口名之一。
- `result: AuditResultCode`
  - 语义：本规格仅强制记录成功提交，因此 `result` 必须为 `OK`。
- `payload: str`
  - 语义：审计载荷（建议为 JSON 字符串）。强约束：仅允许写入摘要信息（计数/ID/布尔/哈希）；不得写入大对象全量内容（例如完整 Q/A 列表），以避免存储爆炸与隐私泄漏。

<a id="toc-1-8-2"></a>

#### 1.8.2 仓库接口

仓库
- 关联仓库：`AuditLogRepository`

写接口
- `append(session: MutationSession, event: AuditLogEvent) -> None`
  - 语义：追加一条审计事件。
  - 写前条件（强约束；0b.5）：`event.project_id == session.project_id`；否则必须抛 `PreconditionFailure` 且不产生任何 staged 写入。

读接口
- `all(session: MutationSession) -> Sequence[AuditLogEvent]`
  - 返回顺序（强约束）：先按 `occurred_at` 升序，再按 `id_canonical_text(event_id)` 升序。
- （可选）`delete_all(session: MutationSession) -> None`
  - 语义：删除 `session.project_id` 作用域内全部审计事件；仅用于 4.1.7 `delete_project`。

<a id="toc-1-8-3"></a>

#### 1.8.3 一致性与校验

索引不变式
- `event_id` 在同一 `project_id` 作用域内唯一。

提交期强制校验
- 无（不新增提交期强制项）。

<a id="toc-1-11"></a>

### 1.11 AsrArtifact（ASR 转写产物）

用途  
本节现行语义改为“legacy/兼容性的 ASR 临时转写结果”。ASR 结果仍可作为兼容接口返回给调用方，但现行产品的播放器字幕与 LLM 补充上下文主路径不得再依赖 ASR；实现必须优先且仅检查“视频同目录下是否存在同名字幕文件”，若存在则直接把该字幕文件用作播放器字幕或 LLM 的补充工具输入。推荐支持的字幕扩展名至少包括 `.srt / .vtt / .ass / .ssa`。

重要声明（强约束）  
- 现行产品不得再使用服务端 `ffmpeg` 或浏览器 `ffmpeg.wasm` 为播放器字幕或 LLM 上下文临时切片/生成 ASR。  
- 若找不到同目录同名字幕文件，则播放器字幕与 LLM 补充上下文路径应视为“无额外字幕输入”，而不是自动回退到 ASR。  
- ASR 结果是派生信息（derived），其正确性不进入系统职责；系统只负责在一次请求内代理外部 ASR 调用并返回结果。  
- 结果不得写入 `ProjectConfig`、项目仓库、SQLite/Postgres 持久层、标准导出存储或服务端长期磁盘。  
- 浏览器允许以 `(project_id, recall_point_id, source_instance_id, window, provider)` 为键缓存复述点窗口结果，也允许以 `(project_id, source_instance_id, start_ms, end_ms, provider)` 为键缓存字幕时间块结果；典型实现可使用 `IndexedDB`。这些缓存均属于客户端实现细节，不构成项目事实。  
- 服务端允许在单次请求生命周期内使用临时文件（例如 `SERVER_FS` 兼容路径上的音频片段），但请求完成后必须清理；浏览器本地切片产生的中间结果不构成项目事实。  
- 结果不得在提交期强制校验中触发外部可达性探测（0b.7.2）。

语义类型  
- `AsrTranscriptResult`：一次 `request_asr(...)` 调用返回给客户端的临时结果；无项目内持久 ID。
- `InstanceAsrTranscriptResult`：一次 `request_instance_asr(...)` 或 `request_instance_asr_from_audio_upload(...)` 调用返回给客户端的实例时间块结果；无项目内持久 ID。

枚举  
- `AsrProvider = {WHISPER}`

返回字段（最小）
- `project_id: ProjectId`
- `provider: AsrProvider`
- `recall_point_id: RecallPointId`
  - 语义：本次临时转写围绕的复述点；必须可解析，且在新请求时其 `RecallPoint.state` 必须为 `ACTIVE`。
  - 强约束：墓碑对象可为历史只读事实保留解析性，但不得作为当前临时转写请求的创建目标。
- `source_instance_id: InstanceId`
  - 语义：该复述点最终落在的材料实例（由 `recall_point.anchor.instance_id` 派生并在返回值中带回）。
- `center_ms: int`
- `pre_ms: int`
- `post_ms: int`
  - 语义：以 `center_ms` 为中心的窗口；窗口为 `[center_ms-pre_ms, center_ms+post_ms]`。  
  - 写前条件：`pre_ms >= 0` 且 `post_ms >= 0`，且窗口长度不得超过实现上限（例如 5min；由实现写死或配置写死）。

- `segments: Tuple[AsrSegment, ...]`
  - `AsrSegment = {start_ms: int, end_ms: int, text: str, confidence: Optional[float]}`
  - 约束：`segments` 允许为空（识别失败或静音）；空不视为错误。

- `InstanceAsrTranscriptResult` 最小字段：
  - `project_id: ProjectId`
  - `provider: AsrProvider`
  - `source_instance_id: InstanceId`
  - `start_ms: int`
  - `end_ms: int`
  - `segments: Tuple[AsrSegment, ...]`
  - 语义：表示素材实例上 `[start_ms, end_ms]` 时间块的一次临时转写结果，适合字幕块缓存与播放器复用；不得被误建模为新的 `RecallPoint` 事实。

一致性与校验  
- `recall_point_id` / `source_instance_id` 必须可解析（请求前条件）；其中 `recall_point_id` 在当前转写请求时还必须满足其 `RecallPoint.state == ACTIVE`。  
- 新策略下，服务端不得为新 ASR 结果分配 `AsrArtifactId`，也不得创建新的持久化 `AsrArtifact`。  
- ASR 外部接口可达性不得进入提交期强制集合；失败必须以显式错误返回给调用方，并且不得留下任何项目级持久化写入（0b.5）。  

兼容说明（强约束）  
- 历史版本中已持久化的 `AsrArtifact / AsrArtifactId` 允许继续被只读接口解析、导出或被辅助对象引用，以保证旧数据兼容。  
- 现行 `request_asr(...)` 不再创建新的 `AsrArtifact`；新前端必须把返回值视为浏览器缓存对象，而不是项目事实。  
- 即使保留 `request_asr(...) / request_instance_asr(...)` 等兼容接口，产品 UI 也不得再把它们当作字幕服务或 LLM 默认工具入口。  

<a id="toc-1-11a"></a>

### 1.11a TempContextFragment（临时上下文片段）

用途  
把 ASR 片段、用户选中的局部文本或其等价局部证据固化为“临时上下文片段”，供 LLM 问答与候选点生成协议引用。该对象是辅助事实，不属于正式 `RecallPoint`，也不得直接进入导出主格式。

重要声明（强约束）  
- `TempContextFragment` 只服务于问答、候选点、故事化等辅助交互能力；其创建不得生成 `ReviewTask`、不得写入 `can_recall`、不得推进主调度闭环。  
- 该对象允许长期保存以支撑历史回看，但仍属于临时/辅助层，不得被 4.8 的标准导出接口隐式混入。  

存储字段（最小）
- `project_id: ProjectId`
- `temp_context_fragment_id: TempContextFragmentId`
- `created_at: Timestamp`
- `producer_runtime_kind: ClientRuntimeKind`
  - 强约束：新建时必须等于发起该创建的 `session.runtime_kind`。
- `source_recall_point_id: RecallPointId`
- `source_asr_artifact_id: Optional[AsrArtifactId]`
  - 语义：仅用于引用历史版本中已持久化的 `AsrArtifact`；现行浏览器缓存 ASR 流程不要求也通常不会提供该字段。
- `start_ms: Optional[int]`
- `end_ms: Optional[int]`
- `origin: Enum{ASR_SEGMENTS, USER_SELECTION}`
- `text: str`

仓库接口  
- 关联仓库：`TempContextFragmentRepository`
- `add(session: MutationSession, fragment: TempContextFragment) -> None`
- `get(session: MutationSession, temp_context_fragment_id: TempContextFragmentId) -> TempContextFragment`
- `all_by_recall_point(session: MutationSession, recall_point_id: RecallPointId) -> Sequence[TempContextFragment]`

一致性与校验  
- `temp_context_fragment_id` 项目内唯一。  
- `source_recall_point_id` 必须可解析。若 `source_asr_artifact_id` 非空，则其 `recall_point_id` 必须等于 `source_recall_point_id`。现行浏览器缓存 ASR 路径下，调用方应优先直接提交 `text`，而不是依赖服务端持久化 ASR 引用。  
- 创建 `TempContextFragment` 不得隐式修改任何 `RecallPoint / LearningTask / ReviewTask`。

<a id="toc-1-11b"></a>

### 1.11b QASession（LLM 问答会话）

用途  
记录一次或多次 LLM 问答交互的会话化上下文。它用于承载 prompt / response 历史与上下文片段引用，但不构成正式学习事实。

重要声明（强约束）  
- `QASession` 的存在不得改变任何 `RecallPoint`、`LearningTask`、`ReviewTask`、`ReviewChain` 或 `Convergence` 的语义。  
- 本对象允许引用 `TempContextFragment`、`RecallPoint`、`StoryArtifact` 等辅助对象，但任何模型回答都不得自动覆盖正式 `RecallPoint` 文本。  

存储字段（最小）
- `project_id: ProjectId`
- `qa_session_id: QASessionId`
- `created_at: Timestamp`
- `updated_at: Timestamp`
- `producer_runtime_kind: ClientRuntimeKind`
  - 强约束：新建与追加 turn 时必须等于发起写入的 `session.runtime_kind`。
- `context_fragment_ids: Tuple[TempContextFragmentId, ...]`
- `turns: Tuple[QATurn, ...]`
  - `QATurn = {question: str, answer: str, created_at: Timestamp}`

仓库接口  
- 关联仓库：`QASessionRepository`
- `add(session: MutationSession, qa_session: QASession) -> None`
- `append_turn(session: MutationSession, qa_session_id: QASessionId, turn: QATurn, context_fragment_ids: Optional[Tuple[TempContextFragmentId, ...]] = None) -> None`
- `get(session: MutationSession, qa_session_id: QASessionId) -> QASession`
- `all(session: MutationSession) -> Sequence[QASession]`

一致性与校验  
- `qa_session_id` 项目内唯一。  
- `context_fragment_ids` 中每个 `TempContextFragmentId` 必须可解析。  
- `turns` 允许追加但不得重写既有 turn 的 `question/answer` 文本。

<a id="toc-1-11c"></a>

### 1.11c CandidateRecallPoint（候选复述点）

用途  
表示由 LLM 问答会话或其上下文派生出的“候选复述点”。它与正式 `RecallPoint` 严格分离：在被用户显式接受之前，它不得进入学习/复习主闭环。

重要声明（强约束）  
- `CandidateRecallPoint` 不是正式 `RecallPoint`；任何推荐、弹幕、画布、故事或 LLM 问答都不得把它当成已提交学习事实。  
- 只有 2.13 `accept_candidate_recall_point(...)` 才允许把候选点转化为正式学习事实；拒绝或未处理状态都不得触发任务调度。  

存储字段（最小）
- `project_id: ProjectId`
- `candidate_recall_point_id: CandidateRecallPointId`
- `qa_session_id: QASessionId`
- `created_at: Timestamp`
- `state: CandidateRecallPointState`
- `question: RichContent`
- `answer: RichContent`
- `suggested_anchor: Optional[Anchor]`
- `supporting_fragment_ids: Tuple[TempContextFragmentId, ...]`
- `decision_at: Optional[Timestamp]`
- `accepted_recall_point_id: Optional[RecallPointId]`

仓库接口  
- 关联仓库：`CandidateRecallPointRepository`
- `add(session: MutationSession, candidate: CandidateRecallPoint) -> None`
- `mark_accepted(session: MutationSession, candidate_recall_point_id: CandidateRecallPointId, accepted_recall_point_id: RecallPointId, decision_at: Timestamp) -> None`
- `mark_rejected(session: MutationSession, candidate_recall_point_id: CandidateRecallPointId, decision_at: Timestamp) -> None`
- `get(session: MutationSession, candidate_recall_point_id: CandidateRecallPointId) -> CandidateRecallPoint`
- `all_by_qa_session(session: MutationSession, qa_session_id: QASessionId) -> Sequence[CandidateRecallPoint]`

一致性与校验  
- `candidate_recall_point_id` 项目内唯一。  
- `state` 只允许单向跃迁：`PENDING -> ACCEPTED` 或 `PENDING -> REJECTED`；一旦决策完成不得再次改写。  
- 当 `state == ACCEPTED` 时，`accepted_recall_point_id` 必须可解析；当 `state != ACCEPTED` 时该字段必须为空。  

<a id="toc-1-11d"></a>

### 1.11d MemoryCanvas（记忆画布）

用途  
为用户提供围绕正式复述点、候选点、临时上下文片段与故事化产物进行整理的持久化画布。画布只承担组织与观察作用，不得直接写入正式复习结果。

重要声明（强约束）  
- 画布是只读事实与用户整理动作的容器；它不得成为 `can_recall` 的写入口。  
- 画布当前态与历史版本必须分离，以支持“继续编辑”和“回看旧版本”这两类需求。  

值对象  
- `CanvasObjectRef = {kind: Enum{RECALL_POINT, CANDIDATE_RECALL_POINT, TEMP_CONTEXT_FRAGMENT, STORY_ARTIFACT}, object_id: str}`

存储字段（最小）
- `project_id: ProjectId`
- `memory_canvas_id: MemoryCanvasId`
- `title: str`
- `created_at: Timestamp`
- `updated_at: Timestamp`
- `producer_runtime_kind: ClientRuntimeKind`
  - 强约束：新建与编辑时必须为 `DESKTOP_NATIVE`。
- `object_refs: Tuple[CanvasObjectRef, ...]`
- `latest_version_id: Optional[MemoryCanvasVersionId]`

仓库接口  
- 关联仓库：`MemoryCanvasRepository`
- `add(session: MutationSession, canvas: MemoryCanvas) -> None`
- `set_latest_version(session: MutationSession, memory_canvas_id: MemoryCanvasId, latest_version_id: MemoryCanvasVersionId, updated_at: Timestamp) -> None`
- `get(session: MutationSession, memory_canvas_id: MemoryCanvasId) -> MemoryCanvas`
- `all(session: MutationSession) -> Sequence[MemoryCanvas]`

一致性与校验  
- `memory_canvas_id` 项目内唯一。  
- `object_refs` 里的对象必须全部可解析。  
- `MemoryCanvas` 只保存“当前工作上下文与版本指针”，不得把版本历史内联覆盖。

<a id="toc-1-11e"></a>

### 1.11e MemoryCanvasVersion（记忆画布版本）

用途  
记录画布在某一时刻被用户显式保存的不可变快照，用于历史回看、回溯比较与审计。

值对象  
- `CanvasNodeSnapshot = {object_ref: CanvasObjectRef, x: float, y: float, note: Optional[str]}`
- `CanvasEdgeSnapshot = {from_ref: CanvasObjectRef, to_ref: CanvasObjectRef, label: Optional[str]}`

存储字段（最小）
- `project_id: ProjectId`
- `memory_canvas_version_id: MemoryCanvasVersionId`
- `memory_canvas_id: MemoryCanvasId`
- `version_no: int`
- `saved_at: Timestamp`
- `nodes: Tuple[CanvasNodeSnapshot, ...]`
- `edges: Tuple[CanvasEdgeSnapshot, ...]`
- `summary_note: Optional[str]`

仓库接口  
- 关联仓库：`MemoryCanvasVersionRepository`
- `add(session: MutationSession, version: MemoryCanvasVersion) -> None`
- `get(session: MutationSession, memory_canvas_version_id: MemoryCanvasVersionId) -> MemoryCanvasVersion`
- `all_by_canvas(session: MutationSession, memory_canvas_id: MemoryCanvasId) -> Sequence[MemoryCanvasVersion]`

一致性与校验  
- `memory_canvas_version_id` 项目内唯一。  
- 对同一 `memory_canvas_id`，`version_no` 必须严格递增且不可复用。  
- 历史版本一经写入不得修改。

<a id="toc-1-11f"></a>

### 1.11f CanvasEdge（画布连线）

用途  
保存画布当前工作态下的边关系，使“编辑中的当前边集”与“已保存版本快照”分离。

存储字段（最小）
- `project_id: ProjectId`
- `canvas_edge_id: CanvasEdgeId`
- `memory_canvas_id: MemoryCanvasId`
- `from_ref: CanvasObjectRef`
- `to_ref: CanvasObjectRef`
- `label: Optional[str]`
- `updated_at: Timestamp`

仓库接口  
- 关联仓库：`CanvasEdgeRepository`
- `replace_all_for_canvas(session: MutationSession, memory_canvas_id: MemoryCanvasId, edges: Tuple[CanvasEdge, ...]) -> None`
- `all_by_canvas(session: MutationSession, memory_canvas_id: MemoryCanvasId) -> Sequence[CanvasEdge]`

一致性与校验  
- `canvas_edge_id` 项目内唯一。  
- `from_ref` 与 `to_ref` 必须都属于对应 `MemoryCanvas.object_refs` 的当前对象集合。  
- `replace_all_for_canvas(...)` 的语义是“整组替换当前边集”；不得改写任何既有 `MemoryCanvasVersion`。

<a id="toc-1-11g"></a>

### 1.11g StoryArtifact（故事化产物）

用途  
表示由已配置 LLM 服务基于正式事实、候选点、上下文片段或画布关系生成的故事化理解产物。它用于辅助理解与记忆，不用于替代正式 `RecallPoint`。

重要声明（强约束）  
- `StoryArtifact` 是派生/辅助对象，不是正式学习事实。  
- `StoryArtifact` 不能覆盖、替换或隐式改写任何 `RecallPoint.question/answer/insights`；若用户希望把其中内容纳入正式事实，必须通过显式编辑或候选点接受路径完成。  

存储字段（最小）
- `project_id: ProjectId`
- `story_artifact_id: StoryArtifactId`
- `created_at: Timestamp`
- `producer_runtime_kind: ClientRuntimeKind`
  - 强约束：新建时必须等于发起该创建的 `session.runtime_kind`。
- `title: str`
- `body: RichContent`
- `source_refs: Tuple[CanvasObjectRef, ...]`
- `qa_session_id: Optional[QASessionId]`
- `memory_canvas_id: Optional[MemoryCanvasId]`

仓库接口  
- 关联仓库：`StoryArtifactRepository`
- `add(session: MutationSession, story_artifact: StoryArtifact) -> None`
- `get(session: MutationSession, story_artifact_id: StoryArtifactId) -> StoryArtifact`
- `all(session: MutationSession) -> Sequence[StoryArtifact]`

一致性与校验  
- `story_artifact_id` 项目内唯一。  
- `source_refs` 中的对象必须可解析。  
- `StoryArtifact` 的写入不得隐式创建 `RecallPoint`、不得创建 `ReviewTask`、不得推进调度。  

<a id="toc-1-9"></a>

### 1.9 MediaAsset（项目富媒体资产）

用途  
为 `RichContent` 的 `IMAGE` 内容块提供项目内可解析的富媒体资产引用。媒体二进制内容存放在项目文件夹（`ProjectStorageConfig.project_root`）下的 `media/` 子树内；本对象只记录引用与元信息，不将二进制内容作为业务事实直接持久化在对象字段中。

<a id="toc-1-9-1"></a>

#### 1.9.1 数据模型

存储字段  
- `project_id: ProjectId`
- `asset_id: MediaAssetId`
  - 语义：项目内唯一富媒体资产 ID。
- `kind: Enum{IMAGE}`
  - 语义：本规格最小支持仅包含 IMAGE（后续可扩展）。
- `relative_path: PurePath`
  - 语义：相对 `ProjectStorageConfig.project_root` 的相对路径。
  - 强约束：必须位于 `media/` 子树内（例如 `media/...`），不得出现 `..` 路径穿越语义。
  - 写入规范化（强约束）：若输入为 `str`，必须先将 `\` 统一替换为 `/`，再以 `PurePosixPath` 解析并存储；不得做可达性探测或外部访问。判定“位于 media/ 子树”的口径写死为：`relative_path.as_posix().startswith('media/')`。
- `created_at: Timestamp`
- `mime_type: Optional[str]`

<a id="toc-1-9-2"></a>

#### 1.9.2 仓库接口（MediaAssetRepository）

写接口  
- `add(session: MutationSession, asset: MediaAsset) -> None`
  - 新增；若 `asset_id` 已存在，必须抛 `PreconditionFailure`（0b.5）。  
  - 写前条件（强约束）：`relative_path` 必须位于 `media/` 子树内。  

读接口  
- `get(session: MutationSession, asset_id: MediaAssetId) -> MediaAsset`
  - 不存在抛 `NotFound`。
- `maybe_get(session: MutationSession, asset_id: MediaAssetId) -> Optional[MediaAsset]`
- `all(session: MutationSession) -> Sequence[MediaAsset]`
  - 按 `id_canonical_text(asset_id)` 的 Unicode code point 字典序升序返回全量（见 0a.9）。

<a id="toc-1-9-3"></a>

#### 1.9.3 一致性与校验

- `asset_id` 在项目内唯一。  
- 富媒体文件的可达性/完整性不得进入系统级 `commit()` 的提交期强制集合（0b.7.2）；如需校验只能通过显式校验接口扩展实现。  



<a id="toc-1-12"></a>

### 1.12 RecallPointReviewRecord（复述点复习记录）

用途（强约束；业务事实）
- 记录每个复述点在每次复习中的结果与时间，用于：  
  (a) 基于遗忘曲线加权法（4.7.2）计算当前记忆强度、复习推荐指数与只读复习曲线；  
  (b) 向用户提供“复习历史”只读视图。  
- 该对象不是审计日志：允许被系统读取并用于派生计算/推荐判断。  
- 该对象为 append-only：只允许追加新记录，不允许修改或删除单条记录（项目删除除外）。

<a id="toc-1-12-1"></a>

#### 1.12.1 数据模型

存储字段
- `project_id: ProjectId`
- `record_id: str`
  - 语义：项目内唯一记录 ID（实现可用 UUID）。
- `recall_point_id: RecallPointId`
  - 语义：被记录的复述点。
- `review_task_id: ReviewTaskId`
  - 语义：产生该记录的复习任务 ID。
- `occurred_at: Timestamp`
  - 语义：本次复习执行时间戳（UTC；系统生成，见 0a.10）。强约束：应等于对应 ReviewTask 的 `executed_at`。
- `result: Enum{CAN_RECALL, CANNOT_RECALL}`
  - 语义：二值复习结果；与 2.2/4.5 `can_recall` 向量逐项对齐。

<a id="toc-1-12-2"></a>

#### 1.12.2 仓库接口（RecallPointReviewRecordRepository）

写接口（append-only）
- `append(session: MutationSession, record: RecallPointReviewRecord) -> None`
  - 写前条件（强约束；0b.5）：  
    - `record.project_id == session.project_id`；否则 `PreconditionFailure`。  
    - `RecallPointRepository.get(session, record.recall_point_id)` 可解析；否则 `PreconditionFailure`（失败不产生任何 staged 写入）。  
    - `ReviewTaskRepository.get(session, record.review_task_id)` 可解析；否则 `PreconditionFailure`。  

读接口
- `all_by_recall_point(session: MutationSession, recall_point_id: RecallPointId) -> Sequence[RecallPointReviewRecord]`
  - 返回顺序（强约束）：先按 `occurred_at` 升序，再按 `id_canonical_text(record_id)` 升序。
- `all(session: MutationSession) -> Sequence[RecallPointReviewRecord]`
  - 返回顺序：同上。

<a id="toc-1-12-3"></a>

#### 1.12.3 一致性与校验

索引不变式
- `record_id` 在同一 `project_id` 作用域内唯一。

提交期强制校验
- 无（不新增提交期强制项）。


<a id="toc-1-13"></a>

### 1.13 AggregationQueue（聚合队列，Layer-owned State）

权威定义（强约束）：本对象的数据模型、持久化字段形态与仓库接口以 4.4.1 为准；其为可提交对象，受 0b.1 的系统级事务语义约束。实现不得另起口径。


<a id="toc-1-14"></a>

### 1.14 AggregationEvent（聚合事件记录）

权威定义（强约束）：本对象的数据模型、持久化字段形态与仓库接口以 4.4.5 的“事件对象（持久化）/仓库接口”为准；其为可提交对象，受 0b.1 的系统级事务语义约束。实现不得另起口径。



<a id="toc-2"></a>

## 2. 事务协议（Transaction Protocols）

本章定义“面向业务事实（business facts）与运行时辅助对象”的写入协议：一次提交（mutation session + commit）只负责创建/更新第 1 章定义的核心对象与辅助对象（例如 `RecallPoint / LearningTask / LearningTaskNode / RangeSnapshot / AsrArtifact / TempContextFragment / QASession / CandidateRecallPoint / MemoryCanvas / MemoryCanvasVersion / CanvasEdge / StoryArtifact`），不直接创建运行时调度对象（`ReviewTask / Convergence / ReviewChain / Orchestrator / Queue`）。运行时调度对象的创建与推进由第 3/4 章的内部调度协议负责。

通用事务语义继承第 0b.1：会话内可暂时违背跨对象结构约束；`commit()` 对最终态一次性校验，失败则整组变更回滚；本章协议的读视图语义完全继承 0b.2：READ_ONLY 为 baseline read，READ_WRITE 为 in-session overlay read（read-your-writes）；不触发隐式修复。

本章目录：
- [2.1 协议：学习任务提交（LearningTask Submit）](#toc-2-1)
- [2.2 协议：复习提交（Review Submit）](#toc-2-2)
- [2.9 协议：服务端代理 ASR 转写（Request ASR）](#toc-2-9)
- [2.10 协议：提取临时上下文片段（Extract Temp Context Fragment）](#toc-2-10)
- [2.11 协议：LLM 问答（Ask LLM）](#toc-2-11)
- [2.12 协议：从问答生成候选复述点（Generate Candidate Recall Points）](#toc-2-12)
- [2.13 协议：接受候选复述点（Accept Candidate Recall Point）](#toc-2-13)
- [2.14 协议：拒绝候选复述点（Reject Candidate Recall Point）](#toc-2-14)
- [2.15 协议：创建记忆画布（Create Memory Canvas）](#toc-2-15)
- [2.16 协议：保存记忆画布版本（Save Memory Canvas Version）](#toc-2-16)
- [2.17 协议：设置画布连线（Set Canvas Edges）](#toc-2-17)
- [2.18 协议：生成故事化产物（Generate Story Artifact）](#toc-2-18)

---

<a id="toc-2-1"></a>

### 2.1 协议：学习任务提交（LearningTask Submit）

用途  
在一次原子提交中创建：学习任务（LearningTask）及其入口学习任务节点（LearningTaskNode）。

Request（输入载荷）
- `items: Sequence[(question: RichContent, answer: RichContent, anchor: Optional[Anchor], references: Sequence[RecallPointId])]`，非空
  - 每个 item 的 `references` 允许为空序列；其语义与 1.4 `RecallPoint.references` 一致。
- `title: str`，非空（强约束）

Read-set（读取项）
- 无（本协议不包含标题派生）

Write-set（写入产物；同一 commit 原子生效）
1) RecallPoint
- 为每个输入 item 分配新的 `RecallPointId`，写入：
  - `created_at`：由系统时钟生成的 UTC 时间戳（ms 语义；0a.10）。
  - `state = ACTIVE`
  - `deleted_at = None`
  - `question, answer, anchor, references`

2) LearningTask
- 分配新 `LearningTaskId`
- 写入：
  - `recall_point_ids`：
    - 为本提交创建的 RecallPointId 序列（顺序与输入 items 相同）
  - `title`：
    - 必须使用请求提供的 `title`

3) LearningTaskNode（入口节点）
- 分配新 `LearningTaskNodeId`
- 创建一个 Leaf 节点，并绑定 `bound_learning_task_id = learning_task_id`（入口标识为该节点的 `node_id`）
- 节点类型：
  - 默认：Leaf（容器节点通常由后续“聚合上推/结构化操作”产生；本协议不强制创建容器）
- `title`：可与 LearningTask.title 相同或由上层另定（本协议不强制）

派生计算（Deterministic derivations）
- RecallPointId 分配：由仓库/ID 生成器决定；需全局稳定可引用

强保证（commit 生效时保证）
- LearningTask 的 `recall_point_ids` 非空且顺序与请求一致
- 新建 ID（LearningTaskId / LearningTaskNodeId / RecallPointId 等）在各自仓库命名空间内唯一（由仓库 add 强制）
- 所有写入在同一次 commit 内原子生效；任一强制校验失败则整体回滚（0b.1.2）

弱保证 / 显式校验（仅通过显式 validate_* 产生独立结果）
- RecallPointId “归属唯一”（任一 RecallPointId 只允许属于一个 LearningTask）：本协议不默认承诺；如要承诺应在相应章节提升为全局不变量并在提交期强制集合中列出

Failure 语义
- 协议前置条件失败（0b.5）：  
  - 输入为空（items 为空）。 
  - 当 `project_type == COURSE` 时：任一 item 的 `anchor` 缺失、格式不是 `t=<毫秒>`，或其 `anchor.instance_id` 在 `InstanceRepository` 不可解析（`NotFound` 对外统一映射为 `PreconditionFailure`）。
  - 当 `project_type == BOOK` 时：任一 item 的 `anchor` 缺失、`anchor.position` 为空、`anchor.position` 误用 `t=<毫秒>` 格式，或其 `anchor.instance_id` 在 `InstanceRepository` 不可解析（`NotFound` 对外统一映射为 `PreconditionFailure`）。
  - 当 `project_type == LOOSE_POINTS` 时：任一 item 的 `anchor != None`。
  - 任一 item 的 `references` 含空值、重复值、自引用，或引用到同项目内不可解析 / 非 `ACTIVE` 的既有 RecallPoint。
  - 以上任一失败都不得产生任何写入（0b.5）。

备注
- 2.1 为“纯业务事实子协议”：不得作为系统对外入口单独提交。
- 系统对外的学习提交必须通过 4.5 的 `submit_learning_task(...)`，并且必须在同一 mutation session 内组合执行 2.1 + 4.3.2（Task Register），以满足 4.1.4 的系统级不变量（同一提交中创建 Convergence/ReviewChain 并登记到目标层 Orchestrator）；是否触发 Tick 由 4.2.4 的 `layer_mode` 决定。

---

<a id="toc-2-2"></a>

### 2.2 协议：复习提交（Review Submit, Binary）

用途
用户对某个 ReviewTask 的输入范围逐项给出二值判定（能复述/不能复述）；系统据此生成“重点列表”（不能复述项，保序）。重点列表（若非空）被去重写入 RangeSnapshot 池，并派生出本次 ReviewTask 的 `result_range_id`（可空表示“无重点”）。

本协议只定义派生与可持久化产物（RangeSnapshot 的 intern）；ReviewTask 的 `result_range_id` 写入与 `PENDING -> DONE`、Q2 出队必须由第 4 章的 ReviewTask Commit 原子完成（见 4.3.3）。

Request（输入载荷）

* `review_task_id: ReviewTaskId`
* `can_recall: Sequence[0|1]`：（实现输入承载允许 JSON 布尔；强约束：若收到 `true/false` 必须确定性映射为 `1/0`，再按本协议校验）

  * 非空
  * 长度必须与本次复习范围内的复述点序列等长，且按同序对齐
  * 语义：`1` = 能复述；`0` = 不能复述

Read-set（读取项）

* 仓库读取：

  * `ReviewTaskRepository.get(session, review_task_id)`：取得 `input_range_id`
  * `RangeSnapshotRepository.get(session, input_range_id)`：取得输入的 `rp_ids`
  * `RecallPointRepository`（协议前置条件检查；强约束）：

    * 对 `rp_ids` 中每个 ID 做解析（`get`）；任一 ID 不可解析必须视为协议前置条件失败（0b.5），且必须在 mutation session 内、在产生任何 staged 写入之前完成该判定（失败不产生任何写入）。

过程变量（Protocol-local variables）

* `rp_ids: Sequence[RecallPointId]`：输入范围的复述点序列（顺序即遍历顺序）
* `focus_rp_ids: Sequence[RecallPointId]`：

  * `focus_rp_ids = [rp_ids[i] for i if can_recall[i] == 0 and RecallPointRepository.get(session, rp_ids[i]).state == ACTIVE]`（保序）

Write-set（写入产物；同一 commit 原子生效）

* 当 `focus_rp_ids` 为空：不调用 intern，派生 `result_range_id = None`。
* 当 `focus_rp_ids` 非空：调用 `RangeSnapshotRepository.intern(session, tuple(focus_rp_ids)) -> result_range_id`。

  * 说明：本协议不强制把 `result_range_id` 写回 ReviewTask；该写回必须在 ReviewTask Commit（4.3.3）与 Q2 出队同事务原子完成。

派生计算（Deterministic derivations）

1. 解析范围序列 `rp_ids`

* `review_task = ReviewTaskRepository.get(session, review_task_id)`
* `input_snapshot = RangeSnapshotRepository.get(session, review_task.input_range_id)`
* `rp_ids = input_snapshot.recall_point_ids`

2. 长度一致性

* 必须 `len(can_recall) == len(rp_ids)`，且按索引对齐

3. 重点列表生成（不能复述项）

* `focus_rp_ids = [rp_ids[i] for i if can_recall[i] == 0 and RecallPointRepository.get(session, rp_ids[i]).state == ACTIVE]`
  * 强约束：历史输入范围中的 `DELETED` RecallPoint 不得再进入新的 `result_range_id`；若全部“不能复述项”都已 `DELETED`，则本次结果必须等价于空重点（`result_range_id = None`）。

强保证（commit 生效时保证）

* 长度一致：`len(can_recall) == len(rp_ids)`。
* `focus_rp_ids` 保序：保持输入 `rp_ids` 的相对顺序。
* `focus_rp_ids` 只允许包含当前 `state == ACTIVE` 的 RecallPointId。
* 若 `focus_rp_ids` 非空：对应的 `result_range_id` 指向一个可解析的 RangeSnapshot（由 intern 保证）。
* 任一强制校验失败则整体回滚（0b.1.2）。

Failure 语义

* PreconditionFailure（0b.5）：

  * `review_task_id` 不可解析。
  * 输入范围中的某个 `RecallPointId` 不可解析（必须在任何 staged 写入之前完成该判定）。
  * `len(can_recall) != len(rp_ids)`。
  * `can_recall` 中出现非 `0|1` 的值。
* 错误映射口径（强约束）：协议内部仓库读取 `get` 的 `NotFound` 对外统一映射为 `PreconditionFailure`（0b.5）。
* CommitTimeValidationFailure：若 `RangeSnapshotRepository.intern` 在并发下触发提交期校验失败则 `commit()` 失败并回滚（0b.1.2）。

备注

* 本协议不对 RecallPoint 内容做任何判断；只依据用户二值判定派生 `result_range_id`（可空）。

---

<a id="toc-2-9"></a>

### 2.9 协议：服务端代理 ASR 转写（Request ASR，legacy compatibility）

目的  
对某个 `RecallPoint` 的来源材料（通常为视频/音频）在其附近窗口执行一次 ASR 转写，返回临时 `AsrTranscriptResult`（1.11）给当前调用方。该协议保留仅为兼容旧接口或调试链路；现行产品不得再把它用于播放器字幕服务或 LLM 补充上下文。

SCHEDULING_EFFECT = NONE（强约束）  
- 本协议不得创建/入队任何 ReviewTask，不得推进 ReviewChain，不得触发 Orchestrator Tick。  
- 允许写入：不得写入任何新的项目事实；仅允许写入必要的审计事件。  

对外入口（并且必须纳入 4.5 系统对外入口白名单）  
- `request_asr(session: MutationSession, recall_point_id: RecallPointId, center_ms: int, pre_ms: int, post_ms: int, provider: AsrProvider=WHISPER, service_config: Optional[LocalServiceConfig]=None) -> AsrTranscriptResult`
- `request_instance_asr(session: MutationSession, instance_id: InstanceId, start_ms: int, end_ms: int, provider: AsrProvider=WHISPER, service_config: Optional[LocalServiceConfig]=None) -> InstanceAsrTranscriptResult`
- `request_instance_asr_from_audio_upload(session: MutationSession, instance_id: InstanceId, start_ms: int, end_ms: int, audio_bytes: bytes, audio_filename: Optional[str]=None, audio_content_type: Optional[str]=None, provider: AsrProvider=WHISPER, service_config: Optional[LocalServiceConfig]=None) -> InstanceAsrTranscriptResult`
  - 会话要求：`session.mode == READ_WRITE`。  
  - 运行时要求：不再有 Native-only 门禁；只要当前部署启用了 ASR 功能，`MOBILE_WEB / DESKTOP_WEB / DESKTOP_NATIVE` 都可调用本协议。  
  - 写前条件：  
    - `RecallPointRepository.get(session, recall_point_id)` 可解析，且其 `RecallPoint.state == ACTIVE`；若不可解析则 `NotFound`，若目标为 `DELETED` 则必须返回 `PreconditionFailure`。  
    - 必须能从该 RecallPoint 的 anchor 推导出 `source_instance_id`（材料实例）；否则 `PreconditionFailure`。  
    - `pre_ms >= 0` 且 `post_ms >= 0`，窗口长度不超过上限；否则 `PreconditionFailure`。  
    - 对实例时间块协议：`InstanceRepository.get(session, instance_id)` 必须可解析；`start_ms >= 0`、`end_ms > start_ms`，且块长不超过上限；否则 `PreconditionFailure`。  
    - 系统必须能够解析出可用的 `LocalServiceConfig`：优先使用本次请求显式给定的 `service_config`，若缺失则允许回退到当前登录用户已保存在服务端的账号级配置；若账号级配置缺失，再允许回退到部署级环境配置；若三者都不可用，则必须返回 `PreconditionFailure`。  
  - 缓存语义（强约束；写死）：  
    - 服务端不得依赖项目级持久化缓存。若前端希望避免重复调用，必须在浏览器侧自行缓存 `AsrTranscriptResult`。  
    - 播放器字幕实现不得按 `timeupdate` 或每次 seek 的细粒度事件直接重复请求；应按稳定时间块复用 `InstanceAsrTranscriptResult`，并优先命中浏览器缓存。  
  - 外部调用：  
    - 现行产品前端不得再使用 `ffmpeg.wasm` 对 `BROWSER_LOCAL` 素材做时间窗口裁剪，也不得把裁剪后音频上传为播放器字幕或 LLM 默认输入。  
    - 现行产品服务端不得再为了播放器字幕或 LLM 工具入口启用 `ffmpeg` 兼容切片路径。若实现为了旧接口兼容仍保留该能力，则必须明确视为非默认、非产品主路径。  
    - 若兼容接口仍被保留，其外部 ASR 端点既可以是 OpenAI 兼容 HTTPS ASR 服务，也可以是需要服务端适配的 provider-native ASR 服务（例如 DashScope 原生异步文件转写），但这不改变其 legacy/非主路径定位。  
    - `service_config.api_key` 可来自用户本次请求显式给定的临时配置、当前登录用户保存在服务端的账号级配置，也可来自部署级环境配置；系统必须仅在受信任的服务端边界使用该值，并且不得把它写入 `ProjectConfig`、项目仓库、标准导出或审计 payload。  
    - 音频提取与外部调用均不得在提交期强制校验中发生（0b.7.2）。  
  - 失败语义：  
    - 若缺少可用 `service_config`、材料文件不存在、材料类型不支持、本机缺少音频提取能力（例如 `ffmpeg`）、浏览器本地素材未获授权读取，或服务端兼容切片队列当前不可接受更多任务，必须返回 `PreconditionFailure`。  
    - ASR 服务不可达、超时或返回无效响应时，必须返回显式错误 `ExternalServiceError`（实现可复用更细分类名，但对外语义必须稳定），且不得留下部分 staged 写入（0b.5）。  
    - 允许返回空 segments 作为成功（例如静音或识别空）；空不视为错误。  

说明（强约束）  
- 本协议不定义“视频容器解析/解码”细节；其属于实现内部能力。对外可观察语义仅限于：成功则返回 `AsrTranscriptResult(segments)`，失败则不产生任何项目级写入。  
- 浏览器侧导出或复用必须基于本协议返回值自行缓存；服务端不得承诺跨请求复用新结果。  
- 现行产品若需要字幕或 LLM 补充上下文，必须优先走“同目录同名字幕文件”策略，而不是本协议。  
- 墓碑边界（强约束）：`DELETED` 的 RecallPoint 仍可作为历史事实被读取或被既有 legacy `AsrArtifact` 引用，但不得再通过本协议生成新的临时转写结果。  
- 若材料非音视频或无法提取音频，则必须 `PreconditionFailure`，并给出可解释错误摘要（例如“不支持的材料类型”）。  

---

<a id="toc-2-10"></a>

### 2.10 协议：提取临时上下文片段（Extract Temp Context Fragment）

目的  
把围绕某个复述点的局部证据提取为 `TempContextFragment`（1.11a），供 LLM 问答与候选点生成使用。

SCHEDULING_EFFECT = NONE（强约束）  
- 本协议不得创建/入队任何 `ReviewTask`，不得推进 ReviewChain，不得触发 Orchestrator Tick。  
- 允许写入：仅允许写入 `TempContextFragment`（1.11a）。  

对外入口  
- `extract_temp_context_fragment(session: MutationSession, recall_point_id: RecallPointId, source_asr_artifact_id: Optional[AsrArtifactId], start_ms: Optional[int], end_ms: Optional[int], text: Optional[str]) -> TempContextFragmentId`
  - 会话要求：`session.mode == READ_WRITE`。  
  - 运行时要求：无 Native-only 门禁；任一可写运行时都可执行。  
  - 写前条件：  
    - `RecallPointRepository.get(session, recall_point_id)` 可解析。  
    - `source_asr_artifact_id` 若非空，则必须可解析，且其 `recall_point_id == recall_point_id`；该路径仅用于 legacy 持久化 `AsrArtifact`。  
    - `text` 与 `(source_asr_artifact_id, start_ms, end_ms)` 至少要提供一类有效来源；两者均缺失时必须返回 `PreconditionFailure`。现行浏览器缓存 ASR 路径下，调用方通常应直接提供 `text`。  
  - 写入语义：  
    - 若提供 `source_asr_artifact_id`，系统可从目标 legacy `AsrArtifact.segments` 中裁剪或拼接局部文本；若同时提供 `text`，则以调用方显式给定文本为权威保存值。  
    - 新建 `TempContextFragment(producer_runtime_kind = session.runtime_kind, source_recall_point_id = recall_point_id, ...)`。  
  - 失败语义：任何输入校验失败或片段抽取失败都不得留下部分 staged 写入。  

---

<a id="toc-2-11"></a>

### 2.11 协议：LLM 问答（Ask LLM）

目的  
基于一个或多个 `TempContextFragment` 进行 LLM 问答，并把问答 turn 持久化到 `QASession`（1.11b）。

兼容说明  
为避免破坏既有接口名与审计事件名，本文仍沿用 `ask_local_llm(...)` 与 `REQUEST_LOCAL_LLM` 作为标识；其语义统一指“调用当前可用的 LLM 服务完成问答”，该服务可以是远程提供商 API，也可以是本机或局域网进程，不要求模型部署在用户本机。

SCHEDULING_EFFECT = NONE（强约束）  
- 本协议不得创建/入队任何 `ReviewTask`，不得推进 ReviewChain，不得触发 Orchestrator Tick。  
- 允许写入：仅允许写入 `QASession`（1.11b）。  

对外入口  
- `ask_local_llm(session: MutationSession, prompt: str, context_fragment_ids: Sequence[TempContextFragmentId], qa_session_id: Optional[QASessionId] = None) -> QASession`
  - 会话要求：`session.mode == READ_WRITE`。  
  - 运行时要求：`LOCAL_LLM_QA ∈ session.runtime_capabilities`。  
  - 写前条件：  
    - `prompt` 必须为非空字符串。  
    - `context_fragment_ids` 中每个 `TempContextFragmentId` 必须可解析。  
    - `NativeRuntimeConfig.local_models.llm_qa` 必须可用；否则 `PreconditionFailure`。  
    - 若 `llm_qa.api_key` 缺失，则系统必须能够从当前用户提供的凭据或部署级密钥中解析出可用鉴权信息；若仍不可用，则必须返回 `PreconditionFailure`。  
    - `qa_session_id` 若非空，则必须可解析。  
  - 写入语义：  
    - 当 `qa_session_id` 为空时，系统必须新建一个 `QASession`，并把本次问答写成其首个 `QATurn`。  
    - 当 `qa_session_id` 非空时，系统必须在既有 `QASession` 尾部追加一个新的 `QATurn`，并更新 `updated_at`。  
    - 系统必须通过受信任的服务端通道调用目标 LLM 服务；浏览器 / Web 客户端不得直接持有第三方模型服务的持久 API Key。  
    - 模型响应必须仅写入 `QASession.turns.answer`；不得直接改写任何正式 `RecallPoint`。  
  - 失败语义：模型服务不可达、超时、鉴权失败或返回无效响应时，必须返回显式错误且不得留下部分 staged 写入。  

---

<a id="toc-2-12"></a>

### 2.12 协议：从问答生成候选复述点（Generate Candidate Recall Points）

目的  
从 `QASession` 中提炼可供用户确认的 `CandidateRecallPoint`（1.11c）集合。

SCHEDULING_EFFECT = NONE（强约束）  
- 本协议不得创建正式 `RecallPoint`、不得创建/入队 `ReviewTask`、不得推进主调度。  

对外入口  
- `generate_candidate_recall_points_from_qa(session: MutationSession, qa_session_id: QASessionId, max_items: int = 5) -> Sequence[CandidateRecallPointId]`
  - 会话要求：`session.mode == READ_WRITE`。  
  - 运行时要求：`LOCAL_LLM_QA ∈ session.runtime_capabilities`。  
  - 写前条件：  
    - `qa_session_id` 必须可解析。  
    - `max_items >= 1`。  
    - `NativeRuntimeConfig.local_models.llm_qa` 必须可用，且系统必须可解析出用于候选点生成的可用鉴权信息；否则 `PreconditionFailure`。  
  - 写入语义：  
    - 系统必须基于 `QASession.turns` 与 `context_fragment_ids` 生成至多 `max_items` 个 `CandidateRecallPoint`。  
    - 所有新候选项必须写入 `state = PENDING`，并与来源 `qa_session_id` 建立显式关联。  
    - 候选项允许缺少 `suggested_anchor`；但缺少锚点的候选项在接受时必须由调用方补齐正式 `Anchor`。  
  - 强约束：本协议生成的是候选层对象，不得直接创建正式 `RecallPoint`。  

---

<a id="toc-2-13"></a>

### 2.13 协议：接受候选复述点（Accept Candidate Recall Point）

目的  
把一个 `CandidateRecallPoint` 显式转化为正式学习事实，同时保留其“来自候选层”的可追溯关系。

SCHEDULING_EFFECT = NONE（子协议层面；强约束）  
- 本协议本身只负责业务事实写入：创建正式 `RecallPoint / LearningTask / LearningTaskNode` 并更新候选状态。  
- 是否触发任务登记与调度，只能由 4.5 的对外入口在同一事务内组合调用 4.3.2 决定；本子协议不得直接创建/入队 `ReviewTask`。  

对外入口  
- `accept_candidate_recall_point(session: MutationSession, candidate_recall_point_id: CandidateRecallPointId, anchor: Anchor, title: Optional[str] = None) -> (learning_task_node_id: LearningTaskNodeId, recall_point_id: RecallPointId)`
  - 会话要求：`session.mode == READ_WRITE`。  
  - 运行时要求：无 LLM / Native 专属门禁；任一可写运行时都可执行。  
  - 写前条件：  
    - `CandidateRecallPointRepository.get(session, candidate_recall_point_id)` 必须可解析，且 `state == PENDING`。  
    - `anchor.instance_id` 必须可解析。  
  - 写入语义：  
    - 系统必须以该候选项的 `question/answer` 与调用方提供的正式 `anchor` 作为单 item 输入，执行一次等价于 2.1 的正式学习事实创建。  
    - 系统必须在同一事务内将候选项更新为 `state = ACCEPTED`，并写入 `accepted_recall_point_id` 与 `decision_at`。  
  - 强约束：本协议不得写入任何 `can_recall` 或复习结果；正式“会/不会”仍只能由 `executor_commit_review_task(...)` 写入。  

---

<a id="toc-2-14"></a>

### 2.14 协议：拒绝候选复述点（Reject Candidate Recall Point）

目的  
显式放弃一个候选复述点，而不影响正式学习事实。

SCHEDULING_EFFECT = NONE（强约束）  

对外入口  
- `reject_candidate_recall_point(session: MutationSession, candidate_recall_point_id: CandidateRecallPointId) -> None`
  - 会话要求：`session.mode == READ_WRITE`。  
  - 运行时要求：无 LLM / Native 专属门禁；任一可写运行时都可执行。  
  - 写前条件：  
    - 目标候选项必须可解析，且 `state == PENDING`。  
  - 写入语义：  
    - 在同一事务内将目标候选项更新为 `state = REJECTED`，并写入 `decision_at`。  
  - 强约束：拒绝不得级联删除或改写其来源 `QASession / TempContextFragment`。  

---

<a id="toc-2-15"></a>

### 2.15 协议：创建记忆画布（Create Memory Canvas）

目的  
创建一个新的 `MemoryCanvas`（1.11d），用于组织正式与辅助对象之间的关系。

SCHEDULING_EFFECT = NONE（强约束）  

对外入口  
- `create_memory_canvas(session: MutationSession, title: str, object_refs: Sequence[CanvasObjectRef]) -> MemoryCanvasId`
  - 会话要求：`session.mode == READ_WRITE`。  
  - 运行时要求：`session.runtime_kind == DESKTOP_NATIVE` 且 `MEMORY_CANVAS_EDIT ∈ session.runtime_capabilities`。  
  - 写前条件：  
    - `title` 必须非空。  
    - `object_refs` 可为空，但若非空则每个对象必须可解析。  
  - 写入语义：  
    - 新建 `MemoryCanvas(producer_runtime_kind = session.runtime_kind, latest_version_id = None, ...)`。  
  - 强约束：创建画布不得隐式生成版本；版本只能通过 2.16 显式保存。  

---

<a id="toc-2-16"></a>

### 2.16 协议：保存记忆画布版本（Save Memory Canvas Version）

目的  
把当前画布工作态保存为不可变版本，支持历史回看。

SCHEDULING_EFFECT = NONE（强约束）  

对外入口  
- `save_memory_canvas_version(session: MutationSession, memory_canvas_id: MemoryCanvasId, nodes: Sequence[CanvasNodeSnapshot], summary_note: Optional[str] = None) -> MemoryCanvasVersionId`
  - 会话要求：`session.mode == READ_WRITE`。  
  - 运行时要求：`session.runtime_kind == DESKTOP_NATIVE` 且 `MEMORY_CANVAS_EDIT ∈ session.runtime_capabilities`。  
  - 写前条件：  
    - `memory_canvas_id` 必须可解析。  
    - `nodes` 中每个 `object_ref` 必须属于该画布当前 `object_refs`。  
  - 写入语义：  
    - 系统必须读取当前 `CanvasEdgeRepository.all_by_canvas(...)` 的边集，并把它与 `nodes` 一起冻结写入新的 `MemoryCanvasVersion`。  
    - 系统必须在同一事务内更新 `MemoryCanvas.latest_version_id`。  
  - 强约束：既有 `MemoryCanvasVersion` 不得被覆盖。  

---

<a id="toc-2-17"></a>

### 2.17 协议：设置画布连线（Set Canvas Edges）

目的  
更新画布当前工作态的边关系。

SCHEDULING_EFFECT = NONE（强约束）  

对外入口  
- `set_canvas_edges(session: MutationSession, memory_canvas_id: MemoryCanvasId, edges: Sequence[(from_ref: CanvasObjectRef, to_ref: CanvasObjectRef, label: Optional[str])]) -> None`
  - 会话要求：`session.mode == READ_WRITE`。  
  - 运行时要求：`session.runtime_kind == DESKTOP_NATIVE` 且 `MEMORY_CANVAS_EDIT ∈ session.runtime_capabilities`。  
  - 写前条件：  
    - `memory_canvas_id` 必须可解析。  
    - 所有 `from_ref/to_ref` 都必须属于目标画布的 `object_refs`。  
  - 写入语义：  
    - `CanvasEdgeRepository.replace_all_for_canvas(...)` 必须以“整组替换”方式写入当前边集。  
  - 强约束：该更新只影响当前工作态，不得追溯改写既有 `MemoryCanvasVersion.edges`。  

---

<a id="toc-2-18"></a>

### 2.18 协议：生成故事化产物（Generate Story Artifact）

目的  
基于已配置 LLM 服务为正式与辅助对象生成一个独立的 `StoryArtifact`（1.11g），用于帮助理解与记忆。

SCHEDULING_EFFECT = NONE（强约束）  
- 本协议只允许写入 `StoryArtifact`，不得隐式改写正式学习事实。  

对外入口  
- `generate_story_artifact(session: MutationSession, title: str, source_refs: Sequence[CanvasObjectRef], qa_session_id: Optional[QASessionId] = None, memory_canvas_id: Optional[MemoryCanvasId] = None) -> StoryArtifactId`
  - 会话要求：`session.mode == READ_WRITE`。  
  - 运行时要求：`STORY_GENERATION ∈ session.runtime_capabilities`。  
  - 写前条件：  
    - `title` 必须非空。  
    - `source_refs` 必须非空，且每个引用都必须可解析。  
    - `NativeRuntimeConfig.local_models.story_generator` 必须可用；否则 `PreconditionFailure`。  
    - 若 `story_generator.api_key` 缺失，则系统必须能够从当前用户提供的凭据或部署级密钥中解析出可用鉴权信息；若仍不可用，则必须返回 `PreconditionFailure`。  
    - `qa_session_id / memory_canvas_id` 若非空，则必须可解析。  
  - 写入语义：  
    - 系统必须通过受信任的服务端通道调用目标故事生成服务；浏览器 / Web 客户端不得直接持有第三方模型服务的持久 API Key。  
    - 系统必须把模型响应固化为新的 `StoryArtifact(producer_runtime_kind = session.runtime_kind, ...)`。  
  - 强约束：`StoryArtifact` 的写入不得覆盖任何 `RecallPoint.question/answer/insights`，也不得创建新的 `CandidateRecallPoint`，除非调用方后续显式触发相应协议。  


<a id="toc-3"></a>

## 3. 运行时调度原语（Runtime Scheduling Primitives）

说明：本章只定义运行时对象的“数据形态 + 本地不变量/语义”，不定义任何“按层管理”的系统策略。

本章目录：
- [3.1 复习任务（ReviewTask）](#toc-3-1)
  - [3.1.1 用途与范围引用（input_range_id / result_range_id）](#toc-3-1-1)
  - [3.1.2 存储字段（建议形态）](#toc-3-1-2)
  - [3.1.3 状态机与不变量（PENDING -> DONE）](#toc-3-1-3)
  - [3.1.4 仓库接口（ReviewTaskRepository）](#toc-3-1-4)
- [3.2 收敛（Convergence）](#toc-3-2)
  - [3.2.1 用途：轮次递推生成器（生成 ReviewTask）](#toc-3-2-1)
  - [3.2.2 存储字段（rule_id / review_task_ids / state）](#toc-3-2-2)
  - [3.2.3 派生量（轮次计数、重点压缩比）](#toc-3-2-3)
  - [3.2.4 推进语义（但不定义“谁来调用推进”）](#toc-3-2-4)
  - [3.2.5 仓库接口（ConvergenceRepository）](#toc-3-2-5)
- [3.3 复习链对象（ReviewChain）](#toc-3-3)
  - [3.3.1 用途：混合队列（Convergence + ReviewTask）](#toc-3-3-1)
  - [3.3.2 存储字段（queue / head / state）](#toc-3-3-2)
  - [3.3.3 可推进态/阻塞态定义（纯派生，不绑定系统调度）](#toc-3-3-3)
  - [3.3.4 仓库接口（ReviewChainRepository）](#toc-3-3-4)
- [3.4 复习任务队列（ReviewTaskQueue）](#toc-3-4)
  - [3.4.1 用途：暂存待执行 ReviewTaskId 的 FIFO](#toc-3-4-1)
  - [3.4.2 存储字段（ids / head）](#toc-3-4-2)
  - [3.4.3 队列不变量（T1/Q1/Q2 的“定义”层面；其强制由第 4 章系统门禁保证）](#toc-3-4-3)
  - [3.4.4 仓库接口（ReviewTaskQueueRepository）](#toc-3-4-4)

---

<a id="toc-3-1"></a>

### 3.1 复习任务（ReviewTask）

<a id="toc-3-1-1"></a>

#### 3.1.1 用途与范围引用（input_range_id / result_range_id）

ReviewTask 是可被队列化与调度的最小执行单元。它只描述“一次复习执行需要覆盖的范围”，并承载执行结果的落库形态。

范围引用只使用 RangeSnapshot 池的 `range_id`：
- `input_range_id: RangeId`：本次复习输入范围（必须可解析为 RangeSnapshot）
- `result_range_id: Optional[RangeId]`：本次复习输出范围（DONE 后写入；可空表示“未产生重点”）

<a id="toc-3-1-2"></a>

#### 3.1.2 存储字段

- `project_id: ProjectId`
- `review_task_id: ReviewTaskId`
- `input_range_id: RangeId`
- `created_at: Timestamp`
- `state: Enum`：`PENDING | DONE`
- `executed_at: Optional[Timestamp]`
- `result_range_id: Optional[RangeId]`

<a id="toc-3-1-3"></a>

#### 3.1.3 状态机与不变量（PENDING -> DONE）

状态跃迁只允许：
- `PENDING -> DONE`

本地不变量：
- 当 `state == PENDING`：
  - `executed_at is None`
  - `result_range_id is None`
- 当 `state == DONE`：
  - `executed_at is not None`
  - `result_range_id` 可空（`None` 表示“未产生重点”，但仍是**最终值**）

语义收紧（与第 4 章一致）：  
- `DONE` 表示本次复习的**提交闭环已完成落库**：`PENDING -> DONE`、`executed_at`、`result_range_id`（可空）写入与队列出队（Q2）必须在同一原子事务中完成（见 4.3.3）。  
- 因此不得存在“`state == DONE` 但 `result_range_id` 尚未写回/未决”的已提交中间态。

<a id="toc-3-1-4"></a>

#### 3.1.4 仓库接口（ReviewTaskRepository）

`ReviewTaskRepository` 以 `review_task_id` 为主键持久化上述字段，并提供以下强约束的最小接口集合（用于支撑第 4 章协议；不得以“等”留白）。本章不规定任何批量扫描或“按层过滤”能力。

- `add(session: MutationSession, review_task: ReviewTask) -> None`：新增；若 `review_task_id` 已存在，必须抛 `PreconditionFailure`（0b.5）。
- `get(session: MutationSession, review_task_id: ReviewTaskId) -> ReviewTask`：不存在则抛 `NotFound`。
- `commit_done(session: MutationSession, review_task_id: ReviewTaskId, executed_at: Timestamp, result_range_id: Optional[RangeId]) -> None`：原子写入 `state = DONE`、`executed_at`、`result_range_id`（可空）。
  - NotFound：若 `review_task_id` 不存在，必须抛 `NotFound`。
  - 写前条件（强约束）：仅允许在 `state == PENDING` 时写入 DONE；若 `state == DONE` 必须幂等返回成功且不得改写任何字段（4.3.3）；其余情形必须抛 `PreconditionFailure`（0b.5）。

---

<a id="toc-3-2"></a>

### 3.2 收敛（Convergence）

<a id="toc-3-2-1"></a>

#### 3.2.1 用途：轮次递推生成器（生成 ReviewTask）

Convergence 是“按轮次递推生成 ReviewTask”的生成器对象。它维护历史轮次所生成的 ReviewTaskId 序列，并以最近一轮 ReviewTask 的执行结果为依据决定：
- 终止（停止生成新任务），或
- 继续（生成下一轮 ReviewTask）

Convergence 只定义“推进一次”的本地语义，不定义“谁来调用推进 / 何时推进”。

<a id="toc-3-2-2"></a>

#### 3.2.2 存储字段（rule_id / review_task_ids / state）

- `project_id: ProjectId`
- `convergence_id: ConvergenceId`
- `seed_range_id: RangeId`（第 1 轮输入范围）
- `rule_id: ConvergenceRuleId`（停止条件/阈值配置标识）
- `review_task_ids: Tuple[ReviewTaskId, ...]`（按轮次顺序）
- `state: Enum`：`IN_PROGRESS | TERMINATED`

<a id="toc-3-2-3"></a>

#### 3.2.3 派生量（轮次计数、重点压缩比）

派生量（不落库）：
- 轮次计数 `i = |review_task_ids|`
- 重点压缩比 `r_k`：基于第 k 轮 `result_range_id` 对应的 RangeSnapshot 的基数比例

<a id="toc-3-2-4"></a>

#### 3.2.4 推进语义（但不定义“谁来调用推进”）

推进规则（本地语义）：
- 若 `review_task_ids` 非空且末尾任务 `state == PENDING`：
  - Convergence 不得生成新任务（推进返回“无产物/不可前进”）
- 若 `review_task_ids` 为空：生成第 1 轮 ReviewTask，`input_range_id = seed_range_id`。  
- 否则取最近一轮 DONE 的 `result_range_id`：  
  - 非空：生成下一轮 ReviewTask，`input_range_id = result_range_id`。  
  - 为空：满足停止条件之一（“上一轮未产生重点”），进入 `TERMINATED`。

<a id="toc-3-2-5"></a>

#### 3.2.5 仓库接口（ConvergenceRepository）

`ConvergenceRepository` 以 `convergence_id` 为主键持久化上述字段，并提供以下强约束的最小接口集合（用于支撑第 4 章协议；不得以“等”留白）。

- `add(session: MutationSession, convergence: Convergence) -> None`：新增；若 `convergence_id` 已存在，必须抛 `PreconditionFailure`（0b.5）。
- `get(session: MutationSession, convergence_id: ConvergenceId) -> Convergence`：不存在则抛 `NotFound`。
- `append_review_task_id(session: MutationSession, convergence_id: ConvergenceId, review_task_id: ReviewTaskId) -> None`：将 `review_task_id` 追加到 `review_task_ids` 尾部（保持轮次顺序）。
- `update_state(session: MutationSession, convergence_id: ConvergenceId, state: ConvergenceState) -> None`：更新 `state` 字段（用于 4.3.6）。

---

<a id="toc-3-3"></a>

### 3.3 复习链对象（ReviewChain）

<a id="toc-3-3-1"></a>

#### 3.3.1 用途：混合队列（Convergence + ReviewTask）

ReviewChain 管理一条运行时混合队列，其元素来自两类对象：
- `Convergence`
- `ReviewTask`

ReviewChain 提供“推进一步”的本地语义：只描述队首元素在不同类型下的可推进/阻塞判定与出队逻辑，不绑定任何系统调度策略。

<a id="toc-3-3-2"></a>

#### 3.3.2 存储字段（queue / head / state）

- `project_id: ProjectId`
- `review_chain_id: ReviewChainId`
- `queue: Tuple[(kind: Enum{CONVERGENCE, REVIEW_TASK}, id: ConvergenceId|ReviewTaskId), ...]`
- `head_index: int`（或等价表示）
- `state: Enum`：`IN_PROGRESS | TERMINATED`

<a id="toc-3-3-3"></a>

#### 3.3.3 可推进态/阻塞态定义（纯派生，不绑定系统调度）

派生定义（不落库）：

可推进态（advanceable）满足任一：
- 对当前链调用一次 4.3.5 `ReviewChain Step` 会返回 `READY_EXISTING(review_task_id)`、`PRODUCED_NEW(review_task_id)` 或 `NO_EFFECT`
- 直观等价口径：
  - 队首为空（`head_index` 已越过队列末尾；对应 `NO_EFFECT`）
  - 队首为 `REVIEW_TASK` 且其 `state == PENDING`（对应 `READY_EXISTING(...)`）
  - 队首为 `REVIEW_TASK` 且其 `state == DONE`（允许在单链内惰性清理后继续暴露后续可见产物或空链）
  - 队首为 `CONVERGENCE` 且该 Convergence 在其本地语义下“可推进”（即可生成下一轮任务，或可终止并继续单链惰性清理）

阻塞态（blocked）：
- 仅当对当前链调用一次 4.3.5 `ReviewChain Step` 会返回 `BLOCKED` 时，视为 blocked。

与 ReviewTaskQueue 的关系（定义层面；非系统门禁）：  
- ReviewChain.queue 中的 `REVIEW_TASK` 项，以及由 `CONVERGENCE` 新生成的 ReviewTask，都是“可被执行的候选”。
- 当 4.3.5 返回 `READY_EXISTING(t)` 或 `PRODUCED_NEW(t)` 时，`t` 成为本次 4.3.4 `Orchestrator Tick` 的批处理候选；系统必须在同一次 Tick 的统一落队阶段按 T1’ 将其落入全局 `ReviewTaskQueue`。  
  `t` 不要求事先出现在 `ReviewChain.queue` 中。

<a id="toc-3-3-4"></a>

#### 3.3.4 仓库接口（ReviewChainRepository）

`ReviewChainRepository` 以 `review_chain_id` 为主键持久化上述字段，并提供以下强约束的最小接口集合（用于支撑第 4 章协议；不得以“等”留白）。

- `add(session: MutationSession, chain: ReviewChain) -> None`：新增；若 `review_chain_id` 已存在，必须抛 `PreconditionFailure`（0b.5）。
- `get(session: MutationSession, review_chain_id: ReviewChainId) -> ReviewChain`：不存在则抛 `NotFound`。
- `advance_head(session: MutationSession, review_chain_id: ReviewChainId) -> None`：将 `head_index` 前进一格（用于 4.3.5 的“出队队首元素”）；若队首为空则不得产生写入且不得报错。

---

<a id="toc-3-4"></a>

### 3.4 复习任务队列（ReviewTaskQueue）

<a id="toc-3-4-1"></a>

#### 3.4.1 用途：暂存待执行 ReviewTaskId 的 FIFO

ReviewTaskQueue 是暂存待执行 ReviewTaskId 的先进先出队列。队列只保存 `ReviewTaskId`，不保存任务实体或范围引用。

<a id="toc-3-4-2"></a>

#### 3.4.2 存储字段（ids / head）

- `project_id: ProjectId`
- `queue_id: ReviewTaskQueueId`（项目内全局唯一；每个 `project_id` 作用域内恰好一个队列实例；取值为系统常量，例如 `GLOBAL_QUEUE`）
- `review_task_ids: Tuple[ReviewTaskId, ...]`
- `head_index: int`（或等价表示）

初始化/恢复语义（强约束）：
- 项目 bootstrap 阶段（0b.1.5a）：必须完成该项目作用域内 `queue_id == GLOBAL_QUEUE` 的队列实例初始化，使得该 `project_id` 的持久化层中存在且仅存在该一条队列记录；之后任何对外可触发的 mutation session 的 `commit()` 均可对其进行 4.1.2 的提交期强制校验。
- `head_index` 的口径：队列的“当前内容”定义为 `review_task_ids[head_index:]`；`head_index` 之前的 ID 视为已逻辑出队（实现可选择物理压缩，但语义等价必须保持）。
- 允许实现对 `head_index` 之前的前缀做物理压缩/截断以控制存储增长，但必须保证对外可观察语义完全等价：`current_ids(session)` 必须严格等于逻辑 FIFO 当前内容，且不得改变队列中现存元素的相对顺序与位置。

<a id="toc-3-4-3"></a>

#### 3.4.3 队列不变量（T1/Q1/Q2 的“定义”层面；其强制由第 4 章系统门禁保证）

本节只定义不变量的语义，不定义其强制机制：

- T1’（可见产物批量入队，定义层面）  
  当系统在一次 `Orchestrator Tick`（4.3.4）内处理某条 ReviewChain，且 4.3.5 返回 `READY_EXISTING(t)` 或 `PRODUCED_NEW(t)` 时，`t` 必须先进入本次 Tick 的 `produced_batch`。  
  当该 Tick 完成对全部目标链的处理后，系统必须按 `produced_batch` 的顺序将这些 `ReviewTaskId` 依次落入项目内全局队列；落队必须使用幂等语义，且不得改变既有位置稳定性。

- Q1（完备性与唯一性，定义层面）  
  任一已入队的 ReviewTaskId 必须且仅能在队列中出现一次，且其对应 ReviewTask 的 `state == PENDING`。

- Q2（跃迁与出队，定义层面）  
  ReviewTask 的 `PENDING -> DONE` 跃迁发生时，该 ReviewTaskId 必须从队列移除，且两者应被视为同一事务语义的一部分。

<a id="toc-3-4-4"></a>

#### 3.4.4 仓库接口（ReviewTaskQueueRepository）

`ReviewTaskQueueRepository` 以 `queue_id` 为主键持久化上述字段，并提供以下强约束的最小接口集合。本章不规定任何与 layer 绑定的 API 形态。
强约束：本仓库所有队列操作均隐式作用于 `session.project_id` 作用域内且 `queue_id == GLOBAL_QUEUE` 的唯一队列实例；实现不得暴露对其他 `queue_id` 或其他 `project_id` 的读写接口。

队列操作承诺（用于支撑第 4 章协议的最小接口面）：
- `enqueue_if_absent(session: MutationSession, review_task_id: ReviewTaskId) -> None`：原子幂等入队（追加到队尾）。若该 `review_task_id` 已在队列中出现，则不得重复入队且不得改变其既有位置；用于实现 4.3.4 的统一落队阶段并支撑 Q1（唯一性）。
- `remove_by_id(session: MutationSession, review_task_id: ReviewTaskId) -> None`：按 id 移除（从队列中删除该 `review_task_id` 的出现）；用于实现 4.3.3 的 Q2 原子“`PENDING -> DONE` + 出队”闭环。  
  - 幂等语义（强约束）：若该 `review_task_id` 不在队列中，则不得产生写入且不得报错。

读接口（用于执行器与门禁判定的最小可计算接口面；强约束）  
- `peek_head(session: MutationSession) -> Optional[ReviewTaskId]`：返回队列“当前内容”序列的队首（语义上等价于 `review_task_ids[head_index]`）；若队列为空则返回 `None`。  
- `is_empty(session: MutationSession) -> bool`：当且仅当 `peek_head(session) is None`。  

提交期强制校验所需的可枚举事实源（系统内部接口；强约束；用于 0b.7.1 / 4.1.2）
- `current_ids(session: MutationSession) -> Tuple[ReviewTaskId, ...]`
  - 语义：返回队列“当前内容”序列，等价于 `review_task_ids[head_index:]`，顺序为 FIFO（队首 → 队尾）。
  - 约束：不得排序、不得去重、不得省略；该序列是 Q1/Q2 校验与执行器 FIFO 的权威事实源。
- `all_queue_ids_for_commit_validation(session: MutationSession) -> Tuple[ReviewTaskQueueId, ...]`
  - 语义：返回 `session.project_id` 作用域内**全部** ReviewTaskQueue 记录的 `queue_id` 主键集合（按 `id_canonical_text(queue_id)` 升序）。
  - 约束：该接口只用于系统级 `commit()` 的 4.1.2 校验；不得在系统对外 API 中暴露“访问非 GLOBAL_QUEUE 队列实例”的能力。

---

<a id="toc-4"></a>

## 4. PLM 系统编排与聚合（System Orchestration & Aggregation）

说明：本章定义系统边界、全局门禁、管理单元 Layer，以及运行时推进/登记/聚合等所有内部协议；本章是控制面（control plane）规格。

本章目录：
- [4.1 系统边界与项目内不变量（System Boundary & Project-scoped Invariants）](#toc-4-1)
  - [4.1.1 单入口 + 原子提交（所有仓库一致更新或全回滚）](#toc-4-1-1)
  - [4.1.2 复习队列完备性与唯一性（Q1/Q2 强制）](#toc-4-1-2)
  - [4.1.3 复习优先门禁（Queue 非空时禁止学习提交/禁止推进）](#toc-4-1-3)
  - [4.1.4 链存在性与登记（每个 entry_node 恰一条链，且必须被管理）](#toc-4-1-4)
  - [4.1.5 终止不阻塞与确定性（TERMINATED 的惰性清理、序列稳定性）](#toc-4-1-5)
  - [4.1.6 复述点归属唯一](#toc-4-1-6)
  - [4.1.7 项目删除（Project Delete）](#toc-4-1-7)
- [4.2 系统管理单元：层（Layer）](#toc-4-2)
  - [4.2.1 Layer 的职责：承载本层控制状态与资源](#toc-4-2-1)
  - [4.2.2 Layer 持有的状态/资源（字段级清单）](#toc-4-2-2)
  - [4.2.3 Layer 与索引的映射（layer_index -> LayerId），以及“上层/下层”的系统语义](#toc-4-2-3)
  - [4.2.4 Layer 运行模式与编排触发策略（LayerMode & Trigger Policy）](#toc-4-2-4)
  - [4.2.5 Layer 持久化与仓库接口（LayerRepository）](#toc-4-2-5)
- [4.3 Layer 子系统：复习编排（Orchestration Subsystem）](#toc-4-3)
  - [4.3.1 编排器（Orchestrator）](#toc-4-3-1)
  - [4.3.2 内部协议：学习任务登记到编排器（Task Register）](#toc-4-3-2)
  - [4.3.3 内部协议：复习任务执行结果落库（ReviewTask Commit）](#toc-4-3-3)
  - [4.3.4 内部协议：编排推进（Orchestrator Tick）](#toc-4-3-4)
- [4.3.5 内部协议：复习链推进到首个可见产物（ReviewChain Step）](#toc-4-3-5)
  - [4.3.6 内部协议：收敛推进（Convergence Step）](#toc-4-3-6)
- [4.4 Layer 子系统：聚合（Aggregation Subsystem）](#toc-4-4)
  - [4.4.1 聚合队列（AggregationQueue，Layer-owned State）](#toc-4-4-1)
  - [4.4.2 聚合阈值与触发（Thresholds & Triggers）](#toc-4-4-2)
  - [4.4.3 聚合周期状态机（AggregationCycle FSM）](#toc-4-4-3)
  - [4.4.4 上推提交（Roll-up Commit）](#toc-4-4-4)
  - [4.4.5 手动聚合与事件记录（Manual Trigger & Events）](#toc-4-4-5)
- [4.5 系统对外入口白名单（System API Whitelist）](#toc-4-5)

---

<a id="toc-4-1"></a>

### 4.1 系统边界与项目内不变量（System Boundary & Project-scoped Invariants）

<a id="toc-4-1-1"></a>

#### 4.1.1 单入口 + 原子提交（所有仓库一致更新或全回滚）

系统状态只能通过系统接口变更；每次接口调用必须原子化：要么所有仓库/队列/链/树一致更新，要么完全不变并返回拒绝原因。

<a id="toc-4-1-2"></a>

#### 4.1.2 复习队列完备性与唯一性（Q1/Q2 强制）

系统强制满足 ReviewTaskQueue 的 Q1/Q2（在 T1’ 语义下）：任一已入队的 ReviewTask 必须且仅能在队列中出现一次，且为 `PENDING`；执行器将其标记 `DONE` 的同一跃迁中必须出队（Q2）。

项目内全局队列单例：每个 `project_id` 作用域内恰好存在一个 `ReviewTaskQueue` 实例；所有入队/出队均作用于该项目内全局队列。`queue_id` 为系统常量（例如 `GLOBAL_QUEUE`）；该实例必须在项目 bootstrap 阶段（0b.1.5a）完成初始化；之后永不更换。

入队幂等与位置稳定性（强约束）：对任一 `review_task_id`，一旦其已在队列中出现，则后续的“确保入队”（4.3.4 / 3.4.4）不得重复入队，且不得改变其既有队列位置；该约束用于保证队列稳定性与协议可重复执行。

提交期强制校验口径（强约束；0b.7.1 / 4.1.2）

可校验事实源（必须持久化且可枚举；用于消除实现分叉）
- ReviewTaskQueue 的“实例集合”事实源：`ReviewTaskQueueRepository.all_queue_ids_for_commit_validation(session)`（3.4.4）。
- ReviewTaskQueue 的“当前内容”事实源：`ReviewTaskQueueRepository.current_ids(session)`（3.4.4）。
- ReviewTask 的状态事实源：`ReviewTaskRepository.get(session, review_task_id)`（3.1.4）。

系统级 `commit()` 的确定性校验算法（对最终态一次性校验；失败则回滚，0b.1.2）
1) 项目内全局队列单例（可枚举性口径写死）
   - 令 `queue_ids := ReviewTaskQueueRepository.all_queue_ids_for_commit_validation(session)`。
   - 必须满足：`queue_ids == (GLOBAL_QUEUE,)`。
     - 若不满足（0 条/多条/或出现非 GLOBAL_QUEUE 的 `queue_id`）：`commit()` 必须失败（CommitTimeValidationFailure）并整体回滚。
2) Q1（完备性与唯一性；对“当前内容”定义域强制）
   - 令 `q := ReviewTaskQueueRepository.current_ids(session)`。
   - `q` 不得包含重复的 `ReviewTaskId`；否则 `commit()` 必须失败并回滚。
   - 对任一 `t in q`：
     - `ReviewTaskRepository.get(session, t)` 必须可解析，且其 `state == PENDING`；否则 `commit()` 必须失败并回滚。
3) Q2 的“已提交态可观察一致性”（闭包到 Q1）
   - 由于 Q2 的协议原子性由 4.3.3 保证，提交期校验只需保证：不存在 “已入队但 state != PENDING” 的已提交态。
   - 该条件已由步骤 (2) 覆盖，因此不得在系统级 `commit()` 额外引入其他 Q2 相关校验项（避免扩大 0b.7.1 闭包）。

<a id="toc-4-1-3"></a>

#### 4.1.3 复习优先门禁（Queue 非空时禁止学习提交/禁止推进）

当项目内全局 ReviewTaskQueue 非空时：
- (a) 禁止：LearningTask Submit（2.1）以及任何会创建新 `entry_node` 并触发 Task Register（4.3.2）/ Orchestrator Tick（4.3.4）的用户操作。
- (b) 允许：对既有数据的编辑类写入（例如修改 RecallPoint 文本等），前提是该写入**不会**创建/入队新的 ReviewTask，且不会调用 Orchestrator Tick（4.3.4）/ ReviewChain Step（4.3.5）等推进协议。
- (c) 推进侧：允许执行器对队首 ReviewTask 执行 ReviewTask Commit（4.3.3，`PENDING -> DONE` + 出队）以清空队列；除此之外的推进（Orchestrator Tick / ReviewChain Step）在队列非空时不得运行。
- (d) 接口侧（可审计白名单原则）：当队列非空时，系统接口层必须禁止任何可能调用 Task Register（4.3.2）/ Orchestrator Tick（4.3.4）/ ReviewChain Step（4.3.5）/ Convergence Step（4.3.6）的路径；每个系统接口需显式标注其是否“调度无副作用”。

执行模型（强约束；用于避免实现分叉）  
- 严格 FIFO 单执行：当队列非空时，执行器每次只能取用 `ReviewTaskQueueRepository.peek_head(session)` 所返回的队首任务执行；不得跳过队首、不得并行取用多个任务、不得乱序执行。  
- 完成语义：执行器对队首任务的唯一有效落库路径为 ReviewTask Commit（4.3.3）；该协议在同一事务内完成 `PENDING -> DONE` + 写入结果 + Q2 出队闭环。  

门禁的归类（强约束）  
- 本小节门禁属于协议/接口的**前置条件**（0b.5）：允许在 session 外直接拒绝（快速失败）。  
  - 但为避免 TOCTOU：若实现选择在 session 外进行门禁判定，则在进入目标 `MutationSession(READ_WRITE)` 并持有写锁后，仍必须在同一会话内一致读视图下复检该门禁，并且必须在产生任何 staged 写入之前复检通过（见 0b.3）。  
  - 若在 session 内执行门禁判定，也必须在产生任何 staged 写入之前拒绝（失败不产生任何写入）。  
- 该门禁不得作为系统级 `commit()` 的提交期强制校验项。  

统一澄清（强约束）
- “项目内全局 `ReviewTaskQueue` 为空”是 `Orchestrator Tick`（4.3.4）的**进入门禁**；其判定口径固定为 Tick 开始时的同一一致读视图。
- Tick 执行过程中由本次 Tick 收集到的 `produced_batch` 不得反向阻断同一 Tick 对后续链的处理。
- `produced_batch` 中的任务只有在 Tick 的统一落队阶段生效；生效后才重新受到本小节门禁约束。

<a id="toc-4-1-4"></a>

#### 4.1.4 链存在性与登记（每个 entry_node 恰一条链，且必须被管理）

系统层面的 entry 规范化为 `LearningTaskNodeId`（记为 `entry_node`）：无论是单任务入口还是聚合父节点入口，均以一个 LearningTaskNode 作为可调度入口。

任意新产生的“可调度入口 entry_node”（LearningTaskNode），在同一提交中必须：
- 创建 Convergence；
- 创建 ReviewChain（初始队列含该 Convergence）；
- 将该 chain 登记到“entry_node 所属层”的 Orchestrator 管理范围。

系统中每个 `entry_node` 恰有一条 ReviewChain。

旧链/新链排序事实源（强约束）
- “旧链优先”的唯一权威事实源必须是持久化登记序号；实现不得从 `Layer.orchestrator_managed_review_chain_ids` 的 ID 排序、内存插入顺序或其他隐式顺序推导旧/新关系。
- 本规格写死：同一 `project_id + target_layer_index` 作用域内，`EntryRegistration.registration_seq` 越小表示链越旧。

提交期强制校验口径（强约束；0b.7.1 / 4.1.4）

可校验事实源（必须持久化且可枚举；用于消除实现分叉）

1) Layer 映射表与 LayerRepository（最小事实源；用于“必须被管理”可判定）

对象（持久化）
- `Layer`（最小必需字段；其余字段可由本章其他小节补齐，但不得改变本小节的可枚举事实源口径）
  - `project_id: ProjectId`
  - `layer_id: LayerId`
  - `layer_index: int`（自然编号；项目内唯一）
  - `layer_mode: LayerMode`
  - `orchestrator_managed_review_chain_ids: Tuple[ReviewChainId, ...]`
    - 语义：本层 Orchestrator 当前管理的 ReviewChainId 集合（集合语义）。
    - 规范化（强约束）：持久化时必须去重，并按 `id_canonical_text(review_chain_id)` 升序排序（以确保跨实现一致、可测试、可比较）。

仓库接口（最小）
- `LayerRepository.get_by_index(session: MutationSession, layer_index: int) -> Layer`
  - 不存在则抛 `NotFound`。
- `LayerRepository.all(session: MutationSession) -> Sequence[Layer]`
  - 返回顺序：按 `layer_index` 升序（确定性）。

2) entry_node -> ReviewChainId 登记索引（RegistryRepository；用于“一对一 + 必须被管理”可判定）

对象（持久化）
- `EntryRegistration`
  - `project_id: ProjectId`
  - `entry_node: LearningTaskNodeId`
  - `target_layer_index: int`
  - `review_chain_id: ReviewChainId`
  - `registration_seq: int`
    - 语义：同一 `project_id + target_layer_index` 作用域内的链登记顺序号。
    - 强约束：必须严格单调递增、唯一；`registration_seq` 越小表示链越旧。

仓库接口（最小）
- `EntryRegistryRepository.add(session: MutationSession, reg: EntryRegistration) -> None`
  - 新增；若同一 `project_id` 下 `entry_node` 已存在则抛 `PreconditionFailure`（0b.5）。
  - （推荐写前条件；用于更早失败、但不改变提交期闭包）：若同一 `project_id` 下 `review_chain_id` 已被其他 entry 登记，则抛 `PreconditionFailure`（失败不产生任何写入）。
  - （强约束；写前条件）：若同一 `project_id + target_layer_index` 下 `registration_seq` 已存在，则必须抛 `PreconditionFailure`（失败不产生任何写入）。
- `EntryRegistryRepository.get(session: MutationSession, entry_node: LearningTaskNodeId) -> EntryRegistration`
  - 不存在则抛 `NotFound`。
- `EntryRegistryRepository.maybe_get(session: MutationSession, entry_node: LearningTaskNodeId) -> Optional[EntryRegistration]`
- `EntryRegistryRepository.all(session: MutationSession) -> Sequence[EntryRegistration]`
  - 返回顺序：先按 `target_layer_index` 升序，再按 `registration_seq` 升序，最后按 `id_canonical_text(entry_node)` 升序（确定性）。

3) 链存在性事实源
- `ReviewChainRepository.get(session: MutationSession, review_chain_id: ReviewChainId) -> ReviewChain`（3.3.4）。

系统级 `commit()` 的确定性校验算法（对最终态一次性校验；失败则回滚，0b.1.2）

令：
- `layers := LayerRepository.all(session)`
- `regs := EntryRegistryRepository.all(session)`

校验步骤：
1) 注册表的一对一（entry_node 恰一条链；且一条链不被多个 entry 共享）
   - `regs` 中 `review_chain_id` 不得重复；否则 `commit()` 必须失败并回滚。
2) 登记可解析性与“必须被管理”
   - 对任一 `reg in regs`：
     - `LearningTaskNodeRepository.get(session, reg.entry_node)` 必须可解析（否则失败并回滚）。
     - `ReviewChainRepository.get(session, reg.review_chain_id)` 必须可解析（否则失败并回滚）。
     - `layer := LayerRepository.get_by_index(session, reg.target_layer_index)` 必须可解析（否则失败并回滚）。
     - 必须满足：`reg.review_chain_id in layer.orchestrator_managed_review_chain_ids`（否则失败并回滚）。
3) “被管理集合”的完备性（避免出现“有链被管理但无 entry”或“挂错层”）
   - 对任一 `layer in layers`，对任一 `cid in layer.orchestrator_managed_review_chain_ids`：
     - 必须存在且仅存在一个 `reg in regs` 使得 `reg.review_chain_id == cid` 且 `reg.target_layer_index == layer.layer_index`；
       否则 `commit()` 必须失败并回滚。

<a id="toc-4-1-5"></a>

#### 4.1.5 终止不阻塞与确定性（TERMINATED 的惰性清理、序列稳定性）

`TERMINATED` 的链/收敛不得阻塞编排推进（应跳过或惰性清理）。所有由树/队列派生的序列必须由 children 顺序诱导的 DFS（及明确去重规则）稳定决定。

<a id="toc-4-1-6"></a>

#### 4.1.6 复述点归属唯一

强约束：任一 `RecallPointId` 必须且仅能出现在同一 `project_id` 作用域内一个 `LearningTask.recall_point_ids` 中一次；系统禁止同一 `RecallPointId` 被多个 LearningTask 引用。

Enforcement 点（强约束；前置条件失败，0b.5）
- 任一系统对外写入入口在创建/更新 `LearningTask`（或创建会间接产生 LearningTask 的协议，例如 2.1）时，必须在 mutation session 内、在产生任何 staged 写入之前，对“归属唯一”做判定；若违反必须抛 `PreconditionFailure` 且不产生任何 staged 写入。

<a id="toc-4-1-7"></a>

#### 4.1.7 项目删除（Project Delete）

语义（强约束）

* `delete_project(project_id)` 必须在一次系统级 mutation session 内原子完成该项目作用域内数据删除；任一步失败则整体回滚。
* 删除成功后，该 `project_id` 不得再用于开启会话或任何对外入口。

前置条件

* `Project(project_id)` 可解析且 `state == ACTIVE`。

删除范围（同一 `project_id` 作用域内）

* `AggregationEvent`
* `AggregationQueue`
* `AuditLogEvent`
* `EntryRegistration`
* `Layer`
* `MediaAsset`
* `AsrArtifact`
* `TempContextFragment`
* `QASession`
* `CandidateRecallPoint`
* `MemoryCanvas`
* `MemoryCanvasVersion`
* `CanvasEdge`
* `StoryArtifact`
* `RecallPointReviewRecord`
* `ProjectConfig`
* `ProjectStorageConfig`
* `ReviewTaskQueue`
* `ReviewChain`
* `Convergence`
* `ReviewTask`
* `RangeSnapshot`
* `LearningTaskNode`
* `LearningTask`
* `RecallPoint`
* `LearningObjectNode`
* `Instance`
* `Project`（最后删除，或先 `mark_deleted` 再物理删，二选一）

删除策略（最小版）

* 允许直接物理删除；不要求软删除保留墓碑。

---

<a id="toc-4-2"></a>

### 4.2 系统管理单元：层（Layer）

<a id="toc-4-2-1"></a>

#### 4.2.1 Layer 的职责：承载本层控制状态与资源

Layer 是在给定范围尺度上驱动“复习编排 + 聚合”的管理单元，承载本层控制状态、资源与协议入口。

<a id="toc-4-2-2"></a>

#### 4.2.2 Layer 持有的状态/资源（字段级清单）

字段：
- `project_id: ProjectId`
- `layer_id: LayerId`
- `layer_index: int`（或由映射表派生）
- `layer_mode: LayerMode`（见 4.2.4）
- `orchestrator`（本层编排器）
- `aggregation_queue`（本层聚合队列）
- `review_task_queue: GlobalReviewTaskQueue`（全局唯一；不属于任何 Layer；Layer 仅引用/访问，不持有独立实例）
- 聚合阈值配置：`K_node`, `K_point`
- 聚合周期状态：`aggregation_cycle_state`

<a id="toc-4-2-3"></a>

#### 4.2.3 Layer 与索引的映射（layer_index -> LayerId），以及“上层/下层”的系统语义

系统维护 `layer_index -> layer_id` 的映射，并定义：
- 上层：`layer_index + 1`
- 下层：`layer_index - 1`

系统语义只在控制面出现：用于登记父任务到上层、以及驱动某一层的编排/聚合协议。

<a id="toc-4-2-4"></a>

#### 4.2.4 Layer 运行模式与编排触发策略（LayerMode & Trigger Policy）

Layer 持有配置字段：
- `layer_mode: LayerMode`

LayerMode 枚举：
- `AUTO_TICK_ON_ENTRY`（模式 1）：新 entry_node 登记后可自动尝试 Tick
- `MANUAL_TICK_ON_ENTRY`（模式 2）：新 entry_node 只登记不 Tick

强约束：
- Orchestrator Tick（4.3.4）不对外暴露；只能由 Layer 在内部按本小节触发策略调用；系统不提供用户/上层显式触发 Tick 的接口/路径。
- 本章中“Tick 返回空产物”指：本次 Tick 的 `produced_batch` 为空，因此统一落队阶段不得对项目内全局 `ReviewTaskQueue` 产生写入（项目内全局队列在本次 Tick 结束后仍为空）。

触发源 A（entry 产生）：
- 当本层产生新的 `entry_node: LearningTaskNodeId`（叶子或容器）并完成 Task Register（4.3.2）后：
  - 若 `layer_mode == AUTO_TICK_ON_ENTRY`：Layer 立即尝试调用一次 Orchestrator Tick（受 4.3.1/4.3.4 门禁约束）
  - 若 `layer_mode == MANUAL_TICK_ON_ENTRY`：不得因该 entry_node 产生而主动触发 Tick（仅登记）

触发源 B（聚合周期 CLEARING）：
- 当本层处于聚合周期 `CLEARING` 且门禁成立（项目内全局队列为空 + 全链可推进）时，Layer 反复尝试调用 Orchestrator Tick：若某次 Tick 产生了入队则进入执行段；若某次 Tick 返回空产物则结束本层 CLEARING 周期。

<a id="toc-4-2-5"></a>

#### 4.2.5 Layer 持久化与仓库接口（LayerRepository）

目的（强约束）
- 为 0b.7.1 所列系统级提交期强制集合中的 4.1.4 提供**可枚举、可验证、跨实现一致**的持久化事实源。
- 本小节只规定“最小可校验事实源 + 最小仓库接口”；不得引入与 0b.7.1 闭包无关的新提交期强制校验项。

仓库
- 关联仓库：`LayerRepository`

写接口（最小；本小节不规定 Layer 的创建策略）
- `add(session: MutationSession, layer: Layer) -> None`
  - 新增；若 `layer_id` 已存在则抛 `PreconditionFailure`。
  - 强约束：`layer_index` 在同一 `project_id` 作用域内唯一；若已存在同 `layer_index` 的 Layer，则抛 `PreconditionFailure`。
- `update_threshold(session: MutationSession, layer_index: int, K_node: int, K_point: int) -> None`
  - 语义：仅更新该 Layer 的聚合阈值控制字段 `K_node/K_point`；不得改写其他字段。
  - NotFound：`layer_index` 对应 Layer 不存在则抛 `NotFound`。
  - 写前条件（强约束；0b.5）：`K_node >= 1` 且 `K_point >= 1`。

读接口（最小）
- `get(session: MutationSession, layer_id: LayerId) -> Layer`
- `get_by_index(session: MutationSession, layer_index: int) -> Layer`
- `maybe_get_by_index(session: MutationSession, layer_index: int) -> Optional[Layer]`
- `all(session: MutationSession) -> Sequence[Layer]`
  - 返回顺序：按 `layer_index` 升序（确定性）。

一致性与校验（与 4.1.4 对齐）
- `orchestrator_managed_review_chain_ids` 必须去重并按 `id_canonical_text` 升序持久化；若实现选择在写入时不规范化，则必须在 `commit()` 的 4.1.4 提交期强制校验中视为不一致并失败回滚（不允许“隐式修复”）。

---

<a id="toc-4-3"></a>

### 4.3 Layer 子系统：复习编排（Orchestration Subsystem）

<a id="toc-4-3-1"></a>

#### 4.3.1 编排器（Orchestrator）

Orchestrator 是 Layer-owned 组件，管理多条 ReviewChain，并在满足前置条件时按“旧链优先”批量驱动这些链推进到首个可见产物；所有产物必须在同一次 Tick 的末尾统一入队。

前置条件/门禁（与队列、链可推进态一致）：
- 门禁：项目内全局 `ReviewTaskQueue` 为空
- Orchestrator 管理的全部 ReviewChain 处于可推进态
- 若不满足：本次推进不得发生（或返回空且不产生事件/产物）

一致性要求：
- “全链可推进态”必须排除任何会导致 Convergence Step 返回 `BLOCKED` 的链首收敛；即当队首为 `CONVERGENCE` 时，要求该 Convergence 在 3.2.4 语义下可生成或可终止。
- “advanceable” 的判定标准写死为：对该链调用一次 4.3.5 `ReviewChain Step` 是否会返回非 `BLOCKED` 结果；单链协议只负责暴露可见产物，不负责直接把产物写入全局队列。

“全链可推进态”的判定算法（强约束；用于避免实现分叉）  
Orchestrator 的门禁判定必须使用与 3.3.3（advanceable/blocked）一致的可计算口径，并满足以下要求：

* 统一读视图：对“队列为空 + 全链可推进态”的判定必须在同一 in-session 一致读视图内完成，并与后续 Tick/Step 写入处于同一系统事务中（TOCTOU 防护）。  
* TERMINATED 处理：`TERMINATED` 的链视为 advanceable（应跳过，不得阻塞）。  
* 判定步骤（对每条被管理的链）：  
  - 若链队首为空：advanceable。  
  - 若队首为 `REVIEW_TASK(t)`：  
    - 若 `t.state == PENDING`：advanceable；4.3.5 将返回 `READY_EXISTING(t)`。  
    - 若 `t.state == DONE`：advanceable；4.3.5 允许在单链内继续惰性清理，并最终返回 `READY_EXISTING(...)`、`PRODUCED_NEW(...)` 或 `NO_EFFECT`。  
  - 若队首为 `CONVERGENCE(c)`：必须读取 `c` 及其末尾 ReviewTask（若存在）以判定：  
    - 若 `c.state == TERMINATED`：advanceable；4.3.5 可继续惰性清理后续链项。  
    - 若 `c.review_task_ids` 非空且末尾 ReviewTask `state == PENDING`：blocked。  
    - 其余情形：advanceable（表示本轮可生成或可终止）。  

<a id="toc-4-3-2"></a>

#### 4.3.2 内部协议：学习任务登记到编排器（Task Register）

输入：
- `entry_node: LearningTaskNodeId`
- `target_layer_index: int`

写入（同一 commit 原子生效）：
- 计算首轮范围（确定性）：
  - `seed_rp_ids := LearningTaskNodeRepository.covered_rp_ids(session, entry_node)`（见 1.6.1；序列稳定性必须由 children 顺序诱导）
  - 若 `seed_rp_ids` 为空：必须抛 `PreconditionFailure`；系统不得对空范围调用 `RangeSnapshotRepository.intern(...)`。
- `seed_range_id := RangeSnapshotRepository.intern(session, tuple(seed_rp_ids))`
- 读取该层配置（确定性；控制面输入，不得引入外部读取）：
  - `cfg := ProjectConfigRepository.get(session)`
  - `layer_cfg := cfg.layer_configs[target_layer_index]`；若不存在则按 1.0.5 的“读取回退”使用默认 `LayerConfig`
  - `template := layer_cfg.review_chain_template`
- 按模板构建初始 ReviewChain.queue（强约束；写死解释规则；仅影响新建链，不回写既有链）：
  - `queue := []`
  - 对 `template.items` 依次实例化并追加到 `queue`：
    - 若 `kind == CONVERGENCE`：创建一个新的 `Convergence(seed_range_id = seed_range_id)`，并追加 `CONVERGENCE(c)`。
    - 若 `kind == REVIEW_TASK(count=n)`：创建 `n` 个 `ReviewTask(input_range_id = seed_range_id, state = PENDING)`，并依次追加 `REVIEW_TASK(t)`。
  - 说明：上述创建的 ReviewTask 不要求在本协议内立即入队；其入队只能由后续一次 `Orchestrator Tick`（4.3.4）在统一落队阶段按 T1’ 完成。
- 创建 `ReviewChain(review_chain_id)`（初始队列为上步构建的 `queue`）
- 分配登记顺序号（强约束；旧链排序事实源）：
  - `registration_seq := 1 + max({reg.registration_seq | reg.target_layer_index == target_layer_index}, default=0)`
  - 上述读取与分配必须在与本次 Task Register 相同的 mutation session / 一致读视图内完成。
  - 若同一事务内向同一 `target_layer_index` 连续登记多条新链，后登记者必须取得更大的 `registration_seq`；实现不得复用或回填序号。
- 创建 `EntryRegistration(entry_node, target_layer_index, review_chain_id, registration_seq)`，并将该 `review_chain_id` 注册到本层 Orchestrator 管理范围
- 将 `entry_node` 入队到目标层的 `AggregationQueue`：`AggregationQueueRepository.enqueue(session, target_layer_index, entry_node)`

强约束（写死；用于封闭聚合候选来源）
- 任一经由 Task Register 成功登记的 `entry_node`，必须在同一系统事务内进入其所属层 `target_layer_index` 的 `AggregationQueue`。
- `registration_seq` 的分配与 ReviewChain/Convergence/EntryRegistration 的创建、以及上述 `AggregationQueue` 入队，必须同事务原子生效；任一步失败则整体回滚。

说明：
- 上述 `AggregationQueue` 入队是 4.4 聚合子系统的候选集闭环的一部分；实现不得改由其他异步路径、后台扫描或隐式修复补入。
- Task Register 完成后是否立刻触发一次 Orchestrator Tick 由 Layer 的 `layer_mode` 决定（见 4.2.4；模式 1 触发，模式 2 不触发）。

<a id="toc-4-3-3"></a>

#### 4.3.3 内部协议：复习任务执行结果落库（ReviewTask Commit）

由执行器调用，写：
- ReviewTask `PENDING -> DONE`
- 写 `executed_at`
- 写 `result_range_id`（来自第 2 章 2.2 的派生；可空）
- 队列出队（Q2 强制）

强约束（必须满足）  
- `result_range_id` 的写入入口唯一：只能由本协议写入。  
- 原子性：不得存在 “DONE 但 result_range_id 未决” 的中间态；`PENDING -> DONE`、`executed_at`、`result_range_id` 写入与 Q2 出队必须同事务原子完成。  
- 不可变：一旦 `result_range_id` 写入（含写入 None 的语义决定），不得修改。
- 幂等与重试语义（强约束；用于崩溃恢复/网络重试）：  
  - 若目标 ReviewTask 已处于 `DONE`：本协议必须幂等返回成功（实现可返回明确的 `AlreadyDone` 结果，但不得视为失败），且不得改写 ReviewTask 任何字段；队列移除可再次调用但必须幂等无副作用（推荐仍调用 `remove_by_id` 以确保闭环）。  
  - Q2 出队的 `remove_by_id(session, review_task_id)` 必须幂等：若该 `review_task_id` 不在队列中，则不得产生写入且不得报错。  

说明（强约束；用于澄清“提交期校验 vs 协议语义”边界）  
- 本协议的“闭环原子性”属于**协议语义约束**：必须通过本协议在单次系统级 mutation session 内完成写入闭环来保证。  
- 该约束不得被表述为“任意 `commit()` 都要做的通用提交期校验项”；否则会导致无关事务承担不合理校验责任。系统只需保证：系统已提交状态中不出现“`state == DONE` 但 `result_range_id` 未决”的中间态。  

<a id="toc-4-3-4"></a>

#### 4.3.4 内部协议：编排推进（Orchestrator Tick）

本协议为 Layer 内部调用点，不对外暴露；只能由 Layer 按 4.2.4 的触发策略调用。

输入：
- `target_layer_index: int`（内部路由字段；必须等于本 Layer 的 `layer_index`）

门禁：
- 项目内全局 `ReviewTaskQueue` 为空 + 全链可推进

推进顺序（强约束）
- 本层 Orchestrator 必须按被管理链对应的 `EntryRegistration.registration_seq` 升序推进；即旧链必须先于新链。
- 强约束：链间推进顺序不得从 `Layer.orchestrator_managed_review_chain_ids` 的 ID 排序推导；该字段仅是“被管理集合”的事实源，不是“旧链优先”的顺序源。

一致读视图/事务性要求（TOCTOU 防护）：
- Orchestrator Tick 的门禁判定（“队列为空 + 全链可推进”）、对链执行 ReviewChain Step（4.3.5）（从而间接调用 Convergence Step，4.3.6）以及本次 Tick 产生的全部写入，必须在同一系统事务内基于同一一致读视图完成（见 0b.1 的 mutation session + commit 语义）；实现不得在“先判定可推进、后另起事务推进”的方式下运行 Tick。

执行阶段（强约束；同一系统事务内原子完成）
1) 令 `ordered_chains` 为当前 `target_layer_index` 下全部受管链按 `registration_seq` 升序排列后的序列。
2) 初始化 `produced_batch := []`。
3) 依次处理 `ordered_chains` 中每条链：
   - 调用 4.3.5 `ReviewChain Step`。
   - 若返回 `READY_EXISTING(t)` 或 `PRODUCED_NEW(t)`，则将 `t` 追加到 `produced_batch`。
   - 若返回 `NO_EFFECT`，继续处理下一条链。
   - 若返回 `BLOCKED`，则视为门禁判定与链状态失配；本次 Tick 必须失败且不得留下任何 staged 写入。
   - 每条链在一次 Tick 中最多向 `produced_batch` 贡献一个 `ReviewTaskId`。
4) 当 `ordered_chains` 全部处理完成后，必须按 `produced_batch` 的顺序依次调用 `ReviewTaskQueueRepository.enqueue_if_absent(session, review_task_id)`，将其统一落入项目内全局队列。

返回语义（强约束）
- 若 `produced_batch` 为空：Tick 返回空产物。
- 若 `produced_batch` 非空：Tick 返回该批产物，且这些任务在项目内全局队列中的 FIFO 顺序必须与 `produced_batch` 完全一致。

用户可感知顺序保证（强约束）
- 当 `layer_mode == AUTO_TICK_ON_ENTRY` 且新 `entry_node` 完成 Task Register 后触发 Orchestrator Tick 时，本次 Tick 必须先处理所有更旧的受管链，再处理该新链。
- 对模板 `[REVIEW_TASK(count=1), CONVERGENCE]`，若提交 `B` 时旧链 `A` 的上一轮 ReviewTask 已 `DONE` 且项目内全局队列为空，则本次 Tick 后新增任务的队列顺序必须为：`A` 的下一轮任务先于 `B` 的首轮任务。

<a id="toc-4-3-5"></a>

#### 4.3.5 内部协议：复习链推进到首个可见产物（ReviewChain Step）

定义对单条链“连续推进直到首个可见产物、空链或阻塞”为止的控制面协议入口（可调用 Convergence Step，并处理惰性清理）。

调用门禁：
- 本协议仅在 4.1.3 门禁允许时被调用（即项目内全局 `ReviewTaskQueue` 为空）。

输入：
- `review_chain_id: ReviewChainId`

输出（Result，纯协议返回值，不持久化）：
- `READY_EXISTING(review_task_id: ReviewTaskId)`：链内已有可直接执行的 `PENDING` ReviewTask
- `PRODUCED_NEW(review_task_id: ReviewTaskId)`：经由 `Convergence Step` 新生成了一个 ReviewTask
- `NO_EFFECT`：本次推进未得到可见产物（例如链被清空、惰性清理后无后续项）
- `BLOCKED`：本链当前不可生成可执行任务

读/写（同一 commit 原子生效）：
- 强约束：本协议不得直接调用 `ReviewTaskQueueRepository.enqueue_if_absent(...)`，也不得直接改写项目内全局 `ReviewTaskQueue`；全局队列写入只能由 4.3.4 的统一落队阶段完成。
- 推进规则（强约束）：
  - 循环读取当前队首元素 `head_item`：
    - 若队首为空：返回 `NO_EFFECT`。  
    - 若队首为 `REVIEW_TASK(t)`：  
      - 若其 `state == DONE`：链 `head_index` 前进一格（出队该元素），并继续循环。  
      - 若其 `state == PENDING`：返回 `READY_EXISTING(t)`；不得在本协议内入队。  
    - 若队首为 `CONVERGENCE(c)`：  
      - 调用 `Convergence Step(c)`（4.3.6），得到 `result`：  
        - 若 `result == PRODUCED(t)`：返回 `PRODUCED_NEW(t)`；不得在本协议内入队。  
        - 若 `result == TERMINATED`：链 `head_index` 前进一格（出队该 `CONVERGENCE` 项），并继续循环。  
        - 若 `result == BLOCKED`：返回 `BLOCKED`。  

说明：  
- 本协议不是“推进一步”，而是“推进到首个用户可见产物”；因此允许在单链内部连续跨过 `DONE` 的 `REVIEW_TASK` 与已终止的 `CONVERGENCE`。  
- 在 Orchestrator Tick 的门禁已成立时，本协议不应返回 `BLOCKED`；若返回则说明门禁判定或链状态失配。  

<a id="toc-4-3-6"></a>

#### 4.3.6 内部协议：收敛推进（Convergence Step）

定义在控制面中推进 Convergence 的协议入口：在满足 3.2.4 本地语义时创建 ReviewTask，并把该 ReviewTaskId 追加到对应 Convergence 的 `review_task_ids`；该任务是否进入本次 Tick 的 `produced_batch` 以及何时入队，由 4.3.5 / 4.3.4 的批处理语义决定。

输入：
- `convergence_id: ConvergenceId`

输出（Result，纯协议返回值，不持久化）：
- `PRODUCED(review_task_id: ReviewTaskId)`：生成了新 ReviewTask
- `BLOCKED`：由于末尾 ReviewTask 仍为 `PENDING`，本次不可生成新任务
- `TERMINATED`：进入终止态（不再生成）

读/写（同一 commit 原子生效）：
- 读取 Convergence（含 `seed_range_id / review_task_ids / state`）。  
- 若 `state == TERMINATED`：返回 `TERMINATED`（不产生写入）。  
- 否则按 3.2.4 的推进规则判定：  
  - 若 `review_task_ids` 非空且末尾 ReviewTask `state == PENDING`：  
    - 返回 `BLOCKED`（不产生写入）。  
  - 若 `review_task_ids` 为空：  
    - 创建第 1 轮 ReviewTask（`input_range_id = seed_range_id`，`state = PENDING`，`executed_at = None`，`result_range_id = None`）  
    - 将其 `review_task_id` 追加到 `review_task_ids`  
    - 返回 `PRODUCED(new_review_task_id)`  
  - 否则（末尾任务为 DONE）读取其 `result_range_id`：  
    - 若 `result_range_id` 非空：创建下一轮 ReviewTask（`input_range_id = result_range_id`，其余字段同上），追加到 `review_task_ids`，返回 `PRODUCED(new_review_task_id)`  
    - 若 `result_range_id` 为空：写 `state := TERMINATED`，返回 `TERMINATED`

门禁一致性声明（强约束）：
- 在 Orchestrator Tick 的门禁成立（项目内全局队列为空 + 全链可推进）时，Convergence Step 不得返回 `BLOCKED`；若出现则视为门禁或链状态判定实现错误。

说明：
- 本协议只负责生成 ReviewTaskId 并写入 Convergence 的轮次序列；不得直接改写项目内全局 `ReviewTaskQueue`。是否进入队列只由 4.3.4 的统一落队阶段决定。

---

<a id="toc-4-4"></a>

### 4.4 Layer 子系统：聚合（Aggregation Subsystem）

<a id="toc-4-4-1"></a>

#### 4.4.1 聚合队列（AggregationQueue，Layer-owned State）

聚合队列是某层用于暂存尚未归入父节点的学习任务节点的 FIFO，仅存放 `LearningTaskNodeId`（不存放 LearningTaskId）。

持久化字段形态（强约束；写死；用于可验证候选集合）
- `project_id: ProjectId`
- `layer_index: int`（所属层）
- `node_ids: Tuple[LearningTaskNodeId, ...]`
- `head_index: int`

语义（强约束）
- 队列的“当前内容”定义为 `node_ids[head_index:]`（队首 → 队尾），且该顺序为权威 FIFO 顺序。
- `head_index` 之前的 ID 视为已逻辑出队；实现不得重排 `node_ids`。

仓库接口（强约束；最小集合；用于 4.4.5）
- 关联仓库：`AggregationQueueRepository`
- `enqueue(session: MutationSession, layer_index: int, node_id: LearningTaskNodeId) -> None`
  - 语义：将 `node_id` 追加到队尾（追加到 `node_ids` 末尾）。
- `current_ids(session: MutationSession, layer_index: int) -> Tuple[LearningTaskNodeId, ...]`
  - 语义：返回当前内容 `node_ids[head_index:]`（队首 → 队尾），不得排序、不得去重、不得省略。
- `is_empty(session: MutationSession, layer_index: int) -> bool`
  - 当且仅当 `current_ids(session, layer_index)` 为空。
- `clear_current(session: MutationSession, layer_index: int) -> None`
  - 语义：清空当前内容；必须通过将 `head_index` 直接设置为 `len(node_ids)` 实现；不得物理删除 `node_ids`，不得重排（与 4.4.5 对齐）。

初始化/恢复语义（强约束）
- 任一可解析的 `Layer`（`layer_index` 可解析）必须且仅能在同一 `project_id` 作用域内对应一条 `AggregationQueue` 持久化记录；其创建必须在系统对外开放前或在创建该 Layer 的同一提交中完成。

<a id="toc-4-4-2"></a>

#### 4.4.2 聚合阈值与触发（Thresholds & Triggers）

阈值由 `(K_node, K_point)` 表达；当且仅当 `threshold_roll_up_enabled == true` 且候选节点数达到 `K_node`，或候选节点覆盖复述点总数达到 `K_point` 时，触发进入聚合周期。

- 若 `threshold_roll_up_enabled == false`：系统不得因为阈值满足而进入/保持 `CLEARING`，也不得记录 `THRESHOLD_DRAIN` 事件；候选节点继续保留在该层 `AggregationQueue` 中，直到用户手动上推（4.4.5）或后续重新开启该开关。

<a id="toc-4-4-3"></a>

#### 4.4.3 聚合周期状态机（AggregationCycle FSM）

状态枚举：
- `CLEARING`：两段式循环（生成段/执行段）
- `ROLL_UP`：上推
- `DONE`：完成

CLEARING（两段式循环）：
- 生成段：当且仅当项目内全局 `ReviewTaskQueue` 为空且本层编排器满足可调用条件时，Layer 按 4.2.4 的触发策略循环尝试 Orchestrator Tick：若某次 Tick 产生了入队则进入执行段；若某次 Tick 返回空产物则结束本层 CLEARING 周期。
- 执行段：执行器必须先清空项目内全局 `ReviewTaskQueue`；队列清空后才允许进入下一次生成段。

<a id="toc-4-4-4"></a>

#### 4.4.4 上推提交（Roll-up Commit）

“系统上推提交”写业务事实：创建聚合父 LearningTaskNode（容器节点）并把子节点重挂到该父节点下。

说明（与复习范围的关系）  
- 父节点的可复习范围由 `LearningTaskNodeRepository.covered_rp_ids(session, parent_node)` 决定（见 1.6.1），并通过 `RangeSnapshotRepository.intern(session, ...)` 得到 `seed_range_id` 后登记到上层。
  - 强约束：若 `covered_rp_ids(session, parent_node)` 为空，则本次上推不得继续执行 Task Register；必须视为 `PreconditionFailure`。

随后必须执行 Task Register：
- 把父 entry_node（LearningTaskNodeId）登记到上层 Layer（保持依赖单向）
- 把父节点入队到上层 AggregationQueue：`AggregationQueueRepository.enqueue(session, upper_layer_index, parent_node_id)`
- 若上层不存在则创建并初始化其资源与状态

说明：
- Task Register 完成后是否立刻触发上层的一次 Orchestrator Tick 由上层 Layer 的 `layer_mode` 决定（见 4.2.4；模式 1 触发，模式 2 不触发）。

统一落地语义（强约束；适用于手动、阈值与学习对象同构触发）
- 上推触发源只允许决定“为何触发”和“选择哪些候选”；一旦候选集合确定，后续落地语义必须一致：消费源层 `AggregationQueue` 中被选中的当前候选、创建或识别唯一父 `LearningTaskNode`、将候选作为该父节点 `children`，并按本节规则登记到上层。
- 学习对象同构触发不得仅因 `LearningObjectNode` 结构存在或 active RecallPoint 覆盖完整而创建上层节点；它必须先从目标学习对象对应的源层 `AggregationQueue.current_ids(...)` 中选出被该学习对象覆盖且尚未消费的候选节点。
- 若学习对象同构触发在源层当前聚合队列中选不出任何被覆盖候选，则本次同构上推对该学习对象必须为 no-op：不得创建上层父节点、不得登记到上层、不得隐式补写聚合队列。
- 若手动或阈值上推已经消费了某学习对象覆盖的候选节点，后续学习对象同构触发不得基于同一内容再次创建同名或同覆盖范围的上层父节点。

<a id="toc-4-4-5"></a>

#### 4.4.5 手动聚合与事件记录（Manual Roll-up Drain & Events）

用途  
手动聚合的唯一语义：**清空目标层的聚合队列（AggregationQueue）**，并将“被清空的全部节点”在一次原子提交中**挂到同一个新建父容器节点**之下，然后按 4.4.4 的规则将该父节点登记到上层。  
该入口不改变自动聚合阈值语义（4.4.2），仅提供“无需等待阈值、立即清空并上推”的显式路径；即使 `threshold_roll_up_enabled == false`，手动聚合仍然允许执行。

接口（系统对外入口）

- `manual_roll_up(project_id: ProjectId, target_layer_index: int, title: Optional[str]) -> Optional[LearningTaskNodeId]`

返回语义：  
- 若目标层 AggregationQueue 为空：返回 `None`，且**不产生任何写入**（不视为失败）。  
- 否则：返回新建父容器节点 `parent_node_id`。

前置条件（precondition failure；失败不产生写入）

- 项目内全局 `ReviewTaskQueue` 为空（受 4.1.3 门禁；队列非空时拒绝）。
- `target_layer_index` 对应 Layer 必须存在且可解析。
- （仅当队列非空时才进入写入路径）从该 Layer 的 `aggregation_queue` 取出的候选节点序列 `candidate_node_ids` 必须满足：
  - `candidate_node_ids` 为非空；
  - `candidate_node_ids` 中每个节点均属于该 Layer 的管理范围（该条件在本接口中以“来自该 Layer 的 aggregation_queue 当前内容”为**充分且确定**的判定方式；实现不得改用外部索引或用户输入替代该事实源）。
  - 候选节点可作为同一父容器的直接子节点：不得包含祖先/后代混杂（避免产生环或重复覆盖）；若违反则拒绝。

祖先/后代混杂的判定算法（强约束；写死）
- 该判定必须在与本次 `manual_roll_up` 写入相同的 mutation session 内、基于同一一致读视图完成（0b.3）。
- 对任意两个不同候选节点 `a, b in candidate_node_ids`，实现必须以 `LearningTaskNodeRepository.path_ids(session, node_id)` 或语义等价的祖先关系查询进行判定：
  - 若 `a in path_ids(session, b)`，则视为 `a` 是 `b` 的祖先；
  - 若 `b in path_ids(session, a)`，则视为 `b` 是 `a` 的祖先。
- 只要存在任意一对候选节点满足上述任一条件，本接口必须抛 `PreconditionFailure`，且不得产生任何 staged 写入。
- 该判定不得做“自动剔除祖先/后代节点后继续执行”的隐式修复；必须整体拒绝。

候选集合的确定（强约束；写死，避免实现分叉）

- 本接口**不得接收** `candidate_node_ids` 参数；候选集合必须且只能来自目标层的 `aggregation_queue`。
- `candidate_node_ids := AggregationQueueRepository.current_ids(session, target_layer_index)`，顺序严格为 FIFO 顺序（队首 → 队尾）。
- `candidate_node_ids` 的顺序为权威：后续挂载到父节点的 `children` 顺序必须与之完全一致；不得排序、不得去重、不得重排。

写入与原子性（同一系统事务内原子生效）

在同一系统级 mutation session 内，基于同一一致读视图完成以下写入；任一步失败则整体回滚（0b.1.2）：

1) 清空聚合队列（强约束：清空语义必须落库）
- 将目标层 `aggregation_queue` 的“当前内容”一次性消费完毕，使其在本次提交后对外呈现为空队列。
- 强约束：不得只“逻辑忽略”而不写队列状态；不得部分清空。
- 实现形态（强约束；写死）：必须调用 `AggregationQueueRepository.clear_current(session, target_layer_index)`，其语义为将 `head_index` 直接设置为 `len(node_ids)`；不得物理删除 `node_ids`，不得重排。

2) 执行 Roll-up Commit（4.4.4）
- 创建父 `LearningTaskNode`（容器节点）`parent_node_id`。
- 将 `candidate_node_ids` 全量重挂为该父节点的 `children`，且 `children` 顺序严格等于 `candidate_node_ids`（见上文顺序强约束）。
- 其他树结构一致性要求由 1.6.3 提交期强制校验保证；若失败则回滚。

3) 对新父节点执行 Task Register（4.3.2）并入上层聚合队列（4.4.4）
- 计算 `seed_rp_ids := LearningTaskNodeRepository.covered_rp_ids(session, parent_node_id)`（见 1.6.1；不去重；顺序由 children 诱导的 DFS 稳定决定）。
- 若 `seed_rp_ids` 为空：必须抛 `PreconditionFailure`；不得继续创建上层 `seed_range_id` / Convergence / ReviewChain。
- `seed_range_id := RangeSnapshotRepository.intern(session, tuple(seed_rp_ids))`
- 创建 Convergence、创建 ReviewChain（初始队列含该 Convergence）、注册到上层 Layer 的 Orchestrator 管理范围。
- 将 `parent_node_id` 入队到上层 Layer 的 `aggregation_queue`：`AggregationQueueRepository.enqueue(session, upper_layer_index, parent_node_id)`（如上层不存在则初始化创建）。

4) Tick 触发约束
- 本接口不得隐式触发 `Orchestrator Tick`；若后续存在由登记触发的 Tick 行为，其触发与否仍由上层 Layer（`upper_layer_index`）的 `layer_mode` 规则决定（4.2.4）。

事件记录（强约束；必须实现）

事件对象（持久化）
- `AggregationEvent`
  - `project_id: ProjectId`
  - `event_id: AggregationEventId`（项目内唯一；排序口径遵循 0a.9）
  - `created_at: Timestamp`
  - `layer_index: int`
  - `parent_node_id: LearningTaskNodeId`
  - `child_node_ids: Tuple[LearningTaskNodeId, ...]`（顺序严格等于 `candidate_node_ids`）
  - `reason: Enum{MANUAL_DRAIN}`
  - `title: Optional[str]`

仓库接口（最小）
- `AggregationEventRepository.append(session: MutationSession, event: AggregationEvent) -> None`

写入承诺（强约束）
- 系统必须在 `manual_roll_up` 成功路径的同一事务内调用 `AggregationEventRepository.append(session, event)` 追加一条事件记录，其字段必须满足：
  - `layer_index == target_layer_index`
  - `parent_node_id` 为本次新建父节点
  - `child_node_ids == candidate_node_ids`
  - `reason == MANUAL_DRAIN`
  - `title` 为请求提供的 title（若提供）

Failure 语义

- 前置条件失败：拒绝执行，不进入 mutation session（0b.5）。
- 提交期校验失败：若树一致性等 commit 强制校验失败（1.6.3）则回滚（0b.1.2）。

---

<a id="toc-4-5"></a>

### 4.5 系统对外入口白名单（System API Whitelist）

目的（强约束；用于使 4.1.3(d) 可测试）
- 系统必须提供一组**可枚举**的对外入口（API 白名单），并对每个入口写死其“是否可能触发调度副作用”（即是否可能调用 4.3.x 内部推进/登记协议）。
- 除本节列出的入口外，系统不得存在其他可触发持久化状态改变的对外入口。
- 可观测性旁路输出例外（强约束）：系统允许为审计/调试/运维目的在任意入口路径上输出仅用于可观测性的旁路日志/指标（见 0b.1.1a）。
  - 该旁路输出不属于任何仓库对象，不产生持久化状态改变，因此不纳入“对外入口白名单”的约束范围；但其失败不得影响业务语义。
  - `READ_ONLY` 语义入口不得因旁路输出而阻塞；旁路输出必须为 best-effort，允许在锁冲突等情况下丢失。
  - 边界澄清：本条不改变 4.6 `AuditLogEvent` 的持久化审计要求；审计事件仍必须在成功提交路径上随业务事实同事务原子落库。

调度副作用分类（强约束）
- `SCHEDULING_EFFECT = NONE`：不调用 `Task Register`（4.3.2）/ `Orchestrator Tick`（4.3.4）/ `ReviewChain Step`（4.3.5）/ `Convergence Step`（4.3.6），且不创建/入队新的 ReviewTask。
- `SCHEDULING_EFFECT = ORCHESTRATION_MUTATING`：可能调用上述任一内部协议，或可能创建/入队新的 ReviewTask。

白名单入口清单（强约束；名字固定；可测试）

1) 会话入口（不产生调度副作用）
- `System.begin_session(project_id: ProjectId, mode: SessionMode) -> MutationSession`
  - 语义补充：返回的 `MutationSession` 必须同时绑定当前调用端的 `runtime_kind/runtime_capabilities`（见 0b.1.6）；这些运行时字段不属于项目事实。
  - `SCHEDULING_EFFECT = NONE`

2) 项目管理（不产生调度副作用）
- `create_project(title: str, project_root: str, initial_source_kind: MaterialSourceKind = SERVER_FS, initial_project_type: ProjectType = COURSE) -> ProjectId`
  - 语义：在一次系统级事务内创建 `Project` 并完成该项目 bootstrap（0b.1.5a）。在该成功提交的同一事务内，系统至少必须写入：  
    - `Project`  
    - 项目内全局队列单例 `ReviewTaskQueue(queue_id == GLOBAL_QUEUE)`  
    - `ProjectStorageConfig(project_root = 规范化后的路径, learning_object_root = PurePosixPath("learning_objects"), fs_sync_policy = STARTUP_SYNC)`（见 1.0.4 / 0b.1.5b）  
      - 强约束（写死默认目录名）：`learning_object_root = PurePosixPath("learning_objects")`。  
      - 若实现允许用户配置该相对路径，则必须通过新增白名单入口扩展；在最小版中不得提供该对外配置入口（避免实现分叉）。  
    - `ProjectMaterialSourceBinding(source_kind = initial_source_kind)`（见 1.0.4a / 0b.1.5b）  
    - `ProjectConfig`（见 1.0.5；必须写入 `project_type = initial_project_type`，以及 `layer_index = 0` 的默认配置与 `push_config` 的写死默认值）  
    - 必须初始化 `layer_index = 0` 的 `Layer`（字段默认值见 0b.1.5a）  
    - 必须初始化 `layer_index = 0` 的 `AggregationQueue`（字段默认值见 0b.1.5a）  
  - 写前条件补充（强约束；0b.5）：
    - `initial_source_kind ∈ {SERVER_FS, BROWSER_LOCAL, NATIVE_LOCAL, MANUAL}`。
    - `initial_project_type ∈ {COURSE, BOOK, LOOSE_POINTS}`。
    - 当 `initial_project_type ∈ {BOOK, LOOSE_POINTS}` 时，`initial_source_kind` 必须为 `MANUAL`。
  - `SCHEDULING_EFFECT = NONE`
- `list_projects() -> Sequence[Project]`
  - `SCHEDULING_EFFECT = NONE`
- `edit_project(project_id: ProjectId, title: str) -> None`
  - 语义：在一次系统事务内更新该项目的 `title`；不得改写 `project_id/created_at/state/deleted_at`，不得触发任何调度推进。
  - `SCHEDULING_EFFECT = NONE`
- `get_project_config(project_id: ProjectId) -> ProjectConfig`
  - 语义：读取并返回该项目的 `ProjectConfig`（1.0.5）；不得产生任何写入。
  - 边界：返回值不得包含 `NativeRuntimeConfig / LocalModelConfig`；这些属于运行时层而非项目事实。
  - `SCHEDULING_EFFECT = NONE`
- `get_project_material_source_binding(project_id: ProjectId) -> ProjectMaterialSourceBinding`
  - 语义：读取并返回该项目当前的权威材料源绑定（1.0.4a）；不得产生任何写入。
  - `SCHEDULING_EFFECT = NONE`
- `set_project_material_source_binding(project_id: ProjectId, source_kind: MaterialSourceKind, source_root_label: Optional[str]) -> None`
  - 语义：在一次系统事务内覆盖该项目的 `ProjectMaterialSourceBinding`（1.0.4a）。
  - 约束：
    - 更新绑定本身不得隐式触发 `sync_learning_objects_from_fs(...)`、`import_learning_objects_from_browser_scan(...)`、`sync_learning_objects_from_native_scan(...)` 或任何调度推进。
    - 已提交的 `Instance/LearningObjectNode` 集合必须保持不变，直到后续显式同步或导入成功。
    - 当 `source_kind == NATIVE_LOCAL` 时，本入口只写入“项目当前选择 Native 本地目录模式”的控制事实与展示标签；稳定目录句柄与绝对路径仍只属于当前 Native 运行时。
    - 当 `source_kind == MANUAL` 时，后续材料事实必须仅通过手工写入口维护；系统不得再把目录扫描或浏览器导入视为当前权威事实，除非绑定再次被显式切换。
  - `SCHEDULING_EFFECT = NONE`
- `delete_project(project_id: ProjectId) -> None`
  - 语义：按 4.1.7 删除该项目作用域内全部持久化对象。
  - `SCHEDULING_EFFECT = NONE`

3) 对象创建/导入（不产生调度副作用）
- `add_instance(project_id: ProjectId, material_id: str) -> InstanceId`
  - 语义：在 `project_id` 作用域内创建一个新的 `Instance` 并返回其 `instance_id`。
  - 约束：`material_id` 的规范化与存储语义必须满足 1.1.1（使用 POSIX 语义 `PurePosixPath` 规范化；不得做可达性探测、外部访问或隐式修复）。当当前 `source_kind == MANUAL` 时，`material_id` 可以仅作为稳定的虚拟材料标识使用，例如书名/册别/章节路径样式标识。
  - 额外约束（强约束）：当 `ProjectConfig.project_type == LOOSE_POINTS` 时，本入口必须抛 `PreconditionFailure`（该项目类型不维护实例）。
  - 额外约束（强约束）：当项目启用 0b.1.5b 的同步/导入协议时，本入口必须抛 `PreconditionFailure`（`Instance` 集合由材料源协议唯一维护，0b.1.5b）。
  - `SCHEDULING_EFFECT = NONE`
- `add_learning_object_leaf(project_id: ProjectId, parent_id: Optional[LearningObjectNodeId], instance_id: InstanceId, title: str) -> LearningObjectNodeId`
  - 语义：在 `project_id` 作用域内创建一个新的 `LearningObjectLeaf` 并返回其 `node_id`。
  - 约束：不得触发任何调度推进；树一致性由 1.2.3 的提交期强制校验保证。当当前 `source_kind == MANUAL` 时，本入口可用于把书本、题册、讲义等非文件材料挂到手工目录树下。
  - 额外约束（强约束）：当 `ProjectConfig.project_type == LOOSE_POINTS` 时，本入口必须抛 `PreconditionFailure`（该项目类型不维护学习对象树）。
  - 额外约束（强约束）：当项目启用 0b.1.5b 的同步/导入协议时，本入口必须抛 `PreconditionFailure`（`LearningObject` 树由材料源协议唯一维护，0b.1.5b）。
  - `SCHEDULING_EFFECT = NONE`
- `add_learning_object_container(project_id: ProjectId, parent_id: Optional[LearningObjectNodeId], children: Sequence[LearningObjectNodeId], title: str) -> LearningObjectNodeId`
  - 语义：在 `project_id` 作用域内创建一个新的 `LearningObjectContainer` 并返回其 `node_id`。
  - 约束：不得触发任何调度推进；`children` 顺序为权威顺序；树一致性由 1.2.3 的提交期强制校验保证。允许 `children == ()`；当当前 `source_kind == MANUAL` 时，空容器可作为手工纲目/空目录挂载点使用。
  - 额外约束（强约束）：当 `ProjectConfig.project_type == LOOSE_POINTS` 时，本入口必须抛 `PreconditionFailure`（该项目类型不维护学习对象树）。
  - 额外约束（强约束）：当项目启用 0b.1.5b 的同步/导入协议时，本入口必须抛 `PreconditionFailure`（`LearningObject` 树由材料源协议唯一维护，0b.1.5b）。
  - `SCHEDULING_EFFECT = NONE`
- `initialize_book_learning_objects(project_id: ProjectId, outline_items: Sequence[(depth: int, title: str)]) -> {created_instances_count: int, created_learning_object_nodes_count: int, root_count: int}`
  - 语义：当且仅当 `project_type == BOOK` 且当前项目仍为空手工树时，按用户提供的目录层级文本一次性初始化手工学习对象树：非末级目录项创建 `LearningObjectContainer`，末级目录项创建 `LearningObjectLeaf`，并自动为每个末级目录项创建一个手工 `Instance`。
  - 写前条件（强约束；0b.5）：
    - `project_type == BOOK`。
    - 当前 `ProjectMaterialSourceBinding.source_kind == MANUAL`。
    - 当前项目内 `Instance` 集合与 `LearningObjectNode` 树都为空。
    - `outline_items` 非空，首项 `depth == 0`，且层级每次最多只允许向下增加一级。
  - `SCHEDULING_EFFECT = NONE`
- `initialize_book_learning_objects_from_subject_material(project_id: ProjectId, source_material_id: str) -> {created_instances_count: int, created_learning_object_nodes_count: int, root_count: int}`
  - 语义：当 `project_type == BOOK` 且当前项目仍为空手工树时，从同一学科下的来源材料复制学习对象结构来初始化当前项目。
  - 写前条件（强约束；0b.5）：
    - `project_type == BOOK`。
    - 当前 `ProjectMaterialSourceBinding.source_kind == MANUAL`。
    - 当前项目内 `Instance` 集合与 `LearningObjectNode` 树都为空。
    - `source_material_id` 对应材料类型必须为 `COURSE`。
  - `SCHEDULING_EFFECT = NONE`

4) 材料源同步与缺失迁移辅助（不产生调度副作用）
- `SyncReport`（值对象；最小返回契约，强约束）
  - `unchanged: bool`
    - 语义：当且仅当本次同步未对任何持久化对象产生变更时为 `true`。
  - `created_instances_count: int`
  - `marked_missing_count: int`
  - `replaced_learning_object_nodes_count: int`
  - `warnings: Tuple[str, ...]`
    - 语义：非致命提示；允许为空。实现不得在此字段中伪装错误成功。
- `sync_learning_objects_from_fs(project_id: ProjectId) -> SyncReport`
  - 语义：当且仅当 `project_type == COURSE` 且 `source_kind == SERVER_FS` 时，按 0b.1.5b 对 `learning_object_root` 执行一次同步：检查目录条目合法性与同构；若一致则幂等返回；若不一致则重建 `LearningObjectNode` 树、为新增文件创建 `Instance`、并将缺失文件对应 `Instance` 标记为 `MISSING`。
  - 返回约束（强约束）：
    - 若本次同步未产生任何持久化变更，则必须返回 `SyncReport(unchanged=true, created_instances_count=0, marked_missing_count=0, replaced_learning_object_nodes_count=0, warnings=...)`。
    - 若本次同步成功且产生了变更，则必须返回 `unchanged=false`，且三个 count 字段必须准确反映本次提交实际生效的变更数量。
  - `SCHEDULING_EFFECT = NONE`
  - 门禁（强约束）：本入口不得调用 4.3.x 任一协议；不得创建/入队 ReviewTask。是否允许在队列非空时执行由实现决定，但若允许必须不改变任何调度相关对象。
  - Failure：目录结构损坏必须抛 `DirectoryStructureCorruptedError` 且不产生任何写入（0b.5）。
- `import_learning_objects_from_browser_scan(project_id: ProjectId, root_title: Optional[str], relative_file_paths: Sequence[PurePath | str]) -> SyncReport`
  - 语义：当且仅当 `project_type == COURSE` 且 `source_kind == BROWSER_LOCAL` 时，按 0b.1.5b 接收一次浏览器本地目录显式导入：对 `relative_file_paths` 做规范化、构造父目录闭包与直接孩子集合；若与已提交结果一致则幂等返回；若不一致则重建 `LearningObjectNode` 树、为新增文件创建 `Instance`、并将缺失文件对应 `Instance` 标记为 `MISSING`。
  - 额外语义（强约束）：若本次导入成功且当前绑定不是 `BROWSER_LOCAL`，系统必须在同一事务内将该项目的 `ProjectMaterialSourceBinding.source_kind` 更新为 `BROWSER_LOCAL`，并把 `source_root_label` 更新为导入使用的根目录显示名（若空则写入最小实现默认值 `"已授权目录"`）。
  - 返回约束（强约束）：
    - 若本次导入未产生任何持久化变更，则必须返回 `SyncReport(unchanged=true, created_instances_count=0, marked_missing_count=0, replaced_learning_object_nodes_count=0, warnings=...)`。
    - 若本次导入成功且产生了变更，则必须返回 `unchanged=false`，且三个 count 字段必须准确反映本次提交实际生效的变更数量。
  - `SCHEDULING_EFFECT = NONE`
  - 门禁（强约束）：本入口不得调用 4.3.x 任一协议；不得创建/入队 ReviewTask。是否允许在队列非空时执行由实现决定，但若允许必须不改变任何调度相关对象。
  - Failure：非法相对路径、空导入、非支持媒体扩展名或目录结构损坏必须抛明确错误且不产生任何写入（0b.5）。
- `sync_learning_objects_from_native_scan(project_id: ProjectId, root_title: Optional[str], relative_file_paths: Sequence[PurePath | str]) -> SyncReport`
  - 语义：当且仅当 `project_type == COURSE` 且 `source_kind == NATIVE_LOCAL` 时，按 0b.1.5b 接收一次来自 `DESKTOP_NATIVE` 运行时稳定目录绑定的快照同步：对 `relative_file_paths` 做与 `BROWSER_LOCAL` 相同的规范化、构造父目录闭包与直接孩子集合；若与已提交结果一致则幂等返回；若不一致则重建 `LearningObjectNode` 树、为新增文件创建 `Instance`、并将缺失文件对应 `Instance` 标记为 `MISSING`。
  - 额外语义（强约束）：若本次同步成功且当前绑定不是 `NATIVE_LOCAL`，系统必须在同一事务内将该项目的 `ProjectMaterialSourceBinding.source_kind` 更新为 `NATIVE_LOCAL`，并把 `source_root_label` 更新为当前 Native 目录显示名（若空则写入最小实现默认值 `"已绑定目录"`）。
  - 返回约束（强约束）：
    - 若本次同步未产生任何持久化变更，则必须返回 `SyncReport(unchanged=true, created_instances_count=0, marked_missing_count=0, replaced_learning_object_nodes_count=0, warnings=...)`。
    - 若本次同步成功且产生了变更，则必须返回 `unchanged=false`，且三个 count 字段必须准确反映本次提交实际生效的变更数量。
  - `SCHEDULING_EFFECT = NONE`
  - 门禁（强约束）：本入口不得调用 4.3.x 任一协议；不得创建/入队 ReviewTask。是否允许在队列非空时执行由实现决定，但若允许必须不改变任何调度相关对象。
  - Failure：非法相对路径、空输入、非支持媒体扩展名、运行时不在 `DESKTOP_NATIVE`、或目录结构损坏必须抛明确错误且不产生任何写入（0b.5）。
- `list_missing_instances(project_id: ProjectId) -> Sequence[InstanceId]`
  - 语义：返回本项目内所有 `presence == MISSING` 的 InstanceId（按 `id_canonical_text(instance_id)` 升序）。
  - `SCHEDULING_EFFECT = NONE`

- `list_recall_points_by_instance(project_id: ProjectId, instance_id: InstanceId) -> Sequence[RecallPointId]`
  - 语义：返回所有满足 `RecallPoint.anchor != None`、`RecallPoint.anchor.instance_id == instance_id` 且 `RecallPoint.state == ACTIVE` 的复述点 ID（返回顺序按 `id_canonical_text(recall_point_id)` 升序）。
  - `SCHEDULING_EFFECT = NONE`

- `bulk_remap_recall_points_instance(project_id: ProjectId, from_instance_id: InstanceId, to_instance_id: InstanceId, recall_point_ids: Optional[Sequence[RecallPointId]] = None) -> int`
  - 语义：批量将目标 RecallPoint 的 `anchor.instance_id` 从 `from_instance_id` 迁移到 `to_instance_id`；用于用户对 MISSING Instance 的手动修复。
  - 若 `recall_point_ids` 为空：默认迁移所有满足 `anchor.instance_id == from_instance_id` 且 `state == ACTIVE` 的 RecallPoint。
  - 写前条件（强约束；0b.5）：`from_instance_id/to_instance_id` 必须可解析；建议要求 `to_instance_id.presence == PRESENT`；迁移的 RecallPoint 必须均可解析，且必须全部满足 `state == ACTIVE`。
  - `SCHEDULING_EFFECT = NONE`

5) 学习提交（会产生调度副作用）

- `submit_learning_task(project_id: ProjectId, items: Sequence[(question: RichContent, answer: RichContent, anchor: Optional[Anchor], references: Sequence[RecallPointId])], title: str) -> LearningTaskNodeId`
  - 语义：执行 2.1（学习任务提交）并在同一提交中完成该入口节点的登记（4.3.2）；是否触发 Tick 由 Layer 的 `layer_mode` 决定（4.2.4）。
  - 项目类型约束（强约束；写死）：
    - `COURSE`：每个 item 的 `anchor` 必须存在，且必须满足 1.3.1 的 COURSE 锚点规则。
    - `BOOK`：每个 item 的 `anchor` 必须存在，且必须满足 1.3.1 的 BOOK 锚点规则。
    - `LOOSE_POINTS`：每个 item 的 `anchor` 必须为 `None`。
  - `SCHEDULING_EFFECT = ORCHESTRATION_MUTATING`
  - 门禁：受 4.1.3(a) 约束（项目内全局 ReviewTaskQueue 非空时必须拒绝）。

6) 编辑/删除类写入（不产生调度副作用）
- `edit_recall_point(project_id: ProjectId, recall_point_id: RecallPointId, question: RichContent, answer: RichContent, anchor: Optional[Anchor]) -> None`
  - 语义：只调用 `RecallPointRepository.update(...)` 产生业务事实更新；不得调用任一 4.3.x 推进协议；不得创建/入队 ReviewTask。
  - 项目类型约束：同 `submit_learning_task(...)`。
  - `SCHEDULING_EFFECT = NONE`
  - 门禁：允许在队列非空时执行（4.1.3(b)）。
- `delete_recall_point(project_id: ProjectId, recall_point_id: RecallPointId) -> None`
  - 语义：在一次系统事务内调用 `RecallPointRepository.mark_deleted(...)` 对目标复述点执行墓碑删除；不得物理删除对象，不得隐式级联改写既有 `LearningTask`、`LearningTaskNode`、`RangeSnapshot`、`ReviewTask`、`Convergence`、`ReviewChain`、`RecallPointReviewRecord` 或 `AsrArtifact`。
  - 约束：不得调用任一 4.3.x 推进协议；不得创建/入队新的 ReviewTask。
  - `SCHEDULING_EFFECT = NONE`
  - 门禁：允许在队列非空时执行（4.1.3(b)）。
- `edit_learning_task(project_id: ProjectId, learning_task_id: LearningTaskId, title: str) -> None`
  - 语义：在一次系统事务内调用 `LearningTaskRepository.update(...)` 更新该 LearningTask 的 `title`；不得调用任一 4.3.x 推进协议；不得创建/入队 ReviewTask。
  - `SCHEDULING_EFFECT = NONE`
  - 门禁：允许在队列非空时执行（4.1.3(b)）。
- `set_layer_config(project_id: ProjectId, layer_index: int, review_chain_template: Optional[ReviewChainTemplate], K_node: Optional[int], K_point: Optional[int], threshold_roll_up_enabled: Optional[bool]) -> None`
  - 语义：只修改配置与 Layer 控制字段；不得调用任一 4.3.x 推进协议；不得创建/入队 ReviewTask。
    - 在同一系统事务内 upsert：`ProjectConfig.layer_configs[layer_index]`（1.0.5）。  
    - 若该 `layer_index` 对应 Layer 已存在：必须在同一事务内调用 `LayerRepository.update_threshold(...)` 更新 Layer 当前阈值，使更新对未来立即生效。  
    - 合并语义（强约束；写死避免分叉）：若某可选参数为 `None`，则该字段保持“更新前”的值；若该层此前无配置，则以 1.0.5 的默认 `LayerConfig` 作为合并基线。  
  - `SCHEDULING_EFFECT = NONE`
  - 门禁：允许在队列非空时执行（4.1.3(b)）。

7) 执行器落库闭环（允许在队列非空时执行）
- `executor_commit_review_task(project_id: ProjectId, review_task_id: ReviewTaskId, can_recall: Sequence[0|1], appended_insights: Optional[Sequence[(recall_point_id: RecallPointId, insight: RichContent)]] = None) -> None`
  - 语义：在一次系统事务内完成 2.2 的派生（`result_range_id`）并执行 4.3.3 `ReviewTask Commit`（`PENDING -> DONE` + 写入结果 + Q2 出队）。
  - 语义补充（强约束）：若提供 `appended_insights`，系统必须在同一事务内对其中每条 `(recall_point_id, insight)` 调用 `RecallPointRepository.append_insight(...)` 追加感悟；并且这些 `recall_point_id` 必须属于本次 ReviewTask 的输入范围（`input_range_id`）所覆盖的复述点集合，否则必须抛 `PreconditionFailure`（失败不产生任何 staged 写入，0b.5）。

  - 复习记录写入（强约束；业务事实）：系统必须在同一事务内为本次输入范围内的每个复述点追加一条 `RecallPointReviewRecord`（1.12），并满足：  
    - `record.review_task_id == review_task_id`；  
    - `record.occurred_at == executed_at`（即本次 ReviewTask 的执行时间）；  
    - `record.result` 与 `can_recall` 同序对齐：`can_recall[i]==1 -> CAN_RECALL`，`can_recall[i]==0 -> CANNOT_RECALL`；  
    - 记录的 `recall_point_id` 序列必须严格等于本次 `input_range_id` 的 `recall_point_ids` 序列（同序），不得排序、不得去重、不得省略。  


  - `SCHEDULING_EFFECT = ORCHESTRATION_MUTATING`
  - 门禁：
    - 允许在队列非空时执行（4.1.3(c)），且必须严格 FIFO 仅对 `ReviewTaskQueueRepository.peek_head(session)` 返回的队首任务调用（4.1.3 执行模型）。

8) 手动聚合上推（会产生调度副作用）
- `manual_roll_up(project_id: ProjectId, target_layer_index: int, title: Optional[str]) -> Optional[LearningTaskNodeId]`
  - 语义：按 4.4.5 清空目标层聚合队列并上推登记到上层；不得隐式触发 Tick（4.4.5）。
  - `SCHEDULING_EFFECT = ORCHESTRATION_MUTATING`
  - 门禁：受 4.1.3 约束（项目内全局 ReviewTaskQueue 非空时必须拒绝）。

9) 节点作用域数据导出（不产生调度副作用）
- `export_recall_points_by_learning_object_node(project_id: ProjectId, node_id: LearningObjectNodeId) -> Sequence[RecallPointData]`
  - 语义：返回该学习对象节点覆盖到的全部**当前内容**复述点数据；纯读取；必须排除 `state == DELETED` 的 RecallPoint；返回顺序必须按 `recall_point_id` 升序。
  - `SCHEDULING_EFFECT = NONE`
- `export_recall_points_by_learning_task_node(project_id: ProjectId, node_id: LearningTaskNodeId) -> Sequence[RecallPointData]`
  - 语义：返回该学习任务节点覆盖到的全部**当前内容**复述点数据；纯读取；其集合必须严格等于 `LearningTaskNodeRepository.covered_rp_ids(...)` 所返回的 ACTIVE RecallPoint 集合；返回顺序必须按该节点覆盖顺序稳定返回。
  - `SCHEDULING_EFFECT = NONE`
- `export_asr_by_learning_object_node(project_id: ProjectId, node_id: LearningObjectNodeId) -> Sequence[AsrArtifactData]`
  - 语义：兼容性只读接口；若实现保留它，则只返回历史版本中已提交的 `AsrArtifact`。现行 `request_asr(...)` 生成的新浏览器缓存结果不得隐式进入该接口。
  - `SCHEDULING_EFFECT = NONE`
- `export_asr_by_learning_task_node(project_id: ProjectId, node_id: LearningTaskNodeId) -> Sequence[AsrArtifactData]`
  - 语义：兼容性只读接口；若实现保留它，则只返回历史版本中已提交的 `AsrArtifact`。现行 `request_asr(...)` 生成的新浏览器缓存结果不得隐式进入该接口。
  - `SCHEDULING_EFFECT = NONE`

10) 运行时辅助写入口
- `request_asr(project_id: ProjectId, recall_point_id: RecallPointId, center_ms: int, pre_ms: int, post_ms: int, provider: AsrProvider=WHISPER, service_config: Optional[LocalServiceConfig]=None) -> AsrTranscriptResult`
  - 语义：按 2.9 返回一次临时 `AsrTranscriptResult`；目标 `recall_point_id` 必须对应 `state == ACTIVE` 的 RecallPoint。
  - 额外门禁：当前部署必须启用 ASR 功能，且系统必须能解析出可用的服务配置与鉴权信息；不再要求 `DESKTOP_NATIVE`。
  - `SCHEDULING_EFFECT = NONE`
- `request_asr_from_audio_upload(project_id: ProjectId, recall_point_id: RecallPointId, center_ms: int, pre_ms: int, post_ms: int, audio_bytes: bytes, audio_filename: Optional[str]=None, audio_content_type: Optional[str]=None, provider: AsrProvider=WHISPER, service_config: Optional[LocalServiceConfig]=None) -> AsrTranscriptResult`
  - 语义：与 `request_asr(...)` 返回值一致，但输入音频片段由浏览器或其他客户端先行裁剪并显式上传；该入口是 `BROWSER_LOCAL` 主路径的推荐实现方式。
  - 额外门禁：当前部署必须启用 ASR 功能，且系统必须能解析出可用的服务配置与鉴权信息；上传的 `audio_bytes` 只允许在当前请求生命周期内暂存。
  - `SCHEDULING_EFFECT = NONE`
- `request_instance_asr(project_id: ProjectId, instance_id: InstanceId, start_ms: int, end_ms: int, provider: AsrProvider=WHISPER, service_config: Optional[LocalServiceConfig]=None) -> InstanceAsrTranscriptResult`
  - 语义：按 2.9 返回一次素材实例时间块的临时转写结果，适合播放器字幕与浏览器时间块缓存；不得隐式创建新的 RecallPoint。
  - 额外门禁：当前部署必须启用 ASR 功能，且系统必须能解析出可用的服务配置与鉴权信息；`SERVER_FS` 兼容路径仍受服务端 `ffmpeg` 并发与超时治理约束。
  - `SCHEDULING_EFFECT = NONE`
- `request_instance_asr_from_audio_upload(project_id: ProjectId, instance_id: InstanceId, start_ms: int, end_ms: int, audio_bytes: bytes, audio_filename: Optional[str]=None, audio_content_type: Optional[str]=None, provider: AsrProvider=WHISPER, service_config: Optional[LocalServiceConfig]=None) -> InstanceAsrTranscriptResult`
  - 语义：与 `request_instance_asr(...)` 返回值一致，但输入音频片段由浏览器或其他客户端先行裁剪并显式上传；该入口是 `BROWSER_LOCAL` 字幕路径的推荐实现方式。
  - 额外门禁：当前部署必须启用 ASR 功能，且系统必须能解析出可用的服务配置与鉴权信息；上传的 `audio_bytes` 只允许在当前请求生命周期内暂存。
  - `SCHEDULING_EFFECT = NONE`
- `extract_temp_context_fragment(project_id: ProjectId, recall_point_id: RecallPointId, source_asr_artifact_id: Optional[AsrArtifactId], start_ms: Optional[int], end_ms: Optional[int], text: Optional[str]) -> TempContextFragmentId`
  - 语义：按 2.10 生成 `TempContextFragment`。
  - 额外门禁：无 Native-only 门禁；任一可写运行时都可执行。
  - `SCHEDULING_EFFECT = NONE`
- `ask_local_llm(project_id: ProjectId, prompt: str, context_fragment_ids: Sequence[TempContextFragmentId], qa_session_id: Optional[QASessionId] = None) -> QASession`
  - 语义：按 2.11 创建或追加 `QASession`。
  - 额外门禁：当前会话必须具备 `LOCAL_LLM_QA` 能力，且系统必须能够解析出可用的 LLM 服务配置与鉴权信息。
  - `SCHEDULING_EFFECT = NONE`
- `generate_candidate_recall_points_from_qa(project_id: ProjectId, qa_session_id: QASessionId, max_items: int = 5) -> Sequence[CandidateRecallPointId]`
  - 语义：按 2.12 生成 `CandidateRecallPoint`。
  - 额外门禁：当前会话必须具备 `LOCAL_LLM_QA` 能力，且系统必须能够解析出可用的 LLM 服务配置与鉴权信息。
  - `SCHEDULING_EFFECT = NONE`
- `accept_candidate_recall_point(project_id: ProjectId, candidate_recall_point_id: CandidateRecallPointId, anchor: Anchor, title: Optional[str] = None) -> (learning_task_node_id: LearningTaskNodeId, recall_point_id: RecallPointId)`
  - 语义：在一次系统事务内执行 2.13，并在同一事务内完成该入口节点的登记（4.3.2）；是否触发 Tick 由 Layer 的 `layer_mode` 决定（4.2.4）。
  - 额外门禁：无 LLM / Native 专属门禁；任一可写运行时都可执行。
  - `SCHEDULING_EFFECT = ORCHESTRATION_MUTATING`
  - 门禁：受 4.1.3(a) 约束（项目内全局 ReviewTaskQueue 非空时必须拒绝）。
- `reject_candidate_recall_point(project_id: ProjectId, candidate_recall_point_id: CandidateRecallPointId) -> None`
  - 语义：按 2.14 将候选点标记为 `REJECTED`。
  - 额外门禁：无 LLM / Native 专属门禁；任一可写运行时都可执行。
  - `SCHEDULING_EFFECT = NONE`
- `create_memory_canvas(project_id: ProjectId, title: str, object_refs: Sequence[CanvasObjectRef]) -> MemoryCanvasId`
  - 语义：按 2.15 创建 `MemoryCanvas`。
  - 额外门禁：当前会话必须来自 `DESKTOP_NATIVE` 且具备 `MEMORY_CANVAS_EDIT` 能力。
  - `SCHEDULING_EFFECT = NONE`
- `save_memory_canvas_version(project_id: ProjectId, memory_canvas_id: MemoryCanvasId, nodes: Sequence[CanvasNodeSnapshot], summary_note: Optional[str] = None) -> MemoryCanvasVersionId`
  - 语义：按 2.16 保存画布版本。
  - 额外门禁：当前会话必须来自 `DESKTOP_NATIVE` 且具备 `MEMORY_CANVAS_EDIT` 能力。
  - `SCHEDULING_EFFECT = NONE`
- `set_canvas_edges(project_id: ProjectId, memory_canvas_id: MemoryCanvasId, edges: Sequence[(from_ref: CanvasObjectRef, to_ref: CanvasObjectRef, label: Optional[str])]) -> None`
  - 语义：按 2.17 更新画布当前边集。
  - 额外门禁：当前会话必须来自 `DESKTOP_NATIVE` 且具备 `MEMORY_CANVAS_EDIT` 能力。
  - `SCHEDULING_EFFECT = NONE`
- `generate_story_artifact(project_id: ProjectId, title: str, source_refs: Sequence[CanvasObjectRef], qa_session_id: Optional[QASessionId] = None, memory_canvas_id: Optional[MemoryCanvasId] = None) -> StoryArtifactId`
  - 语义：按 2.18 生成 `StoryArtifact`。
  - 额外门禁：当前会话必须具备 `STORY_GENERATION` 能力，且系统必须能够解析出可用的故事生成服务配置与鉴权信息。
  - `SCHEDULING_EFFECT = NONE`

11) 只读 projection / 推荐 / 压缩 / 漂移 / 画布视图
- `list_timeline_anchors(project_id: ProjectId, instance_id: InstanceId) -> Sequence[TimelineAnchor]`
  - 语义：返回该材料实例上的时间锚点视图；纯读取。
  - `SCHEDULING_EFFECT = NONE`
- `get_memory_barrage_at_time(project_id: ProjectId, instance_id: InstanceId, center_ms: int, window_ms: int = 30_000) -> Sequence[MemoryBarrageItem]`
  - 语义：返回目标时间窗内的“弹幕式记忆投影”；该结果只能由既有事实投影得到，不得写入任何“会/不会”结果。
  - `SCHEDULING_EFFECT = NONE`
- `list_review_recommendations(project_id: ProjectId, offset: int = 0, limit: Optional[int] = None) -> (items: Sequence[RecallPointReviewRecommendation], total_count: int, next_offset: Optional[int], limit: int)`
  - 语义：按 4.7 返回按推荐指数降序排列的“只读推荐复习”批次；若 `limit` 省略，则必须读取 `ProjectConfig.push_config.recommended_batch_size` 作为批大小；纯读取。
  - `SCHEDULING_EFFECT = NONE`
- `get_recall_point_review_projection(project_id: ProjectId, recall_point_id: RecallPointId) -> RecallPointReviewProjection`
  - 语义：返回单个复述点的只读复习投影，包括历史记录、当前记忆强度、复习推荐指数与绘制复习曲线所需的数据；纯读取。
  - `SCHEDULING_EFFECT = NONE`
- `set_review_recommendation_config(project_id: ProjectId, min_recall_points_to_enable: Optional[int] = None, max_history_len: Optional[int] = None, recommended_batch_size: Optional[int] = None, forgetting_curve_decay_per_day: Optional[float] = None) -> None`
  - 语义：合并更新 `ProjectConfig.push_config`；不得影响任何既有 `ReviewTask / ReviewChain / Convergence / LearningTaskNode`。
  - `SCHEDULING_EFFECT = NONE`
- `get_compression_summary(project_id: ProjectId, learning_task_node_id: Optional[LearningTaskNodeId] = None) -> CompressionSummary`
  - 语义：按 4.7 返回压缩感摘要；纯读取。
  - `SCHEDULING_EFFECT = NONE`
- `list_drift_alerts(project_id: ProjectId, max_results: int) -> Sequence[DriftAlert]`
  - 语义：按 4.7 返回漂移预警；纯读取。
  - `SCHEDULING_EFFECT = NONE`
- `list_memory_canvases(project_id: ProjectId) -> Sequence[MemoryCanvas]`
  - 语义：返回项目内全部画布元数据；纯读取。
  - `SCHEDULING_EFFECT = NONE`
- `get_memory_canvas(project_id: ProjectId, memory_canvas_id: MemoryCanvasId) -> (canvas: MemoryCanvas, current_edges: Sequence[CanvasEdge], latest_version: Optional[MemoryCanvasVersion])`
  - 语义：返回指定画布的当前工作态视图；纯读取。
  - `SCHEDULING_EFFECT = NONE`
- `list_canvas_versions(project_id: ProjectId, memory_canvas_id: MemoryCanvasId) -> Sequence[MemoryCanvasVersion]`
  - 语义：返回指定画布的全部历史版本；纯读取。
  - `SCHEDULING_EFFECT = NONE`
- `list_story_artifacts(project_id: ProjectId, memory_canvas_id: Optional[MemoryCanvasId] = None) -> Sequence[StoryArtifact]`
  - 语义：返回故事化产物列表；纯读取。
  - `SCHEDULING_EFFECT = NONE`


12) 显式校验（不产生调度副作用）
- `validate_material_reachable(project_id: ProjectId, instance_id: InstanceId) -> ValidationResult`
  - 语义：调用 0b.7.2/0b.7.3 定义的显式校验接口；不得改写既有已提交事实。
  - `SCHEDULING_EFFECT = NONE`
- `validate_recall_point_ids_resolvable(project_id: ProjectId, range_id: RangeId) -> ValidationResult`
  - 语义：同上。
  - `SCHEDULING_EFFECT = NONE`

---

<a id="toc-4-6"></a>

### 4.6 审计日志（Audit Logging）

目的（强约束；纯审计）
- 为审计/排障提供“成功提交动作”的可枚举轨迹。
- 强约束：审计日志不得被任何协议/门禁/派生计算读取或依赖；系统行为不得因审计日志的内容而变化（纯审计，不是业务事实）。
- 可测试口径（强约束）：在同一业务事实状态下（除审计表外其他对象完全相同），删除或清空全部 `AuditLogEvent` 不得改变任何对外 API 的返回值、门禁判定或调度推进结果（除非未来新增专门读取审计日志的只读接口）。


记录边界（强约束；写死）
- 本规格仅强制记录“成功提交（commit 成功）”的对外写入口动作；失败路径（PreconditionFailure/NotFound/CommitTimeValidationFailure 等）不强制落入 `AuditLogRepository`，以避免与 0b.5 “失败不产生任何 staged 写入”冲突。
- 审计事件必须在与对应业务事实写入**同一系统级 mutation session**内追加，并随该事务 `commit()` 原子生效；`commit()` 失败则不得留下事件（0b.1.2）。

生成规则（强约束）
- 除 `System.begin_session(...)` 与 `list_projects()` 外，4.5 中所有会产生持久化业务事实变更的对外入口，在其成功提交路径上必须追加且仅追加一条 `AuditLogEvent`（1.8）。
- `AuditLogEvent.api_name` 必须等于该入口名；`AuditLogEvent.result` 必须为 `OK`。
- `payload` 只允许摘要字段：计数、ID、布尔、哈希；不得写入完整大对象内容。
- 对少数“同一 API 名但存在运行时分支语义”的入口，允许按成功分支选择不同 `AuditEventKind`；但一次 API 成功提交路径上仍必须且只能落一条审计事件。

事件类型映射（强约束；最小集合）
- `create_project(...)` -> `PROJECT_CREATED`
- `delete_project(...)` -> `PROJECT_DELETED`
- `edit_project(...)` -> `EDIT_PROJECT`
- `add_instance(...)` -> `ADD_INSTANCE`
- `add_learning_object_leaf(...)` -> `ADD_LEARNING_OBJECT_LEAF`
- `add_learning_object_container(...)` -> `ADD_LEARNING_OBJECT_CONTAINER`
- `set_project_material_source_binding(...)` -> `SET_PROJECT_MATERIAL_SOURCE_BINDING | BIND_NATIVE_LOCAL_ROOT`（当成功分支把 `source_kind` 设为 `NATIVE_LOCAL` 时必须落 `BIND_NATIVE_LOCAL_ROOT`）
- `sync_learning_objects_from_fs(...)` -> `SYNC_LEARNING_OBJECTS_FROM_FS`
- `import_learning_objects_from_browser_scan(...)` -> `SYNC_LEARNING_OBJECTS_FROM_FS`（最小实现复用同一审计事件种类；以 `api_name` 区分具体入口）
- `sync_learning_objects_from_native_scan(...)` -> `SYNC_LEARNING_OBJECTS_FROM_FS`（最小实现复用同一审计事件种类；以 `api_name` 区分具体入口）
- `bulk_remap_recall_points_instance(...)` -> `BULK_REMAP_RECALL_POINTS_INSTANCE`
- `submit_learning_task(...)` -> `SUBMIT_LEARNING_TASK`
- `edit_recall_point(...)` -> `EDIT_RECALL_POINT`
- `delete_recall_point(...)` -> `DELETE_RECALL_POINT`
- `edit_learning_task(...)` -> `EDIT_LEARNING_TASK`
- `set_layer_config(...)` -> `EDIT_PROJECT_CONFIG`
- `set_review_recommendation_config(...)` -> `EDIT_PROJECT_CONFIG`
- `executor_commit_review_task(...)` -> `EXECUTOR_COMMIT_REVIEW_TASK`
- `manual_roll_up(...)` -> `MANUAL_ROLL_UP`
- `request_asr(...)` -> `REQUEST_ASR`
- `extract_temp_context_fragment(...)` -> `EXTRACT_TEMP_CONTEXT_FRAGMENT`
- `ask_local_llm(...)` -> `CREATE_QA_SESSION | REQUEST_LOCAL_LLM`（当该调用新建 `QASession` 时记 `CREATE_QA_SESSION`；向既有会话追加 turn 时记 `REQUEST_LOCAL_LLM`）
- `generate_candidate_recall_points_from_qa(...)` -> `GENERATE_CANDIDATE_RECALL_POINT`
- `accept_candidate_recall_point(...)` -> `ACCEPT_CANDIDATE_RECALL_POINT`
- `reject_candidate_recall_point(...)` -> `REJECT_CANDIDATE_RECALL_POINT`
- `create_memory_canvas(...)` -> `CREATE_MEMORY_CANVAS`
- `save_memory_canvas_version(...)` -> `SAVE_MEMORY_CANVAS_VERSION`
- `set_canvas_edges(...)` -> `SET_CANVAS_EDGES`
- `generate_story_artifact(...)` -> `GENERATE_STORY_ARTIFACT`

Payload 最小摘要建议（非强制；推荐）
- 学习提交：`items_count`、`entry_node_id`（若可得）
- 复习提交落库：`review_task_id`、`can_recall_len`、`result_range_id`（可空）
- 导入/建树：相关 ID、`source_kind` 与计数摘要
- LLM 问答：`qa_session_id`、`context_fragment_count`、`turn_count_delta`
- 候选点确认：`candidate_recall_point_id`、`decision`
- 画布/故事：`memory_canvas_id`、`version_no`、`source_ref_count`


---

<a id="toc-4-7"></a>

### 4.7 推荐 / 压缩感 / 漂移分析与记忆投影（Read-only Recommendation / Compression / Drift / Projection Views）

定位（强约束）
- 本模块提供一组**只读视图**：时间锚点、记忆弹幕、复习推荐、压缩感摘要、漂移预警、画布读取、故事读取。它们只能读取已提交事实或辅助对象，不得写入任何业务事实与调度状态。  
- 推荐判断允许依赖 `RecallPointReviewRecord`（1.12）、`CandidateRecallPoint`（1.11c）、`MemoryCanvas`（1.11d）等对象，但不得创建正式 `ReviewTask`，也不得绕过 4.1.3 的复习优先门禁。  
- 弹幕层是只读 projection：它只能投影既有事实，不得承载“会/不会”写协议，也不得成为 `can_recall` 的旁路入口。  

#### 4.7.1 只读视图返回形态（最小）

- `TimelineAnchor = {recall_point_id: RecallPointId, instance_id: InstanceId, center_ms: int, label: str}`
- `MemoryBarrageItem = {occurred_at_ms: int, source_kind: Enum{RECALL_POINT, CANDIDATE_RECALL_POINT, TEMP_CONTEXT_FRAGMENT, STORY_ARTIFACT}, source_id: str, text: str}`
- `ReviewRecommendation = {subject_kind: Enum{RECALL_POINT, CANDIDATE_RECALL_POINT, MEMORY_CANVAS, STORY_ARTIFACT}, subject_id: str, score: float, reasons: Tuple[str, ...], suggested_action: Enum{OPEN_REVIEW, ACCEPT_CANDIDATE, OPEN_CANVAS, READ_STORY}}`
- `RecallPointReviewRecommendation = {recall_point_id: RecallPointId, review_recommendation_index: float, estimated_memory_strength: float, weighted_success_ratio: float, last_reviewed_at: Optional[Timestamp], last_review_result: Optional[Enum{CAN_RECALL, CANNOT_RECALL}], review_count: int}`
- `RecallPointReviewProjection = {recall_point_id: RecallPointId, calculated_at: Timestamp, review_recommendation_index: float, estimated_memory_strength: float, weighted_success_ratio: float, forgetting_curve_decay_per_day: float, history_window_size: int, last_reviewed_at: Optional[Timestamp], last_review_result: Optional[Enum{CAN_RECALL, CANNOT_RECALL}], history: Sequence[(review_task_id: ReviewTaskId, occurred_at: Timestamp, result: Enum{CAN_RECALL, CANNOT_RECALL})]}`
- `CompressionSummary = {target_learning_task_node_id: Optional[LearningTaskNodeId], score: float, reasons: Tuple[str, ...], summary_text: Optional[str]}`
- `DriftAlert = {subject_kind: Enum{RECALL_POINT, LEARNING_TASK_NODE, MEMORY_CANVAS}, subject_id: str, severity: Enum{INFO, WARNING, CRITICAL}, reasons: Tuple[str, ...], suggested_action: Optional[str]}`

强约束：
- 以上返回形态均为只读值对象，不属于仓库存储对象。  
- `get_memory_barrage_at_time(...)` 的结果只允许由既有 `RecallPoint`、候选点、临时片段、故事化产物投影得到；不得为弹幕层引入独立写协议。  
- `RecallPointReviewRecommendation / RecallPointReviewProjection` 只允许投影既有 `RecallPoint` 与 `RecallPointReviewRecord`；不得创建 `ReviewTask`，不得新增 `RecallPointReviewRecord`，也不得把“查看推荐复习页/点击继续推荐”误记为正式复习。

#### 4.7.2 推荐启用门槛、遗忘曲线加权法与排序（强约束）

设：
- `N := |{rp ∈ RecallPointRepository.all(session) | rp.state == ACTIVE}|`（项目内 ACTIVE 复述点总数）
- `T := ProjectConfig.push_config.min_recall_points_to_enable`
- `H := ProjectConfig.push_config.max_history_len`
- `B := ProjectConfig.push_config.recommended_batch_size`
- `λ := ProjectConfig.push_config.forgetting_curve_decay_per_day`

强约束：
- 若 `N < T`：系统必须视为“推荐未启用”，`list_review_recommendations(...)` 必须返回空列表。  
- 若 `N >= T`：推荐启用；`state == DELETED` 的 `RecallPoint` 必须完全排除在候选集合、候选排序与指数计算之外。  
- `H >= 0`，`B >= 1`，`λ > 0`。若 `limit` 省略，则 `list_review_recommendations(...)` 必须使用 `B`。  

遗忘曲线加权法（最小版，强约束）
- 对任一候选 `recall_point_id`：
  - 进入计算路径前必须满足其 `RecallPoint.state == ACTIVE`。
  - 令 `R := RecallPointReviewRecordRepository.all_by_recall_point(session, recall_point_id)`，按 `occurred_at` 升序。
  - 若 `H > 0` 且 `|R| > H`，则仅保留 `R` 的末尾 `H` 条；若 `H == 0`，则视为 `R = []`。
  - 对任一 `record_i ∈ R`，令 `y_i := 1` 当且仅当 `record_i.result == CAN_RECALL`，否则 `y_i := 0`。
  - 令 `age_i_days := max(0, (calculated_at - record_i.occurred_at) / 1 day)`。
  - 令 `w_i := exp(-λ * age_i_days)`。
- 若 `R == []`：
  - `weighted_success_ratio := 0`
  - `estimated_memory_strength := 0`
  - `review_recommendation_index := 100`
- 否则：
  - `weighted_success_ratio := (Σ_i w_i * y_i) / (Σ_i w_i)`
  - `last_reviewed_at := R[-1].occurred_at`
  - `last_age_days := max(0, (calculated_at - last_reviewed_at) / 1 day)`
  - `freshness := exp(-λ * last_age_days)`
  - `estimated_memory_strength := max(0, min(1, weighted_success_ratio * freshness))`
  - `review_recommendation_index := 100 * (1 - estimated_memory_strength)`

排序与分页（强约束）
- `list_review_recommendations(...)` 必须按以下键排序后再分页：
  - 主键：`review_recommendation_index` 降序
  - 次键：`last_reviewed_at` 升序；`None` 视为早于任何实际时间
  - 末键：`id_canonical_text(recall_point_id)` 升序
- 返回分页必须按已排序全量序列执行 `offset/limit` 切片，并返回 `next_offset`（若无后续批次则为 `None`）。

#### 4.7.3 只读推荐复习页边界与失败语义（强约束）

- “推荐复习页/继续推荐”是**只读复习**：它只能展示 `RecallPoint` 内容、历史记录、曲线和推荐指数；不得创建 `ReviewTask`、不得触发 `executor_commit_review_task(...)`、不得写入任何 `RecallPointReviewRecord`。
- 用户在该页查看题面/答案、展开详情、切换批次，都不得被解释为“完成了一次正式复习任务”。
- `get_recall_point_review_projection(...)` 必须返回当前用于绘制曲线的 `calculated_at` 与 `forgetting_curve_decay_per_day`，以保证前端渲染与后端计算口径一致。
- 任一只读推荐接口失败不得产生任何持久化副作用；若目标 `RecallPoint` 不可解析则返回 `NotFound`，若分页超出尾部则返回空批次且 `next_offset = None`。

<a id="toc-4-8"></a>

### 4.8 节点作用域数据导出（RecallPoint / Legacy Browser-Cached ASR）

目的  
系统可以在 Hosted / Web / Native 形态下，通过服务端代理方式使用部署级或用户自有 API Key 调用外部 LLM 服务。Hosted / Web 形态下，允许把当前登录用户自己的 LLM 三元组（`base_url` / `model_name` / `api_key`）长期保存在服务端的账号级配置里，以支持跨设备复用；这些配置不得进入项目事实、标准导出或审计正文。播放器字幕与 LLM 补充上下文的现行产品路径应直接读取视频同目录同名字幕文件；节点详情页的标准服务端导出仍以 `RecallPoint` 为主。若用户需要读取历史 ASR 结果，则仅限 legacy 浏览器缓存或历史持久化 `AsrArtifact` 场景。

强约束（写死）  
- 导出能力必须是纯读取：不得创建/入队任何 ReviewTask，不得推进 ReviewChain，不得触发 Convergence，不得触发 Orchestrator Tick。  
- 标准导出能力不得隐式触发新的 ASR 请求；现行产品也不得为了导出字幕或 LLM 上下文自动回退到 ASR。  
- 浏览器 / Web 客户端不得绕过系统后端直接以持久 API Key 访问第三方 LLM 服务；若允许用户自带 key，密钥处理也必须被限制在受信任的服务端边界。允许将用户自带 key 以账号级配置形式长期保存在服务端，但服务端对外只可返回“是否已配置 / 掩码预览”，不得把完整密钥重新回传到浏览器。  
- 标准服务端导出结果必须只包含已提交事实；不得把临时上下文、提示词、模型响应、`QASession`、`TempContextFragment`、浏览器缓存 ASR 结果或 `StoryArtifact` 隐式混入。浏览器侧如需导出 ASR，必须明确标记其来源为当前浏览器缓存。  

4.8.1 导出数据形态（强约束）

- `RecallPointData`
  - 最小字段：`recall_point_id`、`question`、`answer`、`anchor`、`insights`
  - 语义：字段语义与 1.4 `RecallPoint` 保持一致；导出时不得重写内容、不得丢失顺序。
- `BrowserCachedAsrData`
  - 最小字段：`provider`、`recall_point_id`、`source_instance_id`、`center_ms`、`pre_ms`、`post_ms`、`segments`
  - 语义：字段语义与 1.11 `AsrTranscriptResult` 保持一致；其生成、缓存与导出由前端在当前浏览器内负责，不构成项目事实。

4.8.2 导出接口语义（强约束）

总原则（强约束）
- 本节导出接口属于“当前内容视图”；除非未来新增单独的历史导出接口，否则 `state == DELETED` 的 RecallPoint 不得出现在任何导出结果中。

- `export_recall_points_by_learning_object_node(...)`
  - 输入作用域：由 `LearningObjectNodeRepository.covered_instance_id_sequence(...)` 定义。
  - 返回集合：所有满足 `anchor.instance_id` 落在该节点覆盖实例集合中且 `state == ACTIVE` 的 `RecallPoint`。
  - 返回顺序：按 `recall_point_id` 升序。
- `export_recall_points_by_learning_task_node(...)`
  - 输入作用域：由 `LearningTaskNodeRepository.covered_rp_ids(...)` 定义。
  - 返回集合：该节点覆盖的全部 ACTIVE `RecallPoint`。
  - 返回顺序：必须与 `covered_rp_ids(...)` 的顺序一致。
- `export_asr_by_learning_object_node(...)`
  - 兼容说明：该接口仅服务于历史版本中已持久化的 `AsrArtifact` 只读导出；在现行浏览器缓存策略下，新生成的 ASR 结果不会进入该接口。
  - 返回顺序：若实现保留该兼容接口，则先按 `recall_point_id` 升序，再按 `(provider, center_ms, pre_ms, post_ms, asr_artifact_id)` 升序。
- `export_asr_by_learning_task_node(...)`
  - 兼容说明：该接口仅服务于历史版本中已持久化的 `AsrArtifact` 只读导出；在现行浏览器缓存策略下，新生成的 ASR 结果不会进入该接口。
  - 返回顺序：若实现保留该兼容接口，则先按该节点覆盖的 `recall_point_id` 顺序，再按 `(provider, center_ms, pre_ms, post_ms, asr_artifact_id)` 升序。

4.8.3 失败与空结果语义（强约束）

- 若目标节点不可解析，必须返回 `NotFound`。  
- 若目标节点覆盖范围内当前没有任何复述点，则复述点导出必须返回空序列，不得报错。  
- 若目标节点覆盖范围内当前没有任何历史 ASR 产物，则兼容性 ASR 导出必须返回空序列，不得报错。  
- 导出接口不得因为某个外部服务未配置而失败；导出只读取既有已提交数据。  


<a id="toc-4-9"></a>

### 4.9 ASR（Whisper）集成：legacy 服务端代理、浏览器缓存的复述点附近范围转写

目的  
将 ASR（Whisper）转写能力保留在当前系统的兼容层，以“围绕复述点的附近窗口”为单位生成临时可引用的转写片段，用于旧接口、调试或历史兼容场景。现行产品的播放器字幕与 LLM 补充上下文不得再依赖本节能力，而应直接读取视频同目录同名字幕文件。ASR 结果不进入项目级持久化存储；ASR 配置可来自部署级环境变量、当前登录用户保存在服务端的账号级配置，或用户在浏览器里显式输入并随请求提交的临时服务配置。

强约束（写死）
- ASR 只对“可提取音频”的材料有效；材料类型判定与音频提取属于实现内部，但失败必须明确返回且不产生写入（0b.5）。  
- ASR 结果为派生信息，不得进入系统级提交期强制集合（0b.7.2）。  
- 系统不得把新 ASR 结果写入项目仓库、SQLite/Postgres 或标准导出持久层。  
- ASR 服务配置不得从 `ProjectConfig` 读取或推断；只能来自部署级环境变量、当前登录用户保存在服务端的账号级配置，或当前用户本次请求显式给定的临时配置。  
- 浏览器缓存是当前策略下唯一允许的新结果复用层；服务端 / Web 端不得把新 ASR 结果沉淀为新的 `AsrArtifact`。  
- 现行产品前端不得再使用 `ffmpeg.wasm` 为字幕或 LLM 默认路径裁剪媒体。  
- 现行产品服务端不得再使用 `ffmpeg` 作为字幕或 LLM 默认路径的媒体切片能力；若为了兼容接口仍保留，则必须明确视为 legacy 分支。  

窗口定义（强约束；写死）  
- 默认窗口：`pre_ms = 30_000`，`post_ms = 30_000`（±30s）；实现可允许配置，但必须对外可预测且稳定。  
- 若 `RecallPoint.anchor` 无时间语义（无法获得 `center_ms`），则必须拒绝自动窗口 ASR（`PreconditionFailure`），并要求用户手动提供或先补齐 anchor。  

与节点导出的结合方式（强约束）  
- 节点详情页若需要把 ASR 结果交给用户，必须由前端基于当前浏览器缓存显式导出；不得把外部模型响应或临时摘要写回系统。  
- 现行产品若需要字幕或问答补充证据，应优先读取同目录同名字幕文件，而不是先调用本节 ASR。  
