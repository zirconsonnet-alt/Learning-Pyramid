import { useEffect, useMemo, useState } from "react"
import { useQueries } from "@tanstack/react-query"
import { ArrowLeft, ArrowRight, ArrowUpDown, BookOpenText, ChevronDown, Lightbulb, Plus, Settings2, Video } from "lucide-react"
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
import { buildProjectSettingsPath, buildProjectWorkbenchPath } from "@/ui/projectPaths"
import { useCreateSubjectMaterial, useSubjectMaterials, useSubjects } from "@/ui/queries/subjects"
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

export function SubjectDashboardPage() {
  const { subjectId = "" } = useParams()
  const navigate = useNavigate()
  const subjectsQ = useSubjects(Boolean(subjectId))
  const materialsQ = useSubjectMaterials(subjectId)
  const createMaterialM = useCreateSubjectMaterial()
  const setSelectedProjectId = useAppStore((state) => state.setSelectedProjectId)
  const [createOpen, setCreateOpen] = useState(false)
  const [sortMode, setSortMode] = useState<MaterialSortMode>("recent")
  const [draftType, setDraftType] = useState<StudyMaterialType | null>(null)
  const [draftTitle, setDraftTitle] = useState("")

  const subject = useMemo(
    () => (subjectsQ.data ?? []).find((item) => item.subjectId === subjectId || item.compatibilityProjectId === subjectId) ?? null,
    [subjectId, subjectsQ.data],
  )
  const subjectTitle = subject?.title ?? "当前学科"
  const subjectProjectId = subject?.compatibilityProjectId ?? subjectId
  const materials = materialsQ.data ?? []
  const materialActivityQs = useQueries({
    queries: materials.map((material) => ({
      queryKey: ["auditLogEvents", material.compatibilityProjectId ?? material.materialId],
      queryFn: () => listAuditLogEvents(material.compatibilityProjectId ?? ""),
      enabled: Boolean(material.compatibilityProjectId) && !materialsQ.isLoading && !materialsQ.error,
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

  useEffect(() => {
    if (!subjectProjectId) return
    setSelectedProjectId(subjectProjectId)
  }, [setSelectedProjectId, subjectProjectId])

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
    const projectId = material.compatibilityProjectId
    if (!projectId) return
    setSelectedProjectId(projectId)
    navigate(
      target === "settings"
        ? buildProjectSettingsPath(projectId, { subjectProjectId })
        : buildProjectWorkbenchPath(projectId),
    )
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
            const active = material.compatibilityProjectId === subjectProjectId
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
                        <CardDescription className="mt-1 text-xs">
                          <span className="theme-meta-strong">{formatStudyMaterialTypeLabel(material.materialType)}</span>
                        </CardDescription>
                      </div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {material.compatibilityProjectId ? (
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" onClick={() => openMaterial(material, "workbench")}>
                        <ArrowRight className="h-4 w-4" />
                        进入工作台
                      </Button>
                      <Button type="button" variant="outline" onClick={() => openMaterial(material, "settings")}>
                        <Settings2 className="h-4 w-4" />
                        项目设置
                      </Button>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">这个项目还没有可进入的兼容工作台。</p>
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
            <div className="space-y-2">
              <div className="text-xl font-semibold text-foreground">新建项目</div>
              <div className="text-sm leading-6 text-muted-foreground">像学科中心一样，从这里新建网课、书本或零散知识点项目。</div>
            </div>
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
    </div>
  )
}
