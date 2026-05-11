# 状态机

更新时间：2026-05-10

本文记录当前代码中可验证的状态集合和主要流转语义。接口字段以运行时 OpenAPI 为准，本文不维护 API 明细。

## Project

状态：

- `ACTIVE`
- `DELETED`

语义：

- 新建项目为 `ACTIVE`。
- 删除项目进入 `DELETED`，并记录删除时间。
- 新功能不应把 `DELETED` 项目当作可写项目。

## RecallPoint

状态：

- `ACTIVE`
- `DELETED`

语义：

- 新写入复述点必须是 `ACTIVE`。
- 写入时 `deleted_at` 必须为空。
- 删除通过后端行为标记，不应通过普通写入构造 `DELETED` 复述点。

## ReviewTask

状态：

- `PENDING`
- `DONE`

语义：

- `PENDING`：`executed_at` 必须为空，`result_range_id` 必须为空。
- `DONE`：`executed_at` 必须存在。
- runtime 接口要求只有 `PENDING` 可写入 `DONE`。
- 已经是 `DONE` 的任务再次提交应幂等成功，不得改写已有执行字段。

## Convergence

状态：

- `IN_PROGRESS`
- `TERMINATED`

语义：

- `IN_PROGRESS` 表示轮次递推仍可继续生成复习任务。
- `TERMINATED` 表示递推已结束。
- `round_count` 由已生成的 `review_task_ids` 数量派生。

## ReviewChain

状态：

- `IN_PROGRESS`
- `TERMINATED`

语义：

- `queue` 由 `CONVERGENCE` 和 `REVIEW_TASK` 两类 item 组成。
- `head_index` 必须在 `0..len(queue)` 范围内。
- `head_index == len(queue)` 表示队首为空。
- `TERMINATED` 表示复习链不再推进。

## Layer Aggregation Cycle

状态：

- `CLEARING`
- `ROLL_UP`
- `DONE`

语义：

- `Layer` 持久化 `aggregation_cycle_state`、`pending_roll_up_parent_node_id` 和 `normal_tick_quota_remaining`。
- `normal_tick_quota_remaining` 只能是 `0` 或 `1`。
- `orchestrator_managed_review_chain_ids` 必须去重，并按 canonical id 升序保存。
- 聚合状态和队列推进由后端行为层维护，router 不应直接拼装状态流转。

## CandidateRecallPoint

状态：

- `PENDING`
- `ACCEPTED`
- `REJECTED`

语义：

- 候选复述点来自生成流程。
- 接受后应转化为正式复述点。
- 拒绝后不应继续参与正式复习任务。

## Auth User

状态：

- `active`
- `suspended`
- `deleted`

语义：

- `active` 是正常用户状态。
- `suspended` 和 `deleted` 表示管理侧限制或删除语义。
- 状态修改由 auth store 统一处理。

## Friend Request

状态：

- `pending`
- `accepted`
- `rejected`
- `cancelled`

语义：

- 新请求为 `pending`。
- 接收方可接受或拒绝。
- 发起方可取消。
- 好友关系落在 `friendships`，不等同于项目访问权限。

## Membership Order

状态：

- `pending`
- `paid`
- `closed`
- `expired`
- `refund_pending`
- `refunded`

语义：

- 新订单为 `pending`，有过期时间。
- 支付确认后进入 `paid`，并生成或更新会员权益。
- 用户或系统关闭未支付订单进入 `closed`。
- 超时未支付订单进入 `expired`。
- 已支付订单发起远端退款后进入 `refund_pending`。
- 退款完成后进入 `refunded`，并重建会员权益、恢复/撤销相关优惠和佣金影响。

## Membership Payment

状态：

- `initiated`
- `succeeded`
- `refund_pending`
- `refunded`
- `failed`

语义：

- 支付 provider 创建或回调后写入支付记录。
- `succeeded` 表示支付确认成功。
- `refund_pending` 表示退款已请求但未最终完成。
- `refunded` 表示退款完成。
- `failed` 表示远端支付或退款相关失败。

## Membership Entitlement

状态：

- `active`
- `expired`
- `revoked`

语义：

- `active` 表示当前权益有效。
- 到期后同步为 `expired`。
- 退款或管理撤销后进入 `revoked`。
- 会员摘要根据权益时间窗和状态计算。

## Invite, Coupon, Reward

邀请绑定状态：

- `bound`
- `discount_issued`
- `commission_pending`
- `commission_settled`
- `rewarded`

优惠券状态：

- `available`
- `used`
- `revoked`
- `expired`

奖励记录状态：

- `issued`
- `revoked`

语义：

- 邀请绑定描述邀请人与被邀请人的长期关系。
- 优惠券使用、过期、撤销会影响会员订单价格和退款恢复。
- 退款可能回滚邀请奖励或佣金状态。

## Commission And Withdrawal

佣金状态：

- `pending`
- `settled`
- `canceled`
- `reversed`

提现状态：

- `created`
- `awaiting_confirmation`
- `processing`
- `succeeded`
- `failed`
- `canceled`
- `needs_attention`

提现身份绑定状态：

- `created`
- `scanned`
- `authorized`
- `confirmed`
- `bound`
- `failed`
- `canceled`
- `expired`

收款身份状态：

- `active`
- `replaced`

语义：

- 佣金先进入 `pending`，退款窗口结束后才可结算为 `settled`。
- 退款窗口内退款会把相关佣金取消。
- 提现先创建并预留金额，再根据支付 provider 状态进入确认、处理中或终态。
- provider 金额、appid 等不一致时进入 `needs_attention` 并生成对账告警。
- 收款身份重新绑定会替换旧身份。

## Reconciliation Warning

状态：

- `open`
- `resolved`

语义：

- 对账发现需要人工确认的问题时创建 `open` 告警。
- 管理端确认处理后进入 `resolved`。

## 维护约束

- 新状态必须同步更新本文和对应数据模型文档。
- 新状态流转应集中在 system store/service，不应散落在 router 或前端。
- 已终态数据不应被静默改写，除非当前 store 明确提供幂等语义。
- 退款、提现、对账相关状态不得通过前端状态推断替代服务端事实。
