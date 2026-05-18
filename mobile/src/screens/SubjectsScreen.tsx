import { Pressable, StyleSheet, Text, View } from "react-native"

import type { Subject } from "../api/subjects"
import { AppButton } from "../components/AppButton"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { Screen } from "../components/Screen"

export function SubjectsScreen({
  loading,
  errorMessage,
  subjects,
  openSubject,
  signOut,
}: {
  loading: boolean
  errorMessage?: string | null
  subjects: Subject[]
  openSubject: (subjectId: string) => void
  signOut: () => void
}) {
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
        <AppButton label="退出" onPress={signOut} />
      </Screen>
    )
  }

  return (
    <Screen>
      <View style={styles.header}>
        <Text style={styles.title}>学科</Text>
        <AppButton label="退出" onPress={signOut} />
      </View>
      {subjects.length === 0 ? <EmptyState title="暂无学科" /> : null}
      <View style={styles.list}>
        {subjects.map((subject) => (
          <Pressable key={subject.subjectId} onPress={() => openSubject(subject.subjectId)} style={styles.row}>
            <Text style={styles.rowTitle}>{subject.title}</Text>
          </Pressable>
        ))}
      </View>
    </Screen>
  )
}

const styles = StyleSheet.create({
  header: { gap: 12 },
  title: { color: "#0f172a", fontSize: 24, fontWeight: "700" },
  list: { gap: 0 },
  row: { borderBottomColor: "#e2e8f0", borderBottomWidth: 1, paddingVertical: 14 },
  rowTitle: { color: "#0f172a", fontSize: 16 },
})
