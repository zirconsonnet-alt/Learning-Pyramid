import type { Instance } from "@/ui/api/instances"
import { ApiError } from "@/ui/api/http"
import type { MaterialSourceKind } from "@/ui/api/projects"
import { askProjectLlmStream, type ProjectLlmImageInput } from "@/ui/api/system"
import type { AiChatCourseEvidence } from "@/ui/store/aiChatStore"
import { loadSubtitleDocumentForInstance, type SubtitleDocument } from "@/ui/subtitles/subtitleSupport"

type CourseAgentHistoryMessage = {
  role: "user" | "assistant"
  content: string
}

export type CourseAgentInitialFrame = {
  timeMs: number
  imageDataUrl: string
  mimeType?: string
}

export type CourseAgentRecallContext = {
  mode: "capture" | "review"
  questionText?: string
  answerText?: string
  referenceIds?: string[]
}

type AskCourseAgentParams = {
  subjectId: string
  projectId: string
  instance: Pick<Instance, "instanceId" | "materialId">
  sourceKind: MaterialSourceKind
  initialFrame?: CourseAgentInitialFrame | null
  recallContext?: CourseAgentRecallContext | null
  nodeLabel: string
  userPrompt: string
  systemPrompt?: string
  anchorMs?: number | null
  historyMessages?: CourseAgentHistoryMessage[]
  modelName?: string
  temperature?: number
  timeoutMs?: number
  signal?: AbortSignal
  onStatus?: (status: string) => void
  onDelta?: (chunk: string, accumulated: string) => void
}

export type CourseAgentContextPackage = {
  nodeLabel: string
  userPrompt: string
  prompt: string
  systemPrompt: string
  supplementalContext: string
  anchorMs: number | null
  instance: Pick<Instance, "instanceId" | "materialId">
  sourceKind: MaterialSourceKind
  recallContext: CourseAgentRecallContext | null
  recallContextText: string
  transcriptContextText: string
  initialFrame: CourseAgentInitialFrame | null
  imageInputs: ProjectLlmImageInput[]
  evidence: AiChatCourseEvidence[]
  hasTranscriptContext: boolean
}

type TranscriptWindow = {
  reason: string
  startMs: number
  endMs: number
  segments: Array<{ startMs: number; endMs: number; text: string }>
}

const DEFAULT_TOOL_TIMEOUT_MS = 90_000
const TEXT_ONLY_FRAME_NOTICE = "提示：本轮回答未使用视频帧，因为当前大模型服务不支持图片输入；已改用字幕、复述点和时间上下文回答。"

export async function askCourseAgent(params: AskCourseAgentParams): Promise<{ content: string; evidence: AiChatCourseEvidence[] }> {
  const contextPackage = await buildCourseAgentContextPackage(params)
  const scope = { subjectId: params.subjectId, scopedProjectId: params.projectId }
  const baseStatus = contextPackage.hasTranscriptContext ? "正在基于当前视频、字幕和复述点生成回答..." : "正在基于当前画面和复述点生成回答..."
  params.onStatus?.(baseStatus)
  let result: Awaited<ReturnType<typeof askProjectLlmStream>>
  let usedImageInputs = contextPackage.imageInputs.length > 0
  try {
    result = await askCourseAgentStream({
      scope,
      prompt: contextPackage.prompt,
      systemPrompt: contextPackage.systemPrompt,
      supplementalContext: contextPackage.supplementalContext,
      imageInputs: contextPackage.imageInputs,
      params,
    })
  } catch (error) {
    if (contextPackage.imageInputs.length === 0 || !isImageInputUnsupportedError(error)) throw error
    usedImageInputs = false
    params.onStatus?.("当前模型不支持视频帧，正在改用字幕和复述点文本回答...")
    result = await retryWithoutImageInputs({
      scope,
      prompt: contextPackage.prompt,
      systemPrompt: contextPackage.systemPrompt,
      supplementalContext: [
        contextPackage.supplementalContext,
        `Video frame note: ${TEXT_ONLY_FRAME_NOTICE}`,
      ].join("\n\n"),
      params,
    })
  }

  return {
    content: usedImageInputs ? result.content : `${TEXT_ONLY_FRAME_NOTICE}\n\n${result.content}`,
    evidence: contextPackage.evidence.slice(0, 8),
  }
}

