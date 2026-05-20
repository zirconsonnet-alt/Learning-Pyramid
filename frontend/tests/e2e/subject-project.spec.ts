import { expect, test, type Page } from "@playwright/test"

import { collectConsoleIssues, expectNoConsoleIssues } from "../fixtures/app-checks"
import { installMockApi } from "../fixtures/mock-api"
import { journeyIds } from "../fixtures/journeys"
import { recordJourney } from "../fixtures/journey-result"
import { gotoProjects, openSubject, projectPath } from "../fixtures/page-objects"
import { instance, material, project, subject } from "../fixtures/test-data"

async function seedGrantedProjectDirectory(page: Page) {
  await page.addInitScript(
    async ({ subjectId, projectId }) => {
      const storage = navigator.storage as StorageManager & {
        getDirectory?: () => Promise<FileSystemDirectoryHandle>
      }
      const root = await storage.getDirectory?.()
      if (!root) return
      const directory = await root.getDirectoryHandle("learningpyramid-e2e-materials", { create: true })
      window.showDirectoryPicker = async () => directory
      const file = await directory.getFileHandle("第一讲 自动化导论.mp4", { create: true })
      const writable = await file.createWritable()
      await writable.write(new Blob(["e2e"], { type: "video/mp4" }))
      await writable.close()

      const dbRequest = indexedDB.open("plm-local-media", 2)
      await new Promise<void>((resolve, reject) => {
        dbRequest.onupgradeneeded = () => {
          const db = dbRequest.result
          if (!db.objectStoreNames.contains("projectDirectories")) {
            db.createObjectStore("projectDirectories", { keyPath: "projectId" })
          }
          if (!db.objectStoreNames.contains("globalDirectories")) {
            db.createObjectStore("globalDirectories", { keyPath: "key" })
          }
        }
        dbRequest.onerror = () => reject(dbRequest.error ?? new Error("IndexedDB open failed"))
        dbRequest.onsuccess = () => {
          const db = dbRequest.result
          const tx = db.transaction("projectDirectories", "readwrite")
          const store = tx.objectStore("projectDirectories")
          store.put({
            projectId: `${subjectId}:${projectId}`,
            handle: directory,
            savedAt: new Date().toISOString(),
          })
          tx.oncomplete = () => {
            db.close()
            resolve()
          }
          tx.onerror = () => {
            db.close()
            reject(tx.error ?? new Error("IndexedDB write failed"))
          }
        }
      })
    },
    { subjectId: subject.subjectId, projectId: project.projectId },
  )
}

async function completeGuideStep(page: Page, stepId: string) {
  await page.evaluate((id) => {
    window.dispatchEvent(new CustomEvent("learningpyramid:guide-walkthrough-step-completed", { detail: { stepId: id } }))
  }, stepId)
}

async function expectGuideStep(page: Page, title: string) {
  await expect(page.getByRole("dialog", { name: title })).toBeVisible()
}

async function dispatchClick(locator: ReturnType<Page["getByRole"]>) {
  await locator.dispatchEvent("click")
}

test(journeyIds.subjectProjectEntry, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await recordJourney(journeyIds.subjectProjectEntry, async () => {
    await openSubject(page)
    await expect(page.getByText(project.title)).toBeVisible()
    await page.getByRole("button", { name: "进入工作台" }).click()
    await expect(page).toHaveURL(new RegExp(projectPath("/workbench")))
    await expect(page.getByRole("heading", { name: "学习统计" })).toBeVisible()
  })

  expectNoConsoleIssues(consoleIssues)
})

