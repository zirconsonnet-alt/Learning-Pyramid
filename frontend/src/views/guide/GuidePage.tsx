import { startTransition, type ReactNode } from "react"
import katex from "katex"
import "katex/dist/katex.min.css"
import { useSearchParams } from "react-router-dom"

import methodGuideMarkdown from "../../../../docs/plm-method-guide.md?raw"
import userManualMarkdown from "../../../../docs/learningpyramid-user-manual.md?raw"

import { cn } from "@/ui/utils"

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
    summary: "从创建项目、整理材料到录入复述点和完成复习，按当前界面一步步上手。",
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
          className="rounded-md bg-[#eef4ff] px-1.5 py-0.5 font-mono text-[0.92em] text-[#1e3a5f]"
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
            <p key={`paragraph-${blockIndex}`} className="whitespace-pre-wrap text-[15px] leading-7 text-[#243246]">
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
                "space-y-2 pl-6 text-[15px] leading-7 text-[#243246]",
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
              className="overflow-x-auto rounded-[1.25rem] border border-[#d9e5f2] bg-[#f7faff] px-4 py-4 text-[#1e3a5f]"
              dangerouslySetInnerHTML={{ __html: renderMathHtml(block.text, true) }}
            />
          )
        }

        if (block.type === "code") {
          return (
            <pre
              key={`code-${blockIndex}`}
              className="overflow-x-auto rounded-[1.25rem] border border-[#d9e5f2] bg-[#f7faff] px-4 py-4 text-sm leading-6 text-[#1e3a5f]"
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
  const outlineLevelCap = 3
  const outline = activeDoc.parsed.headings.filter(
    (heading, index) => index > 0 && heading.text !== "目录" && heading.level <= outlineLevelCap,
  )

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
      <section className="theme-card-main overflow-hidden">
        <div className="theme-card-header px-6 py-6 sm:px-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl space-y-3">
              <span className="theme-meta-strong">文档</span>
              <div className="space-y-2">
                <h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">用户指南</h1>
                <p className="text-sm leading-7 text-muted-foreground">
                  这里集中展示 LearningPyramid 的系统使用说明与方法说明，帮助你先完成上手，再理解背后的学习逻辑。
                </p>
              </div>
            </div>
          </div>
        </div>
        <div className="grid gap-3 border-t border-border/60 px-6 py-5 text-sm text-muted-foreground sm:grid-cols-3 sm:px-8">
          <div>
            <div className="font-medium text-foreground">内容来源</div>
            <div className="mt-1">内容直接来自仓库内维护的用户文档，网页不再单独维护一份副本。</div>
          </div>
          <div>
            <div className="font-medium text-foreground">默认阅读</div>
            <div className="mt-1">建议先阅读系统使用说明，先跑通一次完整流程；再阅读方法说明，理解系统为什么这样组织复习。</div>
          </div>
          <div>
            <div className="font-medium text-foreground">阅读方式</div>
            <div className="mt-1">可以按左侧目录选章节阅读，也可以用右侧导航快速跳转到当前文档重点部分。</div>
          </div>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[18rem_minmax(0,1fr)_16rem]">
        <aside className="xl:sticky xl:top-28 xl:self-start">
          <section className="theme-card p-4">
            <div className="mb-3">
              <div className="text-sm font-semibold text-foreground">文档目录</div>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">当前页面收录的用户文档入口。</p>
            </div>
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
                        ? "border-primary/15 bg-[#eef4ff] shadow-[0_14px_30px_-26px_rgba(30,58,95,0.38)]"
                        : "border-border/70 bg-white/90 hover:border-primary/15 hover:bg-accent/60",
                    )}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium text-foreground">{doc.label}</div>
                      <span className={cn("theme-meta", isActive && "border-primary/15 bg-white text-primary")}>
                        {doc.audience}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">{doc.summary}</p>
                    <div className="mt-3 text-xs text-[#486284]">{doc.sourcePath}</div>
                  </button>
                )
              })}
            </div>
          </section>
        </aside>

        <section className="theme-card-main overflow-hidden">
          <div className="theme-card-header px-6 py-6 sm:px-8">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div className="space-y-2">
                <div className="theme-meta-strong">{activeDoc.audience}</div>
                <div>
                  <h2 className="text-2xl font-semibold tracking-tight text-foreground">{activeDoc.label}</h2>
                  <p className="mt-2 max-w-3xl text-sm leading-7 text-muted-foreground">{activeDoc.summary}</p>
                </div>
              </div>
              <div className="rounded-2xl border border-white/80 bg-white/72 px-4 py-3 text-xs leading-5 text-muted-foreground">
                <div className="font-medium text-foreground">内容来源</div>
                <div className="mt-1 text-[#486284]">{activeDoc.sourcePath}</div>
              </div>
            </div>
          </div>
          <div className="px-6 py-8 sm:px-8">
            <MarkdownContent blocks={activeDoc.parsed.blocks} />
          </div>
        </section>

        <aside className="hidden xl:sticky xl:top-28 xl:block xl:self-start">
          <section className="theme-card p-4">
            <div className="mb-3">
              <div className="text-sm font-semibold text-foreground">本页导航</div>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">快速跳到当前文档的主要章节。</p>
            </div>
            <div className="max-h-[70vh] space-y-1 overflow-y-auto pr-1">
              {outline.length > 0 ? (
                outline.map((heading) => (
                  <a
                    key={heading.id}
                    href={`#${heading.id}`}
                    className={cn(
                      "block rounded-xl px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent/60 hover:text-foreground",
                      heading.level >= 3 && "ml-3 text-[13px]",
                    )}
                  >
                    {heading.text}
                  </a>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">当前文档没有可提取的章节导航。</p>
              )}
            </div>
          </section>
        </aside>
      </div>
    </div>
  )
}
