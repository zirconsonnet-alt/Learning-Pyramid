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
  for (const pointWidth of mobileCarouselLayout.pointWidths) {
    expect(pointWidth, JSON.stringify(mobileCarouselLayout, null, 2)).toBeLessThanOrEqual(170)
  }

  await expect(page.getByText("01 / 04")).toBeVisible()
  const box = await carousel.boundingBox()
  if (!box) throw new Error("home carousel did not render")
  await page.evaluate(({ startX, endX, y }) => {
    const viewport = document.querySelector(".lp-showcase-carousel-viewport") as HTMLElement | null
    if (!viewport) throw new Error("home carousel did not render")
    const pointerId = 7
    viewport.dispatchEvent(
      new PointerEvent("pointerdown", {
        bubbles: true,
        cancelable: true,
        clientX: startX,
        clientY: y,
        pointerId,
        pointerType: "touch",
      }),
    )
    viewport.dispatchEvent(
      new PointerEvent("pointermove", {
        bubbles: true,
        cancelable: true,
        clientX: endX,
        clientY: y,
        pointerId,
        pointerType: "touch",
      }),
    )
    viewport.dispatchEvent(
      new PointerEvent("pointerup", {
        bubbles: true,
        cancelable: true,
        clientX: endX,
        clientY: y,
        pointerId,
        pointerType: "touch",
      }),
    )
  }, {
    startX: box.x + box.width * 0.72,
    endX: box.x + box.width * 0.22,
    y: box.y + box.height * 0.5,
  })
  await expect(page.getByText("02 / 04")).toBeVisible()

  expectNoConsoleIssues(consoleIssues)
})

test("project mobile navigation stays within the viewport", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(`/subjects/${subject.subjectId}/projects/${project.projectId}/workbench`)
  await expectHealthyPage(page, new RegExp(`/subjects/${subject.subjectId}/projects/${project.projectId}/workbench$`))

  const header = page.locator("header.theme-shell-header")
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
