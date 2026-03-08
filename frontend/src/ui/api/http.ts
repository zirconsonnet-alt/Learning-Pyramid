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

function getBaseUrl() {
  const v = import.meta.env.VITE_API_BASE_URL as string | undefined
  return v && v.trim() ? v.trim().replace(/\/$/, "") : "/api"
}

export async function apiRequest<T>({
  path,
  method,
  body,
  responseSchema,
}: {
  path: string
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
  body?: unknown
  responseSchema: z.ZodType<T>
}): Promise<T> {
  const url = `${getBaseUrl()}${path.startsWith("/") ? path : `/${path}`}`
  const res = await fetch(url, {
    method: method ?? "GET",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  const text = await res.text()
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
      details: { url, body: text.slice(0, 500), cause: String(e) },
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
