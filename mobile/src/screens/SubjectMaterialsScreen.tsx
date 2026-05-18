import { Pressable, StyleSheet, Text, View } from "react-native"

import type { StudyMaterial } from "../api/subjects"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { Screen } from "../components/Screen"

export function SubjectMaterialsScreen({
  loading,
  errorMessage,
  materials,
  openMaterial,
}: {
  loading: boolean
  errorMessage?: string | null
  materials: StudyMaterial[]
  openMaterial: (material: StudyMaterial) => void
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
      </Screen>
    )
  }

  return (
    <Screen>
      <Text style={styles.title}>材料</Text>
      {materials.length === 0 ? <EmptyState title="暂无材料" /> : null}
      <View style={styles.list}>
        {materials.map((material) => (
          <Pressable
            disabled={!material.scopedProjectId}
            key={material.materialId}
            onPress={() => openMaterial(material)}
            style={[styles.row, !material.scopedProjectId && styles.disabled]}
          >
            <Text style={styles.rowTitle}>{material.title}</Text>
            <Text style={styles.rowMeta}>{material.materialType}</Text>
          </Pressable>
        ))}
      </View>
    </Screen>
  )
}

const styles = StyleSheet.create({
  title: { color: "#0f172a", fontSize: 24, fontWeight: "700" },
  list: { gap: 0 },
  row: { borderBottomColor: "#e2e8f0", borderBottomWidth: 1, gap: 4, paddingVertical: 14 },
  disabled: { opacity: 0.5 },
  rowTitle: { color: "#0f172a", fontSize: 16 },
  rowMeta: { color: "#64748b", fontSize: 12 },
})
