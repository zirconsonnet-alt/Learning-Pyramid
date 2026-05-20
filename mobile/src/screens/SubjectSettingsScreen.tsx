import { useEffect, useState } from "react"
import { StyleSheet, Text, View } from "react-native"

import type { Subject } from "../api/subjects"
import { AppButton } from "../components/AppButton"
import { AppTextInput } from "../components/AppTextInput"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { Screen } from "../components/Screen"
import { ui } from "../constants/ui"

export function SubjectSettingsScreen({
  loading,
  errorMessage,
  subject,
  saveTitle,
}: {
  loading: boolean
  errorMessage?: string | null
  subject: Subject | null
  saveTitle: (title: string) => void
}) {
  const [title, setTitle] = useState("")

  useEffect(() => {
    if (subject) setTitle(subject.title)
  }, [subject])

  if (loading) {
    return (
      <Screen scroll={false}>
        <LoadingState label="加载中" />
      </Screen>
    )
  }

  if (errorMessage) {
    return (
      <Screen>
        <EmptyState title={errorMessage} />
      </Screen>
    )
  }

  if (!subject) {
    return (
      <Screen>
        <EmptyState title="未找到学科" />
      </Screen>
    )
  }

  return (
    <Screen>
      <Text style={styles.title}>学科设置</Text>
      <View style={styles.form}>
        <AppTextInput placeholder="学科名称" value={title} onChangeText={setTitle} />
        <AppButton
          disabled={!title.trim() || title.trim() === subject.title}
          label="保存学科"
          onPress={() => saveTitle(title.trim())}
        />
      </View>
    </Screen>
  )
}

const styles = StyleSheet.create({
  form: { gap: ui.spacing.md },
  title: { color: ui.colors.text, fontSize: ui.type.title, fontWeight: "800" },
})
