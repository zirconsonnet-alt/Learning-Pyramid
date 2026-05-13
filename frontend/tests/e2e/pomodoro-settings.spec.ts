import { expect, test, type Page } from "@playwright/test"

import { collectConsoleIssues, expectNoConsoleIssues } from "../fixtures/app-checks"
import { createMockGlobalSettings, installMockApi } from "../fixtures/mock-api"
import { journeyIds } from "../fixtures/journeys"
import { recordJourney } from "../fixtures/journey-result"
import { project, subject, testUser } from "../fixtures/test-data"

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

async function seedPomodoroWallpaper(page: Page, recordKey: IDBValidKey = ["user", testUser.userId, "current"]) {
  await page.addInitScript(async ({ key }) => {
    const dbRequest = indexedDB.open("learningpyramid-pomodoro-wallpaper", 1)
    const db = await new Promise<IDBDatabase>((resolve, reject) => {
      dbRequest.onupgradeneeded = () => {
        const db = dbRequest.result
        if (!db.objectStoreNames.contains("wallpaper")) {
          db.createObjectStore("wallpaper")
        }
      }
      dbRequest.onsuccess = () => resolve(dbRequest.result)
      dbRequest.onerror = () => reject(dbRequest.error)
    })
    const blob = await fetch(
      "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='120' height='80'%3E%3Crect width='120' height='80' fill='%232563eb'/%3E%3C/svg%3E",
    ).then((response) => response.blob())
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction("wallpaper", "readwrite")
      transaction.objectStore("wallpaper").put(
        {
          blob,
          name: "e2e-wallpaper.svg",
          type: blob.type,
          updatedAt: Date.now(),
        },
        key,
      )
      transaction.oncomplete = () => {
        db.close()
        resolve()
      }
      transaction.onerror = () => reject(transaction.error)
      transaction.onabort = () => reject(transaction.error)
    })
  }, { key: recordKey })
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

test("pomodoro settings shares the pomodoro wallpaper backdrop", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await seedPomodoroWallpaper(page)
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
          sat: { plans: [createPomodoroPlan({ id: "wallpaper_plan" })] },
          sun: { plans: [] },
        },
      },
    }),
  })

  await page.goto("/pomodoro")
  await expect(page.locator("[data-pomodoro-wallpaper-backdrop]")).toBeVisible()

  await page.goto("/pomodoro/plans/wallpaper_plan")
  await expect(page.locator("[data-pomodoro-wallpaper-backdrop]")).toBeVisible()
  const planDetailFrame = await page.locator("[data-pomodoro-wallpaper-scope='page']").boundingBox()
  await expect(page.getByRole("link", { name: "返回番茄钟" })).toBeVisible()

  await page.goto("/pomodoro/settings")
  await expect(page.locator("[data-pomodoro-wallpaper-backdrop]")).toBeVisible()
  await expect(page.getByText("番茄钟设置")).toBeVisible()
  await expect(page.getByRole("link", { name: "返回番茄钟" })).toBeVisible()
  const settingsFrame = await page.locator("[data-pomodoro-wallpaper-scope='page']").boundingBox()
  expect(settingsFrame?.width).toBe(planDetailFrame?.width)

  expectNoConsoleIssues(consoleIssues)
})

test("pomodoro wallpaper ignores the old browser-global record for signed-in accounts", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await seedPomodoroWallpaper(page, "current")
  await installMockApi(page)

  await page.goto("/pomodoro")
  await expect(page.getByText("番茄钟", { exact: true })).toBeVisible()
  await expect(page.locator("[data-pomodoro-wallpaper-backdrop]")).toHaveCount(0)

  await page.goto("/pomodoro/settings")
  await expect(page.getByText("番茄钟设置")).toBeVisible()
  await expect(page.locator("[data-pomodoro-wallpaper-backdrop]")).toHaveCount(0)

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

test("pomodoro blocks quick pomodoro when it overlaps an enabled plan", async ({ page }) => {
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
          sat: { plans: [createPomodoroPlan({ startTime: "08:00" })] },
          sun: { plans: [] },
        },
      },
    }),
  })

  await page.clock.setFixedTime(new Date("2026-05-08T23:45:00Z"))
  await page.goto("/pomodoro")
  const quickPomodoroButton = page.getByRole("button", { name: "新建小番茄" })
  await expect(quickPomodoroButton).toBeVisible()
  await quickPomodoroButton.click()

  await expect(page.getByText("小番茄时间冲突")).toBeVisible()
  await expect(page.getByText("预计 25 分钟学习会和已有番茄计划重叠，请先调整计划或等计划结束后再创建。")).toBeVisible()
  await expect(page.getByRole("dialog", { name: "新建小番茄" })).toHaveCount(0)
  await expect(page.getByRole("button", { name: "结束小番茄" })).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test("pomodoro ignores saved plans when schedule is disabled for quick pomodoro", async ({ page }) => {
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
          sat: { plans: [createPomodoroPlan({ startTime: "08:00" })] },
          sun: { plans: [] },
        },
      },
    }),
  })

  await page.clock.setFixedTime(new Date("2026-05-08T23:45:00Z"))
  await page.goto("/pomodoro")
  await page.getByRole("button", { name: "新建小番茄" }).click()

  await expect(page.getByRole("dialog", { name: "新建小番茄" })).toBeVisible()
  await expect(page.getByText("小番茄时间冲突")).toHaveCount(0)

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
