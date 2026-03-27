# 会员、邀请码、优惠券落地方案

## 0. 当前实现状态（2026-03-26）

这份文档最初是落地方案，现在项目里对应功能已经基本实现完成。下面先给出“当前代码实际状态”，后面的章节保留原始设计与规划说明；如果两边有冲突，以这一节和 [membership-selfhost-launch-checklist.md](/i:/Projects/LearningPyramid/docs/membership-selfhost-launch-checklist.md) 为准。

当前已经落地：

- 第 1 到第 5 轮会员功能都已完成
- 已支持 `manual_test` 和 `wechat_native`
- 已支持微信支付异步通知与退款通知
- 已支持用户侧手动同步支付状态
- 已支持用户侧关闭待支付订单
- 已支持后台查看订单详情、同步支付、关闭待支付订单、退款回滚
- 已支持远端 `closed / failed` 终态回写本地订单，不再长期停留在 `pending`
- 已提供待支付微信订单巡检脚本：`python tools/reconcile_membership_payments.py`

当前代码里相较于原始方案多出来的关键字段：

- `membership_orders` 实际还包含 `provider_trade_no`、`closed_at`、`refunded_at`、`remark`
- `membership_payments` 实际还包含 `refund_out_refund_no`、`refund_requested_at`、`refund_callback_payload_json`

当前代码里相较于原始方案多出来的关键接口：

- `POST /api/membership/orders/{orderId}/sync-payment`
- `POST /api/membership/orders/{orderId}/close`
- `POST /api/payments/wechat/notify`
- `POST /api/payments/wechat/refund-notify`
- `GET /api/admin/membership/orders/{orderId}`
- `POST /api/admin/membership/orders/{orderId}/sync-payment`
- `POST /api/admin/membership/orders/{orderId}/close`

## 1. 范围与业务规则

这版按你当前确认的规则落地：

- 月会员标准价：`19.9 元`
- 新用户首个成功会员订单：`14.9 元`
- 用户有 `5 元券` 时，可用于首单，也可用于续费
- 每笔订单最多使用 `1 张券`
- 邀请成功定义：被邀请人完成自己的首个成功会员订单
- 邀请奖励：邀请人获得 `1 张 5 元券`
- 每个被邀请人只能绑定 `1` 个邀请人，只能触发 `1` 次邀请奖励
- 邀请码第一版直接复用现有 `user_profiles.public_uid`
- 退款时需要撤销该首单触发的邀请奖励；若奖励券已使用，记为冻结或负账状态

建议补充的固定规则：

- 金额统一使用“分”为单位存储，避免浮点误差
- 会员时长第一版按 `30 天` 发放，前端文案仍显示“月会员”
- 优惠券有效期建议 `30 天`
- 订单成功、发会员、发邀请券都必须做幂等

当前价格换算：

- `1990` 分：标准月会员
- `1490` 分：首单优惠价
- `500` 分：邀请奖励券金额

## 2. 接入现有项目的推荐位置

后端建议新增独立模块，不要继续把会员逻辑直接堆进 [backend/system/auth_store.py](/i:/Projects/LearningPyramid/backend/system/auth_store.py)。

推荐新增：

- `backend/system/membership_store.py`
- `adapter/routers/membership.py`
- `frontend/src/ui/api/membership.ts`
- `frontend/src/ui/queries/membership.ts`
- `frontend/src/views/membership/MembershipPage.tsx`
- `frontend/src/views/admin/AdminMembershipPage.tsx`

现有代码里这些位置可以直接复用：

