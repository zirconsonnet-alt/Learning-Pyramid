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

test("auth page removes secondary helper copy", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page, { authState: "signed-out" })

  await page.goto("/login")
  await expect(page.getByRole("heading", { name: "欢迎回来" })).toBeVisible()
  await expect(page.getByText("使用邮箱和密码登录。")).toHaveCount(0)

  await page.goto("/login?mode=verify&email=test@example.com&waitToken=wait_e2e")
  await expect(page.getByRole("heading", { name: "等待邮箱验证" })).toBeVisible()
  await expect(page.getByText("验证邮件已经发出。你可以在手机或电脑上打开邮箱完成激活，当前页面会自动继续。")).toHaveCount(0)
  await expect(page.getByRole("button", { name: "重新注册" })).toHaveCount(0)
  await expect(page.getByRole("button", { name: "返回登录" })).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test(journeyIds.membership, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await recordJourney(journeyIds.membership, async () => {
    await page.goto("/membership")
    await expect(page.getByRole("heading", { name: "会员中心" })).toBeVisible()
    await expect(page.getByRole("link", { name: "返回个人中心" })).toHaveCount(0)
    await expect(page.getByRole("button", { name: /立即开通|立即续费|继续支付/ })).toBeVisible()
    await page.getByRole("button", { name: "复制邀请码" }).click()
    await expect(page.getByText("当前状态")).toBeVisible()
  })

  expectNoConsoleIssues(consoleIssues)
})

test("membership checkout opens a dedicated payment dialog after order creation", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.goto("/membership")
  await page.getByRole("button", { name: "立即续费" }).click()
  await expect(page.getByRole("heading", { name: "开通会员套餐" })).toBeVisible()

  await page.getByRole("button", { name: "确认并继续" }).click()

  await expect(page.getByRole("heading", { name: "继续支付" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "开通会员套餐" })).toHaveCount(0)
  await expect(page.getByText("待支付订单", { exact: true })).toBeVisible()

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
