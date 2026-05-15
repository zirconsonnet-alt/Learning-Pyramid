import { expect, test, type Page } from "@playwright/test"

import { collectConsoleIssues, expectNoConsoleIssues } from "../fixtures/app-checks"
import { createMockGlobalSettings, installMockApi } from "../fixtures/mock-api"
import { membershipSummary, project, subject } from "../fixtures/test-data"

const genericConditionCopy = /使用前先确认|确保满足|满足以下条件/
const projectRoute = (suffix: string) => `/subjects/${subject.subjectId}/projects/${project.projectId}${suffix.startsWith("/") ? suffix : `/${suffix}`}`

const inactiveMembershipSummary = {
  ...membershipSummary,
  currentStatus: "never_purchased",
  currentStartsAt: null,
  currentEndsAt: null,
  isActive: false,
  isFirstOrderEligible: true,
}

async function expectGuideStep(page: Page, title: string | RegExp) {
  await expect(page.getByRole("dialog", { name: title })).toBeVisible()
}

async function dispatchClick(locator: ReturnType<Page["getByRole"]>) {
  await locator.dispatchEvent("click")
}

async function expectGuideTargetBounds(
  page: Page,
  anchor: string,
  expected: {
    minWidth?: number
    maxWidth?: number
    minHeight?: number
    maxHeight?: number
  },
) {
  const bounds = await page.locator(`[data-guide-tour="${anchor}"]`).boundingBox()
  expect(bounds, `expected [data-guide-tour="${anchor}"] to have layout bounds`).not.toBeNull()
  if (!bounds) return
  if (expected.minWidth !== undefined) expect(bounds.width).toBeGreaterThanOrEqual(expected.minWidth)
  if (expected.maxWidth !== undefined) expect(bounds.width).toBeLessThanOrEqual(expected.maxWidth)
  if (expected.minHeight !== undefined) expect(bounds.height).toBeGreaterThanOrEqual(expected.minHeight)
  if (expected.maxHeight !== undefined) expect(bounds.height).toBeLessThanOrEqual(expected.maxHeight)
}

async function seedSelectedProject(page: Page) {
  await page.addInitScript(({ subjectId, projectId }) => {
    window.localStorage.setItem(
      "plm-app",
      JSON.stringify({
        state: {
          selectedSubjectId: subjectId,
          selectedWorkbenchProjectRef: { subjectId, scopedProjectId: projectId },
          recentSubjectIds: [subjectId],
          recentWorkbenchProjectRefs: [{ subjectId, scopedProjectId: projectId }],
        },
        version: 0,
      }),
    )
  }, { subjectId: subject.subjectId, projectId: project.projectId })
}

test("AI chat guide stops at membership when the account is not active", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await seedSelectedProject(page)
  await installMockApi(page, { membershipSummary: inactiveMembershipSummary })

  await page.goto("/subjects?walkthrough=use-ai-chat")

  await expect(page).toHaveURL(/\/membership$/)
  await expectGuideStep(page, "AI 问答是会员专属功能")
  await expect(page.getByText("当前账号还没有有效会员")).toBeVisible()
  await expect(page.getByText(genericConditionCopy)).toHaveCount(0)
  await expect(page.getByRole("button", { name: "完成" })).toBeVisible()
  await expect(page.getByRole("button", { name: "上一步" })).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test("AI chat guide points to LLM settings when the deployment has no LLM", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await seedSelectedProject(page)
  await installMockApi(page, {
    systemCapabilities: { llmConfigured: false, llmSource: "none" },
  })

  await page.goto("/subjects?walkthrough=use-ai-chat")

  await expect(page).toHaveURL(/\/settings\/global$/)
  await expectGuideStep(page, "先接通 LLM")
  await expect(page.getByText("保存 Base URL、模型名和 API Key")).toBeVisible()
  await expect(page.getByText(genericConditionCopy)).toHaveCount(0)
  await expect(page.getByRole("button", { name: "完成" })).toBeVisible()

  expectNoConsoleIssues(consoleIssues)
})

