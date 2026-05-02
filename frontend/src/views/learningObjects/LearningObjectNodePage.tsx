import { useMemo, type ReactNode } from "react"
import { useQuery } from "@tanstack/react-query"
import { ChevronLeft, Sparkles } from "lucide-react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { listInstances } from "@/ui/api/instances"
import {
  exportRecallPointsByLearningObjectNode,
  getLearningObjectNode,
  listLearningObjectNodes,
  listRecallPointsByLearningObjectNode,
} from "@/ui/api/learningObjects"
import { ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader } from "@/ui/components/ui/card"
import { buildAiChatPath } from "@/views/ai/chatRouting"
import { RecallPointListCard } from "@/views/recallPoints/components/RecallPointListCard"
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
  const backToObjectTreeAction = (
    <Button
      variant="ghost"
      size="sm"
      className="-ml-2 h-8 rounded-full px-2 text-[#60748c] hover:bg-[#f3f7fb] hover:text-foreground"
      asChild
    >
      <Link to={`/p/${pid}/object-tree`}>
        <ChevronLeft className="h-4 w-4" />
        返回学习对象树
      </Link>
    </Button>
  )
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
              <Link className="text-primary underline-offset-4 hover:underline" to={`/p/${pid}/instances/${boundInstance.instanceId}`}>
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
      <LearningObjectSummaryCard
        topAction={backToObjectTreeAction}
        header={<h1 className="truncate text-lg font-semibold">{title}</h1>}
        items={summaryItems}
      />

      <Button asChild className="w-full">
        <Link to={buildAiChatPath(pid, { kind: "object", nodeId: nid })}>
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
              <Link to={`/p/${pid}/object-tree`}>返回学习对象树</Link>
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
                  exportRecallPoints={() => exportRecallPointsByLearningObjectNode(pid, nid)}
                />
              }
            />
          </div>
        </div>
      ) : null}
    </div>
  )
}

type SummaryItem = {
  label: string
  value: ReactNode
}

function LearningObjectSummaryCard({
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
