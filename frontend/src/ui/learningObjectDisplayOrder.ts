import type { LearningObjectNode } from "@/ui/api/learningObjects"

const TITLE_COLLATOR = new Intl.Collator("zh-Hans-CN", {
  numeric: true,
  sensitivity: "base",
})

const ORDERING_UNIT_RE = /^(章|节|课|集|讲|卷|部|篇|回|季|期|天|周|月|年|号|页|题|册|则|部分)/
const ORDERING_BOUNDARY_RE =
  /^(?:$|[\s\-_.:：、，,。;；/\\|()[\]{}<>【】《》「」『』"'“”‘’]|章|节|课|集|讲|卷|部|篇|回|季|期|天|周|月|年|号|页|题|册|则)/

const CHINESE_DIGIT_VALUE: Record<string, number> = {
  "零": 0,
  "〇": 0,
  "一": 1,
  "二": 2,
  "两": 2,
  "三": 3,
  "四": 4,
  "五": 5,
  "六": 6,
  "七": 7,
  "八": 8,
  "九": 9,
}

const CHINESE_UNIT_VALUE: Record<string, number> = {
  "十": 10,
  "百": 100,
  "千": 1000,
}

type ParsedOrderingPrefix = {
  value: number
  rest: string
}

export function isSyntheticFilesContainer(node: LearningObjectNode | undefined) {
  if (!node || node.kind !== "container") return false
  const title = node.title.trim()
  const relativePath = (node.relativePath ?? "").trim()
  return title === "Files" && (relativePath === "__files__" || relativePath.endsWith("/__files__"))
}

function parseChineseNumeral(text: string): number | null {
  if (!text) return null

  let total = 0
  let current = 0
  let seen = false

  for (const ch of text) {
    if (ch in CHINESE_DIGIT_VALUE) {
      current = CHINESE_DIGIT_VALUE[ch]
      seen = true
      continue
    }

    const unit = CHINESE_UNIT_VALUE[ch]
    if (unit) {
      total += (current || 1) * unit
      current = 0
      seen = true
      continue
    }

    return null
  }

  if (!seen) return null
  return total + current
}

function parseOrderingPrefix(title: string): ParsedOrderingPrefix | null {
  const text = title.trim()
  if (!text) return null

  let index = 0
  if (text.startsWith("第")) index = 1

  const digitMatch = text.slice(index).match(/^\d+/)
  const chineseMatch = digitMatch ? null : text.slice(index).match(/^[零〇一二两三四五六七八九十百千]+/)
  const token = digitMatch?.[0] ?? chineseMatch?.[0] ?? ""
  if (!token) return null

  const value = digitMatch ? Number.parseInt(token, 10) : parseChineseNumeral(token)
  if (value === null || Number.isNaN(value)) return null

  const afterToken = text.slice(index + token.length)
  const unitMatch = afterToken.match(ORDERING_UNIT_RE)
  const unit = unitMatch?.[0] ?? ""
  const restWithBoundary = afterToken.slice(unit.length)

  if (!ORDERING_BOUNDARY_RE.test(restWithBoundary)) {
    return null
  }

  return {
    value,
    rest: restWithBoundary.trim(),
  }
}

export function compareDisplayTitles(left: string, right: string) {
  const leftText = left.trim()
  const rightText = right.trim()
  const leftPrefix = parseOrderingPrefix(leftText)
  const rightPrefix = parseOrderingPrefix(rightText)

  if (leftPrefix && rightPrefix) {
    if (leftPrefix.value !== rightPrefix.value) return leftPrefix.value - rightPrefix.value
    const restCompare = TITLE_COLLATOR.compare(leftPrefix.rest, rightPrefix.rest)
    if (restCompare !== 0) return restCompare
  }

  return TITLE_COLLATOR.compare(leftText, rightText)
}

export function compareLearningObjectNodesForDisplay(left: LearningObjectNode, right: LearningObjectNode) {
  const leftSynthetic = isSyntheticFilesContainer(left)
  const rightSynthetic = isSyntheticFilesContainer(right)
  if (leftSynthetic !== rightSynthetic) return leftSynthetic ? 1 : -1

  if (left.kind !== right.kind) return left.kind === "container" ? -1 : 1

  const titleCompare = compareDisplayTitles(left.title, right.title)
  if (titleCompare !== 0) return titleCompare

  return TITLE_COLLATOR.compare(left.nodeId, right.nodeId)
}

export function sortLearningObjectNodeIdsForDisplay(nodeIds: readonly string[], nodeById: Record<string, LearningObjectNode>) {
  return [...nodeIds].sort((leftId, rightId) => {
    const left = nodeById[leftId]
    const right = nodeById[rightId]

    if (!left && !right) return TITLE_COLLATOR.compare(leftId, rightId)
    if (!left) return 1
    if (!right) return -1

    return compareLearningObjectNodesForDisplay(left, right)
  })
}
