# 会员支付上线清单

适用日期：`2026-05-05`

这份清单对应当前已经落地的会员体系实现，包含：

- 月会员 `20 元`、邀请码、被邀请人 `7.5 折会员券`、邀请人固定 `5 元` 佣金
- 考研套餐：每年 `11 月 21 日前`可购买，按购买当天到同年 `12 月 21 日` 逐日计价，每日 `0.5 元`
- `manual_test` 与 `wechat_native`
- 用户侧支付同步、关单
- 用户侧佣金余额、佣金提现申请与提现记录
- 后台订单详情、支付同步、关单、退款回滚、佣金结算与提现处理
- 微信支付通知与退款通知
- 微信支付提现请求与后台提现状态处理
- AI 能力与番茄钟会员门禁

## 1. 上线前必须核对

- `PLM_PUBLIC_ORIGIN` 已配置为外部可访问的 `https://` 地址
- `PLM_TRUSTED_HOSTS` 已配置为外部域名
- `PLM_SECURE_COOKIES=true`
- `PLM_ALLOW_SIGNUP` 是否符合你的运营策略
- `PLM_REQUIRE_SIGNUP_INVITE` 是否符合你的运营策略
- 如果准备开启注册，`PLM_BOOTSTRAP_SUPER_ADMIN_EMAILS` 已先配置为首个管理员邮箱
- 如果准备公网自由开放注册，`PLM_REQUIRE_SIGNUP_INVITE=false`
- 如果准备公网自由开放注册，`PLM_ENABLE_PASSWORD_RESET=true`、`PLM_ENABLE_EMAIL_VERIFICATION=true`、`PLM_ENABLE_SIGNUP_HUMAN_CHECK=true`
- 如果准备公网自由开放注册，`PLM_SMTP_HOST` / `PLM_SMTP_FROM_EMAIL` / `PLM_PUBLIC_ORIGIN` / `PLM_TURNSTILE_SITE_KEY` / `PLM_TURNSTILE_SECRET_KEY` 已配好
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

## 2. 微信支付与提现必须配置

这些变量缺一不可：

- `PLM_WECHAT_PAY_APP_ID`
- `PLM_WECHAT_PAY_MCH_ID`
- `PLM_WECHAT_PAY_CERT_SERIAL_NO`
- `PLM_WECHAT_PAY_API_V3_KEY`
- `PLM_WECHAT_PAY_PRIVATE_KEY_PEM_PATH`
- `PLM_WECHAT_PAY_PUBLIC_KEY_ID`
- `PLM_WECHAT_PAY_PUBLIC_KEY_PEM_PATH`

如果你使用仓库自带的 `docker-compose.selfhost.yml`：

- 把商户私钥和微信支付平台公钥放到仓库根目录 `./certs/`
- compose 会把宿主机 `./certs/` 挂进容器的 `/app/certs/`
- 因此 `.env` 里推荐直接填写：
  - `PLM_WECHAT_PAY_PRIVATE_KEY_PEM_PATH=/app/certs/apiclient_key.pem`
  - `PLM_WECHAT_PAY_PUBLIC_KEY_PEM_PATH=/app/certs/wechatpay_public_key.pem`

通知地址至少满足下面之一：

- 配 `PLM_PUBLIC_ORIGIN`
- 或显式配 `PLM_WECHAT_PAY_NOTIFY_URL`

退款通知至少满足下面之一：

- 配 `PLM_PUBLIC_ORIGIN`
- 或显式配 `PLM_WECHAT_PAY_REFUND_NOTIFY_URL`
- 或显式配 `PLM_WECHAT_PAY_NOTIFY_URL`，系统会用同域名推导退款通知地址

佣金提现使用同一套微信支付商户号、证书和签名配置发起转账请求。上线前需要确认商户号已经具备对应的微信支付转账能力；如果提现请求进入 `processing` 后无法自动获得最终结果，可在后台提现列表中根据微信支付商户后台结果手动标记成功或失败。

生产提现还需要配置微信支付商家转账到零钱场景：

- `PLM_WECHAT_PAY_APP_SECRET`：用于微信授权换取绑定收款身份的 OpenID
- `PLM_WECHAT_PAY_PAYOUT_PROVIDER_MODE`：生产使用 `wechat_native`；本地模拟可配合 `PLM_ENABLE_MANUAL_TEST_PAYMENT=true`
- `PLM_WECHAT_PAY_BINDING_QR_TTL_MINUTES`：桌面绑定二维码有效期，默认 `10`，允许 `1` 到 `60`
- `PLM_WECHAT_PAY_TRANSFER_SCENE_ID`：微信支付商户平台配置的转账场景 ID
- `PLM_WECHAT_PAY_TRANSFER_REMARK`：可选，默认 `会员邀请佣金提现`
- `PLM_WECHAT_PAY_USER_RECV_PERCEPTION`：可选，默认留空；微信会按已开通的转账场景展示收款感知，不要随意填写，否则可能被微信以 `暂不支持展示当前传入的用户收款感知` 拒单
- `PLM_WECHAT_PAY_TRANSFER_NOTIFY_URL`：推荐显式配置为公网 HTTPS 的 `/api/payments/wechat/transfer-notify`
- `PLM_WECHAT_PAY_TRANSFER_SCENE_REPORT_INFOS_JSON`：可选，按微信支付场景要求填写 JSON 数组
- `PLM_WECHAT_PAY_OAUTH_AUTHORIZE_URL` / `PLM_WECHAT_PAY_OAUTH_TOKEN_URL`：通常使用默认微信地址，只有代理或沙箱环境需要覆盖

