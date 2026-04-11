import { useEffect, useMemo, useState } from "react"
import { ArrowLeft, ArrowRight, BookOpenText, ClipboardList, Lightbulb, Plus, Settings2, Video } from "lucide-react"
import { Link, useNavigate, useParams } from "react-router-dom"

import type { StudyMaterial, StudyMaterialType } from "@/ui/api/subjects"
import { ApiError } from "@/ui/api/http"
import { ContentEmptyState, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useCreateSubjectMaterial, useSubjectMaterials, useSubjects } from "@/ui/queries/subjects"
import { useAppStore } from "@/ui/store/appStore"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { describeStudyMaterialHint, formatStudyMaterialTypeLabel } from "@/ui/subjects/studyMaterials"
import { cn } from "@/ui/utils"

const MATERIAL_TYPES: StudyMaterialType[] = ["COURSE", "BOOK", "MISTAKE_BOOK", "LOOSE_POINTS"]

const materialIconByType = {
  COURSE: Video,
  BOOK: BookOpenText,
  MISTAKE_BOOK: ClipboardList,
  LOOSE_POINTS: Lightbulb,
} satisfies Record<StudyMaterialType, typeof Video>

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function getMaterialStats(materials: StudyMaterial[]) {
  return Object.fromEntries(MATERIAL_TYPES.map((type) => [type, materials.filter((material) => material.materialType === type).length])) as Record<
    StudyMaterialType,
    number
  >
}

