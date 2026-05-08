import { useMemo, useState } from "react"
import { useQueries } from "@tanstack/react-query"
import { ArrowLeft, ArrowRight, ArrowUpDown, BookOpenText, ChevronDown, Lightbulb, Plus, Settings2, Trash2, Video } from "lucide-react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { listAuditLogEvents, type AuditLogEvent } from "@/ui/api/auditLog"
import type { StudyMaterial, StudyMaterialType } from "@/ui/api/subjects"
import { ApiError } from "@/ui/api/http"
import { ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/ui/components/ui/dialog"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { completeGuideWalkthroughStep } from "@/ui/guideWalkthrough/guideWalkthroughController"
import { buildProjectSettingsPath, buildProjectWorkbenchPath } from "@/ui/projectPaths"
import { useCreateSubjectMaterial, useDeleteSubjectMaterial, useSubjectMaterials, useSubjects } from "@/ui/queries/subjects"
import { useAppStore } from "@/ui/store/appStore"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { describeStudyMaterialHint, formatStudyMaterialTypeLabel } from "@/ui/subjects/studyMaterials"
import { cn } from "@/ui/utils"

const MATERIAL_TYPES: StudyMaterialType[] = ["COURSE", "BOOK", "LOOSE_POINTS"]
type MaterialSortMode = "recent" | "created"

const materialIconByType = {
  COURSE: Video,
  BOOK: BookOpenText,
  LOOSE_POINTS: Lightbulb,
} satisfies Record<StudyMaterialType, typeof Video>

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function getMaterialLastStudyAt(events: AuditLogEvent[] | undefined) {
  let latest: string | null = null
  for (const event of events ?? []) {
    if (event.result !== "OK" && event.result !== "SUCCESS") continue
    if (event.kind !== "SUBMIT_LEARNING_TASK" && event.kind !== "EXECUTOR_COMMIT_REVIEW_TASK") continue
    if (!latest || Date.parse(event.occurredAt) > Date.parse(latest)) latest = event.occurredAt
  }
  return latest
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

export function SubjectDashboardPage() {
  const { subjectId = "" } = useParams()
  const navigate = useNavigate()
  const subjectsQ = useSubjects(Boolean(subjectId))
  const materialsQ = useSubjectMaterials(subjectId)
  const createMaterialM = useCreateSubjectMaterial()
  const deleteMaterialM = useDeleteSubjectMaterial()
  const selectedWorkbenchProjectId = useAppStore((state) => state.selectedWorkbenchProjectId)
  const setSelectedWorkbenchProjectId = useAppStore((state) => state.setSelectedWorkbenchProjectId)
  const setSelectedSubjectId = useAppStore((state) => state.setSelectedSubjectId)
  const removeRecentWorkbenchProjectId = useAppStore((state) => state.removeRecentWorkbenchProjectId)
  const [createOpen, setCreateOpen] = useState(false)
  const [deleteMaterialTarget, setDeleteMaterialTarget] = useState<StudyMaterial | null>(null)
  const [deleteMaterialConfirmation, setDeleteMaterialConfirmation] = useState("")
  const [sortMode, setSortMode] = useState<MaterialSortMode>("recent")
  const [draftType, setDraftType] = useState<StudyMaterialType | null>(null)
  const [draftTitle, setDraftTitle] = useState("")

  const subject = useMemo(
    () => (subjectsQ.data ?? []).find((item) => item.subjectId === subjectId) ?? null,
    [subjectId, subjectsQ.data],
  )
  const subjectTitle = subject?.title ?? "当前学科"
  const materials = useMemo(() => materialsQ.data ?? [], [materialsQ.data])
  const deleteMaterialExpectedText = deleteMaterialTarget?.title ?? ""
  const deleteMaterialMatches = deleteMaterialConfirmation.trim() === deleteMaterialExpectedText
  const materialActivityQs = useQueries({
    queries: materials.map((material) => ({
      queryKey: ["auditLogEvents", material.projectId ?? material.materialId],
      queryFn: () => listAuditLogEvents(material.projectId ?? ""),
      enabled: Boolean(material.projectId) && !materialsQ.isLoading && !materialsQ.error,
      staleTime: 60_000,
      refetchInterval: 60_000,
    })),
  })
  const lastStudyByMaterialId = useMemo(() => {
    const entries = materials.map((material, index) => [material.materialId, getMaterialLastStudyAt(materialActivityQs[index]?.data)] as const)
    return Object.fromEntries(entries)
  }, [materialActivityQs, materials])
  const sortedMaterials = useMemo(() => {
    const items = [...materials]
    if (sortMode === "created") {
      return items.sort((a, b) => {
        const aTime = Date.parse(a.createdAt)
        const bTime = Date.parse(b.createdAt)
        return (Number.isFinite(bTime) ? bTime : 0) - (Number.isFinite(aTime) ? aTime : 0)
      })
    }

    return items.sort((a, b) => {
      const aStudy = lastStudyByMaterialId[a.materialId]
      const bStudy = lastStudyByMaterialId[b.materialId]
      const aStudyTime = aStudy ? Date.parse(aStudy) : Number.NEGATIVE_INFINITY
      const bStudyTime = bStudy ? Date.parse(bStudy) : Number.NEGATIVE_INFINITY
      if (aStudyTime !== bStudyTime) {
        return (Number.isFinite(bStudyTime) ? bStudyTime : Number.NEGATIVE_INFINITY) - (Number.isFinite(aStudyTime) ? aStudyTime : Number.NEGATIVE_INFINITY)
      }
      const aCreatedTime = Date.parse(a.createdAt)
      const bCreatedTime = Date.parse(b.createdAt)
      return (Number.isFinite(bCreatedTime) ? bCreatedTime : 0) - (Number.isFinite(aCreatedTime) ? aCreatedTime : 0)
    })
  }, [lastStudyByMaterialId, materials, sortMode])

  function getDefaultDraftTitle(materialType: StudyMaterialType) {
    return `${subjectTitle}·${formatStudyMaterialTypeLabel(materialType)}`
  }

  function chooseDraftType(materialType: StudyMaterialType) {
    const currentDefault = draftType ? getDefaultDraftTitle(draftType) : ""
    const nextDefault = getDefaultDraftTitle(materialType)
    setDraftTitle((currentTitle) => {
      const normalized = currentTitle.trim()
      if (!normalized || normalized === currentDefault) return nextDefault
      return currentTitle
    })
    setDraftType(materialType)
  }

  function openCreateDialog(materialType: StudyMaterialType = draftType ?? "COURSE") {
    createMaterialM.reset()
    chooseDraftType(materialType)
    setCreateOpen(true)
  }

  function closeCreateDialog() {
    if (createMaterialM.isPending) return
    createMaterialM.reset()
    setCreateOpen(false)
    setDraftType(null)
    setDraftTitle("")
  }

  function openDeleteMaterialDialog(material: StudyMaterial) {
    deleteMaterialM.reset()
    setDeleteMaterialTarget(material)
    setDeleteMaterialConfirmation("")
  }

  function closeDeleteMaterialDialog() {
    if (deleteMaterialM.isPending) return
    deleteMaterialM.reset()
    setDeleteMaterialTarget(null)
    setDeleteMaterialConfirmation("")
  }

  async function createMaterial() {
    if (!subjectId || !draftType) return
    const title = draftTitle.trim()
    if (!title) return
    try {
      const created = await createMaterialM.mutateAsync({ subjectId, materialType: draftType, title })
      closeCreateDialog()
      showSuccessFeedback("项目已创建", `“${created.title}” 已挂到“${subjectTitle}”下。可以从项目中心进入它的工作台。`)
    } catch (err) {
      showErrorFeedback("创建项目失败", formatApiError(err))
    }
  }

  function openMaterial(material: StudyMaterial, target: "workbench" | "settings") {
    const projectId = material.projectId
    if (!projectId) return
    setSelectedSubjectId(subjectId)
    setSelectedWorkbenchProjectId(projectId)
    if (target === "settings") {
      completeGuideWalkthroughStep("choose-project")
    }
    navigate(
      target === "settings"
        ? buildProjectSettingsPath(projectId)
        : buildProjectWorkbenchPath(projectId),
    )
  }

  async function deleteMaterial() {
    if (!subjectId || !deleteMaterialTarget || !deleteMaterialMatches) return
    const projectId = deleteMaterialTarget.projectId
    try {
      await deleteMaterialM.mutateAsync({ subjectId, materialId: deleteMaterialTarget.materialId })
      if (projectId) {
        removeRecentWorkbenchProjectId(projectId)
      }
      const nextProjectId = materials.find((item) => item.materialId !== deleteMaterialTarget.materialId && item.projectId)?.projectId ?? null
      setSelectedWorkbenchProjectId(nextProjectId)
      showSuccessFeedback("项目已删除", `“${deleteMaterialTarget.title}” 已从“${subjectTitle}”下移除。`)
      closeDeleteMaterialDialog()
    } catch (err) {
      showErrorFeedback("删除项目失败", formatApiError(err))
    }
  }

  if (!subjectId) {
    return (
      <ErrorNotice
        title="缺少学科信息"
        message="当前链接没有携带学科标识。请先回到学科中心，再选择一个学科进入。"
        action={
          <Button asChild>
            <Link to="/projects">返回学科中心</Link>
          </Button>
        }
      />
    )
  }

  return (
    <div className="space-y-6">
      <section className="space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <h1 className="truncate text-2xl font-semibold tracking-tight text-foreground">{subjectTitle}</h1>
            <span className="theme-meta shrink-0 px-3 py-1 text-sm">{materials.length} 个项目</span>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <div className="relative">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-muted-foreground">
                <ArrowLeft className="h-4 w-4" />
              </div>
              <Link to="/projects" className="theme-select inline-flex h-11 items-center rounded-2xl pl-10 pr-4 font-medium">
                学科中心
              </Link>
            </div>
            <div className="relative">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-muted-foreground">
                <ArrowUpDown className="h-4 w-4" />
              </div>
              <select
                id="subjectMaterialSort"
                className="theme-select h-11 rounded-2xl pl-10 pr-11 font-medium"
                value={sortMode}
                onChange={(event) => setSortMode(event.target.value as MaterialSortMode)}
              >
                <option value="recent">最近使用</option>
                <option value="created">最新创建</option>
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-muted-foreground">
                <ChevronDown className="h-4 w-4" />
              </div>
            </div>
          </div>
        </div>

        {materialsQ.isLoading || subjectsQ.isLoading ? <LoadingNotice title="正在加载学科项目" message="正在读取这个学科下面的项目列表。" /> : null}
        {materialsQ.error ? <ErrorNotice title="项目加载失败" message={formatApiError(materialsQ.error)} /> : null}
        {subjectsQ.error ? <ErrorNotice title="学科信息加载失败" message={formatApiError(subjectsQ.error)} /> : null}

        <div className="grid gap-4 xl:grid-cols-2">
          {sortedMaterials.map((material) => {
            const Icon = materialIconByType[material.materialType]
            const active = material.projectId === selectedWorkbenchProjectId
            const materialActivityIndex = materials.findIndex((item) => item.materialId === material.materialId)
            const materialActivityLoading = material.projectId ? Boolean(materialActivityQs[materialActivityIndex]?.isLoading) : false
            const lastStudyDisplay = formatLastStudyText(lastStudyByMaterialId[material.materialId] ?? null)
            return (
              <Card
                key={material.materialId}
                className={cn(
                  "h-full border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] shadow-[var(--theme-soft-shadow)]",
                  active && "border-primary/20 ring-1 ring-primary/10",
                )}
              >
                <CardHeader className="space-y-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 gap-3">
                      <div className="theme-icon-surface h-11 w-11 shrink-0">
                        <Icon className="h-5 w-5" />
                      </div>
                      <div className="min-w-0">
                        <CardTitle className="truncate text-lg">{material.title}</CardTitle>
                        <CardDescription className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                          <span className="theme-meta-strong">{formatStudyMaterialTypeLabel(material.materialType)}</span>
                          <span className={cn("font-medium", materialActivityLoading ? "text-muted-foreground" : lastStudyDisplay.className)}>
                            {materialActivityLoading ? "学习记录载入中" : lastStudyDisplay.text}
                          </span>
                        </CardDescription>
                      </div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {material.projectId ? (
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" onClick={() => openMaterial(material, "workbench")}>
                        <ArrowRight className="h-4 w-4" />
                        进入工作台
                      </Button>
                      <Button type="button" variant="outline" data-guide-tour="subject-project-settings-entry" onClick={() => openMaterial(material, "settings")}>
                        <Settings2 className="h-4 w-4" />
                        项目设置
                      </Button>
                      <Button type="button" variant="destructive" disabled={deleteMaterialM.isPending} onClick={() => openDeleteMaterialDialog(material)}>
                        <Trash2 className="h-4 w-4" />
                        删除
                      </Button>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">这个项目还没有可进入的工作台。</p>
                  )}
                </CardContent>
              </Card>
            )
          })}

          <button
            type="button"
            onClick={() => openCreateDialog()}
            className="group flex h-full min-h-[12.75rem] flex-col items-start gap-5 rounded-[1.75rem] border border-dashed border-[color:var(--theme-subtle-border)] bg-[color:var(--theme-subtle-bg)] p-8 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/25 hover:bg-[color:var(--theme-soft-bg)]"
          >
            <div className="theme-icon-surface h-14 w-14 rounded-3xl transition-transform duration-200 group-hover:scale-105">
              <Plus className="h-6 w-6" />
            </div>
            <div className="text-xl font-semibold text-foreground">新建项目</div>
          </button>
        </div>
      </section>

      <Dialog open={createOpen} onOpenChange={(open) => (open ? setCreateOpen(true) : closeCreateDialog())}>
        <DialogContent className="p-4">
          <DialogHeader>
            <DialogTitle>创建新项目</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label>项目类型</Label>
              <div className="flex flex-wrap gap-2">
                {MATERIAL_TYPES.map((materialType) => (
                  <Button
                    key={materialType}
                    type="button"
                    variant={draftType === materialType ? "default" : "outline"}
                    disabled={createMaterialM.isPending}
                    onClick={() => chooseDraftType(materialType)}
                  >
                    {formatStudyMaterialTypeLabel(materialType)}
                  </Button>
                ))}
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="subject-dashboard-material-title">项目名称</Label>
              <Input
                id="subject-dashboard-material-title"
                value={draftTitle}
                maxLength={120}
                disabled={createMaterialM.isPending}
                onChange={(event) => setDraftTitle(event.target.value)}
                placeholder={draftType ? getDefaultDraftTitle(draftType) : "输入项目名称"}
                autoFocus
              />
            </div>
            <DialogDescription className="rounded-xl border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3 text-sm leading-6 text-muted-foreground">
              {draftType
                ? describeStudyMaterialHint(draftType)
                : "先选择项目类型，再命名。创建完成后会留在当前项目中心，由你决定进入哪个项目。"}
            </DialogDescription>
          </div>
          <DialogFooter>
            <Button variant="secondary" onClick={closeCreateDialog} disabled={createMaterialM.isPending}>
              取消
            </Button>
            <Button onClick={() => void createMaterial()} disabled={createMaterialM.isPending || !draftType || !draftTitle.trim()}>
              {createMaterialM.isPending ? "创建中..." : "创建项目"}
            </Button>
          </DialogFooter>
          {createMaterialM.error ? <p className="text-sm text-destructive">{formatApiError(createMaterialM.error)}</p> : null}
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(deleteMaterialTarget)} onOpenChange={(open) => (!open ? closeDeleteMaterialDialog() : null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>删除项目</DialogTitle>
            <DialogDescription>
              {deleteMaterialTarget
                ? `这会移除“${deleteMaterialTarget.title}”和它的工作台，学科“${subjectTitle}”以及其他项目会保留。`
                : "确认是否删除当前项目。"}
            </DialogDescription>
          </DialogHeader>
          {deleteMaterialTarget ? (
            <div className="space-y-4">
              <div className="rounded-2xl border border-destructive/15 bg-destructive/5 px-4 py-4">
                <div className="space-y-1.5">
                  <div className="text-sm font-semibold text-foreground">{deleteMaterialTarget.title}</div>
                  <div className="text-xs text-muted-foreground">{formatStudyMaterialTypeLabel(deleteMaterialTarget.materialType)}</div>
                </div>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="delete-material-confirmation">输入项目名称以确认删除</Label>
                <Input
                  id="delete-material-confirmation"
                  value={deleteMaterialConfirmation}
                  onChange={(event) => setDeleteMaterialConfirmation(event.target.value)}
                  placeholder="删除前请确认这个项目没有需要保留的内容、草稿或工作流入口。"
                  autoFocus
                />
                <p className="text-xs text-muted-foreground">
                  请输入 <span className="font-semibold text-foreground">{deleteMaterialExpectedText}</span> 完成确认。
                </p>
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="secondary" onClick={closeDeleteMaterialDialog} disabled={deleteMaterialM.isPending}>
              取消
            </Button>
            <Button variant="destructive" onClick={() => void deleteMaterial()} disabled={deleteMaterialM.isPending || !deleteMaterialMatches}>
              {deleteMaterialM.isPending ? "删除中..." : "确认删除"}
            </Button>
          </DialogFooter>
          {deleteMaterialM.error ? <p className="text-sm text-destructive">{formatApiError(deleteMaterialM.error)}</p> : null}
        </DialogContent>
      </Dialog>
    </div>
  )
}
