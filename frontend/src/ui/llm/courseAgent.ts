import type { Instance } from "@/ui/api/instances"
import type { MaterialSourceKind } from "@/ui/api/projects"
import { ApiError, apiUrl } from "@/ui/api/http"
import { projectApiPath } from "@/ui/api/projectScope"
import { askProjectLlmChatCompletion, type RawChatCompletionResponse } from "@/ui/api/system"
import { resolveProjectFile } from "@/ui/localMedia/projectDirectory"
import type { AiChatCourseEvidence } from "@/ui/store/aiChatStore"
import { loadSubtitleDocumentForInstance, type SubtitleDocument } from "@/ui/subtitles/subtitleSupport"

type CourseAgentHistoryMessage = {
  role: "user" | "assistant"
  content: string
}

type CourseAgentInitialFrame = {
  timeMs: number
  imageDataUrl: string
}

type AskCourseAgentParams = {
  subjectId: string
  projectId: string
  instance: Pick<Instance, "instanceId" | "materialId">
  sourceKind: MaterialSourceKind
  canCaptureVideoFrame?: boolean
  preferHighDetailFrame?: boolean
  initialFrame?: CourseAgentInitialFrame | null
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
}

type TranscriptToolResult = {
  segments: Array<{ startMs: number; endMs: number; text: string }>
  hasMoreBefore: boolean
  hasMoreAfter: boolean
}

type SearchToolResult = {
  hits: Array<{ startMs: number; endMs: number; text: string; score: number }>
}

type VideoFrameToolResult = {
  timeMs: number
  available: boolean
  imageDataUrl?: string
  mimeType?: string
  note?: string
}

type SlideTextToolResult = {
  timeMs: number
  available: boolean
  source: "vision_ocr"
  texts: string[]
  note?: string
}

type ChatCompletionMessage = {
  role?: unknown
  content?: unknown
  tool_calls?: unknown
}

type ChatCompletionToolCall = {
  id: string
  function: {
    name: string
    arguments: string
  }
}

type CapabilityErrorKind = "tool" | "vision" | "response_format" | null

type TranscriptWindow = {
  reason: string
  startMs: number
  endMs: number
  segments: TranscriptToolResult["segments"]
}

const MAX_TOOL_ROUNDS = 4
const DEFAULT_TOOL_TIMEOUT_MS = 90_000
const slideTextCache = new Map<string, SlideTextToolResult>()
const toolSupportCache = new Map<string, boolean>()
const visionSupportCache = new Map<string, boolean>()

export async function askCourseAgent(params: AskCourseAgentParams): Promise<{ content: string; evidence: AiChatCourseEvidence[] }> {
  const scope = { subjectId: params.subjectId, scopedProjectId: params.projectId }
  const document = await loadSubtitleDocumentForInstance({
    scope,
    instance: params.instance,
    sourceKind: params.sourceKind,
  })
  const hasTranscriptContext = !!document && document.segments.length > 0
  const hasInitialFrame = !!params.initialFrame?.imageDataUrl
  if (!hasTranscriptContext && !hasInitialFrame) {
    throw new Error("当前视频上下文没有可用字幕，也未能附带当前视频帧")
  }

  const capabilityCacheKey = buildCapabilityCacheKey(params)
  const toolCallingSupported = toolSupportCache.get(capabilityCacheKey) !== false
  const visionSupported = visionSupportCache.get(capabilityCacheKey) !== false
  const effectiveAnchorMs = params.anchorMs ?? params.initialFrame?.timeMs ?? null

  if (!toolCallingSupported) {
    params.onStatus?.("当前模型不支持工具调用，已切换到兼容模式...")
    return await answerWithCompatibilityMode({
      params,
      document,
      hasTranscriptContext,
      anchorMs: effectiveAnchorMs,
      includeVision: visionSupported,
    })
  }

  const messages: Array<Record<string, unknown>> = []
  const baseSystemPrompt = buildCourseAgentSystemPrompt({
    nodeLabel: params.nodeLabel,
    anchorMs: effectiveAnchorMs,
    hasAnchorWindowTool: hasTranscriptContext && params.anchorMs !== null && params.anchorMs !== undefined,
    hasTranscriptTool: hasTranscriptContext,
    hasInitialFrame,
  })
  messages.push({ role: "system", content: baseSystemPrompt })
  if (params.systemPrompt?.trim()) {
    messages.push({ role: "system", content: params.systemPrompt.trim() })
  }
  for (const message of params.historyMessages ?? []) {
    if (!message.content.trim()) continue
    messages.push({ role: message.role, content: message.content.trim() })
  }
  messages.push(
    buildCourseUserMessage({
      userPrompt: params.userPrompt,
      initialFrame: visionSupported ? params.initialFrame ?? null : null,
      preferHighDetailFrame: !!params.preferHighDetailFrame,
    }),
  )

  const tools = buildCourseAgentTools({
    includeTranscriptTools: hasTranscriptContext,
    includeAnchorTool: hasTranscriptContext && params.anchorMs !== null && params.anchorMs !== undefined,
    includeFrameTool: !!params.canCaptureVideoFrame && visionSupported,
    includeSlideTextTool: !!params.canCaptureVideoFrame && visionSupported,
  })
  const evidence: AiChatCourseEvidence[] = []

  try {
    for (let round = 0; round < MAX_TOOL_ROUNDS; round += 1) {
      params.onStatus?.(round === 0 ? "正在检索相关字幕..." : "正在补充上下文...")

      const response = await askProjectLlmChatCompletion(
        scope,
        {
          messages,
          tools,
          toolChoice: "auto",
          parallelToolCalls: false,
          modelName: params.modelName,
          temperature: params.temperature,
        },
        {
          signal: params.signal,
          timeoutMs: params.timeoutMs ?? DEFAULT_TOOL_TIMEOUT_MS,
        },
      )

      const assistantMessage = extractAssistantMessage(response)
      if (!assistantMessage) {
        throw new Error("LLM 服务未返回可用消息")
      }

      const toolCalls = extractToolCalls(assistantMessage)
      const assistantContent = extractMessageText(assistantMessage)
      messages.push(buildAssistantReplayMessage(assistantMessage))

      if (toolCalls.length === 0) {
        const normalized = assistantContent.trim()
        if (!normalized) {
          throw new Error("LLM 服务返回了空回答")
        }
        return { content: normalized, evidence: evidence.slice(0, 8) }
      }

      for (const toolCall of toolCalls) {
        const output = await executeToolCall({
          toolCall,
          params,
          document,
          anchorMs: effectiveAnchorMs,
        })
        appendCourseEvidence(evidence, buildEvidenceFromToolResult(params.instance.instanceId, toolCall.function.name, output))
        messages.push({
          role: "tool",
          tool_call_id: toolCall.id,
          content: JSON.stringify(stripLargeMediaPayload(output)),
        })
        if (isVideoFrameResult(output) && output.available && output.imageDataUrl) {
          messages.push(buildFrameInspectionMessage({
            toolName: toolCall.function.name,
            timeMs: output.timeMs,
            imageDataUrl: output.imageDataUrl,
            preferHighDetail: !!params.preferHighDetailFrame,
          }))
        }
      }
    }
  } catch (error) {
    if (params.signal?.aborted || isAbortLikeError(error)) throw error
    const capabilityError = classifyCapabilityError(error)
    if (capabilityError === "tool") {
      toolSupportCache.set(capabilityCacheKey, false)
      params.onStatus?.("当前模型不支持工具调用，已切换到兼容模式...")
      return await answerWithCompatibilityMode({
        params,
        document,
        hasTranscriptContext,
        anchorMs: effectiveAnchorMs,
        includeVision: visionSupported,
      })
    }
    if (capabilityError === "vision") {
      visionSupportCache.set(capabilityCacheKey, false)
      if (!hasTranscriptContext) {
        throw new Error("当前模型不支持图片输入，而当前视频也没有可用字幕，暂时无法回答这类视频问题。")
      }
      params.onStatus?.("当前模型不支持图片输入，已改为仅依据字幕回答...")
      return await answerWithCompatibilityMode({
        params,
        document,
        hasTranscriptContext,
        anchorMs: effectiveAnchorMs,
        includeVision: false,
      })
    }
    throw error
  }

  throw new Error("视频问答已达到工具调用上限，请缩小问题范围后重试")
}