test("workbench hides Baidu Netdisk playback instead of requesting a playback stream", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  let hiddenMediaPlaybackRequested = false
  const baiduInstance = {
    ...instance,
    mediaSourceKind: "BAIDU_NETDISK",
    playbackKind: "HLS",
  }
  await installMockApi(page, {
    instances: [baiduInstance],
    systemCapabilities: { baiduNetdiskEnabled: true, serverMediaStreamEnabled: true },
  })
  page.on("request", (request) => {
    const pathname = new URL(request.url()).pathname
    if (
      pathname.endsWith(`/media/instances/${instance.instanceId}/playback`) ||
      pathname.endsWith(`/media/instances/${instance.instanceId}/baidu-direct-playback`)
    ) {
      hiddenMediaPlaybackRequested = true
    }
  })

  await page.goto(projectPath("/workbench"))
  await page.getByRole("button", { name: "第一讲 自动化导论" }).click()
  await expect(page.getByText("当前媒体源已隐藏，请改用本地素材。")).toBeVisible()
  await expect(page.getByText("正在连接百度网盘视频流")).toHaveCount(0)
  expect(hiddenMediaPlaybackRequested).toBe(false)

  expectNoConsoleIssues(consoleIssues)
})

test("create subject guide enters workbench after directory sync", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await seedGrantedProjectDirectory(page)
  await installMockApi(page, { contentState: "empty" })

  await page.goto("/subjects?walkthrough=create-subject-project")
  await expectGuideStep(page, "第 1 步：创建学科和项目")
  await page.getByRole("button", { name: "新建学科" }).click()
  await completeGuideStep(page, "create-subject")
  await expectGuideStep(page, "第 2 步：填写标题并创建学科")
  await page.getByLabel("学科标题").fill(subject.title)
  await dispatchClick(page.getByRole("button", { name: "创建学科" }))
  await expect(page).toHaveURL(new RegExp(`/subjects/${subject.subjectId}`))
  await expectGuideStep(page, "第 3 步：打开项目设置")
  await dispatchClick(page.getByRole("button", { name: "项目设置" }))
  await expect(page).toHaveURL(new RegExp(projectPath("/settings")))
  await expectGuideStep(page, "第 2 步：到“项目设置”绑定目录")
  await dispatchClick(page.getByRole("button", { name: "更换目录" }))
  await expectGuideStep(page, "第 3 步：同步目录内容")
  await expect(page.getByRole("button", { name: "同步目录内容" })).toBeVisible()
  await dispatchClick(page.getByRole("button", { name: "同步目录内容" }))

  await expect(page).toHaveURL(new RegExp(projectPath("/workbench")))
  await expectGuideStep(page, "第 6 步：查看导入结果")
  await expect(page.getByText("左侧是刚导入的内容目录。")).toBeVisible()
  await expect(page.getByRole("button", { name: "完成" })).toBeVisible()
  await expect(page.getByRole("button", { name: "上一步" })).toHaveCount(0)
  await expect(page.getByRole("heading", { name: "内容目录" })).toBeVisible()
  await expect(page.getByText("第一讲 自动化导论")).toBeVisible()

  expectNoConsoleIssues(consoleIssues)
})

