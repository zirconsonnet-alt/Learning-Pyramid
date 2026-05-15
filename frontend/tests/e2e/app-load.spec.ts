import { expect, test } from "@playwright/test"

import { expectHealthyPage, expectNoConsoleIssues, collectConsoleIssues } from "../fixtures/app-checks"
import { installMockApi } from "../fixtures/mock-api"
import { journeyIds } from "../fixtures/journeys"
import { recordJourney } from "../fixtures/journey-result"
import { project, subject } from "../fixtures/test-data"

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

test("home guide dropdown matches section headings", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.goto("/")
  const header = page.locator(".lp-showcase-site-header")
  await expect(header).toHaveClass(/theme-shell-header/)
  await expect(header.locator(".lp-showcase-brand-mark")).toHaveCSS("width", "40px")
  const guideButton = page.getByRole("button", { name: /^导览/ })
  await expect(guideButton).toHaveText("导览")
  await expect(guideButton).toHaveCSS("border-radius", "12px")

  await guideButton.hover()
  const guideMenu = page.locator(".lp-showcase-nav-dropdown-menu")
  await expect(guideMenu).toBeVisible()

  const expectedItems = ["方法", "改变，从现在开始", "会员", "常见问题"]
  await expect(guideMenu.getByRole("link")).toHaveText(expectedItems)

  await guideMenu.getByRole("link", { name: "改变，从现在开始" }).click()
  await expect(page).toHaveURL(/#onboarding$/)
  await expect(page.locator("#onboarding")).toBeInViewport()

  expectNoConsoleIssues(consoleIssues)
})

test("home and guide surface the stable-use FAQ and onboarding guide entries", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.goto("/")
  const homeFaq = page.locator("#faq")
  await expect(homeFaq.locator(".lp-showcase-faq-item")).toHaveCount(4)
  await expect(homeFaq.getByRole("heading", { name: "如何长期稳定使用？" })).toBeVisible()
  await expect(homeFaq.getByText("使用电脑浏览器访问即可")).toBeVisible()
  await expect(homeFaq.getByText("为什么佣金不立即生效？")).toHaveCount(0)

  await page.goto("/guide")
  await expect(page.locator(".theme-card-main h2").first()).toHaveText("如何长期稳定使用？")
  await expect(page.getByText("使用电脑浏览器访问即可")).toBeVisible()

  await expect(page.getByRole("navigation", { name: "首页指引" }).getByRole("link")).toHaveText([
    "去管理专业课的学习",
    "去体验自动复习推送",
    "去感受AI学习赋能",
    "去定明早9点的番茄钟",
  ])

  expectNoConsoleIssues(consoleIssues)
})

test("profile learning view uses scoped audit log endpoint", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  let oldAuditLogRequested = false
  let scopedAuditLogRequested = false

  page.on("request", (request) => {
    const pathname = new URL(request.url()).pathname
    if (pathname === `/api/projects/${project.projectId}/audit-log-events`) oldAuditLogRequested = true
    if (pathname === `/api/subjects/${subject.subjectId}/projects/${project.projectId}/audit-log-events`) scopedAuditLogRequested = true
  })

  await installMockApi(page)

  await page.goto("/profile")
  await expect(page.getByText("账户信息", { exact: true })).toBeVisible()
  await expect(page.getByText("进入会员中心")).toHaveCount(0)
  await expect(page.getByText("学习视图", { exact: true })).toBeVisible()
  await expect.poll(() => scopedAuditLogRequested).toBe(true)
  expect(oldAuditLogRequested).toBe(false)

  expectNoConsoleIssues(consoleIssues)
})

test("account menu entry pages share the eyebrow title pattern", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.goto("/profile")
  await expect(page.getByText("Profile Card", { exact: true })).toBeVisible()
  await expect(page.getByText("账户信息", { exact: true })).toBeVisible()

  await page.goto("/friends")
  await expect(page.getByText("Friend Circle", { exact: true })).toBeVisible()
  await expect(page.getByText("好友中心", { exact: true })).toBeVisible()

  await page.goto("/membership")
  await expect(page.getByText("Member Center", { exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "会员中心" })).toBeVisible()

  expectNoConsoleIssues(consoleIssues)
})
