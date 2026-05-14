import { useCallback, useMemo } from "react"
import { useQueries, useQuery } from "@tanstack/react-query"
import { FileVideoCamera } from "lucide-react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { listInstances, listRecallPointsByInstance } from "@/ui/api/instances"
import { listLearningObjectNodes } from "@/ui/api/learningObjects"
import type { ScopedProjectRef } from "@/ui/api/projectScope"
import { getRecallPoint, type RecallPoint } from "@/ui/api/review"
import { ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { buildScopedProjectPath } from "@/ui/projectPaths"
import { RecallPointListCard } from "@/views/recallPoints/components/RecallPointListCard"
import { DetailSummaryCard } from "@/views/shared/DetailSummaryCard"
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
  const { subjectId = "", scopedProjectId, instanceId } = useParams()
  const navigate = useNavigate()
  const pid = scopedProjectId ?? ""
  const iid = instanceId ?? ""
  const projectScope: ScopedProjectRef | null = subjectId && pid ? { subjectId, scopedProjectId: pid } : null
  const setCurrentMs = useCallback(() => undefined, [])

  const instancesQ = useQuery({
    queryKey: ["instances", subjectId, pid],
    queryFn: () => listInstances(projectScope as ScopedProjectRef),
    enabled: !!projectScope,
  })

  const objectNodesQ = useQuery({
    queryKey: ["learningObjectNodes", subjectId, pid],
    queryFn: () => listLearningObjectNodes(projectScope as ScopedProjectRef),
    enabled: !!projectScope,
  })

  const recallPointIdsQ = useQuery({
    queryKey: ["recallPointsByInstance", subjectId, pid, iid],
    queryFn: () => listRecallPointsByInstance(projectScope as ScopedProjectRef, iid),
    enabled: !!projectScope && !!iid,
  })
  const recallPointQs = useQueries({
    queries: (recallPointIdsQ.data?.recallPointIds ?? []).map((recallPointId) => ({
      queryKey: ["recallPoint", subjectId, pid, recallPointId],
      queryFn: () => getRecallPoint(projectScope as ScopedProjectRef, recallPointId),
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
  const summaryPanel = instance ? (
    <div className="space-y-3">
      <DetailSummaryCard
        icon={FileVideoCamera}
        title={instance.materialDisplayName}
        items={[
          { label: "状态", value: instance.presence === "MISSING" ? "缺失" : "正常" },
          { label: "复述点", value: recallPointIdsQ.data?.recallPointIds.length ?? "-" },
          { label: "最近看到", value: formatTimestamp(instance.lastSeenAt) },
        ]}
      />
      {boundObjectNode ? (
        <Button variant="outline" className="w-full rounded-full" asChild>
          <Link to={buildScopedProjectPath(subjectId, pid, `/learning-object-nodes/${boundObjectNode.nodeId}`)}>查看对象节点</Link>
        </Button>
      ) : objectNodesQ.isLoading ? (
        <Button variant="outline" className="w-full rounded-full" disabled>
          读取对象节点中...
        </Button>
      ) : null}
    </div>
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
              surface="detail"
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