export async function buildCourseAgentContextPackage(params: Pick<
  AskCourseAgentParams,
  | "subjectId"
  | "projectId"
  | "instance"
  | "sourceKind"
  | "initialFrame"
  | "recallContext"
  | "nodeLabel"
  | "userPrompt"
  | "systemPrompt"
  | "anchorMs"
  | "historyMessages"
>): Promise<CourseAgentContextPackage> {
  const scope = { subjectId: params.subjectId, scopedProjectId: params.projectId }
  const document = await loadSubtitleDocumentForInstance({
    scope,
    instance: params.instance,
    sourceKind: params.sourceKind,
  })
  const hasTranscriptContext = !!document && document.segments.length > 0
  const hasInitialFrame = !!params.initialFrame?.imageDataUrl
  const recallContextText = buildRecallContextText(params.recallContext)
  if (!hasTranscriptContext && !hasInitialFrame && !recallContextText) {
    throw new Error("当前视频上下文没有可用字幕、当前视频帧或复述点内容")
  }

  const anchorMs = params.anchorMs ?? params.initialFrame?.timeMs ?? null
  const selectedContext = hasTranscriptContext && document
    ? selectTranscriptContext({
        document,
        instanceId: params.instance.instanceId,
        userPrompt: params.userPrompt,
        nodeLabel: params.nodeLabel,
        anchorMs,
      })
    : { contextText: "", evidence: [] as AiChatCourseEvidence[] }

  const supplementalContext = buildSupplementalContext({
    nodeLabel: params.nodeLabel,
    instance: params.instance,
    sourceKind: params.sourceKind,
    anchorMs,
    recallContextText,
    transcriptContextText: selectedContext.contextText,
    initialFrame: params.initialFrame ?? null,
  })
  const systemPrompt = [buildCourseAgentSystemPrompt({ nodeLabel: params.nodeLabel, anchorMs }), params.systemPrompt?.trim()]
    .filter(Boolean)
    .join(" ")
  const prompt = buildConversationPrompt(params.historyMessages ?? [], params.userPrompt)
  const imageInputs: ProjectLlmImageInput[] = params.initialFrame?.imageDataUrl
    ? [
        {
          imageDataUrl: params.initialFrame.imageDataUrl,
          mimeType: params.initialFrame.mimeType ?? "image/jpeg",
          timeMs: params.initialFrame.timeMs,
          label: "current video frame",
        },
      ]
    : []

  return {
    nodeLabel: params.nodeLabel,
    userPrompt: params.userPrompt,
    prompt,
    systemPrompt,
    supplementalContext,
    anchorMs,
    instance: params.instance,
    sourceKind: params.sourceKind,
    recallContext: params.recallContext ?? null,
    recallContextText,
    transcriptContextText: selectedContext.contextText,
    initialFrame: params.initialFrame ?? null,
    imageInputs,
    evidence: selectedContext.evidence.slice(0, 8),
    hasTranscriptContext,
  }
}

export function buildCourseAgentContextText(contextPackage: CourseAgentContextPackage) {
  const playbackText =
    contextPackage.anchorMs === null ? "无" : `${formatTimestamp(contextPackage.anchorMs)} (${contextPackage.anchorMs} ms)`
  const frameText = contextPackage.initialFrame?.imageDataUrl
    ? `截图时间：${formatTimestamp(contextPackage.initialFrame.timeMs)} (${contextPackage.initialFrame.timeMs} ms)`
    : "本次没有截取到视频帧。"

  return [
    "任务",
    "请直接回答用户问题，不要解释这段文本。",
    "优先使用当前视频帧、复述点和字幕；如信息不足，请明确说明缺少什么。",
    "",
    "用户问题",
    contextPackage.userPrompt.trim() || "无",
    "",
    "基本信息",
    `当前节点：${contextPackage.nodeLabel}`,
    `播放位置：${playbackText}`,
    `实例 ID：${contextPackage.instance.instanceId}`,
    `材料 ID：${contextPackage.instance.materialId}`,
    `材料来源：${contextPackage.sourceKind}`,
    "",
    "当前视频帧",
    frameText,
    "",
    "复述点上下文",
    contextPackage.recallContextText || "无",
    "",
    "相关字幕",
    contextPackage.transcriptContextText || "无",
  ].join("\n")
}

function askCourseAgentStream(params: {
  scope: { subjectId: string; scopedProjectId: string }
  prompt: string
  systemPrompt: string
  supplementalContext: string
  imageInputs: ProjectLlmImageInput[]
  params: AskCourseAgentParams
}) {
  return askProjectLlmStream(
    params.scope,
    {
      prompt: params.prompt,
      systemPrompt: params.systemPrompt,
      supplementalContext: params.supplementalContext,
      imageInputs: params.imageInputs,
      modelName: params.params.modelName,
      temperature: params.params.temperature,
    },
    {
      signal: params.params.signal,
      timeoutMs: params.params.timeoutMs ?? DEFAULT_TOOL_TIMEOUT_MS,
      onDelta: params.params.onDelta,
    },
  )
}

