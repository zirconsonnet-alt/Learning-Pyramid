import { useMemo, useState } from "react"
import { useQueries, useQuery } from "@tanstack/react-query"
import { AlertTriangle, ArrowRight, ArrowUpDown, ChevronDown, Plus, Settings2, Trash2 } from "lucide-react"
import { useNavigate } from "react-router-dom"

import { listAuditLogEvents, type AuditLogEvent } from "@/ui/api/auditLog"
import { ApiError } from "@/ui/api/http"
import { setLayerConfig } from "@/ui/api/projectConfig"
import { getSystemDataSafetyStatus } from "@/ui/api/system"
import type { Subject } from "@/ui/api/subjects"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/ui/components/ui/dialog"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useCreateSubject, useDeleteSubject, useSubjects } from "@/ui/queries/subjects"
import { useAppStore } from "@/ui/store/appStore"
import { showErrorFeedback, showInfoFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { useGlobalConfigStore } from "@/ui/store/globalConfigStore"
import { useWorkbenchStore } from "@/ui/store/workbenchStore"
import { cn } from "@/ui/utils"

type ProjectSortMode = "recent" | "created"

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

function formatLastStudyText(occurredAt: string | null) {
  if (!occurredAt) {
    return {
      text: "还未开始学习",
      className: "text-muted-foreground",
    }
  }

  const dt = new Date(occurredAt)
  if (Number.isNaN(dt.getTime())) {
    return {
      text: "学习时间未知",
      className: "text-muted-foreground",
    }
  }

  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const targetStart = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate())
  const dayDiff = Math.max(0, Math.floor((todayStart.getTime() - targetStart.getTime()) / 86_400_000))

  if (dayDiff === 0) {
    return {
      text: "今天已学习",
      className: "text-primary",
    }
  }

  if (dayDiff === 1) {
    return {
      text: "昨天学习过",
      className: "text-[color:var(--theme-subtle-text)]",
    }
  }

  if (dayDiff <= 7) {
    return {
      text: `上次学习 ${dayDiff} 天前`,
      className: "text-[color:var(--theme-subtle-text)]",
    }
  }

  return {
    text: `已 ${dayDiff} 天未学习`,
    className: "text-[color:var(--theme-warm-text)]",
  }
}

function getProjectLastStudyAt(events: AuditLogEvent[] | undefined) {
  let latest: string | null = null
  for (const event of events ?? []) {
    if (event.result !== "OK" && event.result !== "SUCCESS") continue
    if (event.kind !== "SUBMIT_LEARNING_TASK" && event.kind !== "EXECUTOR_COMMIT_REVIEW_TASK") continue
    if (!latest || Date.parse(event.occurredAt) > Date.parse(latest)) latest = event.occurredAt
  }
  return latest
}

