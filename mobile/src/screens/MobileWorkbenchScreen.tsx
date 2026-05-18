import { useMemo, useState } from "react"
import { Pressable, StyleSheet, Text, View } from "react-native"

import type { LearningObjectNode } from "../api/learningObjects"
import type { PlaybackDescriptor } from "../api/media"
import { richContentToPlainText } from "../api/richContent"
import type { RecallPoint } from "../api/review"
import { AppButton } from "../components/AppButton"
import { AppTextInput } from "../components/AppTextInput"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { Screen } from "../components/Screen"
import type { MobileRecallDraft } from "../workbench/recallDrafts"
import { getIncompleteDraftReason } from "../workbench/recallDrafts"
import { LearningMediaPlayer } from "./LearningMediaPlayer"

export type MobileWorkbenchScreenProps = {
  activeNode: LearningObjectNode | null
  apiBaseUrl: string
  currentMs: number
  drafts: MobileRecallDraft[]
  errorMessage?: string | null
  loading: boolean
  nodes: LearningObjectNode[]
  onAddDraft: () => void
  onPlaybackTimeChange: (currentMs: number) => void
  onRemoveDraft: (localId: string) => void
  onSelectNode: (node: LearningObjectNode) => void
  onSubmitDrafts: () => void
  onUpdateDraft: (localId: string, patch: Partial<Pick<MobileRecallDraft, "answerText" | "questionText">>) => void
  openReviewQueue: () => void
  playback: PlaybackDescriptor | null
  playbackErrorMessage?: string | null
  playbackLoading: boolean
  recallPoints: RecallPoint[]
  recallPointsErrorMessage?: string | null
  recallPointsLoading: boolean
  reviewHeadId: string | null
  reviewQueueLoading: boolean
  sessionCookie?: string | null
  submitting: boolean
}

export function MobileWorkbenchScreen(props: MobileWorkbenchScreenProps) {
  const [directoryOpen, setDirectoryOpen] = useState(false)
  const leafNodes = useMemo(() => props.nodes.filter((node) => node.kind === "leaf"), [props.nodes])
  const activeLeaf = props.activeNode?.kind === "leaf" ? props.activeNode : null
  const firstIncompleteReason = props.drafts
    .map(getIncompleteDraftReason)
    .find((reason): reason is string => Boolean(reason))
  const canSubmit =
    props.drafts.length > 0 &&
    !props.reviewQueueLoading &&
    !props.reviewHeadId &&
    !firstIncompleteReason &&
    !props.submitting

  if (props.loading) {
    return (
      <Screen scroll={false}>
        <LoadingState label="加载工作台" />
      </Screen>
    )
  }

  if (props.errorMessage) {
    return (
      <Screen>
        <EmptyState title={props.errorMessage} />
      </Screen>
    )
  }

  if (!activeLeaf) {
    return (
      <Screen>
        <Text style={styles.title}>工作台</Text>
        <EmptyState title={leafNodes.length === 0 ? "暂无可学习内容" : "请选择学习内容"} />
        {leafNodes.length > 0 ? (
          <DirectoryList activeNodeId={null} nodes={props.nodes} onSelectNode={props.onSelectNode} />
        ) : null}
      </Screen>
    )
  }

  function submitDrafts() {
    if (!canSubmit) return
    props.onSubmitDrafts()
  }

  return (
    <Screen>
      <View style={styles.header}>
        <Text style={styles.title}>{activeLeaf.title}</Text>
        <Text style={styles.meta}>当前锚点 {formatMs(props.currentMs)}</Text>
      </View>

      <LearningMediaPlayer
        apiBaseUrl={props.apiBaseUrl}
        descriptor={props.playback}
        errorMessage={props.playbackErrorMessage}
        loading={props.playbackLoading}
        onPlaybackTimeChange={props.onPlaybackTimeChange}
        sessionCookie={props.sessionCookie}
        title={activeLeaf.title}
      />

      <View style={styles.actions}>
        <AppButton label="目录" onPress={() => setDirectoryOpen((current) => !current)} />
        <AppButton label="复习" onPress={props.openReviewQueue} />
      </View>

      {directoryOpen ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>目录</Text>
          <DirectoryList activeNodeId={activeLeaf.nodeId} nodes={props.nodes} onSelectNode={props.onSelectNode} />
        </View>
      ) : null}

      {props.reviewHeadId ? (
        <View style={styles.notice}>
          <Text style={styles.noticeText}>先完成复习</Text>
        </View>
      ) : null}

      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>复述点</Text>
          <AppButton label="记复述点" onPress={props.onAddDraft} />
        </View>
        {props.recallPointsLoading ? <LoadingState label="加载复述点" /> : null}
        {props.recallPointsErrorMessage ? <EmptyState title={props.recallPointsErrorMessage} /> : null}
        {!props.recallPointsLoading && !props.recallPointsErrorMessage && props.recallPoints.length === 0 ? (
          <EmptyState title="暂无复述点" />
        ) : null}
        {!props.recallPointsLoading && !props.recallPointsErrorMessage ? (
          <View style={styles.list}>
            {props.recallPoints.map((item) => (
              <View key={item.recallPointId} style={styles.row}>
                <Text style={styles.question}>{richContentToPlainText(item.question) || "题面为空"}</Text>
                <Text style={styles.answer}>{richContentToPlainText(item.answer) || "答案为空"}</Text>
              </View>
            ))}
          </View>
        ) : null}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>草稿</Text>
        {props.drafts.length === 0 ? <EmptyState title="暂无草稿" /> : null}
        <View style={styles.list}>
          {props.drafts.map((draft, index) => (
            <View key={draft.localId} style={styles.draft}>
              <View style={styles.draftHeader}>
                <Text style={styles.draftTitle}>草稿 {index + 1}</Text>
                <Pressable accessibilityRole="button" onPress={() => props.onRemoveDraft(draft.localId)}>
                  <Text style={styles.removeText}>删除</Text>
                </Pressable>
              </View>
              <Text style={styles.meta}>{draft.position}</Text>
              <AppTextInput
                multiline
                onChangeText={(text) => props.onUpdateDraft(draft.localId, { questionText: text })}
                placeholder="题面"
                value={draft.questionText}
              />
              <AppTextInput
                multiline
                onChangeText={(text) => props.onUpdateDraft(draft.localId, { answerText: text })}
                placeholder="答案"
                value={draft.answerText}
              />
            </View>
          ))}
        </View>
        {firstIncompleteReason ? <Text style={styles.meta}>{firstIncompleteReason}</Text> : null}
        <AppButton disabled={!canSubmit} label={props.submitting ? "提交中" : "提交学习"} onPress={submitDrafts} />
      </View>
    </Screen>
  )
}

