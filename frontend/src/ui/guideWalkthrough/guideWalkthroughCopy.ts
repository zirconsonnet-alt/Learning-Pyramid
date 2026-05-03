import userManualMarkdownSource from "../../../../docs/learningpyramid-user-manual.md?raw"

import type { GuideWalkthroughSourceRef } from "./guideWalkthroughSteps"

export const USER_MANUAL_SOURCE_PATH = "docs/learningpyramid-user-manual.md"
export const userManualMarkdown = userManualMarkdownSource

export type GuideWalkthroughCopy = {
  title: string
  description: string
  sourcePath: string
  sourceHeading: string
}

type ManualSection = {
  heading: string
  lines: string[]
}

function stripInlineMarkdown(value: string) {
  return value
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\\([\\`*_{}#+.!&>-])/g, "$1")
    .trim()
}

export function extractManualSections(markdown = userManualMarkdown): ManualSection[] {
  const sections: ManualSection[] = []
  let current: ManualSection | null = null

  for (const line of markdown.replace(/\r\n/g, "\n").split("\n")) {
    const headingMatch = line.match(/^##\s+(.+)$/)
    if (headingMatch) {
      current = {
        heading: stripInlineMarkdown(headingMatch[1]),
        lines: [],
      }
      sections.push(current)
      continue
    }

    current?.lines.push(line)
  }

  return sections
}

function findSection(heading: string, markdown = userManualMarkdown) {
  return extractManualSections(markdown).find((section) => section.heading === heading) ?? null
}

function extractOrderedItems(section: ManualSection) {
  return section.lines.flatMap((line) => {
    const match = line.match(/^\d+\.\s+(.+)$/)
    return match ? [stripInlineMarkdown(match[1])] : []
  })
}

function extractFirstParagraph(section: ManualSection) {
  let inFence = false
  for (const line of section.lines) {
    const trimmed = line.trim()
    if (/^(```|~~~)/.test(trimmed)) {
      inFence = !inFence
      continue
    }
    if (inFence || !trimmed || trimmed === "---" || /^:::/.test(trimmed) || /^\d+\.\s+/.test(trimmed) || /^[-*]\s+/.test(trimmed)) {
      continue
    }
    return stripInlineMarkdown(trimmed)
  }

  return section.heading
}

export function resolveGuideWalkthroughCopy(sourceRef: GuideWalkthroughSourceRef, markdown = userManualMarkdown): GuideWalkthroughCopy {
  const section = findSection(sourceRef.heading, markdown)
  if (!section) {
    return {
      title: sourceRef.heading,
      description: sourceRef.heading,
      sourcePath: USER_MANUAL_SOURCE_PATH,
      sourceHeading: sourceRef.heading,
    }
  }

  const items = extractOrderedItems(section)
  const description =
    sourceRef.extractMode === "heading"
      ? section.heading
      : sourceRef.extractMode === "paragraph"
        ? extractFirstParagraph(section)
        : sourceRef.extractMode === "summary-from-items"
          ? (sourceRef.itemIndexes ?? []).map((itemIndex) => items[itemIndex - 1]).filter(Boolean).join(" ")
          : sourceRef.itemIndex
            ? items[sourceRef.itemIndex - 1] ?? extractFirstParagraph(section)
            : extractFirstParagraph(section)

  return {
    title: section.heading,
    description: description || section.heading,
    sourcePath: USER_MANUAL_SOURCE_PATH,
    sourceHeading: section.heading,
  }
}
