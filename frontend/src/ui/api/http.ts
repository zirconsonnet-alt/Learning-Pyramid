import { z } from "zod"

const ApiOkEnvelope = z.object({ ok: z.literal(true), data: z.unknown() })
const ApiErrEnvelope = z.object({
  ok: z.literal(false),
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.unknown().optional(),
  }),
})
const ApiEnvelope = z.union([ApiOkEnvelope, ApiErrEnvelope])

export class ApiError extends Error {
  code: string
  status: number
  details?: unknown

  constructor(message: string, opts: { code: string; status: number; details?: unknown }) {
    super(message)
    this.code = opts.code
    this.status = opts.status
    this.details = opts.details
  }
}

export type ApiRequestMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE"

export type ApiRequestExecutionOptions = {
  signal?: AbortSignal
  timeoutMs?: number
}

const API_GET_TIMEOUT_MS = 25_000
const API_MUTATION_TIMEOUT_MS = 25_000
const DEFAULT_PAYLOAD_TOO_LARGE_MESSAGE = "上传内容过大，服务器或网关拒绝了这次请求。请压缩后重试；如果问题持续出现，需要调大站点上传限制。"

export function getBaseUrl() {
  const v = import.meta.env.VITE_API_BASE_URL as string | undefined
  return v && v.trim() ? v.trim().replace(/\/$/, "") : "/api"
}

function resolveTimeoutMs(method: ApiRequestMethod, timeoutMs?: number) {
  if (typeof timeoutMs === "number" && timeoutMs >= 0) return timeoutMs
  return method === "GET" ? API_GET_TIMEOUT_MS : API_MUTATION_TIMEOUT_MS
}

function buildRequestTimeoutMessage(timeoutMs: number) {
  const seconds = Math.max(1, Math.round(timeoutMs / 1000))
  return `请求在 ${seconds} 秒内没有完成。请检查 VPN、Wi-Fi 或移动网络后重试。`
}

function buildNetworkFailureMessage() {
  return "网络连接已中断，暂时无法连接服务器。请检查 VPN、Wi-Fi 或移动网络后重试。"
}

function buildGenericFailureMessage() {
  return "请求失败，请稍后重试。"
}

function buildNonJsonResponseError(params: {
  status: number
  body: string
  url: string
  cause: string
  payloadTooLargeMessage?: string
}) {
  const { status, body, url, cause, payloadTooLargeMessage } = params
  if (status === 413) {
    return new ApiError(payloadTooLargeMessage ?? DEFAULT_PAYLOAD_TOO_LARGE_MESSAGE, {
      code: "PAYLOAD_TOO_LARGE",
      status,
      details: { url, body: body.slice(0, 500), cause },
    })
  }
  return new ApiError(`Invalid JSON response (status=${status})`, {
    code: "INVALID_JSON",
    status,
    details: { url, body: body.slice(0, 500), cause },
  })
}

function toFailureCause(error: unknown) {
  return error instanceof Error ? { name: error.name, message: error.message } : { message: String(error) }
}

function isCallerAborted(signal: AbortSignal | undefined) {
  return Boolean(signal?.aborted)
}

export async function apiRequest<T>({
  path,
  method,
  body,
  headers,
  responseSchema,
  signal,
  timeoutMs,
  payloadTooLargeMessage,
}: {
  path: string
  method?: ApiRequestMethod
  body?: unknown
  headers?: Record<string, string>
  responseSchema: z.ZodType<T>
  signal?: AbortSignal
  timeoutMs?: number
  payloadTooLargeMessage?: string
}): Promise<T> {
  const requestMethod = method ?? "GET"
  const url = `${getBaseUrl()}${path.startsWith("/") ? path : `/${path}`}`
  const controller = new AbortController()
  const listeners: Array<() => void> = []
  const effectiveTimeoutMs = resolveTimeoutMs(requestMethod, timeoutMs)
  let timedOut = false
  let timeoutId: ReturnType<typeof globalThis.setTimeout> | null = null

  if (signal) {
    if (signal.aborted) {
      controller.abort()
    } else {
      const onAbort = () => controller.abort()
      signal.addEventListener("abort", onAbort, { once: true })
      listeners.push(() => signal.removeEventListener("abort", onAbort))
    }
  }

  if (effectiveTimeoutMs > 0) {
    timeoutId = globalThis.setTimeout(() => {
      timedOut = true
      controller.abort()
    }, effectiveTimeoutMs)
  }

  let res: Response
  let text: string
  try {
    const isFormDataBody = typeof FormData !== "undefined" && body instanceof FormData
    const isBlobBody = typeof Blob !== "undefined" && body instanceof Blob
    const requestHeaders =
      body === undefined ? headers : isFormDataBody || isBlobBody ? headers : { "Content-Type": "application/json", ...(headers ?? {}) }
    res = await fetch(url, {
      method: requestMethod,
      credentials: "include",
      headers: requestHeaders,
      body: body === undefined ? undefined : isFormDataBody || isBlobBody ? body : JSON.stringify(body),
      signal: controller.signal,
    })
    text = await res.text()
  } catch (error) {
    if (timeoutId !== null) globalThis.clearTimeout(timeoutId)
    listeners.forEach((cleanup) => cleanup())
    if (isCallerAborted(signal)) throw error
    if (timedOut) {
      throw new ApiError(buildRequestTimeoutMessage(effectiveTimeoutMs), {
        code: "REQUEST_TIMEOUT",
        status: 0,
        details: { url, timeoutMs: effectiveTimeoutMs },
      })
    }
    if (error instanceof TypeError) {
      throw new ApiError(buildNetworkFailureMessage(), {
        code: "NETWORK_ERROR",
        status: 0,
        details: { url, cause: toFailureCause(error) },
      })
    }
    throw new ApiError(buildGenericFailureMessage(), {
      code: "REQUEST_FAILED",
      status: 0,
      details: { url, cause: toFailureCause(error) },
    })
  }

  if (timeoutId !== null) globalThis.clearTimeout(timeoutId)
  listeners.forEach((cleanup) => cleanup())
  const raw = text.trim()
  if (!raw) {
    if (res.status === 413) {
      throw new ApiError(payloadTooLargeMessage ?? DEFAULT_PAYLOAD_TOO_LARGE_MESSAGE, {
        code: "PAYLOAD_TOO_LARGE",
        status: res.status,
        details: { url },
      })
    }
    throw new ApiError(`Empty response body (status=${res.status})`, { code: "EMPTY_RESPONSE", status: res.status })
  }

  let json: unknown
  try {
    json = JSON.parse(text)
  } catch (e) {
    throw buildNonJsonResponseError({
      status: res.status,
      body: text,
      url,
      cause: String(e),
      payloadTooLargeMessage,
    })
  }

  let env: z.infer<typeof ApiEnvelope>
  try {
    env = ApiEnvelope.parse(json)
  } catch (e) {
    throw new ApiError(`Invalid API envelope (status=${res.status})`, {
      code: "INVALID_ENVELOPE",
      status: res.status,
      details: { url, json, cause: String(e) },
    })
  }

  if (!env.ok) {
    throw new ApiError(env.error.message, { code: env.error.code, status: res.status, details: env.error.details })
  }

  return responseSchema.parse(env.data)
}
