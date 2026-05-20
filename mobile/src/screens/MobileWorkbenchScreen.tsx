import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Pressable, StyleSheet, Text, View } from "react-native"

import type { Layer } from "../api/layers"
import type { LearningObjectNode } from "../api/learningObjects"
import type { LearningTaskNode } from "../api/learningTaskNodes"
import type { PlaybackDescriptor } from "../api/media"
import type { ProjectType, RollUpStrategy } from "../api/projectConfig"
import { projectTypeRequiresLearningObjectTree, projectTypeUsesResolvableCourseAnchor } from "../api/projectConfig"
import { richContentToPlainText, richText } from "../api/richContent"
import type { RecallPoint } from "../api/review"
import type { InstanceSubtitleFile } from "../api/subtitles"
import { AppButton } from "../components/AppButton"
import { AppTextInput } from "../components/AppTextInput"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { Screen } from "../components/Screen"
import { ui } from "../constants/ui"
import type { MobileRecallDraft } from "../workbench/recallDrafts"
import { formatCourseAnchorPositionForInput, getIncompleteDraftReason } from "../workbench/recallDrafts"
import { LearningMediaPlayer } from "./LearningMediaPlayer"

export type ReviewCommitPayload = {
  reviewTaskId: string
  canRecall: number[]
  appendedInsights: Array<{ recallPointId: string; insight: ReturnType<typeof richText> }>
}

export type MobileWorkbenchScreenProps = {
  activeNode: LearningObjectNode | null
  aggregationQueuesByLayerIndex: Record<number, { currentNodeIds: string[] }>
  apiBaseUrl: string
  currentMs: number
  drafts: MobileRecallDraft[]
  errorMessage?: string | null
  layers: Layer[]
  layersErrorMessage?: string | null
  layersLoading: boolean
  learningTaskNodesById: Record<string, LearningTaskNode>
  learningTaskNodesLoading: boolean
  loading: boolean
  nodes: LearningObjectNode[]
  onAddDraft: () => void
  onAddDraftReference: (localId: string, recallPointId: string) => void
  onCommitReview: (payload: ReviewCommitPayload) => void
  onImportSubtitle: () => void
  onPlaybackTimeChange: (currentMs: number) => void
  onRemoveDraft: (localId: string) => void
  onRemoveDraftReference: (localId: string, recallPointId: string) => void
  onRollUp: (layerIndex: number) => void
  onSelectNode: (node: LearningObjectNode) => void
  onSubmitDrafts: () => void
  onTaskTitleChange: (title: string) => void
  onToggleThresholdRollUp: (layerIndex: number, enabled: boolean) => void
  onUpdateDraftPosition: (localId: string, position: string) => void
  onUpdateDraftText: (localId: string, field: "question" | "answer", text: string) => void
  playback: PlaybackDescriptor | null
  playbackErrorMessage?: string | null
  playbackLoading: boolean
  projectType: ProjectType
  referenceCandidates: RecallPoint[]
  reviewCommitting: boolean
  reviewErrorMessage?: string | null
  reviewLoading: boolean
  reviewRecallPointIds: string[]
  reviewRecallPoints: RecallPoint[]
  reviewTaskId: string | null
  rollUpErrorMessage?: string | null
  rollUpStrategy: RollUpStrategy
  rollingUp: boolean
  sessionCookie?: string | null
  subtitleErrorMessage?: string | null
  subtitleFile: InstanceSubtitleFile | null
  subtitleImporting: boolean
  subtitleLoading: boolean
  submitting: boolean
  taskTitle: string
  thresholdRollUpEnabledByLayerIndex: Record<number, boolean>
  thresholdRollUpUpdating: boolean
}

type CenterPanelMode = "main" | "rollup"
type PageAction = { label: string; onPress: () => void }
type ReviewAnswer = 0 | 1

