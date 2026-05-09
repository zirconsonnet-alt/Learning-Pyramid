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
