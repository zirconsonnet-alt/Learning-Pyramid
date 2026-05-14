import { expect, test } from "@playwright/test"

import { collectConsoleIssues, expectNoConsoleIssues } from "../fixtures/app-checks"
import { installMockApi } from "../fixtures/mock-api"
import { journeyIds } from "../fixtures/journeys"
import { recordJourney } from "../fixtures/journey-result"
import { gotoWorkbench, projectPath } from "../fixtures/page-objects"
import { instance, reviewTask } from "../fixtures/test-data"

test(journeyIds.workbench, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await recordJourney(journeyIds.workbench, async () => {
    await gotoWorkbench(page)
    await expect(page.getByRole("button", { name: /今日回看/ })).toHaveCount(0)
    await expect(page.getByText("推进判断")).toHaveCount(0)
    await expect(page.getByText("预计剩余学习时长")).toBeVisible()
    await expect(page.getByText("观看覆盖")).toBeVisible()
    await expect(page.getByText("今日回看")).toBeVisible()
    await expect(page.getByLabel("今日回看统计图")).toBeVisible()
    await expect(page.getByText("网页驻留")).toBeVisible()
    await page.getByRole("button", { name: "层推进与学习任务" }).click()
    await expect(page.getByRole("heading", { name: "层推进与学习任务" })).toBeVisible()
  })

  expectNoConsoleIssues(consoleIssues)
})

test("workbench video pane keeps the empty selection prompt to one line", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await gotoWorkbench(page)
  await expect(page.getByText("请先在左侧选择一个视频实例。")).toBeVisible()
  await expect(page.getByText("当前视频还未进入可播放状态")).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test("workbench empty content tree avoids duplicate setup prompt", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page, { contentState: "empty" })

  await gotoWorkbench(page)
  await expect(page.getByText("先绑定并授权素材目录")).toBeVisible()
  const contentTreeCard = page.locator("#workbench-content-tree")
  await expect(contentTreeCard.getByText("尚未绑定素材目录")).toBeVisible()
  await expect(contentTreeCard.getByText("当前还没有学习对象")).toHaveCount(0)
  await expect(contentTreeCard.getByRole("link", { name: "前往项目设置" })).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test("workbench review card hides selected memory label and colors memory buttons", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page, { queueHeadId: reviewTask.reviewTaskId })

  await gotoWorkbench(page)
  await expect(page.getByText("什么是自动化测试？")).toBeVisible()
  await page.getByRole("button", { name: "跳过" }).click()
  const rememberedButton = page.getByRole("button", { name: "记得", exact: true })
  const forgottenButton = page.getByRole("button", { name: "不记得", exact: true })
  await expect(rememberedButton).toHaveClass(/!text-emerald-700/)
  await expect(forgottenButton).toHaveClass(/!text-red-700/)
  await forgottenButton.click()
  await expect(page.getByText("已标记为不记得")).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test("workbench pet assistant stays above the video control bar", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await page.emulateMedia({ reducedMotion: "reduce" })
  await installMockApi(page, { systemCapabilities: { serverMediaStreamEnabled: true } })
  await page.setViewportSize({ width: 1365, height: 744 })

  await gotoWorkbench(page)
  await page.getByRole("button", { name: instance.materialDisplayName }).click()
  const petRoot = page.locator(".plm-desktop-pet")
  const videoChrome = page.getByLabel("播放进度").locator("xpath=ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' z-20 ')][1]")
  const petButton = page.locator(".plm-desktop-pet-button")
  const petPopover = page.locator(".plm-desktop-pet-popover")
  await expect(petRoot).toBeVisible()
  await expect(videoChrome).toBeVisible()
  await petButton.click()
  await expect(petPopover).toBeVisible()

  const [petZIndex, videoChromeZIndex] = await Promise.all([
    petRoot.evaluate((element) => getComputedStyle(element).zIndex),
    videoChrome.evaluate((element) => getComputedStyle(element).zIndex),
  ])
  expect(Number(petZIndex)).toBeGreaterThan(Number(videoChromeZIndex))

  const overlap = await page.evaluate(() => {
    const popover = document.querySelector(".plm-desktop-pet-popover")
    const chrome = document.querySelector("[aria-label='播放进度']")?.closest(".z-20")
    if (!(popover instanceof HTMLElement) || !(chrome instanceof HTMLElement)) {
      return { intersects: false, popoverContainsTop: false, videoChromeContainsTop: false, reason: "missing-elements" }
    }

    const popoverRect = popover.getBoundingClientRect()
    const chromeRect = chrome.getBoundingClientRect()
    const left = Math.max(popoverRect.left, chromeRect.left)
    const top = Math.max(popoverRect.top, chromeRect.top)
    const right = Math.min(popoverRect.right, chromeRect.right)
    const bottom = Math.min(popoverRect.bottom, chromeRect.bottom)
    if (left >= right || top >= bottom) {
      return {
        intersects: false,
        popoverContainsTop: false,
        videoChromeContainsTop: false,
        reason: "no-overlap",
        popoverRect: popoverRect.toJSON(),
        chromeRect: chromeRect.toJSON(),
      }
    }

    const x = Math.floor((left + right) / 2)
    const y = Math.floor((top + bottom) / 2)
    const topElement = document.elementFromPoint(x, y)
    return {
      intersects: true,
      popoverContainsTop: !!topElement && popover.contains(topElement),
      videoChromeContainsTop: !!topElement && chrome.contains(topElement),
      point: { x, y },
      topElementClass: topElement instanceof HTMLElement ? topElement.className : null,
    }
  })
  expect(overlap.intersects, JSON.stringify(overlap)).toBe(true)
  expect(overlap.popoverContainsTop, JSON.stringify(overlap)).toBe(true)
  expect(overlap.videoChromeContainsTop, JSON.stringify(overlap)).toBe(false)

  await page.getByRole("button", { name: "关闭雪豹问答" }).click()
  await expect(petPopover).toBeHidden()
  await page.mouse.move(10, 10)
  await expect(petPopover).toBeHidden()

  expectNoConsoleIssues(consoleIssues)
})

