import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { listInstances } from "@/ui/api/instances"
import {
  exportAsrByLearningObjectNode,
  exportRecallPointsByLearningObjectNode,
  getLearningObjectNode,
  listLearningObjectNodes,
  listRecallPointsByLearningObjectNode,
} from "@/ui/api/learningObjects"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { RecallPointListCard } from "@/views/recallPoints/components/RecallPointListCard"
import { NodeExportCard } from "@/views/shared/NodeExportCard"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function formatNodeType(kind: "leaf" | "container", depth: number) {
  if (kind === "leaf") return "材料节点"
  if (depth === 0) return "根目录"
  return "分组节点"
}

export function LearningObjectNodePage() {
  const { projectId, nodeId } = useParams()
  const navigate = useNavigate()
  const pid = projectId ?? ""
  const nid = nodeId ?? ""

  const nodeQ = useQuery({
    queryKey: ["learningObjectNode", pid, nid],
    queryFn: () => getLearningObjectNode(pid, nid),
    enabled: !!pid && !!nid,
  })

  const nodesQ = useQuery({
    queryKey: ["learningObjectNodes", pid],
    queryFn: () => listLearningObjectNodes(pid),
    enabled: !!pid,
  })

  const instancesQ = useQuery({
    queryKey: ["instances", pid],
    queryFn: () => listInstances(pid),
    enabled: !!pid,
  })
  const recallPointsQ = useQuery({
    queryKey: ["recallPointsByObjectNode", pid, nid],
    queryFn: () => listRecallPointsByLearningObjectNode(pid, nid),
    enabled: !!pid && !!nid,
  })

  const depth = useMemo(() => {
    const nodes = nodesQ.data ?? []
    const nodeById = Object.fromEntries(nodes.map((node) => [node.nodeId, node]))
    const seen = new Set<string>()
    let current = nodeById[nid]
    let value = 0
    while (current?.parentId) {
      if (seen.has(current.nodeId)) break
      seen.add(current.nodeId)
      current = nodeById[current.parentId]
      value += 1
    }
    return value
  }, [nid, nodesQ.data])

  const boundInstance = useMemo(() => {
    const node = nodeQ.data
    if (!node || node.kind !== "leaf") return null
    return (instancesQ.data ?? []).find((instance) => instance.instanceId === node.instanceId) ?? null
  }, [instancesQ.data, nodeQ.data])

  if (!pid || !nid) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">缺少 projectId 或 nodeId。</p>
        <Button onClick={() => navigate("/projects")}>返回项目列表</Button>
      </div>
    )
  }

  const title = nodeQ.data?.title?.trim() || "学习对象节点"
  const isContainer = nodeQ.data?.kind === "container"

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">{title}</h1>
          <p className="text-sm text-muted-foreground">学习对象节点详情。</p>
        </div>
        <Button variant="outline" asChild>
          <Link to={`/p/${pid}/object-tree`}>返回学习对象树</Link>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>节点概览</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {nodeQ.isLoading ? <p className="text-sm text-muted-foreground">加载中...</p> : null}
          {nodeQ.error ? <p className="text-sm text-destructive">{formatApiError(nodeQ.error)}</p> : null}
          {nodesQ.error ? <p className="text-sm text-destructive">{formatApiError(nodesQ.error)}</p> : null}
          {instancesQ.error ? <p className="text-sm text-destructive">{formatApiError(instancesQ.error)}</p> : null}

          {nodeQ.data ? (
            <>
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">节点类型</div>
                  <div className="mt-1 font-medium text-foreground">{formatNodeType(nodeQ.data.kind, depth)}</div>
                </div>
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">{isContainer ? "子节点数" : "树深度"}</div>
                  <div className="mt-1 font-medium text-foreground">
                    {nodeQ.data.kind === "container" ? nodeQ.data.children.length : `D${depth}`}
                  </div>
                </div>
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">节点标题</div>
                  <div className="mt-1 font-medium text-foreground">{nodeQ.data.title || "未命名节点"}</div>
                </div>
              </div>

              {boundInstance ? (
                <div className="grid gap-3 md:grid-cols-3">
                  <div className="rounded-md border bg-muted/30 p-3">
                    <div className="text-xs text-muted-foreground">材料名</div>
                    <div className="mt-1 font-medium text-foreground">{boundInstance.materialDisplayName}</div>
                  </div>
                  <div className="rounded-md border bg-muted/30 p-3">
                    <div className="text-xs text-muted-foreground">材料状态</div>
                    <div className="mt-1 font-medium text-foreground">{boundInstance.presence === "MISSING" ? "缺失" : "正常"}</div>
                  </div>
                  <div className="rounded-md border bg-muted/30 p-3">
                    <div className="text-xs text-muted-foreground">instanceId</div>
                    <div className="mt-1 break-all font-medium text-foreground">{boundInstance.instanceId}</div>
                  </div>
                </div>
              ) : null}

              <div className="flex flex-wrap gap-3">
                {boundInstance ? (
                  <Button variant="outline" asChild>
                    <Link to={`/p/${pid}/instances/${boundInstance.instanceId}`}>查看实例</Link>
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
        description="该学习对象节点覆盖到的复述点会直接显示在这里。"
      />

      <NodeExportCard
        projectId={pid}
        nodeTitle={title}
        recallPoints={recallPointsQ.data ?? []}
        exportRecallPoints={() => exportRecallPointsByLearningObjectNode(pid, nid)}
        exportAsr={() => exportAsrByLearningObjectNode(pid, nid)}
      />
    </div>
  )
}
