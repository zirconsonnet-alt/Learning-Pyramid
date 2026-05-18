import { z } from "zod"

import { buildCookieHeader, extractSessionCookieUpdate } from "../auth/sessionCookie"

const ApiOkEnvelopeSchema = z.object({ ok: z.literal(true), data: z.unknown() })
const ApiErrEnvelopeSchema = z.object({
  ok: z.literal(false),
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.unknown().optional(),
  }),
})
const ApiEnvelopeSchema = z.union([ApiOkEnvelopeSchema, ApiErrEnvelopeSchema])

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

export function parseApiEnvelope<T>(json: unknown, responseSchema: z.ZodType<T>, status: number): T {
  const env = ApiEnvelopeSchema.parse(json)
  if (!env.ok) {
    throw new ApiError(env.error.message, { code: env.error.code, status, details: env.error.details })
  }
  return responseSchema.parse(env.data)
}

export type ApiClientOptions = {
  baseUrl: string
  fetchImpl?: ApiFetch
  getSessionCookie?: () => string | null | undefined
  setSessionCookie?: (cookie: string | null) => void
}

export type ApiFetch = (
  input: string,
  init: { method: string; headers: Record<string, string>; body?: string },
) => Promise<{
  status: number
  headers: { get: (name: string) => string | null }
  text: () => Promise<string>
}>

export type ApiRequestOptions<T> = {
  path: string
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
  body?: unknown
  responseSchema: z.ZodType<T>
}

export function resolveApiResourceUrl(baseUrl: string, resourceUrl: string) {
  const rawUrl = resourceUrl.trim()
  if (/^https?:\/\//i.test(rawUrl)) return rawUrl
  const normalizedBaseUrl = baseUrl.replace(/\/$/, "")
  if (rawUrl.startsWith("/")) return new URL(rawUrl, normalizedBaseUrl).toString()
  return `${normalizedBaseUrl}/${rawUrl}`
}

export function createApiClient(options: ApiClientOptions) {
  const baseUrl = options.baseUrl.replace(/\/$/, "")
  const fetchImpl = options.fetchImpl ?? fetch

  async function request<T>({
    path,
    method = "GET",
    body,
    responseSchema,
  }: ApiRequestOptions<T>): Promise<T> {
    const headers: Record<string, string> = {}
    const cookieHeader = buildCookieHeader(options.getSessionCookie?.())
    if (cookieHeader) headers.Cookie = cookieHeader
    if (body !== undefined) headers["Content-Type"] = "application/json"

    const response = await fetchImpl(`${baseUrl}${path.startsWith("/") ? path : `/${path}`}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    const cookieUpdate = extractSessionCookieUpdate(response.headers.get("set-cookie"))
    if (cookieUpdate.kind === "set") options.setSessionCookie?.(cookieUpdate.cookie)
    if (cookieUpdate.kind === "clear") options.setSessionCookie?.(null)

    const text = await response.text()
    const json = JSON.parse(text)
    return parseApiEnvelope(json, responseSchema, response.status)
  }

  return { request }
}