function DirectoryList({
  activeNodeId,
  nodes,
  onSelectNode,
}: {
  activeNodeId: string | null
  nodes: LearningObjectNode[]
  onSelectNode: (node: LearningObjectNode) => void
}) {
  return (
    <View style={styles.list}>
      {nodes.map((node) => {
        const isLeaf = node.kind === "leaf"
        const active = node.nodeId === activeNodeId
        return (
          <Pressable
            disabled={!isLeaf}
            key={node.nodeId}
            onPress={() => onSelectNode(node)}
            style={[styles.row, !isLeaf && styles.containerRow, active && styles.activeRow]}
          >
            <Text style={[styles.rowTitle, active && styles.activeText]}>{node.title}</Text>
            <Text style={styles.meta}>{isLeaf ? "内容" : "目录"}</Text>
          </Pressable>
        )
      })}
    </View>
  )
}

function formatMs(ms: number) {
  const normalizedMs = Number.isFinite(ms) ? ms : 0
  const totalSeconds = Math.max(0, Math.floor(normalizedMs / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, "0")}`
}

const styles = StyleSheet.create({
  actions: { flexDirection: "row", gap: 10 },
  activeRow: { backgroundColor: "#e0f2fe" },
  activeText: { color: "#0369a1", fontWeight: "700" },
  answer: { color: "#475569", fontSize: 13, lineHeight: 19 },
  containerRow: { opacity: 0.62 },
  draft: { backgroundColor: "#ffffff", borderColor: "#e2e8f0", borderRadius: 8, borderWidth: 1, gap: 10, padding: 12 },
  draftHeader: { alignItems: "center", flexDirection: "row", justifyContent: "space-between" },
  draftTitle: { color: "#0f172a", fontSize: 15, fontWeight: "700" },
  header: { gap: 4 },
  list: { gap: 0 },
  meta: { color: "#64748b", fontSize: 12 },
  notice: { backgroundColor: "#fff7ed", borderColor: "#fed7aa", borderRadius: 8, borderWidth: 1, padding: 12 },
  noticeText: { color: "#9a3412", fontSize: 14, fontWeight: "700" },
  question: { color: "#0f172a", fontSize: 15 },
  removeText: { color: "#b91c1c", fontSize: 13, fontWeight: "700" },
  row: { borderBottomColor: "#e2e8f0", borderBottomWidth: 1, gap: 4, paddingHorizontal: 8, paddingVertical: 14 },
  rowTitle: { color: "#0f172a", fontSize: 16 },
  section: { gap: 10 },
  sectionHeader: { gap: 10 },
  sectionTitle: { color: "#0f172a", fontSize: 18, fontWeight: "700" },
  title: { color: "#0f172a", fontSize: 24, fontWeight: "700" },
})
