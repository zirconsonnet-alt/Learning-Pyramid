# Current Change

更新时间：2026-05-11

## 1. 当前用户要求

- 删除购买弹窗“订单说明”中的“当前价格”行。

## 2. 本次实际修改文件

- `frontend/src/views/membership/components/MembershipPurchaseDialog.tsx`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `frontend/src/views/membership/components/MembershipPurchaseDialog.tsx`：移除订单说明里的“当前价格”展示行，避免和上方价格预览的“本次实付”重复。
- `docs/current-change.md`：记录本次 UI 删除范围、行为影响和验证结果。

## 4. 行为语义是否变化

否。只删除购买弹窗中的一行重复展示文案，不改变价格预览、下单金额、支付方式或订单创建逻辑。

## 5. 是否做了重构，以及为什么

未做重构。只移除单行 JSX。

## 6. 未修改哪些相关内容，以及为什么

- 未修改上方价格预览的“本次实付”：该处仍是主要金额确认入口。
- 未修改订单说明中的会员时长、套餐类型、支付方式和创建待支付订单提示。
- 未修改任何 API、数据结构或支付逻辑。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：无变化。
- 架构：无变化。
- 部署：需要重新构建并同步前端资源后线上生效。
- 数据结构：无变化。
- UI：购买弹窗订单说明少一行“当前价格”。
- 测试：未新增自动化测试。

## 8. 当前风险点和不确定项

无。

## 9. 仍需用户确认的问题

无。

## 10. 验证结果

- `pnpm --dir frontend build`：通过；Vite 输出既有 chunk size warning。
- `git diff --check`：通过；仅提示 `docs/current-change.md` 和 `frontend/src/views/membership/components/MembershipPurchaseDialog.tsx` 下次 Git 触碰时 LF 会替换为 CRLF。
- 已确认 `frontend/src/views/membership/components/MembershipPurchaseDialog.tsx` 中不再包含“当前价格：”，订单说明和上方“本次实付”仍保留。

## 11. 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否
