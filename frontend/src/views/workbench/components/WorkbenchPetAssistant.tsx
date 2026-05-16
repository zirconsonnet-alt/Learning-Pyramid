import { useEffect, useMemo, useRef, useState } from "react"
import { Copy, Image as ImageIcon, Send, Sparkles, Square } from "lucide-react"

import type { Instance } from "@/ui/api/instances"
import type { MaterialSourceKind } from "@/ui/api/projects"
import { ApiError } from "@/ui/api/http"
import type { ScopedProjectRef } from "@/ui/api/projectScope"
import { MarkdownRichText } from "@/ui/components/MarkdownRichText"
import { Button } from "@/ui/components/ui/button"
import { isVirtualStudyReviewProjectId } from "@/ui/guideWalkthrough/guideVirtualProjectIds"
import {
  askCourseAgent,
  buildCourseAgentContextPackage,
  buildCourseAgentContextText,
  type CourseAgentContextPackage,
  type CourseAgentInitialFrame,
  type CourseAgentRecallContext,
} from "@/ui/llm/courseAgent"
import { useProjectDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import { useMembershipSummary } from "@/ui/queries/membership"
import { useProjectMaterialSourceBinding } from "@/ui/queries/projects"
import { useSystemCapabilities } from "@/ui/queries/system"
import type { AiChatCourseEvidence } from "@/ui/store/aiChatStore"
import { showInfoFeedback } from "@/ui/store/feedbackStore"
import { touchDailyStudyActivity } from "@/ui/store/workbenchDailyStats"
import { cn } from "@/ui/utils"

type WorkbenchPetAssistantTurn = {
  id: string
  role: "user" | "assistant"
  content: string
  createdAt: number
  evidence?: AiChatCourseEvidence[]
}

type WorkbenchPetAssistantProps = {
  subjectId: string
  projectId: string
  instance: Instance | null
  currentMs: number
  workStatusDetail: string
  usesResolvableCourseAnchor: boolean
  recallContext?: CourseAgentRecallContext | null
  captureCurrentFrameForAi?: () => Promise<CourseAgentInitialFrame | null>
  onAssistantStateChange?: (state: "idle" | "thinking") => void
  onOpenEvidence?: (evidence: AiChatCourseEvidence) => void
}

const QA_ACTIVITY_WINDOW_MS = 30_000

function createLocalId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

function formatAssistantError(error: unknown) {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`
  if (error instanceof Error) return error.message
  return "雪豹助手暂时不可用"
}

function formatPlaybackClock(ms: number) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`
}

function formatEvidenceTimeRange(startMs: number, endMs: number) {
  return startMs === endMs ? formatPlaybackClock(startMs) : `${formatPlaybackClock(startMs)}-${formatPlaybackClock(endMs)}`
}

function buildWorkbenchSystemPrompt(nodeLabel: string) {
  return [
    "请使用简体中文回答。",
    "你叫雪豹，是学习工作台右侧桌宠弹窗里的 AI 问答助手。",
    `当前问答围绕“${nodeLabel}”和工作台状态展开。`,
    "优先使用当前内容、播放位置、字幕和项目上下文，不要编造项目内不存在的事实。",
    "回答要直接、可执行；如果上下文不足，请明确说明还缺什么。",
  ].join(" ")
}

async function copyContextText(params: {
  subjectId: string
  projectId: string
  instance: Instance
  sourceKind: MaterialSourceKind
  nodeLabel: string
  userPrompt: string
  systemPrompt: string
  currentMs: number
  recallContext?: CourseAgentRecallContext | null
  historyMessages: Array<{ role: "user" | "assistant"; content: string }>
  captureCurrentFrameForAi?: () => Promise<CourseAgentInitialFrame | null>
}) {
  const initialFrame = await params.captureCurrentFrameForAi?.()
  const contextPackage: CourseAgentContextPackage = await buildCourseAgentContextPackage({
    subjectId: params.subjectId,
    projectId: params.projectId,
    instance: params.instance,
    sourceKind: params.sourceKind,
    nodeLabel: params.nodeLabel,
    userPrompt: params.userPrompt,
    systemPrompt: params.systemPrompt,
    anchorMs: initialFrame?.timeMs ?? params.currentMs,
    initialFrame,
    recallContext: params.recallContext,
    historyMessages: params.historyMessages,
  })
  await copyText(buildCourseAgentContextText(contextPackage))
}

async function copyContextImage(params: {
  captureCurrentFrameForAi?: () => Promise<CourseAgentInitialFrame | null>
}) {
  const initialFrame = await params.captureCurrentFrameForAi?.()
  if (!initialFrame?.imageDataUrl) {
    throw new Error("当前视频帧无法复制。")
  }
  await copyImageDataUrl(initialFrame.imageDataUrl)
  return initialFrame
}

async function copyText(text: string) {
  if (!text.trim()) return
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  throw new Error("当前环境不支持剪贴板")
}

async function copyImageDataUrl(imageDataUrl: string) {
  if (!imageDataUrl.trim()) return
  if (typeof navigator === "undefined" || !navigator.clipboard?.write || typeof ClipboardItem === "undefined") {
    throw new Error("当前浏览器不支持图片剪贴板")
  }

  const image = new Image()
  image.decoding = "async"
  image.src = imageDataUrl
  await new Promise<void>((resolve, reject) => {
    image.onload = () => resolve()
    image.onerror = () => reject(new Error("当前视频帧无法复制"))
  })

  const canvas = document.createElement("canvas")
  canvas.width = image.naturalWidth || image.width
  canvas.height = image.naturalHeight || image.height
  const context = canvas.getContext("2d")
  if (!context) throw new Error("当前浏览器不支持图片剪贴板")
  context.drawImage(image, 0, 0)

  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((nextBlob) => {
      if (nextBlob) {
        resolve(nextBlob)
        return
      }
      reject(new Error("当前视频帧无法复制"))
    }, "image/png")
  })

  await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })])
}

