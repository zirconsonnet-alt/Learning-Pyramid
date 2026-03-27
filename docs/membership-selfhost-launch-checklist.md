# 会员支付上线清单

适用日期：`2026-03-26`

这份清单对应当前已经落地的会员体系实现，包含：

- 月会员、首单优惠、邀请码、邀请奖励券
- `manual_test` 与 `wechat_native`
- 用户侧支付同步、关单
- 后台订单详情、支付同步、关单、退款回滚
- 微信支付通知与退款通知

## 1. 上线前必须核对

- `PLM_PUBLIC_ORIGIN` 已配置为外部可访问的 `https://` 地址
- `PLM_TRUSTED_HOSTS` 已配置为外部域名
- `PLM_SECURE_COOKIES=true`
- `PLM_ALLOW_SIGNUP` 是否符合你的运营策略
- `PLM_MEDIA_ACCESS_TOKEN_SECRET` 已替换为真实长随机值
- PostgreSQL 凭据已替换示例值
- 如果服务器访问 PyPI 不稳定，已提前配置 `PLM_PIP_INDEX_URL` / `PLM_PIP_TRUSTED_HOST`

推荐的可选构建变量：

- `PLM_PIP_INDEX_URL`
- `PLM_PIP_EXTRA_INDEX_URL`
- `PLM_PIP_TRUSTED_HOST`
- `PLM_PIP_DEFAULT_TIMEOUT`
- `PLM_PIP_RETRIES`

示例：

```env
PLM_PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
PLM_PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn
PLM_PIP_DEFAULT_TIMEOUT=120
PLM_PIP_RETRIES=10
```

## 2. 微信支付必须配置

这些变量缺一不可：

- `PLM_WECHAT_PAY_APP_ID`
- `PLM_WECHAT_PAY_MCH_ID`
- `PLM_WECHAT_PAY_CERT_SERIAL_NO`
- `PLM_WECHAT_PAY_API_V3_KEY`
- `PLM_WECHAT_PAY_PRIVATE_KEY_PEM_PATH`
- `PLM_WECHAT_PAY_PUBLIC_KEY_ID`
- `PLM_WECHAT_PAY_PUBLIC_KEY_PEM_PATH`

通知地址至少满足下面之一：

- 配 `PLM_PUBLIC_ORIGIN`
- 或显式配 `PLM_WECHAT_PAY_NOTIFY_URL`

退款通知至少满足下面之一：

- 配 `PLM_PUBLIC_ORIGIN`
- 或显式配 `PLM_WECHAT_PAY_REFUND_NOTIFY_URL`
- 或显式配 `PLM_WECHAT_PAY_NOTIFY_URL`，系统会用同域名推导退款通知地址

## 3. 公网回调地址

上线后必须从公网可访问：

- `POST /api/payments/wechat/notify`
- `POST /api/payments/wechat/refund-notify`

推荐至少人工验证一次：

1. 创建一笔 `wechat_native` 订单
2. 完成真实扫码支付
3. 确认用户侧订单变成 `paid`
4. 确认后台订单详情能看到支付流水
5. 发起一次退款
6. 确认订单进入 `refund_pending`
7. 等待或同步退款结果，确认最终进入 `refunded`

## 4. 巡检任务

当前已经提供一次执行式巡检脚本：

```bash
python tools/reconcile_membership_payments.py
```

默认行为：

- 只巡检 `wechat_native`
- 只检查创建时间至少 `5` 分钟前、仍然 `pending` 的订单
- 单次最多处理 `100` 笔
- 会把远端已支付的单补成 `paid`
- 会把远端已关闭或失败的单补成 `closed`
- 标准输出返回 JSON 汇总
- 如果存在巡检错误，进程退出码为 `1`

可调参数：

```bash
python tools/reconcile_membership_payments.py --min-age-minutes 10 --limit 200
```

也可以用环境变量控制默认值：

- `PLM_MEMBERSHIP_PENDING_PAYMENT_RECONCILE_MIN_AGE_MINUTES`
- `PLM_MEMBERSHIP_PENDING_PAYMENT_RECONCILE_LIMIT`

## 5. Windows 计划任务示例

如果你是 Windows 自托管，可以用任务计划程序每 5 分钟执行一次：

```powershell
python i:\Projects\LearningPyramid\tools\reconcile_membership_payments.py --min-age-minutes 5 --limit 100
```

建议：

- 使用与你部署一致的 Python 环境
- 工作目录设为仓库根目录
- 打开“如果任务失败，按间隔重试”
- 保存标准输出到日志文件，方便排障

## 6. Linux cron 示例

```cron
*/5 * * * * cd /srv/learningpyramid && /usr/bin/python3 tools/reconcile_membership_payments.py --min-age-minutes 5 --limit 100 >> /var/log/learningpyramid-membership-reconcile.log 2>&1
```

## 7. 上线后首日重点观察

- 是否存在大量 `pending` 微信订单长期不收口
- 是否出现支付成功但本地没有发会员的情况
- 是否出现退款成功但本地仍停留在 `refund_pending`
- 邀请奖励券是否按首单成功正确发放
- 首单退款后奖励券是否正确撤销

## 8. 当前关键接口

用户侧：

- `GET /api/membership/me`
- `GET /api/membership/orders`
- `POST /api/membership/orders`
- `POST /api/membership/orders/preview`
- `POST /api/membership/orders/{orderId}/sync-payment`
- `POST /api/membership/orders/{orderId}/close`

微信侧：

- `POST /api/payments/wechat/notify`
- `POST /api/payments/wechat/refund-notify`

后台：

- `GET /api/admin/membership/overview`
- `GET /api/admin/membership/orders`
- `GET /api/admin/membership/orders/{orderId}`
- `POST /api/admin/membership/orders/{orderId}/sync-payment`
- `POST /api/admin/membership/orders/{orderId}/close`
- `POST /api/admin/membership/orders/{orderId}/refund`
