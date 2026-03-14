import { useState } from "react"
import { ArrowRight, Clock3, FolderKanban, HardDrive, Plus, Settings2, Sparkles, Trash2, Workflow } from "lucide-react"
import { useNavigate } from "react-router-dom"

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
import { useSystemCapabilities } from "@/ui/queries/system"
import { useAppStore } from "@/ui/store/appStore"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { useWorkbenchStore } from "@/ui/store/workbenchStore"
import { cn } from "@/ui/utils"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "Unknown error"
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

export function ProjectsPage() {
  const nav = useNavigate()
  const { data, isLoading, error } = useProjects()
  const create = useCreateProject()
  const del = useDeleteProject()
  const capabilitiesQ = useSystemCapabilities()

  const selectedProjectId = useAppStore((s) => s.selectedProjectId)
  const setSelectedProjectId = useAppStore((s) => s.setSelectedProjectId)

  const projects = data ?? []
  const selectedProject = projects.find((item) => item.projectId === selectedProjectId) ?? null

  const [title, setTitle] = useState("")
  const [createOpen, setCreateOpen] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null)
  const [deleteConfirmation, setDeleteConfirmation] = useState("")
  const hostedMode = capabilitiesQ.data?.appMode === "hosted"
  const sourceModeLabel = capabilitiesQ.data?.browserLocalMediaEnabled ? "浏览器本地媒体" : hostedMode ? "桌面连接器与服务器素材" : "服务器扫描目录"
  const createHint = capabilitiesQ.data?.browserLocalMediaEnabled
    ? "创建后请在项目设置里绑定本地素材目录，并按需发起同步。"
    : "创建后将使用服务器目录或桌面连接器作为后续素材接入来源。"
  const deleteExpectedText = deleteTarget?.title ?? ""
  const deleteMatches = deleteConfirmation.trim() === deleteExpectedText

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
      if (selectedProjectId === deleteTarget.projectId) setSelectedProjectId(null)
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
        <section className="theme-card-main overflow-hidden">
          <div className="grid gap-8 p-7 lg:grid-cols-[minmax(0,1.2fr)_minmax(280px,0.8fr)] lg:p-8">
            <div className="space-y-5">
              <div className="flex flex-wrap items-center gap-3">
                <span className="theme-meta-strong">Project Hub</span>
                <span className="theme-meta">{hostedMode ? "Hosted Workflow" : "Local Workflow"}</span>
                <span className="theme-meta">{sourceModeLabel}</span>
              </div>
              <div className="space-y-3">
                <h1 className="text-3xl font-semibold tracking-tight text-foreground lg:text-[2.5rem]">项目是整个学习工作流的启动台。</h1>
                <p className="max-w-3xl text-base leading-7 text-[#5f7188]">
                  从这里创建项目、切换到工作台、进入任务树或项目设置，并确认当前素材接入模式和后续处理路径。
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <Button size="lg" onClick={() => setCreateOpen(true)}>
                  <Plus className="h-4 w-4" />
                  创建新项目
                </Button>
                {selectedProject ? (
                  <Button variant="outline" size="lg" onClick={() => openProject(selectedProject.projectId, "workbench")}>
                    回到当前项目
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                ) : null}
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
              <div className="theme-status-surface px-4 py-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#edf4ff] text-primary">
                    <FolderKanban className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-[#70829a]">项目总数</div>
                    <div className="text-xl font-semibold text-foreground">{projects.length}</div>
                  </div>
                </div>
              </div>
              <div className="theme-status-surface px-4 py-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#edf4ff] text-primary">
                    <Workflow className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-[#70829a]">当前项目</div>
                    <div className="truncate text-sm font-semibold text-foreground">{selectedProject?.title ?? "尚未选择"}</div>
                  </div>
                </div>
              </div>
              <div className="theme-status-surface px-4 py-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#edf4ff] text-primary">
                    <HardDrive className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-[#70829a]">素材模式</div>
                    <div className="text-sm font-semibold text-foreground">{sourceModeLabel}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#6d7e95]">Projects</p>
              <h2 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">所有项目</h2>
              <p className="mt-2 text-sm text-muted-foreground">选择一个项目继续进入工作台，或先进入项目设置完成素材接入。</p>
            </div>
            <Button variant="outline" onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" />
              新建项目
            </Button>
          </div>

          {isLoading ? (
            <div className="theme-status-surface px-5 py-4 text-sm text-muted-foreground">正在加载项目列表...</div>
          ) : null}
          {error ? <div className="rounded-2xl border border-destructive/20 bg-destructive/5 px-5 py-4 text-sm text-destructive">{formatApiError(error)}</div> : null}

          {!isLoading && !error && projects.length === 0 ? (
            <Card className="border-dashed border-border/80 bg-white/80">
              <CardContent className="flex flex-col items-center gap-4 px-8 py-14 text-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-[#edf4ff] text-primary">
                  <Sparkles className="h-6 w-6" />
                </div>
                <div className="space-y-2">
                  <h3 className="text-xl font-semibold text-foreground">还没有项目</h3>
                  <p className="max-w-xl text-sm leading-6 text-muted-foreground">{createHint}</p>
                </div>
                <Button size="lg" onClick={() => setCreateOpen(true)}>
                  <Plus className="h-4 w-4" />
                  创建第一个项目
                </Button>
              </CardContent>
            </Card>
          ) : null}

          {!isLoading && !error && projects.length > 0 ? (
            <div className="grid gap-4 xl:grid-cols-2">
              {projects.map((p) => (
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
                          <span>创建于 {formatTs(p.createdAt)}</span>
                        </CardDescription>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        {selectedProjectId === p.projectId ? <span className="theme-meta-strong">当前工作项目</span> : null}
                        <span className="theme-meta">{p.projectId}</span>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm leading-6 text-[#60728a]">{createHint}</p>
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
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Clock3 className="h-3.5 w-3.5" />
                      最适合先进入工作台确认当前媒体、队列和结构节点，再继续深入编辑。
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : null}
        </section>
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>创建新项目</DialogTitle>
            <DialogDescription>{createHint}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="theme-status-surface px-4 py-4 text-sm text-muted-foreground">
              新项目会先生成一个独立工作区，后续再在项目设置或桌面连接器流程里补齐素材接入。
            </div>
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
                    <span>{deleteTarget.projectId}</span>
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
