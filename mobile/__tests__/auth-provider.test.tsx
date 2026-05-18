import { render, waitFor } from "@testing-library/react-native"
import { Text } from "react-native"

import { AuthProvider, useAuth } from "../src/auth/AuthProvider"

function Probe() {
  const auth = useAuth()
  return <Text>{auth.status}</Text>
}

describe("AuthProvider", () => {
  it("restores unauthenticated state when no session exists", async () => {
    const storage = {
      getSessionCookie: async () => null,
      setSessionCookie: async () => undefined,
      clearSessionCookie: async () => undefined,
    }
    const cookieStore = {
      getSessionCookie: () => null,
      setSessionCookie: () => undefined,
      clearSessionCookie: () => undefined,
    }
    const api = { auth: { me: async () => null, login: async () => undefined, logout: async () => null } }

    const screen = render(
      <AuthProvider api={api as never} cookieStore={cookieStore} storage={storage}>
        <Probe />
      </AuthProvider>,
    )

    await waitFor(() => expect(screen.getByText("signedOut")).toBeTruthy())
  })

  it("persists a session cookie after sign-in", async () => {
    let storedCookie: string | null = null
    let memoryCookie: string | null = "plm_session=new"
    const storage = {
      getSessionCookie: async () => null,
      setSessionCookie: async (cookie: string) => {
        storedCookie = cookie
      },
      clearSessionCookie: async () => {
        storedCookie = null
      },
    }
    const cookieStore = {
      getSessionCookie: () => memoryCookie,
      setSessionCookie: (cookie: string | null) => {
        memoryCookie = cookie
      },
      clearSessionCookie: () => {
        memoryCookie = null
      },
    }
    const api = {
      auth: {
        me: async () => null,
        login: async () => {
          memoryCookie = "plm_session=new"
          return {
            userId: "u1",
            email: "me@example.com",
            createdAt: "2026-05-18T00:00:00Z",
            publicUid: "p1",
            nickname: "Me",
            bio: "",
            avatarUrl: null,
            status: "ACTIVE",
            updatedAt: "2026-05-18T00:00:00Z",
            roles: [],
          }
        },
        logout: async () => null,
      },
    }

    function SignInProbe() {
      const auth = useAuth()
      return <Text onPress={() => void auth.signIn("me@example.com", "secret")}>{auth.status}</Text>
    }

    const screen = render(
      <AuthProvider api={api as never} cookieStore={cookieStore} storage={storage}>
        <SignInProbe />
      </AuthProvider>,
    )

    await waitFor(() => expect(screen.getByText("signedOut")).toBeTruthy())
    screen.getByText("signedOut").props.onPress()

    await waitFor(() => expect(screen.getByText("signedIn")).toBeTruthy())
    expect(storedCookie).toBe("plm_session=new")
  })
})
