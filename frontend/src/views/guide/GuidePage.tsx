import { startTransition, type ReactNode } from "react"
import { Copy } from "lucide-react"
import katex from "katex"
import "katex/dist/katex.min.css"
import { useSearchParams } from "react-router-dom"

import methodGuideMarkdown from "../../../../docs/plm-method-guide.md?raw"
import userManualMarkdown from "../../../../docs/learningpyramid-user-manual.md?raw"

import { Button } from "@/ui/components/ui/button"
import {
  getOfficialCommunityCopyLabel,
  getOfficialCommunityCopySuccessMessage,
  getOfficialCommunityCopySuccessTitle,
  getOfficialCommunityCopyValue,
} from "@/ui/officialCommunity"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"
import { copyTextToClipboard } from "@/views/membership/membershipUi"

type HeadingLevel = 1 | 2 | 3 | 4 | 5 | 6

type MarkdownHeading = {
  id: string
  level: HeadingLevel
  text: string
}

type MarkdownBlock =
  | {
      type: "heading"
      id: string
      level: HeadingLevel
      text: string
    }
  | {
      type: "paragraph"
      text: string
    }
  | {
      type: "list"
      ordered: boolean
      items: string[]
    }
  | {
      type: "rule"
    }
  | {
      type: "math"
      text: string
    }
  | {
      type: "code"
      text: string
    }

type ParsedMarkdown = {
  title: string
  blocks: MarkdownBlock[]
  headings: MarkdownHeading[]
}

type DocDefinition = {
  slug: string
  label: string
  audience: string
  summary: string
  sourcePath: string
  parsed: ParsedMarkdown
}

