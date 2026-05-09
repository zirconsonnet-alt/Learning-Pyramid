import { expect, type Page } from "@playwright/test"

const ignoredConsolePatterns = [
  /favicon/i,
]

export function collectConsoleIssues(page: Page) {
  const issues: string[] = []
  page.on("console", (message) => {
    if (message.type() !== "error" && message.type() !== "warning") return
    const text = message.text()
    if (ignoredConsolePatterns.some((pattern) => pattern.test(text))) return
    issues.push(`${message.type()}: ${text}`)
  })
  page.on("pageerror", (error) => {
    issues.push(`pageerror: ${error.message}`)
  })
  return issues
}

export async function expectHealthyPage(page: Page, pathPattern: RegExp | string) {
  if (typeof pathPattern === "string") {
    await expect(page).toHaveURL(new RegExp(`${pathPattern.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?:[?#].*)?$`))
  } else {
    await expect(page).toHaveURL(pathPattern)
  }
  await expect(page.locator("#root")).not.toBeEmpty()
  await expect(page.getByText(/Failed to fetch dynamically imported module|Internal server error|Error:/i)).toHaveCount(0)
  await expect(page.locator("body")).not.toHaveText(/正在准备工作空间$/, { timeout: 1000 })
}

export function expectNoConsoleIssues(issues: string[]) {
  expect(issues, `unexpected console issues:\n${issues.join("\n")}`).toEqual([])
}
