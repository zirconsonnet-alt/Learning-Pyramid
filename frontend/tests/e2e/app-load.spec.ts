import { expect, test } from "@playwright/test"

import { expectHealthyPage, expectNoConsoleIssues, collectConsoleIssues } from "../fixtures/app-checks"
import { installMockApi } from "../fixtures/mock-api"
import { journeyIds } from "../fixtures/journeys"
import { recordJourney } from "../fixtures/journey-result"
import { instance, project, subject } from "../fixtures/test-data"

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

test("home does not show the mobile device notice", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/")
  await expectHealthyPage(page, /\/$/)
  await expect(page.getByRole("note", { name: "电脑端使用提示" })).toHaveCount(0)

  await page.setViewportSize({ width: 1280, height: 900 })
  await page.reload()
  await expect(page.getByRole("note", { name: "电脑端使用提示" })).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test("home mobile carousel uses swipe and two compact columns", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/")
  await expectHealthyPage(page, /\/$/)

  const carousel = page.locator(".lp-showcase-carousel-viewport")
  await expect(carousel).toBeVisible()
  await expect(page.getByRole("button", { name: "查看上一组理由" })).toBeHidden()
  await expect(page.getByRole("button", { name: "查看下一组理由" })).toBeHidden()

  const mobileCarouselLayout = await page.evaluate(() => {
    const viewport = document.querySelector(".lp-showcase-carousel-viewport")?.getBoundingClientRect()
    const slide = document.querySelector(".lp-showcase-carousel-slide")?.getBoundingClientRect()
    const points = Array.from(document.querySelectorAll(".lp-showcase-carousel-slide:first-child .lp-showcase-carousel-point")).map((element) => {
      const rect = element.getBoundingClientRect()
      return {
        left: Math.round(rect.left),
        top: Math.round(rect.top),
        width: Math.round(rect.width),
      }
    })
    return {
      scrollWidth: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth),
      viewportWidth: window.innerWidth,
      viewportWidthPx: viewport ? Math.round(viewport.width) : 0,
      slideWidth: slide ? Math.round(slide.width) : 0,
      firstRowCount: points.filter((point) => point.top === points[0]?.top).length,
      pointWidths: points.map((point) => point.width),
    }
  })

  expect(mobileCarouselLayout.scrollWidth, JSON.stringify(mobileCarouselLayout, null, 2)).toBeLessThanOrEqual(mobileCarouselLayout.viewportWidth)
  expect(mobileCarouselLayout.slideWidth, JSON.stringify(mobileCarouselLayout, null, 2)).toBe(mobileCarouselLayout.viewportWidthPx)
  expect(mobileCarouselLayout.firstRowCount, JSON.stringify(mobileCarouselLayout, null, 2)).toBe(2)
  await expect(carousel).toHaveCSS("touch-action", "pan-y")
  for (const pointWidth of mobileCarouselLayout.pointWidths) {
    expect(pointWidth, JSON.stringify(mobileCarouselLayout, null, 2)).toBeLessThanOrEqual(170)
  }

  await expect(page.getByText("01 / 04")).toBeVisible()
  const box = await carousel.boundingBox()
  if (!box) throw new Error("home carousel did not render")
  const touchClient = await page.context().newCDPSession(page)
  const y = Math.round(box.y + box.height * 0.5)
  async function swipeCarousel(startRatio: number, endRatio: number) {
    const startX = Math.round(box.x + box.width * startRatio)
    const endX = Math.round(box.x + box.width * endRatio)
    await touchClient.send("Input.dispatchTouchEvent", {
      type: "touchStart",
      touchPoints: [{ x: startX, y, id: 1 }],
    })
    for (let step = 1; step <= 8; step += 1) {
      const x = Math.round(startX + ((endX - startX) * step) / 8)
      await touchClient.send("Input.dispatchTouchEvent", {
        type: "touchMove",
        touchPoints: [{ x, y, id: 1 }],
      })
    }
    await touchClient.send("Input.dispatchTouchEvent", {
      type: "touchEnd",
      touchPoints: [],
    })
  }

  await swipeCarousel(0.72, 0.22)
  await expect(page.getByText("02 / 04")).toBeVisible()
  await swipeCarousel(0.22, 0.72)
  await expect(page.getByText("01 / 04")).toBeVisible()

  expectNoConsoleIssues(consoleIssues)
})

