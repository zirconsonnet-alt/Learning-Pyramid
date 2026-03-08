import { useState } from "react"
import { useNavigate } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import type { Project } from "@/ui/api/projects"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/ui/components/ui/dialog"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useCreateProject, useDeleteProject, useProjects } from "@/ui/queries/projects"
import { useAppStore } from "@/ui/store/appStore"
import { useWorkbenchStore } from "@/ui/store/workbenchStore"

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

export function ProjectsPage() {
  const nav = useNavigate()
  const { data, isLoading, error } = useProjects()
  const create = useCreateProject()
  const del = useDeleteProject()

  const selectedProjectId = useAppStore((s) => s.selectedProjectId)
  const setSelectedProjectId = useAppStore((s) => s.setSelectedProjectId)

  const projects = data ?? []

  const [title, setTitle] = useState("")
  const [open, setOpen] = useState(false)

  async function onCreate() {
    const t = title.trim()
    if (!t) return
    const res = await create.mutateAsync({ title: t })
    setTitle("")
    setSelectedProjectId(res.projectId)
    setOpen(false)
  }

  async function onDelete(p: Project) {
    const ok = window.confirm(`确认删除项目“${p.title}”？`)
    if (!ok) return
    await del.mutateAsync(p.projectId)
    useWorkbenchStore.getState().resetProject(p.projectId)
    if (selectedProjectId === p.projectId) setSelectedProjectId(null)
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex-row items-start justify-between space-y-0">
          <div>
            <CardTitle>项目</CardTitle>
          </div>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button>创建</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>创建项目</DialogTitle>
                <DialogDescription>
                  新项目会自动创建在应用目录的 <code>data/&lt;项目名&gt;/learning_objects</code> 下，并作为默认扫描目录。
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-2">
                <Label htmlFor="title">标题</Label>
                <Input
                  id="title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="例如：机器学习"
                  autoFocus
                />
              </div>
              <DialogFooter>
                <Button variant="secondary" onClick={() => setOpen(false)}>
                  取消
                </Button>
                <Button onClick={onCreate} disabled={create.isPending || !title.trim()}>
                  {create.isPending ? "创建中..." : "创建"}
                </Button>
              </DialogFooter>
              {create.error ? <p className="text-sm text-destructive">{formatApiError(create.error)}</p> : null}
            </DialogContent>
          </Dialog>
        </CardHeader>
        <CardContent>
          {isLoading ? <p className="text-sm text-muted-foreground">加载中...</p> : null}
          {error ? <p className="text-sm text-destructive">{formatApiError(error)}</p> : null}
          {!isLoading && !error && projects.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无项目。</p>
          ) : null}
          <div className="divide-y rounded-md border">
            {projects.map((p) => (
              <div
                key={p.projectId}
                className="flex items-center justify-between gap-3 px-4 py-3"
              >
                <div className="min-w-0">
                  <div className="truncate font-medium">{p.title}</div>
                  <div className="truncate text-xs text-muted-foreground">创建于 {formatTs(p.createdAt)}</div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation()
                      setSelectedProjectId(p.projectId)
                      nav(`/p/${p.projectId}/workbench`)
                    }}
                  >
                    进入
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    disabled={del.isPending}
                    onClick={(e) => {
                      e.stopPropagation()
                      void onDelete(p)
                    }}
                  >
                    删除
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
