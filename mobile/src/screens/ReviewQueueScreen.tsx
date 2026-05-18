import { useEffect, useMemo, useState } from "react"
import { StyleSheet, Text, View } from "react-native"

import { richContentToPlainText } from "../api/richContent"
import type { RecallPoint } from "../api/review"
import { AppButton } from "../components/AppButton"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { Screen } from "../components/Screen"

type ReviewAnswer = "remembered" | "forgotten"

export function ReviewQueueScreen({
  committing,
  errorMessage,
  loading,
  onCommit,
  recallPointIds,
  recallPoints,
  reviewTaskId,
  submitted,
}: {
  committing: boolean
  errorMessage?: string | null
  loading: boolean
  onCommit: (params: { reviewTaskId: string; canRecall: number[] }) => void
  recallPointIds: string[]
  recallPoints: RecallPoint[]
  reviewTaskId: string | null
  submitted: boolean
}) {
  const [answers, setAnswers] = useState<Record<string, ReviewAnswer>>({})
  const [revealed, setRevealed] = useState<Record<string, boolean>>({})
  const [currentIndex, setCurrentIndex] = useState(0)
  const orderedRecallPoints = useMemo(() => {
    const byId = new Map(recallPoints.map((item) => [item.recallPointId, item]))
    return recallPointIds.map((id) => byId.get(id)).filter((item): item is RecallPoint => Boolean(item))
  }, [recallPointIds, recallPoints])

  useEffect(() => {
    setAnswers({})
    setRevealed({})
    setCurrentIndex(0)
  }, [reviewTaskId])

  if (loading) {
    return (
      <Screen scroll={false}>
        <LoadingState label="加载复习" />
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
  if (submitted) {
    return (
      <Screen>
        <EmptyState title="复习已提交" />
      </Screen>
    )
  }
  if (!reviewTaskId) {
    return (
      <Screen>
        <EmptyState title="暂无复习任务" />
      </Screen>
    )
  }
  if (recallPointIds.length === 0) {
    return (
      <Screen>
        <EmptyState title="复习任务没有可展示内容" />
      </Screen>
    )
  }
  if (orderedRecallPoints.length !== recallPointIds.length) {
    return (
      <Screen>
        <EmptyState title="复习内容加载不完整" />
      </Screen>
    )
  }

  const activeReviewTaskId = reviewTaskId
  const current = orderedRecallPoints[Math.min(currentIndex, orderedRecallPoints.length - 1)]
  const currentId = current.recallPointId
  const currentRevealed = Boolean(revealed[currentId])
  const answeredCount = recallPointIds.filter((id) => answers[id]).length
  const canSubmit = answeredCount === recallPointIds.length && !committing

  function answerCurrent(answer: ReviewAnswer) {
    setAnswers((currentAnswers) => ({ ...currentAnswers, [currentId]: answer }))
    setRevealed((currentRevealedMap) => ({ ...currentRevealedMap, [currentId]: true }))
    if (currentIndex < orderedRecallPoints.length - 1) setCurrentIndex(currentIndex + 1)
  }

  function submit() {
    if (!canSubmit) return
    onCommit({
      reviewTaskId: activeReviewTaskId,
      canRecall: recallPointIds.map((id) => (answers[id] === "remembered" ? 1 : 0)),
    })
  }

  return (
    <Screen>
      <View style={styles.header}>
        <Text style={styles.title}>复习</Text>
        <Text style={styles.meta}>
          {answeredCount} / {recallPointIds.length}
        </Text>
      </View>

      <View style={styles.panel}>
        <Text style={styles.progress}>第 {currentIndex + 1} 题</Text>
        <Text style={styles.question}>{richContentToPlainText(current.question) || "题面为空"}</Text>
        {currentRevealed ? (
          <Text style={styles.answer}>{richContentToPlainText(current.answer) || "答案为空"}</Text>
        ) : (
          <AppButton label="显示答案" onPress={() => setRevealed((currentMap) => ({ ...currentMap, [currentId]: true }))} />
        )}
      </View>

      <View style={styles.actions}>
        <AppButton disabled={!currentRevealed} label="记得" onPress={() => answerCurrent("remembered")} />
        <AppButton disabled={!currentRevealed} label="不记得" onPress={() => answerCurrent("forgotten")} />
      </View>

      <AppButton disabled={!canSubmit} label={committing ? "提交中" : "提交复习"} onPress={submit} />
    </Screen>
  )
}

const styles = StyleSheet.create({
  header: { gap: 4 },
  title: { color: "#0f172a", fontSize: 24, fontWeight: "700" },
  meta: { color: "#64748b", fontSize: 13 },
  panel: { gap: 12 },
  progress: { color: "#64748b", fontSize: 12 },
  question: { color: "#0f172a", fontSize: 18, fontWeight: "700", lineHeight: 26 },
  answer: { color: "#475569", fontSize: 15, lineHeight: 22 },
  actions: { flexDirection: "row", gap: 10 },
})
