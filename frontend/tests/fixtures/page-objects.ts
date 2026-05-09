import { expect, type Page } from "@playwright/test"

import { project, subject } from "./test-data"

export function projectPath(suffix: string) {
  const normalizedSuffix = suffix.startsWith("/") ? suffix : `/${suffix}`
  return `/subjects/${subject.subjectId}/projects/${project.projectId}${normalizedSuffix}`
}

export async function gotoProjects(page: Page) {
  await page.goto("/projects")
  await expect(page.getByRole("heading", { name: "所有学科" })).toBeVisible()
}

export async function openSubject(page: Page) {
  await gotoProjects(page)
  await expect(page.getByText(subject.title)).toBeVisible()
  await page.getByRole("button", { name: /进入学科/ }).first().click()
  await expect(page).toHaveURL(new RegExp(`/subjects/${subject.subjectId}`))
}

export async function gotoWorkbench(page: Page) {
  await page.goto(projectPath("/workbench"))
  await expect(page.getByText("工作状态")).toBeVisible()
}
