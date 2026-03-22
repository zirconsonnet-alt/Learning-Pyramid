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
import { ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { formatInstanceReference } from "@/ui/displayIdentifiers"
import { RecallPointListCard } from "@/views/recallPoints/components/RecallPointListCard"
import { DetailSummaryCard } from "@/views/shared/DetailSummaryCard"
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
  const instanceTitleById = useMemo(
    () =>
      Object.fromEntries(
        (instancesQ.data ?? []).map((instance) => [instance.instanceId, instance.materialDisplayName]),
      ) as Record<string, string>,
    [instancesQ.data],
  )

  if (!pid || !nid) {
    return (
      <div className="space-y-4">
        <ContentNotice
          title="当前页面缺少对象节点上下文"
          message="当前链接缺少对象节点评息。请先返回项目列表，再从学习对象树重新进入。"
          action={<Button onClick={() => navigate("/projects")}>返回项目列表</Button>}
        />
      </div>
    )
  }

  const title = nodeQ.data?.title?.trim() || "学习对象节点"
  const summaryItems = nodeQ.data
    ? nodeQ.data.kind === "container"
      ? [
          { label: "节点类型", value: formatNodeType(nodeQ.data.kind, depth) },
          { label: "子节点数", value: nodeQ.data.children.length },
          { label: "层级深度", value: `D${depth}` },
        ]
      : [
          { label: "节点类型", value: formatNodeType(nodeQ.data.kind, depth) },
          { label: "材料名", value: boundInstance?.materialDisplayName ?? "未绑定实例" },
          { label: "材料状态", value: boundInstance ? (boundInstance.presence === "MISSING" ? "缺失" : "正常") : "未知" },
          {
            label: "实例入口",
            value: boundInstance ? (
              <Link className="text-primary underline-offset-4 hover:underline" to={`/p/${pid}/instances/${boundInstance.instanceId}`}>
                查看实例
              </Link>
            ) : (
              "暂不可用"
            ),
          },
        ]
    : []

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

      {nodeQ.isLoading ? <LoadingNotice title="正在加载对象节点" message="正在读取这个节点的结构信息、绑定实例和覆盖范围。" /> : null}
      {nodeQ.error ? <ErrorNotice title="对象节点加载失败" message={formatApiError(nodeQ.error)} /> : null}
      {nodesQ.error ? <ErrorNotice title="对象树结构加载失败" message={formatApiError(nodesQ.error)} /> : null}
      {instancesQ.error ? <ErrorNotice title="实例信息加载失败" message={formatApiError(instancesQ.error)} /> : null}
      {!nodeQ.isLoading && !nodeQ.error && !nodeQ.data ? (
        <ContentNotice
          title="未找到这个对象节点"
          message="这个对象节点可能已经被重建或移除。你可以返回学习对象树重新选择。"
          action={
            <Button variant="outline" asChild>
              <Link to={`/p/${pid}/object-tree`}>返回学习对象树</Link>
            </Button>
          }
        />
      ) : null}

      {nodeQ.data ? (
        <>
          <DetailSummaryCard
            title="节点摘要"
            description="先确认这是哪类对象节点、覆盖了什么材料，再继续查看下方的复述点。"
            items={summaryItems}
          />

          {boundInstance ? (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle>实例引用</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="rounded-xl border border-[#dbe4ee] bg-[#f8fafc] px-4 py-3 text-sm text-slate-700">
                  当前节点绑定实例：<span className="font-medium text-slate-900">{formatInstanceReference(boundInstance.instanceId)}</span>
                </div>
              </CardContent>
            </Card>
          ) : null}
        </>
      ) : null}

      <RecallPointListCard
        projectId={pid}
        items={recallPointsQ.data ?? []}
        instanceTitleById={instanceTitleById}
        isLoading={recallPointsQ.isLoading}
        error={recallPointsQ.error}
        title="复述点列表"
        description="这个对象节点关联的复述点会显示在这里。"
      />

      {nodeQ.data ? (
        <NodeExportCard
          projectId={pid}
          nodeTitle={title}
          recallPoints={recallPointsQ.data ?? []}
          exportRecallPoints={() => exportRecallPointsByLearningObjectNode(pid, nid)}
          exportAsr={() => exportAsrByLearningObjectNode(pid, nid)}
        />
      ) : null}
    </div>
  )
}
