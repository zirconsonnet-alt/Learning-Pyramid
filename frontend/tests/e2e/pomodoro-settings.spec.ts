import { expect, test } from "@playwright/test"

import { collectConsoleIssues, expectNoConsoleIssues } from "../fixtures/app-checks"
import { createMockGlobalSettings, installMockApi } from "../fixtures/mock-api"
import { journeyIds } from "../fixtures/journeys"
import { recordJourney } from "../fixtures/journey-result"
import { project, subject } from "../fixtures/test-data"

function createPomodoroPlan(overrides: Partial<ReturnType<typeof createMockGlobalSettings>["pomodoro"]["weeklySchedule"]["sat"]["plans"][number]> = {}) {
  return {
    id: "plan_e2e",
    enabled: true,
    startTime: "20:00",
    focusMinutes: 25,
    breakMinutes: 5,
    pomodoroCount: 1,
    projectRefs: [{ subjectId: subject.subjectId, scopedProjectId: project.projectId }],
    breakPrompt: "",
    focusPrompts: [""],
    ...overrides,
  }
}

test(journeyIds.pomodoro, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await recordJourney(journeyIds.pomodoro, async () => {
    await page.goto("/pomodoro")
    await expect(page.getByText("番茄钟", { exact: true })).toBeVisible()
    await page.getByRole("button", { name: "统计" }).click()
    await expect(page.getByText("今天还没有可统计的番茄记录。")).toBeVisible()
  })

  expectNoConsoleIssues(consoleIssues)
})

test("pomodoro can be turned off even when saved schedule is invalid", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page, {
    globalSettings: createMockGlobalSettings({
      pomodoro: {
        enabled: true,
        transitionSoundEnabled: false,
        defaultFocusPrompt: "",
        defaultBreakPrompt: "",
        microBreaks: {
          enabled: false,
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
          sat: { plans: [createPomodoroPlan({ projectRefs: [null] })] },
          sun: { plans: [] },
        },
      },
    }),
  })

  await page.goto("/pomodoro")
  await expect(page.getByRole("button", { name: "关闭番茄钟" })).toBeVisible()
  await page.getByRole("button", { name: "关闭番茄钟" }).click()
  await expect(page.getByRole("button", { name: "开启番茄钟" })).toBeVisible()

  expectNoConsoleIssues(consoleIssues)
})

