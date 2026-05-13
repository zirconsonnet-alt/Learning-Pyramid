import { expect, test } from "@playwright/test"

import { collectConsoleIssues, expectNoConsoleIssues } from "../fixtures/app-checks"
import { installMockApi } from "../fixtures/mock-api"
import { testUser } from "../fixtures/test-data"

test("llm settings fields are not exposed as login credentials", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.goto("/settings/global")
  await expect(page.getByText("大模型配置", { exact: true })).toBeVisible()

  const baseUrlInput = page.getByLabel("Base URL")
  const modelInput = page.getByLabel("模型名")
  const apiKeyInput = page.getByLabel("API 密钥")

  await expect(baseUrlInput).toHaveAttribute("name", "userLlmBaseUrl")
  await expect(baseUrlInput).toHaveAttribute("autocomplete", "off")
  await expect(modelInput).toHaveAttribute("name", "userLlmModelName")
  await expect(modelInput).toHaveAttribute("autocomplete", "off")
  await expect(modelInput).not.toHaveValue(testUser.email)
  await expect(apiKeyInput).toHaveAttribute("name", "userLlmApiKey")
  await expect(apiKeyInput).toHaveAttribute("autocomplete", "new-password")

  expectNoConsoleIssues(consoleIssues)
})