当前邀请佣金提现使用微信支付商家转账场景 `1005`（佣金报酬）。该场景的默认报备信息为 `岗位类型=推广员`、`报酬说明=会员邀请佣金`。用户收款感知默认不主动传给微信，由微信按商户已开通场景展示。

用户提现前必须先绑定微信收款身份。生产环境应通过微信授权拿到当前 AppID 下的 OpenID；本地验收可以在开启 `PLM_ENABLE_MANUAL_TEST_PAYMENT=true` 时使用 `manual_test` 绑定和提现模拟。电脑端已登录用户发起绑定后，二维码会指向公网后端入口 `/api/commissions/payout-identity/wechat/mobile-bind?attempt=...&state=...`；手机微信扫码后由后端校验一次性绑定 token，再跳转微信网页授权，授权完成后回到手机确认页。手机端不需要再次登录 LearningPyramid。

注意：`wechat_native` 支付能下单成功，不代表提现绑定链路也已经配置完成。普通支付使用微信支付商户 API 和支付二维码；收款身份绑定还依赖公众号网页授权域名与 `PLM_WECHAT_PAY_APP_ID` / `PLM_WECHAT_PAY_APP_SECRET`；商家转账还依赖商户号开通转账能力、`PLM_WECHAT_PAY_TRANSFER_SCENE_ID` 和微信客户端内的确认收款能力。如果手机授权页提示 `redirect_uri域名与后台配置不一致，错误码:10003`，优先检查微信公众平台/开放平台里该 AppID 的网页授权回调域名是否包含当前公网域名，例如 `plm.xuebao.chat`。

佣金默认在支付成功后 `24 小时` 退款窗口结束才进入可提现。本地或预发验收需要快速走通提现时，可以临时设置 `PLM_MEMBERSHIP_COMMISSION_REFUND_WINDOW_MINUTES=1`；生产环境建议保持默认 `1440`。

## 3. 公网回调地址

上线后必须从公网可访问：

- `POST /api/payments/wechat/notify`
- `POST /api/payments/wechat/refund-notify`
- `POST /api/payments/wechat/transfer-notify`

推荐至少人工验证一次：

1. 创建一笔 `wechat_native` 订单
2. 完成真实扫码支付
3. 确认用户侧订单变成 `paid`
4. 确认后台订单详情能看到支付流水
5. 在支付成功后 `24 小时` 内发起一次退款
6. 确认订单进入 `refund_pending`
7. 等待或同步退款结果，确认最终进入 `refunded`
8. 使用一笔超过支付成功后 `24 小时` 的已支付订单尝试发起新退款，确认系统拒绝且不会向微信提交新退款请求

邀请佣金链路建议至少人工验证一次：

1. 使用邀请人邀请码绑定一个新被邀请人
2. 确认被邀请人获得 `7.5 折会员券`
3. 创建 `20 元` 月会员订单并使用该券，确认实付为 `15 元`
4. 完成支付后，确认邀请人出现 `5 元` 待结算佣金
5. 在 `24 小时` 退款窗口内退款一次，确认待结算佣金不会进入可提现余额
6. 再创建一笔不退款的邀请订单，退款窗口结束后触发结算，确认邀请人可提现余额增加 `5 元`

考研套餐链路建议至少人工验证一次：

1. 在会员中心选择 `考研套餐`
2. 将测试时间固定到 `11 月 1 日`，确认预览为 `51` 天、`25.5 元`
3. 将测试时间固定到 `11 月 20 日`，确认预览为 `32` 天、`16 元`
4. 将测试时间固定到 `11 月 21 日`，确认接口拒绝购买并提示仅支持 `11 月 21 日前`
5. 完成一笔考研套餐支付，确认订单详情中的套餐类型、套餐天数和会员到期时间与价格预览一致

佣金提现链路建议至少人工验证一次：

1. 使用有可提现佣金的邀请人完成微信收款身份绑定，页面只应显示脱敏身份
2. 发起提现，确认请求体不再要求手输 OpenID
3. 如果微信返回待用户确认，必须在微信客户端内触发 `requestMerchantTransfer`
4. 确认提现金额从可提现余额转入冻结/处理中余额
5. 通过微信转账通知或主动对账同步最终状态
6. 成功时确认金额进入已打款余额；失败/取消时确认金额退回可提现余额

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

邀请佣金和提现自动化还需要两个定时任务：

```bash
python tools/settle_membership_commissions.py --limit 200
python tools/reconcile_commission_withdrawals.py --min-age-minutes 2 --limit 100
```

