import { useEffect, useMemo, useState } from "react"
import { useQueries } from "@tanstack/react-query"
import { BookOpen, Boxes, FolderTree, Settings2, TriangleAlert, Wrench } from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { useLocation, useNavigate, useParams } from "react-router-dom"

import { listRecallPointsByInstance, type Instance } from "@/ui/api/instances"
import { ApiError } from "@/ui/api/http"
import type { ReviewChainTemplateItem, RollUpStrategy } from "@/ui/api/projectConfig"
import type { ProjectType } from "@/ui/api/projects"
import type { StudyMaterial } from "@/ui/api/subjects"
import { ContentNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { formatMaterialReference, formatRecallPointReference } from "@/ui/displayIdentifiers"
import { completeGuideWalkthroughStep } from "@/ui/guideWalkthrough/guideWalkthroughController"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { scanProjectDirectoryMedia, useProjectDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import { formatProjectTypeLabel } from "@/ui/projectTypes"
import { useProject } from "@/ui/queries/projects"
import {
  useEditSubject,
  useEditSubjectMaterial,
  useSubjectContext,
} from "@/ui/queries/subjects"
import { useSystemCapabilities } from "@/ui/queries/system"
import {
  useBulkRemapRecallPointsInstance,
  useImportLearningObjectsFromBrowser,
  useInitializeBookLearningObjects,
  useInitializeBookLearningObjectsFromSubjectMaterial,
  useInstances,
  useLayers,
  useProjectConfig,
  useSetProjectRollUpStrategy,
  useSetLayerConfig,
} from "@/ui/queries/workbench"
import { showErrorFeedback, showInfoFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { formatStudyMaterialTypeLabel } from "@/ui/subjects/studyMaterials"
import { cn } from "@/ui/utils"
import { BaiduNetdiskImportDialog } from "@/views/settings/components/BaiduNetdiskImportDialog"

let nextTemplateItemId = 1

type TemplateEditorItem = {
  id: number
  kind: "CONVERGENCE" | "REVIEW_TASK"
  count: string
}

type SettingsPanelKey = "basic" | "missing"

function SettingsCardTitle({ icon: Icon, title }: { icon: LucideIcon; title: string }) {
  return (
    <div className="flex flex-wrap items-center gap-4">
      <div className="theme-icon-surface h-11 w-11 shrink-0">
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0">
        <CardTitle>{title}</CardTitle>
      </div>
    </div>
  )
}

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function createTemplateEditorItem(kind: "CONVERGENCE" | "REVIEW_TASK", count = 1): TemplateEditorItem {
  return {
    id: nextTemplateItemId++,
    kind,
    count: String(count),
  }
}

function toTemplateEditorItems(items: ReviewChainTemplateItem[]): TemplateEditorItem[] {
  return items.map((item) => createTemplateEditorItem(item.kind, item.count ?? 1))
}

function formatLastSeenAt(value: string | null | undefined) {
  if (!value) return "未记录"
  const dt = new Date(value)
  return Number.isNaN(dt.getTime()) ? value : dt.toLocaleString()
}

function suggestTargetInstance(missingInstance: Instance, presentInstances: Instance[]) {
  return (
    presentInstances.find((item) => item.materialDisplayName === missingInstance.materialDisplayName)?.instanceId ??
    presentInstances[0]?.instanceId ??
    ""
  )
}

function describeDirectoryPermission(permission: "unsupported" | "missing" | "prompt" | "granted" | "denied") {
  if (permission === "unsupported") return "当前浏览器不支持目录授权"
  if (permission === "missing") return "未绑定目录"
  if (permission === "prompt") return "待授权"
  if (permission === "denied") return "已拒绝"
  return "已授权"
}

function describeDirectoryPermissionTone(permission: "unsupported" | "missing" | "prompt" | "granted" | "denied") {
  if (permission === "granted") return "theme-pill-accent"
  if (permission === "prompt") return "theme-pill-warm"
  if (permission === "denied") return "theme-pill-danger"
  return "theme-pill-default"
}

function describeDirectorySummary(permission: "unsupported" | "missing" | "prompt" | "granted" | "denied") {
  return `本地素材目录 · ${describeDirectoryPermission(permission)}`
}

function getRollUpStrategyLabel(strategy: RollUpStrategy) {
  if (strategy === "MANUAL") return "仅手动上推"
  if (strategy === "LEARNING_OBJECT_ISOMORPHIC") return "学习对象树同构上推"
  return "阈值自动上推"
}

function isDirectoryPickerAbort(err: unknown) {
  return err instanceof DOMException && err.name === "AbortError"
}

function countOutlineIndentDepth(rawLine: string) {
  const prefix = rawLine.match(/^[\t ]*/)?.[0] ?? ""
  let visualColumns = 0
  for (const ch of prefix) {
    visualColumns += ch === "\t" ? 2 : 1
  }
  return Math.floor(visualColumns / 2)
}

function parseBookOutlineDraft(value: string) {
  return value
    .split(/\r?\n/)
    .map((line) => ({ rawLine: line, title: line.trim() }))
    .filter((line) => line.title.length > 0)
    .map((line) => ({
      depth: countOutlineIndentDepth(line.rawLine),
      title: line.title,
    }))
}

function SettingsPanelSwitchCard(props: {
  title: string
  status: string
  icon: typeof Settings2
  active: boolean
  tone?: "default" | "success" | "warning"
  onClick: () => void
}) {
  const { title, status, icon: Icon, active, tone = "default", onClick } = props
  const toneClass =
    tone === "success"
      ? "theme-pill-accent"
      : tone === "warning"
        ? "theme-pill-warm"
        : "theme-pill-default"

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group rounded-[1.55rem] border px-4 py-4 text-left transition-all",
        active
          ? "border-primary/30 bg-[linear-gradient(180deg,hsl(var(--primary)/0.11),hsl(var(--background)))] shadow-[0_26px_60px_-40px_hsl(var(--primary)/0.45)]"
          : "border-border/70 bg-card hover:border-primary/18 hover:bg-[hsl(var(--primary)/0.05)]",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[color:var(--theme-soft-bg)] text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <span className={cn("inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold", toneClass)}>{status}</span>
      </div>
      <div className="mt-4 text-base font-semibold tracking-tight text-foreground">{title}</div>
    </button>
  )
}

export function ProjectSettingsPage() {
  const { projectId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const pid = projectId ?? ""
  const projectQ = useProject(pid, { enabled: !!pid })
  const subjectContextQ = useSubjectContext(pid, !!pid)
  const editSubjectM = useEditSubject()
  const editSubjectMaterialM = useEditSubjectMaterial()
  const capabilitiesQ = useSystemCapabilities()
  const directoryBinding = useProjectDirectoryBinding(pid)
  const directoryPermission = directoryBinding.permission
  const browserLocalMediaEnabled = capabilitiesQ.data?.browserLocalMediaEnabled ?? false
  const baiduNetdiskEnabled = capabilitiesQ.data?.baiduNetdiskEnabled ?? false

  const layersQ = useLayers(pid)
  const projectConfigQ = useProjectConfig(pid)
  const instancesQ = useInstances(pid)
  const importLearningObjectsM = useImportLearningObjectsFromBrowser(pid)
  const initializeBookLearningObjectsM = useInitializeBookLearningObjects(pid)
  const initializeBookFromMaterialM = useInitializeBookLearningObjectsFromSubjectMaterial(pid)
  const setLayerConfigM = useSetLayerConfig(pid)
  const setProjectRollUpStrategyM = useSetProjectRollUpStrategy(pid)
  const bulkRemapM = useBulkRemapRecallPointsInstance(pid)
  const projectType = projectConfigQ.data?.projectType ?? "COURSE"
  const currentRollUpStrategy = projectConfigQ.data?.rollUpStrategy ?? "THRESHOLD_AUTO"
  const subjectContext = subjectContextQ.data
  const subjectProjectId = subjectContext?.subjectProjectId ?? pid
  const isSubjectRoot = subjectContext?.isSubjectRoot ?? true
  const isSubjectSettingsScope = isSubjectRoot && !location.pathname.endsWith("/project-settings")
  const subjectTitle = subjectContext?.subject.title ?? projectQ.project?.title ?? ""
  const currentMaterial = subjectContext?.currentMaterial ?? null
  const currentMaterialTitle = currentMaterial?.title ?? projectQ.project?.title ?? ""
  const currentMaterialType =
    currentMaterial?.materialType ??
    (projectType === "BOOK"
      ? "BOOK"
      : projectType === "LOOSE_POINTS"
          ? "LOOSE_POINTS"
          : "COURSE")
  const subjectMaterials = subjectContext?.materials ?? []
  const sourceCourseMaterials = subjectMaterials.filter(
    (material) => material.materialType === "COURSE" && material.projectId && material.projectId !== pid,
  )

  const existingLayerIndexes = useMemo(() => (layersQ.data ?? []).map((l) => l.layerIndex).sort((a, b) => a - b), [layersQ.data])
  const defaultLayerConfig = useMemo(
    () => ({ reviewChainTemplate: [{ kind: "CONVERGENCE" as const }], aggregationKNode: 10, aggregationKPoint: 200, thresholdRollUpEnabled: true }),
    [],
  )

  const [configLayerIndex, setConfigLayerIndex] = useState(0)
  const effectiveConfigLayerIndex = configLayerIndex
  const knownLayerIndexes = useMemo(() => [0, 1, 2, 3, 4, 5], [])
  const selectedLayerExists = existingLayerIndexes.includes(effectiveConfigLayerIndex)
  const effectiveLayerConfig = useMemo(() => {
    const k = String(effectiveConfigLayerIndex)
    return projectConfigQ.data?.layerConfigs[k] ?? defaultLayerConfig
  }, [defaultLayerConfig, effectiveConfigLayerIndex, projectConfigQ.data?.layerConfigs])
  const templateConfigSignature = useMemo(
    () => JSON.stringify(effectiveLayerConfig.reviewChainTemplate),
    [effectiveLayerConfig.reviewChainTemplate],
  )
  const layerConfigVersion = `${currentRollUpStrategy}:${effectiveConfigLayerIndex}:${effectiveLayerConfig.aggregationKNode}:${effectiveLayerConfig.aggregationKPoint}:${effectiveLayerConfig.thresholdRollUpEnabled}:${templateConfigSignature}`

  const [remapTargets, setRemapTargets] = useState<Record<string, string>>({})
  const [directoryAction, setDirectoryAction] = useState<"authorize" | "request" | "clear" | "import" | null>(null)
  const [bookOutlineDraft, setBookOutlineDraft] = useState("")
  const [isBaiduImportDialogOpen, setIsBaiduImportDialogOpen] = useState(false)

  const missingInstances = useMemo(
    () => (instancesQ.data ?? []).filter((item) => item.presence === "MISSING"),
    [instancesQ.data],
  )
  const presentInstances = useMemo(
    () => (instancesQ.data ?? []).filter((item) => item.presence !== "MISSING"),
    [instancesQ.data],
  )

  const missingRecallPointQs = useQueries({
    queries: missingInstances.map((instance) => ({
      queryKey: ["recallPointsByInstance", pid, instance.instanceId],
      queryFn: () => listRecallPointsByInstance(pid, instance.instanceId),
      enabled: !!pid,
    })),
  })

  const recallPointIdsByInstanceId = useMemo(() => {
    const out: Record<string, string[]> = {}
    missingInstances.forEach((instance, index) => {
      out[instance.instanceId] = missingRecallPointQs[index]?.data?.recallPointIds ?? []
    })
    return out
  }, [missingInstances, missingRecallPointQs])
  const actionableMissingInstances = useMemo(
    () =>
      missingInstances.filter((_, index) => {
        const query = missingRecallPointQs[index]
        if (!query || query.isLoading || query.error) return true
        return (query.data?.recallPointIds ?? []).length > 0
      }),
    [missingInstances, missingRecallPointQs],
  )
  const missingRepairCountsLoading = missingInstances.length > 0 && missingRecallPointQs.some((query) => query.isLoading)

  const canChooseDirectory = !!pid && !directoryBinding.loading && directoryBinding.supported
  const canRequestDirectoryPermission =
    !!pid && !directoryBinding.loading && (directoryPermission === "prompt" || directoryPermission === "denied")
  const canClearDirectory = !!pid && !directoryBinding.loading && directoryPermission !== "missing"
  const directoryBusy = directoryAction !== null
  const [activePanel, setActivePanel] = useState<SettingsPanelKey>("basic")
  const supportsMissingInstanceRepair = projectType !== "LOOSE_POINTS"

  const directoryStatusText =
    projectType === "BOOK"
      ? "目录初始化"
      : projectType === "LOOSE_POINTS"
        ? "零散模式"
        : browserLocalMediaEnabled
          ? directoryPermission === "granted"
            ? "目录已接通"
            : directoryPermission === "denied"
              ? "等待重授权"
              : directoryPermission === "prompt"
                ? "等待授权"
                : "待配置"
          : "基础配置"
  const missingStatusText =
    projectType === "LOOSE_POINTS"
      ? "不适用"
      : missingRepairCountsLoading
        ? "整理中..."
        : actionableMissingInstances.length > 0
          ? `${actionableMissingInstances.length} 个待修复`
          : "当前无缺失实例"
  const parsedBookOutlineItems = useMemo(() => parseBookOutlineDraft(bookOutlineDraft), [bookOutlineDraft])
  const bookOutlineValidationMessage = useMemo(() => {
    if (projectType !== "BOOK") return null
    if (parsedBookOutlineItems.length === 0) return "请先粘贴目录文本。"
    if (parsedBookOutlineItems[0]?.depth !== 0) return "目录第一行必须是顶层节点，不能带缩进。"
    for (let index = 1; index < parsedBookOutlineItems.length; index += 1) {
      if (parsedBookOutlineItems[index].depth - parsedBookOutlineItems[index - 1].depth > 1) {
        return "目录层级每次最多只能向下增加一级缩进。"
      }
    }
    return null
  }, [parsedBookOutlineItems, projectType])
  const bookProjectAlreadyInitialized = (instancesQ.data?.length ?? 0) > 0

  useEffect(() => {
    if (isSubjectSettingsScope && activePanel !== "basic") {
      setActivePanel("basic")
      return
    }
    if (!supportsMissingInstanceRepair && activePanel === "missing") {
      setActivePanel("basic")
    }
  }, [activePanel, isSubjectSettingsScope, supportsMissingInstanceRepair])

  async function onRemapMissingInstance(fromInstanceId: string) {
    const sourceInstance = actionableMissingInstances.find((item) => item.instanceId === fromInstanceId) ?? missingInstances.find((item) => item.instanceId === fromInstanceId)
    const toInstanceId = remapTargets[fromInstanceId] ?? (sourceInstance ? suggestTargetInstance(sourceInstance, presentInstances) : "")
    if (!toInstanceId) return
    const targetInstance = presentInstances.find((item) => item.instanceId === toInstanceId)
    try {
      await bulkRemapM.mutateAsync({ fromInstanceId, toInstanceId })
      showSuccessFeedback(
        "复述点已迁移",
        `已把 ${sourceInstance?.materialDisplayName ?? "缺失实例"} 的锚点迁移到 ${targetInstance?.materialDisplayName ?? "目标实例"}。`,
      )
    } catch (err) {
      showErrorFeedback("迁移复述点失败", formatApiError(err))
    }
  }

  async function onAuthorizeDirectory() {
    if (!canChooseDirectory || directoryBusy) return
    setDirectoryAction("authorize")
    try {
      const permission = await directoryBinding.authorizeDirectory()
      if (permission === "granted") {
        showSuccessFeedback("本地目录已绑定", "浏览器已经记录并授权当前项目的本地素材目录。")
        await importAuthorizedDirectory(true)
        completeGuideWalkthroughStep("authorize-directory")
        return
      } else {
        showInfoFeedback("目录已记录", "目录已经保存到当前项目，但浏览器还需要你继续授予读取权限。")
      }
    } catch (err) {
      if (!isDirectoryPickerAbort(err)) {
        showErrorFeedback("绑定本地目录失败", formatApiError(err))
      }
    } finally {
      setDirectoryAction((current) => (current === "authorize" ? null : current))
    }
  }

  async function onRequestDirectoryPermission() {
    if (!canRequestDirectoryPermission || directoryBusy) return
    setDirectoryAction("request")
    try {
      const permission = await directoryBinding.requestPermission()
      if (permission === "granted") {
        showSuccessFeedback("目录权限已恢复", `现在可以扫描并导入当前项目的本地素材目录。`)
        await importAuthorizedDirectory(true)
        completeGuideWalkthroughStep("authorize-directory")
        return
      } else if (permission === "denied") {
        showInfoFeedback("目录权限未授予", "浏览器仍未允许读取该目录，你可以重试或直接更换目录。")
      } else {
        showInfoFeedback("等待目录授权", "浏览器还没有授予读取权限，请继续完成授权。")
      }
    } catch (err) {
      showErrorFeedback("请求目录权限失败", formatApiError(err))
    } finally {
      setDirectoryAction((current) => (current === "request" ? null : current))
    }
  }

  async function importAuthorizedDirectory(silentSuccess = false) {
    if (!pid) return
    setDirectoryAction("import")
    try {
      const scan = await scanProjectDirectoryMedia(pid)
      const result = await importLearningObjectsM.mutateAsync(scan)
      if (result.unchanged) {
        if (!silentSuccess) {
          showInfoFeedback("目录已是最新", "当前已授权目录里的媒体文件没有变化。")
        }
        return
      }
      showSuccessFeedback(
        "目录内容已同步",
        `已同步 ${scan.relativeFilePaths.length} 个媒体文件，新增 ${result.created_instances_count} 个实例。`,
      )
    } catch (err) {
      showErrorFeedback("同步本地目录失败", formatApiError(err))
    } finally {
      setDirectoryAction(null)
    }
  }

  async function onImportAuthorizedDirectory(silentSuccess = false) {
    if (!pid || directoryBusy) return
    await importAuthorizedDirectory(silentSuccess)
  }

  async function onClearDirectoryBinding() {
    if (!canClearDirectory || directoryBusy) return
    setDirectoryAction("clear")
    try {
      await directoryBinding.clearDirectory()
      showSuccessFeedback("本地目录绑定已清除", `当前项目不再保留这个浏览器里的目录授权记录。`)
    } catch (err) {
      showErrorFeedback("清除本地目录绑定失败", formatApiError(err))
    } finally {
      setDirectoryAction(null)
    }
  }

  async function onInitializeBookOutline() {
    if (projectType !== "BOOK") return
    if (bookOutlineValidationMessage) {
      showInfoFeedback("目录暂时还不能初始化", bookOutlineValidationMessage)
      return
    }
    try {
      const result = await initializeBookLearningObjectsM.mutateAsync({ items: parsedBookOutlineItems })
      showSuccessFeedback(
        "书本目录已初始化",
        `已创建 ${result.created_learning_object_nodes_count} 个目录节点和 ${result.created_instances_count} 个书本实例。`,
      )
    } catch (err) {
      showErrorFeedback("初始化书本目录失败", formatApiError(err))
    }
  }

  async function onInitializeBookFromMaterial(sourceMaterialId: string) {
    if (projectType !== "BOOK") return
    if (!sourceMaterialId.trim()) {
      showInfoFeedback("还没选来源项目", "先选一个要复用的来源项目，再开始初始化。")
      return
    }
    try {
      const result = await initializeBookFromMaterialM.mutateAsync({ sourceMaterialId })
      showSuccessFeedback(
        "书本目录已复用网课树",
        `已创建 ${result.created_learning_object_nodes_count} 个目录节点和 ${result.created_instances_count} 个书本实例。`,
      )
    } catch (err) {
      showErrorFeedback("复用网课树失败", formatApiError(err))
    }
  }

  const renameMutationError = isSubjectSettingsScope ? editSubjectM.error : editSubjectMaterialM.error
  const renameMutationPending = isSubjectSettingsScope ? editSubjectM.isPending : editSubjectMaterialM.isPending

  if (!pid) {
    return (
      <div className="space-y-4">
        <ContentNotice
          title="当前页面缺少学科上下文"
          message="当前链接缺少学科信息。请先返回学科列表，再重新进入学科设置。"
          action={<Button onClick={() => navigate("/projects")}>返回学科列表</Button>}
        />
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {!isSubjectSettingsScope ? (
        <Card className="theme-card">
          <CardHeader className="theme-card-header pb-4">
            <SettingsCardTitle icon={Settings2} title="设置分区" />
          </CardHeader>
          <CardContent className={cn("grid gap-3", supportsMissingInstanceRepair ? "md:grid-cols-2" : "md:grid-cols-1")}>
            <SettingsPanelSwitchCard
              title="基本设置"
              status={directoryStatusText}
              icon={Settings2}
              active={activePanel === "basic"}
              tone={directoryPermission === "granted" ? "success" : "default"}
              onClick={() => setActivePanel("basic")}
            />
            {supportsMissingInstanceRepair ? (
              <SettingsPanelSwitchCard
                title="缺失实例设置"
                status={missingStatusText}
                icon={TriangleAlert}
                active={activePanel === "missing"}
                tone={missingRepairCountsLoading || actionableMissingInstances.length > 0 ? "warning" : "default"}
                onClick={() => setActivePanel("missing")}
              />
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {activePanel === "basic" ? (
        <>
          {isSubjectSettingsScope ? (
            <SubjectSettingsInfoCard
              subjectTitle={subjectTitle}
              isLoading={projectQ.isLoading || subjectContextQ.isLoading}
              isPending={renameMutationPending}
              queryError={subjectContextQ.error ?? projectQ.error}
              saveError={renameMutationError}
              onSave={async (title) => {
                try {
                  await editSubjectM.mutateAsync({ subjectId: subjectProjectId, title })
                  showSuccessFeedback("学科名称已更新", `当前学科现在显示为“${title}”。`)
                } catch (err) {
                  showErrorFeedback("更新学科名称失败", formatApiError(err))
                }
              }}
            />
          ) : (
            <BasicInfoCard
              actionableMissingInstanceCount={actionableMissingInstances.length}
              baiduNetdiskEnabled={baiduNetdiskEnabled}
              browserLocalMediaEnabled={browserLocalMediaEnabled}
              canChooseDirectory={canChooseDirectory}
              canClearDirectory={canClearDirectory}
              canRequestDirectoryPermission={canRequestDirectoryPermission}
              directoryAction={directoryAction}
              directoryBinding={directoryBinding}
              directoryBusy={directoryBusy}
              directoryPermission={directoryPermission}
              entityLabel="项目"
              entityPlaceholder="输入新的项目名称"
              entitySaveLabel="保存项目名称"
              entityTitle={currentMaterialTitle}
              importError={importLearningObjectsM.error}
              isLoading={projectQ.isLoading || subjectContextQ.isLoading}
              isPending={renameMutationPending}
              isSubjectRoot={false}
              materialTitle={currentMaterialTitle}
              materialType={currentMaterialType}
              onOpenSubjectSettings={
                subjectProjectId
                  ? () => {
                      navigate(`/p/${subjectProjectId}/settings`)
                    }
                  : undefined
              }
              projectType={projectType}
              queryError={subjectContextQ.error ?? projectQ.error}
              rollUpStrategy={currentRollUpStrategy}
              saveError={renameMutationError}
              rollUpStrategyError={setProjectRollUpStrategyM.error}
              rollUpStrategySaving={setProjectRollUpStrategyM.isPending}
              subjectTitle={subjectTitle}
              onAuthorizeDirectory={onAuthorizeDirectory}
              onChangeRollUpStrategy={async (nextStrategy) => {
                try {
                  await setProjectRollUpStrategyM.mutateAsync(nextStrategy)
                  showSuccessFeedback("上推策略已更新", `当前项目已切换到“${getRollUpStrategyLabel(nextStrategy)}”。`)
                } catch (err) {
                  showErrorFeedback("更新上推策略失败", formatApiError(err))
                }
              }}
              onClearDirectoryBinding={onClearDirectoryBinding}
              onOpenBaiduImport={() => setIsBaiduImportDialogOpen(true)}
              onImportAuthorizedDirectory={onImportAuthorizedDirectory}
              onRequestDirectoryPermission={onRequestDirectoryPermission}
              onSave={async (title) => {
                try {
                  if (!currentMaterial) {
                    showInfoFeedback("项目信息仍在加载", "等项目上下文同步完成后再试一次。")
                    return
                  }
                  await editSubjectMaterialM.mutateAsync({ subjectId: subjectProjectId, materialId: currentMaterial.materialId, title })
                  showSuccessFeedback("项目名称已更新", `当前项目现在显示为“${title}”。`)
                } catch (err) {
                  showErrorFeedback("更新项目名称失败", formatApiError(err))
                }
              }}
            />
          )}

          {!isSubjectSettingsScope ? (
            <LayerConfigEditor
              key={layerConfigVersion}
              canSave={!!pid}
              existingLayerIndexes={existingLayerIndexes}
              initialConfig={effectiveLayerConfig}
              knownLayerIndexes={knownLayerIndexes}
              layersError={layersQ.error}
              mutationError={setLayerConfigM.error}
              projectConfigError={projectConfigQ.error}
              selectedLayerIndex={effectiveConfigLayerIndex}
              saving={setLayerConfigM.isPending}
              onSave={async ({ kNode, kPoint, reviewChainTemplate, thresholdRollUpEnabled }) => {
                try {
                  await setLayerConfigM.mutateAsync({
                    layerIndex: effectiveConfigLayerIndex,
                    kNode,
                    kPoint,
                    reviewChainTemplate,
                    thresholdRollUpEnabled,
                  })
                  showSuccessFeedback(
                    selectedLayerExists ? "层配置已保存" : "未来层预配置已保存",
                    selectedLayerExists
                      ? currentRollUpStrategy === "THRESHOLD_AUTO"
                        ? `第 ${effectiveConfigLayerIndex} 层现在使用 ${reviewChainTemplate.length} 个模板步骤，节点阈值 ${kNode}，复述点阈值 ${kPoint}，阈值自动上推已${thresholdRollUpEnabled ? "开启" : "关闭"}。`
                        : `第 ${effectiveConfigLayerIndex} 层现在使用 ${reviewChainTemplate.length} 个模板步骤；阈值参数也已保存，等切回“阈值自动上推”时会继续沿用。`
                      : currentRollUpStrategy === "THRESHOLD_AUTO"
                        ? `第 ${effectiveConfigLayerIndex} 层还不存在，已先保存预配置；等它被创建时会自动使用这 ${reviewChainTemplate.length} 个模板步骤、当前阈值和阈值自动上推${thresholdRollUpEnabled ? "开启" : "关闭"}状态。`
                        : `第 ${effectiveConfigLayerIndex} 层还不存在，已先保存预配置；等它被创建时会自动使用这 ${reviewChainTemplate.length} 个模板步骤，并保留当前阈值参数。`,
                  )
                } catch (err) {
                  showErrorFeedback("保存层配置失败", formatApiError(err))
                }
              }}
              onSelectedLayerIndexChange={setConfigLayerIndex}
            />
          ) : null}

          {!isSubjectSettingsScope && projectType === "BOOK" ? (
            <div id="settings-book-outline">
              <BookOutlineSetupCard
                courseMaterials={sourceCourseMaterials}
                draftValue={bookOutlineDraft}
                initialized={bookProjectAlreadyInitialized}
                initializeFromMaterialError={initializeBookFromMaterialM.error}
                initializeFromMaterialPending={initializeBookFromMaterialM.isPending}
                isPending={initializeBookLearningObjectsM.isPending}
                mutationError={initializeBookLearningObjectsM.error}
                onChange={setBookOutlineDraft}
                onInitializeFromMaterial={onInitializeBookFromMaterial}
                onInitialize={onInitializeBookOutline}
                parsedCount={parsedBookOutlineItems.length}
                validationMessage={bookOutlineValidationMessage}
              />
            </div>
          ) : null}

          {!isSubjectSettingsScope ? (
            <BaiduNetdiskImportDialog
              projectId={pid}
              open={isBaiduImportDialogOpen}
              onOpenChange={setIsBaiduImportDialogOpen}
            />
          ) : null}
        </>
      ) : null}

      {!isSubjectSettingsScope && supportsMissingInstanceRepair && activePanel === "missing" ? (
      <Card className="theme-card">
        <CardHeader className="theme-card-header">
          <SettingsCardTitle icon={Wrench} title="缺失内容修复" />
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          {instancesQ.isLoading ? <p className="text-sm text-muted-foreground">加载实例中...</p> : null}
          {instancesQ.error ? <p className="text-sm text-destructive">{formatApiError(instancesQ.error)}</p> : null}
          {!instancesQ.isLoading && !instancesQ.error && !missingRepairCountsLoading && actionableMissingInstances.length > 0 ? (
            <div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">
              这里只显示仍有活跃复述点需要迁移的缺失实例；已经没有迁移价值的旧实例会自动从列表里消失。
            </div>
          ) : null}
          {!instancesQ.isLoading && !instancesQ.error && missingRepairCountsLoading ? (
            <div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">正在整理仍需迁移的缺失实例...</div>
          ) : null}
          {!instancesQ.isLoading && !instancesQ.error && !missingRepairCountsLoading && actionableMissingInstances.length === 0 ? (
            <div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">当前没有需要迁移的缺失内容实例。</div>
          ) : null}

          <div className="space-y-3">
            {actionableMissingInstances.map((instance) => {
              const index = missingInstances.findIndex((item) => item.instanceId === instance.instanceId)
              const recallPointIds = recallPointIdsByInstanceId[instance.instanceId] ?? []
              const countQuery = missingRecallPointQs[index]
              const targetInstanceId = remapTargets[instance.instanceId] ?? suggestTargetInstance(instance, presentInstances)

              return (
                <div key={instance.instanceId} className="theme-status-surface space-y-3 rounded-[1.2rem] border border-border/70 p-4">
                  <div className="space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-foreground">{instance.materialDisplayName}</span>
                      <span className="theme-meta">缺失</span>
                    </div>
                    <div className="break-all text-xs text-muted-foreground">{formatMaterialReference(instance.materialId)}</div>
                    <div className="text-xs text-muted-foreground">最近观测：{formatLastSeenAt(instance.lastSeenAt)}</div>
                  </div>

                  <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_280px_auto] lg:items-end">
                    <div className="space-y-1">
                      <div className="text-xs text-muted-foreground">受影响复述点</div>
                      <div className="text-sm text-foreground">
                        {countQuery?.isLoading ? "统计中..." : `${recallPointIds.length} 个复述点仍指向该旧实例`}
                      </div>
                      {recallPointIds.length > 0 ? (
                        <div className="break-all text-xs text-muted-foreground">
                          {recallPointIds.slice(0, 6).map((id) => formatRecallPointReference(id)).join(" / ")}
                          {recallPointIds.length > 6 ? " / ..." : ""}
                        </div>
                      ) : (
                        <div className="text-xs text-muted-foreground">该旧实例已无锚点引用。</div>
                      )}
                    </div>

                    <div className="space-y-1">
                      <Label htmlFor={`remap-target-${instance.instanceId}`}>迁移到新实例</Label>
                      <select
                        id={`remap-target-${instance.instanceId}`}
                        className="h-10 w-full rounded-xl border bg-background px-3 text-sm"
                        value={targetInstanceId}
                        onChange={(e) =>
                          setRemapTargets((prev) => ({
                            ...prev,
                            [instance.instanceId]: e.target.value,
                          }))
                        }
                        disabled={presentInstances.length === 0 || bulkRemapM.isPending}
                      >
                        {presentInstances.length === 0 ? <option value="">当前没有可迁移到的新实例</option> : null}
                        {presentInstances.map((item) => (
                          <option key={item.instanceId} value={item.instanceId}>
                            {item.materialDisplayName}（{formatMaterialReference(item.materialId)}）
                          </option>
                        ))}
                      </select>
                    </div>

                    <Button
                      onClick={() => void onRemapMissingInstance(instance.instanceId)}
                      disabled={bulkRemapM.isPending || recallPointIds.length === 0 || !targetInstanceId}
                    >
                      {bulkRemapM.isPending ? "迁移中..." : "迁移复述点"}
                    </Button>
                  </div>
                </div>
              )
            })}
          </div>

          {bulkRemapM.error ? <p className="text-sm text-destructive">{formatApiError(bulkRemapM.error)}</p> : null}
        </CardContent>
      </Card>
      ) : null}
    </div>
  )
}

function BookOutlineSetupCard({
  courseMaterials,
  draftValue,
  initialized,
  initializeFromMaterialError,
  initializeFromMaterialPending,
  isPending,
  mutationError,
  onChange,
  onInitializeFromMaterial,
  onInitialize,
  parsedCount,
  validationMessage,
}: {
  courseMaterials: StudyMaterial[]
  draftValue: string
  initialized: boolean
  initializeFromMaterialError: unknown
  initializeFromMaterialPending: boolean
  isPending: boolean
  mutationError: unknown
  onChange: (value: string) => void
  onInitializeFromMaterial: (sourceMaterialId: string) => Promise<void>
  onInitialize: () => Promise<void>
  parsedCount: number
  validationMessage: string | null
}) {
  const [selectedSourceMaterialId, setSelectedSourceMaterialId] = useState("")
  const effectiveSourceMaterialId = courseMaterials.some((item) => item.materialId === selectedSourceMaterialId)
    ? selectedSourceMaterialId
    : courseMaterials[0]?.materialId ?? ""

  return (
    <Card className="theme-card">
      <CardHeader className="theme-card-header">
        <SettingsCardTitle icon={BookOpen} title="书本目录初始化" />
      </CardHeader>
      <CardContent className="space-y-4 pt-0 text-sm">
        <div className="rounded-[1.2rem] border border-border/70 bg-muted/15 px-4 py-4 text-muted-foreground">
          书本项目会维护自己的学习对象树。你可以手工粘贴目录文本，也可以直接复用同一门学科下某个网课项目的学习对象树，系统会把末级节点自动转换为可绑定复述点的书本实例。
        </div>

        {initialized ? (
          <div className="rounded-[1.2rem] border border-emerald-200 bg-emerald-50 px-4 py-4 text-emerald-700">
            当前书本项目已经存在目录节点和实例。如需重新初始化，请先清理现有目录结构后再执行。
          </div>
        ) : (
          <>
            <div className="space-y-4 rounded-[1.2rem] border border-border/70 bg-muted/10 px-4 py-4">
              <div className="space-y-1">
                <div className="text-sm font-semibold text-foreground">一键复用网课树</div>
                <p className="text-xs leading-5 text-muted-foreground">把同一门学科下某个网课项目的学习对象树复制成书本目录结构，省掉手动重新录目录。</p>
              </div>

              {courseMaterials.length > 0 ? (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="bookOutlineSourceMaterial">来源网课项目</Label>
                    <select
                      id="bookOutlineSourceMaterial"
                      className="h-11 w-full rounded-xl border bg-background px-4 text-sm"
                      value={effectiveSourceMaterialId}
                      onChange={(event) => setSelectedSourceMaterialId(event.target.value)}
                      disabled={initializeFromMaterialPending}
                    >
                      {courseMaterials.map((material) => (
                        <option key={material.materialId} value={material.materialId}>
                          {material.title}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex justify-end">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => void onInitializeFromMaterial(effectiveSourceMaterialId)}
                      disabled={initializeFromMaterialPending || !effectiveSourceMaterialId}
                    >
                      {initializeFromMaterialPending ? "复用中..." : "一键复用网课树"}
                    </Button>
                  </div>
                </>
              ) : (
                <div className="rounded-[1rem] border border-border/70 bg-background px-4 py-3 text-xs leading-5 text-muted-foreground">
                  当前学科下还没有可复用的网课项目。先去新建或导入一个网课项目，再回来一键复用。
                </div>
              )}

              {initializeFromMaterialError ? <p className="text-sm text-destructive">{formatApiError(initializeFromMaterialError)}</p> : null}
            </div>

            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <div className="h-px flex-1 bg-border/70" />
              <span>或者手动粘贴目录</span>
              <div className="h-px flex-1 bg-border/70" />
            </div>

            <div className="space-y-2">
              <Label htmlFor="bookOutlineDraft">目录文本</Label>
              <textarea
                id="bookOutlineDraft"
                value={draftValue}
                onChange={(event) => onChange(event.target.value)}
                placeholder={`第一章 极限\n  1.1 函数\n  1.2 极限定义\n第二章 导数\n  2.1 导数概念`}
                rows={10}
                className="min-h-[15rem] w-full resize-y rounded-[1rem] border border-border/70 bg-background px-4 py-3 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/15"
              />
            </div>

            <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
              <span>当前已解析 {parsedCount} 行有效目录</span>
              <span>使用两个空格或一个 Tab 表示下一级缩进</span>
            </div>

            {validationMessage ? <p className="text-sm text-destructive">{validationMessage}</p> : null}

            <div className="flex justify-end">
              <Button type="button" onClick={() => void onInitialize()} disabled={isPending || !!validationMessage}>
                {isPending ? "初始化中..." : "初始化书本目录"}
              </Button>
            </div>
          </>
        )}

        {mutationError ? <p className="text-sm text-destructive">{formatApiError(mutationError)}</p> : null}
      </CardContent>
    </Card>
  )
}

function SubjectSettingsInfoCard(props: {
  subjectTitle: string
  isLoading: boolean
  isPending: boolean
  queryError: unknown
  saveError: unknown
  onSave: (title: string) => Promise<void>
}) {
  const {
    subjectTitle,
    isLoading,
    isPending,
    queryError,
    saveError,
    onSave,
  } = props
  const [titleDraft, setTitleDraft] = useState(subjectTitle)

  useEffect(() => {
    setTitleDraft(subjectTitle)
  }, [subjectTitle])

  const trimmedTitle = titleDraft.trim()
  const canSave = !isLoading && !isPending && !!trimmedTitle && trimmedTitle !== subjectTitle.trim()

  return (
    <Card className="theme-card">
      <CardHeader className="theme-card-header">
        <SettingsCardTitle icon={FolderTree} title="学科信息" />
      </CardHeader>
      <CardContent className="space-y-5 pt-0 text-sm">
        <section className="space-y-3">
          <div className="space-y-1">
            <div className="text-sm font-semibold text-foreground">学科名称</div>
          </div>
          <form
            className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-center"
            onSubmit={(event) => {
              event.preventDefault()
              if (!canSave) return
              void onSave(trimmedTitle)
            }}
          >
            <div>
              <Label htmlFor="subjectTitle" className="sr-only">
                学科名称
              </Label>
              <Input
                id="subjectTitle"
                value={titleDraft}
                onChange={(event) => setTitleDraft(event.target.value)}
                placeholder="输入新的学科名称"
                disabled={isLoading || isPending}
              />
            </div>
            <div className="flex items-center justify-end">
              <Button type="submit" disabled={!canSave} className="w-full md:w-auto">
                {isPending ? "保存中..." : "保存学科名称"}
              </Button>
            </div>
          </form>
          {queryError ? <p className="text-sm text-destructive">{formatApiError(queryError)}</p> : null}
          {saveError ? <p className="text-sm text-destructive">{formatApiError(saveError)}</p> : null}
        </section>
      </CardContent>
    </Card>
  )
}

function BasicInfoCard({
  actionableMissingInstanceCount,
  baiduNetdiskEnabled,
  browserLocalMediaEnabled,
  canChooseDirectory,
  canClearDirectory,
  canRequestDirectoryPermission,
  directoryAction,
  directoryBinding,
  directoryBusy,
  directoryPermission,
  entityLabel,
  entityPlaceholder,
  entitySaveLabel,
  entityTitle,
  importError,
  isLoading,
  isPending,
  isSubjectRoot,
  materialTitle,
  materialType,
  onOpenSubjectSettings,
  projectType,
  queryError,
  rollUpStrategy,
  saveError,
  rollUpStrategyError,
  rollUpStrategySaving,
  subjectTitle,
  onAuthorizeDirectory,
  onChangeRollUpStrategy,
  onClearDirectoryBinding,
  onOpenBaiduImport,
  onImportAuthorizedDirectory,
  onRequestDirectoryPermission,
  onSave,
}: {
  actionableMissingInstanceCount: number
  baiduNetdiskEnabled: boolean
  browserLocalMediaEnabled: boolean
  canChooseDirectory: boolean
  canClearDirectory: boolean
  canRequestDirectoryPermission: boolean
  directoryAction: "authorize" | "request" | "clear" | "import" | null
  directoryBinding: ReturnType<typeof useProjectDirectoryBinding>
  directoryBusy: boolean
  directoryPermission: "unsupported" | "missing" | "prompt" | "granted" | "denied"
  entityLabel: string
  entityPlaceholder: string
  entitySaveLabel: string
  entityTitle: string
  importError: unknown
  isLoading: boolean
  isPending: boolean
  isSubjectRoot: boolean
  materialTitle: string
  materialType: StudyMaterial["materialType"]
  onOpenSubjectSettings?: () => void
  projectType: ProjectType
  queryError: unknown
  rollUpStrategy: RollUpStrategy
  saveError: unknown
  rollUpStrategyError: unknown
  rollUpStrategySaving: boolean
  subjectTitle: string
  onAuthorizeDirectory: () => Promise<void>
  onChangeRollUpStrategy: (nextStrategy: RollUpStrategy) => Promise<void>
  onClearDirectoryBinding: () => Promise<void>
  onOpenBaiduImport: () => void
  onImportAuthorizedDirectory: (silentSuccess?: boolean) => Promise<void>
  onRequestDirectoryPermission: () => Promise<void>
  onSave: (title: string) => Promise<void>
}) {
  const [titleDraft, setTitleDraft] = useState(entityTitle)
  const subjectSummary = isSubjectRoot ? `${formatStudyMaterialTypeLabel(materialType)} · ${formatProjectTypeLabel(projectType)}` : formatStudyMaterialTypeLabel(materialType)
  const directorySummary = describeDirectorySummary(directoryPermission)

  useEffect(() => {
    setTitleDraft(entityTitle)
  }, [entityTitle])

  const trimmedTitle = titleDraft.trim()
  const canSave = !isLoading && !isPending && !!trimmedTitle && trimmedTitle !== entityTitle.trim()

  return (
    <Card className="theme-card">
      <CardHeader className="theme-card-header border-b border-[color:var(--theme-soft-border)] pb-6">
        <SettingsCardTitle icon={Settings2} title="基本信息" />
      </CardHeader>
      <CardContent className="space-y-5 pt-0 text-sm">
        <section className="grid gap-4 lg:grid-cols-[minmax(0,1.45fr)_minmax(280px,0.75fr)] lg:items-start">
          <div className="space-y-3">
            <div className="space-y-1">
              <div className="text-sm font-semibold text-foreground">{entityLabel}名称</div>
            </div>
            <form
              className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-center"
              onSubmit={(event) => {
                event.preventDefault()
                if (!canSave) return
                void onSave(trimmedTitle)
              }}
            >
              <div>
                <Label htmlFor="projectTitle" className="sr-only">
                  新名称
                </Label>
                <Input
                  id="projectTitle"
                  value={titleDraft}
                  onChange={(event) => setTitleDraft(event.target.value)}
                  placeholder={entityPlaceholder}
                  disabled={isLoading || isPending}
                />
              </div>
              <div className="flex items-center justify-end">
                <Button type="submit" disabled={!canSave} className="w-full md:w-auto">
                  {isPending ? "保存中..." : entitySaveLabel}
                </Button>
              </div>
            </form>
            {queryError ? <p className="text-sm text-destructive">{formatApiError(queryError)}</p> : null}
            {saveError ? <p className="text-sm text-destructive">{formatApiError(saveError)}</p> : null}
          </div>

          <div className="space-y-3">
            <div className="space-y-1">
              <div className="text-sm font-semibold text-foreground">{isSubjectRoot ? "当前项目" : "所属学科"}</div>
            </div>
            <div className="rounded-[1.2rem] border border-border/70 bg-muted/15 px-4 py-3">
              {isSubjectRoot ? (
                <>
                  <div className="text-sm font-semibold text-foreground">{materialTitle || "当前项目"}</div>
                  <div className="mt-1 text-xs text-muted-foreground">{formatStudyMaterialTypeLabel(materialType)} · {formatProjectTypeLabel(projectType)}</div>
                </>
              ) : (
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <div className="text-sm font-semibold text-foreground">{subjectTitle || "当前学科"}</div>
                    <span className="theme-pill-default inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold">
                      {subjectSummary}
                    </span>
                  </div>
                  {onOpenSubjectSettings ? (
                    <Button type="button" variant="outline" size="sm" onClick={onOpenSubjectSettings}>
                      学科设置
                    </Button>
                  ) : null}
                </div>
              )}
            </div>
          </div>
        </section>

        <div className="border-t border-border/60" />

        <section className="space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="text-sm font-semibold text-foreground">{isSubjectRoot ? "当前项目" : `当前${formatStudyMaterialTypeLabel(materialType)}项目`}</div>
            {projectType === "COURSE" && browserLocalMediaEnabled ? (
              <span
                className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${describeDirectoryPermissionTone(directoryPermission)}`}
              >
                {directorySummary}
              </span>
            ) : null}
          </div>

          {projectType === "COURSE" ? (
            <div className="space-y-3">
              {browserLocalMediaEnabled ? (
                <div className="theme-status-surface rounded-[1.35rem] border border-border/70 p-4">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                      <div className="text-sm text-foreground">
                        {directoryBinding.handleName ? directoryBinding.handleName : "当前项目还没有绑定浏览器目录。"}
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2 lg:justify-end">
                      {directoryPermission === "granted" ? (
                        <>
                          <Button type="button" data-guide-tour="import-directory-button" onClick={() => void onImportAuthorizedDirectory()} disabled={directoryBusy}>
                            {directoryAction === "import" ? "同步中..." : "同步目录内容"}
                          </Button>
                          <Button
                            type="button"
                            data-guide-tour="authorize-directory-button"
                            variant="outline"
                            onClick={() => void onAuthorizeDirectory()}
                            disabled={!canChooseDirectory || directoryBusy}
                          >
                            {directoryAction === "authorize" ? "打开目录选择器..." : "更换目录"}
                          </Button>
                        </>
                      ) : null}

                      {(directoryPermission === "missing" || directoryPermission === "unsupported") ? (
                        <Button type="button" data-guide-tour="authorize-directory-button" onClick={() => void onAuthorizeDirectory()} disabled={!canChooseDirectory || directoryBusy}>
                          {directoryAction === "authorize" ? "打开目录选择器..." : "选择目录"}
                        </Button>
                      ) : null}

                      {(directoryPermission === "prompt" || directoryPermission === "denied") ? (
                        <>
                          <Button
                            type="button"
                            data-guide-tour="authorize-directory-button"
                            onClick={() => void onRequestDirectoryPermission()}
                            disabled={!canRequestDirectoryPermission || directoryBusy}
                          >
                            {directoryAction === "request" ? "请求中..." : "继续授权"}
                          </Button>
                          <Button
                            type="button"
                            data-guide-tour="authorize-directory-button"
                            variant="outline"
                            onClick={() => void onAuthorizeDirectory()}
                            disabled={!canChooseDirectory || directoryBusy}
                          >
                            {directoryAction === "authorize" ? "打开目录选择器..." : "更换目录"}
                          </Button>
                        </>
                      ) : null}

                      {(directoryPermission === "granted" || directoryPermission === "prompt" || directoryPermission === "denied") &&
                      canClearDirectory ? (
                        <Button
                          type="button"
                          variant="ghost"
                          className="text-muted-foreground"
                          onClick={() => void onClearDirectoryBinding()}
                          disabled={!canClearDirectory || directoryBusy}
                        >
                          {directoryAction === "clear" ? "清除中..." : "清除本地绑定"}
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-[1.2rem] border border-border/70 bg-muted/15 px-4 py-4 text-sm text-muted-foreground">
                  当前部署没有开启浏览器本地目录模式。
                </div>
              )}

              {baiduNetdiskEnabled ? (
                <div className="theme-status-surface rounded-[1.35rem] border border-border/70 p-4">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="theme-meta-strong">百度网盘视频</span>
                        <span className="theme-pill-accent inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold">
                          已启用
                        </span>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        支持在当前项目里浏览百度网盘目录、导入视频并按实例播放；字幕会按同目录同名规则自动识别。
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2 lg:justify-end">
                      <Button type="button" onClick={onOpenBaiduImport}>
                        从百度网盘导入
                      </Button>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="rounded-[1.2rem] border border-border/70 bg-muted/15 px-4 py-4 text-sm text-muted-foreground">
              {projectType === "BOOK"
                ? `当前${isSubjectRoot ? "书本入口" : "书本项目"}不依赖浏览器目录授权；请使用“书本目录初始化”把目录文本转换为学习对象树。`
                : `当前${isSubjectRoot ? "零散知识入口" : "零散知识项目"}不接入素材目录，也不会维护学习对象树。`}
            </div>
          )}

          {projectType === "COURSE" && directoryBinding.error ? <p className="text-sm text-destructive">{directoryBinding.error}</p> : null}
          {projectType === "COURSE" && !directoryBinding.supported ? (
            <p className="text-sm text-muted-foreground">当前浏览器不支持目录授权。首版建议使用桌面 Chrome 或 Edge。</p>
          ) : null}
          {projectType === "COURSE" && importError ? <p className="text-sm text-destructive">{formatApiError(importError)}</p> : null}
        </section>

        <div className="border-t border-border/60" />

        <section className="space-y-4">
          <div className="space-y-1">
            <div className="text-sm font-semibold text-foreground">上推策略</div>
          </div>

          <div>
            <select
              id="rollUpStrategy"
              aria-label="选择上推策略"
              className="h-11 w-full rounded-xl border bg-background px-4 text-sm"
              value={rollUpStrategy}
              disabled={rollUpStrategySaving}
              onChange={(event) => {
                const nextStrategy = event.target.value as RollUpStrategy
                void onChangeRollUpStrategy(nextStrategy)
              }}
            >
              <option value="MANUAL">仅手动上推</option>
              <option value="THRESHOLD_AUTO">阈值自动上推</option>
              <option value="LEARNING_OBJECT_ISOMORPHIC">学习对象树同构上推</option>
            </select>
          </div>

          {rollUpStrategy === "LEARNING_OBJECT_ISOMORPHIC" && actionableMissingInstanceCount > 0 ? (
            <div className="rounded-[1.1rem] border border-amber-200 bg-amber-50/80 p-4 text-sm text-amber-900">
              当前有 {actionableMissingInstanceCount} 个待迁移的缺失实例，同构上推和学习任务提交都会先被门禁拦住。请先完成下方修复。
            </div>
          ) : null}

          {rollUpStrategyError ? <p className="text-sm text-destructive">{formatApiError(rollUpStrategyError)}</p> : null}
        </section>

      </CardContent>
    </Card>
  )
}

function LayerConfigEditor({
  canSave,
  existingLayerIndexes,
  initialConfig,
  knownLayerIndexes,
  layersError,
  mutationError,
  onSave,
  onSelectedLayerIndexChange,
  projectConfigError,
  saving,
  selectedLayerIndex,
}: {
  canSave: boolean
  existingLayerIndexes: number[]
  initialConfig: {
    reviewChainTemplate: ReviewChainTemplateItem[]
    aggregationKNode: number
    aggregationKPoint: number
    thresholdRollUpEnabled: boolean
  }
  knownLayerIndexes: number[]
  layersError: unknown
  mutationError: unknown
  onSave: (payload: {
    kNode: number
    kPoint: number
    reviewChainTemplate: ReviewChainTemplateItem[]
    thresholdRollUpEnabled: boolean
  }) => Promise<void>
  onSelectedLayerIndexChange: (layerIndex: number) => void
  projectConfigError: unknown
  saving: boolean
  selectedLayerIndex: number
}) {
  const [cfgKNode, setCfgKNode] = useState(() => String(initialConfig.aggregationKNode))
  const [cfgKPoint, setCfgKPoint] = useState(() => String(initialConfig.aggregationKPoint))
  const cfgThresholdRollUpEnabled = initialConfig.thresholdRollUpEnabled
  const [cfgTemplateItems, setCfgTemplateItems] = useState<TemplateEditorItem[]>(() => toTemplateEditorItems(initialConfig.reviewChainTemplate))
  const [cfgErr, setCfgErr] = useState<string | null>(null)
  const [pendingTemplateKind, setPendingTemplateKind] = useState<"" | "CONVERGENCE" | "REVIEW_TASK">("")

  function onAppendTemplateItem() {
    if (!pendingTemplateKind) return
    setCfgTemplateItems((prev) => [...prev, createTemplateEditorItem(pendingTemplateKind)])
    setPendingTemplateKind("")
  }

  async function onSaveLayerConfig() {
    setCfgErr(null)

    const kNode = Number(cfgKNode)
    const kPoint = Number(cfgKPoint)
    if (!Number.isInteger(kNode) || kNode < 1) {
      setCfgErr("节点阈值必须是大于等于 1 的整数")
      return
    }
    if (!Number.isInteger(kPoint) || kPoint < 1) {
      setCfgErr("复述点阈值必须是大于等于 1 的整数")
      return
    }

    const items: ReviewChainTemplateItem[] = []
    let hasConvergence = false

    for (const item of cfgTemplateItems) {
      if (item.kind === "CONVERGENCE") {
        hasConvergence = true
        items.push({ kind: "CONVERGENCE" })
        continue
      }

      const count = Number(item.count)
      if (!Number.isInteger(count) || count < 1) {
        setCfgErr("复习任务次数必须是大于等于 1 的整数")
        return
      }
      items.push(count === 1 ? { kind: "REVIEW_TASK" } : { kind: "REVIEW_TASK", count })
    }

    if (items.length === 0) {
      setCfgErr("模板不能为空")
      return
    }
    if (!hasConvergence) {
      setCfgErr("模板里至少需要一个收敛步骤")
      return
    }

    await onSave({ kNode, kPoint, reviewChainTemplate: items, thresholdRollUpEnabled: cfgThresholdRollUpEnabled })
  }

  const header = (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <SettingsCardTitle icon={Boxes} title="层配置" />

      <div className="w-full max-w-[360px] shrink-0 space-y-3">
        <div>
          <select
            id="configLayer"
            aria-label="选择已知层"
            className="h-11 w-full rounded-xl border bg-background px-4 text-sm"
            value={String(selectedLayerIndex)}
            onChange={(e) => {
              const next = Number(e.target.value)
              if (!Number.isInteger(next) || next < 0) return
              onSelectedLayerIndexChange(next)
            }}
            disabled={saving}
          >
            {knownLayerIndexes.map((idx) => (
              <option key={idx} value={idx}>
                第 {idx} 层{existingLayerIndexes.includes(idx) ? "（已创建）" : "（未创建）"}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  )

  const content = (
    <div className="space-y-5 text-sm">
      <section className="space-y-3">
        <div className="text-sm font-semibold text-foreground">阈值参数</div>
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="kNode">节点阈值</Label>
            <Input id="kNode" value={cfgKNode} onChange={(e) => setCfgKNode(e.target.value)} disabled={saving} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="kPoint">复述点阈值</Label>
            <Input id="kPoint" value={cfgKPoint} onChange={(e) => setCfgKPoint(e.target.value)} disabled={saving} />
          </div>
        </div>
      </section>

      <div className="border-t border-border/60" />

      <section className="space-y-3">
        <div className="text-sm font-semibold text-foreground">复习链模板</div>

        <div className="overflow-hidden rounded-[1.1rem] border border-border/70 bg-background">
          {cfgTemplateItems.length === 0 ? (
            <div className="px-4 py-6 text-sm text-muted-foreground">
              还没有模板步骤，请在下方选择步骤类型后点击加号。
            </div>
          ) : null}

          {cfgTemplateItems.map((item, index) => (
            <div key={item.id} className="border-t border-border/70 p-4 first:border-t-0">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex items-start gap-3">
                  <span className="theme-pill-default inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold">
                    第 {index + 1} 步
                  </span>
                  <div className="space-y-1">
                    <div className="text-sm font-medium text-foreground">{item.kind === "CONVERGENCE" ? "收敛" : "复习任务"}</div>
                    <div className="text-xs text-muted-foreground">
                      {item.kind === "CONVERGENCE"
                        ? "完成一轮后决定是否继续生成复习任务。"
                        : "在当前范围上直接生成待执行复习任务。"}
                    </div>
                  </div>
                </div>

                <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
                  {item.kind === "REVIEW_TASK" ? (
                    <div className="w-full max-w-[220px] space-y-2">
                      <Label htmlFor={`template-count-${item.id}`}>次数</Label>
                      <Input
                        id={`template-count-${item.id}`}
                        inputMode="numeric"
                        value={item.count}
                        onChange={(e) =>
                          setCfgTemplateItems((prev) =>
                            prev.map((current) =>
                              current.id === item.id
                                ? {
                                    ...current,
                                    count: e.target.value,
                                  }
                                : current,
                            ),
                          )
                        }
                        disabled={saving}
                      />
                    </div>
                  ) : (
                    <div className="text-xs text-muted-foreground">这个步骤没有额外参数</div>
                  )}

                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setCfgTemplateItems((prev) => prev.filter((current) => current.id !== item.id))}
                    disabled={saving}
                  >
                    删除
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="shrink-0"
            onClick={onAppendTemplateItem}
            disabled={saving || !pendingTemplateKind}
            aria-label="追加模板步骤"
          >
            <span className="text-lg leading-none">+</span>
          </Button>
          <div className="w-full sm:max-w-[220px]">
            <Label htmlFor="pendingTemplateKind" className="sr-only">
              选择步骤类型
            </Label>
            <select
              id="pendingTemplateKind"
              aria-label="选择步骤类型"
              className="h-10 w-full rounded-xl border bg-background px-4 text-sm"
              value={pendingTemplateKind}
              onChange={(e) => setPendingTemplateKind(e.target.value as "" | "CONVERGENCE" | "REVIEW_TASK")}
              disabled={saving}
            >
              <option value="">选择类型</option>
              <option value="CONVERGENCE">收敛</option>
              <option value="REVIEW_TASK">复习任务</option>
            </select>
          </div>
        </div>
      </section>

      <div className="flex justify-end">
        <Button onClick={() => void onSaveLayerConfig()} disabled={saving || !canSave}>
          {saving ? "保存中..." : "保存配置"}
        </Button>
      </div>

      {layersError ? <p className="text-sm text-destructive">{formatApiError(layersError)}</p> : null}
      {projectConfigError ? <p className="text-sm text-destructive">{formatApiError(projectConfigError)}</p> : null}
      {cfgErr ? <p className="text-sm text-destructive">{cfgErr}</p> : null}
      {mutationError ? <p className="text-sm text-destructive">{formatApiError(mutationError)}</p> : null}
    </div>
  )

  return (
    <Card className="theme-card">
      <CardHeader className="space-y-4 border-b border-[color:var(--theme-soft-border)] pb-6">{header}</CardHeader>
      <CardContent>{content}</CardContent>
    </Card>
  )
}
