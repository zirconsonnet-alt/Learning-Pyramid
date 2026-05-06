import { useEffect, useState, type ReactNode } from "react"
import { ChevronLeft, Sparkles } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import {
  exportRecallPointsByLearningTaskNode,
  listRecallPointsByLearningTaskNode,
} from "@/ui/api/learningTaskNodes"
import { ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { useEditLearningTask, useEditLearningTaskNode, useLearningTask, useLearningTaskNode, useLearningTaskNodeBinding } from "@/ui/queries/learningTasks"
import { useInstances } from "@/ui/queries/workbench"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { buildAiChatPath } from "@/views/ai/chatRouting"
import { formatLearningTaskNodeDisplayTitle } from "@/views/learningTasks/displayTitle"
import { RecallPointListCard } from "@/views/recallPoints/components/RecallPointListCard"
import { NodeExportCard } from "@/views/shared/NodeExportCard"
import type { LearningTaskNode } from "@/ui/api/learningTaskNodes"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function getLearningTaskNodeDisplayChildIds(node: LearningTaskNode | undefined) {
  if (!node || node.kind !== "container") return []
  return node.children
}

export function LearningTaskNodePage() {
  const { projectId, nodeId } = useParams()
  const navigate = useNavigate()
  const pid = projectId ?? ""
  const nid = nodeId ?? ""

  const nodeQ = useLearningTaskNode(pid, nid)
  const bindingQ = useLearningTaskNodeBinding(pid, nid)
  const instancesQ = useInstances(pid)
  const recallPointsQ = useQuery({
    queryKey: ["recallPointsByTaskNode", pid, nid],
    queryFn: () => listRecallPointsByLearningTaskNode(pid, nid),
    enabled: !!pid && !!nid,
  })
  const learningTaskId = nodeQ.data?.kind === "leaf" ? nodeQ.data.boundLearningTaskId : ""
  const learningTaskQ = useLearningTask(pid, learningTaskId)

  if (!pid || !nid) {
    return (
      <div className="space-y-4">
        <ContentNotice
          title="当前页面缺少任务节点上下文"
          message="当前链接缺少任务节点信息。请先返回项目列表，再从学习任务树重新进入。"
          action={<Button onClick={() => navigate("/projects")}>返回项目列表</Button>}
        />
      </div>
    )
  }

  const sourceLayerIndex =
    bindingQ.data?.targetLayerIndex === undefined || bindingQ.data?.targetLayerIndex === null
      ? undefined
      : Math.max(0, bindingQ.data.targetLayerIndex - 1)
  const title = formatLearningTaskNodeDisplayTitle(nodeQ.data?.title ?? "任务节点", { sourceLayerIndex })
  const isContainer = nodeQ.data?.kind === "container"
  const childCount = isContainer ? getLearningTaskNodeDisplayChildIds(nodeQ.data).length : null
  const instanceTitleById = Object.fromEntries((instancesQ.data ?? []).map((instance) => [instance.instanceId, instance.materialDisplayName])) as Record<string, string>
  const relatedInstanceLabel = (() => {
    const ids = Array.from(new Set((recallPointsQ.data ?? []).flatMap((item) => (item.anchor?.instanceId ? [item.anchor.instanceId] : []))))
    if (ids.length === 0) return "未绑定内容锚点"
    if (ids.length === 1) return instanceTitleById[ids[0]] ?? "关联内容"
    return `${ids.length} 个关联内容`
  })()
  const backToTaskTreeAction = (
    <Button
      variant="ghost"
      size="sm"
      className="-ml-2 h-8 rounded-full px-2 text-[#60748c] hover:bg-[#f3f7fb] hover:text-foreground"
      asChild
    >
      <Link to={`/p/${pid}/task-tree`}>
        <ChevronLeft className="h-4 w-4" />
        返回学习任务树
      </Link>
    </Button>
  )
  const summaryPanel = nodeQ.data ? (
    <div className="space-y-3">
      {isContainer ? (
        <LearningTaskSummaryCard
          topAction={backToTaskTreeAction}
          header={
            <LearningTaskNodeTitleHeaderEditor
              projectId={pid}
              nodeId={nid}
              displayTitle={title}
              nodeTitle={nodeQ.data.title}
            />
          }
          items={[
            { label: "节点类型", value: "聚合节点" },
            { label: "子节点数", value: childCount ?? 0 },
            {
              label: "复习关系",
              value: bindingQ.data?.reviewChainId ? (
                <Link className="text-primary underline-offset-4 hover:underline" to={`/p/${pid}/review-chains/${bindingQ.data.reviewChainId}`}>
                  查看复习链
                </Link>
              ) : (
                "暂未关联"
              ),
            },
          ]}
        />
      ) : learningTaskId ? (
        <LeafLearningTaskCard
          projectId={pid}
          learningTaskId={learningTaskId}
          learningTaskQ={learningTaskQ}
          displayTitle={title}
          relatedInstanceLabel={relatedInstanceLabel}
          reviewChainId={bindingQ.data?.reviewChainId ?? null}
          topAction={backToTaskTreeAction}
        />
      ) : null}
      <Button asChild className="w-full">
        <Link to={buildAiChatPath(pid, { kind: "task", nodeId: nid })}>
          <Sparkles className="h-4 w-4" />
          AI问答
        </Link>
      </Button>
    </div>
  ) : null

  return (
    <div className="space-y-4">
      {nodeQ.isLoading ? <LoadingNotice title="正在加载任务节点" message="正在读取这个节点的层级、子节点和关联任务信息。" /> : null}
      {nodeQ.error ? <ErrorNotice title="任务节点加载失败" message={formatApiError(nodeQ.error)} /> : null}
      {bindingQ.error ? <ErrorNotice title="节点绑定加载失败" message={formatApiError(bindingQ.error)} /> : null}
      {!isContainer && learningTaskId && learningTaskQ.error ? (
        <ErrorNotice title="学习任务加载失败" message={formatApiError(learningTaskQ.error)} />
      ) : null}
      {!nodeQ.isLoading && !nodeQ.error && !nodeQ.data ? (
        <ContentNotice
          title="未找到这个任务节点"
          message="这个任务节点可能已经被重建或移除。你可以返回学习任务树重新选择。"
          action={
            <Button variant="outline" asChild>
              <Link to={`/p/${pid}/task-tree`}>返回学习任务树</Link>
            </Button>
          }
        />
      ) : null}

      {nodeQ.data ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)] xl:items-start">
          {summaryPanel ? <aside className="xl:sticky xl:top-28 xl:self-start">{summaryPanel}</aside> : <div />}
          <div className="min-w-0">
            <RecallPointListCard
              projectId={pid}
              items={recallPointsQ.data ?? []}
              instanceTitleById={instanceTitleById}
              isLoading={recallPointsQ.isLoading}
              error={recallPointsQ.error}
              title="复述点列表"
              headerAction={
                <NodeExportCard
                  projectId={pid}
                  nodeTitle={title}
                  recallPoints={recallPointsQ.data ?? []}
                  exportRecallPoints={() => exportRecallPointsByLearningTaskNode(pid, nid)}
                />
              }
            />
          </div>
        </div>
      ) : null}
    </div>
  )
}

