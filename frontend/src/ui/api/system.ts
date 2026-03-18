import { z } from "zod"

import { ApiError, apiRequest, getBaseUrl, type ApiRequestExecutionOptions } from "@/ui/api/http"

export const SystemCapabilitiesSchema = z.object({
  appMode: z.enum(["local", "hosted"]),
  asrEnabled: z.boolean(),
  serverMediaStreamEnabled: z.boolean(),
  browserLocalMediaEnabled: z.boolean(),
  authEnabled: z.boolean(),
  allowSignup: z.boolean(),
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

export const SystemRuntimeSchema = z
  .object({
    status: z.string(),
    appMode: z.enum(["local", "hosted"]),
    authEnabled: z.boolean(),
    allowSignup: z.boolean(),
    asrEnabled: z.boolean(),
    serverMediaStreamEnabled: z.boolean(),
    browserLocalMediaEnabled: z.boolean(),
    sqlBackend: z.string(),
  })
  .passthrough()
export type SystemRuntime = z.infer<typeof SystemRuntimeSchema> & { ready: boolean }

const SystemRuntimeEnvelopeSchema = z.object({
  ok: z.boolean(),
  data: SystemRuntimeSchema,
})

export async function getSystemRuntime(options?: ApiRequestExecutionOptions): Promise<SystemRuntime> {
  const controller = new AbortController()
  const listeners: Array<() => void> = []
  const timeoutMs = options?.timeoutMs ?? 12_000
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
      throw new ApiError("请求在 12 秒内没有完成。请检查 VPN、Wi-Fi 或移动网络后重试。", {
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
