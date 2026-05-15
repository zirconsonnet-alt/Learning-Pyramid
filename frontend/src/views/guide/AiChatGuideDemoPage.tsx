import { CheckCircle2, MessageSquareText, Send } from "lucide-react"
import { useState } from "react"

import { Button } from "@/ui/components/ui/button"
import { completeGuideWalkthroughStep } from "@/ui/guideWalkthrough/guideWalkthroughController"
import { cn } from "@/ui/utils"

const SAMPLE_NODES = ["第 2 章 随机变量", "2.1 分布函数.mp4", "2.2 常见分布.mp4"]
const GUIDE_QUESTION = "请用更容易懂的话解释这个小节。"
const GUIDE_ANSWER = "可以把分布函数理解成“随机变量落在某个位置左边的累计概率”。横轴上的点越往右，累计进去的概率通常越多。"

export function AiChatGuideDemoPage() {
  const [selectedNode, setSelectedNode] = useState("")
  const [message, setMessage] = useState(GUIDE_QUESTION)
  const [sent, setSent] = useState(false)

  function selectNode(node: string) {
    setSelectedNode(node)
    completeGuideWalkthroughStep("ai-select-node")
  }

  function sendMessage() {
    setSent(true)
    completeGuideWalkthroughStep("ai-send-message")
  }

  return (
    <div className="space-y-5">
      <section className="grid min-h-[calc(100dvh-10rem)] gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="overflow-hidden rounded-[1.75rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] shadow-[var(--theme-soft-shadow)] xl:sticky xl:top-28 xl:self-start">
          <div className="border-b border-[color:var(--theme-soft-border)] px-4 py-4">
            <div className="text-sm font-semibold text-foreground">学习对象目录</div>
          </div>
          <div className="space-y-2 px-4 py-4">
            {SAMPLE_NODES.map((node) => {
              const active = selectedNode === node
              const selectable = node.endsWith(".mp4")
              return (
                <button
                  key={node}
                  type="button"
                  data-guide-tour={node === SAMPLE_NODES[1] ? "ai-learning-object-node" : undefined}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 rounded-2xl px-3 py-3 text-left text-sm transition",
                    active
                      ? "bg-[hsl(var(--primary)/0.1)] text-foreground shadow-[0_18px_36px_-30px_hsl(var(--primary)/0.45)]"
                      : selectable
                        ? "text-[color:var(--theme-subtle-text)] hover:bg-[color:var(--theme-soft-bg)] hover:text-foreground"
                        : "text-muted-foreground",
                  )}
                  onClick={() => {
                    if (selectable) selectNode(node)
                  }}
                >
                  <span className="min-w-0 truncate font-medium">{node}</span>
                  {active ? <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" /> : null}
                </button>
              )
            })}
          </div>
        </aside>

        <section className="flex min-h-[calc(100dvh-10rem)] flex-col overflow-hidden rounded-[2rem] border border-[color:var(--theme-soft-border)] bg-[linear-gradient(180deg,hsl(var(--background)/0.96),hsl(var(--background)/0.92))] shadow-[0_34px_90px_-46px_rgba(15,23,42,0.28)]">
          <div className="border-b border-[color:var(--theme-soft-border)] px-5 py-4 sm:px-7">
            <div className="flex flex-wrap items-center gap-2">
              <span className="theme-meta-strong">学习对象节点</span>
              <span className="truncate text-lg font-semibold tracking-tight text-foreground">{selectedNode || "未选择节点"}</span>
            </div>
          </div>

          <div className="flex-1 space-y-5 px-4 py-6 sm:px-7">
            {!selectedNode ? (
              <div className="mx-auto flex max-w-3xl flex-col items-center px-2 pt-16 text-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-[1.75rem] bg-[linear-gradient(135deg,hsl(var(--primary)),hsl(var(--primary)/0.72))] text-primary-foreground shadow-[0_24px_48px_-26px_hsl(var(--primary)/0.5)]">
                  <MessageSquareText className="h-7 w-7" />
                </div>
                <div className="mt-6 text-3xl font-semibold tracking-tight text-foreground">先选择一个节点开始提问</div>
              </div>
            ) : (
              <div className="space-y-5">
                <div className="rounded-[1.75rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-5 py-4 text-sm leading-6 text-foreground">
                  当前上下文：{selectedNode}
                </div>
                {sent ? (
                  <div data-guide-tour="ai-answer-result" className="flex gap-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,hsl(var(--primary)),hsl(var(--primary)/0.72))] text-primary-foreground">
                      <MessageSquareText className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 flex-1 rounded-[1.75rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] px-5 py-4 text-[15px] leading-7 text-foreground">
                      {GUIDE_ANSWER}
                    </div>
                  </div>
                ) : null}
              </div>
            )}
          </div>

          <div className="border-t border-[color:var(--theme-soft-border)] px-4 py-4 sm:px-7">
            <div data-guide-tour="ai-message-composer" className="rounded-[1.75rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)]">
              <label htmlFor="guide-ai-message" className="sr-only">
                提问内容
              </label>
              <textarea
                id="guide-ai-message"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                className="min-h-[128px] w-full resize-none rounded-t-[1.75rem] bg-transparent px-5 py-4 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground"
                placeholder="写下你想问的问题"
              />
              <div className="flex justify-end border-t border-[color:var(--theme-soft-border)] px-4 py-3">
                <Button
                  type="button"
                  data-guide-tour="ai-send-message-button"
                  onClick={sendMessage}
                  disabled={!selectedNode || !message.trim()}
                  className="justify-center"
                >
                  <Send className="h-4 w-4" />
                  发送问题
                </Button>
              </div>
            </div>
          </div>
        </section>
      </section>
    </div>
  )
}