export function MobileWorkbenchScreen(props: MobileWorkbenchScreenProps & { onPageActionsChange?: (actions: PageAction[]) => void }) {
  const [learningSwitcherOpen, setLearningSwitcherOpen] = useState(false)
  const [centerPanelMode, setCenterPanelMode] = useState<CenterPanelMode>("main")
  const onImportSubtitleRef = useRef(props.onImportSubtitle)
  const leafNodes = useMemo(() => props.nodes.filter((node) => node.kind === "leaf"), [props.nodes])
  const activeLeaf = props.activeNode?.kind === "leaf" ? props.activeNode : null
  const requiresLearningObjectTree = projectTypeRequiresLearningObjectTree(props.projectType)
  const importSubtitleLabel =
    props.subtitleImporting
      ? "导入中"
      : props.subtitleLoading
        ? "字幕载入"
        : props.subtitleFile?.found
          ? "替换字幕"
          : "导入字幕"

  useEffect(() => {
    onImportSubtitleRef.current = props.onImportSubtitle
  }, [props.onImportSubtitle])

  const toggleLearningSwitcher = useCallback(() => setLearningSwitcherOpen((current) => !current), [])
  const importSubtitle = useCallback(() => onImportSubtitleRef.current(), [])

  useEffect(() => {
    if (!props.onPageActionsChange) return

    const actions: PageAction[] = []
    if (props.projectType === "COURSE") {
      actions.push({ label: importSubtitleLabel, onPress: importSubtitle })
    }

    props.onPageActionsChange(actions)
  }, [
    importSubtitleLabel,
    importSubtitle,
    props.onPageActionsChange,
    props.projectType,
  ])

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

  if (requiresLearningObjectTree && !activeLeaf) {
    return (
      <Screen>
        <Text maxFontSizeMultiplier={1.1} style={styles.title}>工作台</Text>
        <EmptyState title={leafNodes.length === 0 ? "暂无可学习内容" : "请选择学习内容"} />
        {leafNodes.length > 0 ? (
          <DirectoryList activeNodeId={null} nodes={props.nodes} onSelectNode={props.onSelectNode} />
        ) : null}
      </Screen>
    )
  }

  const currentTitle = activeLeaf?.title ?? (props.projectType === "LOOSE_POINTS" ? "零散知识点" : "工作台")
  const workStatusDetail = props.reviewTaskId ? "待复习" : props.projectType === "LOOSE_POINTS" ? "可直接录入" : "正在学习"
  const submissionStatus = props.reviewTaskId ? "待复习" : props.submitting ? "提交中" : "未提交"

  return (
    <Screen>
      <View style={styles.header}>
        {requiresLearningObjectTree ? (
          <Pressable
            accessibilityLabel={`切换学习内容：${currentTitle}`}
            accessibilityRole="button"
            onPress={toggleLearningSwitcher}
            style={styles.titleButton}
          >
            <Text maxFontSizeMultiplier={1.1} numberOfLines={2} style={styles.title}>
              {currentTitle}
            </Text>
            <Text maxFontSizeMultiplier={1.1} style={styles.titleChevron}>
              {learningSwitcherOpen ? "⌃" : "⌄"}
            </Text>
          </Pressable>
        ) : (
          <Text maxFontSizeMultiplier={1.1} numberOfLines={2} style={styles.title}>
            {currentTitle}
          </Text>
        )}
        <View style={styles.headerMetaRow}>
          <Text maxFontSizeMultiplier={1.1} style={styles.headerMeta}>
            {props.projectType === "LOOSE_POINTS" ? workStatusDetail : `当前锚点 ${formatMs(props.currentMs)}`}
          </Text>
          <View style={styles.statusPill}>
            <Text maxFontSizeMultiplier={1.1} style={styles.statusPillText}>{submissionStatus}</Text>
          </View>
        </View>
      </View>

      {learningSwitcherOpen && requiresLearningObjectTree ? (
        <DirectoryList
          activeNodeId={activeLeaf?.nodeId ?? null}
          nodes={props.nodes}
          onSelectNode={(node) => {
            setLearningSwitcherOpen(false)
            props.onSelectNode(node)
          }}
        />
      ) : null}

      {projectTypeUsesResolvableCourseAnchor(props.projectType) ? (
        <LearningMediaPlayer
          apiBaseUrl={props.apiBaseUrl}
          currentMs={props.currentMs}
          descriptor={props.playback}
          errorMessage={props.playbackErrorMessage}
          loading={props.playbackLoading}
          onPlaybackTimeChange={props.onPlaybackTimeChange}
          sessionCookie={props.sessionCookie}
          subtitleFile={props.subtitleFile}
          title={currentTitle}
        />
      ) : null}

      <StudyStatsPanel
        durationMs={props.playback?.durationMs ?? null}
        usesResolvableCourseAnchor={projectTypeUsesResolvableCourseAnchor(props.projectType)}
      />

      <View style={styles.primaryActions}>
        {props.projectType === "COURSE" ? (
          <>
            <QuickAction
              disabled={props.subtitleLoading || props.subtitleImporting}
              label={importSubtitleLabel}
              onPress={importSubtitle}
            />
            {props.subtitleErrorMessage ? (
              <Text maxFontSizeMultiplier={1.1} style={styles.meta}>
                {props.subtitleErrorMessage}
              </Text>
            ) : null}
          </>
        ) : null}
      </View>

      <View style={styles.segment}>
        <SegmentButton
          active={centerPanelMode === "main"}
          label={props.reviewTaskId ? "复习任务" : "复述点录入"}
          onPress={() => setCenterPanelMode("main")}
        />
        <SegmentButton active={centerPanelMode === "rollup"} label="层推进与学习任务" onPress={() => setCenterPanelMode("rollup")} />
      </View>

      {centerPanelMode === "main" ? (
        props.reviewTaskId ? (
          <ReviewPane
            committing={props.reviewCommitting}
            errorMessage={props.reviewErrorMessage}
            loading={props.reviewLoading}
            onCommitReview={props.onCommitReview}
            recallPointIds={props.reviewRecallPointIds}
            recallPoints={props.reviewRecallPoints}
            reviewTaskId={props.reviewTaskId}
          />
        ) : (
          <ComposePane
            drafts={props.drafts}
            onAddDraft={props.onAddDraft}
            onAddDraftReference={props.onAddDraftReference}
            onRemoveDraft={props.onRemoveDraft}
            onRemoveDraftReference={props.onRemoveDraftReference}
            onSubmitDrafts={props.onSubmitDrafts}
            onTaskTitleChange={props.onTaskTitleChange}
            onUpdateDraftPosition={props.onUpdateDraftPosition}
            onUpdateDraftText={props.onUpdateDraftText}
            projectType={props.projectType}
            referenceCandidates={props.referenceCandidates}
            submitting={props.submitting}
            taskTitle={props.taskTitle}
          />
        )
      ) : (
        <RollupPane
          aggregationQueuesByLayerIndex={props.aggregationQueuesByLayerIndex}
          errorMessage={props.layersErrorMessage}
          layers={props.layers}
          learningTaskNodesById={props.learningTaskNodesById}
          learningTaskNodesLoading={props.learningTaskNodesLoading}
          loading={props.layersLoading}
          onRollUp={props.onRollUp}
          onToggleThresholdRollUp={props.onToggleThresholdRollUp}
          rollUpErrorMessage={props.rollUpErrorMessage}
          rollUpStrategy={props.rollUpStrategy}
          rollingUp={props.rollingUp}
          thresholdRollUpEnabledByLayerIndex={props.thresholdRollUpEnabledByLayerIndex}
          thresholdRollUpUpdating={props.thresholdRollUpUpdating}
        />
      )}
    </Screen>
  )
}

function QuickAction({
  disabled = false,
  label,
  onPress,
}: {
  disabled?: boolean
  label: string
  onPress: () => void
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={[styles.quickAction, disabled && styles.disabled]}
    >
      <Text maxFontSizeMultiplier={1.1} style={styles.quickActionText}>{label}</Text>
    </Pressable>
  )
}

