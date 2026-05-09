import { expect, test } from "@playwright/test"

import { collectConsoleIssues, expectNoConsoleIssues } from "../fixtures/app-checks"
import { installMockApi } from "../fixtures/mock-api"
import { journeyIds } from "../fixtures/journeys"
import { recordJourney } from "../fixtures/journey-result"
import { gotoWorkbench } from "../fixtures/page-objects"

test(journeyIds.mediaUpload, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await recordJourney(journeyIds.mediaUpload, async () => {
    await gotoWorkbench(page)
    await expect(page.getByRole("heading", { name: "内容目录" })).toBeVisible()
    await expect(page.getByRole("heading", { name: "复述点录入" })).toBeVisible()
    await page.getByRole("button", { name: "层推进与学习任务" }).click()
    await expect(page.getByRole("heading", { name: "层推进与学习任务" })).toBeVisible()
  })

  expectNoConsoleIssues(consoleIssues)
})
