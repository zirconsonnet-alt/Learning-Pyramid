import { useCallback, useMemo, type ReactNode } from "react"
import { useQueries, useQuery } from "@tanstack/react-query"
import { ChevronLeft } from "lucide-react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { listInstances, listRecallPointsByInstance } from "@/ui/api/instances"
import { listLearningObjectNodes } from "@/ui/api/learningObjects"
import type { ProjectScope } from "@/ui/api/projectScope"
import { getRecallPoint, type RecallPoint } from "@/ui/api/review"
import { ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader } from "@/ui/components/ui/card"
import { formatInstanceReference, formatMaterialReference } from "@/ui/displayIdentifiers"
import { buildScopedProjectPath } from "@/ui/projectPaths"
import { RecallPointListCard } from "@/views/recallPoints/components/RecallPointListCard"
import { VideoPane } from "@/views/workbench/components/VideoPane"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function formatTimestamp(value: string | null) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", { hour12: false })
}

export function InstancePage() {
  const { subjectId = "", projectId, instanceId } = useParams()
  const navigate = useNavigate()
  const pid = projectId ?? ""
  const iid = instanceId ?? ""
  const projectScope: ProjectScope | null = subjectId && pid ? { subjectId, projectId: pid } : null
  const setCurrentMs = useCallback(() => undefined, [])

  const instancesQ = useQuery({
    queryKey: ["instances", subjectId, pid],
    queryFn: () => listInstances(projectScope as ProjectScope),
    enabled: !!projectScope,
  })

  const objectNodesQ = useQuery({
    queryKey: ["learningObjectNodes", subjectId, pid],
    queryFn: () => listLearningObjectNodes(projectScope as ProjectScope),
    enabled: !!projectScope,
  })

  const recallPointIdsQ = useQuery({
    queryKey: ["recallPointsByInstance", subjectId, pid, iid],
    queryFn: () => listRecallPointsByInstance(projectScope as ProjectScope, iid),
    enabled: !!projectScope && !!iid,
  })
  const recallPointQs = useQueries({
    queries: (recallPointIdsQ.data?.recallPointIds ?? []).map((recallPointId) => ({
      queryKey: ["recallPoint", subjectId, pid, recallPointId],
      queryFn: () => getRecallPoint(projectScope as ProjectScope, recallPointId),
      enabled: !!projectScope && !!recallPointId,
    })),
  })

  const instance = useMemo(
    () => (instancesQ.data ?? []).find((item) => item.instanceId === iid) ?? null,
    [iid, instancesQ.data],
  )

  const boundObjectNode = useMemo(() => {
    return (
      (objectNodesQ.data ?? []).find((node) => node.kind === "leaf" && node.instanceId === iid) ?? null
    )
  }, [iid, objectNodesQ.data])
  const recallPoints = useMemo(
    () => recallPointQs.map((query) => query.data).filter((item): item is RecallPoint => !!item),
    [recallPointQs],
  )
  const instanceTitleById = useMemo(
    () =>
      Object.fromEntries(
        (instancesQ.data ?? []).map((item) => [item.instanceId, item.materialDisplayName]),
      ) as Record<string, string>,
    [instancesQ.data],
  )
  const recallPointsLoading = recallPointIdsQ.isLoading || recallPointQs.some((query) => query.isLoading)
  const recallPointsError = recallPointIdsQ.error ?? recallPointQs.find((query) => query.error)?.error ?? null
  const boundObjectNodeValue = boundObjectNode ? (
    <Link className="text-primary underline-offset-4 hover:underline" to={buildScopedProjectPath(subjectId, pid, `/learning-object-nodes/${boundObjectNode.nodeId}`)}>
      {boundObjectNode.title}
    </Link>
  ) : objectNodesQ.isLoading ? (
    "读取中..."
  ) : (
    "未绑定对象节点"
  )
  const backAction = (
    <Button
      variant="ghost"
      size="sm"
      className="-ml-2 h-8 rounded-full px-2 text-[#60748c] hover:bg-[#f3f7fb] hover:text-foreground"
      asChild
    >
      <Link to={buildScopedProjectPath(subjectId, pid, "/structure-view?view=object")}>
        <ChevronLeft className="h-4 w-4" />
        返回学习对象树
      </Link>
    </Button>
  )
  const summaryPanel = instance ? (
    <InstanceSummaryCard
      topAction={backAction}
      header={<h1 className="truncate text-lg font-semibold">{instance.materialDisplayName}</h1>}
      description="查看这个内容实例的播放、对象树绑定与复述点引用。"
      items={[
        { label: "状态", value: instance.presence === "MISSING" ? "缺失" : "正常" },
        { label: "当前引用", value: formatInstanceReference(iid) },
        { label: "复述点", value: recallPointIdsQ.data?.recallPointIds.length ?? "-" },
        { label: "内容引用", value: formatMaterialReference(instance.materialId) },
        { label: "最近看到", value: formatTimestamp(instance.lastSeenAt) },
        { label: "对象树绑定", value: boundObjectNodeValue },
      ]}
    />
  ) : null

  if (!pid || !iid) {
    return (
      <div className="space-y-4">
        <ContentNotice
          title="当前页面缺少实例上下文"
          message="当前链接缺少实例信息。请先返回项目列表，再从对象树或实例入口重新进入。"
          action={<Button onClick={() => navigate("/subjects")}>返回学科中心</Button>}
        />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {instancesQ.isLoading ? <LoadingNotice title="正在加载实例详情" message="正在读取内容实例、对象树绑定和复述点引用情况。" /> : null}
      {instancesQ.error ? <ErrorNotice title="实例详情加载失败" message={formatApiError(instancesQ.error)} /> : null}
      {objectNodesQ.error ? <ErrorNotice title="对象树绑定加载失败" message={formatApiError(objectNodesQ.error)} /> : null}
      {recallPointIdsQ.error ? <ErrorNotice title="复述点引用加载失败" message={formatApiError(recallPointIdsQ.error)} /> : null}

      {!instancesQ.isLoading && !instancesQ.error && !instance ? (
        <ContentNotice
          title="未找到这个实例"
          message="这个实例可能已经被移除，或当前入口已失效。请返回对象树重新选择。"
          action={
            <Button variant="outline" asChild>
              <Link to={buildScopedProjectPath(subjectId, pid, "/structure-view?view=object")}>返回学习对象树</Link>
            </Button>
          }
        />
      ) : null}

      {instance ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)] xl:items-start">
          {summaryPanel ? <aside className="xl:sticky xl:top-28 xl:self-start">{summaryPanel}</aside> : <div />}
          <div className="min-w-0 space-y-4">
            <VideoPane
              key={instance.instanceId}
              subjectId={subjectId}
              projectId={pid}
              instance={instance}
              setCurrentMs={setCurrentMs}
              queueHasGate={false}
              allowCaptureDrafts={false}
            />
            <RecallPointListCard
              subjectId={subjectId}
              projectId={pid}
              items={recallPoints}
              instanceTitleById={instanceTitleById}
              isLoading={recallPointsLoading}
              error={recallPointsError}
              title="相关复述点"
              description="所有锚定到这个实例的复述点都会显示在这里。"
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

function InstanceSummaryCard({
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
              <div className="mt-1.5 break-words text-sm font-semibold text-slate-900">{item.value}</div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
