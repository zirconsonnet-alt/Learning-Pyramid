import { expect, test } from "@playwright/test"

import { collectConsoleIssues, expectHealthyPage, expectNoConsoleIssues } from "../fixtures/app-checks"
import { installMockApi } from "../fixtures/mock-api"
import { journeyIds } from "../fixtures/journeys"
import { recordJourney } from "../fixtures/journey-result"

test(journeyIds.mainNavigation, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await recordJourney(journeyIds.mainNavigation, async () => {
    await page.goto("/projects")
    await expect(page.getByRole("heading", { name: "所有学科" })).toBeVisible()
    await page.getByRole("button", { name: /全局/ }).click()
    await page.getByText("用户指南").click()
    await expect(page).toHaveURL(/\/guide$/)
    await expect(page.getByText("产品指南")).toBeVisible()
    await expectHealthyPage(page, "/guide")
  })

  expectNoConsoleIssues(consoleIssues)
})