function SegmentButton({ active, label, onPress }: { active: boolean; label: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={[styles.segmentButton, active && styles.segmentButtonActive]}>
      <Text maxFontSizeMultiplier={1.1} style={[styles.segmentText, active && styles.segmentTextActive]}>{label}</Text>
    </Pressable>
  )
}

function StudyStatsPanel({
  durationMs,
  usesResolvableCourseAnchor,
}: {
  durationMs: number | null
  usesResolvableCourseAnchor: boolean
}) {
  const totalMs = typeof durationMs === "number" && durationMs > 0 ? durationMs : 0
  const watchedMs = 0
  const progressPercent = totalMs > 0 ? Math.round((watchedMs / totalMs) * 100) : 0

  return (
    <View style={styles.statsPanel}>
      <View style={styles.statsHeader}>
        <View style={styles.statsTitleRow}>
          <View style={styles.statsIcon}>
            <Text maxFontSizeMultiplier={1.1} style={styles.statsIconText}>↗</Text>
          </View>
          <Text maxFontSizeMultiplier={1.1} style={styles.sectionTitle}>学习统计</Text>
        </View>
        {usesResolvableCourseAnchor ? (
          <View style={styles.coverageSummary}>
            <View style={styles.inlineLabelRow}>
              <Text maxFontSizeMultiplier={1.1} style={styles.statLabel}>观看覆盖</Text>
              <InfoBadge />
            </View>
            <Text maxFontSizeMultiplier={1.1} style={styles.statValue}>
              {formatDurationCompact(watchedMs)} / {formatDurationCompact(totalMs)}
            </Text>
            <Text maxFontSizeMultiplier={1.1} style={styles.statPercent}>{progressPercent}%</Text>
          </View>
        ) : null}
      </View>

      {usesResolvableCourseAnchor ? (
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: `${progressPercent}%` }]} />
        </View>
      ) : null}

      <View style={styles.statsDetailCard}>
        <View style={styles.remainingBlock}>
          <View style={styles.inlineLabelRow}>
            <Text maxFontSizeMultiplier={1.1} style={styles.statLabel}>预计剩余学习时长</Text>
            <InfoBadge />
          </View>
          <Text maxFontSizeMultiplier={1.1} style={styles.remainingValue}>继续学习后生成</Text>
        </View>
        <View style={styles.statsDivider} />
        <View style={styles.distributionBlock}>
          <View style={styles.inlineLabelRow}>
            <Text maxFontSizeMultiplier={1.1} style={styles.statLabel}>今日学习行为分布</Text>
            <InfoBadge />
          </View>
          <View style={styles.reviewChartRow}>
            <View accessibilityLabel="今日学习行为分布统计图" accessibilityRole="image" style={styles.reviewDonut}>
              <View style={styles.reviewDonutHole}>
                <Text maxFontSizeMultiplier={1.1} style={styles.donutValue}>0m</Text>
                <Text maxFontSizeMultiplier={1.1} style={styles.donutLabel}>总计</Text>
              </View>
            </View>
            <View style={styles.reviewLegend}>
              <LegendRow color="#5067f6" label="驻留时长" value={formatDurationCompact(watchedMs)} />
              <LegendRow color="#64c7a5" label="学习时长" value="0m" />
              <LegendRow color="#ffad54" label="走神时长" value="0m" />
            </View>
          </View>
          <Text maxFontSizeMultiplier={1.1} style={styles.meta}>暂无足够数据生成学习分解</Text>
        </View>
      </View>
    </View>
  )
}

function InfoBadge() {
  return (
    <View style={styles.infoBadge}>
      <Text maxFontSizeMultiplier={1.1} style={styles.infoBadgeText}>i</Text>
    </View>
  )
}

function LegendRow({ color, label, value }: { color: string; label: string; value: string }) {
  return (
    <View style={styles.legendRow}>
      <View style={styles.legendLabel}>
        <View style={[styles.legendDot, { backgroundColor: color }]} />
        <Text maxFontSizeMultiplier={1.1} style={styles.meta}>{label}</Text>
      </View>
      <Text maxFontSizeMultiplier={1.1} style={styles.meta}>{value}</Text>
    </View>
  )
}

