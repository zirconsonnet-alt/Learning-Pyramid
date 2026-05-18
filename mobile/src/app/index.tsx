import { useState } from "react"
import { router } from "expo-router"
import { useQuery } from "@tanstack/react-query"

import { useLearningPyramidApi } from "../api/ApiProvider"
import { toErrorMessage } from "../api/errorMessage"
import { useAuth } from "../auth/AuthProvider"
import { LoadingState } from "../components/LoadingState"
import { Screen } from "../components/Screen"
import { LoginScreen } from "../screens/LoginScreen"
import { SubjectsScreen } from "../screens/SubjectsScreen"

export default function HomeScreen() {
  const api = useLearningPyramidApi()
  const auth = useAuth()
  const [signingIn, setSigningIn] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const subjectsQ = useQuery({
    queryKey: ["subjects"],
    queryFn: () => api.subjects.listSubjects(),
    enabled: auth.status === "signedIn",
  })

  if (auth.status === "loading") {
    return (
      <Screen scroll={false}>
        <LoadingState label="加载中" />
      </Screen>
    )
  }

  if (auth.status === "signedOut") {
    return (
      <LoginScreen
        errorMessage={errorMessage}
        loading={signingIn}
        signIn={(email, password) => {
          setErrorMessage(null)
          setSigningIn(true)
          void auth
            .signIn(email, password)
            .catch((error: unknown) => {
              setErrorMessage(error instanceof Error ? error.message : "登录失败")
            })
            .finally(() => setSigningIn(false))
        }}
      />
    )
  }

  return (
    <SubjectsScreen
      errorMessage={subjectsQ.isError ? toErrorMessage(subjectsQ.error, "学科加载失败") : null}
      loading={subjectsQ.isLoading}
      openSubject={(subjectId) => router.push({ pathname: "/subject/[subjectId]", params: { subjectId } })}
      signOut={() => void auth.signOut()}
      subjects={subjectsQ.data ?? []}
    />
  )
}
