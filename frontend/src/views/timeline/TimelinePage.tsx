import { Clock3 } from "lucide-react"
import { useMemo } from "react"
import { useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import type { AuditLogEvent } from "@/ui/api/auditLog"
import { ContentEmptyState, ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import {
  formatArtifactReference,
  formatInstanceReference,
  formatLearningTaskReference,
  formatObjectNodeReference,
  formatParentNodeReference,
  formatRangeReference,
  formatRecallPointReference,
  formatReviewTaskReference,
} from "@/ui/displayIdentifiers"
import { useAuditLogEvents } from "@/ui/queries/auditLog"
import { useProject } from "@/ui/queries/projects"

const TIMELINE_VISIBLE_KINDS = new Set([
  "PROJECT_CREATED",
  "PROJECT_DELETED",
  "SUBMIT_LEARNING_TASK",
  "EXECUTOR_COMMIT_REVIEW_TASK",
  "MANUAL_ROLL_UP",
  "EDIT_PROJECT_CONFIG",
  "BULK_REMAP_RECALL_POINTS_INSTANCE",
])

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function formatTs(iso: string) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString()
}

function parsePayload(payload: string): Record<string, unknown> | null {
  try {
    const v: unknown = JSON.parse(payload)
    if (!v || typeof v !== "object" || Array.isArray(v)) return null
    return v as Record<string, unknown>
  } catch {
    return null
  }
}

function asText(v: unknown): string | null {
  if (v === null || v === undefined) return null
  if (typeof v === "string") return v
  if (typeof v === "number" || typeof v === "boolean") return String(v)
  return null
}

function formatMs(v: unknown): string | null {
  if (typeof v !== "number" || Number.isNaN(v)) return null
  if (v < 1000) return `${v} 毫秒`
  return `${(v / 1000).toFixed(1)} 秒`
}

function formatTimelineValue(key: string, value: string) {
  if (key === "instanceId" || key === "fromInstanceId" || key === "toInstanceId") return formatInstanceReference(value)
  if (key === "recallPointId") return formatRecallPointReference(value)
  if (key === "nodeId") return formatObjectNodeReference(value)
  if (key === "parentId") return formatParentNodeReference(value)
  if (key === "learningTaskId") return formatLearningTaskReference(value)
  if (key === "reviewTaskId") return formatReviewTaskReference(value)
  if (key === "resultRangeId" || key === "seedRangeId" || key === "inputRangeId") return formatRangeReference(value)
  if (key === "asrArtifactId") return formatArtifactReference(value)
  return value
}

function describeEvent(
  ev: AuditLogEvent,
  projectTitle: string,
): { title: string; details: { label: string; value: string }[] } {
  const p = parsePayload(ev.payload)
  const details: { label: string; value: string }[] = []

  const add = (label: string, key: string) => {
    const v = p ? asText(p[key]) : null
    if (v !== null) details.push({ label, value: formatTimelineValue(key, v) })
  }
  const addValue = (label: string, value: string | null) => {
    if (value !== null) details.push({ label, value })
  }

  switch (ev.kind) {
    case "PROJECT_CREATED":
      details.push({ label: "项目", value: projectTitle })
      return { title: "创建项目", details }
    case "PROJECT_DELETED":
      details.push({ label: "项目", value: projectTitle })
      return { title: "删除项目", details }
    case "ADD_INSTANCE":
      add("材料实例", "instanceId")
      return { title: "录入材料", details }
    case "ADD_LEARNING_OBJECT_LEAF":
      add("对象节点", "nodeId")
      add("父节点", "parentId")
      add("材料实例", "instanceId")
      return { title: "添加学习对象", details }
    case "ADD_LEARNING_OBJECT_CONTAINER":
      add("对象节点", "nodeId")
      add("父节点", "parentId")
      add("子节点数", "childrenCount")
      return { title: "整理学习对象分组", details }
    case "SYNC_LEARNING_OBJECTS_FROM_FS": {
      const unchanged = p?.unchanged === true
      add("扫描文件", "filesCount")
      add("扫描目录", "dirsCount")
      add("新增材料", "createdInstancesCount")
      add("标记缺失", "markedMissingCount")
      add("更新节点", "replacedLearningObjectNodesCount")
      return { title: unchanged ? "检查学习对象目录" : "同步学习对象目录", details }
    }
    case "SUBMIT_LEARNING_TASK": {
      const n = p ? asText(p.itemsCount) : null
      add("入口节点", "entryNodeId")
      return { title: n ? `创建学习任务（${n} 条）` : "创建学习任务", details }
    }
    case "EDIT_RECALL_POINT":
      add("复述点", "recallPointId")
      return { title: "保存复述点", details }
    case "APPEND_RECALL_POINT_INSIGHT":
      add("复述点", "recallPointId")
      return { title: "追加复述洞察", details }
    case "EDIT_LEARNING_TASK":
      add("学习任务", "learningTaskId")
      return { title: "更新学习任务", details }
    case "EDIT_PROJECT_CONFIG":
      add("层", "layerIndex")
      return { title: "更新层配置", details }
    case "BULK_REMAP_RECALL_POINTS_INSTANCE":
      add("原材料实例", "fromInstanceId")
      add("目标材料实例", "toInstanceId")
      add("调整数量", "movedCount")
      add("范围", "scope")
      return { title: "调整复述点材料关联", details }
    case "EXECUTOR_COMMIT_REVIEW_TASK":
      add("复习任务", "reviewTaskId")
      add("条目数", "canRecallLen")
      add("追加洞察", "appendedInsightsCount")
      add("结果范围", "resultRangeId")
      return { title: "完成复习任务", details }
    case "MANUAL_ROLL_UP":
      add("目标层", "targetLayerIndex")
      add("父节点", "parentNodeId")
      add("候选数", "candidateCount")
      return { title: "执行上推聚合", details }
    case "REQUEST_ASR":
      add("复述点", "recallPointId")
      add("转写片段", "asrArtifactId")
      addValue("锚点时间", p ? formatMs(p.centerMs) : null)
      addValue("前置截取", p ? formatMs(p.preMs) : null)
      addValue("后置截取", p ? formatMs(p.postMs) : null)
      return { title: "生成语音转写", details }
    default:
      return { title: "完成系统操作", details }
  }
}

export function TimelinePage() {
  const { projectId } = useParams()
  const pid = projectId ?? ""
  const nav = useNavigate()
  const { projectTitle } = useProject(pid)

  const q = useAuditLogEvents(pid)

  const events = useMemo(
    () => (q.data ? [...q.data].reverse().filter((ev) => TIMELINE_VISIBLE_KINDS.has(ev.kind)) : []),
    [q.data],
  )

  if (!pid) {
    return (
      <div className="space-y-4">
        <ContentNotice
          title="当前页面缺少项目上下文"
          message="当前链接缺少项目信息。请先返回项目列表，再重新进入时间线。"
          action={<Button onClick={() => nav("/projects")}>返回项目列表</Button>}
        />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">时间线</h1>
          <p className="text-sm text-muted-foreground">
            项目：<span className="font-medium text-foreground">{projectTitle}</span>
          </p>
        </div>
        <Button variant="outline" onClick={() => void q.refetch()} disabled={!pid || q.isFetching}>
          {q.isFetching ? "刷新中..." : "刷新"}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>事件记录</CardTitle>
          <CardDescription>按时间倒序展示该项目的关键学习里程碑。</CardDescription>
        </CardHeader>
        <CardContent>
          {q.isLoading ? <LoadingNotice title="正在加载项目时间线" message="正在整理这个项目最近的学习、复习和配置事件。" /> : null}
          {q.error ? <ErrorNotice title="项目时间线加载失败" message={formatApiError(q.error)} /> : null}
          {!q.isLoading && !q.error && events.length === 0 ? (
            <ContentEmptyState
              icon={Clock3}
              title="这条时间线还没有新的项目里程碑"
              message="创建学习任务、提交复习、执行上推或调整项目配置后，关键变动会记录在这里。"
            />
          ) : null}

          {!q.isLoading && !q.error && events.length > 0 ? (
            <div className="divide-y rounded-md border">
              {events.map((ev) => {
                const d = describeEvent(ev, projectTitle)
                return (
                  <div key={ev.eventId} className="px-4 py-3">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <div className="font-medium">{d.title}</div>
                      <div className="text-xs text-muted-foreground">{formatTs(ev.occurredAt)}</div>
                    </div>

                    {d.details.length > 0 ? (
                      <div className="mt-2 grid gap-1 text-sm">
                        {d.details.map((it) => (
                          <div key={`${ev.eventId}:${it.label}`} className="flex flex-wrap gap-x-2">
                            <span className="text-muted-foreground">{it.label}：</span>
                            <span className={it.label === "项目" ? "font-medium" : "font-mono"}>{it.value}</span>
                          </div>
                        ))}
                      </div>
                    ) : null}

                    <details className="mt-2 text-xs text-muted-foreground">
                      <summary className="cursor-pointer select-none">查看技术记录</summary>
                      <pre className="mt-2 overflow-auto rounded-md border bg-muted/30 p-2">{ev.payload}</pre>
                    </details>
                  </div>
                )
              })}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