function ComposePane({
  drafts,
  onAddDraft,
  onAddDraftReference,
  onRemoveDraft,
  onRemoveDraftReference,
  onSubmitDrafts,
  onTaskTitleChange,
  onUpdateDraftPosition,
  onUpdateDraftText,
  projectType,
  referenceCandidates,
  submitting,
  taskTitle,
}: {
  drafts: MobileRecallDraft[]
  onAddDraft: () => void
  onAddDraftReference: (localId: string, recallPointId: string) => void
  onRemoveDraft: (localId: string) => void
  onRemoveDraftReference: (localId: string, recallPointId: string) => void
  onSubmitDrafts: () => void
  onTaskTitleChange: (title: string) => void
  onUpdateDraftPosition: (localId: string, position: string) => void
  onUpdateDraftText: (localId: string, field: "question" | "answer", text: string) => void
  projectType: ProjectType
  referenceCandidates: RecallPoint[]
  submitting: boolean
  taskTitle: string
}) {
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null)
  const activeDraftId = drafts.some((draft) => draft.localId === selectedDraftId)
    ? selectedDraftId
    : drafts[0]?.localId ?? null
  const activeDraftIndex = activeDraftId ? drafts.findIndex((draft) => draft.localId === activeDraftId) : -1
  const activeDraft = activeDraftIndex >= 0 ? drafts[activeDraftIndex] : null
  const firstIncompleteReason = drafts.map((draft) => getIncompleteDraftReason(draft, projectType)).find(Boolean)
  const canSubmit = drafts.length > 0 && !firstIncompleteReason && taskTitle.trim().length > 0 && !submitting
  const submitHint = drafts.length === 0 ? "添加至少 1 个复述点后可提交" : firstIncompleteReason

  useEffect(() => {
    if (activeDraftId !== selectedDraftId) setSelectedDraftId(activeDraftId)
  }, [activeDraftId, selectedDraftId])

  function selectDraftAt(index: number) {
    const nextDraft = drafts[index]
    if (nextDraft) setSelectedDraftId(nextDraft.localId)
  }

  const submitBlock = (
    <View style={styles.submitBlock}>
      <Text maxFontSizeMultiplier={1.1} style={styles.inputLabel}>任务标题</Text>
      <AppTextInput onChangeText={onTaskTitleChange} placeholder="任务标题" value={taskTitle} />
      <AppButton
        disabled={!canSubmit}
        label={submitting ? "提交中" : "提交学习"}
        onPress={onSubmitDrafts}
        style={[styles.submitButton, !canSubmit && styles.submitButtonDisabled]}
      />
      {submitHint ? <Text maxFontSizeMultiplier={1.1} style={styles.submitHint}>{submitHint}</Text> : null}
    </View>
  )

  if (drafts.length === 0) {
    return (
      <View style={styles.section}>
        <RecallEmptyPanel onAddDraft={onAddDraft} />
        {submitBlock}
      </View>
    )
  }

  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Text maxFontSizeMultiplier={1.1} style={styles.sectionTitle}>复述点录入</Text>
        <View style={styles.titleActions}>
          <AppButton label="添加" onPress={onAddDraft} style={styles.compactButton} />
          {activeDraft ? (
            <AppButton
              label="删除"
              onPress={() => onRemoveDraft(activeDraft.localId)}
              style={styles.compactButton}
              variant="secondary"
            />
          ) : null}
        </View>
      </View>

      {drafts.length > 0 ? (
        <View style={styles.progressRow}>
          {drafts.map((draft, index) => {
            const completed = getIncompleteDraftReason(draft, projectType) === null
            const active = draft.localId === activeDraftId
            return (
              <Pressable
                accessibilityRole="button"
                key={draft.localId}
                onPress={() => setSelectedDraftId(draft.localId)}
                style={[styles.progressButton, completed && styles.progressButtonDone, active && styles.progressButtonActive]}
              >
                <Text maxFontSizeMultiplier={1.1} style={[styles.progressText, completed && styles.progressTextDone]}>{index + 1}</Text>
              </Pressable>
            )
          })}
        </View>
      ) : null}

      {activeDraft ? (
        <View style={styles.panel}>
          <View style={styles.cardNav}>
            <AppButton
              disabled={activeDraftIndex <= 0}
              label="上一张"
              onPress={() => selectDraftAt(activeDraftIndex - 1)}
              style={styles.compactButton}
              variant="secondary"
            />
            <Text maxFontSizeMultiplier={1.1} style={styles.meta}>
              {activeDraftIndex + 1} / {drafts.length}
            </Text>
            <AppButton
              disabled={activeDraftIndex >= drafts.length - 1}
              label="下一张"
              onPress={() => selectDraftAt(activeDraftIndex + 1)}
              style={styles.compactButton}
              variant="secondary"
            />
          </View>

          {projectType !== "LOOSE_POINTS" ? (
            <AppTextInput
              onChangeText={(text) => onUpdateDraftPosition(activeDraft.localId, text)}
              placeholder={projectTypeUsesResolvableCourseAnchor(projectType) ? "例如：17:57 / 1:02:03 / t=1077104" : "例如：第 45 页 例 2"}
              value={
                projectTypeUsesResolvableCourseAnchor(projectType)
                  ? formatCourseAnchorPositionForInput(activeDraft.position)
                  : activeDraft.position ?? ""
              }
            />
          ) : null}

          <AppTextInput
            multiline
            onChangeText={(text) => onUpdateDraftText(activeDraft.localId, "question", text)}
            placeholder="问题/提示语"
            value={richContentToPlainText(activeDraft.question)}
          />
          <AppTextInput
            multiline
            onChangeText={(text) => onUpdateDraftText(activeDraft.localId, "answer", text)}
            placeholder="答案/复述内容"
            value={richContentToPlainText(activeDraft.answer)}
          />

          <View style={styles.referenceBox}>
            <Text maxFontSizeMultiplier={1.1} style={styles.meta}>答案引用</Text>
            {activeDraft.references.map((referenceId) => (
              <Pressable
                accessibilityRole="button"
                key={referenceId}
                onPress={() => onRemoveDraftReference(activeDraft.localId, referenceId)}
                style={styles.referenceButton}
              >
                <Text maxFontSizeMultiplier={1.1} style={styles.referenceText}>移除引用 {referenceId}</Text>
              </Pressable>
            ))}
            {referenceCandidates
              .filter((candidate) => !activeDraft.references.includes(candidate.recallPointId))
              .slice(0, 6)
              .map((candidate) => (
                <Pressable
                  accessibilityRole="button"
                  key={candidate.recallPointId}
                  onPress={() => onAddDraftReference(activeDraft.localId, candidate.recallPointId)}
                  style={styles.referenceButton}
                >
                  <Text maxFontSizeMultiplier={1.1} style={styles.referenceText}>引用候选</Text>
                </Pressable>
              ))}
          </View>
        </View>
      ) : null}

      {submitBlock}
    </View>
  )
}

function RecallEmptyPanel({ onAddDraft }: { onAddDraft: () => void }) {
  return (
    <View style={styles.emptyRecallPanel}>
      <View style={styles.emptyIllustration} pointerEvents="none">
        <View style={styles.emptyBubble} />
        <View style={styles.emptyClipboard}>
          <View style={styles.emptyClip} />
          <View style={styles.emptyLineWide} />
          <View style={styles.emptyLine} />
          <View style={styles.emptyLineShort} />
        </View>
        <View style={styles.emptyPen} />
      </View>
      <View style={styles.emptyCopy}>
        <Text maxFontSizeMultiplier={1.1} style={styles.emptyTitle}>还没有复述点</Text>
        <Text maxFontSizeMultiplier={1.1} style={styles.emptyBody}>
          播放视频时，遇到关键概念、易错点或需要回忆的内容，可以添加复述点。
        </Text>
        <AppButton label="+ 添加第一个复述点" onPress={onAddDraft} style={styles.emptyActionButton} />
      </View>
    </View>
  )
}