function LeafLearningTaskCard(props: {
  projectId: string
  learningTaskId: string
  learningTaskQ: ReturnType<typeof useLearningTask>
  displayTitle: string
  relatedInstanceLabel: string
  reviewChainId: string | null
  topAction?: ReactNode
}) {
  const { projectId, learningTaskId, learningTaskQ, displayTitle, relatedInstanceLabel, reviewChainId, topAction } = props

  return (
    <LearningTaskSummaryCard
      topAction={topAction}
      header={
        learningTaskQ.data ? (
          <LearningTaskTitleHeaderEditor
            projectId={projectId}
            learningTaskId={learningTaskId}
            displayTitle={displayTitle}
            taskTitle={learningTaskQ.data.title}
          />
        ) : (
          <h1 className="truncate text-lg font-semibold">{displayTitle}</h1>
        )
      }
      items={[
        { label: "复述点", value: learningTaskQ.data?.size ?? "-" },
        {
          label: "层级",
          value: learningTaskQ.data?.targetLayerIndex === null || learningTaskQ.data == null ? "-" : `L${learningTaskQ.data.targetLayerIndex}`,
        },
        { label: "关联内容", value: relatedInstanceLabel },
        {
          label: "复习关系",
          value: reviewChainId ? (
            <Link className="text-primary underline-offset-4 hover:underline" to={`/p/${projectId}/review-chains/${reviewChainId}`}>
              查看复习链
            </Link>
          ) : (
            "暂未关联"
          ),
        },
      ]}
    />
  )
}

type SummaryItem = {
  label: string
  value: ReactNode
}