async function answerWithCompatibilityMode(params: {
  params: AskCourseAgentParams
  document: SubtitleDocument | null
  hasTranscriptContext: boolean
  anchorMs: number | null
  includeVision: boolean
}): Promise<{ content: string; evidence: AiChatCourseEvidence[] }> {
  const selectedContext = params.hasTranscriptContext && params.document
    ? selectCompatibilityTranscriptContext({
        document: params.document,
        instanceId: params.params.instance.instanceId,
        userPrompt: params.params.userPrompt,
        nodeLabel: params.params.nodeLabel,
        anchorMs: params.anchorMs,
      })
    : { contextText: "", evidence: [] as AiChatCourseEvidence[], primaryTimeMs: params.anchorMs }

  const supplementalSections: string[] = []
  if (selectedContext.contextText) {
    supplementalSections.push(selectedContext.contextText)
  }

  if (params.includeVision && params.params.canCaptureVideoFrame && looksLikeSlideTextQuestion(params.params.userPrompt)) {
    params.params.onStatus?.("正在补充页面文字...")
    const slideText = await getSlideTextAround(params.params, {
      timeMs: selectedContext.primaryTimeMs ?? params.anchorMs ?? 0,
    })
    if (slideText.available && slideText.texts.length > 0) {
      appendCourseEvidence(
        selectedContext.evidence,
        buildEvidenceFromToolResult(params.params.instance.instanceId, "get_slide_text_around", slideText),
      )
      supplementalSections.push(
        [
          `页面文字（${formatTimestamp(slideText.timeMs)}）`,
          ...slideText.texts.slice(0, 8).map((line) => `- ${line}`),
        ].join("\n"),
      )
    }
  }

  const messages: Array<Record<string, unknown>> = [
    {
      role: "system",
      content: buildCourseCompatibilitySystemPrompt({
        nodeLabel: params.params.nodeLabel,
        anchorMs: params.anchorMs,
      }),
    },
  ]
  if (params.params.systemPrompt?.trim()) {
    messages.push({ role: "system", content: params.params.systemPrompt.trim() })
  }
  for (const message of params.params.historyMessages ?? []) {
    if (!message.content.trim()) continue
    messages.push({ role: message.role, content: message.content.trim() })
  }
  messages.push({
    role: "user",
    content: buildCompatibilityUserContent({
      userPrompt: params.params.userPrompt,
      contextText: supplementalSections.join("\n\n").trim(),
      initialFrame: params.includeVision ? params.params.initialFrame ?? null : null,
      preferHighDetailFrame: !!params.params.preferHighDetailFrame,
    }),
  })

  params.params.onStatus?.(params.hasTranscriptContext ? "正在基于相关字幕生成回答..." : "正在基于当前画面生成回答...")
  const response = await askProjectLlmChatCompletion(
    { subjectId: params.params.subjectId, scopedProjectId: params.params.projectId },
    {
      messages,
      modelName: params.params.modelName,
      temperature: params.params.temperature,
    },
    {
      signal: params.params.signal,
      timeoutMs: params.params.timeoutMs ?? DEFAULT_TOOL_TIMEOUT_MS,
    },
  )

  const assistantMessage = extractAssistantMessage(response)
  const content = extractMessageText(assistantMessage ?? {}).trim()
  if (!content) {
    throw new Error("LLM 服务返回了空回答")
  }
  return {
    content,
    evidence: selectedContext.evidence.slice(0, 8),
  }
}