function ReviewPane({
  committing,
  errorMessage,
  loading,
  onCommitReview,
  recallPointIds,
  recallPoints,
  reviewTaskId,
}: {
  committing: boolean
  errorMessage?: string | null
  loading: boolean
  onCommitReview: (payload: ReviewCommitPayload) => void
  recallPointIds: string[]
  recallPoints: RecallPoint[]
  reviewTaskId: string
}) {
  const [activeIndex, setActiveIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<string, ReviewAnswer>>({})
  const [revealed, setRevealed] = useState<Record<string, boolean>>({})
  const [writtenAnswers, setWrittenAnswers] = useState<Record<string, string>>({})
  const [insights, setInsights] = useState<Record<string, string>>({})
  const orderedRecallPoints = useMemo(() => {
    const byId = new Map(recallPoints.map((item) => [item.recallPointId, item]))
    return recallPointIds.map((id) => byId.get(id)).filter((item): item is RecallPoint => Boolean(item))
  }, [recallPointIds, recallPoints])

  useEffect(() => {
    setActiveIndex(0)
    setAnswers({})
    setRevealed({})
    setWrittenAnswers({})
    setInsights({})
  }, [reviewTaskId])

  if (loading) return <LoadingState label="加载复习任务" />
  if (errorMessage) return <EmptyState title={errorMessage} />
  if (recallPointIds.length === 0) return <EmptyState title="复习任务没有可展示内容" />
  if (orderedRecallPoints.length !== recallPointIds.length) return <EmptyState title="复习内容加载不完整" />

  const current = orderedRecallPoints[Math.min(activeIndex, orderedRecallPoints.length - 1)]
  const currentId = current.recallPointId
  const answerSubmitted = revealed[currentId] === true
  const answeredCount = recallPointIds.filter((id) => answers[id] !== undefined).length
  const canSubmit = answeredCount === recallPointIds.length && !committing

  function choose(value: ReviewAnswer) {
    if (!answerSubmitted) return
    setAnswers((currentAnswers) => ({ ...currentAnswers, [currentId]: value }))
    if (activeIndex < orderedRecallPoints.length - 1) setActiveIndex(activeIndex + 1)
  }

  function submitReview() {
    if (!canSubmit) return
    onCommitReview({
      reviewTaskId,
      canRecall: recallPointIds.map((id) => answers[id] ?? 0),
      appendedInsights: recallPointIds.flatMap((id) => {
        const text = insights[id]?.trim()
        return text ? [{ recallPointId: id, insight: richText(text) }] : []
      }),
    })
  }

  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Text maxFontSizeMultiplier={1.1} style={styles.sectionTitle}>复习任务</Text>
        <Text maxFontSizeMultiplier={1.1} style={styles.meta}>
          {answeredCount} / {recallPointIds.length}
        </Text>
      </View>
      <View style={styles.progressRow}>
        {recallPointIds.map((id, index) => (
          <Pressable
            accessibilityRole="button"
            key={id}
            onPress={() => setActiveIndex(index)}
            style={[styles.progressButton, answers[id] !== undefined && styles.progressButtonDone, index === activeIndex && styles.progressButtonActive]}
          >
            <Text maxFontSizeMultiplier={1.1} style={[styles.progressText, answers[id] !== undefined && styles.progressTextDone]}>{index + 1}</Text>
          </Pressable>
        ))}
      </View>
      <View style={styles.panel}>
        <Text maxFontSizeMultiplier={1.1} style={styles.meta}>第 {activeIndex + 1} 题</Text>
        <Text maxFontSizeMultiplier={1.1} style={styles.question}>{richContentToPlainText(current.question) || "题面为空"}</Text>
        <AppTextInput
          editable={!answerSubmitted}
          multiline
          onChangeText={(text) => setWrittenAnswers((currentAnswers) => ({ ...currentAnswers, [currentId]: text }))}
          placeholder="先写自己的答案"
          value={writtenAnswers[currentId] ?? ""}
        />
        {!answerSubmitted ? (
          <View style={styles.actions}>
            <AppButton
              disabled={!writtenAnswers[currentId]?.trim()}
              label="提交答案"
              onPress={() => setRevealed((currentRevealed) => ({ ...currentRevealed, [currentId]: true }))}
            />
            <AppButton
              label="跳过"
              onPress={() => setRevealed((currentRevealed) => ({ ...currentRevealed, [currentId]: true }))}
              variant="secondary"
            />
          </View>
        ) : null}
        {answerSubmitted ? (
          <>
            <Text maxFontSizeMultiplier={1.1} style={styles.answer}>{richContentToPlainText(current.answer) || "答案为空"}</Text>
            <AppTextInput
              multiline
              onChangeText={(text) => setInsights((currentInsights) => ({ ...currentInsights, [currentId]: text }))}
              placeholder="追加理解"
              value={insights[currentId] ?? ""}
            />
            <View style={styles.actions}>
              <AppButton label="记得" onPress={() => choose(1)} />
              <AppButton label="不记得" onPress={() => choose(0)} variant="secondary" />
            </View>
          </>
        ) : null}
      </View>
      <AppButton disabled={!canSubmit} label={committing ? "提交中" : "提交本轮复习"} onPress={submitReview} />
    </View>
  )
}

