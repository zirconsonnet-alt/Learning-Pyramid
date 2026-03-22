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
  const learningTaskId = nodeQ.data?.kind === "leaf" ? nodeQ.data.boundLearningTaskId : ""
  const learningTaskQ = useLearningTask(pid, learningTaskId)
  const pageDescription = isContainer ? "聚合节点详情。" : "学习任务详情。"

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
        <Card>
          <CardHeader>
            <CardTitle>节点概览</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="text-xs text-muted-foreground">节点类型</div>
                <div className="mt-1 font-medium text-foreground">聚合节点</div>
              </div>
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="text-xs text-muted-foreground">子节点数</div>
                <div className="mt-1 font-medium text-foreground">{childCount ?? 0}</div>
              </div>
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="text-xs text-muted-foreground">节点标题</div>
                <div className="mt-1 font-medium text-foreground">
                  {formatLearningTaskNodeDisplayTitle(nodeQ.data.title, { sourceLayerIndex })}
                </div>
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              {bindingQ.data?.reviewChainId ? (
                <Button asChild>
                  <Link to={`/p/${pid}/review-chains/${bindingQ.data.reviewChainId}`}>查看复习链</Link>
                </Button>
              ) : null}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {!isContainer && learningTaskId ? (
        <>
          <LeafLearningTaskCard
            projectId={pid}
            learningTaskId={learningTaskId}
            learningTaskQ={learningTaskQ}
            reviewChainId={bindingQ.data?.reviewChainId ?? null}
          />
        </>
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
  reviewChainId: string | null
}) {
  const { projectId, learningTaskId, learningTaskQ, reviewChainId } = props

  return (
    <Card>
      <CardHeader>
        <CardTitle>学习任务信息</CardTitle>
        <CardDescription>这里只保留任务规模、所在层和复习链这些真正有判断价值的信息。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {learningTaskQ.isLoading ? <LoadingNotice title="正在加载学习任务" message="正在读取这个叶子节点绑定的学习任务。" /> : null}
        {learningTaskQ.error ? <ErrorNotice title="学习任务加载失败" message={formatApiError(learningTaskQ.error)} /> : null}
        {learningTaskQ.data ? (
          <>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="text-xs text-muted-foreground">复述点数量</div>
                <div className="mt-1 font-medium text-foreground">{learningTaskQ.data.size}</div>
              </div>
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="text-xs text-muted-foreground">所在层</div>
                <div className="mt-1 font-medium text-foreground">
                  {learningTaskQ.data.targetLayerIndex === null ? "-" : `L${learningTaskQ.data.targetLayerIndex}`}
                </div>
              </div>
            </div>

            {reviewChainId ? (
              <div className="flex flex-wrap gap-3">
                <Button asChild>
                  <Link to={`/p/${projectId}/review-chains/${reviewChainId}`}>查看复习链</Link>
                </Button>
              </div>
            ) : null}

            <LearningTaskTitleEditor
              projectId={projectId}
              learningTaskId={learningTaskId}
              taskTitle={learningTaskQ.data.title}
            />
          </>
        ) : null}
      </CardContent>
    </Card>
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
      className="grid gap-3 rounded-md border p-4 md:grid-cols-[minmax(0,1fr)_auto]"
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
        <Label htmlFor={`learningTaskTitle-${learningTaskId}`}>重命名学习任务</Label>
        <Input
          id={`learningTaskTitle-${learningTaskId}`}
          value={titleDraft}
          onChange={(event) => setTitleDraft(event.target.value)}
          placeholder="请输入学习任务名称"
          disabled={editTaskM.isPending}
        />
      </div>
      <div className="flex items-end">
        <Button type="submit" disabled={!canSave}>
          {editTaskM.isPending ? "保存中..." : "保存任务名称"}
        </Button>
      </div>
    </form>
  )
}