test("study review guide auto-fills recall question learning answer and review answer", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.goto("/subjects?walkthrough=study-review")
  await expect(page).toHaveURL(/\/subjects\/guide-virtual-study-review\/projects\/guide-virtual-study-review\/workbench/)
  await expectGuideStep(page, "第 5 步：在工作台录入复述点")
  await expect(page.getByRole("button", { name: "上一步", exact: true })).toHaveCount(0)

  await dispatchClick(page.getByRole("button", { name: "01 向量与线性组合" }))
  await expectGuideStep(page, "第 5 步：在工作台录入复述点")
  await expect(page.getByRole("button", { name: "上一步", exact: true })).toHaveCount(0)

  await dispatchClick(page.getByRole("button", { name: "添加", exact: true }))
  await expectGuideStep(page, "第 4 步：填写问题")
  await expect(page.getByPlaceholder("请输入问题/提示语")).toHaveValue("线性组合的目标是什么？")
  await expect(page.getByRole("button", { name: "下一步", exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "上一步", exact: true })).toHaveCount(0)
  await completeGuideStep(page, "fill-recall-question")
  await expectGuideStep(page, "第 4 步：填写问题")

  await page.getByRole("button", { name: "下一步", exact: true }).click()
  await expectGuideStep(page, "第 5 步：填写答案")
  await expect(page.getByPlaceholder("请输入答案/复述内容")).toHaveValue("用一组基向量和对应系数表示目标向量。")
  await expect(page.getByRole("button", { name: "下一步", exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "上一步", exact: true })).toHaveCount(0)
  await completeGuideStep(page, "fill-recall-answer")
  await expectGuideStep(page, "第 5 步：填写答案")

  await page.getByRole("button", { name: "下一步", exact: true }).click()
  await expectGuideStep(page, "第 5 步：在工作台录入复述点")
  await expect(page.getByRole("button", { name: "下一步", exact: true })).toHaveCount(0)
  await expect(page.getByRole("button", { name: "上一步", exact: true })).toHaveCount(0)

  await expect(page.getByRole("button", { name: "提交学习", exact: true })).toBeEnabled()
  await dispatchClick(page.getByRole("button", { name: "提交学习", exact: true }))
  await expectGuideStep(page, "第 6 步：填写复习答案")
  await expect(page.getByPlaceholder("先写下自己的答案，提交后会自动展开标准答案。")).toHaveValue("线性组合可以用基向量和系数表示目标向量。")
  await expect(page.getByRole("button", { name: "下一步", exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "上一步", exact: true })).toHaveCount(0)
  const reviewAnswerTargetBox = await page.locator('[data-guide-tour="review-answer-editor"]').boundingBox()
  const submitReviewAnswerButtonBox = await page.getByRole("button", { name: "提交答案", exact: true }).boundingBox()
  expect(reviewAnswerTargetBox).not.toBeNull()
  expect(submitReviewAnswerButtonBox).not.toBeNull()
  const guideStagePadding = 8
  expect((reviewAnswerTargetBox?.y ?? 0) + (reviewAnswerTargetBox?.height ?? 0) + guideStagePadding).toBeLessThanOrEqual(
    (submitReviewAnswerButtonBox?.y ?? 0) - 1,
  )
  await completeGuideStep(page, "fill-review-answer")
  await expectGuideStep(page, "第 6 步：填写复习答案")

  await page.getByRole("button", { name: "下一步", exact: true }).click()
  await expectGuideStep(page, "第 6 步：做复习")
  await expect(page.getByRole("button", { name: "提交答案", exact: true })).toBeEnabled()
  await expect(page.getByText("系统会")).toHaveCount(0)
  await expect(page.getByText("引导会")).toHaveCount(0)
  await dispatchClick(page.getByRole("button", { name: "提交答案", exact: true }))
  await expectGuideStep(page, "第 6 步：做复习")
  await dispatchClick(page.getByRole("button", { name: "记得", exact: true }))
  await expectGuideStep(page, "第 6 步：做复习")
  await dispatchClick(page.getByRole("button", { name: "提交本轮复习", exact: true }))
  await expect(page).toHaveURL(/\/subjects$/)
  await expect(page.getByText("学习复习引导示范学科")).toHaveCount(0)
  await expect(page.getByText("学习复习引导示范项目")).toHaveCount(0)
  const persistedAppState = await page.evaluate(() => JSON.parse(window.localStorage.getItem("plm-app") || "{}").state ?? {})
  expect(persistedAppState.selectedSubjectId).not.toBe("guide-virtual-study-review-subject")
  expect(persistedAppState.selectedSubjectId).not.toBe("guide-virtual-study-review")
  expect(persistedAppState.selectedWorkbenchProjectId).not.toBe("guide-virtual-study-review")
  const selectedWorkbenchProjectRefKey = persistedAppState.selectedWorkbenchProjectRef
    ? `${persistedAppState.selectedWorkbenchProjectRef.subjectId}:${persistedAppState.selectedWorkbenchProjectRef.scopedProjectId}`
    : ""
  expect(selectedWorkbenchProjectRefKey).not.toBe("guide-virtual-study-review:guide-virtual-study-review")
  expect(selectedWorkbenchProjectRefKey).not.toBe("guide-virtual-study-review-subject:guide-virtual-study-review")
  expect(persistedAppState.recentSubjectIds ?? []).not.toContain("guide-virtual-study-review")
  expect(persistedAppState.recentSubjectIds ?? []).not.toContain("guide-virtual-study-review-subject")
  expect(persistedAppState.recentWorkbenchProjectRefs ?? []).not.toContainEqual({
    subjectId: "guide-virtual-study-review",
    scopedProjectId: "guide-virtual-study-review",
  })
  expect(persistedAppState.recentWorkbenchProjectRefs ?? []).not.toContainEqual({
    subjectId: "guide-virtual-study-review-subject",
    scopedProjectId: "guide-virtual-study-review",
  })

  expectNoConsoleIssues(consoleIssues)
})

