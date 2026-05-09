import { expect, test } from "@playwright/test"

import { collectConsoleIssues, expectNoConsoleIssues } from "../fixtures/app-checks"
import { installMockApi } from "../fixtures/mock-api"
import { journeyIds } from "../fixtures/journeys"
import { recordJourney } from "../fixtures/journey-result"
import { gotoWorkbench, projectPath } from "../fixtures/page-objects"
import { project } from "../fixtures/test-data"

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
