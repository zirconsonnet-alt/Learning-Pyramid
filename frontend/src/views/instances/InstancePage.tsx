import { useMemo } from "react"
import { useQueries, useQuery } from "@tanstack/react-query"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { listInstances, listRecallPointsByInstance } from "@/ui/api/instances"
import { listLearningObjectNodes } from "@/ui/api/learningObjects"
import { getRecallPoint, type RecallPoint } from "@/ui/api/review"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { RecallPointListCard } from "@/views/recallPoints/components/RecallPointListCard"

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
  const { projectId, instanceId } = useParams()
  const navigate = useNavigate()
  const pid = projectId ?? ""
  const iid = instanceId ?? ""

  const instancesQ = useQuery({
    queryKey: ["instances", pid],
    queryFn: () => listInstances(pid),
    enabled: !!pid,
  })

  const objectNodesQ = useQuery({
    queryKey: ["learningObjectNodes", pid],
    queryFn: () => listLearningObjectNodes(pid),
    enabled: !!pid,
  })

  const recallPointIdsQ = useQuery({
    queryKey: ["recallPointsByInstance", pid, iid],
    queryFn: () => listRecallPointsByInstance(pid, iid),
    enabled: !!pid && !!iid,
  })
  const recallPointQs = useQueries({
    queries: (recallPointIdsQ.data?.recallPointIds ?? []).map((recallPointId) => ({
      queryKey: ["recallPoint", pid, recallPointId],
      queryFn: () => getRecallPoint(pid, recallPointId),
      enabled: !!pid && !!recallPointId,
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
  const recallPointsLoading = recallPointIdsQ.isLoading || recallPointQs.some((query) => query.isLoading)
  const recallPointsError = recallPointIdsQ.error ?? recallPointQs.find((query) => query.error)?.error ?? null

  if (!pid || !iid) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">缺少 projectId 或 instanceId。</p>
        <Button onClick={() => navigate("/projects")}>返回项目列表</Button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">{instance?.materialDisplayName ?? iid}</h1>
          <p className="text-sm text-muted-foreground">查看实例材料信息、对象树绑定与复述点引用。</p>
        </div>
        <Button variant="outline" asChild>
          <Link to={`/p/${pid}/object-tree`}>返回学习对象树</Link>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>实例概览</CardTitle>
          <CardDescription>实例是学习对象树叶子节点绑定到的具体材料。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {instancesQ.isLoading ? <p className="text-sm text-muted-foreground">加载中...</p> : null}
          {instancesQ.error ? <p className="text-sm text-destructive">{formatApiError(instancesQ.error)}</p> : null}
          {objectNodesQ.error ? <p className="text-sm text-destructive">{formatApiError(objectNodesQ.error)}</p> : null}
          {recallPointIdsQ.error ? <p className="text-sm text-destructive">{formatApiError(recallPointIdsQ.error)}</p> : null}

          {instance ? (
            <>
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">材料名</div>
                  <div className="mt-1 font-medium text-foreground">{instance.materialDisplayName}</div>
                </div>
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">材料状态</div>
                  <div className="mt-1 font-medium text-foreground">{instance.presence === "MISSING" ? "缺失" : "正常"}</div>
                </div>
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">复述点数量</div>
                  <div className="mt-1 font-medium text-foreground">{recallPointIdsQ.data?.recallPointIds.length ?? "-"}</div>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-md border p-4">
                  <div className="text-xs text-muted-foreground">materialId</div>
                  <div className="mt-1 break-all text-sm font-medium text-foreground">{instance.materialId}</div>
                </div>
                <div className="rounded-md border p-4">
                  <div className="text-xs text-muted-foreground">最近看到时间</div>
                  <div className="mt-1 text-sm font-medium text-foreground">{formatTimestamp(instance.lastSeenAt)}</div>
                </div>
              </div>

              <div className="rounded-md border p-4">
                <div className="text-xs text-muted-foreground">对象树绑定</div>
                <div className="mt-1 text-sm font-medium text-foreground">{boundObjectNode?.title || "未绑定对象节点"}</div>
              </div>

              <div className="flex flex-wrap gap-3">
                {boundObjectNode ? (
                  <Button variant="outline" asChild>
                    <Link to={`/p/${pid}/learning-object-nodes/${boundObjectNode.nodeId}`}>查看对象节点</Link>
                  </Button>
                ) : null}
              </div>
            </>
          ) : (
            !instancesQ.isLoading && <p className="text-sm text-muted-foreground">未找到该实例。</p>
          )}
        </CardContent>
      </Card>

      <RecallPointListCard
        projectId={pid}
        items={recallPoints}
        isLoading={recallPointsLoading}
        error={recallPointsError}
        title="相关复述点"
        description="所有锚定到这个实例的复述点都会直接显示在这里。"
      />
    </div>
  )
}
