# 当前变更：Task 3 低风险回归测试补强

## 当前用户要求

- 做 Task 3 复审后的低风险测试强化。
- 只修改并提交 `mobile/__tests__/session-cookie.test.ts` 和 `docs/current-change.md`。
- 补一条显式回归测试，确认 `Set-Cookie` 中 `Expires=Wed, 21 Oct ...` 的逗号不会被 `splitSetCookieHeader` 误切。
- 确认后续合并 cookie 中仍能找到 `plm_session`。

## 根因

- 现有测试覆盖了普通合并 `Set-Cookie` header 查找 `plm_session`。
- 但缺少显式覆盖 `Expires` 属性内逗号的回归用例，后续维护者改动拆分逻辑时可能误把日期逗号当作 cookie 边界。

## 本次实际修改文件

- `mobile/__tests__/session-cookie.test.ts`
  - 追加 `does not split Expires commas while finding plm_session` 回归测试。
  - 用带 `Expires=Wed, 21 Oct 2030 07:28:00 GMT` 的合并 `Set-Cookie` 字符串验证仍返回 `{ kind: "set", cookie: "plm_session=abc123" }`。
- `docs/current-change.md`
  - 覆盖为当前低风险回归测试补强工作单。

## 行为语义是否变化

- 无生产行为变化。
- 仅新增回归测试，锁定已有 `Set-Cookie` 解析语义。

## 重构说明

- 未做重构。

## 未修改内容

- 未修改生产代码。
- 未修改后端、移动端 API client、认证策略或部署配置。
- 未新增 fallback、shim、legacy 或特殊认证分支。
- 未修改测试配置、构建配置或无关工作区改动。
- 未更新长期文档；本次只补充低风险回归测试，不改变长期行为事实。

## 影响范围

- API：无影响。
- 架构：无影响。
- 部署：无影响。
- 数据结构：无影响。
- UI：无影响。
- 测试：补充移动端 session cookie helper 回归测试。

## 当前风险点和不确定项

- 风险低；新增测试依赖已有 `extractSessionCookieUpdate` 行为，不改变实现。

## 仍需用户确认的问题

- 无。

## 验证记录

- GREEN：`pnpm --dir mobile test -- session-cookie.test.ts` 通过，1 个测试套件、7 个测试通过。
- GREEN：`pnpm --dir mobile typecheck` 通过。
- GREEN：`git diff --check -- mobile/__tests__/session-cookie.test.ts docs/current-change.md` 通过；仅有 Git 换行转换 warning，无 whitespace error。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否
