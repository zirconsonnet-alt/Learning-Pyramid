import { z } from "zod"

import { ApiError, apiRequest, getBaseUrl, type ApiRequestExecutionOptions } from "@/ui/api/http"
import { isVirtualStudyReviewProjectId } from "@/ui/guideWalkthrough/guideVirtualProjectIds"

export const SystemCapabilitiesSchema = z.object({
  appMode: z.enum(["local", "hosted"]),
  asrEnabled: z.boolean(),
  serverMediaStreamEnabled: z.boolean(),
  browserLocalMediaEnabled: z.boolean(),
  baiduNetdiskEnabled: z.boolean(),
  authEnabled: z.boolean(),
  allowSignup: z.boolean(),
  signupInviteRequired: z.boolean(),
  passwordResetEnabled: z.boolean(),
  emailVerificationEnabled: z.boolean(),
  signupHumanCheckEnabled: z.boolean(),
  signupHumanCheckProvider: z.literal("altcha").nullable(),
  signupHumanCheckChallengeUrl: z.string().nullable(),
  llmConfigured: z.boolean(),
  storyGenerationConfigured: z.boolean(),
  llmSource: z.enum(["user", "global", "env", "none"]),
})
export type SystemCapabilities = z.infer<typeof SystemCapabilitiesSchema>

