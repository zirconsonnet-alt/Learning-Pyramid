import { useState } from "react"
import { Pressable, StyleSheet, Text, View } from "react-native"

import type { Subject } from "../api/subjects"
import { AppButton } from "../components/AppButton"
import { AppTextInput } from "../components/AppTextInput"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { Screen } from "../components/Screen"
import { ui } from "../constants/ui"

export function SubjectsScreen({
  loading,
  errorMessage,
  subjects,
  openSubject,
  openSubjectSettings,
  openGlobalSettings,
  openMine,
  createSubject,
  deleteSubject,
  signOut,
}: {
  loading: boolean
  errorMessage?: string | null
  subjects: Subject[]
  openSubject: (subjectId: string) => void
  openSubjectSettings?: (subjectId: string) => void
  openGlobalSettings?: () => void
  openMine?: () => void
  createSubject?: (title: string) => void
  deleteSubject?: (subjectId: string) => void
  signOut: () => void
}) {
  const [draftTitle, setDraftTitle] = useState("")
  const [deleteConfirmations, setDeleteConfirmations] = useState<Record<string, string>>({})
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null)

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
        <Text style={styles.title}>{subjects.length === 0 ? "开始学习" : "学科中心"}</Text>
        <View style={styles.actions}>
          {openGlobalSettings ? (
            <AppButton
              label="全局设置"
              onPress={openGlobalSettings}
              style={styles.actionButton}
              variant="secondary"
            />
          ) : null}
          {openMine ? <AppButton label="我的" onPress={openMine} style={styles.actionButton} variant="secondary" /> : null}
          <AppButton label="退出" onPress={signOut} style={styles.actionButton} variant="secondary" />
        </View>
      </View>
      {createSubject ? (
        <View style={styles.form}>
          <AppTextInput placeholder="新学科名称" value={draftTitle} onChangeText={setDraftTitle} />
          <AppButton
            disabled={!draftTitle.trim()}
            label="新建学科"
            onPress={() => {
              const title = draftTitle.trim()
              if (!title) return
              createSubject(title)
              setDraftTitle("")
            }}
          />
        </View>
      ) : null}
      {subjects.length === 0 ? <EmptyState title="暂无学科" /> : null}
      <View style={styles.list}>
        {subjects.map((subject) => {
          const deleting = deleteTargetId === subject.subjectId
          return (
            <View key={subject.subjectId} style={styles.row}>
              <Pressable onPress={() => openSubject(subject.subjectId)} style={styles.rowMain}>
                <View style={styles.rowText}>
                  <Text style={styles.rowTitle}>{subject.title}</Text>
                  <Text style={styles.rowMeta}>进入项目中心</Text>
                </View>
                <Text style={styles.chevron}>›</Text>
              </Pressable>
              <View style={styles.rowActions}>
                {openSubjectSettings ? (
                  <AppButton
                    label="设置"
                    onPress={() => openSubjectSettings(subject.subjectId)}
                    style={styles.rowActionButton}
                    variant="secondary"
                  />
                ) : null}
                {deleteSubject ? (
                  <AppButton
                    label={deleting ? "取消删除" : "删除"}
                    onPress={() => {
                      setDeleteTargetId(deleting ? null : subject.subjectId)
                      if (deleting) {
                        setDeleteConfirmations((current) => ({ ...current, [subject.subjectId]: "" }))
                      }
                    }}
                    style={styles.rowActionButton}
                    variant="secondary"
                  />
                ) : null}
              </View>
              {deleteSubject && deleting ? (
                <View style={styles.deleteRow}>
                  <AppTextInput
                    placeholder="输入学科名称删除"
                    value={deleteConfirmations[subject.subjectId] ?? ""}
                    onChangeText={(text) =>
                      setDeleteConfirmations((current) => ({ ...current, [subject.subjectId]: text }))
                    }
                  />
                  <AppButton
                    disabled={(deleteConfirmations[subject.subjectId] ?? "").trim() !== subject.title}
                    label="删除学科"
                    onPress={() => deleteSubject(subject.subjectId)}
                    variant="secondary"
                  />
                </View>
              ) : null}
            </View>
          )
        })}
      </View>
    </Screen>
  )
}

const styles = StyleSheet.create({
  actionButton: { flex: 1 },
  actions: { flexDirection: "row", gap: ui.spacing.md },
  chevron: { color: ui.colors.textSoft, fontSize: 28, lineHeight: 30 },
  deleteRow: { gap: ui.spacing.sm, paddingTop: ui.spacing.md },
  form: { gap: ui.spacing.md },
  header: { gap: ui.spacing.lg },
  list: { gap: 0 },
  row: { borderBottomColor: ui.colors.borderSoft, borderBottomWidth: 1, paddingVertical: ui.spacing.lg },
  rowActionButton: { flex: 1 },
  rowActions: { flexDirection: "row", gap: ui.spacing.sm, paddingTop: ui.spacing.md },
  rowMain: {
    alignItems: "center",
    flexDirection: "row",
    gap: ui.spacing.lg,
    justifyContent: "space-between",
    minHeight: 44,
  },
  rowMeta: { color: ui.colors.textMuted, fontSize: ui.type.caption },
  rowText: { flex: 1, gap: ui.spacing.xs },
  rowTitle: { color: ui.colors.text, fontSize: 17, fontWeight: "700" },
  title: { color: ui.colors.text, fontSize: ui.type.title, fontWeight: "800" },
})
