import { expect, test, type Page } from "@playwright/test"

import { collectConsoleIssues, expectNoConsoleIssues } from "../fixtures/app-checks"
import { createMockGlobalSettings, installMockApi } from "../fixtures/mock-api"
import { projectPath } from "../fixtures/page-objects"
import { membershipSummary, project, subject } from "../fixtures/test-data"

const genericConditionCopy = /使用前先确认|确保满足|满足以下条件/

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

test("AI chat guide opens the selected project AI chat when membership and LLM are ready", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await seedSelectedProject(page)
  await installMockApi(page)

  await page.goto("/subjects?walkthrough=use-ai-chat")

  await expect(page).toHaveURL(new RegExp(projectPath("/ai-chat")))
  await expectGuideStep(page, "第 1 步：进入项目 AI 问答")
  await expect(page.getByText(genericConditionCopy)).toHaveCount(0)

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

test("pomodoro guide starts from the enable button when pomodoro is off", async ({ page }) => {
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
  await expectGuideStep(page, "第 1 步：开启番茄钟")
  await expect(page.getByRole("button", { name: "开启番茄钟" })).toBeVisible()
  await expect(page.getByRole("dialog", { name: /番茄钟设置/ })).toHaveCount(0)
  await expect(page.getByText(genericConditionCopy)).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})
