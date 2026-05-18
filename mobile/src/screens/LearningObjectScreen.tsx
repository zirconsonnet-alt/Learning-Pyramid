import { StyleSheet, Text, View } from "react-native"

import type { LearningObjectNode } from "../api/learningObjects"
import type { PlaybackDescriptor } from "../api/media"
import { richContentToPlainText } from "../api/richContent"
import type { RecallPoint } from "../api/review"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { Screen } from "../components/Screen"
import { LearningMediaPlayer } from "./LearningMediaPlayer"

export function LearningObjectScreen({
  apiBaseUrl,
  node,
  nodeErrorMessage,
  nodeLoading,
  playback,
  playbackErrorMessage,
  playbackLoading,
  recallPoints,
  recallPointsErrorMessage,
  recallPointsLoading,
  sessionCookie,
}: {
  apiBaseUrl: string
  node: LearningObjectNode | null
  nodeErrorMessage?: string | null
  nodeLoading: boolean
  playback: PlaybackDescriptor | null
  playbackErrorMessage?: string | null
  playbackLoading: boolean
  recallPoints: RecallPoint[]
  recallPointsErrorMessage?: string | null
  recallPointsLoading: boolean
  sessionCookie?: string | null
}) {
  if (nodeLoading) {
    return (
      <Screen scroll={false}>
        <LoadingState label="加载对象" />
      </Screen>
    )
  }
  if (nodeErrorMessage) {
    return (
      <Screen>
        <EmptyState title={nodeErrorMessage} />
      </Screen>
    )
  }
  if (!node) {
    return (
      <Screen>
        <EmptyState title="未找到学习对象" />
      </Screen>
    )
  }

  return (
    <Screen>
      <View style={styles.header}>
        <Text style={styles.title}>{node.title}</Text>
        <Text style={styles.meta}>{node.kind === "leaf" ? "内容" : "目录"}</Text>
      </View>

      {node.kind === "leaf" ? (
        <LearningMediaPlayer
          apiBaseUrl={apiBaseUrl}
          descriptor={playback}
          errorMessage={playbackErrorMessage}
          loading={playbackLoading}
          sessionCookie={sessionCookie}
          title={node.title}
        />
      ) : (
        <EmptyState title="目录节点没有媒体" />
      )}

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>复述点</Text>
        {recallPointsLoading ? <LoadingState label="加载复述点" /> : null}
        {recallPointsErrorMessage ? <EmptyState title={recallPointsErrorMessage} /> : null}
        {!recallPointsLoading && !recallPointsErrorMessage && recallPoints.length === 0 ? (
          <EmptyState title="暂无复述点" />
        ) : null}
        {!recallPointsLoading && !recallPointsErrorMessage ? (
          <View style={styles.list}>
            {recallPoints.map((item) => (
              <View key={item.recallPointId} style={styles.row}>
                <Text style={styles.question}>{richContentToPlainText(item.question) || "题面为空"}</Text>
                <Text style={styles.answer}>{richContentToPlainText(item.answer) || "答案为空"}</Text>
              </View>
            ))}
          </View>
        ) : null}
      </View>
    </Screen>
  )
}

const styles = StyleSheet.create({
  header: { gap: 4 },
  title: { color: "#0f172a", fontSize: 24, fontWeight: "700" },
  meta: { color: "#64748b", fontSize: 12 },
  section: { gap: 10 },
  sectionTitle: { color: "#0f172a", fontSize: 18, fontWeight: "700" },
  list: { gap: 0 },
  row: { borderBottomColor: "#e2e8f0", borderBottomWidth: 1, gap: 6, paddingVertical: 14 },
  question: { color: "#0f172a", fontSize: 15 },
  answer: { color: "#475569", fontSize: 13, lineHeight: 19 },
})