test("project settings shows concise convergence template copy", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.goto(projectPath("/settings"))
  await expect(page.getByText("复习链模板")).toBeVisible()
  await expect(page.getByText("推送上次复习时不记得的重点")).toBeVisible()
  await expect(page.getByText("完成一轮后决定是否继续生成复习任务。")).toHaveCount(0)
  await expect(page.getByText("这个步骤没有额外参数")).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test("project settings hides Baidu Netdisk import even when the backend capability is enabled", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page, { systemCapabilities: { baiduNetdiskEnabled: true } })

  await page.goto(projectPath("/settings"))
  await expect(page.getByText("当前网课项目")).toBeVisible()
  await expect(page.getByText("百度网盘视频")).toHaveCount(0)
  await expect(page.getByRole("button", { name: "从百度网盘导入" })).toHaveCount(0)

  expectNoConsoleIssues(consoleIssues)
})

test("project settings does not probe every missing instance before showing repair count", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  let recallPointProbeCount = 0
  page.on("request", (request) => {
    const pathname = new URL(request.url()).pathname
    if (pathname.includes("/instances/") && pathname.endsWith("/recall-points")) {
      recallPointProbeCount += 1
    }
  })

  const actionableMissingId = "inst_missing_actionable"
  const staleMissingInstances = Array.from({ length: 40 }, (_, index) => ({
    instanceId: `inst_missing_stale_${index}`,
    materialId: `stale-${index}.mp4`,
    materialDisplayName: `stale-${index}.mp4`,
    presence: "MISSING",
    lastSeenAt: null,
    mediaSourceKind: "BROWSER_LOCAL",
    playbackKind: "FILE",
    durationMs: null,
  }))
  await installMockApi(page, {
    instances: [
      instance,
      {
        instanceId: actionableMissingId,
        materialId: "missing-actionable.mp4",
        materialDisplayName: "missing-actionable.mp4",
        presence: "MISSING",
        lastSeenAt: null,
        mediaSourceKind: "BROWSER_LOCAL",
        playbackKind: "FILE",
        durationMs: null,
      },
      ...staleMissingInstances,
    ],
    missingInstanceIds: [actionableMissingId],
    recallPointIdsByInstanceId: {
      [actionableMissingId]: ["rp_missing_actionable"],
    },
  })

  await page.goto(projectPath("/settings"))
  await expect(page.getByText("1 个待修复")).toBeVisible()
  expect(recallPointProbeCount).toBeLessThanOrEqual(1)

  expectNoConsoleIssues(consoleIssues)
})

test("recommended review actions live inside the review task card", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await page.goto(projectPath("/recommended-reviews"))
  await expect(page.getByRole("heading", { name: "推荐复习" })).toHaveCount(0)
  await expect(page.getByRole("link", { name: "返回工作台" })).toHaveCount(0)

  const reviewTaskCard = page.locator(".theme-card-main").filter({ has: page.getByRole("heading", { name: "复习任务" }) })
  await expect(reviewTaskCard).toBeVisible()
  const completedText = reviewTaskCard.getByText(/已完成 \d+ \/ \d+/)
  const thresholdButton = reviewTaskCard.getByRole("button", { name: "更新推荐阈值" })
  await expect(completedText).toBeVisible()
  await expect(thresholdButton).toBeVisible()

  const completedBox = await completedText.boundingBox()
  const thresholdButtonBox = await thresholdButton.boundingBox()
  expect(completedBox).not.toBeNull()
  expect(thresholdButtonBox).not.toBeNull()
  expect((thresholdButtonBox?.x ?? 0)).toBeGreaterThan((completedBox?.x ?? 0) + (completedBox?.width ?? 0) - 1)

  expectNoConsoleIssues(consoleIssues)
})