export function getSystemCapabilities(options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: "/system/capabilities",
    responseSchema: SystemCapabilitiesSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export const DataSafetyFindingSchema = z.object({
  severity: z.enum(["blocking", "warning", "info"]),
  code: z.string(),
  message: z.string(),
  protectedClassId: z.string(),
  affectedEntityIds: z.array(z.string()),
  expectedLocation: z.string().nullable(),
  observedState: z.string().nullable(),
  recommendedAction: z.string().nullable(),
})

export const ProtectedDataClassSchema = z.object({
  id: z.string(),
  label: z.string(),
  storageKind: z.enum(["database", "filesystem", "derived-index"]),
  locations: z.array(z.string()),
  criticality: z.enum(["blocking", "warning"]),
  ownerComponent: z.string(),
})

export const DataSafetyStatusSchema = z.object({
  state: z.enum(["ok", "warning", "blocked", "unknown"]),
  checkedAt: z.string(),
  environment: z.string(),
  releaseBlocked: z.boolean(),
  protectedClasses: z.array(ProtectedDataClassSchema),
  latestVerifiedBackup: z.record(z.string(), z.unknown()).nullable(),
  findings: z.array(DataSafetyFindingSchema),
})
export type DataSafetyStatus = z.infer<typeof DataSafetyStatusSchema>

export function getSystemDataSafetyStatus(options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: "/system/data-safety",
    responseSchema: DataSafetyStatusSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export const PublicDownloadItemSchema = z.object({
  id: z.string(),
  displayName: z.string(),
  version: z.string().nullable(),
  platform: z.string().nullable(),
  summary: z.string().nullable(),
  fileName: z.string(),
  assetPath: z.string(),
  downloadPath: z.string(),
  publishedAt: z.string().nullable(),
  sha256: z.string().nullable(),
  sizeBytes: z.number().int().nonnegative(),
  recommended: z.boolean(),
  includedComponents: z.array(z.string()),
  requirements: z.array(z.string()),
})
export type PublicDownloadItem = z.infer<typeof PublicDownloadItemSchema>

export const PublicDownloadsSchema = z.object({
  generatedAt: z.string().nullable(),
  items: z.array(PublicDownloadItemSchema),
})
export type PublicDownloads = z.infer<typeof PublicDownloadsSchema>

export function getPublicDownloads(options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: "/system/public-downloads",
    responseSchema: PublicDownloadsSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export const SystemRuntimeSchema = z
  .object({
    status: z.string(),
    appMode: z.enum(["local", "hosted"]),
    authEnabled: z.boolean(),
    allowSignup: z.boolean(),
    signupInviteRequired: z.boolean(),
    asrEnabled: z.boolean(),
    serverMediaStreamEnabled: z.boolean(),
    browserLocalMediaEnabled: z.boolean(),
    baiduNetdiskEnabled: z.boolean(),
    emailVerificationEnabled: z.boolean().optional(),
    signupHumanCheckEnabled: z.boolean().optional(),
    signupHumanCheckProvider: z.literal("altcha").nullable().optional(),
    sqlBackend: z.string(),
  })
  .passthrough()
export type SystemRuntime = z.infer<typeof SystemRuntimeSchema> & { ready: boolean }

const SystemRuntimeEnvelopeSchema = z.object({
  ok: z.boolean(),
  data: SystemRuntimeSchema,
})

function buildRequestTimeoutMessage(timeoutMs: number) {
  const seconds = Math.max(1, Math.round(timeoutMs / 1000))
  return `请求在 ${seconds} 秒内没有完成。请检查 VPN、Wi-Fi 或移动网络后重试。`
}

export async function getSystemRuntime(options?: ApiRequestExecutionOptions): Promise<SystemRuntime> {
  const controller = new AbortController()
  const listeners: Array<() => void> = []
  const timeoutMs = options?.timeoutMs ?? 25_000
  let timedOut = false
  let timeoutId: ReturnType<typeof globalThis.setTimeout> | null = null

  if (options?.signal) {
    if (options.signal.aborted) {
      controller.abort()
    } else {
      const onAbort = () => controller.abort()
      options.signal.addEventListener("abort", onAbort, { once: true })
      listeners.push(() => options.signal?.removeEventListener("abort", onAbort))
    }
  }

  timeoutId = globalThis.setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  let res: Response
  let text: string
  try {
    res = await fetch(`${getBaseUrl()}/system/runtime`, {
      method: "GET",
      credentials: "include",
      signal: controller.signal,
    })
    text = await res.text()
  } catch (error) {
    if (timeoutId !== null) globalThis.clearTimeout(timeoutId)
    listeners.forEach((cleanup) => cleanup())
    if (options?.signal?.aborted) throw error
    if (timedOut) {
      throw new ApiError(buildRequestTimeoutMessage(timeoutMs), {
        code: "REQUEST_TIMEOUT",
        status: 0,
        details: { path: "/system/runtime", timeoutMs },
      })
    }
    if (error instanceof TypeError) {
      throw new ApiError("网络连接已中断，暂时无法连接服务器。请检查 VPN、Wi-Fi 或移动网络后重试。", {
        code: "NETWORK_ERROR",
        status: 0,
        details: {
          path: "/system/runtime",
          cause: { name: error.name, message: error.message },
        },
      })
    }
    throw new ApiError("请求失败，请稍后重试。", {
      code: "REQUEST_FAILED",
      status: 0,
      details: {
        path: "/system/runtime",
        cause: error instanceof Error ? { name: error.name, message: error.message } : { message: String(error) },
      },
    })
  }

  if (timeoutId !== null) globalThis.clearTimeout(timeoutId)
  listeners.forEach((cleanup) => cleanup())
  const raw = text.trim()
  if (!raw) {
    throw new ApiError(`Empty response body (status=${res.status})`, { code: "EMPTY_RESPONSE", status: res.status })
  }
  let json: unknown
  try {
    json = JSON.parse(text)
  } catch (e) {
    throw new ApiError(`Invalid JSON response (status=${res.status})`, {
      code: "INVALID_JSON",
      status: res.status,
      details: { cause: String(e), body: text.slice(0, 500) },
    })
  }
  const env = SystemRuntimeEnvelopeSchema.parse(json)
  return {
    ...env.data,
    ready: env.ok,
  }
}

export async function requestPomodoroTtsPreviewAudio(
  body: { text: string },
  options?: ApiRequestExecutionOptions,
): Promise<Blob> {
  const controller = new AbortController()
  const listeners: Array<() => void> = []
  const timeoutMs = options?.timeoutMs ?? 25_000
  let timedOut = false
  let timeoutId: ReturnType<typeof globalThis.setTimeout> | null = null

  if (options?.signal) {
    if (options.signal.aborted) {
      controller.abort()
    } else {
      const onAbort = () => controller.abort()
      options.signal.addEventListener("abort", onAbort, { once: true })
      listeners.push(() => options.signal?.removeEventListener("abort", onAbort))
    }
  }

  if (timeoutMs > 0) {
    timeoutId = globalThis.setTimeout(() => {
      timedOut = true
      controller.abort()
    }, timeoutMs)
  }

  try {
    const response = await fetch(`${getBaseUrl()}/system/pomodoro/tts-preview`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    })

    if (!response.ok) {
      const text = await response.text()
      try {
        const json = JSON.parse(text)
        const errorEnvelope = z
          .object({
            ok: z.literal(false),
            error: z.object({
              code: z.string(),
              message: z.string(),
              details: z.unknown().optional(),
            }),
          })
          .safeParse(json)
        if (errorEnvelope.success) {
          throw new ApiError(errorEnvelope.data.error.message, {
            code: errorEnvelope.data.error.code,
            status: response.status,
            details: errorEnvelope.data.error.details,
          })
        }
      } catch (error) {
        if (error instanceof ApiError) throw error
      }
      throw new ApiError(`HTTP ${response.status}`, {
        code: "HTTP_ERROR",
        status: response.status,
        details: { path: "/system/pomodoro/tts-preview", body: text.slice(0, 500) },
      })
    }

    const blob = await response.blob()
    if (!blob.size) {
      throw new ApiError("Empty audio response", {
        code: "EMPTY_RESPONSE",
        status: response.status,
        details: { path: "/system/pomodoro/tts-preview" },
      })
    }
    return blob
  } catch (error) {
    if (options?.signal?.aborted) throw error
    if (timedOut) {
      throw new ApiError(buildRequestTimeoutMessage(timeoutMs), {
        code: "REQUEST_TIMEOUT",
        status: 0,
        details: { path: "/system/pomodoro/tts-preview", timeoutMs },
      })
    }
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === "AbortError") throw error
    if (error instanceof TypeError) {
      throw new ApiError("网络连接已中断，暂时无法连接服务器。请检查 VPN、Wi-Fi 或移动网络后重试。", {
        code: "NETWORK_ERROR",
        status: 0,
        details: { path: "/system/pomodoro/tts-preview", cause: { name: error.name, message: error.message } },
      })
    }
    throw new ApiError("请求失败，请稍后重试。", {
      code: "REQUEST_FAILED",
      status: 0,
      details: {
        path: "/system/pomodoro/tts-preview",
        cause: error instanceof Error ? { name: error.name, message: error.message } : { message: String(error) },
      },
    })
  } finally {
    if (timeoutId !== null) globalThis.clearTimeout(timeoutId)
    listeners.forEach((cleanup) => cleanup())
  }
}

export const GlobalLlmSettingsSchema = z.object({
  baseUrl: z.string(),
  modelName: z.string(),
  promptAssemblyMode: z.enum(["system", "user_concat"]),
  savedApiKeyConfigured: z.boolean(),
  savedApiKeyPreview: z.string().nullable(),
  llmConfigured: z.boolean(),
  storyGenerationConfigured: z.boolean(),
  llmSource: z.enum(["user", "global", "env", "none"]),
})
export type GlobalLlmSettings = z.infer<typeof GlobalLlmSettingsSchema>

export function getGlobalLlmSettings(options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: "/system/global-llm-settings",
    responseSchema: GlobalLlmSettingsSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function updateGlobalLlmSettings(
  body: {
    baseUrl?: string
    modelName?: string
    apiKey?: string
    promptAssemblyMode?: "system" | "user_concat"
    clearApiKey?: boolean
  },
  options?: ApiRequestExecutionOptions,
) {
  return apiRequest({
    path: "/system/global-llm-settings",
    method: "PUT",
    body,
    responseSchema: GlobalLlmSettingsSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export const AskSystemLlmResultSchema = z.object({
  content: z.string(),
})
export type AskSystemLlmResult = z.infer<typeof AskSystemLlmResultSchema>

export const RawChatCompletionResponseSchema = z.object({}).passthrough()
export type RawChatCompletionResponse = z.infer<typeof RawChatCompletionResponseSchema>

export const ProjectLlmDebugMessageSchema = z.object({
  role: z.string(),
  content: z.string(),
})
export type ProjectLlmDebugMessage = z.infer<typeof ProjectLlmDebugMessageSchema>

export const ProjectLlmDebugRecordSchema = z.object({
  recordedAt: z.string(),
  projectId: z.string(),
  requestModelName: z.string().nullable(),
  resolvedModelName: z.string(),
  temperature: z.number().nullable(),
  stream: z.boolean(),
  serviceUrl: z.string(),
  contextTargetKind: z.enum(["project", "task", "object", "recall"]),
  contextTargetId: z.string().nullable(),
  messages: z.array(ProjectLlmDebugMessageSchema),
  responseContent: z.string(),
  errorMessage: z.string().nullable(),
})
export type ProjectLlmDebugRecord = z.infer<typeof ProjectLlmDebugRecordSchema>

export function getLatestProjectLlmDebug(projectId: string, options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: `/projects/${projectId}/llm/debug/latest`,
    responseSchema: ProjectLlmDebugRecordSchema.nullable(),
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function askSystemLlm(
  body: {
    prompt: string
    systemPrompt?: string
    modelName?: string
    temperature?: number
  },
  options?: ApiRequestExecutionOptions,
) {
  return apiRequest({
    path: "/system/llm/ask",
    method: "POST",
    body,
    responseSchema: AskSystemLlmResultSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function askProjectLlm(
  projectId: string,
  body: {
    prompt: string
    systemPrompt?: string
    supplementalContext?: string
    modelName?: string
    temperature?: number
    recallPointId?: string
    learningTaskNodeId?: string
    learningObjectNodeId?: string
  },
  options?: ApiRequestExecutionOptions,
) {
  return apiRequest({
    path: `/projects/${projectId}/llm/ask`,
    method: "POST",
    body,
    responseSchema: AskSystemLlmResultSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function askProjectLlmChatCompletion(
  projectId: string,
  body: {
    messages: Array<Record<string, unknown>>
    tools?: Array<Record<string, unknown>>
    toolChoice?: unknown
    parallelToolCalls?: boolean
    responseFormat?: Record<string, unknown>
    modelName?: string
    temperature?: number
  },
  options?: ApiRequestExecutionOptions,
) {
  if (isVirtualStudyReviewProjectId(projectId)) {
    throw new ApiError("引导示范项目不提供 AI 对话。", {
      code: "PRECONDITION",
      status: 400,
      details: { projectId },
    })
  }
  return apiRequest({
    path: `/projects/${projectId}/llm/chat-completions`,
    method: "POST",
    body,
    responseSchema: RawChatCompletionResponseSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

function buildStreamTimeoutMessage(timeoutMs: number) {
  const seconds = Math.max(1, Math.round(timeoutMs / 1000))
  return `请求在 ${seconds} 秒内没有完成。请检查 VPN、Wi-Fi 或移动网络后重试。`
}

type AskProjectLlmStreamOptions = ApiRequestExecutionOptions & {
  onDelta?: (chunk: string, accumulated: string) => void
}

export async function askProjectLlmStream(
  projectId: string,
  body: {
    prompt: string
    systemPrompt?: string
    supplementalContext?: string
    modelName?: string
    temperature?: number
    recallPointId?: string
    learningTaskNodeId?: string
    learningObjectNodeId?: string
  },
  options?: AskProjectLlmStreamOptions,
): Promise<{ content: string }> {
  const url = `${getBaseUrl()}/projects/${projectId}/llm/ask/stream`
  const controller = new AbortController()
  const listeners: Array<() => void> = []
  const timeoutMs = options?.timeoutMs ?? 90_000
  let timedOut = false
  let timeoutId: ReturnType<typeof globalThis.setTimeout> | null = null

  if (options?.signal) {
    if (options.signal.aborted) {
      controller.abort()
    } else {
      const onAbort = () => controller.abort()
      options.signal.addEventListener("abort", onAbort, { once: true })
      listeners.push(() => options.signal?.removeEventListener("abort", onAbort))
    }
  }

  if (timeoutMs > 0) {
    timeoutId = globalThis.setTimeout(() => {
      timedOut = true
      controller.abort()
    }, timeoutMs)
  }

  try {
    const response = await fetch(url, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    })

    if (!response.ok) {
      const text = await response.text()
      try {
        const json = JSON.parse(text)
        const errorEnvelope = z
          .object({
            ok: z.literal(false),
            error: z.object({
              code: z.string(),
              message: z.string(),
              details: z.unknown().optional(),
            }),
          })
          .safeParse(json)
        if (errorEnvelope.success) {
          throw new ApiError(errorEnvelope.data.error.message, {
            code: errorEnvelope.data.error.code,
            status: response.status,
            details: errorEnvelope.data.error.details,
          })
        }
      } catch (error) {
        if (error instanceof ApiError) throw error
      }
      throw new ApiError(`HTTP ${response.status}`, {
        code: "HTTP_ERROR",
        status: response.status,
        details: { url, body: text.slice(0, 500) },
      })
    }

    if (!response.body) {
      throw new ApiError("Empty stream body", { code: "EMPTY_RESPONSE", status: response.status, details: { url } })
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""
    let accumulated = ""

    function handleEventBlock(block: string) {
      const normalizedBlock = block.replace(/\r\n/g, "\n").trim()
      if (!normalizedBlock) return
      let eventName = "message"
      const dataLines: string[] = []
      for (const line of normalizedBlock.split("\n")) {
        if (line.startsWith("event:")) {
          eventName = line.slice(6).trim() || "message"
          continue
        }
        if (line.startsWith("data:")) {
          dataLines.push(line.slice(5).trimStart())
        }
      }
      if (dataLines.length === 0) return
      const payloadText = dataLines.join("\n")
      let payload: unknown
      try {
        payload = JSON.parse(payloadText)
      } catch (error) {
        throw new ApiError("Invalid stream payload", {
          code: "INVALID_STREAM",
          status: response.status,
          details: { url, payloadText: payloadText.slice(0, 500), cause: String(error) },
        })
      }
      if (!payload || typeof payload !== "object") return
      if (eventName === "delta") {
        const chunk = typeof (payload as { content?: unknown }).content === "string" ? (payload as { content: string }).content : ""
        if (!chunk) return
        accumulated += chunk
        options?.onDelta?.(chunk, accumulated)
        return
      }
      if (eventName === "error") {
        const message = typeof (payload as { message?: unknown }).message === "string" ? (payload as { message: string }).message : "请求失败，请稍后重试。"
        const code = typeof (payload as { code?: unknown }).code === "string" ? (payload as { code: string }).code : "STREAM_ERROR"
        throw new ApiError(message, { code, status: response.status, details: payload })
      }
    }

    while (true) {
      const { value, done } = await reader.read()
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
      const normalizedBuffer = buffer.replace(/\r\n/g, "\n")
      const parts = normalizedBuffer.split("\n\n")
      buffer = parts.pop() ?? ""
      for (const part of parts) {
        handleEventBlock(part)
      }
      if (done) break
    }

    if (buffer.trim()) {
      handleEventBlock(buffer)
    }

    return { content: accumulated }
  } catch (error) {
    if (options?.signal?.aborted) throw error
    if (timedOut) {
      throw new ApiError(buildStreamTimeoutMessage(timeoutMs), {
        code: "REQUEST_TIMEOUT",
        status: 0,
        details: { url, timeoutMs },
      })
    }
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === "AbortError") throw error
    if (error instanceof TypeError) {
      throw new ApiError("网络连接已中断，暂时无法连接服务器。请检查 VPN、Wi-Fi 或移动网络后重试。", {
        code: "NETWORK_ERROR",
        status: 0,
        details: { url, cause: { name: error.name, message: error.message } },
      })
    }
    throw new ApiError("请求失败，请稍后重试。", {
      code: "REQUEST_FAILED",
      status: 0,
      details: { url, cause: error instanceof Error ? { name: error.name, message: error.message } : { message: String(error) } },
    })
  } finally {
    if (timeoutId !== null) globalThis.clearTimeout(timeoutId)
    listeners.forEach((cleanup) => cleanup())
  }
}
