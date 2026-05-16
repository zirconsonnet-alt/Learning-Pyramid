# 领域模型

更新时间：2026-05-13

本文记录当前仓库中可验证的长期业务概念。接口字段以运行时 OpenAPI 为准，本文不维护 API 明细。

## 项目与作用域

`Project` 是学习数据的最高业务容器：

- `project_id` 是后端内部主键。
- `subject_id` 与 `scoped_project_id` 成对出现，用于公开路由中的 subject / project 作用域。
- `public_project_id` 优先返回 `scoped_project_id`，没有 scoped identity 时返回内部 `project_id`。
- `state` 当前为 `ACTIVE` 或 `DELETED`。

scoped project 的公开身份解析属于 adapter 边界：公开 `{subjectId, scopedProjectId}` 必须通过 `adapter/scoped_projects.py` 解析为内部 project id。

## 材料与媒体

学习材料围绕项目组织：

- `StudyMaterial` 表示用户导入或绑定的学习材料。
- `Instance` 表示材料在项目内可学习、可播放、可定位的实例。
- `ProjectMaterialSourceBinding` 记录项目材料来源。
- `InstanceMediaBinding` 记录实例级媒体绑定，支持本地文件、浏览器本地、原生本地、手工、百度网盘等来源。
- `MediaAsset` 记录项目内生成或上传的媒体资产。

视频字幕与 AI 文本上下文优先使用视频同目录同名字幕文件；自动转写不是当前主路径。工作台视频助手可以额外把当前复述点内容和当前视频帧作为项目 LLM ask 上下文；如果模型服务不支持图片输入，课程助手会明确提示本轮未使用视频帧，并继续使用字幕、复述点和时间文本上下文回答。桌宠现在通过“复制文本”和“复制图片”两个动作复用同一套课程上下文选择逻辑：文本复制会整理任务说明、用户问题、复述点、字幕片段、播放位置和当前帧信息；图片复制会把当前帧直接放进剪贴板。两个动作都不调用 LLM。

## 学习对象树

学习对象树表达“要学什么”：

- `LearningObjectContainer` 是目录或分组节点。
- `LearningObjectLeaf` 是叶子节点，并绑定一个 `instance_id`。
- 节点 `source` 当前为 `FILESYSTEM` 或 `MANUAL`。
- 节点路径必须是相对路径，不能是绝对路径，不能包含 `..`。
- 容器子节点允许为空；双向一致、无环、同质等结构校验由提交期逻辑保证。

## 复述点

`RecallPoint` 是复习和任务生成的核心知识单元：

- `question` 和 `answer` 使用富文本。
- `anchor` 可指向一个 `Instance` 的位置。
- `references` 可以引用其它复述点，但不能引用自身，不能重复。
- `insights` 记录追加理解。
- 当前写入语义要求新写入复述点为 `ACTIVE`，删除通过删除行为表达。

`RecallPointReviewRecord` 记录一次复述点复习结果，当前结果包括 `CAN_RECALL` 和 `CANNOT_RECALL`。

## 学习任务树

学习任务表达“怎么复习一组复述点”：

- `LearningTask` 绑定非空、有序的 `recall_point_ids`。
- `LearningTaskLeaf` 绑定一个 `LearningTask`。
- `LearningTaskContainer` 聚合学习任务节点，当前 `node_origin` 为 `AGGREGATION`。
- 学习任务树可以由聚合逻辑生成，也可以被页面作为结构化任务入口使用。

## 复习链与聚合

复习执行由几个模型协作：

- `RangeSnapshot` 保存一组复述点的稳定快照。
- `ReviewTask` 是可执行的最小复习任务。
- `Convergence` 是轮次递推生成器，用于持续生成 `ReviewTask`。
- `ReviewChain` 是由 `Convergence` 与 `ReviewTask` 混合组成的队列，并通过 `head_index` 表示当前位置。
- `ReviewTaskQueue` 是项目级待执行复习任务队列。
- `EntryRegistration` 把学习任务节点登记到指定层。
- `Layer` 记录分层聚合配置、聚合状态和其管理的复习链。
- `AggregationQueue` 与 `AggregationEvent` 记录聚合队列和聚合事件。

聚合、复习链推进和任务提交属于后端行为层职责，不应在 router 或前端复制业务规则。

新建项目默认第 0 层配置使用 `REVIEW_TASK -> CONVERGENCE` 复习链模板，默认上推策略为 `LEARNING_OBJECT_ISOMORPHIC`。该默认只描述新配置入口；已有项目的已保存配置不应被静默改写。

## 认证、用户与会员

认证域包含：

- `AuthUser`、用户档案、session、密码重置、邮箱验证。
- 全局角色：`super_admin`、`admin`。
- 项目 membership：当前用于记录用户对项目的 owner 访问关系。
- 好友关系和好友请求。
- 用户级服务配置、全局设置、云账号绑定、每日学习统计。

会员域包含：

- 会员订单、支付记录、会员权益。
- 邀请绑定、优惠券、邀请奖励记录。
- 邀请佣金、提现身份、提现请求、支付 provider 事件、对账运行和对账告警。

会员权益可以作为功能门禁；权限细节维护在 `docs/auth-and-permissions.md`。

## 审计与运行能力

`AuditLogEvent` 记录项目内行为事件。事件种类包括项目、学习对象、复述点、学习任务、复习、聚合、ASR、LLM、候选复述点、记忆画布和故事生成等。

运行能力由 runtime feature 和 client capability 表达，例如视频播放、轻量复习、原生文件绑定、本地 ASR、本地 LLM、本地推荐、记忆画布和故事生成。

## 维护约束

- 新长期业务概念应优先落在 `backend/models/` 或明确的 system store/service 中。
- 新行为不应把领域规则写散到 router、前端 query 或页面组件里。
- 新 scoped project 行为必须区分公开 project id 和内部 project id。
- 文档只记录已存在且可验证的长期语义，不写未确认的产品计划。
