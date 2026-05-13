import { expect, test } from "@playwright/test"

import { collectConsoleIssues, expectNoConsoleIssues } from "../fixtures/app-checks"
import { installMockApi } from "../fixtures/mock-api"
import { journeyIds } from "../fixtures/journeys"
import { recordJourney } from "../fixtures/journey-result"
import { gotoProjects, openSubject, projectPath } from "../fixtures/page-objects"
import { material, project, subject } from "../fixtures/test-data"

test(journeyIds.subjectProjectEntry, async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await recordJourney(journeyIds.subjectProjectEntry, async () => {
    await openSubject(page)
    await expect(page.getByText(project.title)).toBeVisible()
    await page.getByRole("button", { name: "进入工作台" }).click()
    await expect(page).toHaveURL(new RegExp(projectPath("/workbench")))
    await expect(page.getByText("工作状态")).toBeVisible()
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

test("subject cards show a leading icon like project cards", async ({ page }) => {
  const consoleIssues = collectConsoleIssues(page)
  await installMockApi(page)

  await gotoProjects(page)
  const subjectCard = page.getByTestId(`subject-card-${subject.subjectId}`)
  await expect(subjectCard.getByTestId("subject-card-icon")).toBeVisible()

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
