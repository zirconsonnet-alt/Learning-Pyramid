import { useMemo, useState } from "react"
import { useQueries } from "@tanstack/react-query"
import { ArrowRight, ArrowUpDown, ChevronDown, Plus, Settings2, Trash2 } from "lucide-react"
import { useNavigate } from "react-router-dom"

import { listAuditLogEvents, type AuditLogEvent } from "@/ui/api/auditLog"
import { ApiError } from "@/ui/api/http"
import type { Project } from "@/ui/api/projects"
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
import { useCreateProject, useDeleteProject, useProjects } from "@/ui/queries/projects"
import { useAppStore } from "@/ui/store/appStore"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
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

function formatProjectState(state: string) {
  if (state === "ACTIVE") return "运行中"
  if (state === "READY") return "已就绪"
  if (state === "DELETED") return "已删除"
  return state
}

function formatLastStudyText(occurredAt: string | null) {
  if (!occurredAt) {
    return {
      text: "还未开始学习",
      className: "text-[#7b8797]",
    }
  }

  const dt = new Date(occurredAt)
  if (Number.isNaN(dt.getTime())) {
    return {
      text: "学习时间未知",
      className: "text-[#7b8797]",
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
      className: "text-[#64748b]",
    }
  }

  if (dayDiff <= 7) {
    return {
      text: `上次学习 ${dayDiff} 天前`,
      className: "text-[#6b7280]",
    }
  }

  return {
    text: `已 ${dayDiff} 天未学习`,
    className: "text-[#b7791f]",
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
  const { data, isLoading, error } = useProjects()
  const create = useCreateProject()
  const del = useDeleteProject()

  const selectedProjectId = useAppStore((s) => s.selectedProjectId)
  const recentProjectIds = useAppStore((s) => s.recentProjectIds)
  const setSelectedProjectId = useAppStore((s) => s.setSelectedProjectId)
  const removeRecentProjectId = useAppStore((s) => s.removeRecentProjectId)

  const projects = data ?? []

  const [title, setTitle] = useState("")
  const [createOpen, setCreateOpen] = useState(false)
  const [sortMode, setSortMode] = useState<ProjectSortMode>("recent")
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null)
  const [deleteConfirmation, setDeleteConfirmation] = useState("")
  const deleteExpectedText = deleteTarget?.title ?? ""
  const deleteMatches = deleteConfirmation.trim() === deleteExpectedText
  const projectActivityQs = useQueries({
    queries: projects.map((project) => ({
      queryKey: ["auditLogEvents", project.projectId],
      queryFn: () => listAuditLogEvents(project.projectId),
      enabled: !isLoading && !error,
      staleTime: 60_000,
      refetchInterval: 60_000,
    })),
  })

  const lastStudyByProjectId = useMemo(() => {
    const entries = projects.map((project, index) => [project.projectId, getProjectLastStudyAt(projectActivityQs[index]?.data)] as const)
    return Object.fromEntries(entries)
  }, [projectActivityQs, projects])
  const activityLoadingByProjectId = useMemo(() => {
    const entries = projects.map((project, index) => [project.projectId, Boolean(projectActivityQs[index]?.isLoading)] as const)
    return Object.fromEntries(entries)
  }, [projectActivityQs, projects])

  const sortedProjects = useMemo(() => {
    const items = [...projects]
    if (sortMode === "created") {
      return items.sort((a, b) => {
        const aTime = Date.parse(a.createdAt)
        const bTime = Date.parse(b.createdAt)
        return (Number.isFinite(bTime) ? bTime : 0) - (Number.isFinite(aTime) ? aTime : 0)
      })
    }

    const recentRank = new Map(recentProjectIds.map((projectId, index) => [projectId, index]))
    return items.sort((a, b) => {
      const aRank = recentRank.get(a.projectId)
      const bRank = recentRank.get(b.projectId)
      if (aRank !== undefined || bRank !== undefined) {
        if (aRank === undefined) return 1
        if (bRank === undefined) return -1
        if (aRank !== bRank) return aRank - bRank
      }
      const aTime = Date.parse(a.createdAt)
      const bTime = Date.parse(b.createdAt)
      return (Number.isFinite(bTime) ? bTime : 0) - (Number.isFinite(aTime) ? aTime : 0)
    })
  }, [projects, recentProjectIds, sortMode])

  function openDeleteDialog(project: Project) {
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
      const res = await create.mutateAsync({ title: t })
      setTitle("")
      setSelectedProjectId(res.projectId)
      setCreateOpen(false)
      showSuccessFeedback("项目已创建", `“${t}” 已准备好，正在进入工作台。`)
      nav(`/p/${res.projectId}/workbench`)
    } catch (err) {
      showErrorFeedback("创建项目失败", formatApiError(err))
    }
  }

  async function onDelete() {
    if (!deleteTarget || !deleteMatches) return
    const deletedTitle = deleteTarget.title
    try {
      await del.mutateAsync(deleteTarget.projectId)
      useWorkbenchStore.getState().resetProject(deleteTarget.projectId)
      removeRecentProjectId(deleteTarget.projectId)
      closeDeleteDialog()
      showSuccessFeedback("项目已删除", `“${deletedTitle}” 已从当前工作区移除。`)
    } catch (err) {
      showErrorFeedback("删除项目失败", formatApiError(err))
    }
  }

  function openProject(projectId: string, target: "workbench" | "settings") {
    setSelectedProjectId(projectId)
    nav(target === "workbench" ? `/p/${projectId}/workbench` : `/p/${projectId}/settings`)
  }

  return (
    <>
      <div className="space-y-8">
        <section className="space-y-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-semibold tracking-tight text-foreground">所有项目</h2>
              <span className="theme-meta px-3 py-1 text-sm">{projects.length} 个项目</span>
            </div>
            <div className="relative">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-[#6a7e98]">
                <ArrowUpDown className="h-4 w-4" />
              </div>
              <select
                id="projectSort"
                className="h-11 appearance-none rounded-2xl border border-[#dbe4ef] bg-white/90 pl-10 pr-11 text-sm font-medium text-[#42566f] shadow-[0_14px_30px_-26px_rgba(15,23,42,0.2)] outline-none transition-colors hover:border-primary/20 focus:border-primary/30"
                value={sortMode}
                onChange={(event) => setSortMode(event.target.value as ProjectSortMode)}
              >
                <option value="recent">最近使用</option>
                <option value="created">最新创建</option>
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-[#6a7e98]">
                <ChevronDown className="h-4 w-4" />
              </div>
            </div>
          </div>

          {isLoading ? (
            <div className="theme-status-surface px-5 py-4 text-sm text-muted-foreground">正在加载项目列表...</div>
          ) : null}
          {error ? <div className="rounded-2xl border border-destructive/20 bg-destructive/5 px-5 py-4 text-sm text-destructive">{formatApiError(error)}</div> : null}

          {!isLoading && !error ? (
            <div className="grid gap-4 xl:grid-cols-2">
              {sortedProjects.map((p) => (
                (() => {
                  const lastStudyDisplay = formatLastStudyText(lastStudyByProjectId[p.projectId] ?? null)
                  const activityLoading = activityLoadingByProjectId[p.projectId]
                  return (
                    <Card
                      key={p.projectId}
                      className={cn(
                        "h-full border-white/80 bg-white/90 transition-all duration-200",
                        selectedProjectId === p.projectId && "border-primary/20 shadow-[0_24px_60px_-38px_rgba(30,58,95,0.34)] ring-1 ring-primary/10",
                      )}
                    >
                      <CardHeader className="space-y-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0 space-y-2">
                            <CardTitle className="truncate text-xl">{p.title}</CardTitle>
                            <CardDescription className="flex flex-wrap items-center gap-2 text-xs">
                              <span className="theme-meta">{formatProjectState(p.state)}</span>
                              <span className={cn("font-medium", activityLoading ? "text-[#7b8797]" : lastStudyDisplay.className)}>
                                {activityLoading ? "学习记录载入中" : lastStudyDisplay.text}
                              </span>
                            </CardDescription>
                          </div>
                          <div className="flex flex-wrap items-center gap-2">
                            {selectedProjectId === p.projectId ? <span className="theme-meta-strong">当前工作项目</span> : null}
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div className="flex flex-wrap gap-2">
                          <Button
                            onClick={() => {
                              openProject(p.projectId, "workbench")
                            }}
                          >
                            <ArrowRight className="h-4 w-4" />
                            进入工作台
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => {
                              openProject(p.projectId, "settings")
                            }}
                          >
                            <Settings2 className="h-4 w-4" />
                            项目设置
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
                onClick={() => setCreateOpen(true)}
                className="group flex h-full min-h-[12.75rem] flex-col items-start gap-5 rounded-[1.75rem] border border-dashed border-[#d5deea] bg-white/75 p-8 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/25 hover:bg-white"
              >
                <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-[#edf4ff] text-primary transition-transform duration-200 group-hover:scale-105">
                  <Plus className="h-6 w-6" />
                </div>
                <div className="text-xl font-semibold text-foreground">新建项目</div>
              </button>
            </div>
          ) : null}
        </section>
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>创建新项目</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="title">项目标题</Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="例如：机器学习 / 医学解剖 / 英语听力"
                autoFocus
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button onClick={onCreate} disabled={create.isPending || !title.trim()}>
              {create.isPending ? "创建中..." : "创建并进入"}
            </Button>
          </DialogFooter>
          {create.error ? <p className="text-sm text-destructive">{formatApiError(create.error)}</p> : null}
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(deleteTarget)} onOpenChange={(open) => (!open ? closeDeleteDialog() : null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>删除项目</DialogTitle>
            <DialogDescription>
              {deleteTarget
                ? `这会移除“${deleteTarget.title}”的当前项目入口，并清掉本浏览器里与该项目相关的已选状态和草稿缓存。`
                : "确认是否删除当前项目。"}
            </DialogDescription>
          </DialogHeader>
          {deleteTarget ? (
            <div className="space-y-4">
              <div className="rounded-2xl border border-destructive/15 bg-destructive/5 px-4 py-4">
                <div className="space-y-1.5">
                  <div className="text-sm font-semibold text-foreground">{deleteTarget.title}</div>
                  <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span className="theme-meta">{formatProjectState(deleteTarget.state)}</span>
                    <span>创建于 {formatTs(deleteTarget.createdAt)}</span>
                  </div>
                </div>
              </div>

              <div className="theme-status-surface px-4 py-4 text-sm text-muted-foreground">
                删除前建议确认是否还有未处理的素材绑定、草稿或工作流入口需要保留。该操作完成后，当前浏览器会同步清掉这个项目的本地上下文。
              </div>

              <div className="grid gap-2">
                <Label htmlFor="delete-project-confirmation">输入项目标题以确认删除</Label>
                <Input
                  id="delete-project-confirmation"
                  value={deleteConfirmation}
                  onChange={(event) => setDeleteConfirmation(event.target.value)}
                  placeholder={deleteExpectedText || "输入项目标题"}
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