test("subject cards show a leading icon like project cards", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await gotoProjects(page)
  const subjectCard = page.getByTestId(`subject-card-${subject.subjectId}`)
  await expect(subjectCard.getByTestId("subject-card-icon")).toBeVisible()

  expectNoConsoleIssues(consoleIssues)
})

test("subject and project cards share title meta and selected styles", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)
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

  const selectedShadowClass = /shadow-\[0_24px_60px_-38px_rgba\(30,58,95,0\.34\)\]/

  await gotoProjects(page)
  const subjectCard = page.getByTestId(`subject-card-${subject.subjectId}`)
  const subjectHeading = subjectCard.getByRole("heading", { name: subject.title })
  const subjectTitleStack = subjectHeading.locator("xpath=..")
  await expect(subjectHeading).toHaveClass(/text-lg/)
  await expect(subjectTitleStack).toHaveClass(/(^|\s)space-y-2(\s|$)/)
  await expect(subjectTitleStack.locator("p").first()).not.toHaveClass(/(^|\s)mt-1(\s|$)/)
  await expect(subjectCard.getByTestId("subject-card-project-count")).toHaveClass(/theme-meta-strong/)
  await expect(subjectCard).toHaveClass(/border-primary\/20/)
  await expect(subjectCard).toHaveClass(selectedShadowClass)
  await expect(subjectCard).toHaveClass(/ring-primary\/10/)

  await page.goto(`/subjects/${subject.subjectId}`)
  const projectCard = page.getByTestId(`project-card-${material.materialId}`)
  const projectHeading = projectCard.getByRole("heading", { name: project.title })
  const projectTitleStack = projectHeading.locator("xpath=..")
  await expect(projectHeading).toHaveClass(/text-lg/)
  await expect(projectTitleStack).toHaveClass(/(^|\s)space-y-2(\s|$)/)
  await expect(projectTitleStack.locator("p").first()).not.toHaveClass(/(^|\s)mt-1(\s|$)/)
  await expect(projectCard.getByTestId("project-card-type")).toHaveClass(/theme-meta-strong/)
  await expect(projectCard.getByText("当前项目", { exact: true })).toBeVisible()
  await expect(projectCard).toHaveClass(/border-primary\/20/)
  await expect(projectCard).toHaveClass(selectedShadowClass)
  await expect(projectCard).toHaveClass(/ring-primary\/10/)

  expectNoConsoleIssues(consoleIssues)
})

test("delete confirmation dialogs keep confirmation copy inside the input", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await gotoProjects(page)
  await page.getByRole("button", { name: "删除" }).click()
  const subjectDialog = page.getByRole("dialog", { name: "删除学科" })
  await expect(subjectDialog).toBeVisible()
  await expect(subjectDialog.getByText(`这会移除“${subject.title}”的当前学科入口。`, { exact: true })).toBeVisible()
  await expect(subjectDialog.getByText("并清掉本浏览器里与该学科相关的已选状态和草稿缓存。")).toHaveCount(0)
  await expect(subjectDialog.getByText("输入学科标题以确认删除")).toHaveCount(0)
  await expect(subjectDialog.getByText(`请输入 ${subject.title} 完成确认。`)).toHaveCount(0)
  await expect(subjectDialog.getByPlaceholder(`请输入 ${subject.title} 完成确认。`)).toBeVisible()

  await subjectDialog.getByRole("button", { name: "取消" }).click()
  await openSubject(page)
  await page.getByRole("button", { name: "删除" }).click()
  const materialDialog = page.getByRole("dialog", { name: "删除项目" })
  await expect(materialDialog).toBeVisible()
  await expect(materialDialog.getByText(`这会移除“${material.title}”和它的工作台。`, { exact: true })).toBeVisible()
  await expect(materialDialog.getByText(`学科“${subject.title}”以及其他项目会保留。`)).toHaveCount(0)
  await expect(materialDialog.getByText("输入项目名称以确认删除")).toHaveCount(0)
  await expect(materialDialog.getByText(`请输入 ${material.title} 完成确认。`)).toHaveCount(0)
  await expect(materialDialog.getByPlaceholder(`请输入 ${material.title} 完成确认。`)).toBeVisible()

  expectNoConsoleIssues(consoleIssues)
})