export function WorkbenchPetAssistant({
  subjectId,
  projectId,
  instance,
  currentMs,
  workStatusDetail,
  usesResolvableCourseAnchor,
  recallContext,
  captureCurrentFrameForAi,
  onAssistantStateChange,
  onOpenEvidence,
}: WorkbenchPetAssistantProps) {
  const projectScope: ScopedProjectRef = { subjectId, scopedProjectId: projectId }
  const [composer, setComposer] = useState("")
  const [turns, setTurns] = useState<WorkbenchPetAssistantTurn[]>([])
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isAsking, setIsAsking] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const threadEndRef = useRef<HTMLDivElement | null>(null)

  const capabilitiesQ = useSystemCapabilities()
  const authEnabled = capabilitiesQ.data?.authEnabled ?? false
  const membershipQ = useMembershipSummary(authEnabled)
  const materialSourceBindingQ = useProjectMaterialSourceBinding(projectScope)
  const directoryBinding = useProjectDirectoryBinding(projectId)

  const sourceKind = (instance?.mediaSourceKind ?? materialSourceBindingQ.data?.sourceKind ?? null) as MaterialSourceKind | null
  const llmConfigured = capabilitiesQ.data?.llmConfigured ?? false
  const memberBlocked = authEnabled && (membershipQ.isLoading || Boolean(membershipQ.error) || !membershipQ.data?.isActive)
  const virtualProjectBlocked = isVirtualStudyReviewProjectId(projectId)
  const nodeLabel = instance?.materialDisplayName || instance?.materialId || "当前工作台"
  const canUseCourseAgent =
    usesResolvableCourseAnchor &&
    !!instance &&
    !!sourceKind &&
    (sourceKind !== "BROWSER_LOCAL" || directoryBinding.permission === "granted")

  const disabledReason = useMemo(() => {
    if (virtualProjectBlocked) return "引导示范项目不提供 AI 对话。"
    if (capabilitiesQ.isLoading) return "正在确认 AI 服务状态..."
    if (!llmConfigured) return "当前还没有配置可用的 LLM 服务。"
    if (memberBlocked) return "雪豹问答是会员专属功能，请先前往会员中心开通会员。"
    return null
  }, [capabilitiesQ.isLoading, llmConfigured, memberBlocked, virtualProjectBlocked])
  const interactionDisabled = !!disabledReason || isAsking

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
      onAssistantStateChange?.("idle")
    }
  }, [onAssistantStateChange])

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ block: "nearest" })
  }, [turns, status])

  async function submitQuestion() {
    const prompt = composer.trim()
    if (!prompt) {
      setError("先输入一个问题，再让雪豹帮你看工作台。")
      return
    }
    if (interactionDisabled) {
      setError(disabledReason ?? "雪豹助手正在回答上一个问题。")
      return
    }

    touchDailyStudyActivity(projectId, "aiQa", QA_ACTIVITY_WINDOW_MS)
    const controller = new AbortController()
    abortRef.current = controller
    const historyMessages = turns
    const userTurn: WorkbenchPetAssistantTurn = {
      id: createLocalId(),
      role: "user",
      content: prompt,
      createdAt: Date.now(),
    }
    const assistantTurnId = createLocalId()

    setTurns((current) => [...current, userTurn])
    setComposer("")
    setError(null)
    setStatus("正在读取当前工作台...")
    setIsAsking(true)
    onAssistantStateChange?.("thinking")

    try {
      if (!canUseCourseAgent || !instance || !sourceKind) {
        throw new Error("当前工作台没有可用的视频上下文。")
      }

      setTurns((current) => [
        ...current,
        {
          id: assistantTurnId,
          role: "assistant",
          content: "",
          createdAt: Date.now(),
        },
      ])
      setStatus("正在截取当前画面...")
      const initialFrame = await captureCurrentFrameForAi?.()
      if (controller.signal.aborted) return

      const commonParams = {
        subjectId,
        projectId,
        instance,
        sourceKind,
        nodeLabel,
        userPrompt: prompt,
        systemPrompt: `${buildWorkbenchSystemPrompt(nodeLabel)} 当前工作台状态：${workStatusDetail}。`,
        anchorMs: initialFrame?.timeMs ?? currentMs,
        initialFrame,
        recallContext,
        historyMessages: historyMessages.map((turn) => ({
          role: turn.role,
          content: turn.content,
        })),
      }

      setStatus("正在检索当前内容字幕...")
      const result = await askCourseAgent({
        ...commonParams,
        temperature: 0.2,
        signal: controller.signal,
        timeoutMs: 90_000,
        onStatus: (nextStatus) => {
          touchDailyStudyActivity(projectId, "aiQa", QA_ACTIVITY_WINDOW_MS)
          setStatus(nextStatus)
        },
        onDelta: (_chunk, accumulated) => {
          touchDailyStudyActivity(projectId, "aiQa", QA_ACTIVITY_WINDOW_MS)
          setTurns((current) =>
            current.map((turn) => (turn.id === assistantTurnId ? { ...turn, content: accumulated } : turn)),
          )
        },
      })
      if (controller.signal.aborted) return
      setTurns((current) =>
        current.map((turn) =>
          turn.id === assistantTurnId
            ? { ...turn, content: result.content.trim() || "我没有拿到可用回答。", evidence: result.evidence }
            : turn,
        ),
      )
      setStatus(null)
    } catch (requestError) {
      if (controller.signal.aborted) return
      setError(formatAssistantError(requestError))
      setStatus(null)
      setTurns((current) => current.filter((turn) => turn.id !== assistantTurnId || turn.content.trim()))
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null
      }
      setIsAsking(false)
      onAssistantStateChange?.("idle")
    }
  }

  function stopQuestion() {
    abortRef.current?.abort()
    abortRef.current = null
    setIsAsking(false)
    setStatus(null)
    onAssistantStateChange?.("idle")
  }

  async function copyLatestAnswer() {
    const latestAssistantTurn = [...turns].reverse().find((turn) => turn.role === "assistant" && turn.content.trim())
    if (!latestAssistantTurn) return
    try {
      await copyText(latestAssistantTurn.content)
      showInfoFeedback("回答已复制", "雪豹助手的最新回答已经复制到剪贴板。")
    } catch (copyError) {
      setError(formatAssistantError(copyError))
    }
  }

  const hasConversation = turns.length > 0

  return (
    <section className="flex h-full min-h-0 flex-col overflow-hidden rounded-[1.25rem] border border-border/80 bg-background/95 p-3 shadow-[0_24px_70px_-42px_rgba(31,41,55,0.55)] backdrop-blur">
      <header className="flex items-start gap-2 border-b border-border/70 pb-2.5">
        <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Sparkles className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-foreground">问问雪豹</div>
          <div className="mt-0.5 truncate text-xs text-muted-foreground">{nodeLabel}</div>
        </div>
      </header>

      <div className="mt-3 min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        {!hasConversation ? (
          <div className="rounded-[1rem] border border-dashed border-border/80 bg-muted/30 px-3 py-3 text-xs leading-5 text-muted-foreground">
            鼠标停在雪豹身上就能在这里提问。它会优先读取当前内容、播放位置和字幕，再结合工作台状态回答。
          </div>
        ) : null}
        {turns.map((turn) => (
          <article key={turn.id} className={cn("space-y-2", turn.role === "user" ? "text-right" : "text-left")}>
            <div
              className={cn(
                "inline-block max-w-[92%] rounded-[1rem] px-3 py-2 text-sm leading-6",
                turn.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "border border-border/70 bg-card text-card-foreground",
              )}
            >
              {turn.role === "assistant" ? (
                turn.content.trim() ? (
                  <MarkdownRichText text={turn.content} className="space-y-2" textClassName="text-sm leading-6" />
                ) : (
                  <span className="text-muted-foreground">正在组织回答...</span>
                )
              ) : (
                <span className="whitespace-pre-wrap">{turn.content}</span>
              )}
            </div>
            {turn.evidence?.length ? (
              <div className="flex flex-wrap gap-1.5">
                {turn.evidence.slice(0, 4).map((evidence, index) => (
                  <button
                    key={`${evidence.kind}-${evidence.startMs}-${index}`}
                    type="button"
                    className="rounded-full border border-border/80 bg-background px-2 py-1 text-[11px] font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-primary"
                    onClick={() => onOpenEvidence?.(evidence)}
                  >
                    {formatEvidenceTimeRange(evidence.startMs, evidence.endMs)} · {evidence.title}
                  </button>
                ))}
              </div>
            ) : null}
          </article>
        ))}
        <div ref={threadEndRef} />
      </div>

      {status ? <div className="mt-2 rounded-lg bg-primary/10 px-3 py-2 text-xs text-primary">{status}</div> : null}
      {error ? <div className="mt-2 rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">{error}</div> : null}
      {disabledReason ? <div className="mt-2 rounded-lg bg-muted/60 px-3 py-2 text-xs text-muted-foreground">{disabledReason}</div> : null}

      <form
        className="mt-3 space-y-2"
        onSubmit={(event) => {
          event.preventDefault()
          void submitQuestion()
        }}
      >
        <textarea
          value={composer}
          onChange={(event) => setComposer(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault()
              void submitQuestion()
            }
          }}
          disabled={!!disabledReason}
          rows={3}
          className="min-h-[74px] w-full resize-none rounded-[1rem] border border-input bg-background px-3 py-2 text-sm leading-5 outline-none transition-colors placeholder:text-muted-foreground focus:border-primary/50 focus:ring-2 focus:ring-primary/15 disabled:cursor-not-allowed disabled:opacity-60"
          placeholder="问当前内容、进度或复述点..."
        />
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="复制最新回答"
              title="复制最新回答"
              onClick={() => void copyLatestAnswer()}
              disabled={!turns.some((turn) => turn.role === "assistant" && turn.content.trim())}
            >
              <Copy className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                const prompt = composer.trim()
                if (!prompt) {
                  setError("先输入一个问题，再复制文本。")
                  return
                }
                if (!canUseCourseAgent || !instance || !sourceKind) {
                  setError("当前工作台没有可用的视频上下文。")
                  return
                }
                setStatus("正在整理可复制文本...")
                void (async () => {
                  try {
                    await copyContextText({
                      subjectId,
                      projectId,
                      instance,
                      sourceKind,
                      nodeLabel,
                      userPrompt: prompt,
                      systemPrompt: `${buildWorkbenchSystemPrompt(nodeLabel)} 当前工作台状态：${workStatusDetail}。`,
                      currentMs,
                      recallContext,
                      historyMessages: turns.map((turn) => ({ role: turn.role, content: turn.content })),
                      captureCurrentFrameForAi,
                    })
                    showInfoFeedback("文本已复制", "当前问题和上下文已经复制到剪贴板。")
                    setStatus(null)
                  } catch (copyError) {
                    setError(formatAssistantError(copyError))
                    setStatus(null)
                  }
                })()
              }}
              disabled={!composer.trim() || !canUseCourseAgent || !instance || !sourceKind}
            >
              <Copy className="h-4 w-4" />
              复制文本
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                if (!canUseCourseAgent || !instance || !sourceKind) {
                  setError("当前工作台没有可用的视频上下文。")
                  return
                }
                setStatus("正在复制当前视频帧...")
                void (async () => {
                  try {
                    const initialFrame = await copyContextImage({ captureCurrentFrameForAi })
                    if (!initialFrame?.imageDataUrl) {
                      throw new Error("当前视频帧无法复制。")
                    }
                    showInfoFeedback("图片已复制", `当前视频帧（${formatPlaybackClock(initialFrame.timeMs)}）已经复制到剪贴板。`)
                    setStatus(null)
                  } catch (copyError) {
                    setError(formatAssistantError(copyError))
                    setStatus(null)
                  }
                })()
              }}
              disabled={!canUseCourseAgent || !instance || !sourceKind}
            >
              <ImageIcon className="h-4 w-4" />
              复制图片
            </Button>
          </div>
          {isAsking ? (
            <Button type="button" variant="outline" size="sm" onClick={stopQuestion}>
              <Square className="mr-1.5 h-3.5 w-3.5" />
              停止
            </Button>
          ) : (
            <Button type="submit" size="sm" disabled={!!disabledReason || !composer.trim()}>
              <Send className="mr-1.5 h-3.5 w-3.5" />
              发送
            </Button>
          )}
        </div>
      </form>
    </section>
  )
}