function RollupPane({
  aggregationQueuesByLayerIndex,
  errorMessage,
  layers,
  learningTaskNodesById,
  learningTaskNodesLoading,
  loading,
  onRollUp,
  onToggleThresholdRollUp,
  rollUpErrorMessage,
  rollUpStrategy,
  rollingUp,
  thresholdRollUpEnabledByLayerIndex,
  thresholdRollUpUpdating,
}: {
  aggregationQueuesByLayerIndex: Record<number, { currentNodeIds: string[] }>
  errorMessage?: string | null
  layers: Layer[]
  learningTaskNodesById: Record<string, LearningTaskNode>
  learningTaskNodesLoading: boolean
  loading: boolean
  onRollUp: (layerIndex: number) => void
  onToggleThresholdRollUp: (layerIndex: number, enabled: boolean) => void
  rollUpErrorMessage?: string | null
  rollUpStrategy: RollUpStrategy
  rollingUp: boolean
  thresholdRollUpEnabledByLayerIndex: Record<number, boolean>
  thresholdRollUpUpdating: boolean
}) {
  const [selectedLayerIndex, setSelectedLayerIndex] = useState<number | null>(null)
  const effectiveLayer =
    (selectedLayerIndex !== null ? layers.find((layer) => layer.layerIndex === selectedLayerIndex) : null) ?? layers[0] ?? null
  const currentQueue = effectiveLayer ? aggregationQueuesByLayerIndex[effectiveLayer.layerIndex]?.currentNodeIds ?? [] : []
  const thresholdEnabled = effectiveLayer ? thresholdRollUpEnabledByLayerIndex[effectiveLayer.layerIndex] ?? true : true
  const isThresholdStrategy = rollUpStrategy === "THRESHOLD_AUTO"
  const isIsomorphicStrategy = rollUpStrategy === "LEARNING_OBJECT_ISOMORPHIC"
  const actionLayerIndex = effectiveLayer?.layerIndex ?? 0

  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Text maxFontSizeMultiplier={1.1} style={styles.sectionTitle}>层推进与学习任务</Text>
        <View style={styles.actions}>
          {isThresholdStrategy && effectiveLayer ? (
            <AppButton
              disabled={thresholdRollUpUpdating}
              label={thresholdEnabled ? "禁止阈值上推" : "恢复阈值上推"}
              onPress={() => onToggleThresholdRollUp(effectiveLayer.layerIndex, !thresholdEnabled)}
              variant="secondary"
            />
          ) : null}
          <AppButton
            disabled={rollingUp || (!isIsomorphicStrategy && (!effectiveLayer || currentQueue.length === 0))}
            label={rollingUp ? "处理中" : isIsomorphicStrategy ? "重新扫描对象树推进" : "上推"}
            onPress={() => onRollUp(actionLayerIndex)}
          />
        </View>
      </View>
      {loading ? <LoadingState label="加载层级任务" /> : null}
      {errorMessage ? <EmptyState title={errorMessage} /> : null}
      {!loading && !errorMessage && layers.length === 0 ? <EmptyState title="当前还没有层配置" /> : null}
      {layers.length > 0 ? (
        <View style={styles.progressRow}>
          {layers.map((layer) => (
            <Pressable
              accessibilityRole="button"
              key={layer.layerId}
              onPress={() => setSelectedLayerIndex(layer.layerIndex)}
              style={[styles.layerButton, layer.layerIndex === effectiveLayer?.layerIndex && styles.progressButtonActive]}
            >
              <Text maxFontSizeMultiplier={1.1} style={styles.rowTitle}>L{layer.layerIndex}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
      {effectiveLayer ? (
        <View style={styles.panel}>
          <Text maxFontSizeMultiplier={1.1} style={styles.meta}>
            {isIsomorphicStrategy
              ? "当前使用学习对象树同构上推。"
              : isThresholdStrategy
                ? thresholdEnabled
                  ? `L${effectiveLayer.layerIndex} 已开启阈值自动上推。`
                  : `L${effectiveLayer.layerIndex} 已关闭阈值自动上推。`
                : "当前使用手动上推模式。"}
          </Text>
          {currentQueue.length === 0 ? (
            <EmptyState title="这一层当前没有待推进任务" />
          ) : (
            currentQueue.map((nodeId, index) => {
              const node = learningTaskNodesById[nodeId]
              return (
                <View key={nodeId} style={styles.row}>
                  <Text maxFontSizeMultiplier={1.1} style={styles.meta}>{index + 1}</Text>
                  <Text maxFontSizeMultiplier={1.1} style={styles.rowTitle}>{node?.title ?? (learningTaskNodesLoading ? "正在加载学习任务" : "节点信息同步中")}</Text>
                </View>
              )
            })
          )}
        </View>
      ) : null}
      {rollUpErrorMessage ? <Text maxFontSizeMultiplier={1.1} style={styles.error}>{rollUpErrorMessage}</Text> : null}
    </View>
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
            accessibilityRole="button"
            disabled={!isLeaf}
            key={node.nodeId}
            onPress={() => onSelectNode(node)}
            style={[styles.row, !isLeaf && styles.containerRow, active && styles.activeRow]}
          >
            <Text maxFontSizeMultiplier={1.1} style={[styles.rowTitle, active && styles.activeText]}>{node.title}</Text>
            <Text maxFontSizeMultiplier={1.1} style={styles.meta}>{isLeaf ? "内容" : "目录"}</Text>
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

function formatDurationCompact(ms: number) {
  if (!Number.isFinite(ms) || ms <= 0) return "0m"
  const totalMinutes = Math.floor(ms / 60000)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours <= 0) return `${Math.max(1, minutes)}m`
  if (minutes === 0) return `${hours}h`
  return `${hours}h ${minutes}m`
}

const styles = StyleSheet.create({
  actions: { flexDirection: "row", flexWrap: "wrap", gap: ui.spacing.md },
  activeRow: { backgroundColor: ui.colors.primarySoft },
  activeText: { color: "#1d4ed8", fontWeight: "800" },
  answer: { color: ui.colors.textMuted, fontSize: ui.type.control, lineHeight: 22 },
  cardNav: { alignItems: "center", flexDirection: "row", justifyContent: "space-between" },
  compactButton: { minHeight: 38, paddingHorizontal: 14, paddingVertical: 7 },
  containerRow: { opacity: 0.62 },
  disabled: { opacity: 0.55 },
  error: { color: ui.colors.danger, fontSize: 13 },
  header: { gap: ui.spacing.md, paddingTop: ui.spacing.sm },
  headerMeta: { color: ui.colors.textMuted, fontSize: 16, fontWeight: "600" },
  headerMetaRow: { alignItems: "center", flexDirection: "row", flexWrap: "wrap", gap: ui.spacing.sm },
  statusPill: {
    backgroundColor: "#eef0ff",
    borderRadius: ui.radius.xl,
    paddingHorizontal: 14,
    paddingVertical: 5,
  },
  statusPillText: { color: "#6e7895", fontSize: ui.type.caption, fontWeight: "700" },
  inputLabel: { color: ui.colors.text, fontSize: ui.type.control, fontWeight: "600" },
  inlineLabelRow: { alignItems: "center", flexDirection: "row", gap: ui.spacing.sm },
  infoBadge: {
    alignItems: "center",
    borderColor: "#98a2b8",
    borderRadius: 7,
    borderWidth: 1,
    height: 14,
    justifyContent: "center",
    width: 14,
  },
  infoBadgeText: { color: "#7b8499", fontSize: 9, fontWeight: "800", lineHeight: 12 },
  layerButton: {
    alignItems: "center",
    borderColor: ui.colors.border,
    borderRadius: ui.radius.lg,
    borderWidth: 1,
    minWidth: 52,
    paddingHorizontal: 12,
    paddingVertical: ui.spacing.md,
  },
  list: { gap: 0 },
  meta: { color: ui.colors.textMuted, fontSize: ui.type.caption },
  panel: {
    backgroundColor: ui.colors.surface,
    borderColor: ui.colors.borderSoft,
    borderRadius: ui.radius.lg,
    borderWidth: 1,
    gap: ui.spacing.md,
    padding: ui.spacing.lg,
  },
  primaryActions: { flexDirection: "row", flexWrap: "wrap", gap: ui.spacing.sm },
  primaryActionButton: { flex: 1 },
  progressButton: {
    alignItems: "center",
    borderColor: ui.colors.border,
    borderRadius: ui.radius.lg,
    borderWidth: 1,
    height: 40,
    justifyContent: "center",
    width: 40,
  },
  progressButtonActive: { borderColor: "#2563eb", borderWidth: 2 },
  progressButtonDone: { backgroundColor: ui.colors.primary, borderColor: ui.colors.primary },
  progressRow: { flexDirection: "row", flexWrap: "wrap", gap: ui.spacing.sm },
  progressText: { color: ui.colors.text, fontSize: 14, fontWeight: "700" },
  progressTextDone: { color: ui.colors.primaryText },
  question: { color: ui.colors.text, fontSize: ui.type.sectionTitle, fontWeight: "800", lineHeight: 26 },
  quickAction: {
    alignItems: "center",
    backgroundColor: ui.colors.secondaryBackground,
    borderColor: ui.colors.borderSoft,
    borderRadius: ui.radius.md,
    borderWidth: 1,
    minHeight: 34,
    paddingHorizontal: ui.spacing.lg,
    paddingVertical: ui.spacing.sm,
  },
  quickActionText: { color: ui.colors.secondaryText, fontSize: ui.type.caption, fontWeight: "700" },
  referenceBox: { gap: ui.spacing.sm },
  referenceButton: { alignSelf: "flex-start", paddingVertical: 4 },
  referenceText: { color: "#2563eb", fontSize: 13, fontWeight: "700" },
  row: {
    borderBottomColor: ui.colors.borderSoft,
    borderBottomWidth: 1,
    gap: ui.spacing.xs,
    paddingHorizontal: ui.spacing.xs,
    paddingVertical: ui.spacing.lg,
  },
  rowTitle: { color: ui.colors.text, fontSize: ui.type.body, fontWeight: "700" },
  section: { gap: ui.spacing.md, paddingVertical: 2 },
  sectionHeader: {
    alignItems: "center",
    flexDirection: "row",
    gap: ui.spacing.md,
    justifyContent: "space-between",
  },
  sectionTitle: { color: ui.colors.text, fontSize: ui.type.sectionTitle, fontWeight: "800" },
  coverageSummary: { alignItems: "center", flexDirection: "row", flexShrink: 1, gap: ui.spacing.lg },
  distributionBlock: { flex: 1.55, gap: ui.spacing.md, minWidth: 0 },
  donutLabel: { color: ui.colors.textMuted, fontSize: 12, fontWeight: "600" },
  donutValue: { color: ui.colors.text, fontSize: 22, fontWeight: "800", lineHeight: 26 },
  emptyActionButton: { alignSelf: "flex-start", minHeight: 42, paddingHorizontal: 24 },
  emptyBody: { color: ui.colors.textMuted, fontSize: ui.type.control, lineHeight: 22 },
  emptyBubble: {
    backgroundColor: "#6577f8",
    borderRadius: 12,
    height: 34,
    left: 2,
    opacity: 0.18,
    position: "absolute",
    top: 18,
    width: 42,
  },
  emptyClip: {
    alignSelf: "center",
    backgroundColor: "#6f7ff8",
    borderRadius: 8,
    height: 16,
    marginTop: -8,
    width: 44,
  },
  emptyClipboard: {
    backgroundColor: "#f4f6ff",
    borderColor: "#b8c0ff",
    borderRadius: ui.radius.xl,
    borderWidth: 2,
    gap: 9,
    height: 116,
    paddingHorizontal: 18,
    paddingTop: 20,
    transform: [{ rotate: "6deg" }],
    width: 98,
  },
  emptyCopy: { flex: 1, gap: ui.spacing.md, minWidth: 170 },
  emptyIllustration: { alignItems: "center", height: 132, justifyContent: "center", width: 132 },
  emptyLine: { backgroundColor: "#cbd1ff", borderRadius: 999, height: 7, width: 54 },
  emptyLineShort: { backgroundColor: "#d8dcff", borderRadius: 999, height: 7, width: 42 },
  emptyLineWide: { backgroundColor: "#bfc7ff", borderRadius: 999, height: 7, width: 62 },
  emptyPen: {
    backgroundColor: "#6373f6",
    borderRadius: 999,
    height: 62,
    position: "absolute",
    right: 14,
    top: 62,
    transform: [{ rotate: "-38deg" }],
    width: 14,
  },
  emptyRecallPanel: {
    alignItems: "center",
    backgroundColor: ui.colors.surface,
    borderColor: ui.colors.borderSoft,
    borderRadius: ui.radius.xl,
    borderWidth: 1,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: ui.spacing.xl,
    paddingHorizontal: ui.spacing.xl,
    paddingVertical: ui.spacing.xl,
  },
  emptyTitle: { color: ui.colors.text, fontSize: 24, fontWeight: "800", lineHeight: 30 },
  legendDot: { borderRadius: 5, height: 10, width: 10 },
  legendLabel: { alignItems: "center", flexDirection: "row", gap: ui.spacing.sm },
  legendRow: { alignItems: "center", flexDirection: "row", justifyContent: "space-between" },
  progressFill: { backgroundColor: "#5067f6", borderRadius: 999, height: "100%" },
  progressTrack: { backgroundColor: "#e4e7ef", borderRadius: 999, height: 8, overflow: "hidden" },
  remainingBlock: { flex: 1, gap: 24, minWidth: 0 },
  remainingValue: { color: ui.colors.text, fontSize: 21, fontWeight: "800", lineHeight: 28 },
  reviewChartRow: { alignItems: "center", flexDirection: "row", gap: ui.spacing.lg },
  reviewDonut: {
    alignItems: "center",
    backgroundColor: "transparent",
    borderBottomColor: "#64c7a5",
    borderColor: "#5067f6",
    borderLeftColor: "#64c7a5",
    borderRadius: 46,
    borderRightColor: "#ffad54",
    borderWidth: 16,
    height: 92,
    justifyContent: "center",
    width: 92,
  },
  reviewDonutHole: {
    alignItems: "center",
    backgroundColor: ui.colors.surface,
    borderRadius: 30,
    height: 60,
    justifyContent: "center",
    width: 60,
  },
  reviewLegend: { flex: 1, gap: ui.spacing.sm },
  segment: {
    backgroundColor: "#e8ecf2",
    borderRadius: ui.radius.xl,
    flexDirection: "row",
    gap: ui.spacing.xs,
    padding: ui.spacing.xs,
  },
  segmentButton: { borderRadius: 9, flex: 1, paddingHorizontal: ui.spacing.md, paddingVertical: ui.spacing.md },
  segmentButtonActive: { backgroundColor: "#5067f6" },
  segmentText: { color: ui.colors.textMuted, fontSize: 14, fontWeight: "700", textAlign: "center" },
  segmentTextActive: { color: ui.colors.primaryText },
  submitBlock: {
    backgroundColor: ui.colors.surface,
    borderColor: ui.colors.borderSoft,
    borderRadius: ui.radius.xl,
    borderWidth: 1,
    gap: ui.spacing.sm,
    padding: ui.spacing.xl,
  },
  submitButton: { marginTop: 2 },
  submitButtonDisabled: { backgroundColor: "#cfd3dd" },
  submitHint: { color: ui.colors.textMuted, fontSize: ui.type.caption, textAlign: "center" },
  statLabel: { color: ui.colors.textMuted, fontSize: ui.type.caption, fontWeight: "800" },
  statPercent: { color: ui.colors.text, fontSize: ui.type.caption, fontWeight: "800" },
  statValue: { color: ui.colors.text, fontSize: 18, fontWeight: "800" },
  statsDetailCard: {
    backgroundColor: ui.colors.surface,
    borderColor: ui.colors.borderSoft,
    borderRadius: ui.radius.xl,
    borderWidth: 1,
    flexDirection: "row",
    gap: ui.spacing.lg,
    padding: ui.spacing.lg,
  },
  statsDivider: { backgroundColor: ui.colors.borderSoft, width: 1 },
  statsHeader: { alignItems: "center", flexDirection: "row", gap: ui.spacing.md, justifyContent: "space-between" },
  statsIcon: {
    alignItems: "center",
    backgroundColor: "#f0f2ff",
    borderColor: "#e7e9ff",
    borderRadius: ui.radius.lg,
    borderWidth: 1,
    height: 42,
    justifyContent: "center",
    width: 42,
  },
  statsIconText: { color: "#5067f6", fontSize: 20, fontWeight: "800" },
  statsPanel: {
    backgroundColor: ui.colors.surface,
    borderColor: ui.colors.borderSoft,
    borderRadius: ui.radius.xl,
    borderWidth: 1,
    gap: ui.spacing.lg,
    padding: ui.spacing.lg,
  },
  statsTitleRow: { alignItems: "center", flexDirection: "row", gap: ui.spacing.md },
  titleActions: { flexDirection: "row", flexShrink: 0, gap: ui.spacing.sm },
  title: { color: ui.colors.text, fontSize: 28, fontWeight: "800", lineHeight: 36 },
  titleButton: { alignItems: "center", alignSelf: "flex-start", flexDirection: "row", gap: ui.spacing.xs, maxWidth: "100%" },
  titleChevron: { color: ui.colors.textMuted, fontSize: 16, fontWeight: "800" },
  toolbarButton: { flex: 1, minHeight: 40, paddingVertical: 8 },
})
