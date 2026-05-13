import { expect, test, type Page } from "@playwright/test"

import { collectConsoleIssues, expectNoConsoleIssues } from "../fixtures/app-checks"
import { installMockApi } from "../fixtures/mock-api"
import { journeyIds } from "../fixtures/journeys"
import { recordJourney } from "../fixtures/journey-result"

async function installWeixinBridge(page: Page) {
  await page.addInitScript(() => {
    const target = window as unknown as { WeixinJSBridge?: { invoke: (_name: string, _params: Record<string, string>, callback: (result?: { err_msg?: string }) => void) => void } }
    target.WeixinJSBridge = {
      invoke: (_name: string, _params: Record<string, string>, callback: (result?: { err_msg?: string }) => void) => callback({ err_msg: "requestMerchantTransfer:ok" }),
    }
  })
}

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
  await installMockApi(page, { authState: "signed-out", systemCapabilities: { emailVerificationEnabled: true } })

  await page.goto("/login?mode=register")
  await expect(page.getByRole("heading", { name: "创建账号" })).toBeVisible()
  await expect(page.getByText("注册后需要先完成邮箱验证，再进入工作区。")).toHaveCount(0)

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

test("membership WeChat payment dialog relies on automatic status refresh", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page, { membershipProvider: "wechat_native" })

  await page.goto("/membership")
  await page.getByRole("button", { name: "立即续费" }).click()
  await page.getByRole("button", { name: "确认并继续" }).click()

  await expect(page.getByRole("heading", { name: "继续支付" })).toBeVisible()
  await expect(page.getByAltText("微信支付二维码")).toBeVisible()
  await expect(page.getByText("支付成功后页面会自动刷新")).toBeVisible()
  await expect(page.getByRole("button", { name: /同步/ })).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test("membership withdrawal confirmation dialog closes after payout becomes terminal", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page, { withdrawalScenario: "awaiting_then_succeeded" })

  await page.goto("/membership")
  await page.getByRole("button", { name: "申请提现" }).click()
  const dialog = page.getByRole("dialog", { name: "微信扫码确认收款" })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByText(/membership\/wechat-payout-confirm/)).toHaveCount(0)
  await expect(dialog).toHaveCount(0, { timeout: 10_000 })

  expectNoConsoleIssues(consoleIssues)
})

test("membership withdrawal confirmation dialog closes after WeChat confirmation starts", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page, { withdrawalScenario: "awaiting_then_processing" })

  await page.goto("/membership")
  await page.getByRole("button", { name: "申请提现" }).click()
  const dialog = page.getByRole("dialog", { name: "微信扫码确认收款" })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByText(/membership\/wechat-payout-confirm/)).toHaveCount(0)
  await expect(dialog).toHaveCount(0, { timeout: 10_000 })

  expectNoConsoleIssues(consoleIssues)
})

test("wechat payout confirmation page shows a readable account label for scanned withdrawals", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.goto("/membership/wechat-payout-confirm?attempt=bind_e2e&state=state_e2e&code=code_e2e")
  await expect(page.getByRole("heading", { name: "确认微信提现" })).toBeVisible()
  await expect(page.getByText("自动化测试账号（LP-E2E）")).toBeVisible()
  await expect(page.getByText("user_e2e")).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test("wechat payout confirmation page disables repeated scanned withdrawal confirmation after invoking WeChat", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  let confirmationStartedRequested = false
  page.on("request", (request) => {
    const url = new URL(request.url())
    if (request.method() === "POST" && url.pathname === "/api/commissions/withdrawals/mwd_e2e/wechat-confirmation/started") {
      confirmationStartedRequested = true
    }
  })
  await installMockApi(page)
  await installWeixinBridge(page)

  await page.goto("/membership/wechat-payout-confirm?attempt=bind_e2e&state=state_e2e&code=code_e2e")
  await page.getByRole("button", { name: "确认并提现" }).click()

  await expect(page.getByRole("heading", { name: "已提交微信确认" })).toBeVisible()
  await expect(page.getByRole("button", { name: "确认并提现" })).toHaveCount(0)
  await expect(page.getByText("请回到电脑端查看到账状态。")).toBeVisible()
  await expect.poll(() => confirmationStartedRequested).toBe(true)

  expectNoConsoleIssues(consoleIssues)
})

test("wechat withdrawal confirmation page disables repeated confirmation after invoking WeChat", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  let confirmationStartedRequested = false
  page.on("request", (request) => {
    const url = new URL(request.url())
    if (request.method() === "POST" && url.pathname === "/api/commissions/withdrawals/mwd_e2e/wechat-confirmation/started") {
      confirmationStartedRequested = true
    }
  })
  await installMockApi(page)
  await installWeixinBridge(page)

  await page.goto("/membership/wechat-payout-confirm?withdrawal=mwd_e2e&token=token_e2e")
  await page.getByRole("button", { name: "继续微信确认" }).click()

  await expect(page.getByRole("heading", { name: "已提交微信确认" })).toBeVisible()
  await expect(page.getByRole("button", { name: "继续微信确认" })).toHaveCount(0)
  await expect(page.getByText("请回到电脑端查看到账状态。")).toBeVisible()
  await expect.poll(() => confirmationStartedRequested).toBe(true)

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
