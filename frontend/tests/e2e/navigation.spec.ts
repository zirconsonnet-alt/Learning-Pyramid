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

test("global pages keep the explicitly selected project context in the header", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)
  await page.addInitScript(({ subjectId, projectId }) => {
    window.localStorage.setItem(
      "plm-app",
      JSON.stringify({
        state: {
          selectedSubjectId: subjectId,
          selectedWorkbenchProjectId: projectId,
          selectedWorkbenchProjectRef: { subjectId, scopedProjectId: projectId },
          recentSubjectIds: [subjectId],
          recentWorkbenchProjectIds: [projectId],
          recentWorkbenchProjectRefs: [{ subjectId, scopedProjectId: projectId }],
        },
        version: 0,
      }),
    )
  }, { subjectId: subject.subjectId, projectId: project.projectId })

  await page.goto("/pomodoro")
  await expect(page.getByRole("button", { name: /全局/ })).toBeVisible()
  await expect(page.getByRole("button", { name: /系统/ })).toBeVisible()
  await expect(page.getByRole("button", { name: new RegExp(`学科.*${subject.title}`) })).toBeVisible()
  await expect(page.getByRole("button", { name: new RegExp(`项目.*${project.title}`) })).toBeVisible()

  expectNoConsoleIssues(consoleIssues)
})

test("global pages do not expose unresolved project identifiers in the header", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)
  await page.addInitScript(() => {
    window.localStorage.setItem(
      "plm-app",
      JSON.stringify({
        state: {
          selectedSubjectId: "proj_000022",
          selectedWorkbenchProjectId: "proj_000066",
          selectedWorkbenchProjectRef: { subjectId: "proj_000022", scopedProjectId: "proj_000066" },
          recentSubjectIds: ["proj_000022"],
          recentWorkbenchProjectIds: ["proj_000066"],
          recentWorkbenchProjectRefs: [{ subjectId: "proj_000022", scopedProjectId: "proj_000066" }],
        },
        version: 0,
      }),
    )
  })

  await page.goto("/pomodoro")
  await expect(page.getByRole("button", { name: /全局/ })).toBeVisible()
  await expect(page.getByText("proj_000022")).toHaveCount(0)
  await expect(page.getByText("proj_000066")).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test("navigating from a project page to guide keeps the current project context in the header", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.goto(`/subjects/${subject.subjectId}/projects/${project.projectId}/settings`)
  await expect(page.getByText("项目设置")).toBeVisible()
  await expect(page.getByRole("button", { name: new RegExp(`项目.*${project.title}`) })).toBeVisible()

  await page.getByRole("button", { name: /全局/ }).click()
  await page.getByText("用户指南").click()
  await expect(page).toHaveURL(/\/guide$/)
  await expect(page.getByText("产品指南")).toBeVisible()
  await expect(page.getByRole("button", { name: new RegExp(`学科.*${subject.title}`) })).toBeVisible()
  await expect(page.getByRole("button", { name: new RegExp(`项目.*${project.title}`) })).toBeVisible()

  expectNoConsoleIssues(consoleIssues)
})
