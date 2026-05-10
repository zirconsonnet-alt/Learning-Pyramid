import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react"
import { useQueries, useQuery } from "@tanstack/react-query"
import { BookPlus, ChevronLeft, ChevronRight } from "lucide-react"

import { ApiError } from "@/ui/api/http"
import { listRecallPointsByLearningTaskNode } from "@/ui/api/learningTaskNodes"
import type { Instance } from "@/ui/api/instances"
import type { ProjectScope } from "@/ui/api/projectScope"
import type { ProjectType } from "@/ui/api/projects"
import { searchRecallPoints, type RecallPoint } from "@/ui/api/review"
import { richContentHasMeaning, richContentToPlainText, richText } from "@/ui/api/richContent"
import { RichContentEditor } from "@/ui/components/RichContentEditor"
import { ContentEmptyState } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { formatInstanceReference, formatRecallPointReference, simplifyMaterialDisplayName } from "@/ui/displayIdentifiers"
import { completeGuideWalkthroughStep } from "@/ui/guideWalkthrough/guideWalkthroughController"
import {
  projectTypeRequiresAnchor,
  projectTypeRequiresLearningObjectTree,
  projectTypeUsesResolvableCourseAnchor,
} from "@/ui/projectTypes"
import { useLearningTaskNodes } from "@/ui/queries/learningTasks"
import { useSubmitLearningTask } from "@/ui/queries/workbench"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { touchDailyStudyActivity } from "@/ui/store/workbenchDailyStats"
import { getWorkbenchTaskScopeKey, useWorkbenchStore, type DraftRecallPoint } from "@/ui/store/workbenchStore"
import { cn } from "@/ui/utils"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function newLocalId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}_${Math.random().toString(16).slice(2)}`
}

function isDraftComplete(draft: DraftRecallPoint) {
  return richContentHasMeaning(draft.question) && richContentHasMeaning(draft.answer)
}

function buildRecommendedTaskTitle(instanceDisplayName: string, previousLearningCount: number) {
  return previousLearningCount <= 0 ? instanceDisplayName : `${instanceDisplayName}（${previousLearningCount + 1}）`
}

function createDraft(projectType: ProjectType, instanceId: string | null, ms: number): DraftRecallPoint {
  const position = projectType === "COURSE" ? `t=${ms}` : projectType === "BOOK" ? "" : null
  const now = Date.now()
  return {
    localId: newLocalId(),
    instanceId,
    position,
    question: richText(""),
    answer: richText(""),
    references: [],
    createdAt: now,
    updatedAt: now,
  }
}

function formatCourseAnchorMs(ms: number) {
  const totalSec = Math.max(0, Math.floor(ms / 1000))
  const h = Math.floor(totalSec / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
  return `${m}:${String(s).padStart(2, "0")}`
}

function parseCourseAnchorTime(value: string): number | null {
  const trimmed = value.trim()
  const rawMs = trimmed.match(/^t=(\d+)$/i)
  if (rawMs) return Number(rawMs[1])

  const parts = trimmed.split(":")
  if (parts.length < 2 || parts.length > 3 || parts.some((part) => !/^\d+$/.test(part))) return null
  const values = parts.map(Number)
  const [h, m, s] = parts.length === 3 ? values : [0, values[0], values[1]]
  if (m > 59 || s > 59) return null
  return ((h * 3600) + (m * 60) + s) * 1000
}

function formatCourseAnchorPositionForInput(position: string | null) {
  if (!position) return ""
  const ms = parseCourseAnchorTime(position)
  return ms === null ? position : formatCourseAnchorMs(ms)
}

function normalizeCourseAnchorPositionForSubmit(position: string | null) {
  const trimmed = position?.trim() ?? ""
  if (!trimmed) return null
  const ms = parseCourseAnchorTime(trimmed) ?? (/^\d+$/.test(trimmed) ? Number(trimmed) : null)
  return ms === null ? trimmed : `t=${ms}`
}

function normalizeAnchorPositionForSubmit(position: string | null, projectType: ProjectType) {
  if (projectTypeUsesResolvableCourseAnchor(projectType)) return normalizeCourseAnchorPositionForSubmit(position)
  const trimmed = position?.trim() ?? ""
  return trimmed || null
}

const COMPOSE_ACTIVITY_WINDOW_MS = 60_000
const MAX_REFERENCE_PICKER_ITEMS = 12

type ReferencePickerField = "question" | "answer"

type ReferenceCandidate = {
  recallPointId: string
  questionPreview: string
  answerPreview: string
}

export function ComposePane({
  subjectId,
  projectId,
  projectType,
  selectedInstanceId,
  instance,
  currentMs,
  queueHasGate,
  actionableMissingGate,
  actionableMissingInstanceCount,
}: {
  subjectId: string
  projectId: string
  projectType: ProjectType
  selectedInstanceId: string | null
  instance: Instance | null
  currentMs: number
  queueHasGate: boolean
  actionableMissingGate: boolean
  actionableMissingInstanceCount: number
}) {
  const projectScope: ProjectScope = { subjectId, projectId }
  const ps = useWorkbenchStore((s) => s.byProjectId[projectId])
  const addDraft = useWorkbenchStore((s) => s.addDraft)
  const updateDraftPosition = useWorkbenchStore((s) => s.updateDraftPosition)
  const updateDraftText = useWorkbenchStore((s) => s.updateDraftText)
  const appendDraftImage = useWorkbenchStore((s) => s.appendDraftImage)
  const removeDraftImage = useWorkbenchStore((s) => s.removeDraftImage)
  const addDraftReference = useWorkbenchStore((s) => s.addDraftReference)
  const removeDraftReference = useWorkbenchStore((s) => s.removeDraftReference)
  const removeDraft = useWorkbenchStore((s) => s.removeDraft)
  const clearDraftsForInstance = useWorkbenchStore((s) => s.clearDraftsForInstance)
  const setTaskTitle = useWorkbenchStore((s) => s.setTaskTitle)
  const cardRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const questionRefs = useRef<Record<string, HTMLTextAreaElement | null>>({})
  const answerRefs = useRef<Record<string, HTMLTextAreaElement | null>>({})
  const lastRecommendedTitleRef = useRef("")
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null)
  const [referencePicker, setReferencePicker] = useState<{
    field: ReferencePickerField
    draftId: string
    query: string
    highlightedIndex: number
  } | null>(null)

  const submit = useSubmitLearningTask(projectScope)
  const learningTaskNodesQ = useLearningTaskNodes(projectScope)
  const requiresLearningObjectTree = projectTypeRequiresLearningObjectTree(projectType)
  const requiresAnchor = projectTypeRequiresAnchor(projectType)
  const usesResolvableCourseAnchor = projectTypeUsesResolvableCourseAnchor(projectType)
  const activeScopeInstanceId = requiresLearningObjectTree ? selectedInstanceId : null
  const taskScopeKey = getWorkbenchTaskScopeKey(activeScopeInstanceId)

  const drafts = (ps?.drafts ?? []).filter((d) => d.instanceId === activeScopeInstanceId)
  const taskTitle = ps?.taskTitlesByInstanceId?.[taskScopeKey] ?? ""
  const leafNodeIds = useMemo(
    () =>
      (learningTaskNodesQ.data ?? [])
        .filter((node) => node.kind === "leaf")
        .map((node) => node.nodeId),
    [learningTaskNodesQ.data],
  )
  const learningTaskRecallPointQs = useQueries({
    queries: leafNodeIds.map((nodeId) => ({
      queryKey: ["recallPointsByTaskNode", subjectId, projectId, nodeId],
      queryFn: () => listRecallPointsByLearningTaskNode(projectScope, nodeId),
      enabled: !!projectId && requiresLearningObjectTree && !!selectedInstanceId,
    })),
  })
  const previousLearningCountForInstance = useMemo(() => {
    if (projectType === "LOOSE_POINTS") return leafNodeIds.length
    if (!selectedInstanceId) return 0
    let count = 0
    for (const query of learningTaskRecallPointQs) {
      const recallPoints = query.data ?? []
      if (recallPoints.length === 0) continue
      if (recallPoints.every((rp) => rp.anchor?.instanceId === selectedInstanceId)) count += 1
    }
    return count
  }, [leafNodeIds.length, learningTaskRecallPointQs, projectType, selectedInstanceId])
  const recommendedTaskTitle = useMemo(() => {
    if (projectType === "LOOSE_POINTS") {
      return buildRecommendedTaskTitle("零散知识点", previousLearningCountForInstance)
    }
    if (!instance) return ""
    const instanceTitle = simplifyMaterialDisplayName(
      formatInstanceReference(instance.instanceId, instance.materialDisplayName),
      "未命名内容",
    )
    return buildRecommendedTaskTitle(instanceTitle, previousLearningCountForInstance)
  }, [instance, previousLearningCountForInstance, projectType])

  function touchComposeActivity() {
    touchDailyStudyActivity(projectId, "recallEntry", COMPOSE_ACTIVITY_WINDOW_MS)
  }

  useEffect(() => {
    const previousRecommendedTitle = lastRecommendedTitleRef.current
    const trimmedTitle = taskTitle.trim()
    const shouldAdoptRecommended = !trimmedTitle || taskTitle === previousRecommendedTitle
    if (requiresLearningObjectTree && !selectedInstanceId) {
      lastRecommendedTitleRef.current = ""
      return
    }
    if (recommendedTaskTitle && shouldAdoptRecommended && taskTitle !== recommendedTaskTitle) {
      setTaskTitle(projectId, activeScopeInstanceId, recommendedTaskTitle)
    }
    lastRecommendedTitleRef.current = recommendedTaskTitle
  }, [activeScopeInstanceId, projectId, recommendedTaskTitle, requiresLearningObjectTree, selectedInstanceId, setTaskTitle, taskTitle])

  function onAdd() {
    if (requiresLearningObjectTree && !selectedInstanceId) return
    touchComposeActivity()
    const draft = createDraft(projectType, activeScopeInstanceId, currentMs)
    addDraft(projectId, draft)
    setSelectedDraftId(draft.localId)
    completeGuideWalkthroughStep("add-recall-point")
    window.setTimeout(() => focusDraftFields(draft), 80)
  }

  async function onSubmit() {
    if (queueHasGate || actionableMissingGate) return
    const title = taskTitle.trim()
    if (!title) return
    if (
      drafts.some(
        (d) =>
          !richContentHasMeaning(d.question) ||
          !richContentHasMeaning(d.answer) ||
          (requiresAnchor && (!d.instanceId || !(d.position ?? "").trim())),
      )
    ) {
      return
    }
    const items = drafts.map((d) => {
      const anchorPosition = normalizeAnchorPositionForSubmit(d.position, projectType)
      return {
        question: d.question,
        answer: d.answer,
        anchor: requiresAnchor && d.instanceId && anchorPosition ? { instanceId: d.instanceId, position: anchorPosition } : null,
        references: d.references,
      }
    })
    if (items.length === 0) return
    try {
      touchComposeActivity()
      await submit.mutateAsync({ title, items })
      clearDraftsForInstance(projectId, activeScopeInstanceId)
      showSuccessFeedback("学习任务已提交", `“${title}” 已提交，共包含 ${items.length} 个复述点。`)
      completeGuideWalkthroughStep("submit-learning")
    } catch (err) {
      showErrorFeedback("提交学习任务失败", formatApiError(err))
    }
  }

  const hasIncompleteAnchor = requiresAnchor && drafts.some((d) => !d.instanceId || !(d.position ?? "").trim())
  const canSubmit =
    !queueHasGate &&
    !actionableMissingGate &&
    !submit.isPending &&
    !!taskTitle.trim() &&
    drafts.length > 0 &&
    !drafts.some((d) => !richContentHasMeaning(d.question) || !richContentHasMeaning(d.answer)) &&
    !hasIncompleteAnchor

  const completedDraftCount = drafts.filter((draft) => isDraftComplete(draft)).length
  const completionPercent = drafts.length > 0 ? Math.round((completedDraftCount / drafts.length) * 100) : 0
  const resolvedActiveDraftId = drafts.some((draft) => draft.localId === selectedDraftId)
    ? selectedDraftId
    : drafts[0]?.localId ?? null
  const activeDraftIndex = resolvedActiveDraftId ? drafts.findIndex((draft) => draft.localId === resolvedActiveDraftId) : -1
  const activeDraft = activeDraftIndex >= 0 ? drafts[activeDraftIndex] : null
  const effectiveReferencePicker = referencePicker?.draftId === resolvedActiveDraftId ? referencePicker : null
  const deferredReferenceQuery = useDeferredValue(effectiveReferencePicker?.query.trim() ?? "")
  const referenceSearchQ = useQuery({
    queryKey: ["recallPointSearch", subjectId, projectId, deferredReferenceQuery],
    queryFn: ({ signal }) =>
      searchRecallPoints(
        projectScope,
        { q: deferredReferenceQuery || undefined, limit: MAX_REFERENCE_PICKER_ITEMS * 4 },
        { signal },
      ),
    enabled: !!projectId && !!effectiveReferencePicker,
    placeholderData: (previous) => previous,
    staleTime: 30_000,
  })
  const allReferenceCandidates = useMemo<ReferenceCandidate[]>(
    () =>
      (referenceSearchQ.data ?? []).map((item: RecallPoint) => {
        const questionPreview = richContentToPlainText(item.question).trim() || "题面为空"
        const answerPreview = richContentToPlainText(item.answer).trim() || "答案为空"
        return {
          recallPointId: item.recallPointId,
          questionPreview,
          answerPreview,
        }
      }),
    [referenceSearchQ.data],
  )
  const selectedReferenceIds = activeDraft?.references ?? []
  const referencePickerCandidates = (() => {
    if (!effectiveReferencePicker || !activeDraft) return []
    const referenceIdSet = new Set(activeDraft.references)
    return allReferenceCandidates
      .filter((candidate) => !referenceIdSet.has(candidate.recallPointId))
      .slice(0, MAX_REFERENCE_PICKER_ITEMS)
  })()
  const effectiveReferencePickerHighlightIndex = Math.min(
    effectiveReferencePicker?.highlightedIndex ?? 0,
    Math.max(referencePickerCandidates.length - 1, 0),
  )

  function focusDraftFields(draft: DraftRecallPoint) {
    const questionFilled = richContentHasMeaning(draft.question)
    const answerFilled = richContentHasMeaning(draft.answer)
    const target =
      !questionFilled
        ? questionRefs.current[draft.localId]
        : !answerFilled
          ? answerRefs.current[draft.localId]
          : questionRefs.current[draft.localId]

    cardRefs.current[draft.localId]?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    })
    target?.focus()
  }

  function focusDraft(draft: DraftRecallPoint) {
    touchComposeActivity()
    setSelectedDraftId(draft.localId)
    window.setTimeout(() => focusDraftFields(draft), 80)
  }

  function focusEditorField(field: ReferencePickerField) {
    const target = field === "question" ? questionRefs.current[resolvedActiveDraftId ?? ""] : answerRefs.current[resolvedActiveDraftId ?? ""]
    target?.focus()
  }

  function openReferencePicker(field: ReferencePickerField) {
    if (!activeDraft) return
    touchComposeActivity()
    setReferencePicker({ field, draftId: activeDraft.localId, query: "", highlightedIndex: 0 })
  }

  function closeReferencePicker(field?: ReferencePickerField) {
    setReferencePicker(null)
    if (field) {
      window.setTimeout(() => focusEditorField(field), 0)
    }
  }

  function confirmReferencePickerSelection(field: ReferencePickerField) {
    const selected = referencePickerCandidates[effectiveReferencePickerHighlightIndex]
    if (!selected || !activeDraft) {
      closeReferencePicker(field)
      return
    }
    touchComposeActivity()
    addDraftReference(projectId, activeDraft.localId, selected.recallPointId)
    closeReferencePicker(field)
  }

  function goToDraft(index: number) {
    const nextDraft = drafts[index]
    if (!nextDraft) return
    touchComposeActivity()
    setSelectedDraftId(nextDraft.localId)
  }

  return (
    <Card className="theme-card-main">
      <CardHeader className="theme-card-header flex-col gap-4 space-y-0 md:flex-row md:items-start md:justify-between">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <div className="theme-icon-surface h-10 w-10">
            <BookPlus className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <CardTitle>复述点录入</CardTitle>
            {projectType === "LOOSE_POINTS" ? (
              <div className="mt-1 text-xs text-muted-foreground">当前项目按零散知识点模式录入，不需要选择内容实例或绑定锚点。</div>
            ) : instance ? (
              <div className="mt-1 truncate text-xs text-muted-foreground">{instance.materialDisplayName}</div>
            ) : (
              <div className="mt-1 text-xs text-muted-foreground">
                {projectType === "BOOK" ? "请先从左侧目录中选择一个章节、小节或条目。" : "请先从左侧目录中选择一个视频实例。"}
              </div>
            )}
          </div>
        </div>

        <div className="grid w-full gap-3 md:w-[24rem] md:shrink-0 md:grid-cols-[minmax(0,1fr)_auto] md:items-center md:gap-4">
          <div className="min-w-0 space-y-2">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="theme-meta">{drafts.length} 个复述点</span>
              <span className="font-medium text-[color:var(--theme-subtle-text)]">
                已完成 {completedDraftCount} / {drafts.length}
              </span>
            </div>
            <div className="theme-progress-track h-2 overflow-hidden rounded-full">
              <div
                className="theme-progress-fill h-full rounded-full transition-[width] duration-300"
                style={{ width: `${completionPercent}%` }}
              />
            </div>
          </div>
          <div className="flex w-full gap-2 md:w-auto md:self-center">
            <Button
              data-guide-tour="add-recall-point-button"
              onClick={onAdd}
              disabled={requiresLearningObjectTree && !selectedInstanceId}
              className="flex-1 whitespace-nowrap md:flex-none"
            >
              添加
            </Button>
            {activeDraft ? (
              <Button
                variant="ghost"
                onClick={() => {
                  touchComposeActivity()
                  removeDraft(projectId, activeDraft.localId)
                }}
                className="flex-1 whitespace-nowrap text-muted-foreground md:flex-none"
              >
                删除
              </Button>
            ) : null}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 pt-5">
        {queueHasGate ? (
          <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm">
            门禁：队列非空时禁止提交学习。请先完成“复习”。
          </div>
        ) : null}
        {actionableMissingGate ? (
          <div className="rounded-2xl border border-amber-300/60 bg-amber-50 p-4 text-sm text-amber-900">
            门禁：当前还有 {actionableMissingInstanceCount} 个待迁移的缺失实例。请先去项目设置完成修复，再继续提交学习任务。
          </div>
        ) : null}

        {drafts.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {drafts.map((draft, index) => {
              const completed = isDraftComplete(draft)
              const isActive = draft.localId === resolvedActiveDraftId
              return (
                <button
                  key={`draft-progress-${draft.localId}`}
                  type="button"
                  onClick={() => focusDraft(draft)}
                  aria-current={isActive ? "true" : undefined}
                  className={cn(
                    "flex size-10 items-center justify-center rounded-xl border text-sm font-semibold transition-all",
                    completed
                      ? "border-primary/20 bg-primary text-primary-foreground shadow-[0_12px_24px_-20px_hsl(var(--primary)/0.55)]"
                      : "[border-color:var(--theme-soft-border)] [background:var(--theme-soft-bg)] text-[color:var(--theme-subtle-text)] hover:border-primary/25 hover:text-primary",
                    isActive && "ring-2 ring-primary/25 ring-offset-2 ring-offset-background",
                  )}
                  title={completed ? `第 ${index + 1} 个复述点，已填写` : `第 ${index + 1} 个复述点，尚未填写完成`}
                  aria-label={completed ? `第 ${index + 1} 个复述点，已填写` : `第 ${index + 1} 个复述点，尚未填写完成`}
                >
                  {index + 1}
                </button>
              )
            })}
          </div>
        ) : null}

        {drafts.length === 0 && selectedInstanceId ? (
          <div className="theme-subtle-surface border-dashed px-4 py-5 text-[15px] font-medium">
            暂无复述点
          </div>
        ) : null}

        {drafts.length === 0 && !selectedInstanceId ? (
          requiresLearningObjectTree ? (
            <ContentEmptyState
              icon={BookPlus}
              title={
                projectType === "BOOK" ? "先选择一个书本目录节点" : "先选择一个视频再开始录入"
              }
              message={
                projectType === "BOOK"
                  ? "请先从左侧内容目录里选择一个章节、小节或条目，随后就能录入带文本锚点的复述点。"
                  : "请先从左侧内容目录里选择一个视频，随后就能开始录入复述点。"
              }
            />
          ) : null
        ) : null}
        {drafts.length === 0 && !requiresLearningObjectTree ? (
          <div className="theme-subtle-surface border-dashed px-4 py-5 text-[15px] font-medium">
            当前还没有零散知识点，点击“添加”即可开始录入。
          </div>
        ) : null}

        {activeDraft ? (
          <div className="grid gap-3">
            <div
              key={activeDraft.localId}
              ref={(node) => {
                cardRefs.current[activeDraft.localId] = node
              }}
              className="relative overflow-visible"
            >
              <div className="sr-only" aria-live="polite">
                {activeDraftIndex >= 0 ? `第 ${activeDraftIndex + 1} 个 / 共 ${drafts.length} 个复述点` : `${drafts.length} 个复述点`}
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="absolute inset-y-0 -left-4 z-10 h-auto w-4 rounded-none border-0 bg-transparent p-0 text-[color:var(--theme-subtle-text)] shadow-none outline-none hover:bg-transparent hover:text-foreground focus-visible:ring-0 focus-visible:ring-offset-0 sm:-left-5 sm:w-5"
                onClick={() => goToDraft(activeDraftIndex - 1)}
                disabled={activeDraftIndex <= 0}
                aria-label="上一张复述点卡片"
                title="上一张"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="absolute inset-y-0 -right-4 z-10 h-auto w-4 rounded-none border-0 bg-transparent p-0 text-[color:var(--theme-subtle-text)] shadow-none outline-none hover:bg-transparent hover:text-foreground focus-visible:ring-0 focus-visible:ring-offset-0 sm:-right-5 sm:w-5"
                onClick={() => goToDraft(activeDraftIndex + 1)}
                disabled={activeDraftIndex < 0 || activeDraftIndex >= drafts.length - 1}
                aria-label="下一张复述点卡片"
                title="下一张"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>

              <div className="theme-status-surface rounded-[1.15rem] border border-[color:var(--theme-status-border)] px-4 py-4 sm:px-5">
                {requiresAnchor ? (
                  <div className="mb-4 space-y-2 border-b border-[color:var(--theme-soft-border)] pb-4">
                    <Label
                      htmlFor={`draft-anchor-${activeDraft.localId}`}
                      className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground"
                    >
                      锚点位置
                    </Label>
                    <Input
                      id={`draft-anchor-${activeDraft.localId}`}
                      value={
                        usesResolvableCourseAnchor
                          ? formatCourseAnchorPositionForInput(activeDraft.position)
                          : activeDraft.position ?? ""
                      }
                      onChange={(event) => {
                        touchComposeActivity()
                        updateDraftPosition(projectId, activeDraft.localId, event.target.value)
                      }}
                      onFocus={touchComposeActivity}
                      placeholder={
                        usesResolvableCourseAnchor ? "例如：17:57 / 1:02:03 / t=1077104" : "例如：第 45 页 例 2 / 第 3 章 1.2 节 / 习题 7"
                      }
                      className="h-11 rounded-xl border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)]"
                    />
                    <p className="text-xs text-muted-foreground">
                      {usesResolvableCourseAnchor
                        ? "网课锚点可编辑，提交时会保存为可跳转的视频时间点。"
                        : "书本项目必须填写文本锚点，例如页码、章节、小节、题号或段落说明。"}
                    </p>
                  </div>
                ) : null}

                <div className="grid gap-3 xl:grid-cols-2">
                  <div className="space-y-2" data-guide-tour="recall-question-editor">
                    <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">问题</div>
                    <RichContentEditor
                      subjectId={subjectId}
                      projectId={projectId}
                      field="question"
                      value={activeDraft.question}
                      placeholder="请输入问题/提示语"
                      onTextChange={(text) => {
                        updateDraftText(projectId, activeDraft.localId, "question", text)
                        if (text.trim()) completeGuideWalkthroughStep("fill-recall-question")
                      }}
                      onAppendImage={(assetId) => {
                        touchComposeActivity()
                        appendDraftImage(projectId, activeDraft.localId, "question", assetId)
                      }}
                      onRemoveImage={(imageIndex) => {
                        touchComposeActivity()
                        removeDraftImage(projectId, activeDraft.localId, "question", imageIndex)
                      }}
                      onUserActivity={touchComposeActivity}
                      onTextKeyDown={(event) => {
                        if (event.key !== "Tab" || event.shiftKey || event.nativeEvent.isComposing) return
                        event.preventDefault()
                        openReferencePicker("question")
                      }}
                      referencePicker={
                        effectiveReferencePicker?.field === "question"
                          ? {
                              isOpen: true,
                              isLoading: referenceSearchQ.isLoading || (referenceSearchQ.isFetching && !referenceSearchQ.data),
                              query: effectiveReferencePicker.query,
                              highlightedIndex: effectiveReferencePickerHighlightIndex,
                              candidates: referencePickerCandidates,
                              onQueryChange: (query) => setReferencePicker((current) => (current ? { ...current, query, highlightedIndex: 0 } : current)),
                              onHighlightChange: (index) =>
                                setReferencePicker((current) => (current ? { ...current, highlightedIndex: index } : current)),
                              onConfirm: () => confirmReferencePickerSelection("question"),
                              onSelect: (recallPointId) => {
                                touchComposeActivity()
                                addDraftReference(projectId, activeDraft.localId, recallPointId)
                                closeReferencePicker("question")
                              },
                              onClose: () => closeReferencePicker("question"),
                            }
                          : undefined
                      }
                      textareaRef={(node) => {
                        questionRefs.current[activeDraft.localId] = node
                      }}
                      textareaClassName="min-h-[180px] resize-y rounded-2xl [border-color:var(--theme-subtle-border)] [background:var(--theme-subtle-bg)] text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/15"
                      imageClassName="h-28 w-full max-w-[220px] rounded-2xl border [border-color:var(--theme-subtle-border)] [background:var(--theme-subtle-bg)] object-cover"
                    />
                  </div>

                  <div className="space-y-2" data-guide-tour="recall-answer-editor">
                    <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">答案</div>
                    <RichContentEditor
                      subjectId={subjectId}
                      projectId={projectId}
                      field="answer"
                      value={activeDraft.answer}
                      placeholder="请输入答案/复述内容"
                      onTextChange={(text) => {
                        updateDraftText(projectId, activeDraft.localId, "answer", text)
                        if (text.trim()) completeGuideWalkthroughStep("fill-recall-answer")
                      }}
                      onAppendImage={(assetId) => {
                        touchComposeActivity()
                        appendDraftImage(projectId, activeDraft.localId, "answer", assetId)
                      }}
                      onRemoveImage={(imageIndex) => {
                        touchComposeActivity()
                        removeDraftImage(projectId, activeDraft.localId, "answer", imageIndex)
                      }}
                      onUserActivity={touchComposeActivity}
                      onTextKeyDown={(event) => {
                        if (event.key !== "Tab" || event.shiftKey || event.nativeEvent.isComposing) return
                        event.preventDefault()
                        openReferencePicker("answer")
                      }}
                      referencePicker={
                        effectiveReferencePicker?.field === "answer"
                          ? {
                              isOpen: true,
                              isLoading: referenceSearchQ.isLoading || (referenceSearchQ.isFetching && !referenceSearchQ.data),
                              query: effectiveReferencePicker.query,
                              highlightedIndex: effectiveReferencePickerHighlightIndex,
                              candidates: referencePickerCandidates,
                              onQueryChange: (query) => setReferencePicker((current) => (current ? { ...current, query, highlightedIndex: 0 } : current)),
                              onHighlightChange: (index) =>
                                setReferencePicker((current) => (current ? { ...current, highlightedIndex: index } : current)),
                              onConfirm: () => confirmReferencePickerSelection("answer"),
                              onSelect: (recallPointId) => {
                                touchComposeActivity()
                                addDraftReference(projectId, activeDraft.localId, recallPointId)
                                closeReferencePicker("answer")
                              },
                              onClose: () => closeReferencePicker("answer"),
                            }
                          : undefined
                      }
                      textareaRef={(node) => {
                        answerRefs.current[activeDraft.localId] = node
                      }}
                      textareaClassName="min-h-[180px] resize-y rounded-2xl [border-color:var(--theme-subtle-border)] [background:var(--theme-subtle-bg)] text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/15"
                      imageClassName="h-28 w-full max-w-[220px] rounded-2xl border [border-color:var(--theme-subtle-border)] [background:var(--theme-subtle-bg)] object-cover"
                    />
                    {selectedReferenceIds.length > 0 ? (
                      <div className="flex flex-wrap gap-2" aria-label="答案引用">
                        {selectedReferenceIds.map((referenceId) => (
                          <button
                            key={`selected-reference-link-${referenceId}`}
                            type="button"
                            className="selected-reference-link inline-flex max-w-full items-center rounded-md px-1 text-left text-sm font-medium text-primary underline underline-offset-4 transition hover:text-primary/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                            onClick={() => {
                              touchComposeActivity()
                              removeDraftReference(projectId, activeDraft.localId, referenceId)
                            }}
                            title={`删除引用 ${referenceId}`}
                            aria-label={`删除答案引用 ${referenceId}`}
                          >
                            <span className="truncate">{formatRecallPointReference(referenceId)}</span>
                          </button>
                        ))}
                      </div>
                    ) : null}
                    {referenceSearchQ.error ? <p className="text-xs text-destructive">候选复述点加载失败：{formatApiError(referenceSearchQ.error)}</p> : null}
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : null}

        <div className="border-t border-[color:var(--theme-soft-border)] pt-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <Label htmlFor="taskTitle" className="shrink-0 text-sm font-medium text-[color:var(--theme-subtle-text)] md:w-[6.5rem]">
              任务标题
            </Label>
            <Input
              id="taskTitle"
              value={taskTitle}
              onChange={(e) => {
                if (requiresLearningObjectTree && !selectedInstanceId) return
                touchComposeActivity()
                setTaskTitle(projectId, activeScopeInstanceId, e.target.value)
              }}
              onFocus={touchComposeActivity}
              onKeyDown={(e) => {
                if (e.key !== "Enter" || e.nativeEvent.isComposing) return
                e.preventDefault()
                if (canSubmit) {
                  void onSubmit()
                } else if (!taskTitle.trim() && recommendedTaskTitle) {
                  setTaskTitle(projectId, activeScopeInstanceId, recommendedTaskTitle)
                }
              }}
              className="h-11 flex-1"
              placeholder={
                projectType === "LOOSE_POINTS"
                  ? recommendedTaskTitle || "例如：离散数学零散练习"
                  : instance
                    ? recommendedTaskTitle
                    : "例如：第一节"
              }
            />
            <Button
              data-guide-tour="submit-learning-button"
              className="h-11 shrink-0 rounded-xl px-5 md:min-w-[7rem]"
              onClick={() => void onSubmit()}
              disabled={!canSubmit}
            >
              {submit.isPending ? "提交中..." : "提交学习"}
            </Button>
          </div>
          {submit.error ? <p className="mt-2 text-sm text-destructive">{formatApiError(submit.error)}</p> : null}
          {!submit.isPending && !submit.error && actionableMissingGate ? (
            <p className="mt-2 text-xs text-muted-foreground">当前提交已被缺失实例门禁拦住，完成实例迁移后会自动恢复。</p>
          ) : null}
          {!submit.isPending && !submit.error && hasIncompleteAnchor ? (
            <p className="mt-2 text-xs text-muted-foreground">提交前还需要把每条复述点的锚点位置补完整。</p>
          ) : null}
          {!submit.isPending &&
          !submit.error &&
          drafts.length > 0 &&
          !drafts.some((d) => !richContentHasMeaning(d.question) || !richContentHasMeaning(d.answer)) &&
          !hasIncompleteAnchor ? (
            <p className="mt-2 text-xs text-muted-foreground">已准备好提交，共 {drafts.length} 个复述点，已完成 {completedDraftCount} 个。</p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}
