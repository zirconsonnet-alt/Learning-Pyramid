import { useMemo, useState } from "react"
import { Pressable, StyleSheet, Text, View } from "react-native"

import { richContentHasMeaning, richContentToPlainText, richText } from "../api/richContent"
import type { ReviewRecommendationItem, ReviewRecommendationPage } from "../api/review"
import { AppButton } from "../components/AppButton"
import { AppTextInput } from "../components/AppTextInput"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { Screen } from "../components/Screen"
import { ui } from "../constants/ui"

type SessionAnswer = "remembered" | "forgotten"

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`
}

function formatDateTime(value: string | null) {
  if (!value) return "未复习"
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString()
}

function formatReviewResult(value: ReviewRecommendationItem["lastReviewResult"]) {
  if (value === "CAN_RECALL") return "会"
  if (value === "CANNOT_RECALL") return "不会"
  return "无记录"
}

export function ProjectReviewRecommendationsScreen({
  data,
  errorMessage,
  loading,
}: {
  data: ReviewRecommendationPage | null
  errorMessage?: string | null
  loading: boolean
}) {
  const items = data?.items ?? []
  const [activeId, setActiveId] = useState<string | null>(null)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [submitted, setSubmitted] = useState<Record<string, boolean>>({})
  const [sessionAnswers, setSessionAnswers] = useState<Record<string, SessionAnswer>>({})
  const activeItem = useMemo(
    () => items.find((item) => item.recallPoint.recallPointId === activeId) ?? items[0] ?? null,
    [activeId, items],
  )
  const answeredCount = items.filter((item) => sessionAnswers[item.recallPoint.recallPointId] !== undefined).length

  if (loading) {
    return (
      <Screen scroll={false}>
        <LoadingState label="加载复习推荐" />
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

  if (!activeItem) {
    return (
      <Screen>
        <Text style={styles.title}>复习推荐</Text>
        <EmptyState title="当前没有推荐复习" />
      </Screen>
    )
  }

  const activeRecallPointId = activeItem.recallPoint.recallPointId
  const draft = drafts[activeRecallPointId] ?? ""
  const hasSubmitted = submitted[activeRecallPointId] === true
  const canSubmit = richContentHasMeaning(richText(draft))
  const sessionAnswer = sessionAnswers[activeRecallPointId]

  function markAnswer(answer: SessionAnswer) {
    if (!hasSubmitted) return
    setSessionAnswers((current) => ({ ...current, [activeRecallPointId]: answer }))
    const currentIndex = items.findIndex((item) => item.recallPoint.recallPointId === activeRecallPointId)
    const nextItem = items[currentIndex + 1]
    if (nextItem) setActiveId(nextItem.recallPoint.recallPointId)
  }

  return (
    <Screen>
      <View style={styles.header}>
        <Text style={styles.title}>复习推荐</Text>
        <Text style={styles.meta}>
          已完成 {answeredCount} / {items.length}
        </Text>
      </View>

      <View style={styles.progressRow}>
        {items.map((item, index) => {
          const recallPointId = item.recallPoint.recallPointId
          const isActive = recallPointId === activeRecallPointId
          const answer = sessionAnswers[recallPointId]
          return (
            <Pressable
              accessibilityRole="button"
              key={recallPointId}
              onPress={() => setActiveId(recallPointId)}
              style={[styles.progressDot, isActive && styles.progressDotActive, answer && styles.progressDotDone]}
            >
              <Text style={[styles.progressText, (isActive || answer) && styles.progressTextActive]}>{index + 1}</Text>
            </Pressable>
          )
        })}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionKicker}>题面</Text>
        <Text style={styles.question}>{richContentToPlainText(activeItem.recallPoint.question) || "题面为空"}</Text>
        <Text style={styles.meta}>
          推荐指数 {activeItem.reviewRecommendationIndex.toFixed(1)} · 记忆强度 {formatPercent(activeItem.estimatedMemoryStrength)}
        </Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionKicker}>你的答案</Text>
        <AppTextInput
          editable={!hasSubmitted}
          multiline
          onChangeText={(text) => setDrafts((current) => ({ ...current, [activeRecallPointId]: text }))}
          placeholder="先写下自己的答案"
          style={styles.answerInput}
          value={draft}
        />
        {!hasSubmitted ? (
          <View style={styles.actionRow}>
            <AppButton
              disabled={!canSubmit}
              label="提交答案"
              onPress={() => setSubmitted((current) => ({ ...current, [activeRecallPointId]: true }))}
              style={styles.actionButton}
            />
            <AppButton
              label="跳过"
              onPress={() => setSubmitted((current) => ({ ...current, [activeRecallPointId]: true }))}
              style={styles.actionButton}
              variant="secondary"
            />
          </View>
        ) : null}
      </View>

      {hasSubmitted ? (
        <View style={styles.section}>
          <Text style={styles.sectionKicker}>答案</Text>
          <Text style={styles.answer}>{richContentToPlainText(activeItem.recallPoint.answer) || "答案为空"}</Text>
        </View>
      ) : null}

      <View style={styles.actionRow}>
        <AppButton
          disabled={!hasSubmitted}
          label={sessionAnswer === "remembered" ? "已记得" : "记得"}
          onPress={() => markAnswer("remembered")}
          style={styles.actionButton}
          variant={sessionAnswer === "remembered" ? "primary" : "secondary"}
        />
        <AppButton
          disabled={!hasSubmitted}
          label={sessionAnswer === "forgotten" ? "已不记得" : "不记得"}
          onPress={() => markAnswer("forgotten")}
          style={styles.actionButton}
          variant={sessionAnswer === "forgotten" ? "primary" : "secondary"}
        />
      </View>

      <View style={styles.stats}>
        <Stat label="最近复习" value={formatDateTime(activeItem.lastReviewedAt)} />
        <Stat label="最近结果" value={formatReviewResult(activeItem.lastReviewResult)} />
        <Stat label="复习次数" value={String(activeItem.reviewCount)} />
      </View>
    </Screen>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={styles.statValue}>{value}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  actionButton: { flex: 1 },
  actionRow: { flexDirection: "row", gap: ui.spacing.sm },
  answer: { color: ui.colors.text, fontSize: ui.type.body, lineHeight: 24 },
  answerInput: { minHeight: 116, textAlignVertical: "top" },
  header: { gap: ui.spacing.xs },
  meta: { color: ui.colors.textMuted, fontSize: ui.type.caption, lineHeight: 18 },
  progressDot: {
    alignItems: "center",
    borderColor: ui.colors.border,
    borderRadius: ui.radius.md,
    borderWidth: 1,
    height: 36,
    justifyContent: "center",
    width: 36,
  },
  progressDotActive: { backgroundColor: ui.colors.primary, borderColor: ui.colors.primary },
  progressDotDone: { backgroundColor: ui.colors.secondaryText, borderColor: ui.colors.secondaryText },
  progressRow: { flexDirection: "row", flexWrap: "wrap", gap: ui.spacing.sm },
  progressText: { color: ui.colors.textMuted, fontSize: ui.type.caption, fontWeight: "800" },
  progressTextActive: { color: ui.colors.primaryText },
  question: { color: ui.colors.text, fontSize: 17, fontWeight: "700", lineHeight: 25 },
  section: { gap: ui.spacing.sm },
  sectionKicker: { color: ui.colors.textMuted, fontSize: ui.type.caption, fontWeight: "800" },
  stat: { borderTopColor: ui.colors.borderSoft, borderTopWidth: 1, gap: ui.spacing.xs, paddingTop: ui.spacing.md },
  statLabel: { color: ui.colors.textMuted, fontSize: ui.type.caption },
  stats: { gap: ui.spacing.md },
  statValue: { color: ui.colors.text, fontSize: ui.type.control, fontWeight: "700" },
  title: { color: ui.colors.text, fontSize: ui.type.title, fontWeight: "800" },
})