export function ProjectsPage() {
  const nav = useNavigate()
  const { data, isLoading, error } = useSubjects()
  const create = useCreateSubject()
  const del = useDeleteSubject()

  const selectedProjectId = useAppStore((s) => s.selectedProjectId)
  const recentProjectIds = useAppStore((s) => s.recentProjectIds)
  const setSelectedProjectId = useAppStore((s) => s.setSelectedProjectId)
  const removeRecentProjectId = useAppStore((s) => s.removeRecentProjectId)
  const defaultProjectReviewTemplate = useGlobalConfigStore((s) => s.defaultProjectReviewTemplate)

  const subjects = data ?? []
  const dataSafety = useQuery({
    queryKey: ["systemDataSafety"],
    queryFn: () => getSystemDataSafetyStatus(),
    staleTime: 60_000,
    refetchInterval: 60_000,
  })
  const dataSafetyStatus = dataSafety.data

  const [title, setTitle] = useState("")
  const [createOpen, setCreateOpen] = useState(false)
  const [sortMode, setSortMode] = useState<ProjectSortMode>("recent")
  const [deleteTarget, setDeleteTarget] = useState<Subject | null>(null)
  const [deleteConfirmation, setDeleteConfirmation] = useState("")
  const deleteExpectedText = deleteTarget?.title ?? ""
  const deleteMatches = deleteConfirmation.trim() === deleteExpectedText
  const projectActivityQs = useQueries({
    queries: subjects.map((subject) => ({
      queryKey: ["auditLogEvents", subject.compatibilityProjectId],
      queryFn: () => listAuditLogEvents(subject.compatibilityProjectId),
      enabled: !isLoading && !error,
      staleTime: 60_000,
      refetchInterval: 60_000,
    })),
  })

  const lastStudyByProjectId = useMemo(() => {
    const entries = subjects.map((subject, index) => [subject.subjectId, getProjectLastStudyAt(projectActivityQs[index]?.data)] as const)
    return Object.fromEntries(entries)
  }, [projectActivityQs, subjects])
  const activityLoadingByProjectId = useMemo(() => {
    const entries = subjects.map((subject, index) => [subject.subjectId, Boolean(projectActivityQs[index]?.isLoading)] as const)
    return Object.fromEntries(entries)
  }, [projectActivityQs, subjects])

  const sortedSubjects = useMemo(() => {
    const items = [...subjects]
    if (sortMode === "created") {
      return items.sort((a, b) => {
        const aTime = Date.parse(a.createdAt)
        const bTime = Date.parse(b.createdAt)
        return (Number.isFinite(bTime) ? bTime : 0) - (Number.isFinite(aTime) ? aTime : 0)
      })
    }

    const recentRank = new Map(recentProjectIds.map((projectId, index) => [projectId, index]))
    return items.sort((a, b) => {
      const aRank = recentRank.get(a.subjectId)
      const bRank = recentRank.get(b.subjectId)
      if (aRank !== undefined || bRank !== undefined) {
        if (aRank === undefined) return 1
        if (bRank === undefined) return -1
        if (aRank !== bRank) return aRank - bRank
      }
      const aTime = Date.parse(a.createdAt)
      const bTime = Date.parse(b.createdAt)
      return (Number.isFinite(bTime) ? bTime : 0) - (Number.isFinite(aTime) ? aTime : 0)
    })
  }, [subjects, recentProjectIds, sortMode])

  function openDeleteDialog(project: Subject) {
    del.reset()
    setDeleteTarget(project)
    setDeleteConfirmation("")
  }

  function closeDeleteDialog() {
    if (del.isPending) return
    del.reset()
    setDeleteTarget(null)
    setDeleteConfirmation("")
  }

  async function onCreate() {
    const t = title.trim()
    if (!t) return
    try {
      const res = await create.mutateAsync({
        title: t,
      })
      try {
        await setLayerConfig(res.compatibilityProjectId, 0, { reviewChainTemplate: defaultProjectReviewTemplate })
      } catch (templateErr) {
        showInfoFeedback("学科已创建，但默认复习模板未自动套用", formatApiError(templateErr))
      }
      setTitle("")
      setSelectedProjectId(res.compatibilityProjectId)
      setCreateOpen(false)
      showSuccessFeedback("学科已创建", `“${t}” 已准备好。先在项目中心里选择或创建项目。`)
      nav(`/subjects/${res.subjectId}`)
    } catch (err) {
      showErrorFeedback("创建学科失败", formatApiError(err))
    }
  }

  async function onDelete() {
    if (!deleteTarget || !deleteMatches) return
    const deletedTitle = deleteTarget.title
    try {
      await del.mutateAsync(deleteTarget.subjectId)
      useWorkbenchStore.getState().resetProject(deleteTarget.subjectId)
      removeRecentProjectId(deleteTarget.subjectId)
      closeDeleteDialog()
      showSuccessFeedback("学科已删除", `“${deletedTitle}” 已从当前工作区移除。`)
    } catch (err) {
      showErrorFeedback("删除学科失败", formatApiError(err))
    }
  }

  function openSubject(subject: Subject, target: "dashboard" | "settings") {
    const projectId = subject.compatibilityProjectId
    setSelectedProjectId(projectId)
    nav(target === "dashboard" ? `/subjects/${subject.subjectId}` : `/p/${projectId}/settings`)
  }

  return (
    <>
      <div className="space-y-8">
        <section className="space-y-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-semibold tracking-tight text-foreground">所有学科</h2>
              <span className="theme-meta px-3 py-1 text-sm">{subjects.length} 个学科</span>
            </div>
            <div className="relative">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-muted-foreground">
                <ArrowUpDown className="h-4 w-4" />
              </div>
              <select
                id="projectSort"
                className="theme-select h-11 rounded-2xl pl-10 pr-11 font-medium"
                value={sortMode}
                onChange={(event) => setSortMode(event.target.value as ProjectSortMode)}
              >
                <option value="recent">最近使用</option>
                <option value="created">最新创建</option>
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-muted-foreground">
                <ChevronDown className="h-4 w-4" />
              </div>
            </div>
          </div>

          {isLoading ? (
            <div className="theme-status-surface px-5 py-4 text-sm text-muted-foreground">正在加载学科列表...</div>
          ) : null}
          {error ? <div className="rounded-2xl border border-destructive/20 bg-destructive/5 px-5 py-4 text-sm text-destructive">{formatApiError(error)}</div> : null}

          {dataSafetyStatus && (dataSafetyStatus.state === "blocked" || dataSafetyStatus.state === "unknown") ? (
            <div className="flex items-start gap-3 rounded-2xl border border-destructive/25 bg-destructive/5 px-5 py-4 text-sm text-destructive">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <div className="space-y-1">
                <div className="font-semibold">数据安全检查未通过</div>
                <div className="text-destructive/80">
                  当前服务器报告用户数据可能不可达。为避免把异常误认为空项目，请先联系运维处理数据安全状态。
                </div>
              </div>
            </div>
          ) : null}

          {!isLoading && !error ? (
            <div className="grid gap-4 xl:grid-cols-2">
              {sortedSubjects.map((p) => (
                (() => {
                  const lastStudyDisplay = formatLastStudyText(lastStudyByProjectId[p.subjectId] ?? null)
                  const activityLoading = activityLoadingByProjectId[p.subjectId]
                  return (
                    <Card
                      key={p.subjectId}
                      className={cn(
                        "h-full border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] shadow-[var(--theme-soft-shadow)] transition-all duration-200",
                        selectedProjectId === p.subjectId && "border-primary/20 shadow-[0_24px_60px_-38px_rgba(30,58,95,0.34)] ring-1 ring-primary/10",
                      )}
                    >
                      <CardHeader className="space-y-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0 space-y-2">
                            <CardTitle className="truncate text-xl">{p.title}</CardTitle>
                            <CardDescription className="flex flex-wrap items-center gap-2 text-xs">
                              <span className={cn("font-medium", activityLoading ? "text-muted-foreground" : lastStudyDisplay.className)}>
                                {activityLoading ? "学习记录载入中" : lastStudyDisplay.text}
                              </span>
                            </CardDescription>
                          </div>
                          <div className="flex flex-wrap items-center gap-2">
                            {selectedProjectId === p.subjectId ? <span className="theme-meta-strong">当前学科</span> : null}
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div className="flex flex-wrap gap-2">
                          <Button
                            onClick={() => {
                              openSubject(p, "dashboard")
                            }}
                          >
                            <ArrowRight className="h-4 w-4" />
                            进入学科
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => {
                              openSubject(p, "settings")
                            }}
                          >
                            <Settings2 className="h-4 w-4" />
                            学科设置
                          </Button>
                          <Button
                            variant="destructive"
                            disabled={del.isPending}
                            onClick={() => {
                              openDeleteDialog(p)
                            }}
                          >
                            <Trash2 className="h-4 w-4" />
                            删除
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  )
                })()
              ))}
              <button
                type="button"
                data-guide-tour="new-subject-button"
                onClick={() => setCreateOpen(true)}
                className="group flex h-full min-h-[12.75rem] flex-col items-start gap-5 rounded-[1.75rem] border border-dashed border-[color:var(--theme-subtle-border)] bg-[color:var(--theme-subtle-bg)] p-8 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/25 hover:bg-[color:var(--theme-soft-bg)]"
              >
                <div className="theme-icon-surface h-14 w-14 rounded-3xl transition-transform duration-200 group-hover:scale-105">
                  <Plus className="h-6 w-6" />
                </div>
                <div className="text-xl font-semibold text-foreground">新建学科</div>
              </button>
            </div>
          ) : null}
        </section>
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="p-4">
          <DialogHeader>
            <DialogTitle>创建新学科</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="title">学科标题</Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="例如：高等数学 / 机器学习 / 英语听力"
                autoFocus
              />
            </div>
            <DialogDescription className="rounded-xl border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3 text-sm leading-6 text-muted-foreground">
              学科是复习、复述点、层推进和统计的共享空间。网课、书本和零散知识会作为项目挂在学科下面；当前版本会先创建一个默认项目。
            </DialogDescription>
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button data-guide-tour="create-subject-submit" onClick={onCreate} disabled={create.isPending || !title.trim()}>
              {create.isPending ? "创建中..." : "创建学科"}
            </Button>
          </DialogFooter>
          {create.error ? <p className="text-sm text-destructive">{formatApiError(create.error)}</p> : null}
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(deleteTarget)} onOpenChange={(open) => (!open ? closeDeleteDialog() : null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>删除学科</DialogTitle>
            <DialogDescription>
              {deleteTarget
                ? `这会移除“${deleteTarget.title}”的当前学科入口，并清掉本浏览器里与该学科相关的已选状态和草稿缓存。`
                : "确认是否删除当前学科。"}
            </DialogDescription>
          </DialogHeader>
          {deleteTarget ? (
            <div className="space-y-4">
              <div className="rounded-2xl border border-destructive/15 bg-destructive/5 px-4 py-4">
                <div className="space-y-1.5">
                  <div className="text-sm font-semibold text-foreground">{deleteTarget.title}</div>
                  <div className="text-xs text-muted-foreground">创建于 {formatTs(deleteTarget.createdAt)}</div>
                </div>
              </div>

              <div className="theme-status-surface px-4 py-4 text-sm text-muted-foreground">
                删除前建议确认是否还有未处理的内容绑定、草稿或工作流入口需要保留。该操作完成后，当前浏览器会同步清掉这个学科的本地上下文。
              </div>

              <div className="grid gap-2">
                <Label htmlFor="delete-project-confirmation">输入学科标题以确认删除</Label>
                <Input
                  id="delete-project-confirmation"
                  value={deleteConfirmation}
                  onChange={(event) => setDeleteConfirmation(event.target.value)}
                  placeholder={deleteExpectedText || "输入学科标题"}
                  autoFocus
                />
                <p className="text-xs text-muted-foreground">
                  请输入 <span className="font-semibold text-foreground">{deleteExpectedText}</span> 完成确认。
                </p>
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="secondary" onClick={closeDeleteDialog} disabled={del.isPending}>
              取消
            </Button>
            <Button variant="destructive" onClick={() => void onDelete()} disabled={del.isPending || !deleteMatches}>
              {del.isPending ? "删除中..." : "确认删除"}
            </Button>
          </DialogFooter>
          {del.error ? <p className="text-sm text-destructive">{formatApiError(del.error)}</p> : null}
        </DialogContent>
      </Dialog>
    </>
  )
}
