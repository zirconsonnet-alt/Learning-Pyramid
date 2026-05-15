import { Bot, MessageSquareText, Send } from "lucide-react"
import { useState } from "react"

import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { completeGuideWalkthroughStep } from "@/ui/guideWalkthrough/guideWalkthroughController"
import { cn } from "@/ui/utils"

const SAMPLE_NODES = ["第 2 章 随机变量", "2.1 分布函数.mp4", "2.2 常见分布.mp4"]

export function AiChatGuideDemoPage() {
  const [chatOpen, setChatOpen] = useState(false)
  const [selectedNode, setSelectedNode] = useState(SAMPLE_NODES[1])
  const [message, setMessage] = useState("帮我用简单的话解释分布函数。")
  const [sent, setSent] = useState(false)

  function openChat() {
    setChatOpen(true)
    completeGuideWalkthroughStep("ai-open-chat")
  }

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
      <section className="theme-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-sm font-semibold text-foreground">AI 问答引导演示</div>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              这里模拟一个会员和 LLM 都可用的项目，只演示进入 AI 问答、选择学习对象并发起对话，不会调用真实模型。
            </p>
          </div>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="space-y-5 xl:sticky xl:top-28 xl:self-start">
          <Button type="button" data-guide-tour="ai-chat-entry" className="w-full justify-center" onClick={openChat}>
            <Bot className="h-4 w-4" />
            进入项目 AI 问答
          </Button>
        </aside>

        <section className={cn("grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)]", chatOpen ? "" : "opacity-70")}>
          <Card className="theme-card-main">
            <CardHeader className="theme-card-header">
              <CardTitle>学习对象树</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 pt-4">
              {SAMPLE_NODES.slice(0, 1).map((node) => (
                <button
                  key={node}
                  type="button"
                  className={cn(
                    "w-full rounded-[1rem] border px-3 py-3 text-left text-sm transition-colors",
                    selectedNode === node
                      ? "border-primary/20 bg-primary/10 text-foreground"
                      : "border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] text-muted-foreground hover:border-primary/20",
                  )}
                  onClick={() => selectNode(node)}
                >
                  {node}
                </button>
              ))}
              <button
                type="button"
                data-guide-tour="ai-learning-object-node"
                className={cn(
                  "w-full rounded-[1rem] border px-3 py-3 text-left text-sm transition-colors",
                  selectedNode === SAMPLE_NODES[1]
                    ? "border-primary/20 bg-primary/10 text-foreground"
                    : "border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] text-muted-foreground hover:border-primary/20",
                )}
                onClick={() => selectNode(SAMPLE_NODES[1])}
              >
                {SAMPLE_NODES[1]}
              </button>
              {SAMPLE_NODES.slice(2).map((node) => (
                <button
                  key={node}
                  type="button"
                  className={cn(
                    "w-full rounded-[1rem] border px-3 py-3 text-left text-sm transition-colors",
                    selectedNode === node
                      ? "border-primary/20 bg-primary/10 text-foreground"
                      : "border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] text-muted-foreground hover:border-primary/20",
                  )}
                  onClick={() => selectNode(node)}
                >
                  {node}
                </button>
              ))}
            </CardContent>
          </Card>

          <Card className="theme-card-main">
            <CardHeader className="theme-card-header">
              <CardTitle className="flex items-center gap-2">
                <MessageSquareText className="h-5 w-5" />
                对话
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 pt-4">
              <div className="rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3 text-sm">
                当前上下文：{selectedNode}
              </div>
              <div className="rounded-[1rem] border border-primary/15 bg-primary/10 px-4 py-3 text-sm leading-6 text-foreground">
                可以围绕当前节点提问，例如解释概念、整理脉络或生成复习题。
              </div>
              {sent ? (
                <div className="rounded-[1rem] border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm leading-6 text-emerald-900">
                  AI 会结合当前学习对象回答；演示页不会调用真实模型，也不会保存对话。
                </div>
              ) : null}
              <div data-guide-tour="ai-message-composer" className="space-y-3">
                <textarea
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  className="min-h-[112px] w-full rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] px-4 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary/25"
                />
                <Button type="button" onClick={sendMessage} disabled={!message.trim()} className="justify-center">
                  <Send className="h-4 w-4" />
                  发送问题
                </Button>
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  )
}