- 邀请码复用用户 UID： [backend/system/auth_store.py](/i:/Projects/LearningPyramid/backend/system/auth_store.py#L733)
- 注册登录入口： [adapter/routers/auth.py](/i:/Projects/LearningPyramid/adapter/routers/auth.py#L32)
- 个人页入口： [frontend/src/views/profile/ProfilePage.tsx](/i:/Projects/LearningPyramid/frontend/src/views/profile/ProfilePage.tsx#L175)
- 后台总览： [adapter/routers/admin.py](/i:/Projects/LearningPyramid/adapter/routers/admin.py#L203)
- 前端路由： [frontend/src/router.tsx](/i:/Projects/LearningPyramid/frontend/src/router.tsx#L40)

## 3. 数据库表设计

如果你沿用当前 `auth_store` 风格，SQLite 可以继续用 `TEXT` 存 ISO8601 时间；如果走 PostgreSQL 迁移，下面所有时间列都可替换成 `TIMESTAMPTZ`。

### 3.1 邀请绑定表 `invite_bindings`

用途：记录“谁邀请了谁”，一个被邀请人只能有一条有效绑定。

```sql
CREATE TABLE IF NOT EXISTS invite_bindings (
    invitee_user_id TEXT PRIMARY KEY,
    inviter_user_id TEXT NOT NULL,
    invite_code_snapshot TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'register',
    status TEXT NOT NULL DEFAULT 'active',
    bound_at TEXT NOT NULL,
    locked_at TEXT,
    invalidated_at TEXT,
    invalid_reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(invitee_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY(inviter_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CHECK (invitee_user_id <> inviter_user_id),
    CHECK (status IN ('active', 'locked', 'invalid'))
);

CREATE INDEX IF NOT EXISTS idx_invite_bindings_inviter
ON invite_bindings (inviter_user_id, bound_at DESC);
```

字段说明：

- `invitee_user_id`：被邀请人，主键保证只能绑一次
- `inviter_user_id`：邀请人
- `invite_code_snapshot`：绑定时的邀请码快照，避免后续 UID 规则变更影响追溯
- `source`：`register` / `manual_bind`
- `status`：`active` 绑定中，`locked` 已首单锁定，`invalid` 无效

### 3.2 优惠券表 `coupons`

用途：承载邀请奖励券，也为后续活动券预留统一结构。

```sql
CREATE TABLE IF NOT EXISTS coupons (
    coupon_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    coupon_type TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_ref_id TEXT,
    title TEXT NOT NULL,
    amount_cent INTEGER NOT NULL,
    threshold_cent INTEGER NOT NULL DEFAULT 0,
    applicable_scope TEXT NOT NULL DEFAULT 'membership_order',
    first_order_only INTEGER NOT NULL DEFAULT 0,
    new_user_only INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    used_order_id TEXT,
    voided_at TEXT,
    void_reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CHECK (amount_cent > 0),
    CHECK (threshold_cent >= 0),
    CHECK (status IN ('available', 'reserved', 'used', 'void'))
);

CREATE INDEX IF NOT EXISTS idx_coupons_user_status
ON coupons (user_id, status, expires_at ASC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_coupons_used_order
ON coupons (used_order_id)
WHERE used_order_id IS NOT NULL;
```

首版邀请奖励券建议固定写入：

- `coupon_type = 'cash'`
- `source_type = 'invite_reward'`
- `title = '邀请奖励 5 元券'`
- `amount_cent = 500`
- `threshold_cent = 0`
- `applicable_scope = 'membership_order'`
- `first_order_only = 0`
- `new_user_only = 0`
- `expires_at = issued_at + 30 天`

### 3.3 会员订单表 `membership_orders`

用途：承载下单、价格快照、优惠信息、支付状态。

```sql
CREATE TABLE IF NOT EXISTS membership_orders (
    order_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    order_type TEXT NOT NULL,
    pricing_version TEXT NOT NULL,
    period_days INTEGER NOT NULL,
    list_amount_cent INTEGER NOT NULL,
    first_order_discount_cent INTEGER NOT NULL DEFAULT 0,
    coupon_discount_cent INTEGER NOT NULL DEFAULT 0,
    payable_amount_cent INTEGER NOT NULL,
    coupon_id TEXT,
    currency TEXT NOT NULL DEFAULT 'CNY',
    status TEXT NOT NULL,
    provider TEXT,
    provider_trade_no TEXT,
    client_ip TEXT NOT NULL DEFAULT '',
    client_version TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    paid_at TEXT,
    closed_at TEXT,
    expired_at TEXT,
    refunded_at TEXT,
    refund_amount_cent INTEGER NOT NULL DEFAULT 0,
    entitlement_id TEXT,
    remark TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY(coupon_id) REFERENCES coupons(coupon_id) ON DELETE SET NULL,
    CHECK (order_type IN ('first_purchase', 'renewal')),
    CHECK (period_days > 0),
    CHECK (list_amount_cent >= 0),
    CHECK (first_order_discount_cent >= 0),
    CHECK (coupon_discount_cent >= 0),
    CHECK (payable_amount_cent >= 0),
    CHECK (refund_amount_cent >= 0),
    CHECK (status IN ('pending', 'paid', 'closed', 'expired', 'refund_pending', 'refunded'))
);

CREATE INDEX IF NOT EXISTS idx_membership_orders_user_created
ON membership_orders (user_id, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_membership_orders_provider_trade_no
ON membership_orders (provider, provider_trade_no)
WHERE provider_trade_no IS NOT NULL;
```

价格计算规则：

- `list_amount_cent = 1990`
- 若用户没有成功会员订单，则 `first_order_discount_cent = 500`
- 若本单使用 5 元券，则 `coupon_discount_cent = 500`
- `payable_amount_cent = list_amount_cent - first_order_discount_cent - coupon_discount_cent`

首单支付场景的结果：

- 无券：`1990 - 500 = 1490`
- 有券：`1990 - 500 - 500 = 990`

### 3.4 支付流水表 `membership_payments`

用途：承载三方支付流水和回调幂等。

```sql
CREATE TABLE IF NOT EXISTS membership_payments (
    payment_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_trade_no TEXT NOT NULL,
    provider_buyer_id TEXT NOT NULL DEFAULT '',
    amount_cent INTEGER NOT NULL,
    status TEXT NOT NULL,
    callback_payload_json TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    confirmed_at TEXT,
    refunded_at TEXT,
    FOREIGN KEY(order_id) REFERENCES membership_orders(order_id) ON DELETE CASCADE,
    CHECK (amount_cent >= 0),
    CHECK (status IN ('initiated', 'succeeded', 'refund_pending', 'refunded', 'failed'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_membership_payments_trade_no
ON membership_payments (provider, provider_trade_no);

CREATE INDEX IF NOT EXISTS idx_membership_payments_order
ON membership_payments (order_id, created_at DESC);
```

### 3.5 会员权益发放表 `membership_entitlements`

用途：每个成功订单对应一条权益发放记录，支持续费顺延和退款回滚。

```sql
CREATE TABLE IF NOT EXISTS membership_entitlements (
    entitlement_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    source_order_id TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    granted_days INTEGER NOT NULL,
    status TEXT NOT NULL,
    granted_at TEXT NOT NULL,
    revoked_at TEXT,
    revoke_reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY(source_order_id) REFERENCES membership_orders(order_id) ON DELETE CASCADE,
    CHECK (granted_days > 0),
    CHECK (status IN ('active', 'expired', 'revoked'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_membership_entitlements_source_order
ON membership_entitlements (source_order_id);

CREATE INDEX IF NOT EXISTS idx_membership_entitlements_user_end
ON membership_entitlements (user_id, end_at DESC);
```

发放规则：

- 用户无有效会员时：`start_at = paid_at`
- 用户已有未过期会员时：`start_at = 当前会员 end_at`
- `end_at = start_at + 30 天`

### 3.6 邀请奖励表 `invite_reward_records`

用途：记录邀请奖励是否已发、是否已撤销，避免重复发券。

```sql
CREATE TABLE IF NOT EXISTS invite_reward_records (
    reward_id TEXT PRIMARY KEY,
    inviter_user_id TEXT NOT NULL,
    invitee_user_id TEXT NOT NULL,
    trigger_order_id TEXT NOT NULL,
    coupon_id TEXT,
    status TEXT NOT NULL,
    issued_at TEXT,
    voided_at TEXT,
    void_reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(inviter_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY(invitee_user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY(trigger_order_id) REFERENCES membership_orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY(coupon_id) REFERENCES coupons(coupon_id) ON DELETE SET NULL,
    CHECK (status IN ('pending', 'issued', 'void'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_invite_reward_invitee_once
ON invite_reward_records (invitee_user_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_invite_reward_trigger_order
ON invite_reward_records (trigger_order_id);
```

### 3.7 可选的会员汇总表 `membership_accounts`

用途：做个人页和后台列表时减少实时聚合成本。第一版不是必须。

```sql
CREATE TABLE IF NOT EXISTS membership_accounts (
    user_id TEXT PRIMARY KEY,
    current_status TEXT NOT NULL,
    current_started_at TEXT,
    current_ends_at TEXT,
    last_paid_order_id TEXT,
    total_paid_order_count INTEGER NOT NULL DEFAULT 0,
    total_paid_amount_cent INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CHECK (current_status IN ('never_purchased', 'active', 'expired'))
);
```

## 4. 关键约束与判定逻辑

### 4.1 首单判定

用户满足以下条件时，算“首单”：

- `membership_orders` 中不存在 `status in ('paid', 'refund_pending', 'refunded')` 的成功成交订单时，不准确
- 实际应以“不存在 `status = 'paid'` 且未被全额退款撤销的会员订单”为准

推荐实现口径：

- 查询该用户是否存在“成功且未完全退款失效”的会员订单
- 没有，则本单 `order_type = 'first_purchase'`
- 有，则本单 `order_type = 'renewal'`

### 4.2 邀请奖励触发

满足以下全部条件才发券：

- 被邀请人存在有效 `invite_bindings`
- 当前支付成功订单是被邀请人的首个成功会员订单
- `invite_reward_records` 里还没有这位被邀请人的已发奖励

### 4.3 退款撤销

若被邀请人的首个成功订单退款：

- 该订单对应的 `membership_entitlements` 标记 `revoked`
- 该订单触发的 `invite_reward_records` 标记 `void`
- 对应奖励券如果还未使用，`coupons.status = 'void'`
- 若奖励券已使用，记录 `void_reason = 'used_after_reward_revoke'`，并对邀请人账户进入人工审核或负券处理

### 4.4 幂等要求

以下动作必须按唯一键保证幂等：

- 支付回调：`provider + provider_trade_no`
- 会员发放：`source_order_id`
- 邀请发券：`invitee_user_id` 或 `trigger_order_id`
- 券核销：`used_order_id`

## 5. 接口清单

接口风格建议继续沿用当前项目的 `{"ok": true, "data": ...}` 包装结构。

### 5.1 注册与邀请码绑定

这一部分可以直接扩展 [adapter/routers/auth.py](/i:/Projects/LearningPyramid/adapter/routers/auth.py#L32)。

#### `POST /api/auth/register`

请求体：

```json
{
  "email": "a@example.com",
  "password": "12345678",
  "inviteCode": "LPAB12CD34"
}
```

处理逻辑：

- 创建用户
- 若携带 `inviteCode`，按 `public_uid` 查邀请人
- 禁止绑定自己
- 写入 `invite_bindings`

响应：

```json
{
  "ok": true,
  "data": {
    "userId": "user_xxx",
    "email": "a@example.com",
    "publicUid": "LPAB12CD34",
    "roles": [],
    "membership": {
      "currentStatus": "never_purchased",
      "isFirstOrderEligible": true,
      "firstOrderPriceCent": 1490
    }
  }
}
```

#### `POST /api/invites/bind`

用途：允许用户在首单支付前补填一次邀请码。

请求体：

```json
{
  "inviteCode": "LPAB12CD34"
}
```

规则：

- 当前用户还没有 `invite_bindings`
- 当前用户还没有成功会员订单
- 成功后立即锁成 `active`

### 5.2 会员中心

建议新增 `adapter/routers/membership.py`。

#### `GET /api/membership/me`

返回当前会员状态、首单资格、当前价格、可用券、邀请码统计。

响应示例：

```json
{
  "ok": true,
  "data": {
    "currentStatus": "active",
    "currentEndsAt": "2026-04-25T12:00:00+00:00",
    "isFirstOrderEligible": false,
    "baseMonthlyPriceCent": 1990,
    "firstOrderPriceCent": 1490,
    "nextRenewalPriceCent": 1990,
    "availableCouponCount": 2,
    "bestCoupon": {
      "couponId": "coupon_xxx",
      "amountCent": 500,
      "expiresAt": "2026-04-08T12:00:00+00:00"
    },
    "invite": {
      "myInviteCode": "LPAB12CD34",
      "inviterCode": "LPZZ11YY22",
      "invitedUsers": 8,
      "rewardIssuedCount": 3
    }
  }
}
```

#### `GET /api/invites/me`

返回我的邀请码、绑定关系、邀请明细。

#### `GET /api/coupons/me`

查询当前用户优惠券列表。

查询参数：

- `status=available|used|void|all`
- `limit=50`

#### `GET /api/membership/orders`

查询当前用户会员订单历史。

### 5.3 下单与支付

#### `POST /api/membership/orders/preview`

用途：在下单前计算价格，给前端确认页面使用。

请求体：

```json
{
  "couponId": "coupon_xxx"
}
```

返回：

```json
{
  "ok": true,
  "data": {
    "orderType": "first_purchase",
    "periodDays": 30,
    "listAmountCent": 1990,
    "firstOrderDiscountCent": 500,
    "couponDiscountCent": 500,
    "payableAmountCent": 990,
    "coupon": {
      "couponId": "coupon_xxx",
      "title": "邀请奖励 5 元券"
    }
  }
}
```

#### `POST /api/membership/orders`

用途：正式创建订单。

请求体：

```json
{
  "couponId": "coupon_xxx",
  "provider": "wechat_native"
}
```

处理逻辑：

- 服务端重算价格，不能信前端金额
- 若使用优惠券，先把券设为 `reserved`
- 创建 `membership_orders`
- 调起支付网关

返回：

```json
{
  "ok": true,
  "data": {
    "orderId": "mord_xxx",
    "payableAmountCent": 990,
    "provider": "wechat_native",
    "paymentPayload": {
      "codeUrl": "weixin://wxpay/..."
    },
    "expiresAt": "2026-03-26T12:15:00+00:00"
  }
}
```

#### `POST /api/payments/membership/callback/{provider}`

用途：当前主要保留给 `manual_test` 验收链路；真实微信支付走下面的公网通知地址。

处理顺序：

1. 校验签名
2. 根据 `provider_trade_no` 做幂等
3. 标记订单 `paid`
4. 标记券 `used`
5. 发放 `membership_entitlements`
6. 若是被邀请人的首单，给邀请人发 `5 元券`
7. 锁定 `invite_bindings.status = 'locked'`

#### `POST /api/membership/orders/{orderId}/sync-payment`

用途：用户侧主动同步微信支付状态。

补充说明：

- 当远端状态为 `paid` 时，本地会补发会员权益
- 当远端状态为 `closed / failed` 时，本地会把订单收口成 `closed`
- 这个接口适合前端轮询失败、公网回调延迟、或联调阶段手动补偿

#### `POST /api/payments/wechat/notify`

用途：微信支付成功异步通知。

#### `POST /api/payments/wechat/refund-notify`

用途：微信退款异步通知。

#### `POST /api/membership/orders/{orderId}/close`

用途：关闭未支付订单，释放已保留优惠券。

#### `POST /api/membership/orders/{orderId}/refund`

用途：后台退款或人工触发退款。

### 5.4 管理后台

#### `GET /api/admin/membership/overview`

返回统计：

- 会员总成交订单数
- 会员有效用户数
- 今日支付金额
- 首单转化数
- 邀请绑定数
- 已发券数
- 已用券数
- 退款数

#### `GET /api/admin/membership/orders`

查询参数：

- `status`
- `orderType`
- `userSearch`
- `provider`
- `dateFrom`
- `dateTo`
- `limit`

#### `GET /api/admin/membership/orders/{orderId}`

用途：查看单笔会员订单详情，聚合订单、会员状态、支付流水、用券、邀请链路、奖励券与可执行操作。

#### `POST /api/admin/membership/orders/{orderId}/sync-payment`

用途：后台主动同步微信支付状态。

#### `POST /api/admin/membership/orders/{orderId}/close`

用途：后台关闭待支付订单。

#### `GET /api/admin/membership/invites`

看邀请链路、邀请人、被邀请人、是否已发奖励。

#### `GET /api/admin/membership/coupons`

看券状态与核销情况。

#### `POST /api/admin/membership/coupons/{couponId}/void`

废券。

#### `POST /api/admin/membership/coupons/grant`

人工补发券。

请求体：

```json
{
  "userId": "user_xxx",
  "amountCent": 500,
  "title": "运营补偿券",
  "expiresInDays": 30
}
```

## 6. 请求模型建议

下面这些 Pydantic 请求体可以直接加到 [adapter/schemas.py](/i:/Projects/LearningPyramid/adapter/schemas.py#L23)。

```python
class RegisterAuthRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)
    inviteCode: str | None = Field(default=None, min_length=1, max_length=32)


class BindInviteCodeRequest(BaseModel):
    inviteCode: str = Field(min_length=1, max_length=32)


class PreviewMembershipOrderRequest(BaseModel):
    couponId: str | None = Field(default=None, min_length=1)


class CreateMembershipOrderRequest(BaseModel):
    provider: str = Field(min_length=1)
    couponId: str | None = Field(default=None, min_length=1)


class CloseMembershipOrderRequest(BaseModel):
    reason: str = Field(min_length=0, max_length=200)


class RefundMembershipOrderRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=200)


class AdminGrantCouponRequest(BaseModel):
    userId: str = Field(min_length=1)
    amountCent: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=60)
    expiresInDays: int = Field(ge=1, le=365)
```

## 7. 页面原型

## 7.1 注册页

复用 [frontend/src/views/auth/AuthPage.tsx](/i:/Projects/LearningPyramid/frontend/src/views/auth/AuthPage.tsx#L29)。

新增字段：

- 邀请码输入框
- 首单价格说明
- 邀请奖励文案

页面结构：

```text
+------------------------------------------------------+
| 进入工作空间                                         |
| 创建账号后立刻进入项目空间                           |
|                                                      |
| 邮箱 [________________________]                      |
| 密码 [________________________]                      |
| 邀请码（可选） [________________]                    |
|                                                      |
| 新用户首单 14.9 元，月会员标准价 19.9 元             |
| 邀请好友首单成功后，可获得 5 元券                    |
|                                                      |
| [ 注册并进入 ]                                       |
+------------------------------------------------------+
```

交互：

- 邀请码可不填
- 若邀请码无效，注册不通过并提示
- 注册成功后直接进入系统，同时写入绑定关系

## 7.2 个人中心页

建议继续放在 [frontend/src/views/profile/ProfilePage.tsx](/i:/Projects/LearningPyramid/frontend/src/views/profile/ProfilePage.tsx#L175) 里，新增一个“会员与邀请”区块。

页面结构：

```text
+------------------------------------------------------+
| 会员与邀请                                           |
| 当前状态：会员有效至 2026-04-25                      |
| 月会员标准价：19.9 元                                |
| 新用户首单价：14.9 元                                |
|                                                      |
| 我的邀请码：LPAB12CD34   [复制]                      |
| 绑定上级邀请码：LPZZ11YY22                           |
| 已邀请 8 人，成功转化 3 人                            |
|                                                      |
| 可用优惠券                                           |
| - 邀请奖励 5 元券   2026-04-08 到期   [立即使用]     |
| - 运营补偿 5 元券   2026-04-15 到期   [立即使用]     |
|                                                      |
| [ 立即开通 / 立即续费 ]                              |
+------------------------------------------------------+
```

建议把“立即开通/续费”做成弹窗或独立页。

## 7.3 购买确认弹窗

新增一个前端组件，例如：

- `frontend/src/views/membership/components/MembershipPurchaseDialog.tsx`

页面结构：

```text
+-------------------------------------------+
| 开通月会员                                |
| 标准价          19.9 元                   |
| 首单优惠        -5.0 元                   |
| 优惠券          -5.0 元                   |
| ---------------------------------------   |
| 实付            9.9 元                    |
|                                           |
| 可用优惠券                                |
| ( ) 不使用                                |
| (x) 邀请奖励 5 元券，2026-04-08 到期      |
|                                           |
| [确认支付]                                |
+-------------------------------------------+
```

交互：

- 打开弹窗先调 `/membership/orders/preview`
- 切券时重新调预览接口
- 点击确认才创建正式订单

## 7.4 会员独立页

建议新增路由：

- `/membership`

页面职责：

- 展示权益说明
- 展示当前会员状态
- 展示价格卡
- 展示邀请奖励规则
- 展示订单历史

页面结构：

```text
+------------------------------------------------------+
| 月会员                                               |
| 标准价 19.9 元 / 30 天                               |
| 新用户首单 14.9 元                                   |
| 有 5 元券时，最低可 9.9 元开通                        |
|                                                      |
| [立即开通]                                           |
|                                                      |
| 邀请规则                                             |
| 1. 分享邀请码                                        |
| 2. 好友注册并完成首单                                |
| 3. 你获得 5 元券                                     |
|                                                      |
| 最近订单                                             |
| 2026-03-26  首单  14.9 元  已支付                    |
| 2026-04-25  续费  19.9 元  已支付                    |
+------------------------------------------------------+
```

## 7.5 后台会员管理页

建议新增：

- 路由：`/admin/membership`
- 页面：`frontend/src/views/admin/AdminMembershipPage.tsx`
- 导航：更新 `frontend/src/views/admin/AdminNav.tsx`

页面结构：

```text
+------------------------------------------------------+
| 后台管理 / 会员                                      |
| 成交订单 120 | 有效会员 63 | 今日 GMV 1283.0         |
| 邀请绑定 48  | 已发券 31   | 已用券 19               |
|                                                      |
| [搜索用户] [订单状态] [订单类型] [日期范围]          |
|                                                      |
| 订单列表                                             |
| 用户A | 首单 | 14.9 | 已支付 | wechat_native | 03-26  |
| 用户B | 续费 | 19.9 | 已支付 | wechat_native | 03-26  |
|                                                      |
| 邀请记录                                             |
| 邀请人A -> 被邀请人B -> 已发 5 元券                  |
|                                                      |
| 优惠券记录                                           |
| 用户A | 邀请奖励 5 元券 | 已使用 | 关联订单 xxx      |
+------------------------------------------------------+
```

## 8. 路由与文件改动建议

后端：

- 在 [adapter/routers/__init__.py](/i:/Projects/LearningPyramid/adapter/routers/__init__.py) 注册 `membership` router
- 在 [adapter/schemas.py](/i:/Projects/LearningPyramid/adapter/schemas.py) 增加会员相关请求模型
- 新建 `backend/system/membership_store.py`
- 若继续复用 auth DB，在 [backend/system/auth_store.py](/i:/Projects/LearningPyramid/backend/system/auth_store.py#L703) 的初始化脚本里补充建表

前端：

- 在 [frontend/src/router.tsx](/i:/Projects/LearningPyramid/frontend/src/router.tsx#L40) 新增 `/membership` 与 `/admin/membership`
- 新增 `frontend/src/ui/api/membership.ts`
- 新增 `frontend/src/ui/queries/membership.ts`
- 修改 [frontend/src/views/auth/AuthPage.tsx](/i:/Projects/LearningPyramid/frontend/src/views/auth/AuthPage.tsx#L29) 增加邀请码输入
- 修改 [frontend/src/views/profile/ProfilePage.tsx](/i:/Projects/LearningPyramid/frontend/src/views/profile/ProfilePage.tsx#L175) 增加会员区块
- 修改 `frontend/src/views/admin/AdminNav.tsx` 增加会员入口

## 9. 开发轮次

建议按下面轮次推进：

补充说明：下面保留原始推进顺序，当前代码实际上已经推进到“上线收尾轮”，包括真实微信支付第一版、异常订单收口、后台订单工作台和待支付巡检脚本。

### 第 1 轮：打通会员最小闭环

目标：

- 让用户可以看到会员价格
- 能创建会员订单
- 能完成支付成功后的会员发放

范围：

- 建表：`membership_orders`、`membership_payments`、`membership_entitlements`
- 完成首单 `14.9`、续费 `19.9` 的价格计算
- 完成 `/api/membership/me`
- 完成 `/api/membership/orders/preview`
- 完成 `/api/membership/orders`
- 完成 `/api/payments/membership/callback/{provider}`
- 前端补一个基础购买入口，可先放在个人页或独立 `/membership` 页面

这一轮交付后，系统已经具备“可付费开会员”的基础能力。

### 第 2 轮：打通邀请绑定与奖励发券

目标：

- 让邀请码真正参与首单转化
- 邀请人在被邀请人首单成功后拿到 `5 元券`

范围：

- 建表：`invite_bindings`、`coupons`、`invite_reward_records`
- 注册接口支持 `inviteCode`
- 增加 `/api/invites/bind`
- 增加 `/api/invites/me`
- 增加 `/api/coupons/me`
- 支付成功后补发邀请奖励券
- 购买页支持选择并使用 `5 元券`

这一轮交付后，用户已经能完成“邀请好友 -> 好友首单 -> 我得券 -> 我下次用券”的完整链路。

### 第 3 轮：补齐前端会员中心

目标：

- 把会员、邀请码、优惠券能力集中展示出来
- 让用户能看清自己的会员状态和奖励情况

范围：

- 注册页增加邀请码输入和价格说明
- 个人中心增加“会员与邀请”区块
- 新增会员独立页 `/membership`
- 新增购买确认弹窗
- 增加订单历史展示
- 增加邀请码复制、邀请记录、可用券展示

这一轮交付后，用户侧体验会比较完整。

### 第 4 轮：补后台运营与风控

目标：

- 让后台能看订单、看邀请转化、查券状态、处理异常

范围：

- 新增 `/api/admin/membership/overview`
- 新增 `/api/admin/membership/orders`
- 新增 `/api/admin/membership/invites`
- 新增 `/api/admin/membership/coupons`
- 新增人工补券、废券、退款撤销能力
- 前端新增 `/admin/membership`

这一轮交付后，运营和客服就有基本抓手了。

### 第 5 轮：补退款回滚与稳定性

目标：

- 把财务回滚、奖励撤销、幂等保护补扎实

范围：

- 首单退款后自动撤销邀请奖励
- 已使用奖励券的异常场景进入冻结或人工审核
- 关闭未支付订单时释放已保留优惠券
- 强化支付回调、权益发放、发券的幂等约束
- 补齐自动化测试和管理日志

这一轮交付后，整套会员系统才算进入可稳定运营状态。

## 10. 必测场景

- 无邀请码注册，首单价格应为 `14.9`
- 有邀请码注册，但尚未支付时，不应给邀请人发券
- 被邀请人首单成功后，邀请人获得 `5 元券`
- 邀请人未开会员时，也能先拿到券，并用于自己的首单
- 首单同时使用 `5 元券` 时，实付应为 `9.9`
- 同一支付回调重复触发，不得重复发会员和重复发券
- 关闭未支付订单时，已保留优惠券要释放
- 首单退款后，邀请奖励券应撤销
- 被邀请人不得绑定自己
- 已成功首单后，不允许再补绑邀请码

## 11. 上线收尾轮（已落地）

这一轮补的是从“功能完成”到“可稳定上线”之间的最后一段：

- 文档与当前实现对齐
- 微信配置缺失或半配置的运行期告警
- 待支付微信订单巡检脚本
- 自托管上线核对清单

当前已经提供：

- 上线清单文档：[membership-selfhost-launch-checklist.md](/i:/Projects/LearningPyramid/docs/membership-selfhost-launch-checklist.md)
- 巡检脚本：`python tools/reconcile_membership_payments.py`
- 默认巡检环境变量：
  - `PLM_MEMBERSHIP_PENDING_PAYMENT_RECONCILE_MIN_AGE_MINUTES`
  - `PLM_MEMBERSHIP_PENDING_PAYMENT_RECONCILE_LIMIT`