建议每 5 分钟执行一次。第一个脚本会把超过 24 小时退款窗口且未退款的待结算佣金转入可提现；第二个脚本会按商户提现单号查询微信转账状态，补齐漏掉的通知结果，并保留对账运行摘要和告警。

## 5. Windows 计划任务示例

如果你是 Windows 自托管，可以用任务计划程序每 5 分钟执行一次：

```powershell
python i:\Projects\LearningPyramid\tools\reconcile_membership_payments.py --min-age-minutes 5 --limit 100
python i:\Projects\LearningPyramid\tools\settle_membership_commissions.py --limit 200
python i:\Projects\LearningPyramid\tools\reconcile_commission_withdrawals.py --min-age-minutes 2 --limit 100
```

建议：

- 使用与你部署一致的 Python 环境
- 工作目录设为仓库根目录
- 打开“如果任务失败，按间隔重试”
- 保存标准输出到日志文件，方便排障

## 6. Linux cron 示例

```cron
*/5 * * * * cd /srv/learningpyramid && /usr/bin/python3 tools/reconcile_membership_payments.py --min-age-minutes 5 --limit 100 >> /var/log/learningpyramid-membership-reconcile.log 2>&1
*/5 * * * * cd /srv/learningpyramid && /usr/bin/python3 tools/settle_membership_commissions.py --limit 200 >> /var/log/learningpyramid-commission-settle.log 2>&1
*/5 * * * * cd /srv/learningpyramid && /usr/bin/python3 tools/reconcile_commission_withdrawals.py --min-age-minutes 2 --limit 100 >> /var/log/learningpyramid-withdrawal-reconcile.log 2>&1
```

## 7. 上线后首日重点观察

- 是否存在大量 `pending` 微信订单长期不收口
- 是否出现支付成功但本地没有发会员的情况
- 是否出现退款成功但本地仍停留在 `refund_pending`
- 是否出现超过 `24 小时` 的已支付订单仍能发起新退款
- 是否出现提现长期停留在 `awaiting_confirmation` / `processing`
- 是否出现对账告警未处理或同一商户单反复异常
- 被邀请人绑定邀请码后是否只获得一张 `7.5 折会员券`
- 邀请人是否不再获得新的 `邀请奖励 5 元券`
- 邀请佣金是否在首单支付后进入待结算，并只在 `24 小时` 退款窗口结束后转入可提现
- 首单退款后待结算佣金是否正确取消或保持不可提现
- 提现失败后冻结余额是否正确退回可提现余额
- 非会员是否被正确拦截在个人 LLM 配置、AI 问答、播放器 AI 问答和番茄钟之外
- 有效会员购买或续费后，受保护功能是否在下一次访问时恢复可用

## 8. 会员专属功能核验

上线前建议至少用一个非会员账号和一个有效会员账号各跑一遍：

- 非会员打开全局设置，应看到大模型配置的会员专属提示和会员中心入口
- 非会员打开 AI 问答页，输入框和发送行为应被会员门禁拦截
- 非会员在播放器里打开视频助手，应看到会员专属提示
- 非会员打开番茄钟和番茄钟设置，应看到会员专属提示
- 有效会员应能正常保存个人 LLM 配置、发起 AI 问答、使用播放器 AI 问答和进入番茄钟
- 退款、过期或后台撤销后，下一次访问上述功能应重新进入会员门禁

## 9. 当前关键接口

用户侧：

- `GET /api/membership/me`
- `GET /api/membership/orders`
- `POST /api/membership/orders`
- `POST /api/membership/orders/preview`
- `POST /api/membership/orders/{orderId}/sync-payment`
- `POST /api/membership/orders/{orderId}/close`
- `GET /api/commissions/me`
- `GET /api/commissions/payout-identity`
- `POST /api/commissions/payout-identity/wechat/binding-attempts`
- `POST /api/commissions/payout-identity/wechat/bind`
- `GET /api/commissions/withdrawals`
- `POST /api/commissions/withdrawals`

微信侧：

- `POST /api/payments/wechat/notify`
- `POST /api/payments/wechat/refund-notify`
- `POST /api/payments/wechat/transfer-notify`

后台：

- `GET /api/admin/membership/overview`
- `GET /api/admin/membership/orders`
- `GET /api/admin/membership/orders/{orderId}`
- `POST /api/admin/membership/grants`
- `POST /api/admin/membership/orders/{orderId}/sync-payment`
- `POST /api/admin/membership/orders/{orderId}/close`
- `POST /api/admin/membership/orders/{orderId}/refund`
- `GET /api/admin/membership/commissions`
- `POST /api/admin/membership/commissions/settle`
- `GET /api/admin/membership/withdrawals`
- `GET /api/admin/membership/payout-identities`
- `GET /api/admin/membership/withdrawals/events`
- `GET /api/admin/membership/withdrawals/warnings`
- `POST /api/admin/membership/withdrawals/warnings/{warningId}/ack`
- `POST /api/admin/membership/withdrawals/{withdrawalId}/sync`
- `POST /api/admin/membership/withdrawals/{withdrawalId}/resolve`
