import { useState } from "react"
import { StyleSheet, Text, View } from "react-native"

import { useAuth } from "../auth/AuthProvider"
import { AppButton } from "../components/AppButton"
import { LoadingState } from "../components/LoadingState"
import { Screen } from "../components/Screen"
import { LoginScreen } from "../screens/LoginScreen"

export default function HomeScreen() {
  const auth = useAuth()
  const [signingIn, setSigningIn] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

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
    <Screen>
      <View style={styles.header}>
        <Text style={styles.title}>学习项目</Text>
        <Text style={styles.user}>{auth.user?.nickname || auth.user?.email}</Text>
      </View>
      <AppButton label="退出" onPress={() => void auth.signOut()} />
    </Screen>
  )
}

const styles = StyleSheet.create({
  header: { gap: 6 },
  title: { color: "#0f172a", fontSize: 24, fontWeight: "700" },
  user: { color: "#475569", fontSize: 14 },
})
