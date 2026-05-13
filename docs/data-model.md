# 数据模型

更新时间：2026-05-13

本文记录当前持久化边界、主要数据集合和迁移规则。接口字段以运行时 OpenAPI 为准，本文不维护 API 明细。

## 持久化边界

当前后端有三类主要持久化边界：

- core store：项目、学习对象、复述点、学习任务、复习链、层、聚合、媒体、审计等核心学习数据。
- auth store：用户、session、角色、项目访问、好友、用户设置、云账号、每日学习统计等认证和用户数据。
- membership store：会员订单、支付、权益、邀请、优惠券、佣金、提现、对账等商业数据。

core store 支持 SQLite 和 PostgreSQL。auth store 支持 SQLite 和 PostgreSQL。membership store 当前由独立 SQLite 文件初始化和维护。

客户端浏览器也会保存少量本地偏好，不进入后端 store。番茄钟壁纸保存在 IndexedDB
`learningpyramid-pomodoro-wallpaper` 的 `wallpaper` object store 中；启用账号系统时按 `user_id`
使用账号级 key，未启用账号系统时使用浏览器本地 key。登录账号不得读取浏览器旧的全局壁纸 key。

## SQLite 与 PostgreSQL

运行时通过 `LEARNINGPYRAMID_SQL_BACKEND` 选择 core/auth 的 SQL 后端：

- `sqlite`：本地优先和简单单机路径。
- `postgres`：当前推荐的自托管生产路径。

PostgreSQL schema 由 `backend/system/postgres_schema.py` 中的 `POSTGRES_MIGRATIONS` 定义，并通过 `schema_migrations` 按 `store` 与 `auth` 两个 scope 记录版本。store migration 10 会在 subject-material backfill 前把 `subject_material_collection_index.initialized` 规范成 BOOLEAN；store migration 11 会补齐 `project_snapshots.snapshot_json` 非空壳列，保持 repository 写入合约；store migration 12 会对已应用早期 relationship migration 的数据库再次幂等规范 `initialized` 为 BOOLEAN。

SQLite core schema 由 `backend/system/persistence_store.py` 初始化。PostgreSQL 初始 schema 从 SQLite schema 渲染，再叠加显式迁移。

## Core Store 表组

core store 的主要表包括：

- `system_state`：全局 schema 版本和 id 计数器。
- `global_settings_index`：部署级全局设置。
- `project_snapshots`：项目快照、状态、scoped identity。`project_id` 是内部存储身份；`subject_id` 与 `scoped_project_id` 只描述材料项目的学科归属和学科内编号。
- `subject_material_collection_index`：学科材料集合初始化状态；PostgreSQL 中 `initialized` 是 BOOLEAN。
- `subject_material_relationship_index`：学科材料关系，连接 `subject_id`、`scoped_project_id` 与内部 `internal_project_id`。
- `project_storage_config_index`：项目存储根和文件同步策略。
- `project_material_source_binding_index`：项目材料来源绑定。
- `project_config_index`：项目配置 JSON。
- `instance_index`：项目内材料实例。
- `instance_media_binding_index`：实例媒体绑定。
- `learning_object_node_index`：学习对象树。
- `recall_point_index`：复述点索引和完整 payload。
- `learning_task_index`：学习任务。
- `learning_task_node_index`：学习任务树。
- `entry_registration_index`：入口节点到层和复习链的登记。
- `range_snapshot_index`：复述点范围快照。
- `review_task_index`：复习任务。
- `convergence_index`：收敛/递推复习生成器。
- `review_chain_index`：复习链。
- `review_task_queue_index`：项目级复习任务队列。
- `layer_state_index`：分层聚合状态。
- `audit_log_event_index`：项目审计事件。
- `asr_artifact_index`：ASR 片段和产物。
- `aggregation_queue_index`：聚合队列。
- `aggregation_event_index`：聚合事件。
- `material_allowlist_index`：项目材料 allowlist。
- `media_asset_index`：项目媒体资产。
- `recall_point_review_record_index`：复述点复习记录。

`project_snapshots.snapshot_json` 仍是兼容/导出壳，不是新功能的数据写入模式。PostgreSQL 生产 schema 仍要求该列非空；normalized repository 写入时只维护最小稳定壳 `{}`，不从该列恢复新业务语义。

## Auth Store 表组

auth store 的主要表包括：

- `users`：登录用户。
- `sessions`：session token 哈希与过期时间。
- `password_reset_tokens`：密码重置 token。
- `email_verification_tokens`：邮箱验证 token。
- `project_memberships`：用户与项目访问关系。
- `user_profiles`：公开 UID、昵称、简介、头像和用户状态。
- `user_service_configs`：用户级 LLM / ASR 等服务配置。
- `user_global_settings`：用户主题、番茄钟、默认复习模板、学习计划等。
- `user_cloud_accounts`：用户云账号绑定。
- `user_global_roles`：`super_admin` / `admin` 全局角色。
- `friend_requests` 与 `friendships`：好友关系。
- `admin_action_logs`：管理员动作日志。
- `user_project_daily_study_stats`：用户项目每日学习统计。

