import createSubjectProjectMarkdownSource from "../../../../docs/how-to-create-subject-project.md?raw"
import studyReviewMarkdownSource from "../../../../docs/how-to-study-review.md?raw"

import { DEFAULT_GUIDE_WALKTHROUGH_DOC_SLUG, type GuideWalkthroughDocSlug, type GuideWalkthroughSourceRef } from "./guideWalkthroughSteps"

export const CREATE_SUBJECT_PROJECT_SOURCE_PATH = "docs/how-to-create-subject-project.md"
export const STUDY_REVIEW_SOURCE_PATH = "docs/how-to-study-review.md"

export const guideWalkthroughCopySources: Record<GuideWalkthroughDocSlug, { markdown: string; sourcePath: string }> = {
  "create-subject-project": {
    markdown: createSubjectProjectMarkdownSource,
    sourcePath: CREATE_SUBJECT_PROJECT_SOURCE_PATH,
  },
  "study-review": {
    markdown: studyReviewMarkdownSource,
    sourcePath: STUDY_REVIEW_SOURCE_PATH,
  },
}

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

export function extractManualSections(markdown = guideWalkthroughCopySources[DEFAULT_GUIDE_WALKTHROUGH_DOC_SLUG].markdown): ManualSection[] {
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

function findSection(heading: string, markdown = guideWalkthroughCopySources[DEFAULT_GUIDE_WALKTHROUGH_DOC_SLUG].markdown) {
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

export function resolveGuideWalkthroughCopy(
  sourceRef: GuideWalkthroughSourceRef,
  docSlug: GuideWalkthroughDocSlug = DEFAULT_GUIDE_WALKTHROUGH_DOC_SLUG,
  markdown = guideWalkthroughCopySources[docSlug]?.markdown ?? guideWalkthroughCopySources[DEFAULT_GUIDE_WALKTHROUGH_DOC_SLUG].markdown,
): GuideWalkthroughCopy {
  const sourcePath = guideWalkthroughCopySources[docSlug]?.sourcePath ?? guideWalkthroughCopySources[DEFAULT_GUIDE_WALKTHROUGH_DOC_SLUG].sourcePath
  const section = findSection(sourceRef.heading, markdown)
  if (!section) {
    return {
      title: sourceRef.heading,
      description: sourceRef.heading,
      sourcePath,
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
    sourcePath,
    sourceHeading: section.heading,
  }
}