test("home mobile content sections use compact grids", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/")
  await expectHealthyPage(page, /\/$/)

  const methodGrid = page.locator(".lp-showcase-method-grid")
  const onboardingGrid = page.locator(".lp-showcase-onboarding-grid")
  const membershipPlanGrid = page.locator(".lp-showcase-membership-plan-grid")
  await expect(methodGrid).toBeVisible()
  await expect(onboardingGrid).toBeVisible()
  await expect(membershipPlanGrid).toBeVisible()

  const compactLayout = await page.evaluate(() => {
    function allHidden(selector: string) {
      const items = Array.from(document.querySelectorAll(selector))
      return items.length > 0 && items.every((element) => window.getComputedStyle(element).display === "none")
    }

    function firstRowCount(selector: string) {
      const items = Array.from(document.querySelectorAll(selector)).map((element) => {
        const rect = element.getBoundingClientRect()
        return {
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          top: Math.round(rect.top),
          height: Math.round(rect.height),
          width: Math.round(rect.width),
        }
      })
      return {
        items,
        count: items.filter((item) => item.top === items[0]?.top).length,
      }
    }

    const method = firstRowCount(".lp-showcase-method-grid > .lp-showcase-method-card")
    const onboarding = firstRowCount(".lp-showcase-onboarding-grid > .lp-showcase-step")
    const membershipPlans = firstRowCount(".lp-showcase-membership-plan-grid > .lp-showcase-membership-price-block")
    const membershipPanels = firstRowCount(".lp-showcase-membership-grid > .lp-showcase-membership-panel")
    const faq = firstRowCount(".lp-showcase-faq-grid > .lp-showcase-faq-item")
    return {
      viewportWidth: window.innerWidth,
      scrollWidth: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth),
      methodIconsHidden: allHidden(".lp-showcase-method-grid .lp-showcase-feature-icon"),
      onboardingNumbersHidden: allHidden(".lp-showcase-onboarding-grid .lp-showcase-step-no"),
      method,
      onboarding,
      membershipPlans,
      membershipPanels,
      faq,
    }
  })

  expect(compactLayout.scrollWidth, JSON.stringify(compactLayout, null, 2)).toBeLessThanOrEqual(compactLayout.viewportWidth)
  expect(compactLayout.methodIconsHidden, JSON.stringify(compactLayout, null, 2)).toBe(true)
  expect(compactLayout.onboardingNumbersHidden, JSON.stringify(compactLayout, null, 2)).toBe(true)
  expect(compactLayout.method.count, JSON.stringify(compactLayout, null, 2)).toBe(3)
  expect(compactLayout.onboarding.count, JSON.stringify(compactLayout, null, 2)).toBe(2)
  expect(compactLayout.membershipPlans.count, JSON.stringify(compactLayout, null, 2)).toBe(2)
  expect(compactLayout.membershipPanels.count, JSON.stringify(compactLayout, null, 2)).toBe(2)
  expect(compactLayout.faq.count, JSON.stringify(compactLayout, null, 2)).toBe(2)
  expect(
    Math.abs(compactLayout.membershipPanels.items[0].height - compactLayout.membershipPanels.items[1].height),
    JSON.stringify(compactLayout, null, 2),
  ).toBeLessThanOrEqual(1)
  for (const item of compactLayout.method.items) {
    expect(item.width, JSON.stringify(compactLayout, null, 2)).toBeLessThanOrEqual(120)
  }
  for (const item of compactLayout.membershipPlans.items) {
    expect(item.width, JSON.stringify(compactLayout, null, 2)).toBeGreaterThanOrEqual(130)
  }

  expectNoConsoleIssues(consoleIssues)
})

