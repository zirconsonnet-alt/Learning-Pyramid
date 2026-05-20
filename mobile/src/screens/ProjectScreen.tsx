import { Pressable, StyleSheet, Text, View } from "react-native"

import type { LearningObjectNode } from "../api/learningObjects"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { Screen } from "../components/Screen"
import { ui } from "../constants/ui"

export function ProjectScreen({
  loading,
  errorMessage,
  nodes,
  openNode,
}: {
  loading: boolean
  errorMessage?: string | null
  nodes: LearningObjectNode[]
  openNode: (node: LearningObjectNode) => void
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
      <View style={styles.header}>
        <Text style={styles.title}>学习对象</Text>
      </View>
      {nodes.length === 0 ? <EmptyState title="暂无学习对象" /> : null}
      <View style={styles.list}>
        {nodes.map((node) => (
          <Pressable key={node.nodeId} onPress={() => openNode(node)} style={styles.row}>
            <Text style={styles.rowTitle}>{node.title}</Text>
            <Text style={styles.rowMeta}>{node.kind === "container" ? "目录" : "内容"}</Text>
          </Pressable>
        ))}
      </View>
    </Screen>
  )
}

const styles = StyleSheet.create({
  header: { gap: ui.spacing.lg },
  list: { gap: 0 },
  row: {
    borderBottomColor: ui.colors.borderSoft,
    borderBottomWidth: 1,
    gap: ui.spacing.xs,
    paddingVertical: ui.spacing.lg,
  },
  rowTitle: { color: ui.colors.text, fontSize: 17, fontWeight: "700" },
  rowMeta: { color: ui.colors.textMuted, fontSize: ui.type.caption },
  title: { color: ui.colors.text, fontSize: ui.type.title, fontWeight: "800" },
})
