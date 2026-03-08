import { useQuery } from "@tanstack/react-query"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import {
  exportAsrByLearningTaskNode,
  exportRecallPointsByLearningTaskNode,
  listRecallPointsByLearningTaskNode,
} from "@/ui/api/learningTaskNodes"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { useLearningTaskNode, useLearningTaskNodeBinding } from "@/ui/queries/learningTasks"
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
  const recallPointsQ = useQuery({
    queryKey: ["recallPointsByTaskNode", pid, nid],
    queryFn: () => listRecallPointsByLearningTaskNode(pid, nid),
    enabled: !!pid && !!nid,
  })

  if (!pid || !nid) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">缺少 projectId 或 nodeId。</p>
        <Button onClick={() => navigate("/projects")}>返回项目列表</Button>
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

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">{title}</h1>
          <p className="text-sm text-muted-foreground">聚合节点或任务节点详情。</p>
        </div>
        <Button variant="outline" asChild>
          <Link to={`/p/${pid}/task-tree`}>返回学习任务树</Link>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>节点概览</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {nodeQ.isLoading ? <p className="text-sm text-muted-foreground">加载中...</p> : null}
          {nodeQ.error ? <p className="text-sm text-destructive">{formatApiError(nodeQ.error)}</p> : null}
          {bindingQ.error ? <p className="text-sm text-destructive">{formatApiError(bindingQ.error)}</p> : null}

          {nodeQ.data ? (
            <>
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">节点类型</div>
                  <div className="mt-1 font-medium text-foreground">{isContainer ? "聚合节点" : "学习任务"}</div>
                </div>
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">{isContainer ? "子节点数" : "目标层"}</div>
                  <div className="mt-1 font-medium text-foreground">
                    {isContainer
                      ? (childCount ?? 0)
                      : bindingQ.data?.targetLayerIndex === null || bindingQ.data == null
                        ? "-"
                        : `L${bindingQ.data.targetLayerIndex}`}
                  </div>
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
                {nodeQ.data.kind === "leaf" && nodeQ.data.boundLearningTaskId ? (
                  <Button variant="outline" asChild>
                    <Link to={`/p/${pid}/learning-tasks/${nodeQ.data.boundLearningTaskId}`}>查看学习任务</Link>
                  </Button>
                ) : null}
              </div>
            </>
          ) : null}
        </CardContent>
      </Card>

      <RecallPointListCard
        projectId={pid}
        items={recallPointsQ.data ?? []}
        isLoading={recallPointsQ.isLoading}
        error={recallPointsQ.error}
        title="复述点列表"
        description="该学习任务节点覆盖到的复述点会直接显示在这里。"
      />

      <NodeExportCard
        projectId={pid}
        nodeTitle={title}
        recallPoints={recallPointsQ.data ?? []}
        exportRecallPoints={() => exportRecallPointsByLearningTaskNode(pid, nid)}
        exportAsr={() => exportAsrByLearningTaskNode(pid, nid)}
      />
    </div>
  )
}