test("workbench compose pane hides redundant helper copy", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await gotoWorkbench(page)
  await page.getByRole("button", { name: instance.materialDisplayName }).click()
  await page.getByRole("button", { name: "添加" }).click()

  await expect(page.getByText("网课锚点可编辑，提交时会保存为可跳转的视频时间点。")).toHaveCount(0)

  await page.getByPlaceholder("请输入问题/提示语").fill("1")
  await page.getByPlaceholder("请输入答案/复述内容").fill("1")
  await expect(page.getByText("已准备好提交，共 1 个复述点，已完成 1 个。")).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test("workbench compose pane previews markdown and latex while hovering field labels", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await gotoWorkbench(page)
  await page.getByRole("button", { name: instance.materialDisplayName }).click()
  await page.getByRole("button", { name: "添加" }).click()

  await page.getByPlaceholder("请输入问题/提示语").fill("**正态分布** 的密度函数：$f(x)=\\frac{1}{\\sqrt{2\\pi}\\sigma}$")
  await page.getByPlaceholder("请输入答案/复述内容").fill("答案满足 $\\mu=0$，且支持 Markdown。")

  const questionPreviewButton = page.getByRole("button", { name: "问题预览" })
  const answerPreviewButton = page.getByRole("button", { name: "答案预览" })
  await expect(questionPreviewButton).toBeVisible()
  await expect(answerPreviewButton).toBeVisible()

  await questionPreviewButton.hover()
  const questionPreview = page.getByRole("tooltip", { name: "问题渲染预览" })
  await expect(questionPreview).toBeVisible()
  await expect(questionPreview.locator(".katex")).toHaveCount(1)
  await expect(questionPreview.getByText("正态分布")).toBeVisible()

  await answerPreviewButton.hover()
  const answerPreview = page.getByRole("tooltip", { name: "答案渲染预览" })
  await expect(answerPreview).toBeVisible()
  await expect(answerPreview.locator(".katex")).toHaveCount(1)
  await expect(questionPreview).toBeHidden()

  await page.mouse.move(5, 5)
  await expect(answerPreview).toBeHidden()

  expectNoConsoleIssues(consoleIssues)
})

test(journeyIds.review, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await recordJourney(journeyIds.review, async () => {
    await page.goto(projectPath("/recommended-reviews"))
    await expect(page.getByText("什么是自动化测试？")).toBeVisible()
    await expect(page.getByText("查看复述点详情")).toHaveCount(0)
    await expect(page.getByRole("link", { name: "回到锚点" })).toHaveCount(0)
    const anchorLink = page.getByRole("link", { name: "第一讲 自动化导论 · 0:00" })
    await expect(anchorLink).toBeVisible()
    await expect(page.getByText(/内容实例 #/)).toHaveCount(0)
    await expect(page.getByText(/t=0/)).toHaveCount(0)
    const anchorActionRow = anchorLink.locator("xpath=ancestor::div[contains(@class,'flex')][1]")
    await expect(anchorActionRow.getByRole("button", { name: "追加理解" })).toBeVisible()
    await page.getByRole("button", { name: "跳过" }).click()
    await expect(page.getByText("用程序验证用户关键流程。")).toBeVisible()
    await expect(page.getByText("已提交答案")).toHaveCount(0)
    await expect(page.getByText(/已展开答案/)).toHaveCount(0)
    const answerContentCard = page.getByText("用程序验证用户关键流程。").locator("xpath=ancestor::div[contains(@class,'theme-canvas')][1]")
    await expect(answerContentCard.getByText("答案", { exact: true })).toHaveCount(0)
    const rememberedButton = page.getByRole("button", { name: "记得", exact: true })
    const forgottenButton = page.getByRole("button", { name: "不记得", exact: true })
    await expect(rememberedButton).toHaveClass(/text-emerald-700/)
    await expect(forgottenButton).toHaveClass(/text-red-700/)
    await forgottenButton.click()
    await expect(page.getByText("已标记为不记得")).toHaveCount(0)
  })

  expectNoConsoleIssues(consoleIssues)
})