function retryWithoutImageInputs(params: {
  scope: { subjectId: string; scopedProjectId: string }
  prompt: string
  systemPrompt: string
  supplementalContext: string
  params: AskCourseAgentParams
}) {
  return askCourseAgentStream({
    ...params,
    imageInputs: [],
  })
}

function isImageInputUnsupportedError(error: unknown) {
  if (!(error instanceof ApiError)) return false
  const message = `${error.message} ${JSON.stringify(error.details ?? "")}`.toLowerCase()
  return message.includes("image_url") && (message.includes("unknown variant") || message.includes("expected") || message.includes("deserialize"))
}

function buildConversationPrompt(messages: CourseAgentHistoryMessage[], latestUserInput: string) {
  const recentBlocks: string[] = []
  let charBudget = 4_000

  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    const block = `${message.role === "user" ? "用户" : "助手"}：\n${message.content.trim()}`
    if (!block.trim()) continue
    if (recentBlocks.length > 0 && block.length > charBudget) break
    recentBlocks.unshift(block)
    charBudget -= block.length
  }

  const sections = recentBlocks.length > 0 ? ["以下是同一个视频学习助手里的最近对话，请延续上下文回答最后一个用户问题。", ...recentBlocks] : []
  sections.push(`用户：\n${latestUserInput.trim()}`)
  return sections.join("\n\n")
}

function buildRecallContextText(context: CourseAgentRecallContext | null | undefined) {
  if (!context) return ""
  const lines: string[] = [context.mode === "review" ? "Current recall point under review:" : "Current recall point draft:"]
  const questionText = context.questionText?.trim()
  const answerText = context.answerText?.trim()
  if (questionText) lines.push(`Question: ${truncateForPrompt(questionText, 1200)}`)
  if (answerText) lines.push(`Answer: ${truncateForPrompt(answerText, 1600)}`)
  if (context.referenceIds?.length) lines.push(`References: ${context.referenceIds.join(", ")}`)
  return lines.length > 1 ? lines.join("\n") : ""
}

function buildSupplementalContext(params: {
  nodeLabel: string
  instance: Pick<Instance, "instanceId" | "materialId">
  sourceKind: MaterialSourceKind
  anchorMs: number | null
  recallContextText: string
  transcriptContextText: string
  initialFrame: CourseAgentInitialFrame | null
}) {
  const sections: string[] = [
    [
      "Video learning context:",
      `Current node: ${params.nodeLabel}`,
      `Instance ID: ${params.instance.instanceId}`,
      `Material ID: ${params.instance.materialId}`,
      `Material source kind: ${params.sourceKind}`,
      params.anchorMs === null ? "Playback anchor: none" : `Playback anchor: ${formatTimestamp(params.anchorMs)} (${params.anchorMs} ms)`,
    ].join("\n"),
  ]

  if (params.recallContextText) sections.push(params.recallContextText)
  if (params.transcriptContextText) sections.push(params.transcriptContextText)
  if (params.initialFrame) {
    sections.push(`Current video frame is attached as an image input at ${formatTimestamp(params.initialFrame.timeMs)} (${params.initialFrame.timeMs} ms).`)
  }
  return sections.join("\n\n")
}

function buildCourseAgentSystemPrompt(params: { nodeLabel: string; anchorMs: number | null }) {
  const anchorHint =
    params.anchorMs === null ? "当前没有预设锚点。" : `当前上下文锚点时间约为 ${formatTimestamp(params.anchorMs)}。`
  return [
    "你是视频播放器里的同一个学习助手，桌宠和全屏视频助手都会使用这套能力。",
    `当前节点标题：${params.nodeLabel}。`,
    anchorHint,
    "你会收到当前复述点内容、当前播放位置、当前视频帧和字幕片段中可用的部分。",
    "请优先依据这些上下文回答，不要要求用户重复粘贴已经提供的题面、答案、画面或字幕。",
    "如果证据不足，请明确指出还缺少哪一段，不要编造。",
    "回答请直接、可执行；需要引用视频内容时自然写出时间片段，例如 32:50-34:10。",
    "请始终使用简体中文回答。",
  ].join(" ")
}

