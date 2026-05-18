import { z } from "zod"

import { ApiError, createApiClient, parseApiEnvelope } from "../src/api/http"

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
    const fetchImpl = jest.fn(async (_url: string, _init: { headers: Record<string, string> }) => ({
      status: 200,
      headers: {
        get: (name: string) =>
          name.toLowerCase() === "set-cookie" ? "plm_session=new; Path=/; HttpOnly" : null,
      },
      text: async () => JSON.stringify({ ok: true, data: { userId: "u1" } }),
    }))

    const client = createApiClient({
      baseUrl: "https://plm.xuebao.chat/api",
      fetchImpl: fetchImpl as never,
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
})
