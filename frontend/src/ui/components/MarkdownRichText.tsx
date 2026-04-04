import { type ReactNode, useMemo } from "react"
import ReactMarkdown, { type Components } from "react-markdown"
import rehypeKatex from "rehype-katex"
import remarkBreaks from "remark-breaks"
import remarkGfm from "remark-gfm"
import remarkMath from "remark-math"
import "katex/dist/katex.min.css"

import { cn } from "@/ui/utils"

function flattenText(children: ReactNode): string {
  if (children === null || children === undefined || typeof children === "boolean") return ""
  if (typeof children === "string" || typeof children === "number") return String(children)
  if (Array.isArray(children)) return children.map((child) => flattenText(child)).join("")
  return ""
}

function normalizeMathDelimitersOutsideCode(text: string) {
  return text
    .replace(/\\\[\s*([\s\S]+?)\s*\\\]/g, (_match, expression: string) => `\n\n$$\n${expression.trim()}\n$$\n\n`)
    .replace(/\\\(([\s\S]+?)\\\)/g, (_match, expression: string) => {
      const trimmed = expression.trim()
      if (!trimmed) return ""
      if (trimmed.includes("\n")) return `\n\n$$\n${trimmed}\n$$\n\n`
      return `$${trimmed}$`
    })
}

function normalizeMarkdownMath(text: string) {
  const fencedSegments = text.split(/(```[\s\S]*?```|~~~[\s\S]*?~~~)/g)
  return fencedSegments
    .map((segment) => {
      if (
        (segment.startsWith("```") && segment.endsWith("```")) ||
        (segment.startsWith("~~~") && segment.endsWith("~~~"))
      ) {
        return segment
      }

      const inlineCodeSegments = segment.split(/(`[^`\n]+`)/g)
      return inlineCodeSegments
        .map((inlineSegment) => {
          if (/^`[^`\n]+`$/.test(inlineSegment)) return inlineSegment
          return normalizeMathDelimitersOutsideCode(inlineSegment)
        })
        .join("")
    })
    .join("")
}

const markdownComponents: Components = {
  p({ children }) {
    return <p className="break-words text-[15px] leading-7 text-foreground">{children}</p>
  },
  a({ href, children }) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noreferrer"
        className="font-medium text-primary underline decoration-primary/30 underline-offset-4 hover:decoration-primary"
      >
        {children}
      </a>
    )
  },
  h1({ children }) {
    return <h1 className="text-2xl font-semibold leading-9 text-foreground">{children}</h1>
  },
  h2({ children }) {
    return <h2 className="text-xl font-semibold leading-8 text-foreground">{children}</h2>
  },
  h3({ children }) {
    return <h3 className="text-lg font-semibold leading-8 text-foreground">{children}</h3>
  },
  h4({ children }) {
    return <h4 className="text-base font-semibold leading-7 text-foreground">{children}</h4>
  },
  blockquote({ children }) {
    return (
      <blockquote className="border-l-2 border-[color:var(--theme-soft-border)] pl-4 text-[15px] leading-7 text-muted-foreground">
        {children}
      </blockquote>
    )
  },
  ul({ children }) {
    return <ul className="list-disc space-y-2 pl-6 text-[15px] leading-7 text-foreground">{children}</ul>
  },
  ol({ children }) {
    return <ol className="list-decimal space-y-2 pl-6 text-[15px] leading-7 text-foreground">{children}</ol>
  },
  li({ children }) {
    return <li>{children}</li>
  },
  hr() {
    return <hr className="border-[color:var(--theme-soft-border)]" />
  },
  table({ children }) {
    return (
      <div className="overflow-x-auto rounded-[1.25rem] border border-[color:var(--theme-soft-border)]">
        <table className="min-w-full border-collapse text-left text-sm leading-6 text-foreground">{children}</table>
      </div>
    )
  },
  th({ children }) {
    return (
      <th className="border-b border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3 font-semibold text-foreground">
        {children}
      </th>
    )
  },
  td({ children }) {
    return <td className="border-b border-[color:var(--theme-soft-border)] px-4 py-3 align-top">{children}</td>
  },
  img({ src, alt }) {
    return (
      <img
        src={src ?? ""}
        alt={alt ?? ""}
        loading="lazy"
        className="max-h-[28rem] rounded-[1.25rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] object-contain"
      />
    )
  },
  pre({ children }) {
    return <>{children}</>
  },
  code({ className, children, ...props }) {
    const content = flattenText(children).replace(/\n$/, "")
    const isBlock = Boolean(className) || content.includes("\n")

    if (isBlock) {
      return (
        <pre className="overflow-x-auto rounded-[1.25rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-4">
          <code className={cn("font-mono text-sm leading-6 text-[color:var(--theme-subtle-text)]", className)} {...props}>
            {content}
          </code>
        </pre>
      )
    }

    return (
      <code
        className="rounded-md border border-[color:var(--theme-subtle-border)] bg-[color:var(--theme-subtle-bg)] px-1.5 py-0.5 font-mono text-[0.92em] text-[color:var(--theme-subtle-text)]"
        {...props}
      >
        {content}
      </code>
    )
  },
}

export function MarkdownRichText({ text, className }: { text: string; className?: string }) {
  const normalizedText = useMemo(() => normalizeMarkdownMath(text.replace(/\r\n/g, "\n")), [text])

  return (
    <div className={cn("space-y-4", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={markdownComponents}
      >
        {normalizedText}
      </ReactMarkdown>
    </div>
  )
}