function selectTranscriptContext(params: {
  document: SubtitleDocument
  instanceId: string
  userPrompt: string
  nodeLabel: string
  anchorMs: number | null
}): { contextText: string; evidence: AiChatCourseEvidence[] } {
  const windows: TranscriptWindow[] = []
  const referencedTimeMs = extractReferencedTimeMs(params.userPrompt)

  if (referencedTimeMs !== null) {
    appendTranscriptWindow(windows, params.document, {
      reason: `用户提到的时间点 ${formatTimestamp(referencedTimeMs)}`,
      startMs: Math.max(0, referencedTimeMs - 45_000),
      endMs: referencedTimeMs + 45_000,
    })
  } else if (params.anchorMs !== null) {
    appendTranscriptWindow(windows, params.document, {
      reason: `当前锚点附近 ${formatTimestamp(params.anchorMs)}`,
      startMs: Math.max(0, params.anchorMs - 60_000),
      endMs: params.anchorMs + 45_000,
    })
  }

  for (const query of buildSearchQueries(params.userPrompt, params.nodeLabel)) {
    const hits = searchTranscript(params.document, { query, topK: 3 }).hits
    for (const hit of hits) {
      appendTranscriptWindow(windows, params.document, {
        reason: `相关字幕命中：${normalizePreviewText(query, 28)}`,
        startMs: Math.max(0, hit.startMs - 20_000),
        endMs: hit.endMs + 20_000,
      })
      if (windows.length >= 3) break
    }
    if (windows.length >= 3) break
  }

  if (windows.length === 0) {
    const defaultStartMs = Math.max(0, (params.anchorMs ?? 0) - 30_000)
    appendTranscriptWindow(windows, params.document, {
      reason: params.anchorMs === null ? "默认取视频开头附近字幕" : `默认取锚点附近字幕 ${formatTimestamp(params.anchorMs)}`,
      startMs: defaultStartMs,
      endMs: defaultStartMs + 60_000,
    })
  }

  const evidence: AiChatCourseEvidence[] = []
  const sections = windows.map((window) => {
    appendCourseEvidence(evidence, [
      {
        kind: "transcript",
        instanceId: params.instanceId,
        startMs: window.startMs,
        endMs: window.endMs,
        title: `字幕片段 ${formatTimestamp(window.startMs)}-${formatTimestamp(window.endMs)}`,
        preview: normalizePreviewText(window.segments.map((segment) => segment.text).join(" "), 180),
      },
    ])
    return formatTranscriptWindowForPrompt(window)
  })

  return {
    contextText: sections.join("\n\n").slice(0, 6_500).trim(),
    evidence,
  }
}

function appendTranscriptWindow(
  target: TranscriptWindow[],
  document: SubtitleDocument,
  params: { reason: string; startMs: number; endMs: number },
) {
  const range = getTranscriptRange(document, {
    startMs: params.startMs,
    endMs: params.endMs,
    maxSegments: 80,
  })
  if (range.length === 0) return
  const startMs = range[0]?.startMs ?? params.startMs
  const endMs = range.at(-1)?.endMs ?? params.endMs
  if (target.some((window) => windowsOverlap(window, { startMs, endMs }))) return
  target.push({
    reason: params.reason,
    startMs,
    endMs,
    segments: range,
  })
}

function getTranscriptRange(document: SubtitleDocument, args: { startMs: number; endMs: number; maxSegments: number }) {
  const startMs = Math.max(0, Math.min(args.startMs, args.endMs))
  const endMs = Math.max(startMs, args.endMs)
  return document.segments
    .filter((segment) => segment.endMs >= startMs && segment.startMs <= endMs)
    .slice(0, args.maxSegments)
    .map((segment) => ({ startMs: segment.startMs, endMs: segment.endMs, text: segment.text }))
}

function searchTranscript(document: SubtitleDocument, args: { query: string; topK: number }) {
  const normalizedQuery = normalizeSearchText(args.query)
  if (!normalizedQuery) return { hits: [] as Array<{ startMs: number; endMs: number; text: string; score: number }> }
  const hits = document.segments
    .map((segment) => ({
      startMs: segment.startMs,
      endMs: segment.endMs,
      text: segment.text,
      score: scoreTranscriptSegment(segment.text, normalizedQuery),
    }))
    .filter((hit) => hit.score > 0)
    .sort((left, right) => right.score - left.score || left.startMs - right.startMs)
    .slice(0, Math.max(1, Math.min(args.topK, 10)))
  return { hits }
}

function scoreTranscriptSegment(text: string, normalizedQuery: string) {
  const normalizedText = normalizeSearchText(text)
  if (!normalizedText) return 0
  if (normalizedText.includes(normalizedQuery)) return 10 + normalizedQuery.length / 10

  let score = 0
  for (const token of normalizedQuery.match(/[\u4e00-\u9fff]{2,}|[a-z0-9]+/gi) ?? []) {
    if (normalizedText.includes(token.toLowerCase())) score += Math.max(1, token.length / 4)
  }
  return score
}

