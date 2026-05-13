import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { Boxes, Sparkles } from "lucide-react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { listInstances } from "@/ui/api/instances"
import {
  exportRecallPointsByLearningObjectNode,
  getLearningObjectNode,
  listLearningObjectNodes,
  listRecallPointsByLearningObjectNode,
} from "@/ui/api/learningObjects"
import type { ScopedProjectRef } from "@/ui/api/projectScope"
import { ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { buildScopedProjectPath } from "@/ui/projectPaths"
import { buildAiChatPath } from "@/views/ai/chatRouting"
import { RecallPointListCard } from "@/views/recallPoints/components/RecallPointListCard"
import { DetailSummaryCard } from "@/views/shared/DetailSummaryCard"
import { NodeExportCard } from "@/views/shared/NodeExportCard"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function formatNodeType(kind: "leaf" | "container", depth: number) {
  if (kind === "leaf") return "内容节点"
  if (depth === 0) return "根目录"
  return "分组节点"
}

export function LearningObjectNodePage() {
  const { subjectId = "", scopedProjectId, nodeId } = useParams()
  const navigate = useNavigate()
  const pid = scopedProjectId ?? ""
  const nid = nodeId ?? ""
  const projectScope: ScopedProjectRef | null = subjectId && pid ? { subjectId, scopedProjectId: pid } : null

  const nodeQ = useQuery({
    queryKey: ["learningObjectNode", subjectId, pid, nid],
    queryFn: () => getLearningObjectNode(projectScope as ScopedProjectRef, nid),
    enabled: !!projectScope && !!nid,
  })

  const nodesQ = useQuery({
    queryKey: ["learningObjectNodes", subjectId, pid],
    queryFn: () => listLearningObjectNodes(projectScope as ScopedProjectRef),
    enabled: !!projectScope,
  })

  const instancesQ = useQuery({
    queryKey: ["instances", subjectId, pid],
    queryFn: () => listInstances(projectScope as ScopedProjectRef),
    enabled: !!projectScope,
  })
  const recallPointsQ = useQuery({
    queryKey: ["recallPointsByObjectNode", subjectId, pid, nid],
    queryFn: () => listRecallPointsByLearningObjectNode(projectScope as ScopedProjectRef, nid),
    enabled: !!projectScope && !!nid,
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
          action={<Button onClick={() => navigate("/subjects")}>返回学科中心</Button>}
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
          { label: "内容名", value: boundInstance?.materialDisplayName ?? "未绑定实例" },
          { label: "内容状态", value: boundInstance ? (boundInstance.presence === "MISSING" ? "缺失" : "正常") : "未知" },
          {
            label: "实例入口",
            value: boundInstance ? (
              <Link className="text-primary underline-offset-4 hover:underline" to={buildScopedProjectPath(subjectId, pid, `/instances/${boundInstance.instanceId}`)}>
                查看实例
              </Link>
            ) : (
              "暂不可用"
            ),
          },
        ]
    : []
  const summaryPanel = nodeQ.data ? (
    <div className="space-y-4">
      <DetailSummaryCard
        icon={Boxes}
        title={title}
        items={summaryItems}
      />

      <Button asChild className="w-full">
        <Link to={buildAiChatPath(subjectId, pid, { kind: "object", nodeId: nid })}>
          <Sparkles className="h-4 w-4" />
          AI问答
        </Link>
      </Button>
    </div>
  ) : null

  return (
    <div className="space-y-4">
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
              <Link to={buildScopedProjectPath(subjectId, pid, "/structure-view?view=object")}>返回学习对象树</Link>
            </Button>
          }
        />
      ) : null}

      {nodeQ.data ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)] xl:items-start">
          {summaryPanel ? <aside className="xl:sticky xl:top-28 xl:self-start">{summaryPanel}</aside> : <div />}
          <div className="min-w-0">
            <RecallPointListCard
              subjectId={subjectId}
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
                  exportRecallPoints={() => exportRecallPointsByLearningObjectNode(projectScope as ScopedProjectRef, nid)}
                />
              }
            />
          </div>
        </div>
      ) : null}
    </div>
  )
}
