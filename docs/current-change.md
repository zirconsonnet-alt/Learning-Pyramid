# 当前变更：移动端学科、材料与学习对象浏览

## 当前用户要求

- 继续 React Native 移动端 App MVP。
- 当前执行 Task 6：实现学科列表、材料列表和学习对象浏览。
- 继续只使用现有公开 API，不新增移动端专用协议。

## 根因

- 移动端已有认证和领域 API client，但登录后仍没有学科/材料/学习对象的浏览入口。
- 页面如果各自创建 API client，会产生重复 client 和 session 状态分裂；需要移动端内部 `ApiProvider` 统一提供同一个 API 实例。

## 本次实际修改文件

- `mobile/__tests__/learning-navigation.test.tsx`
  - 新增 `ProjectScreen` 渲染学习对象标题的 RED 测试。
- `mobile/src/api/ApiProvider.tsx`
  - 新增移动端内部 API context，供页面复用 `_layout` 创建的 API 实例。
- `mobile/src/api/errorMessage.ts`
  - 新增统一错误消息转换，避免请求失败被列表页误显示为空状态。
- `mobile/src/routing/params.ts`
  - 新增 Expo Router 动态参数归一化 helper，避免动态路由重复处理 `string | string[] | undefined`。
- `mobile/src/screens/SubjectsScreen.tsx`
  - 新增学科列表页面。
- `mobile/src/screens/SubjectMaterialsScreen.tsx`
  - 新增材料列表页面。
- `mobile/src/screens/ProjectScreen.tsx`
  - 新增学习对象浏览页面。
- `mobile/src/app/_layout.tsx`
  - 增加 `ApiProvider` 包裹。
- `mobile/src/app/index.tsx`
  - signedIn 状态下加载并展示学科列表。
- `mobile/src/app/subject/[subjectId].tsx`
  - 新增学科材料路由。
- `mobile/src/app/project/[subjectId]/[scopedProjectId].tsx`
  - 新增项目学习对象路由。
- `docs/current-change.md`
  - 更新当前工作单。

## 行为语义是否变化

- 移动端登录后显示学科列表。
- 用户可进入某个学科的材料列表，并进入材料对应的 scoped project 学习对象列表。
- 学科、材料和学习对象加载失败时显示错误状态，不伪装为“暂无”。
- 学习对象详情仍未实现，`ProjectScreen` 当前只浏览列表；详情在 Task 7 实现。
- 不改变后端 API、部署、数据结构或 Web/Tauri 行为。

## 重构说明

- 做了当前需求范围内的局部结构整理。
- 新增 `ApiProvider` 是为了避免页面重复创建 API client 和 session 状态分裂。
- 新增 `firstRouteParam` 是为了消除两个动态路由的重复参数归一化逻辑。

## 未修改内容

- 未修改后端 API。
- 未新增移动端专用协议。
- 未引入或持久化内部 backend project id。
- 未实现学习对象详情、媒体播放或复习提交。
- 未删除 Expo 模板其它文件。
- 未更新长期文档；移动端预览整体完成后统一同步。

## 影响范围

- API：仅移动端调用现有公开 API。
- 架构：移动端内部新增 API context。
- 部署：无影响。
- 数据结构：无影响。
- UI：移动端新增学科、材料、学习对象列表。
- 测试：新增学习对象列表渲染测试。

## 当前风险点和不确定项

- `ProjectScreen` 的节点点击在 Task 6 中暂不导航，避免指向尚未实现的详情路由；Task 7 会接入。
- 材料没有 `scopedProjectId` 时禁用进入，不伪造项目身份。

## 仍需用户确认的问题

- 无。

## 验证记录

- RED：`pnpm --dir mobile test -- learning-navigation.test.tsx` 失败，摘要：`../src/screens/ProjectScreen` 不存在。
- RED：补充错误态测试后失败，摘要：`ProjectScreen` 将加载失败显示为 `暂无学习对象`。
- GREEN：`pnpm --dir mobile test -- learning-navigation.test.tsx` 通过，1 个测试套件、2 个测试通过。
- 已运行：`pnpm --dir mobile typecheck`，通过。
- 已运行：`git diff --check -- mobile/src/api/ApiProvider.tsx mobile/src/api/errorMessage.ts mobile/src/routing/params.ts mobile/src/screens/SubjectsScreen.tsx mobile/src/screens/SubjectMaterialsScreen.tsx mobile/src/screens/ProjectScreen.tsx mobile/src/app/_layout.tsx mobile/src/app/index.tsx mobile/src/app/subject mobile/src/app/project mobile/__tests__/learning-navigation.test.tsx docs/current-change.md`，通过；仅有 Git 换行转换 warning，无 whitespace error。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否
