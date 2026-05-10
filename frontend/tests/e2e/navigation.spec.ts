import { expect, test } from "@playwright/test"

import { collectConsoleIssues, expectHealthyPage, expectNoConsoleIssues } from "../fixtures/app-checks"
import { installMockApi } from "../fixtures/mock-api"
import { journeyIds } from "../fixtures/journeys"
import { recordJourney } from "../fixtures/journey-result"
import { project, subject } from "../fixtures/test-data"

test(journeyIds.mainNavigation, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await recordJourney(journeyIds.mainNavigation, async () => {
    await page.goto("/subjects")
    await expect(page.getByRole("heading", { name: "所有学科" })).toBeVisible()
    await page.getByRole("button", { name: /全局/ }).click()
    await page.getByText("用户指南").click()
    await expect(page).toHaveURL(/\/guide$/)
    await expect(page.getByText("产品指南")).toBeVisible()
    await expectHealthyPage(page, "/guide")
  })

  expectNoConsoleIssues(consoleIssues)
})

test("global pages do not reuse stale workbench project as current project", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)
  await page.addInitScript(({ subjectId, projectId }) => {
    window.localStorage.setItem(
      "plm-app",
      JSON.stringify({
        state: {
          selectedSubjectId: subjectId,
          selectedWorkbenchProjectId: projectId,
          selectedWorkbenchProjectRef: { subjectId, projectId },
          recentSubjectIds: [subjectId],
          recentWorkbenchProjectIds: [projectId],
          recentWorkbenchProjectRefs: [{ subjectId, projectId }],
        },
        version: 0,
      }),
    )
  }, { subjectId: subject.subjectId, projectId: project.projectId })

  await page.goto("/pomodoro")
  await expect(page.getByRole("button", { name: /全局/ })).toBeVisible()
  await expect(page.getByRole("button", { name: /系统/ })).toBeVisible()
  await expect(page.getByRole("button", { name: /当前项目|自动化测试项目/ })).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})
