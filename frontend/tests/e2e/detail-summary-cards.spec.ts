import { expect, test } from "@playwright/test"

import { collectConsoleIssues, expectHealthyPage, expectNoConsoleIssues } from "../fixtures/app-checks"
import { installMockApi } from "../fixtures/mock-api"
import { projectPath } from "../fixtures/page-objects"
import {
  convergence,
  instance,
  learningObjectNode,
  learningTask,
  learningTaskNode,
  recallPoint,
  reviewChain,
  reviewTask,
} from "../fixtures/test-data"

const detailPages = [
  {
    name: "review task",
    path: projectPath(`/review-tasks/${reviewTask.reviewTaskId}`),
    title: "复习任务",
  },
  {
    name: "review chain",
    path: projectPath(`/review-chains/${reviewChain.reviewChainId}`),
    title: "复习链",
  },
  {
    name: "convergence",
    path: projectPath(`/convergences/${convergence.convergenceId}`),
    title: "收敛",
  },
  {
    name: "learning task",
    path: projectPath(`/learning-task-nodes/${learningTaskNode.nodeId}`),
    title: learningTask.title,
  },
  {
    name: "recall point",
    path: projectPath(`/recall-points/${recallPoint.recallPointId}`),
    title: "复述点",
  },
  {
    name: "instance",
    path: projectPath(`/instances/${instance.instanceId}`),
    title: instance.materialDisplayName,
  },
  {
    name: "learning object",
    path: projectPath(`/learning-object-nodes/${learningObjectNode.nodeId}`),
    title: learningObjectNode.title,
  },
] as const

for (const detailPage of detailPages) {
  test(`detail summary card uses the unified header on ${detailPage.name}`, async ({ page }) => {
    const consoleIssues = collectConsoleIssues(page)
    await installMockApi(page)

    await page.goto(detailPage.path)
    await expectHealthyPage(page, detailPage.path)

    const summaryCard = page.getByTestId("detail-summary-card")
    await expect(summaryCard).toBeVisible()
    await expect(summaryCard.getByTestId("detail-summary-title-icon")).toBeVisible()
    await expect(summaryCard.getByRole("heading", { name: detailPage.title, exact: true })).toBeVisible()
    await expect(summaryCard.getByTestId("detail-summary-title-divider")).toBeVisible()
    await expect(summaryCard.getByRole("link", { name: /^返回/ })).toHaveCount(0)
    await expect(summaryCard.getByRole("button", { name: /^返回/ })).toHaveCount(0)
    await expect(summaryCard.getByText(/^项目：/)).toHaveCount(0)
    await expect(page.getByText(/^项目：/)).toHaveCount(0)

    expectNoConsoleIssues(consoleIssues)
  })
}
