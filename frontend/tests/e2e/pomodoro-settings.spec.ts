import { expect, test } from "@playwright/test"

import { collectConsoleIssues, expectNoConsoleIssues } from "../fixtures/app-checks"
import { installMockApi } from "../fixtures/mock-api"
import { journeyIds } from "../fixtures/journeys"
import { recordJourney } from "../fixtures/journey-result"

test(journeyIds.pomodoro, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await recordJourney(journeyIds.pomodoro, async () => {
    await page.goto("/pomodoro")
    await expect(page.getByText("番茄钟")).toBeVisible()
    await page.getByRole("button", { name: "统计" }).click()
    await expect(page.getByText("今天还没有可统计的番茄记录。")).toBeVisible()
  })

  expectNoConsoleIssues(consoleIssues)
})

test(journeyIds.settings, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await recordJourney(journeyIds.settings, async () => {
    await page.goto("/settings/global")
    await expect(page.getByText("全局配置")).toBeVisible()
    await expect(page.locator("#root")).not.toBeEmpty()
  })

  expectNoConsoleIssues(consoleIssues)
})