test("project mobile navigation stays within the viewport", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/subjects/${subject.subjectId}/projects/${project.projectId}/workbench`)
  await expectHealthyPage(page, new RegExp(`/subjects/${subject.subjectId}/projects/${project.projectId}/workbench$`))

  const header = page.locator("header.theme-shell-header")
  await expect(header.getByRole("link", { name: "查看公开首页" })).toBeVisible()
  await expect(header.getByText("LearningPyramid")).toHaveCount(0)
  await header.getByRole("button", { name: "打开导航" }).click()

  const mobileNav = page.getByRole("navigation", { name: "移动导航" })
  await expect(mobileNav).toBeVisible()
  const navBox = await mobileNav.boundingBox()
  if (!navBox) throw new Error("mobile navigation menu did not render")
  expect(Math.floor(navBox.x)).toBeGreaterThanOrEqual(0)
  expect(Math.ceil(navBox.x + navBox.width)).toBeLessThanOrEqual(390)

  const scrollWidth = await page.evaluate(() => Math.max(document.body.scrollWidth, document.documentElement.scrollWidth))
  expect(scrollWidth).toBeLessThanOrEqual(390)

  expectNoConsoleIssues(consoleIssues)
})

test("workbench mobile learning object tree keeps deep nesting within the viewport", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  const deepLearningObjectNodes = [
    {
      kind: "container",
      projectId: project.projectId,
      nodeId: "deep_root",
      parentId: null,
      children: ["deep_level_1"],
      title: "第一部分：一个很长很长的根目录标题",
    },
    ...Array.from({ length: 7 }, (_, index) => {
      const level = index + 1
      return {
        kind: "container",
        projectId: project.projectId,
        nodeId: `deep_level_${level}`,
        parentId: level === 1 ? "deep_root" : `deep_level_${level - 1}`,
        children: [level === 7 ? "deep_leaf" : `deep_level_${level + 1}`],
        title: `第 ${level} 层目录：这是一段用于验证手机端不会横向溢出的长标题`,
      }
    }),
    {
      kind: "leaf",
      projectId: project.projectId,
      nodeId: "deep_leaf",
      parentId: "deep_level_7",
      instanceId: instance.instanceId,
      relativePath: "很深/很深/很深/很深/第一讲 自动化导论.mp4",
      source: "browser",
      title: "很深层级下的第一讲自动化导论，标题足够长用于截断验证",
    },
  ]
  await installMockApi(page, { learningObjectNodes: deepLearningObjectNodes })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/subjects/${subject.subjectId}/projects/${project.projectId}/workbench`)
  await expectHealthyPage(page, new RegExp(`/subjects/${subject.subjectId}/projects/${project.projectId}/workbench$`))

  await expect(page.locator("#workbench-mobile-content-tree")).toBeHidden()
  await page.getByRole("button", { name: /内容目录/ }).click()
  await expect(page.getByRole("dialog", { name: "内容目录" })).toBeVisible()
  const tree = page.locator("#workbench-mobile-content-tree [data-guide-tour='learning-object-tree']")
  await expect(tree).toBeVisible()

  const layout = await page.evaluate(() => {
    const viewportWidth = window.innerWidth
    const buttons = Array.from(document.querySelectorAll("#workbench-mobile-content-tree [data-guide-tour='learning-object-tree'] button")).map((element) => {
      const rect = element.getBoundingClientRect()
      return {
        left: Math.floor(rect.left),
        right: Math.ceil(rect.right),
        width: Math.round(rect.width),
      }
    })
    return {
      viewportWidth,
      scrollWidth: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth),
      buttons,
    }
  })

  expect(layout.scrollWidth, JSON.stringify(layout, null, 2)).toBeLessThanOrEqual(layout.viewportWidth)
  expect(layout.buttons.length, JSON.stringify(layout, null, 2)).toBeGreaterThanOrEqual(8)
  for (const button of layout.buttons) {
    expect(button.left, JSON.stringify(layout, null, 2)).toBeGreaterThanOrEqual(0)
    expect(button.right, JSON.stringify(layout, null, 2)).toBeLessThanOrEqual(layout.viewportWidth)
  }

  expectNoConsoleIssues(consoleIssues)
})

