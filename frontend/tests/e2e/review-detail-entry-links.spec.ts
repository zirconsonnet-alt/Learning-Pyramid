import { expect, test, type Locator, type Page } from "@playwright/test"

import { collectConsoleIssues, expectHealthyPage, expectNoConsoleIssues } from "../fixtures/app-checks"
import { installMockApi } from "../fixtures/mock-api"
import { projectPath } from "../fixtures/page-objects"
import { convergence, instance, learningTaskNode, learningObjectNode, reviewChain, reviewTask } from "../fixtures/test-data"

async function expectSummaryLabelOrder(summaryCard: Locator, labels: string[]) {
  const text = await summaryCard.innerText()
  let previousIndex = -1
  for (const label of labels) {
    const index = text.indexOf(label)
    expect(index, `summary card should contain label ${label}`).toBeGreaterThanOrEqual(0)
    expect(index, `summary label ${label} should keep the shared order`).toBeGreaterThan(previousIndex)
    previousIndex = index
  }
}

async function expectNoOpaqueReviewReferences(page: Page) {
  const bodyText = await page.locator("body").innerText()
  expect(bodyText).not.toMatch(/复习任务\s+#/)
  expect(bodyText).not.toMatch(/收敛步骤\s+#/)
  expect(bodyText).not.toMatch(/复习链\s+#/)
  expect(bodyText).not.toMatch(/结果范围\s+#/)
  expect(bodyText).not.toMatch(/内容实例\s+#/)
  expect(bodyText).not.toMatch(/复述点\s+#/)
}

async function expectNoOpaqueInstanceReferences(page: Page) {
  const bodyText = await page.locator("body").innerText()
  expect(bodyText).not.toMatch(/内容实例\s+#/)
  expect(bodyText).not.toMatch(/内容\s+#/)
}

test("review task detail uses a clickable related entry and hides unreadable ids", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.goto(projectPath(`/review-tasks/${reviewTask.reviewTaskId}`))
  await expectHealthyPage(page, projectPath(`/review-tasks/${reviewTask.reviewTaskId}`))

  const summaryCard = page.getByTestId("detail-summary-card")
  await expectSummaryLabelOrder(summaryCard, ["状态", "复述点", "结果摘要", "关联入口", "创建时间", "执行时间"])
  await expect(summaryCard.getByRole("link", { name: "查看复习链" })).toHaveAttribute("href", projectPath(`/review-chains/${reviewChain.reviewChainId}`))
  await expect(page.getByText("按这次复习的输入顺序展开每个复述点，以及对应的会/不会判定。")).toHaveCount(0)
  await expect(page.getByText("关联内容")).toHaveCount(0)
  await expectNoOpaqueReviewReferences(page)

  expectNoConsoleIssues(consoleIssues)
})

test("review chain detail keeps shared summary order and removes queue item id labels", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.goto(projectPath(`/review-chains/${reviewChain.reviewChainId}`))
  await expectHealthyPage(page, projectPath(`/review-chains/${reviewChain.reviewChainId}`))

  const summaryCard = page.getByTestId("detail-summary-card")
  await expectSummaryLabelOrder(summaryCard, ["状态", "队列长度", "目标层级", "关联入口", "当前任务"])
  await expect(summaryCard.getByRole("link", { name: "自动化测试任务" })).toHaveAttribute("href", projectPath(`/learning-task-nodes/${learningTaskNode.nodeId}`))
  await expectNoOpaqueReviewReferences(page)

  expectNoConsoleIssues(consoleIssues)
})

test("convergence detail links back to the review chain and hides range ids", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.goto(projectPath(`/convergences/${convergence.convergenceId}`))
  await expectHealthyPage(page, projectPath(`/convergences/${convergence.convergenceId}`))

  const summaryCard = page.getByTestId("detail-summary-card")
  await expectSummaryLabelOrder(summaryCard, ["状态", "轮次数", "已生成复习任务", "关联入口"])
  await expect(summaryCard.getByRole("link", { name: "查看复习链" })).toHaveAttribute("href", projectPath(`/review-chains/${reviewChain.reviewChainId}`))
  await expectNoOpaqueReviewReferences(page)

  expectNoConsoleIssues(consoleIssues)
})

test("learning task detail renames related content to a clickable related entry", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.goto(projectPath(`/learning-task-nodes/${learningTaskNode.nodeId}`))
  await expectHealthyPage(page, projectPath(`/learning-task-nodes/${learningTaskNode.nodeId}`))

  const summaryCard = page.getByTestId("detail-summary-card")
  await expectSummaryLabelOrder(summaryCard, ["复述点", "层级", "关联入口", "复习关系"])
  await expect(summaryCard.getByRole("link", { name: instance.materialDisplayName })).toHaveAttribute("href", projectPath(`/instances/${instance.instanceId}`))
  await expect(summaryCard.getByText("关联内容")).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test("instance detail removes opaque ids from the summary card", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.goto(projectPath(`/instances/${instance.instanceId}`))
  await expectHealthyPage(page, projectPath(`/instances/${instance.instanceId}`))

  const summaryCard = page.getByTestId("detail-summary-card")
  await expect(summaryCard.getByText("当前引用")).toHaveCount(0)
  await expect(summaryCard.getByText("内容引用")).toHaveCount(0)
  await expect(summaryCard.getByRole("link", { name: learningObjectNode.title })).toHaveAttribute("href", projectPath(`/learning-object-nodes/${learningObjectNode.nodeId}`))
  await expectNoOpaqueInstanceReferences(page)

  expectNoConsoleIssues(consoleIssues)
})
