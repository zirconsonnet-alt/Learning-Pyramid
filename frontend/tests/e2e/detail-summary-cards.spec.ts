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

test("recall point detail editor previews markdown and latex while hovering field labels", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.goto(projectPath(`/recall-points/${recallPoint.recallPointId}`))
  await expectHealthyPage(page, projectPath(`/recall-points/${recallPoint.recallPointId}`))

  await page.getByRole("button", { name: "修改内容" }).click()
  await page.getByPlaceholder("输入问题/提示语").fill("**概率论** 的密度函数：$f(x)=\\frac{1}{\\sqrt{2\\pi}\\sigma}$")
  await page.getByPlaceholder("输入答案/复述内容").fill("答案满足 $\\mu=0$。")

  const questionPreviewButton = page.getByRole("button", { name: "题面预览" })
  const answerPreviewButton = page.getByRole("button", { name: "答案预览" })
  await expect(questionPreviewButton).toBeVisible()
  await expect(answerPreviewButton).toBeVisible()

  await questionPreviewButton.hover()
  const questionPreview = page.getByRole("tooltip", { name: "题面渲染预览" })
  await expect(questionPreview).toBeVisible()
  await expect(questionPreview.locator(".katex")).toHaveCount(1)
  await expect(questionPreview.getByText("概率论")).toBeVisible()

  await answerPreviewButton.hover()
  const answerPreview = page.getByRole("tooltip", { name: "答案渲染预览" })
  await expect(answerPreview).toBeVisible()
  await expect(answerPreview.locator(".katex")).toHaveCount(1)
  await expect(questionPreview).toBeHidden()

  await page.mouse.move(5, 5)
  await expect(answerPreview).toBeHidden()

  expectNoConsoleIssues(consoleIssues)
})