test("workbench mobile opens study stats and directory dialogs above the player", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/subjects/${subject.subjectId}/projects/${project.projectId}/workbench`)
  await expectHealthyPage(page, new RegExp(`/subjects/${subject.subjectId}/projects/${project.projectId}/workbench$`))

  const toolButtons = page.locator("#workbench-mobile-tool-buttons")
  const videoPane = page.locator("#workbench-video-pane")
  const centerPanel = page.locator("#workbench-center-panel")
  await expect(toolButtons).toBeVisible()
  await expect(videoPane).toBeVisible()
  await expect(centerPanel).toBeVisible()
  await expect(page.locator("#workbench-status-card")).toBeHidden()
  await expect(page.locator("#workbench-content-tree")).toBeHidden()

  const toolButtonLayout = await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll("#workbench-mobile-tool-buttons button")).map((element) => {
      const rect = element.getBoundingClientRect()
      return {
        label: (element.textContent ?? "").replace(/\s+/g, ""),
        left: Math.round(rect.left),
        width: Math.round(rect.width),
      }
    })
    return { buttons }
  })
  expect(toolButtonLayout.buttons.slice(0, 2).map((button) => button.label), JSON.stringify(toolButtonLayout, null, 2)).toEqual([
    "内容目录",
    "学习统计",
  ])
  expect(
    Math.abs((toolButtonLayout.buttons[0]?.width ?? 0) - (toolButtonLayout.buttons[1]?.width ?? 0)),
    JSON.stringify(toolButtonLayout, null, 2),
  ).toBeLessThanOrEqual(1)
  expect(toolButtonLayout.buttons[0]?.left ?? 0, JSON.stringify(toolButtonLayout, null, 2)).toBeLessThan(
    toolButtonLayout.buttons[1]?.left ?? 0,
  )

  await expect(page.locator("#workbench-mobile-study-stats-dialog")).toBeHidden()
  await expect(page.locator("#workbench-mobile-directory-dialog")).toBeHidden()
  await expect(page.locator("#workbench-mobile-content-tree [data-guide-tour='learning-object-tree']")).toBeHidden()

  const closedLayout = await page.evaluate(() => {
    function top(selector: string) {
      const rect = document.querySelector(selector)?.getBoundingClientRect()
      return rect ? Math.round(rect.top + window.scrollY) : null
    }
    return {
      viewportWidth: window.innerWidth,
      scrollWidth: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth),
      toolTop: top("#workbench-mobile-tool-buttons"),
      videoTop: top("#workbench-video-pane"),
      centerTop: top("#workbench-center-panel"),
    }
  })

  expect(closedLayout.scrollWidth, JSON.stringify(closedLayout, null, 2)).toBeLessThanOrEqual(closedLayout.viewportWidth)
  expect(closedLayout.toolTop, JSON.stringify(closedLayout, null, 2)).not.toBeNull()
  expect(closedLayout.videoTop, JSON.stringify(closedLayout, null, 2)).not.toBeNull()
  expect(closedLayout.centerTop, JSON.stringify(closedLayout, null, 2)).not.toBeNull()
  expect(closedLayout.videoTop, JSON.stringify(closedLayout, null, 2)).toBeGreaterThan(closedLayout.toolTop ?? 0)
  expect(closedLayout.centerTop, JSON.stringify(closedLayout, null, 2)).toBeGreaterThan(closedLayout.videoTop ?? 0)

  await page.getByRole("button", { name: /学习统计/ }).click()
  await expect(page.getByRole("dialog", { name: "学习统计" })).toBeVisible()
  await expect(page.locator("#workbench-status-detail")).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(page.locator("#workbench-mobile-study-stats-dialog")).toBeHidden()

  await page.getByRole("button", { name: /内容目录/ }).click()
  await expect(page.getByRole("dialog", { name: "内容目录" })).toBeVisible()
  await expect(page.locator("#workbench-mobile-content-tree")).toBeVisible()

  await page.getByRole("button", { name: /第一讲 自动化导论/ }).click()
  await expect(page.locator("#workbench-mobile-content-tree")).toBeHidden()

  const openLayout = await page.evaluate(() => ({
    viewportWidth: window.innerWidth,
    scrollWidth: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth),
  }))
  expect(openLayout.scrollWidth, JSON.stringify(openLayout, null, 2)).toBeLessThanOrEqual(openLayout.viewportWidth)

  expectNoConsoleIssues(consoleIssues)
})

test("mobile account menu aligns with the header row", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/profile")
  await expectHealthyPage(page, /\/profile$/)

  const header = page.locator("header.theme-shell-header")
  await header.getByRole("button", { name: "打开账号菜单" }).click()

  const accountMenu = header.locator("[aria-label='账号菜单']")
  await expect(accountMenu).toBeVisible()

  const layout = await page.evaluate(() => {
    const viewportWidth = window.innerWidth
    const headerRow = document.querySelector("header.theme-shell-header .container > .relative")?.getBoundingClientRect()
    const menu = document.querySelector("header.theme-shell-header [aria-label='账号菜单']")?.getBoundingClientRect()
    return {
      viewportWidth,
      scrollWidth: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth),
      headerLeft: headerRow ? Math.floor(headerRow.left) : null,
      headerRight: headerRow ? Math.ceil(headerRow.right) : null,
      menuLeft: menu ? Math.floor(menu.left) : null,
      menuRight: menu ? Math.ceil(menu.right) : null,
    }
  })

  expect(layout.scrollWidth, JSON.stringify(layout, null, 2)).toBeLessThanOrEqual(layout.viewportWidth)
  expect(layout.menuLeft).toBe(layout.headerLeft)
  expect(layout.menuRight).toBe(layout.headerRight)

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
  let baiduCloudAccountRequested = false

  page.on("request", (request) => {
    const pathname = new URL(request.url()).pathname
    if (pathname === `/api/projects/${project.projectId}/audit-log-events`) oldAuditLogRequested = true
    if (pathname === `/api/subjects/${subject.subjectId}/projects/${project.projectId}/audit-log-events`) scopedAuditLogRequested = true
    if (pathname === "/api/profile/me/cloud-accounts/baidu-netdisk") baiduCloudAccountRequested = true
  })

  await installMockApi(page, { systemCapabilities: { baiduNetdiskEnabled: true } })

  await page.goto("/profile")
  await expect(page.getByText("账户信息", { exact: true })).toBeVisible()
  await expect(page.getByText("进入会员中心")).toHaveCount(0)
  await expect(page.getByText("学习视图", { exact: true })).toBeVisible()
  await expect(page.getByText("百度网盘", { exact: true })).toHaveCount(0)
  await expect.poll(() => scopedAuditLogRequested).toBe(true)
  expect(oldAuditLogRequested).toBe(false)
  expect(baiduCloudAccountRequested).toBe(false)

  expectNoConsoleIssues(consoleIssues)
})

test("subtitle tool public page only describes local subtitle generation", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.goto("/subtitle-tool")
  await expect(page.getByRole("heading", { name: "字幕工具" })).toBeVisible()
  await expect(page.getByText("本机批量生成本地视频字幕。")).toBeVisible()
  await expect(page.getByText("百度网盘")).toHaveCount(0)
  await expect(page.getByText("网盘")).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test("friends leaderboard uses a mobile list without horizontal overflow", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page, {
    friendLeaderboard: [
      {
        user: {
          userId: "user_e2e",
          publicUid: "LP-E2E",
          nickname: "自动化学习者",
          bio: "",
          avatarUrl: null,
        },
        isSelf: true,
        friendedAt: null,
        stats: {
          projectCount: 3,
          effectiveMs: 31_740_000,
          watchMs: 13_260_000,
          composeMs: 7_860_000,
          reviewMs: 7_920_000,
          qaMs: 360_000,
          learningCount: 64,
          reviewCount: 20,
          totalActions: 84,
          studyDays: 16,
          lastStudyAt: "2026-05-09T00:00:00Z",
        },
      },
      {
        user: {
          userId: "friend_e2e",
          publicUid: "LP-FRIEND",
          nickname: "朋友甲",
          bio: "",
          avatarUrl: null,
        },
        isSelf: false,
        friendedAt: "2026-05-01T00:00:00Z",
        stats: {
          projectCount: 2,
          effectiveMs: 12_600_000,
          watchMs: 5_400_000,
          composeMs: 3_000_000,
          reviewMs: 3_600_000,
          qaMs: 600_000,
          learningCount: 28,
          reviewCount: 8,
          totalActions: 36,
          studyDays: 9,
          lastStudyAt: "2026-05-08T00:00:00Z",
        },
      },
    ],
  })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/friends")
  await expect(page.getByText("好友学习排行榜", { exact: true })).toBeVisible()

  const mobileList = page.locator("[data-friend-leaderboard-mobile-list]")
  await expect(mobileList).toBeVisible()
  await expect(page.locator("[data-friend-leaderboard-desktop]")).toBeHidden()
  await expect(page.getByRole("columnheader", { name: "排名" })).toBeHidden()
  await expect(mobileList.getByText("#1")).toBeVisible()
  await expect(mobileList.getByText("自动化学习者（我）")).toBeVisible()
  await expect(mobileList.getByText("8h 49m")).toBeVisible()
  await expect(mobileList.getByText("16 天活跃")).toBeVisible()
  await expect(mobileList.getByText("84 动作")).toBeVisible()

  const layout = await page.evaluate(() => {
    const viewportWidth = window.innerWidth
    const list = document.querySelector("[data-friend-leaderboard-mobile-list]")?.getBoundingClientRect()
    const items = Array.from(document.querySelectorAll("[data-friend-leaderboard-mobile-item]")).map((element) => {
      const rect = element.getBoundingClientRect()
      return {
        left: Math.floor(rect.left),
        right: Math.ceil(rect.right),
        width: Math.ceil(rect.width),
      }
    })
    return {
      viewportWidth,
      scrollWidth: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth),
      listLeft: list ? Math.floor(list.left) : null,
      listRight: list ? Math.ceil(list.right) : null,
      items,
    }
  })

  expect(layout.scrollWidth, JSON.stringify(layout, null, 2)).toBeLessThanOrEqual(layout.viewportWidth)
  expect(layout.listLeft, JSON.stringify(layout, null, 2)).toBeGreaterThanOrEqual(16)
  expect(layout.listRight, JSON.stringify(layout, null, 2)).toBeLessThanOrEqual(layout.viewportWidth - 16)
  for (const item of layout.items) {
    expect(item.left, JSON.stringify(layout, null, 2)).toBeGreaterThanOrEqual(layout.listLeft ?? 0)
    expect(item.right, JSON.stringify(layout, null, 2)).toBeLessThanOrEqual(layout.listRight ?? layout.viewportWidth)
  }

  expectNoConsoleIssues(consoleIssues)
})

test("profile mobile layout aligns with the header without horizontal overflow", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/profile")
  await expect(page.getByText("账户信息", { exact: true })).toBeVisible()
  await expect(page.locator("[data-profile-learning-chart]")).toBeVisible()

  await expect.poll(async () => {
    return page.evaluate(() => {
      const chart = document.querySelector("[data-profile-learning-chart]") as SVGSVGElement | null
      const chartBox = chart?.getBoundingClientRect()
      const chartFrame = chart?.parentElement
      const frameStyle = chartFrame ? window.getComputedStyle(chartFrame) : null
      const renderedWidth = chartBox ? Math.round(chartBox.width) : 0
      const frameContentWidth =
        chartFrame && frameStyle
          ? Math.floor(
              chartFrame.clientWidth - Number.parseFloat(frameStyle.paddingLeft) - Number.parseFloat(frameStyle.paddingRight),
            )
          : 0
      const viewBoxWidth = chart?.viewBox.baseVal.width ?? 0
      return Boolean(
        renderedWidth > 0 &&
        viewBoxWidth < 640 &&
        Math.abs(viewBoxWidth - frameContentWidth) <= 4 &&
        chart?.getAttribute("preserveAspectRatio") === "xMidYMid meet",
      )
    })
  }).toBe(true)

  const chartLayout = await page.evaluate(() => {
    const chart = document.querySelector("[data-profile-learning-chart]") as SVGSVGElement | null
    const chartBox = chart?.getBoundingClientRect()
    const chartFrame = chart?.parentElement
    const frameStyle = chartFrame ? window.getComputedStyle(chartFrame) : null
    return {
      renderedWidth: chartBox ? Math.round(chartBox.width) : 0,
      frameContentWidth:
        chartFrame && frameStyle
          ? Math.floor(
              chartFrame.clientWidth - Number.parseFloat(frameStyle.paddingLeft) - Number.parseFloat(frameStyle.paddingRight),
            )
          : 0,
      viewBoxWidth: chart?.viewBox.baseVal.width ?? 0,
    }
  })
  expect(chartLayout.renderedWidth, JSON.stringify(chartLayout, null, 2)).toBeGreaterThan(0)
  expect(chartLayout.viewBoxWidth, JSON.stringify(chartLayout, null, 2)).toBeLessThan(640)
  expect(Math.abs(chartLayout.viewBoxWidth - chartLayout.frameContentWidth), JSON.stringify(chartLayout, null, 2)).toBeLessThanOrEqual(4)

  const layout = await page.evaluate(() => {
    const viewportWidth = window.innerWidth
    const headerRow = document.querySelector("header.theme-shell-header .container > .relative")?.getBoundingClientRect()
    const cards = Array.from(document.querySelectorAll(".theme-card-main")).map((element) => {
      const rect = element.getBoundingClientRect()
      return {
        className: element.className,
        left: Math.floor(rect.left),
        right: Math.ceil(rect.right),
        width: Math.ceil(rect.width),
      }
    })
    return {
      viewportWidth,
      scrollWidth: Math.max(document.body.scrollWidth, document.documentElement.scrollWidth),
      headerLeft: headerRow ? Math.floor(headerRow.left) : null,
      headerRight: headerRow ? Math.ceil(headerRow.right) : null,
      cards,
    }
  })

  expect(layout.scrollWidth, JSON.stringify(layout, null, 2)).toBeLessThanOrEqual(layout.viewportWidth)
  expect(layout.headerLeft).toBe(16)
  expect(layout.headerRight).toBe(layout.viewportWidth - 16)
  for (const card of layout.cards) {
    expect(card.left).toBeGreaterThanOrEqual(layout.headerLeft ?? 0)
    expect(card.right).toBeLessThanOrEqual(layout.headerRight ?? layout.viewportWidth)
    expect(card.left).toBeLessThanOrEqual(16)
    expect(card.right).toBeGreaterThanOrEqual(layout.viewportWidth - 16)
  }

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