function decodeMarkdownEscapes(text: string) {
  return text.replace(/\\([\\`*_{}#+.!&>-])/g, "$1")
}

function escapeHtml(text: string) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;")
}

function renderMathHtml(expression: string, displayMode: boolean) {
  try {
    return katex.renderToString(expression, {
      displayMode,
      throwOnError: false,
      strict: "ignore",
    })
  } catch {
    return escapeHtml(expression)
  }
}

function parseMarkdown(source: string): ParsedMarkdown {
  const lines = source.replace(/\r\n/g, "\n").split("\n")
  const blocks: MarkdownBlock[] = []
  const headings: MarkdownHeading[] = []

  let index = 0
  let pendingAnchorId: string | null = null

  while (index < lines.length) {
    const rawLine = lines[index]
    const trimmed = rawLine.trim()

    if (!trimmed) {
      index += 1
      continue
    }

    const anchorMatch = trimmed.match(/^<a id="([^"]+)"><\/a>$/)
    if (anchorMatch) {
      pendingAnchorId = anchorMatch[1]
      index += 1
      continue
    }

    const headingMatch = rawLine.match(/^(#{1,6})\s+(.*)$/)
    if (headingMatch) {
      const level = headingMatch[1].length as HeadingLevel
      const text = decodeMarkdownEscapes(headingMatch[2].trim())
      const id = pendingAnchorId ?? `section-${headings.length + 1}`
      pendingAnchorId = null

      const heading = { id, level, text }
      headings.push(heading)
      blocks.push({ type: "heading", ...heading })
      index += 1
      continue
    }

    if (/^---+$/.test(trimmed)) {
      blocks.push({ type: "rule" })
      index += 1
      continue
    }

    if (trimmed === "\\[") {
      const formulaLines: string[] = []
      index += 1
      while (index < lines.length) {
        const formulaLine = lines[index].trimEnd()
        index += 1
        if (formulaLine.trim() === "\\]") break
        formulaLines.push(formulaLine)
      }
      blocks.push({ type: "math", text: formulaLines.join("\n").trim() })
      continue
    }

    const codeFenceMatch = trimmed.match(/^(```|~~~)/)
    if (codeFenceMatch) {
      const fence = codeFenceMatch[1]
      const codeLines: string[] = []
      index += 1

      while (index < lines.length && !lines[index].trim().startsWith(fence)) {
        codeLines.push(lines[index].trimEnd())
        index += 1
      }

      if (index < lines.length) index += 1
      blocks.push({ type: "code", text: codeLines.join("\n") })
      continue
    }

    const unorderedMatch = rawLine.match(/^[-*]\s+(.*)$/)
    const orderedMatch = rawLine.match(/^\d+\.\s+(.*)$/)
    if (unorderedMatch || orderedMatch) {
      const ordered = Boolean(orderedMatch)
      const items: string[] = []

      while (index < lines.length) {
        const listLine = lines[index]
        const nextMatch = ordered ? listLine.match(/^\d+\.\s+(.*)$/) : listLine.match(/^[-*]\s+(.*)$/)
        if (!nextMatch) break
        items.push(decodeMarkdownEscapes(nextMatch[1].trimEnd()))
        index += 1
      }

      blocks.push({ type: "list", ordered, items })
      continue
    }

    const paragraphLines: string[] = []
    while (index < lines.length) {
      const paragraphLine = lines[index]
      const nextTrimmed = paragraphLine.trim()

      if (!nextTrimmed) break
      if (/^<a id="([^"]+)"><\/a>$/.test(nextTrimmed)) break
      if (/^(#{1,6})\s+/.test(paragraphLine)) break
      if (/^---+$/.test(nextTrimmed)) break
      if (nextTrimmed === "\\[") break
      if (/^(```|~~~)/.test(nextTrimmed)) break
      if (/^[-*]\s+/.test(paragraphLine) || /^\d+\.\s+/.test(paragraphLine)) break

      paragraphLines.push(decodeMarkdownEscapes(paragraphLine.trimEnd()))
      index += 1
    }

    if (paragraphLines.length > 0) {
      blocks.push({ type: "paragraph", text: paragraphLines.join("\n") })
      continue
    }

    index += 1
  }

  return {
    title: headings[0]?.text ?? "文档",
    blocks,
    headings,
  }
}

const docs: DocDefinition[] = [
  {
    slug: "manual",
    label: "系统使用说明",
    audience: "面向使用者",
    summary: "从创建项目、整理内容到录入复述点和完成复习，按当前界面一步步上手。",
    sourcePath: "仓库文档 / 系统使用说明",
    parsed: parseMarkdown(userManualMarkdown),
  },
  {
    slug: "method",
    label: "方法说明",
    audience: "面向使用者",
    summary: "解释 LearningPyramid 的核心思路、分层复习逻辑，以及为什么要这样组织学习。",
    sourcePath: "仓库文档 / 方法说明",
    parsed: parseMarkdown(methodGuideMarkdown),
  },
]

function renderInline(text: string, keyPrefix: string) {
  const pieces: Array<ReactNode> = []
  const pattern = /(`[^`]+`)|(\\\((?:\\.|[^\\])+?\\\))|(\[[^\]]+\]\([^)]+\))|(\*\*[^*]+\*\*)/g
  let lastIndex = 0
  let pieceIndex = 0

  for (const match of text.matchAll(pattern)) {
    const matchedText = match[0]
    const startIndex = match.index ?? 0

    if (startIndex > lastIndex) {
      pieces.push(text.slice(lastIndex, startIndex))
    }

    if (matchedText.startsWith("`")) {
      pieces.push(
        <code
          key={`${keyPrefix}-code-${pieceIndex}`}
          className="rounded-md border border-[color:var(--theme-subtle-border)] bg-[color:var(--theme-subtle-bg)] px-1.5 py-0.5 font-mono text-[0.92em] text-[color:var(--theme-subtle-text)]"
        >
          {matchedText.slice(1, -1)}
        </code>,
      )
    } else if (matchedText.startsWith("\\(")) {
      pieces.push(
        <span
          key={`${keyPrefix}-math-${pieceIndex}`}
          className="inline-block align-middle"
          dangerouslySetInnerHTML={{
            __html: renderMathHtml(matchedText.slice(2, -2).trim(), false),
          }}
        />,
      )
    } else if (matchedText.startsWith("[")) {
      const linkMatch = matchedText.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
      if (linkMatch) {
        pieces.push(
          <a
            key={`${keyPrefix}-link-${pieceIndex}`}
            href={linkMatch[2]}
            className="font-medium text-primary underline decoration-primary/30 underline-offset-4 hover:decoration-primary"
          >
            {linkMatch[1]}
          </a>,
        )
      }
    } else if (matchedText.startsWith("**")) {
      pieces.push(
        <strong key={`${keyPrefix}-strong-${pieceIndex}`} className="font-semibold text-foreground">
          {matchedText.slice(2, -2)}
        </strong>,
      )
    }

    pieceIndex += 1
    lastIndex = startIndex + matchedText.length
  }

  if (lastIndex < text.length) {
    pieces.push(text.slice(lastIndex))
  }

  return pieces
}

function MarkdownContent({ blocks }: { blocks: MarkdownBlock[] }) {
  return (
    <div className="space-y-6">
      {blocks.map((block, blockIndex) => {
        if (block.type === "heading") {
          const headingClassName =
            block.level === 1
              ? "scroll-mt-28 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl"
              : block.level === 2
                ? "scroll-mt-28 pt-2 text-2xl font-semibold tracking-tight text-foreground"
                : block.level === 3
                  ? "scroll-mt-28 text-xl font-semibold text-foreground"
                  : "scroll-mt-28 text-lg font-semibold text-foreground"

          const HeadingTag = `h${block.level}` as const
          return (
            <HeadingTag key={block.id} id={block.id} className={headingClassName}>
              {block.text}
            </HeadingTag>
          )
        }

        if (block.type === "paragraph") {
          return (
            <p key={`paragraph-${blockIndex}`} className="whitespace-pre-wrap text-[15px] leading-7 text-foreground">
              {renderInline(block.text, `paragraph-${blockIndex}`)}
            </p>
          )
        }

        if (block.type === "list") {
          const ListTag = block.ordered ? "ol" : "ul"
          return (
            <ListTag
              key={`list-${blockIndex}`}
              className={cn(
                "space-y-2 pl-6 text-[15px] leading-7 text-foreground",
                block.ordered ? "list-decimal" : "list-disc",
              )}
            >
              {block.items.map((item, itemIndex) => (
                <li key={`item-${blockIndex}-${itemIndex}`}>{renderInline(item, `item-${blockIndex}-${itemIndex}`)}</li>
              ))}
            </ListTag>
          )
        }

        if (block.type === "math") {
          return (
            <div
              key={`math-${blockIndex}`}
              className="overflow-x-auto rounded-[1.25rem] border border-[color:var(--theme-subtle-border)] bg-[color:var(--theme-subtle-bg)] px-4 py-4 text-[color:var(--theme-subtle-text)]"
              dangerouslySetInnerHTML={{ __html: renderMathHtml(block.text, true) }}
            />
          )
        }

        if (block.type === "code") {
          return (
            <pre
              key={`code-${blockIndex}`}
              className="overflow-x-auto rounded-[1.25rem] border border-[color:var(--theme-subtle-border)] bg-[color:var(--theme-subtle-bg)] px-4 py-4 text-sm leading-6 text-[color:var(--theme-subtle-text)]"
            >
              <code>{block.text}</code>
            </pre>
          )
        }

        return <div key={`rule-${blockIndex}`} className="h-px bg-border/80" />
      })}
    </div>
  )
}

export function GuidePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedSlug = searchParams.get("doc")
  const activeDoc = docs.find((item) => item.slug === requestedSlug) ?? docs[0]

  async function onCopyOfficialCommunityContact() {
    try {
      await copyTextToClipboard(getOfficialCommunityCopyValue())
      showSuccessFeedback(getOfficialCommunityCopySuccessTitle(), getOfficialCommunityCopySuccessMessage())
    } catch (err) {
      const message = err instanceof Error ? err.message : "请稍后再试。"
      showErrorFeedback("复制官方群入口失败", message)
    }
  }

  function selectDoc(slug: string) {
    const nextSearchParams = new URLSearchParams(searchParams)
    if (slug === docs[0].slug) nextSearchParams.delete("doc")
    else nextSearchParams.set("doc", slug)

    startTransition(() => {
      setSearchParams(nextSearchParams, { replace: true })
    })

    window.scrollTo({ top: 0, behavior: "smooth" })
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-[18rem_minmax(0,1fr)]">
        <aside className="xl:sticky xl:top-28 xl:self-start">
          <section className="theme-card p-4">
            <div className="mb-3 text-sm font-semibold text-foreground">文档目录</div>
            <div className="space-y-2">
              {docs.map((doc) => {
                const isActive = doc.slug === activeDoc.slug
                return (
                  <button
                    key={doc.slug}
                    type="button"
                    onClick={() => selectDoc(doc.slug)}
                    className={cn(
                      "w-full rounded-2xl border p-4 text-left transition-colors",
                      isActive
                        ? "border-primary/15 bg-primary/10 shadow-[0_14px_30px_-26px_rgba(30,58,95,0.38)]"
                        : "border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] hover:border-primary/15 hover:bg-accent/60",
                    )}
                  >
                    <div className="font-medium text-foreground">{doc.label}</div>
                  </button>
                )
              })}
            </div>
          </section>

          <section className="theme-card mt-4 p-4">
            <div className="text-sm font-semibold text-foreground">官方群与反馈</div>
            <img
              src="/official-community-qq-group.png"
              alt="LearningPyramid 官方群二维码"
              className="mt-4 w-full rounded-[1.25rem] border border-[color:var(--theme-soft-border)] bg-white object-cover"
              loading="lazy"
            />
            <Button type="button" variant="outline" className="mt-4 w-full justify-center" onClick={() => void onCopyOfficialCommunityContact()}>
              <Copy className="h-4 w-4" />
              {getOfficialCommunityCopyLabel()}
            </Button>
          </section>
        </aside>

        <section className="theme-card-main overflow-hidden">
          <div className="px-6 py-8 sm:px-8">
            <MarkdownContent blocks={activeDoc.parsed.blocks} />
          </div>
        </section>
      </div>
    </div>
  )
}
