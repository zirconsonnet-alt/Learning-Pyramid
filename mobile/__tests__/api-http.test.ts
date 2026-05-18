import { z } from "zod"

import { ApiError, createApiClient, parseApiEnvelope } from "../src/api/http"

type FetchInit = {
  method?: string
  headers: Record<string, string>
  body?: string
}

type FetchResponse = {
  status: number
  headers: { get: (name: string) => string | null }
  text: () => Promise<string>
}

function createFetchMock(handler: (url: string, init: FetchInit) => Promise<FetchResponse>) {
  return jest.fn(handler) as jest.MockedFunction<(url: string, init: FetchInit) => Promise<FetchResponse>>
}

describe("parseApiEnvelope", () => {
  it("returns typed data from ok envelope", () => {
    const data = parseApiEnvelope(
      { ok: true, data: { userId: "u1" } },
      z.object({ userId: z.string() }),
      200,
    )

    expect(data.userId).toBe("u1")
  })

  it("throws ApiError from error envelope", () => {
    expect(() =>
      parseApiEnvelope(
        { ok: false, error: { code: "AUTH", message: "Authentication required" } },
        z.object({}),
        401,
      ),
    ).toThrow(ApiError)
  })
})

describe("createApiClient", () => {
  it("sends existing session cookie and stores new session cookie", async () => {
    let storedCookie: string | null = "plm_session=old"
    const fetchImpl = createFetchMock(async () => ({
      status: 200,
      headers: {
        get: (name: string) =>
          name.toLowerCase() === "set-cookie" ? "plm_session=new; Path=/; HttpOnly" : null,
      },
      text: async () => JSON.stringify({ ok: true, data: { userId: "u1" } }),
    }))

    const client = createApiClient({
      baseUrl: "https://plm.xuebao.chat/api",
      fetchImpl,
      getSessionCookie: () => storedCookie,
      setSessionCookie: (cookie) => {
        storedCookie = cookie
      },
    })

    const data = await client.request({
      path: "/auth/me",
      responseSchema: z.object({ userId: z.string() }),
    })

    expect(data.userId).toBe("u1")
    expect(fetchImpl.mock.calls[0][1].headers.Cookie).toBe("plm_session=old")
    expect(storedCookie).toBe("plm_session=new")
  })

  it("clears stored session cookie when Set-Cookie clears plm_session", async () => {
    let storedCookie: string | null = "plm_session=old"
    const fetchImpl = createFetchMock(async () => ({
      status: 200,
      headers: {
        get: (name: string) =>
          name.toLowerCase() === "set-cookie" ? "plm_session=; Max-Age=0; Path=/" : null,
      },
      text: async () => JSON.stringify({ ok: true, data: { ok: true } }),
    }))

    const client = createApiClient({
      baseUrl: "https://plm.xuebao.chat/api",
      fetchImpl,
      getSessionCookie: () => storedCookie,
      setSessionCookie: (cookie) => {
        storedCookie = cookie
      },
    })

    await client.request({
      path: "/auth/logout",
      method: "POST",
      responseSchema: z.object({ ok: z.boolean() }),
    })

    expect(storedCookie).toBeNull()
  })

  it("posts JSON body to the resolved URL with Content-Type", async () => {
    const fetchImpl = createFetchMock(async () => ({
      status: 200,
      headers: { get: () => null },
      text: async () => JSON.stringify({ ok: true, data: { saved: true } }),
    }))

    const client = createApiClient({
      baseUrl: "https://plm.xuebao.chat/api/",
      fetchImpl,
    })

    const data = await client.request({
      path: "auth/login",
      method: "POST",
      body: { email: "a@example.com", password: "pw" },
      responseSchema: z.object({ saved: z.boolean() }),
    })

    expect(data.saved).toBe(true)
    expect(fetchImpl.mock.calls[0][0]).toBe("https://plm.xuebao.chat/api/auth/login")
    expect(fetchImpl.mock.calls[0][1].headers["Content-Type"]).toBe("application/json")
    expect(fetchImpl.mock.calls[0][1].body).toBe(
      JSON.stringify({ email: "a@example.com", password: "pw" }),
    )
  })
})
