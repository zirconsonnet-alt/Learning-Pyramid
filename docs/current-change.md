# Current Change

更新时间：2026-05-11

## 1. 当前用户要求

- 将线上会员退款期改成 1 分钟并同步服务器，用于测试佣金功能。

## 2. 本次实际修改文件

- `backend/system/membership_store.py`
- `docker-compose.selfhost.yml`
- `docs/current-change.md`
- `docs/guide-faq.md`
- `frontend/src/views/home/HomePage.tsx`
- `tests/test_backend_legacy_cleanup.py`

## 3. 每个文件为什么修改

- `backend/system/membership_store.py`：新增 `LEARNINGPYRAMID_MEMBERSHIP_REFUND_WINDOW_MINUTES`，让会员订单可退款窗口可按环境配置；默认仍为 1440 分钟。
- `docker-compose.selfhost.yml`：把 `LEARNINGPYRAMID_MEMBERSHIP_REFUND_WINDOW_MINUTES` 传入自托管 app 容器。
- `docs/guide-faq.md`、`frontend/src/views/home/HomePage.tsx`：移除写死的“3天退款期”文案，改为退款窗口语义。
- `tests/test_backend_legacy_cleanup.py`：补充会员退款窗口读取当前环境变量的回归测试。
- `docs/current-change.md`：记录本次变更边界、验证和风险。

## 4. 行为语义是否变化

是。会员订单可发起退款窗口从固定 24 小时变为环境变量可配置；未配置时仍保持 24 小时。

线上同步 overlay 将 `LEARNINGPYRAMID_MEMBERSHIP_REFUND_WINDOW_MINUTES` 和 `LEARNINGPYRAMID_MEMBERSHIP_COMMISSION_REFUND_WINDOW_MINUTES` 都设为 1 分钟，用于佣金功能测试。

## 5. 是否做了重构，以及为什么

未做重构。只补一个配置读取函数和自托管环境传递，保持现有 membership store 边界不变。

## 6. 未修改哪些相关内容，以及为什么

- 未把默认退款窗口改成 1 分钟：1 分钟是线上测试配置，不应污染产品默认。
- 未修改佣金结算窗口实现：该窗口已有 `LEARNINGPYRAMID_MEMBERSHIP_COMMISSION_REFUND_WINDOW_MINUTES`，线上已配置为 1 分钟。
- 未提交 `.env.selfhost.sync`：该文件包含线上密钥，只作为本机部署 overlay 使用。
- 未修改同步脚本 `--no-cache` 策略：这属于部署构建策略变化，不是本次退款窗口需求。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：无接口参数或返回结构变化。
- 架构：无架构边界变化。
- 部署：新增自托管 app 环境变量传递。
- 数据结构：无 schema 变化。
- UI：主页 FAQ 文案不再写死 3 天。
- 测试：新增后端单元测试。

## 8. 当前风险点和不确定项

- 线上测试配置把会员订单退款窗口缩短到 1 分钟，适合佣金测试，但不适合作为长期生产策略。
- `.env.selfhost.example` 仍使用旧 `PLM_*` 命名，和当前 compose 的 `LEARNINGPYRAMID_*` 不一致；本次不改示例文件，避免扩大配置迁移范围。

## 9. 仍需用户确认的问题

无。用户已明确要求改成 1 分钟并同步线上服务器。

## 10. 验证结果

- 已先运行新增测试，确认现状失败：`PreconditionFailure not raised`。
- `python -m unittest tests.test_backend_legacy_cleanup.BackendLegacyCleanupTest.test_membership_refund_window_uses_current_env_minutes`：通过。
- `git diff --check`：通过；仅提示多个文件下次 Git 触碰时 LF 会替换为 CRLF。
- `python -m unittest tests.test_backend_legacy_cleanup`：通过，35 tests。
- `python tools/verify_backend_boundaries.py`：通过，输出 `backend boundary guards verified`。
- 本机 `.env.selfhost.sync` 只读确认：`LEARNINGPYRAMID_MEMBERSHIP_REFUND_WINDOW_MINUTES=1`，`LEARNINGPYRAMID_MEMBERSHIP_COMMISSION_REFUND_WINDOW_MINUTES=1`。
- `python -m unittest discover -s tests`：通过，78 tests。
- `pnpm --dir frontend build`：通过；Vite 输出 chunk size warning。
- 线上同步和线上健康检查：待执行。

## 11. 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否
