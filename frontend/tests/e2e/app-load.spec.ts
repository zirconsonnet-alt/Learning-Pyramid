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
  await expect(page.getByText("学习视图")).toBeVisible()
  await expect.poll(() => scopedAuditLogRequested).toBe(true)
  expect(oldAuditLogRequested).toBe(false)

  expectNoConsoleIssues(consoleIssues)
})
