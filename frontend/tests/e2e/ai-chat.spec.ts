import { expect, test } from "@playwright/test"

import { collectConsoleIssues, expectNoConsoleIssues } from "../fixtures/app-checks"
import { installMockApi } from "../fixtures/mock-api"
import { journeyIds } from "../fixtures/journeys"
import { recordJourney } from "../fixtures/journey-result"
import { projectPath } from "../fixtures/page-objects"
import { learningObjectNode } from "../fixtures/test-data"

test(journeyIds.aiChat, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await recordJourney(journeyIds.aiChat, async () => {
    await page.goto(projectPath("/ai-chat"))
    await expect(page.getByText("AI问答")).toBeVisible()
    await page.getByRole("button", { name: learningObjectNode.title }).click()
    await page.getByRole("textbox", { name: new RegExp(`围绕.*${learningObjectNode.title}`) }).fill("请解释自动化测试")
    await page.getByRole("button", { name: "发送" }).click()
    await expect(page.getByText("这是自动化测试的确定性 AI 回复。")).toBeVisible()
  })

  expectNoConsoleIssues(consoleIssues)
})
