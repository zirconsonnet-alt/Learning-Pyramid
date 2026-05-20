import { useState } from "react"
import { StyleSheet, Text, View } from "react-native"

import { AppButton } from "../components/AppButton"
import { AppTextInput } from "../components/AppTextInput"
import { Screen } from "../components/Screen"
import { ui } from "../constants/ui"

export function LoginScreen({
  signIn,
  loading,
  errorMessage,
}: {
  signIn: (email: string, password: string) => void
  loading: boolean
  errorMessage: string | null
}) {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  return (
    <Screen>
      <View style={styles.header}>
        <Text style={styles.title}>LearningPyramid</Text>
      </View>
      <View style={styles.form}>
        <AppTextInput autoCapitalize="none" keyboardType="email-address" onChangeText={setEmail} placeholder="邮箱" value={email} />
        <AppTextInput onChangeText={setPassword} placeholder="密码" secureTextEntry value={password} />
        {errorMessage ? <Text style={styles.error}>{errorMessage}</Text> : null}
        <AppButton disabled={loading} label={loading ? "登录中" : "登录"} onPress={() => signIn(email.trim(), password)} />
      </View>
    </Screen>
  )
}

const styles = StyleSheet.create({
  header: { paddingTop: 28 },
  title: { color: ui.colors.text, fontSize: 28, fontWeight: "800" },
  form: { gap: ui.spacing.lg },
  error: { color: ui.colors.danger, fontSize: 14 },
})
