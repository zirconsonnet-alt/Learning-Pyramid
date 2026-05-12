import { expect, test } from "@playwright/test"

import { collectConsoleIssues, expectNoConsoleIssues } from "../fixtures/app-checks"
import { installMockApi } from "../fixtures/mock-api"
import { journeyIds } from "../fixtures/journeys"
import { recordJourney } from "../fixtures/journey-result"
import { openSubject, projectPath } from "../fixtures/page-objects"
import { project } from "../fixtures/test-data"

test(journeyIds.subjectProjectEntry, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await recordJourney(journeyIds.subjectProjectEntry, async () => {
    await openSubject(page)
    await expect(page.getByText(project.title)).toBeVisible()
    await page.getByRole("button", { name: "进入工作台" }).click()
    await expect(page).toHaveURL(new RegExp(projectPath("/workbench")))
    await expect(page.getByText("工作状态")).toBeVisible()
  })

  expectNoConsoleIssues(consoleIssues)
})

test("project settings shows concise convergence template copy", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.goto(projectPath("/settings"))
  await expect(page.getByText("复习链模板")).toBeVisible()
  await expect(page.getByText("推送上次复习时不记得的重点")).toBeVisible()
  await expect(page.getByText("完成一轮后决定是否继续生成复习任务。")).toHaveCount(0)
  await expect(page.getByText("这个步骤没有额外参数")).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})