function buildSearchQueries(userPrompt: string, nodeLabel: string) {
  const queries = [userPrompt.trim(), stripExplicitTimeExpressions(userPrompt), nodeLabel.trim()]
  return queries
    .map((query) => query.replace(/\s+/g, " ").trim())
    .filter((query) => normalizeSearchText(query).length >= 2)
    .filter((query, index, items) => items.indexOf(query) === index)
    .slice(0, 3)
}

function formatTranscriptWindowForPrompt(window: TranscriptWindow) {
  return [
    `${window.reason}（${formatTimestamp(window.startMs)}-${formatTimestamp(window.endMs)}）`,
    ...window.segments.map((segment) => `[${formatTimestamp(segment.startMs)}-${formatTimestamp(segment.endMs)}] ${segment.text}`),
  ].join("\n")
}

function appendCourseEvidence(target: AiChatCourseEvidence[], items: AiChatCourseEvidence[]) {
  for (const item of items) {
    const key = `${item.kind}:${item.instanceId}:${item.startMs}:${item.endMs}`
    if (target.some((current) => `${current.kind}:${current.instanceId}:${current.startMs}:${current.endMs}` === key)) continue
    target.push(item)
  }
}

function normalizeSearchText(text: string) {
  return text.replace(/\s+/g, "").trim().toLowerCase()
}

function normalizePreviewText(text: string, maxChars = 140) {
  const normalized = text.replace(/\s+/g, " ").trim()
  if (!normalized) return ""
  if (normalized.length <= maxChars) return normalized
  return `${normalized.slice(0, Math.max(1, maxChars - 1)).trimEnd()}...`
}

function truncateForPrompt(text: string, maxChars: number) {
  const normalized = text.replace(/\s+/g, " ").trim()
  if (normalized.length <= maxChars) return normalized
  return `${normalized.slice(0, Math.max(1, maxChars - 3)).trimEnd()}...`
}

function windowsOverlap(left: { startMs: number; endMs: number }, right: { startMs: number; endMs: number }) {
  return Math.max(left.startMs, right.startMs) <= Math.min(left.endMs, right.endMs) + 10_000
}

function formatTimestamp(ms: number) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
  return `${minutes}:${String(seconds).padStart(2, "0")}`
}

function extractReferencedTimeMs(text: string) {
  const normalized = text.replace(/\s+/g, "")
  const hmsMatch = normalized.match(/(\d{1,2}):(\d{2})(?::(\d{2}))?/)
  if (hmsMatch) {
    if (hmsMatch[3] !== undefined) {
      const hours = Number(hmsMatch[1])
      const minutes = Number(hmsMatch[2])
      const seconds = Number(hmsMatch[3])
      if ([hours, minutes, seconds].every(Number.isFinite)) return (hours * 3600 + minutes * 60 + seconds) * 1000
    }
    const minutes = Number(hmsMatch[1])
    const seconds = Number(hmsMatch[2])
    if ([minutes, seconds].every(Number.isFinite)) return (minutes * 60 + seconds) * 1000
  }

  const zhMatch = normalized.match(/(?:(\d{1,2})小时)?(\d{1,3})分(?:钟)?(?:(\d{1,2})秒)?/)
  if (zhMatch) {
    const hours = Number(zhMatch[1] ?? 0)
    const minutes = Number(zhMatch[2] ?? 0)
    const seconds = Number(zhMatch[3] ?? 0)
    if ([hours, minutes, seconds].every(Number.isFinite)) return (hours * 3600 + minutes * 60 + seconds) * 1000
  }

  const minuteOnlyMatch = normalized.match(/(?:^|[^\d])(\d{1,3})(?:分钟|分)(?!钟|秒)/)
  if (minuteOnlyMatch) {
    const minutes = Number(minuteOnlyMatch[1])
    if (Number.isFinite(minutes)) return minutes * 60 * 1000
  }
  return null
}

function stripExplicitTimeExpressions(text: string) {
  return text
    .replace(/\b\d{1,2}:\d{2}(?::\d{2})?\b/g, " ")
    .replace(/\d{1,2}小时\d{1,3}分(?:钟)?\d{0,2}秒?/g, " ")
    .replace(/\d{1,3}分(?:钟)?\d{0,2}秒?/g, " ")
    .replace(/\d{1,3}(?:分钟|分)/g, " ")
}