auth migration 3 到 5 曾引入 study group 相关表，当前迁移历史保留这些版本，并由后续迁移移除废弃表。

## Membership Store 表组

会员数据使用会员 store 初始化，主要表包括：

- `membership_orders`：会员订单，状态包括 `pending`、`paid`、`closed`、`expired`、`refund_pending`、`refunded`。
- `membership_payments`：支付记录，状态包括 `initiated`、`succeeded`、`refund_pending`、`refunded`、`failed`。
- `membership_entitlements`：会员权益，状态包括 `active`、`expired`、`revoked`。
- `invite_bindings`：邀请绑定和奖励进度。
- `coupons`：优惠券。
- `invite_reward_records`：邀请奖励记录。
- `commission_records`：邀请佣金。
- `commission_withdrawal_requests`：佣金提现请求。
- `payout_identities`：提现收款身份。
- `payout_binding_attempts`：微信提现确认扫码 attempt；表名沿用早期 binding 命名，但产品入口不再支持单独绑定微信。
- `payout_provider_events`：支付 provider 事件。
- `reconciliation_runs`：对账运行记录。
- `reconciliation_warnings`：对账告警。

会员、佣金和提现的状态流转维护在 `docs/state-machines.md`。

## 数据完整性规则

- project 级数据必须带 `project_id`。
- 学科材料工作台由 `{subjectId, scopedProjectId}` 定位；scoped public id 不能直接当内部 project id 使用。
- 学科材料关系必须通过 `subject_material_relationship_index` 持久化，并指向 active subject 与 active internal project。
- 可恢复历史材料关系只从 active material project 的 `subject_id`、`scoped_project_id`、`project_config_index.config_json.projectType` 和内部 `project_id` 确定性恢复；恢复生成的 `material_id` 使用 `mat_recovered_{internalProjectId}`。
- 缺失 subject、缺失 internal project、已删除 subject、已删除 internal project 或缺失/不支持材料 `projectType` 都是数据完整性问题，不能在请求期猜测绑定。
- core store 中多数 project 子表通过 `project_id` 外键关联 `project_snapshots`。
- active project 必须同时具备 `project_storage_config_index`、`project_material_source_binding_index` 和 `project_config_index` 行；缺失时运行时应视为数据一致性错误，而不是从 `project_snapshots.snapshot_json` 恢复业务语义。
- 学习对象树和学习任务树的结构一致性由提交期逻辑保证。
- 会员金额字段以 cent 为单位。
- 日期时间字段在后端以 ISO 字符串或毫秒时间戳持久化，具体列语义以对应 store 初始化代码为准。

## 迁移与导出

PostgreSQL 迁移入口：

```powershell
python tools/apply_postgres_migrations.py --postgres-dsn postgresql://user:pass@localhost:5432/learningpyramid
```

迁移状态检查：

```powershell
python tools/apply_postgres_migrations.py --postgres-dsn postgresql://user:pass@localhost:5432/learningpyramid --check
```

SQLite 到 PostgreSQL 导出或迁移：

```powershell
python tools/export_sqlite_to_postgres.py --output learningpyramid-postgres.sql
python tools/migrate_sqlite_to_postgres.py --postgres-dsn postgresql://user:pass@localhost:5432/learningpyramid
```

运行时备份和恢复记录在 `docs/deployment.md`。

## 数据修复入口

`tools/repair_project_material_source_binding_index.py` 用于修复已迁移 PostgreSQL 中 active project 缺失 `project_material_source_binding_index` 的数据一致性问题。

- 默认 dry-run，只输出计划。
- 显式传入 `--apply` 才会写入缺失行。
- `sourceKind` 只从当前 normalized `project_config_index.config_json.projectType` 推导：
  - `COURSE` -> `SERVER_FS`
  - `BOOK` -> `MANUAL`
  - `LOOSE_POINTS` -> `MANUAL`
- 遇到 active project 缺失 `project_config_index` 或未知 `projectType` 时必须阻断。
- 生产执行前必须先备份目标 PostgreSQL。

`tools/repair_subject_material_relationship_index.py` 用于检查和修复 PostgreSQL 中缺失的学科材料关系。

- 默认 dry-run，只输出可恢复计划和完整性问题。
- 显式传入 `--apply` 才会写入 `subject_material_collection_index` 和 `subject_material_relationship_index`。
- 只恢复同时满足 active subject、active material project、存在 `subject_id`、存在 `scoped_project_id` 且 `projectType` 为 `COURSE`、`BOOK` 或 `LOOSE_POINTS` 的记录。
- 不从学科内编号反查内部项目；内部项目身份只来自 material project 行的 `project_id`。
- 生产执行前必须先备份目标 PostgreSQL。

## 维护约束

- 新表或新迁移必须同步更新本文。
- 新 PostgreSQL 迁移版本必须按 scope 连续递增。
- 不允许通过未记录的兼容字段承载新业务语义。
- 不允许为了迁移方便跳过 schema 校验或把失败包装成成功。
