import { Pressable, StyleSheet, Text, View } from "react-native"

import type { LearningObjectNode } from "../api/learningObjects"
import { AppButton } from "../components/AppButton"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { Screen } from "../components/Screen"

export function ProjectScreen({
  loading,
  errorMessage,
  nodes,
  openNode,
  openReviewQueue,
}: {
  loading: boolean
  errorMessage?: string | null
  nodes: LearningObjectNode[]
  openNode: (node: LearningObjectNode) => void
  openReviewQueue?: () => void
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
        {openReviewQueue ? <AppButton label="复习" onPress={openReviewQueue} /> : null}
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
  header: { gap: 12 },
  title: { color: "#0f172a", fontSize: 24, fontWeight: "700" },
  list: { gap: 0 },
  row: { borderBottomColor: "#e2e8f0", borderBottomWidth: 1, gap: 4, paddingVertical: 14 },
  rowTitle: { color: "#0f172a", fontSize: 16 },
  rowMeta: { color: "#64748b", fontSize: 12 },
})
