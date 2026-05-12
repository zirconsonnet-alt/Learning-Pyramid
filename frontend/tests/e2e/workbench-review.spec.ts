import { expect, test } from "@playwright/test"

import { collectConsoleIssues, expectNoConsoleIssues } from "../fixtures/app-checks"
import { installMockApi } from "../fixtures/mock-api"
import { journeyIds } from "../fixtures/journeys"
import { recordJourney } from "../fixtures/journey-result"
import { gotoWorkbench, projectPath } from "../fixtures/page-objects"

test(journeyIds.workbench, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await recordJourney(journeyIds.workbench, async () => {
    await gotoWorkbench(page)
    const todayReviewToggle = page.getByRole("button", { name: /今日回看.*展开/ })
    await todayReviewToggle.focus()
    await page.keyboard.press("Enter")
    await expect(page.getByText("网页驻留")).toBeVisible()
    await page.getByRole("button", { name: "层推进与学习任务" }).click()
    await expect(page.getByRole("heading", { name: "层推进与学习任务" })).toBeVisible()
  })

  expectNoConsoleIssues(consoleIssues)
})

test("workbench video pane keeps the empty selection prompt to one line", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await gotoWorkbench(page)
  await expect(page.getByText("请先在左侧选择一个视频实例。")).toBeVisible()
  await expect(page.getByText("当前视频还未进入可播放状态")).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test("workbench empty content tree avoids duplicate setup prompt", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page, { contentState: "empty" })

  await gotoWorkbench(page)
  await expect(page.getByText("先绑定并授权素材目录")).toBeVisible()
  const contentTreeCard = page.locator("#workbench-content-tree")
  await expect(contentTreeCard.getByText("尚未绑定素材目录")).toBeVisible()
  await expect(contentTreeCard.getByText("当前还没有学习对象")).toHaveCount(0)
  await expect(contentTreeCard.getByRole("link", { name: "前往项目设置" })).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test(journeyIds.review, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await recordJourney(journeyIds.review, async () => {
    await page.goto(projectPath("/recommended-reviews"))
    await expect(page.getByText("什么是自动化测试？")).toBeVisible()
    await page.getByRole("button", { name: "跳过" }).click()
    await expect(page.getByText("用程序验证用户关键流程。")).toBeVisible()
  })

  expectNoConsoleIssues(consoleIssues)
})
