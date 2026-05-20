import { useState } from "react"
import { Pressable, StyleSheet, Text, View } from "react-native"

import type { StudyMaterial, StudyMaterialType } from "../api/subjects"
import { AppButton } from "../components/AppButton"
import { AppTextInput } from "../components/AppTextInput"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { Screen } from "../components/Screen"
import { ui } from "../constants/ui"

const MATERIAL_TYPES: StudyMaterialType[] = ["COURSE", "BOOK", "LOOSE_POINTS"]
const MATERIAL_TYPE_LABELS: Record<StudyMaterialType, string> = {
  BOOK: "书籍",
  COURSE: "课程",
  LOOSE_POINTS: "零散",
}

export function SubjectMaterialsScreen({
  loading,
  errorMessage,
  materials,
  openMaterial,
  openMine,
  openSubjectSettings,
  createMaterial,
  deleteMaterial,
}: {
  loading: boolean
  errorMessage?: string | null
  materials: StudyMaterial[]
  openMaterial: (material: StudyMaterial) => void
  openMine?: () => void
  openSubjectSettings?: () => void
  createMaterial?: (input: { materialType: StudyMaterialType; title: string }) => void
  deleteMaterial?: (materialId: string) => void
}) {
  const [draftTitle, setDraftTitle] = useState("")
  const [draftType, setDraftType] = useState<StudyMaterialType>("COURSE")
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
      </Screen>
    )
  }

  return (
    <Screen>
      <View style={styles.header}>
        <Text style={styles.title}>项目中心</Text>
        {openSubjectSettings ? (
          <AppButton label="学科设置" onPress={openSubjectSettings} style={styles.headerButton} variant="secondary" />
        ) : null}
        {openMine ? <AppButton label="我的" onPress={openMine} style={styles.headerButton} variant="secondary" /> : null}
      </View>
      {createMaterial ? (
        <View style={styles.form}>
          <View style={styles.typeRow}>
            {MATERIAL_TYPES.map((materialType) => (
              <AppButton
                key={materialType}
                label={MATERIAL_TYPE_LABELS[materialType]}
                onPress={() => setDraftType(materialType)}
                variant={draftType === materialType ? "primary" : "secondary"}
                style={styles.typeButton}
              />
            ))}
          </View>
          <AppTextInput placeholder="新项目名称" value={draftTitle} onChangeText={setDraftTitle} />
          <AppButton
            disabled={!draftTitle.trim()}
            label="新建项目"
            onPress={() => {
              const title = draftTitle.trim()
              if (!title) return
              createMaterial({ materialType: draftType, title })
              setDraftTitle("")
            }}
          />
        </View>
      ) : null}
      {materials.length === 0 ? <EmptyState title="暂无项目" /> : null}
      <View style={styles.list}>
        {materials.map((material) => {
          const deleting = deleteTargetId === material.materialId
          return (
            <View key={material.materialId} style={[styles.row, !material.scopedProjectId && styles.disabled]}>
              <Pressable disabled={!material.scopedProjectId} onPress={() => openMaterial(material)} style={styles.rowMain}>
                <View style={styles.rowText}>
                  <Text style={styles.rowTitle}>{material.title}</Text>
                  <Text style={styles.rowMeta}>{MATERIAL_TYPE_LABELS[material.materialType]}</Text>
                </View>
                <Text style={styles.chevron}>›</Text>
              </Pressable>
              {deleteMaterial ? (
                <View style={styles.rowActions}>
                  <AppButton
                    label={deleting ? "取消删除" : "删除"}
                    onPress={() => {
                      setDeleteTargetId(deleting ? null : material.materialId)
                      if (deleting) {
                        setDeleteConfirmations((current) => ({ ...current, [material.materialId]: "" }))
                      }
                    }}
                    style={styles.rowActionButton}
                    variant="secondary"
                  />
                </View>
              ) : null}
              {deleteMaterial && deleting ? (
                <View style={styles.deleteRow}>
                  <AppTextInput
                    placeholder="输入项目名称删除"
                    value={deleteConfirmations[material.materialId] ?? ""}
                    onChangeText={(text) =>
                      setDeleteConfirmations((current) => ({ ...current, [material.materialId]: text }))
                    }
                  />
                  <AppButton
                    disabled={(deleteConfirmations[material.materialId] ?? "").trim() !== material.title}
                    label="删除项目"
                    onPress={() => deleteMaterial(material.materialId)}
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
  chevron: { color: ui.colors.textSoft, fontSize: 28, lineHeight: 30 },
  deleteRow: { gap: ui.spacing.sm, paddingTop: ui.spacing.md },
  form: { gap: ui.spacing.md },
  header: { gap: ui.spacing.md },
  headerButton: { alignSelf: "stretch" },
  list: { gap: 0 },
  row: {
    borderBottomColor: ui.colors.borderSoft,
    borderBottomWidth: 1,
    gap: ui.spacing.xs,
    paddingVertical: ui.spacing.lg,
  },
  rowActionButton: { flex: 1 },
  rowActions: { flexDirection: "row", gap: ui.spacing.sm, paddingTop: ui.spacing.md },
  rowMain: {
    alignItems: "center",
    flexDirection: "row",
    gap: ui.spacing.lg,
    justifyContent: "space-between",
    minHeight: 44,
  },
  disabled: { opacity: 0.5 },
  rowText: { flex: 1, gap: ui.spacing.xs },
  rowTitle: { color: ui.colors.text, fontSize: 17, fontWeight: "700" },
  rowMeta: { color: ui.colors.textMuted, fontSize: ui.type.caption },
  title: { color: ui.colors.text, fontSize: ui.type.title, fontWeight: "800" },
  typeButton: { flex: 1 },
  typeRow: { flexDirection: "row", flexWrap: "wrap", gap: ui.spacing.sm },
})