function LearningTaskSummaryCard({
  description,
  header,
  items,
  topAction,
}: {
  description?: string
  header: ReactNode
  items: SummaryItem[]
  topAction?: ReactNode
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        {topAction ? <div className="flex items-center">{topAction}</div> : null}
        <div className="min-w-0">{header}</div>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-3">
          {items.map((item) => (
            <div
              key={item.label}
              className="min-w-[10rem] flex-1 rounded-xl border border-[#dbe4ee] bg-[#f8fafc] px-4 py-3 shadow-[0_10px_24px_-24px_rgba(15,23,42,0.6)]"
            >
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#64748b]">{item.label}</div>
              <div className="mt-1.5 text-sm font-semibold text-slate-900">{item.value}</div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function LearningTaskTitleHeaderEditor({
  projectId,
  learningTaskId,
  displayTitle,
  taskTitle,
}: {
  projectId: string
  learningTaskId: string
  displayTitle: string
  taskTitle: string
}) {
  const editTaskM = useEditLearningTask(projectId, learningTaskId)
  return (
    <TitleHeaderEditor
      id={`learningTaskTitle-${learningTaskId}`}
      displayTitle={displayTitle}
      titleValue={taskTitle}
      placeholder="请输入学习任务名称"
      pending={editTaskM.isPending}
      onSave={async (trimmedTitle) => {
        try {
          await editTaskM.mutateAsync(trimmedTitle)
          showSuccessFeedback("学习任务名称已更新", `当前任务现在显示为“${trimmedTitle}”。`)
          return true
        } catch (err) {
          showErrorFeedback("更新学习任务名称失败", formatApiError(err))
          return false
        }
      }}
    />
  )
}

function LearningTaskNodeTitleHeaderEditor({
  projectId,
  nodeId,
  displayTitle,
  nodeTitle,
}: {
  projectId: string
  nodeId: string
  displayTitle: string
  nodeTitle: string
}) {
  const editNodeM = useEditLearningTaskNode(projectId, nodeId)
  return (
    <TitleHeaderEditor
      id={`learningTaskNodeTitle-${nodeId}`}
      displayTitle={displayTitle}
      titleValue={nodeTitle}
      placeholder="请输入聚合节点名称"
      pending={editNodeM.isPending}
      onSave={async (trimmedTitle) => {
        try {
          await editNodeM.mutateAsync(trimmedTitle)
          showSuccessFeedback("聚合节点名称已更新", `当前节点现在显示为“${trimmedTitle}”。`)
          return true
        } catch (err) {
          showErrorFeedback("更新聚合节点名称失败", formatApiError(err))
          return false
        }
      }}
    />
  )
}

function TitleHeaderEditor({
  id,
  displayTitle,
  titleValue,
  placeholder,
  pending,
  onSave,
}: {
  id: string
  displayTitle: string
  titleValue: string
  placeholder: string
  pending: boolean
  onSave: (trimmedTitle: string) => Promise<boolean>
}) {
  const [titleDraft, setTitleDraft] = useState(titleValue)
  const [isEditing, setIsEditing] = useState(false)

  useEffect(() => {
    setTitleDraft(titleValue)
  }, [titleValue])

  const trimmedTitle = titleDraft.trim()
  const canSave = !!trimmedTitle && trimmedTitle !== titleValue.trim() && !pending

  function openEditor() {
    setTitleDraft(titleValue)
    setIsEditing(true)
  }

  function cancelEditor() {
    setTitleDraft(titleValue)
    setIsEditing(false)
  }

  async function handleSave() {
    if (!canSave) return
    const saved = await onSave(trimmedTitle)
    if (saved) setIsEditing(false)
  }

  if (!isEditing) {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="truncate text-lg font-semibold">{displayTitle}</h1>
        <Button type="button" size="sm" variant="outline" className="shrink-0 rounded-full" onClick={openEditor}>
          修改名称
        </Button>
      </div>
    )
  }

  return (
    <form
      className="flex flex-col gap-3"
      onSubmit={(event) => {
        event.preventDefault()
        void handleSave()
      }}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Input
          id={id}
          value={titleDraft}
          onChange={(event) => setTitleDraft(event.target.value)}
          placeholder={placeholder}
          disabled={pending}
          className="h-10 min-w-0 flex-1"
        />
        <div className="flex shrink-0 items-center gap-2">
          <Button type="button" variant="ghost" onClick={cancelEditor} disabled={pending}>
            取消
          </Button>
          <Button type="submit" disabled={!canSave}>
            {pending ? "保存中..." : "保存"}
          </Button>
        </div>
      </div>
    </form>
  )
}