test("AI chat guide walks through the virtual study review project AI question flow", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await seedSelectedProject(page)
  await installMockApi(page)

  await page.goto("/subjects?walkthrough=use-ai-chat")

  await expect(page).toHaveURL(/\/subjects\/guide-virtual-study-review\/projects\/guide-virtual-study-review\/ai-chat$/)
  await expectGuideStep(page, "第 1 步：选择提问对象")
  await expect(page.locator(".guide-walkthrough-fallback")).toHaveCount(0)
  await expect(page.getByRole("button", { name: "学科 学习复习引导示范学科" })).toBeVisible()
  await expect(page.getByRole("button", { name: "项目 线性代数导论示范视频" })).toBeVisible()
  await expect(page.getByText("点击项目左侧导航里的“AI问答”。")).toHaveCount(0)
  await expect(page.getByText(genericConditionCopy)).toHaveCount(0)
  await expect(page.getByRole("button", { name: "上一步", exact: true })).toHaveCount(0)

  await dispatchClick(page.getByRole("button", { name: "01 向量与线性组合.mp4" }))
  await expectGuideStep(page, "第 2 步：确认问题")
  await expect(page.getByLabel("提问内容")).toHaveValue("请用更容易懂的话解释这个小节。")
  await expect(page.getByRole("button", { name: "下一步", exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "上一步", exact: true })).toHaveCount(0)

  await page.getByRole("button", { name: "下一步", exact: true }).click()
  await expectGuideStep(page, "第 3 步：发送问题")
  await expect(page.getByRole("button", { name: "发送", exact: true })).toBeEnabled()
  await dispatchClick(page.getByRole("button", { name: "发送", exact: true }))
  await expectGuideStep(page, "第 4 步：查看回答")
  await expect(page.getByText("看这类内容时，可以先分清“基向量是什么”和“系数怎么取”。")).toBeVisible()
  await expect(page.getByRole("button", { name: "完成" })).toBeVisible()
  await page.getByRole("button", { name: "完成" }).click()
  await expect(page).toHaveURL(/\/subjects$/)
  await expect(page.getByText("学习复习引导示范项目")).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test("pomodoro guide stops at membership when the account is not active", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page, { membershipSummary: inactiveMembershipSummary })

  await page.goto("/pomodoro?walkthrough=use-pomodoro")

  await expect(page).toHaveURL(/\/membership$/)
  await expectGuideStep(page, "番茄钟是会员专属功能")
  await expect(page.getByText("当前账号还没有有效会员")).toBeVisible()
  await expect(page.getByText(genericConditionCopy)).toHaveCount(0)
  await expect(page.getByRole("button", { name: "完成" })).toBeVisible()

  expectNoConsoleIssues(consoleIssues)
})

test("pomodoro guide walks through the real plan and workbench flow", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page, {
    globalSettings: createMockGlobalSettings({
      pomodoro: {
        enabled: false,
        transitionSoundEnabled: false,
        defaultFocusPrompt: "",
        defaultBreakPrompt: "",
        microBreaks: {
          enabled: true,
          minIntervalSeconds: 180,
          maxIntervalSeconds: 300,
          durationSeconds: 10,
        },
        weeklySchedule: {
          mon: { plans: [] },
          tue: { plans: [] },
          wed: { plans: [] },
          thu: { plans: [] },
          fri: { plans: [] },
          sat: { plans: [] },
          sun: { plans: [] },
        },
      },
    }),
  })

  await page.goto("/pomodoro?walkthrough=use-pomodoro")

  await expect(page).toHaveURL(/\/pomodoro$/)
  await expectGuideStep(page, "第 1 步：新建番茄计划")
  await expect(page.getByRole("button", { name: "新增计划" })).toBeVisible()
  await expect(page.getByRole("dialog", { name: /番茄钟设置/ })).toHaveCount(0)
  await expect(page.getByText(genericConditionCopy)).toHaveCount(0)
  await expect(page.getByText(/登录网页|保持浏览器标签页|等待开始/)).toHaveCount(0)
  await expect(page.getByRole("button", { name: "上一步", exact: true })).toHaveCount(0)

  await dispatchClick(page.getByRole("button", { name: "新增计划" }))
  await expect(page).toHaveURL(/\/pomodoro\/plans\/[^/]+$/)
  await expectGuideStep(page, "第 2 步：绑定学习项目")
  await expectGuideTargetBounds(page, "pomodoro-project-binding", { minWidth: 300, maxWidth: 430, minHeight: 100 })
  await page.locator('[data-guide-tour="pomodoro-project-binding"] select').selectOption(project.projectId)

  await expectGuideStep(page, "第 3 步：保存番茄计划")
  await dispatchClick(page.getByRole("button", { name: "保存" }))
  await expect(page).toHaveURL(/\/pomodoro$/)

  await expectGuideStep(page, "第 4 步：开启番茄钟")
  await dispatchClick(page.getByRole("button", { name: "开启番茄钟" }))
  await expect(page).toHaveURL(new RegExp(`${projectRoute("/workbench")}$`))
  await expectGuideStep(page, "第 5 步：查看工作台")
  await expect(page.locator('[data-guide-tour="learning-object-tree"]')).toBeVisible()
  await expect(page.getByRole("button", { name: "完成" })).toBeVisible()

  expectNoConsoleIssues(consoleIssues)
})
