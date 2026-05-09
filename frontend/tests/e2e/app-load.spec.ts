import { expect, test } from "@playwright/test"

import { expectHealthyPage, expectNoConsoleIssues, collectConsoleIssues } from "../fixtures/app-checks"
import { installMockApi } from "../fixtures/mock-api"
import { journeyIds } from "../fixtures/journeys"
import { recordJourney } from "../fixtures/journey-result"

test(journeyIds.appLoad, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await recordJourney(journeyIds.appLoad, async () => {
    await page.goto("/")
    await expect(page.getByRole("link", { name: /LearningPyramid/ })).toBeVisible()
    await expectHealthyPage(page, /\/$/)
  })

  expectNoConsoleIssues(consoleIssues)
})
