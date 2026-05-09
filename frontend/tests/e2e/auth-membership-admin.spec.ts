import { expect, test } from "@playwright/test"

import { collectConsoleIssues, expectNoConsoleIssues } from "../fixtures/app-checks"
import { installMockApi } from "../fixtures/mock-api"
import { journeyIds } from "../fixtures/journeys"
import { recordJourney } from "../fixtures/journey-result"

test(journeyIds.auth, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page, { authState: "signed-out" })

  await recordJourney(journeyIds.auth, async () => {
    await page.goto("/login?mode=register")
    await expect(page.getByRole("heading", { name: "创建账号" })).toBeVisible()
    await page.getByLabel("邮箱").fill("new-user@example.com")
    await page.getByLabel("密码").fill("password123")
    await expect(page.getByRole("button", { name: "注册并进入" })).toBeEnabled()
  })

  expectNoConsoleIssues(consoleIssues)
})

test(journeyIds.membership, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await recordJourney(journeyIds.membership, async () => {
    await page.goto("/membership")
    await expect(page.getByRole("heading", { name: "会员中心" })).toBeVisible()
    await page.getByRole("button", { name: "复制邀请码" }).click()
    await expect(page.getByText("当前状态")).toBeVisible()
  })

  expectNoConsoleIssues(consoleIssues)
})

test(journeyIds.admin, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await recordJourney(journeyIds.admin, async () => {
    await page.goto("/admin")
    await expect(page.getByRole("heading", { name: "运营控制台" })).toBeVisible()
    await expect(page.getByText("平台治理")).toBeVisible()
  })

  expectNoConsoleIssues(consoleIssues)
})