function selectCompatibilityTranscriptContext(params: {
  document: SubtitleDocument
  instanceId: string
  userPrompt: string
  nodeLabel: string
  anchorMs: number | null
}): { contextText: string; evidence: AiChatCourseEvidence[]; primaryTimeMs: number | null } {
  const windows: TranscriptWindow[] = []
  const referencedTimeMs = extractReferencedTimeMs(params.userPrompt)
  const primaryTimeMs = referencedTimeMs ?? params.anchorMs

  if (referencedTimeMs !== null) {
    appendTranscriptWindow(windows, params.document, {
      reason: `用户提到的时间点 ${formatTimestamp(referencedTimeMs)}`,
      startMs: Math.max(0, referencedTimeMs - 45_000),
      endMs: referencedTimeMs + 45_000,
    })
  } else if (params.anchorMs !== null) {
    appendTranscriptWindow(windows, params.document, {
      reason: `当前锚点附近 ${formatTimestamp(params.anchorMs)}`,
      startMs: Math.max(0, params.anchorMs - 45_000),
      endMs: params.anchorMs + 45_000,
    })
  }

  for (const query of buildCompatibilitySearchQueries(params.userPrompt, params.nodeLabel)) {
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
    const fallbackStartMs = Math.max(0, (params.anchorMs ?? 0) - 30_000)
    appendTranscriptWindow(windows, params.document, {
      reason: params.anchorMs === null ? "默认取视频开头附近字幕" : `默认取锚点附近字幕 ${formatTimestamp(params.anchorMs)}`,
      startMs: fallbackStartMs,
      endMs: fallbackStartMs + 60_000,
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
    primaryTimeMs,
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
  if (range.segments.length === 0) return
  const startMs = range.segments[0]?.startMs ?? params.startMs
  const endMs = range.segments.at(-1)?.endMs ?? params.endMs
  if (target.some((window) => windowsOverlap(window, { startMs, endMs }))) return
  target.push({
    reason: params.reason,
    startMs,
    endMs,
    segments: range.segments,
  })
}

function formatTranscriptWindowForPrompt(window: TranscriptWindow) {
  return [
    `${window.reason}（${formatTimestamp(window.startMs)}-${formatTimestamp(window.endMs)}）`,
    ...window.segments.map((segment) => `[${formatTimestamp(segment.startMs)}-${formatTimestamp(segment.endMs)}] ${segment.text}`),
  ].join("\n")
}

function buildCompatibilitySearchQueries(userPrompt: string, nodeLabel: string) {
  const queries = [userPrompt.trim(), stripExplicitTimeExpressions(userPrompt), nodeLabel.trim()]
  return queries
    .map((query) => query.replace(/\s+/g, " ").trim())
    .filter((query) => normalizeSearchText(query).length >= 2)
    .filter((query, index, items) => items.indexOf(query) === index)
    .slice(0, 3)
}

function buildCourseCompatibilitySystemPrompt(params: { nodeLabel: string; anchorMs: number | null }) {
  const anchorHint =
    params.anchorMs === null ? "当前没有预设锚点。" : `当前上下文锚点时间约为 ${formatTimestamp(params.anchorMs)}。`
  return [
    "你是视频播放器里的学习助手，当前对话已绑定到同一个视频实例。",
    `当前节点标题：${params.nodeLabel}。`,
    anchorHint,
    "你会收到按需检索出的少量视频证据，请优先依据这些证据回答。",
    "如果证据不足，请明确指出还缺少哪一段，不要编造。",
    "最终回答请直接给结论，并在正文中自然引用时间片段，例如 32:50-34:10。",
    "请始终使用简体中文回答。",
  ].join(" ")
}

function buildCompatibilityUserContent(params: {
  userPrompt: string
  contextText: string
  initialFrame: CourseAgentInitialFrame | null
  preferHighDetailFrame: boolean
}) {
  const sections = [`用户问题：\n${params.userPrompt.trim()}`]
  if (params.contextText.trim()) {
    sections.push(`已检索到的视频证据：\n${params.contextText.trim()}`)
  }
  if (params.initialFrame) {
    sections.push(`已附带当前播放位置的视频帧（${formatTimestamp(params.initialFrame.timeMs)}）。`)
  }
  sections.push("请优先依据这些证据回答；如果证据仍不足，请明确说明还需要哪一段内容。")
  const promptText = sections.join("\n\n")
  if (!params.initialFrame) return promptText
  return [
    {
      type: "text",
      text: promptText,
    },
    {
      type: "image_url",
      image_url: {
        url: params.initialFrame.imageDataUrl,
        detail: params.preferHighDetailFrame ? "high" : "low",
      },
    },
  ]
}

function buildCourseAgentSystemPrompt(params: {
  nodeLabel: string
  anchorMs: number | null
  hasAnchorWindowTool: boolean
  hasTranscriptTool: boolean
  hasInitialFrame: boolean
}) {
  const anchorHint =
    params.anchorMs === null
      ? "当前没有预设锚点。"
      : `当前上下文锚点时间约为 ${formatTimestamp(params.anchorMs)}。`
  const anchorToolHint = !params.hasTranscriptTool
    ? "当前没有可用字幕工具，只能结合当前画面和按需抽帧来回答；如果证据不足请直接说明。"
    : params.hasAnchorWindowTool
      ? "如果问题明显围绕当前复述点或当前播放位置展开，优先调用 get_anchor_transcript_window；如需获取“当前到一段时间前”的字幕，可把 afterMs 设为 0。"
      : "如果用户提到明确时间点，优先先取该时间点前后 30 到 90 秒字幕。"
  const frameHint = params.hasInitialFrame ? "当前这一轮用户问题已经附带当前播放位置的视频帧。" : "当前这一轮未预先附带视频帧。"

  return [
    "你是视频播放器里的学习助手，当前对话已绑定到同一个视频实例。",
    `当前节点标题：${params.nodeLabel}。`,
    anchorHint,
    frameHint,
    params.hasTranscriptTool ? "你可以通过工具按需检索字幕，不要要求用户重复粘贴视频内容。" : "当前没有字幕可检索，不要假装引用不存在的字幕。",
    params.hasTranscriptTool ? "优先使用最少的上下文回答问题，不要一次性读取很长的字幕。" : "优先依据当前帧、OCR 结果和后续抽帧结果回答问题。",
    anchorToolHint,
    "如果当前视频是 PPT/讲义页面，且你主要需要页面文字、标题、要点或公式文本，优先调用 get_slide_text_around。",
    "如果你需要的是布局、图示、箭头、标注、图表关系，再调用 get_video_frame。",
    "如果局部字幕存在承接词、代词、省略或定义不完整，再向前或向后扩展 30 到 60 秒。",
    "如果用户的问题本质上是视频整体总结，但工具证据不足，请明确说明范围不足，不要编造。",
    "最多进行 4 轮工具调用。",
    "最终回答请直接给结论，并在正文中自然引用时间片段，例如 32:50-34:10。",
    "请始终使用简体中文回答。",
  ].join(" ")
}

function buildCourseUserMessage(params: {
  userPrompt: string
  initialFrame: CourseAgentInitialFrame | null
  preferHighDetailFrame: boolean
}) {
  if (!params.initialFrame) {
    return {
      role: "user",
      content: params.userPrompt.trim(),
    }
  }
  return {
    role: "user",
    content: [
      {
        type: "text",
        text: [
          params.userPrompt.trim(),
          `补充说明：当前播放位置的视频帧（${formatTimestamp(params.initialFrame.timeMs)}）已一并附上，可直接结合画面回答。`,
        ].join("\n\n"),
      },
      {
        type: "image_url",
        image_url: {
          url: params.initialFrame.imageDataUrl,
          detail: params.preferHighDetailFrame ? "high" : "low",
        },
      },
    ],
  }
}

function buildCourseAgentTools(params: {
  includeTranscriptTools: boolean
  includeAnchorTool: boolean
  includeFrameTool: boolean
  includeSlideTextTool: boolean
}) {
  const tools: Array<Record<string, unknown>> = []

  if (params.includeTranscriptTools) {
    tools.push(
      {
        type: "function",
        function: {
          name: "get_transcript_range",
          description:
            "获取当前视频实例指定时间范围内的字幕。优先使用 30 到 90 秒的小窗口；仅在证据不足时再扩大范围。",
          parameters: {
            type: "object",
            properties: {
              startMs: {
                type: "integer",
                description: "起始时间，毫秒。",
              },
              endMs: {
                type: "integer",
                description: "结束时间，毫秒。建议单次不超过 180000 毫秒。",
              },
              maxSegments: {
                type: "integer",
                description: "可选，限制返回的字幕段数量。",
              },
            },
            required: ["startMs", "endMs"],
            additionalProperties: false,
          },
        },
      },
      {
        type: "function",
        function: {
          name: "search_transcript",
          description: "按语义和关键词搜索当前视频实例的字幕，适合没有明确时间锚点的概念性问题。",
          parameters: {
            type: "object",
            properties: {
              query: {
                type: "string",
                description: "搜索查询。",
              },
              topK: {
                type: "integer",
                description: "可选，返回命中数量。",
              },
            },
            required: ["query"],
            additionalProperties: false,
          },
        },
      },
    )
  }

  if (params.includeAnchorTool) {
    tools.push({
      type: "function",
      function: {
        name: "get_anchor_transcript_window",
        description: "围绕当前上下文锚点时间获取字幕，适合用户问“这一段”“这个复述点”时使用。把 afterMs 设为 0 可获取“当前到一段时间前”的字幕。",
        parameters: {
          type: "object",
          properties: {
            beforeMs: {
              type: "integer",
              description: "锚点之前回看的毫秒数，默认 45000。",
            },
            afterMs: {
              type: "integer",
              description: "锚点之后查看的毫秒数，默认 45000。",
            },
            maxSegments: {
              type: "integer",
              description: "可选，限制返回的字幕段数量。",
            },
          },
          additionalProperties: false,
        },
      },
    })
  }

  if (params.includeSlideTextTool) {
    tools.push({
      type: "function",
      function: {
        name: "get_slide_text_around",
        description: "获取某个时间点附近 PPT/讲义页的可见文字。适合标题、要点、列表、定义、公式文本等文字性信息。",
        parameters: {
          type: "object",
          properties: {
            timeMs: {
              type: "integer",
              description: "目标时间，毫秒。",
            },
          },
          required: ["timeMs"],
          additionalProperties: false,
        },
      },
    })
  }

  if (params.includeFrameTool) {
    tools.push({
      type: "function",
      function: {
        name: "get_video_frame",
        description: "获取指定时间点的视频帧。当字幕提到图、表、公式、这一页、箭头、标注或画面关系时再使用。",
        parameters: {
          type: "object",
          properties: {
            timeMs: {
              type: "integer",
              description: "目标时间，毫秒。",
            },
          },
          required: ["timeMs"],
          additionalProperties: false,
        },
      },
    })
  }

  return tools
}

async function executeToolCall(params: {
  toolCall: ChatCompletionToolCall
  params: AskCourseAgentParams
  document: SubtitleDocument | null
  anchorMs: number | null
}): Promise<TranscriptToolResult | SearchToolResult | VideoFrameToolResult | SlideTextToolResult> {
  const { toolCall, document, anchorMs } = params
  const rawArgs = safeJsonParse(toolCall.function.arguments)
  const args = rawArgs && typeof rawArgs === "object" ? (rawArgs as Record<string, unknown>) : {}

  switch (toolCall.function.name) {
    case "get_transcript_range":
      if (!document) return { segments: [], hasMoreBefore: false, hasMoreAfter: false }
      return getTranscriptRange(document, {
        startMs: toInt(args.startMs, 0),
        endMs: toInt(args.endMs, 0),
        maxSegments: toOptionalInt(args.maxSegments),
      })
    case "search_transcript":
      if (!document) return { hits: [] }
      return searchTranscript(document, {
        query: typeof args.query === "string" ? args.query : "",
        topK: toOptionalInt(args.topK),
      })
    case "get_anchor_transcript_window": {
      if (!document || anchorMs === null) {
        return { segments: [], hasMoreBefore: false, hasMoreAfter: false }
      }
      const beforeMs = clampInt(toOptionalInt(args.beforeMs) ?? 45_000, 5_000, 180_000)
      const afterMs = clampInt(toOptionalInt(args.afterMs) ?? 45_000, 5_000, 180_000)
      return getTranscriptRange(document, {
        startMs: Math.max(0, anchorMs - beforeMs),
        endMs: anchorMs + afterMs,
        maxSegments: toOptionalInt(args.maxSegments),
      })
    }
    case "get_slide_text_around":
      return await getSlideTextAround(params.params, {
        timeMs: toInt(args.timeMs, anchorMs ?? 0),
      })
    case "get_video_frame":
      return await getVideoFrame(params.params, {
        timeMs: toInt(args.timeMs, anchorMs ?? 0),
      })
    default:
      throw new Error(`未知工具：${toolCall.function.name}`)
  }
}

async function getVideoFrame(
  params: AskCourseAgentParams,
  args: { timeMs: number },
): Promise<VideoFrameToolResult> {
  if (!params.canCaptureVideoFrame) {
    return {
      timeMs: Math.max(0, args.timeMs),
      available: false,
      note: "当前环境无法读取视频帧，请仅依据字幕回答。",
    }
  }

  try {
    const source = await resolveVideoSource(params)
    if (!source) {
      return {
        timeMs: Math.max(0, args.timeMs),
        available: false,
        note: "当前环境无法访问视频文件，请仅依据字幕回答。",
      }
    }

    const frame = await captureFrameAsDataUrl({
      src: source.src,
      revokeSrc: source.revokeSrc,
      timeMs: Math.max(0, args.timeMs),
    })
    return {
      timeMs: frame.timeMs,
      available: true,
      imageDataUrl: frame.imageDataUrl,
      mimeType: "image/jpeg",
    }
  } catch (error) {
    return {
      timeMs: Math.max(0, args.timeMs),
      available: false,
      note: error instanceof Error ? error.message : "视频抽帧失败",
    }
  }
}

async function getSlideTextAround(
  params: AskCourseAgentParams,
  args: { timeMs: number },
): Promise<SlideTextToolResult> {
  const timeMs = Math.max(0, args.timeMs)
  const cacheKey = [params.projectId, params.instance.instanceId, params.modelName ?? "", timeMs].join(":")
  const cached = slideTextCache.get(cacheKey)
  if (cached) return cached

  if (!params.canCaptureVideoFrame) {
    return {
      timeMs,
      available: false,
      source: "vision_ocr",
      texts: [],
      note: "当前环境无法读取视频帧，不能提取页面文字。",
    }
  }

  try {
    const source = await resolveVideoSource(params)
    if (!source) {
      return {
        timeMs,
        available: false,
        source: "vision_ocr",
        texts: [],
        note: "当前环境无法访问视频文件，不能提取页面文字。",
      }
    }

    const frame = await captureFrameAsDataUrl({
      src: source.src,
      revokeSrc: source.revokeSrc,
      timeMs,
    })
    const result = await extractSlideTextFromImage(params, {
      timeMs: frame.timeMs,
      imageDataUrl: frame.imageDataUrl,
    })
    slideTextCache.set(cacheKey, result)
    return result
  } catch (error) {
    if (classifyCapabilityError(error) === "vision") {
      visionSupportCache.set(buildCapabilityCacheKey(params), false)
    }
    return {
      timeMs,
      available: false,
      source: "vision_ocr",
      texts: [],
      note: error instanceof Error ? error.message : "页面文字提取失败",
    }
  }
}

function getTranscriptRange(
  document: SubtitleDocument,
  args: { startMs: number; endMs: number; maxSegments?: number | null },
): TranscriptToolResult {
  const startMs = Math.max(0, Math.min(args.startMs, args.endMs))
  const endMs = Math.max(startMs, args.endMs)
  const maxSegments = clampInt(args.maxSegments ?? 120, 1, 400)
  const filtered = document.segments
    .filter((segment) => segment.endMs >= startMs && segment.startMs <= endMs)
    .slice(0, maxSegments)
  const firstSelected = filtered[0]
  const lastSelected = filtered.at(-1)

  return {
    segments: filtered.map((segment) => ({
      startMs: segment.startMs,
      endMs: segment.endMs,
      text: segment.text,
    })),
    hasMoreBefore: Boolean(firstSelected && document.segments[0] && document.segments[0].startMs < firstSelected.startMs),
    hasMoreAfter: Boolean(lastSelected && document.segments.at(-1) && (document.segments.at(-1)?.endMs ?? 0) > lastSelected.endMs),
  }
}

function searchTranscript(
  document: SubtitleDocument,
  args: { query: string; topK?: number | null },
): SearchToolResult {
  const normalizedQuery = normalizeSearchText(args.query)
  if (!normalizedQuery) return { hits: [] }
  const topK = clampInt(args.topK ?? 5, 1, 10)

  const hits = document.segments
    .map((segment) => ({
      startMs: segment.startMs,
      endMs: segment.endMs,
      text: segment.text,
      score: scoreTranscriptSegment(segment.text, normalizedQuery),
    }))
    .filter((hit) => hit.score > 0)
    .sort((left, right) => right.score - left.score || left.startMs - right.startMs)
    .slice(0, topK)

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

function normalizeSearchText(text: string) {
  return text.replace(/\s+/g, "").trim().toLowerCase()
}

function extractAssistantMessage(response: RawChatCompletionResponse): ChatCompletionMessage | null {
  const choices = Array.isArray(response.choices) ? response.choices : []
  const first = choices[0]
  if (!first || typeof first !== "object") return null
  const message = (first as { message?: unknown }).message
  if (!message || typeof message !== "object") return null
  return message as ChatCompletionMessage
}

function extractToolCalls(message: ChatCompletionMessage): ChatCompletionToolCall[] {
  if (!Array.isArray(message.tool_calls)) return []
  const toolCalls: ChatCompletionToolCall[] = []
  for (const item of message.tool_calls) {
    if (!item || typeof item !== "object") continue
    const raw = item as Record<string, unknown>
    const id = typeof raw.id === "string" ? raw.id : ""
    const fn = raw.function
    if (!id || !fn || typeof fn !== "object") continue
    const fnRecord = fn as Record<string, unknown>
    const name = typeof fnRecord.name === "string" ? fnRecord.name : ""
    const args = typeof fnRecord.arguments === "string" ? fnRecord.arguments : "{}"
    if (!name) continue
    toolCalls.push({
      id,
      function: {
        name,
        arguments: args,
      },
    })
  }
  return toolCalls
}

function extractMessageText(message: ChatCompletionMessage) {
  if (typeof message.content === "string") return message.content
  if (!Array.isArray(message.content)) return ""
  const fragments: string[] = []
  for (const part of message.content) {
    if (typeof part === "string") {
      fragments.push(part)
      continue
    }
    if (!part || typeof part !== "object") continue
    const text = (part as { text?: unknown }).text
    if (typeof text === "string") fragments.push(text)
  }
  return fragments.join("")
}

function buildAssistantReplayMessage(message: ChatCompletionMessage) {
  const replay: Record<string, unknown> = {
    role: "assistant",
  }
  replay.content = message.content ?? null
  if (Array.isArray(message.tool_calls) && message.tool_calls.length > 0) {
    replay.tool_calls = message.tool_calls
  }
  return replay
}

function buildFrameInspectionMessage(params: {
  toolName: string
  timeMs: number
  imageDataUrl: string
  preferHighDetail: boolean
}) {
  return {
    role: "user",
    content: [
      {
        type: "text",
        text: `以下是工具 ${params.toolName} 获取的视频帧，时间点为 ${formatTimestamp(params.timeMs)}。请将这张图片视为工具结果，用它辅助理解 PPT、公式、图表或页面结构；不要把它当成新的用户问题。`,
      },
      {
        type: "image_url",
        image_url: {
          url: params.imageDataUrl,
          detail: params.preferHighDetail ? "high" : "low",
        },
      },
    ],
  }
}

function buildEvidenceFromToolResult(
  instanceId: string,
  toolName: string,
  result: TranscriptToolResult | SearchToolResult | VideoFrameToolResult | SlideTextToolResult,
): AiChatCourseEvidence[] {
  if (toolName === "get_transcript_range" || toolName === "get_anchor_transcript_window") {
    if (!("segments" in result) || result.segments.length === 0) return []
    const startMs = result.segments[0]?.startMs ?? 0
    const endMs = result.segments.at(-1)?.endMs ?? startMs
    const preview = result.segments.map((segment) => segment.text.trim()).filter(Boolean).join(" ").slice(0, 160).trim()
    return [
      {
        kind: "transcript",
        instanceId,
        startMs,
        endMs,
        title: `字幕片段 ${formatTimestamp(startMs)}-${formatTimestamp(endMs)}`,
        preview,
      },
    ]
  }

  if (toolName === "search_transcript") {
    if (!("hits" in result) || result.hits.length === 0) return []
    return result.hits.slice(0, 3).map((hit) => ({
      kind: "transcript",
      instanceId,
      startMs: hit.startMs,
      endMs: hit.endMs,
      title: `相关字幕 ${formatTimestamp(hit.startMs)}-${formatTimestamp(hit.endMs)}`,
      preview: hit.text.trim().slice(0, 160).trim(),
    }))
  }

  if (toolName === "get_slide_text_around" && "texts" in result) {
    return [
      {
        kind: "slide_text",
        instanceId,
        startMs: result.timeMs,
        endMs: result.timeMs,
        title: `页面文字 ${formatTimestamp(result.timeMs)}`,
        preview: (result.texts.slice(0, 3).join(" / ") || result.note || "").slice(0, 160).trim(),
      },
    ]
  }

  if (toolName === "get_video_frame" && isVideoFrameResult(result) && result.available) {
    return [
      {
        kind: "video_frame",
        instanceId,
        startMs: result.timeMs,
        endMs: result.timeMs,
        title: `视频帧 ${formatTimestamp(result.timeMs)}`,
        preview: result.note?.slice(0, 160).trim() || "可回看该时刻的 PPT 或画面。",
      },
    ]
  }

  return []
}

function appendCourseEvidence(target: AiChatCourseEvidence[], items: AiChatCourseEvidence[]) {
  for (const item of items) {
    const key = `${item.kind}:${item.instanceId}:${item.startMs}:${item.endMs}`
    if (target.some((current) => `${current.kind}:${current.instanceId}:${current.startMs}:${current.endMs}` === key)) {
      continue
    }
    target.push(item)
  }
}

function stripLargeMediaPayload(result: TranscriptToolResult | SearchToolResult | VideoFrameToolResult | SlideTextToolResult) {
  if (!isVideoFrameResult(result)) return result
  return {
    timeMs: result.timeMs,
    available: result.available,
    mimeType: result.mimeType,
    note: result.note ?? (result.available ? "视频帧已捕获，并已作为多模态图片补充到后续消息中。" : "视频帧不可用。"),
  }
}

function isVideoFrameResult(
  result: TranscriptToolResult | SearchToolResult | VideoFrameToolResult | SlideTextToolResult,
): result is VideoFrameToolResult {
  return "imageDataUrl" in result || "mimeType" in result
}

function safeJsonParse(text: string) {
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

function toOptionalInt(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) return Math.floor(value)
  if (typeof value !== "string" || !value.trim()) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? Math.floor(parsed) : null
}

function toInt(value: unknown, fallback: number) {
  return toOptionalInt(value) ?? fallback
}

function clampInt(value: number, min: number, max: number) {
  return Math.min(Math.max(Math.floor(value), min), max)
}

function formatTimestamp(ms: number) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`
}

function normalizePreviewText(text: string, maxChars = 140) {
  const normalized = text.replace(/\s+/g, " ").trim()
  if (!normalized) return ""
  if (normalized.length <= maxChars) return normalized
  return `${normalized.slice(0, Math.max(1, maxChars - 1)).trimEnd()}…`
}

function buildCapabilityCacheKey(params: AskCourseAgentParams) {
  return [params.subjectId, params.projectId, params.modelName?.trim() || "__default__"].join(":")
}

function windowsOverlap(left: { startMs: number; endMs: number }, right: { startMs: number; endMs: number }) {
  return Math.max(left.startMs, right.startMs) <= Math.min(left.endMs, right.endMs) + 10_000
}

function extractReferencedTimeMs(text: string) {
  const normalized = text.replace(/\s+/g, "")
  const hmsMatch = normalized.match(/(\d{1,2}):(\d{2})(?::(\d{2}))?/)
  if (hmsMatch) {
    if (hmsMatch[3] !== undefined) {
      const hours = Number(hmsMatch[1])
      const minutes = Number(hmsMatch[2])
      const seconds = Number(hmsMatch[3])
      if ([hours, minutes, seconds].every(Number.isFinite)) {
        return (hours * 3600 + minutes * 60 + seconds) * 1000
      }
    }
    const minutes = Number(hmsMatch[1])
    const seconds = Number(hmsMatch[2])
    if ([minutes, seconds].every(Number.isFinite)) {
      return (minutes * 60 + seconds) * 1000
    }
  }

  const zhMatch = normalized.match(/(?:(\d{1,2})小时)?(\d{1,3})分(?:钟)?(?:(\d{1,2})秒)?/)
  if (zhMatch) {
    const hours = Number(zhMatch[1] ?? 0)
    const minutes = Number(zhMatch[2] ?? 0)
    const seconds = Number(zhMatch[3] ?? 0)
    if ([hours, minutes, seconds].every(Number.isFinite)) {
      return (hours * 3600 + minutes * 60 + seconds) * 1000
    }
  }

  const minuteOnlyMatch = normalized.match(/(?:^|[^\d])(\d{1,3})(?:分钟|分)(?!钟|秒)/)
  if (minuteOnlyMatch) {
    const minutes = Number(minuteOnlyMatch[1])
    if (Number.isFinite(minutes)) {
      return minutes * 60 * 1000
    }
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

function looksLikeSlideTextQuestion(text: string) {
  const normalized = text.replace(/\s+/g, "").toLowerCase()
  return (
    normalized.includes("ppt") ||
    normalized.includes("页面") ||
    normalized.includes("这一页") ||
    normalized.includes("这页") ||
    normalized.includes("标题") ||
    normalized.includes("要点") ||
    normalized.includes("公式") ||
    normalized.includes("图上") ||
    normalized.includes("图里")
  )
}

function classifyCapabilityError(error: unknown): CapabilityErrorKind {
  const haystack = collectErrorText(error)
  if (!haystack) return null
  const unsupportedHint = /(unsupported|not supported|does not support|is not supported|unknown parameter|unknown field|unexpected field|unrecognized request argument|invalid parameter|extra fields not permitted|not allowed)/

  if (unsupportedHint.test(haystack) && /(response_format|json_object|json schema|structured output|structured outputs)/.test(haystack)) {
    return "response_format"
  }
  if (unsupportedHint.test(haystack) && /(image_url|vision|multimodal|image input|images are not supported|content\[1\]\.image_url)/.test(haystack)) {
    return "vision"
  }
  if (unsupportedHint.test(haystack) && /(tool_choice|parallel_tool_calls|function calling|function call|tool calls|tool call|\btools\b)/.test(haystack)) {
    return "tool"
  }
  return null
}

function collectErrorText(error: unknown) {
  if (error instanceof ApiError) {
    return `${error.code} ${error.message} ${JSON.stringify(error.details ?? {})}`.toLowerCase()
  }
  if (error instanceof Error) {
    return `${error.name} ${error.message}`.toLowerCase()
  }
  return String(error).toLowerCase()
}

function isAbortLikeError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError"
}

async function resolveVideoSource(params: AskCourseAgentParams): Promise<{ src: string; revokeSrc?: () => void } | null> {
  if (params.sourceKind === "BAIDU_NETDISK") {
    return null
  }
  if (params.sourceKind === "BROWSER_LOCAL") {
    const file = await resolveProjectFile(params.projectId, params.instance.materialId)
    if (!file) return null
    const objectUrl = URL.createObjectURL(file)
    return {
      src: objectUrl,
      revokeSrc: () => URL.revokeObjectURL(objectUrl),
    }
  }

  return {
    src: apiUrl(projectApiPath({ subjectId: params.subjectId, scopedProjectId: params.projectId }, `/media/instances/${params.instance.instanceId}`)),
  }
}

async function captureFrameAsDataUrl(params: {
  src: string
  timeMs: number
  revokeSrc?: () => void
}): Promise<{ timeMs: number; imageDataUrl: string }> {
  const video = document.createElement("video")
  video.preload = "auto"
  video.muted = true
  video.playsInline = true
  video.crossOrigin = "anonymous"

  try {
    const metadataReady = waitForEvent(video, "loadedmetadata")
    video.src = params.src
    await metadataReady
    const durationMs =
      Number.isFinite(video.duration) && video.duration > 0 ? Math.floor(video.duration * 1000) : Number.POSITIVE_INFINITY
    const clampedMs = Number.isFinite(durationMs) ? clampInt(params.timeMs, 0, durationMs) : Math.max(0, params.timeMs)
    const seekReady = waitForEvent(video, "seeked")
    video.currentTime = clampedMs / 1000
    await seekReady

    const width = video.videoWidth || 0
    const height = video.videoHeight || 0
    if (width <= 0 || height <= 0) {
      throw new Error("视频帧尺寸不可用")
    }

    const scale = Math.min(1, 960 / Math.max(width, height))
    const canvas = document.createElement("canvas")
    canvas.width = Math.max(1, Math.round(width * scale))
    canvas.height = Math.max(1, Math.round(height * scale))
    const context = canvas.getContext("2d")
    if (!context) throw new Error("无法初始化视频帧画布")
    context.drawImage(video, 0, 0, canvas.width, canvas.height)

    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.76))
    if (!blob) throw new Error("视频帧编码失败")
    const imageDataUrl = await blobToDataUrl(blob)
    return { timeMs: clampedMs, imageDataUrl }
  } finally {
    video.pause()
    video.removeAttribute("src")
    video.load()
    params.revokeSrc?.()
  }
}

function waitForEvent(target: HTMLMediaElement, eventName: "loadedmetadata" | "seeked") {
  return new Promise<void>((resolve, reject) => {
    let settled = false
    const cleanup = () => {
      target.removeEventListener(eventName, handleSuccess)
      target.removeEventListener("error", handleError)
    }
    const finish = (callback: () => void) => {
      if (settled) return
      settled = true
      cleanup()
      callback()
    }
    const handleSuccess = () => finish(() => resolve())
    const handleError = () => finish(() => reject(new Error("视频加载失败")))
    target.addEventListener(eventName, handleSuccess, { once: true })
    target.addEventListener("error", handleError, { once: true })
  })
}

function blobToDataUrl(blob: Blob) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result)
        return
      }
      reject(new Error("图片编码失败"))
    }
    reader.onerror = () => reject(reader.error ?? new Error("图片读取失败"))
    reader.readAsDataURL(blob)
  })
}

async function extractSlideTextFromImage(
  params: AskCourseAgentParams,
  payload: { timeMs: number; imageDataUrl: string },
): Promise<SlideTextToolResult> {
  let response: RawChatCompletionResponse
  try {
    response = await requestSlideTextExtraction(params, payload, { useResponseFormat: true })
  } catch (error) {
    const capabilityError = classifyCapabilityError(error)
    if (capabilityError === "response_format") {
      response = await requestSlideTextExtraction(params, payload, { useResponseFormat: false })
    } else {
      if (capabilityError === "vision") {
        visionSupportCache.set(buildCapabilityCacheKey(params), false)
      }
      throw error
    }
  }

  const message = extractAssistantMessage(response)
  const text = extractMessageText(message ?? {}).trim()
  const parsedPayload = parseSlideTextPayload(text)

  return {
    timeMs: payload.timeMs,
    available: parsedPayload.texts.length > 0,
    source: "vision_ocr",
    texts: parsedPayload.texts,
    note: parsedPayload.note,
  }
}

async function requestSlideTextExtraction(
  params: AskCourseAgentParams,
  payload: { timeMs: number; imageDataUrl: string },
  options: { useResponseFormat: boolean },
) {
  return await askProjectLlmChatCompletion(
    { subjectId: params.subjectId, scopedProjectId: params.projectId },
    {
      modelName: params.modelName,
      temperature: 0,
      messages: [
        {
          role: "system",
          content:
            "你现在充当视频幻灯片 OCR 提取器。请只提取图片中清晰可见、足够确定的文字内容，优先保留标题、要点、项目符号、定义、公式中的文本变量与文字说明。不要解释，不要总结，不要补全看不清的内容。",
        },
        {
          role: "user",
          content: [
            {
              type: "text",
              text:
                "请从这张视频页面截图中提取可见文字，并输出 JSON：{\"texts\":[\"...\"],\"note\":\"...\"}。texts 里每一项是一行或一个要点；看不清就跳过；不要编造。",
            },
            {
              type: "image_url",
              image_url: {
                url: payload.imageDataUrl,
                detail: "high",
              },
            },
          ],
        },
      ],
      responseFormat: options.useResponseFormat
        ? {
            type: "json_object",
          }
        : undefined,
    },
    {
      signal: params.signal,
      timeoutMs: Math.min(params.timeoutMs ?? DEFAULT_TOOL_TIMEOUT_MS, DEFAULT_TOOL_TIMEOUT_MS),
    },
  )
}

function parseSlideTextPayload(text: string) {
  const parsed = safeJsonParse(text)
  const lines =
    parsed && typeof parsed === "object" && Array.isArray((parsed as { texts?: unknown }).texts)
      ? (parsed as { texts: unknown[] }).texts.filter((item): item is string => typeof item === "string").map((item) => item.trim()).filter(Boolean)
      : text
          .split(/\r?\n+/)
          .map((line) => line.replace(/^[-*•\d.\s]+/, "").trim())
          .filter(Boolean)
          .slice(0, 12)
  const note =
    parsed && typeof parsed === "object" && typeof (parsed as { note?: unknown }).note === "string"
      ? (parsed as { note: string }).note.trim()
      : text || "未提取到稳定文字。"
  return {
    texts: lines,
    note,
  }
}