test("pomodoro blocks workbench when enabled without an active focus segment", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page, {
    globalSettings: createMockGlobalSettings({
      pomodoro: {
        enabled: true,
        transitionSoundEnabled: false,
        defaultFocusPrompt: "",
        defaultBreakPrompt: "",
        microBreaks: {
          enabled: false,
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
  await page.addInitScript(({ subjectId, projectId }) => {
    window.localStorage.setItem(
      "plm-app",
      JSON.stringify({
        state: {
          selectedSubjectId: subjectId,
          selectedWorkbenchProjectId: projectId,
          selectedWorkbenchProjectRef: { subjectId, scopedProjectId: projectId },
          recentSubjectIds: [subjectId],
          recentWorkbenchProjectIds: [projectId],
          recentWorkbenchProjectRefs: [{ subjectId, scopedProjectId: projectId }],
        },
        version: 0,
      }),
    )
  }, { subjectId: subject.subjectId, projectId: project.projectId })

  await page.goto("/pomodoro")
  await expect(page.getByRole("link", { name: /进入.*工作台/ })).toHaveCount(0)
  await page.goto(`/subjects/${subject.subjectId}/projects/${project.projectId}/workbench`)
  await expect(page).toHaveURL(/\/pomodoro$/)

  expectNoConsoleIssues(consoleIssues)
})

test("pomodoro creates quick pomodoro from an explicit subject and project selection", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page, {
    globalSettings: createMockGlobalSettings({
      pomodoro: {
        enabled: true,
        transitionSoundEnabled: false,
        defaultFocusPrompt: "",
        defaultBreakPrompt: "",
        microBreaks: {
          enabled: false,
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
  await page.addInitScript(({ subjectId, projectId }) => {
    window.localStorage.setItem(
      "plm-app",
      JSON.stringify({
        state: {
          selectedSubjectId: subjectId,
          selectedWorkbenchProjectId: projectId,
          selectedWorkbenchProjectRef: { subjectId, scopedProjectId: projectId },
          recentSubjectIds: [subjectId],
          recentWorkbenchProjectIds: [projectId],
          recentWorkbenchProjectRefs: [{ subjectId, scopedProjectId: projectId }],
        },
        version: 0,
      }),
    )
  }, { subjectId: subject.subjectId, projectId: project.projectId })

  await page.goto("/pomodoro")
  await page.waitForLoadState("networkidle")
  const quickPomodoroButton = page.getByRole("button", { name: "新建小番茄" })
  await expect(quickPomodoroButton).toBeVisible()
  await expect(page.getByRole("link", { name: /进入.*工作台/ })).toHaveCount(0)
  await quickPomodoroButton.click()
  const dialog = page.getByRole("dialog", { name: "新建小番茄" })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByLabel("学科")).toHaveValue("")
  await expect(dialog.getByLabel("项目")).toBeDisabled()
  await expect(dialog.getByRole("button", { name: "创建小番茄" })).toBeDisabled()

  await dialog.getByLabel("学科").selectOption(subject.subjectId)
  await dialog.getByLabel("项目").selectOption(project.projectId)
  await dialog.getByRole("button", { name: "创建小番茄" }).click()

  await expect(dialog).toHaveCount(0)
  await expect(page.getByRole("button", { name: "结束小番茄" })).toBeVisible()
  await expect(page.getByRole("link", { name: "进入自动化测试项目工作台" })).toHaveCount(0)
  await expect(page.getByText("10 秒后开始 25 分钟学习，系统会进入所选项目工作台。")).toBeVisible()
  await expect(page).toHaveURL(new RegExp(`/subjects/${subject.subjectId}/projects/${project.projectId}/workbench$`), { timeout: 15_000 })

  expectNoConsoleIssues(consoleIssues)
})

test("pomodoro allows only the focused project workbench during focus time", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page, {
    globalSettings: createMockGlobalSettings({
      pomodoro: {
        enabled: true,
        transitionSoundEnabled: false,
        defaultFocusPrompt: "",
        defaultBreakPrompt: "",
        microBreaks: {
          enabled: false,
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
          sat: { plans: [createPomodoroPlan({ startTime: "08:00", focusMinutes: 180 })] },
          sun: { plans: [] },
        },
      },
    }),
  })

  await page.clock.setFixedTime(new Date("2026-05-09T00:30:00Z"))
  await page.goto("/pomodoro")
  await expect(page).toHaveURL(new RegExp(`/subjects/${subject.subjectId}/projects/${project.projectId}/workbench$`))

  expectNoConsoleIssues(consoleIssues)
})

test("pomodoro focused workbench does not depend on legacy project catalog", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page, {
    globalSettings: createMockGlobalSettings({
      pomodoro: {
        enabled: true,
        transitionSoundEnabled: false,
        defaultFocusPrompt: "",
        defaultBreakPrompt: "",
        microBreaks: {
          enabled: false,
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
          sat: { plans: [createPomodoroPlan({ startTime: "08:00", focusMinutes: 180 })] },
          sun: { plans: [] },
        },
      },
    }),
  })
  await page.route("**/api/projects", async (route) => {
    await route.fulfill({
      status: 400,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify({
        ok: false,
        error: { code: "PRECONDITION", message: "旧项目列表已失效，请从学科中心进入项目" },
      }),
    })
  })

  await page.clock.setFixedTime(new Date("2026-05-09T00:30:00Z"))
  await page.goto("/pomodoro")
  await expect(page).toHaveURL(new RegExp(`/subjects/${subject.subjectId}/projects/${project.projectId}/workbench$`))

  expectNoConsoleIssues(consoleIssues)
})

test("pomodoro delete plan persists after returning to overview", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page, {
    globalSettings: createMockGlobalSettings({
      pomodoro: {
        enabled: false,
        transitionSoundEnabled: false,
        defaultFocusPrompt: "",
        defaultBreakPrompt: "",
        microBreaks: {
          enabled: false,
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
          sat: { plans: [createPomodoroPlan({ id: "delete_me" })] },
          sun: { plans: [] },
        },
      },
    }),
  })

  await page.goto("/pomodoro/plans/delete_me")
  await expect(page.getByText("计划 1")).toBeVisible()
  await page.getByRole("button", { name: "删除计划" }).click()
  await expect(page).toHaveURL(/\/pomodoro$/)
  await expect(page.getByText("番茄计划：0组")).toBeVisible()
  await expect(page.getByText("还没有计划，新增一组后再进入详情设置。")).toHaveCount(0)
  await page.reload()
  await expect(page.getByText("番茄计划：0组")).toBeVisible()
  await expect(page.getByText("还没有计划，新增一组后再进入详情设置。")).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test("pomodoro save plan returns to overview", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page, {
    globalSettings: createMockGlobalSettings({
      pomodoro: {
        enabled: false,
        transitionSoundEnabled: false,
        defaultFocusPrompt: "",
        defaultBreakPrompt: "",
        microBreaks: {
          enabled: false,
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
          sat: { plans: [createPomodoroPlan({ id: "save_me" })] },
          sun: { plans: [] },
        },
      },
    }),
  })

  await page.goto("/pomodoro/plans/save_me")
  await expect(page.getByText("计划 1")).toBeVisible()
  await page.getByRole("button", { name: "保存" }).click()
  await expect(page).toHaveURL(/\/pomodoro$/)

  expectNoConsoleIssues(consoleIssues)
})

test("pomodoro restore returns to overview when current draft no longer exists", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.goto("/pomodoro")
  await page.getByRole("button", { name: "新增计划" }).click()
  await expect(page.getByText("计划 1")).toBeVisible()
  await page.getByRole("button", { name: "恢复" }).click()
  await expect(page).toHaveURL(/\/pomodoro$/)
  await expect(page.getByText("番茄计划：0组")).toBeVisible()
  await expect(page.getByText("还没有计划，新增一组后再进入详情设置。")).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test(journeyIds.settings, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await recordJourney(journeyIds.settings, async () => {
    await page.goto("/settings/global")
    await expect(page.getByText("全局配置")).toBeVisible()
    await expect(page.locator("#root")).not.toBeEmpty()
  })

  expectNoConsoleIssues(consoleIssues)
})