export function SubjectDashboardPage() {
  const { subjectId = "" } = useParams()
  const navigate = useNavigate()
  const subjectsQ = useSubjects(Boolean(subjectId))
  const materialsQ = useSubjectMaterials(subjectId)
  const createMaterialM = useCreateSubjectMaterial()
  const setSelectedProjectId = useAppStore((state) => state.setSelectedProjectId)
  const [draftType, setDraftType] = useState<StudyMaterialType | null>(null)
  const [draftTitle, setDraftTitle] = useState("")

  const subject = useMemo(
    () => (subjectsQ.data ?? []).find((item) => item.subjectId === subjectId || item.compatibilityProjectId === subjectId) ?? null,
    [subjectId, subjectsQ.data],
  )
  const subjectTitle = subject?.title ?? "当前学科"
  const subjectProjectId = subject?.compatibilityProjectId ?? subjectId
  const materials = materialsQ.data ?? []
  const materialStats = useMemo(() => getMaterialStats(materials), [materials])

  useEffect(() => {
    if (!subjectProjectId) return
    setSelectedProjectId(subjectProjectId)
  }, [setSelectedProjectId, subjectProjectId])

  function beginCreate(materialType: StudyMaterialType) {
    setDraftType(materialType)
    setDraftTitle(`${subjectTitle}·${formatStudyMaterialTypeLabel(materialType)}`)
  }

  async function createMaterial() {
    if (!subjectId || !draftType) return
    const title = draftTitle.trim()
    if (!title) return
    try {
      const created = await createMaterialM.mutateAsync({ subjectId, materialType: draftType, title })
      setDraftType(null)
      setDraftTitle("")
      showSuccessFeedback("材料已创建", `“${created.title}” 已挂到“${subjectTitle}”下。可以从学科总面板进入它的工作台。`)
    } catch (err) {
      showErrorFeedback("创建材料失败", formatApiError(err))
    }
  }

  function openMaterial(material: StudyMaterial, target: "workbench" | "settings") {
    const projectId = material.compatibilityProjectId
    if (!projectId) return
    setSelectedProjectId(projectId)
    navigate(target === "settings" ? `/p/${projectId}/settings` : `/p/${projectId}/workbench`)
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
      <Card className="theme-card-main">
        <CardHeader className="space-y-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <div className="theme-meta mb-3 inline-flex">学科总面板</div>
              <CardTitle className="text-2xl tracking-[-0.03em] sm:text-3xl">{subjectTitle}</CardTitle>
              <CardDescription className="mt-3 max-w-3xl text-sm leading-6">
                先在这里选择或创建学科下面的材料项目。网课、书本、错题和零散知识点各自拥有自己的工作台，进入具体材料后再开始学习、复习和设置。
              </CardDescription>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <Button asChild variant="outline">
                <Link to="/projects">
                  <ArrowLeft className="h-4 w-4" />
                  学科中心
                </Link>
              </Button>
              <Button asChild variant="outline">
                <Link to={`/p/${subjectProjectId}/settings`}>
                  <Settings2 className="h-4 w-4" />
                  学科设置
                </Link>
              </Button>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {MATERIAL_TYPES.map((materialType) => (
              <div key={materialType} className="theme-soft-surface px-4 py-3">
                <div className="text-xs text-muted-foreground">{formatStudyMaterialTypeLabel(materialType)}</div>
                <div className="mt-1 text-2xl font-semibold tracking-[-0.03em] text-foreground">{materialStats[materialType]}</div>
              </div>
            ))}
          </div>
        </CardHeader>
      </Card>

      <Card className="theme-card">
        <CardHeader>
          <CardTitle>创建材料项目</CardTitle>
          <CardDescription>先选材料类型，再命名。创建完成后会留在这个学科总面板，方便你再决定进入哪个材料。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {MATERIAL_TYPES.map((materialType) => (
              <Button key={materialType} type="button" variant="outline" disabled={createMaterialM.isPending} onClick={() => beginCreate(materialType)}>
                <Plus className="h-4 w-4" />
                新建{formatStudyMaterialTypeLabel(materialType)}
              </Button>
            ))}
          </div>

          {draftType ? (
            <div className="space-y-3 rounded-[1.2rem] border border-border/70 bg-muted/10 px-4 py-4">
              <div>
                <div className="text-sm font-semibold text-foreground">创建{formatStudyMaterialTypeLabel(draftType)}</div>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">{describeStudyMaterialHint(draftType)}</p>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="subject-dashboard-material-title">材料名称</Label>
                <Input
                  id="subject-dashboard-material-title"
                  value={draftTitle}
                  maxLength={120}
                  disabled={createMaterialM.isPending}
                  onChange={(event) => setDraftTitle(event.target.value)}
                  placeholder={`${subjectTitle}·${formatStudyMaterialTypeLabel(draftType)}`}
                  autoFocus
                />
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" disabled={createMaterialM.isPending || !draftTitle.trim()} onClick={() => void createMaterial()}>
                  {createMaterialM.isPending ? "创建中..." : "确认创建"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={createMaterialM.isPending}
                  onClick={() => {
                    setDraftType(null)
                    setDraftTitle("")
                  }}
                >
                  取消
                </Button>
              </div>
            </div>
          ) : null}

          {createMaterialM.error ? <p className="text-sm text-destructive">{formatApiError(createMaterialM.error)}</p> : null}
        </CardContent>
      </Card>

      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-foreground">材料项目</h2>
            <p className="mt-1 text-sm text-muted-foreground">进入具体材料后，才会出现这个材料自己的工作台、推荐复习和学习树。</p>
          </div>
          <span className="theme-meta px-3 py-1 text-sm">{materials.length} 个材料</span>
        </div>

        {materialsQ.isLoading || subjectsQ.isLoading ? <LoadingNotice title="正在加载学科材料" message="正在读取这个学科下面的材料项目。" /> : null}
        {materialsQ.error ? <ErrorNotice title="材料加载失败" message={formatApiError(materialsQ.error)} /> : null}
        {subjectsQ.error ? <ErrorNotice title="学科信息加载失败" message={formatApiError(subjectsQ.error)} /> : null}

        {!materialsQ.isLoading && !materialsQ.error && materials.length === 0 ? (
          <ContentEmptyState title="当前学科还没有材料" message="先新建网课、书本、错题或零散知识点，再进入具体材料工作台。" />
        ) : null}

        <div className="grid gap-4 xl:grid-cols-2">
          {materials.map((material) => {
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
                        <CardDescription className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                          <span className="theme-meta-strong">{formatStudyMaterialTypeLabel(material.materialType)}</span>
                          {active ? <span className="theme-meta">默认入口</span> : null}
                        </CardDescription>
                      </div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="text-sm leading-6 text-muted-foreground">{describeStudyMaterialHint(material.materialType)}</p>
                  {material.compatibilityProjectId ? (
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" onClick={() => openMaterial(material, "workbench")}>
                        <ArrowRight className="h-4 w-4" />
                        进入工作台
                      </Button>
                      <Button type="button" variant="outline" onClick={() => openMaterial(material, "settings")}>
                        <Settings2 className="h-4 w-4" />
                        材料设置
                      </Button>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">这个材料还没有可进入的兼容工作台。</p>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      </section>
    </div>
  )
}
