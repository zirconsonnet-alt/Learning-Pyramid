import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import {
  exportAsrByLearningTaskNode,
  exportRecallPointsByLearningTaskNode,
  listRecallPointsByLearningTaskNode,
} from "@/ui/api/learningTaskNodes"
import { ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useEditLearningTask, useLearningTask, useLearningTaskNode, useLearningTaskNodeBinding } from "@/ui/queries/learningTasks"
import { useInstances } from "@/ui/queries/workbench"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { formatLearningTaskNodeDisplayTitle } from "@/views/learningTasks/displayTitle"
import { RecallPointListCard } from "@/views/recallPoints/components/RecallPointListCard"
import { DetailSummaryCard } from "@/views/shared/DetailSummaryCard"
import { NodeExportCard } from "@/views/shared/NodeExportCard"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
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
  const childCount = nodeQ.data?.kind === "container" ? nodeQ.data.children.length : null
  const instanceTitleById = Object.fromEntries((instancesQ.data ?? []).map((instance) => [instance.instanceId, instance.materialDisplayName])) as Record<string, string>
  const pageDescription = isContainer ? "聚合节点详情。" : "学习任务详情。"
  const relatedInstanceLabel = (() => {
    const ids = Array.from(new Set((recallPointsQ.data ?? []).map((item) => item.anchor.instanceId)))
    if (ids.length === 0) return "未关联视频"
    if (ids.length === 1) return instanceTitleById[ids[0]] ?? "关联视频"
    return `${ids.length} 个关联视频`
  })()

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">{title}</h1>
          <p className="text-sm text-muted-foreground">{pageDescription}</p>
        </div>
        <Button variant="outline" asChild>
          <Link to={`/p/${pid}/task-tree`}>返回学习任务树</Link>
        </Button>
      </div>

      {nodeQ.isLoading ? <LoadingNotice title="正在加载任务节点" message="正在读取这个节点的层级、子节点和关联任务信息。" /> : null}
      {nodeQ.error ? <ErrorNotice title="任务节点加载失败" message={formatApiError(nodeQ.error)} /> : null}
      {bindingQ.error ? <ErrorNotice title="节点绑定加载失败" message={formatApiError(bindingQ.error)} /> : null}
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

      {nodeQ.data && isContainer ? (
        <DetailSummaryCard
          title="节点摘要"
          description="先确认这个聚合节点覆盖的规模，再继续查看下方的复述点。"
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
      ) : null}

      {!isContainer && learningTaskId ? (
        <LeafLearningTaskCard
          projectId={pid}
          learningTaskId={learningTaskId}
          learningTaskQ={learningTaskQ}
          relatedInstanceLabel={relatedInstanceLabel}
          reviewChainId={bindingQ.data?.reviewChainId ?? null}
        />
      ) : null}

      <RecallPointListCard
        projectId={pid}
        items={recallPointsQ.data ?? []}
        instanceTitleById={instanceTitleById}
        isLoading={recallPointsQ.isLoading}
        error={recallPointsQ.error}
        title="复述点列表"
        description="这个任务节点关联的复述点会显示在这里。"
      />

      {nodeQ.data ? (
        <NodeExportCard
          projectId={pid}
          nodeTitle={title}
          recallPoints={recallPointsQ.data ?? []}
          exportRecallPoints={() => exportRecallPointsByLearningTaskNode(pid, nid)}
          exportAsr={() => exportAsrByLearningTaskNode(pid, nid)}
        />
      ) : null}
    </div>
  )
}

function LeafLearningTaskCard(props: {
  projectId: string
  learningTaskId: string
  learningTaskQ: ReturnType<typeof useLearningTask>
  relatedInstanceLabel: string
  reviewChainId: string | null
}) {
  const { projectId, learningTaskId, learningTaskQ, relatedInstanceLabel, reviewChainId } = props

  return (
    <div className="space-y-4">
      <DetailSummaryCard
        title="任务摘要"
        description="先快速扫清这个任务的规模和上下文，再决定是改名、看复习关系，还是继续处理复述点。"
        items={[
          { label: "复述点", value: learningTaskQ.data?.size ?? "-" },
          {
            label: "层级",
            value: learningTaskQ.data?.targetLayerIndex === null || learningTaskQ.data == null ? "-" : `L${learningTaskQ.data.targetLayerIndex}`,
          },
          { label: "关联视频", value: relatedInstanceLabel },
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

      <Card>
        <CardHeader className="pb-3">
          <CardTitle>任务名称</CardTitle>
          <CardDescription>修改后会同步体现在任务树与相关入口里。</CardDescription>
        </CardHeader>
        <CardContent>
          {learningTaskQ.isLoading ? <LoadingNotice title="正在加载学习任务" message="正在读取这个叶子节点绑定的学习任务。" /> : null}
          {learningTaskQ.error ? <ErrorNotice title="学习任务加载失败" message={formatApiError(learningTaskQ.error)} /> : null}
          {learningTaskQ.data ? (
            <LearningTaskTitleEditor
              projectId={projectId}
              learningTaskId={learningTaskId}
              taskTitle={learningTaskQ.data.title}
            />
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}

function LearningTaskTitleEditor({
  projectId,
  learningTaskId,
  taskTitle,
}: {
  projectId: string
  learningTaskId: string
  taskTitle: string
}) {
  const [titleDraft, setTitleDraft] = useState(taskTitle)
  const editTaskM = useEditLearningTask(projectId, learningTaskId)

  useEffect(() => {
    setTitleDraft(taskTitle)
  }, [taskTitle])

  const trimmedTitle = titleDraft.trim()
  const canSave = !!trimmedTitle && trimmedTitle !== taskTitle.trim() && !editTaskM.isPending

  return (
    <form
      className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]"
      onSubmit={(event) => {
        event.preventDefault()
        if (!canSave) return
        void editTaskM
          .mutateAsync(trimmedTitle)
          .then(() => {
            showSuccessFeedback("学习任务名称已更新", `当前任务现在显示为“${trimmedTitle}”。`)
          })
          .catch((err) => {
            showErrorFeedback("更新学习任务名称失败", formatApiError(err))
          })
      }}
    >
      <div className="space-y-2">
        <Label htmlFor={`learningTaskTitle-${learningTaskId}`}>当前名称</Label>
        <Input
          id={`learningTaskTitle-${learningTaskId}`}
          value={titleDraft}
          onChange={(event) => setTitleDraft(event.target.value)}
          placeholder="请输入学习任务名称"
          disabled={editTaskM.isPending}
        />
      </div>
      <div className="flex items-end">
        <Button type="submit" disabled={!canSave} variant={canSave ? "default" : "secondary"}>
          {editTaskM.isPending ? "保存中..." : "保存任务名称"}
        </Button>
      </div>
    </form>
  )
}
