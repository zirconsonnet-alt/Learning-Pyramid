import { StyleSheet, Text, View } from "react-native"

import type { LearningObjectNode } from "../api/learningObjects"
import type { PlaybackDescriptor } from "../api/media"
import { richContentToPlainText } from "../api/richContent"
import type { RecallPoint } from "../api/review"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { Screen } from "../components/Screen"
import { ui } from "../constants/ui"
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
  header: { gap: ui.spacing.xs },
  title: { color: ui.colors.text, fontSize: ui.type.title, fontWeight: "800" },
  meta: { color: ui.colors.textMuted, fontSize: ui.type.caption },
  section: { gap: ui.spacing.md },
  sectionTitle: { color: ui.colors.text, fontSize: ui.type.sectionTitle, fontWeight: "800" },
  list: { gap: 0 },
  row: { borderBottomColor: ui.colors.borderSoft, borderBottomWidth: 1, gap: 6, paddingVertical: ui.spacing.xl },
  question: { color: ui.colors.text, fontSize: ui.type.control },
  answer: { color: ui.colors.textMuted, fontSize: 13, lineHeight: 19 },
})
