import { useEffect, useMemo, useState } from "react"
import { useQueries } from "@tanstack/react-query"
import { Settings2, Sparkles, TriangleAlert } from "lucide-react"
import { useNavigate, useParams } from "react-router-dom"

import { listRecallPointsByInstance, type Instance } from "@/ui/api/instances"
import { ApiError } from "@/ui/api/http"
import type { ReviewChainTemplateItem } from "@/ui/api/projectConfig"
import type { ProjectType } from "@/ui/api/projects"
import { ContentNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { formatMaterialReference, formatRecallPointReference } from "@/ui/displayIdentifiers"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { scanProjectDirectoryMedia, useProjectDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import { formatProjectTypeLabel } from "@/ui/projectTypes"
import { useMyLlmSettings, useUpdateMyLlmSettings } from "@/ui/queries/profile"
import { useEditProject, useProject } from "@/ui/queries/projects"
import { useGlobalLlmSettings, useSystemCapabilities, useUpdateGlobalLlmSettings } from "@/ui/queries/system"
import {
  useBulkRemapRecallPointsInstance,
  useImportLearningObjectsFromBrowser,
  useInitializeBookLearningObjects,
  useInstances,
  useLayers,
  useProjectConfig,
  useSetReviewRecommendationConfig,
  useSetLayerConfig,
} from "@/ui/queries/workbench"
import { showErrorFeedback, showInfoFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"
import { BaiduNetdiskImportDialog } from "@/views/settings/components/BaiduNetdiskImportDialog"

let nextTemplateItemId = 1

type TemplateEditorItem = {
  id: number
  kind: "CONVERGENCE" | "REVIEW_TASK"
  count: string
}

type SettingsPanelKey = "basic" | "ai" | "missing"
type LlmPromptAssemblyMode = "system" | "user_concat"

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
  if (permission === "granted") return "border-emerald-200 bg-emerald-50 text-emerald-700"
  if (permission === "prompt") return "border-amber-200 bg-amber-50 text-amber-700"
  if (permission === "denied") return "border-rose-200 bg-rose-50 text-rose-700"
  return "border-slate-200 bg-slate-50 text-slate-600"
}

function describeLlmSource(source: "user" | "global" | "env" | "none") {
  if (source === "user") return "我的密钥"
  if (source === "global") return "全局密钥"
  if (source === "env") return "部署环境"
  return "未配置"
}

function describeLlmSourceTone(source: "user" | "global" | "env" | "none") {
  if (source === "user") return "border-emerald-200 bg-emerald-50 text-emerald-700"
  if (source === "global") return "border-emerald-200 bg-emerald-50 text-emerald-700"
  if (source === "env") return "border-sky-200 bg-sky-50 text-sky-700"
  return "border-slate-200 bg-slate-50 text-slate-600"
}

function PromptAssemblyModeSelector({
  value,
  onChange,
  disabled,
}: {
  value: LlmPromptAssemblyMode
  onChange: (value: LlmPromptAssemblyMode) => void
  disabled: boolean
}) {
  const options: Array<{
    value: LlmPromptAssemblyMode
    title: string
    description: string
  }> = [
    {
      value: "system",
      title: "系统信息",
      description: "优先让兼容 OpenAI 的主流 chat 模型按 system/context 角色理解规则与上下文。",
    },
    {
      value: "user_concat",
      title: "拼接到用户信息",
      description: "把系统规则和节点上下文一并拼进用户消息，适合 qvq 这类对 system 遵循较弱的模型。",
    },
  ]

  return (
    <div className="grid gap-2 md:grid-cols-2">
      {options.map((option) => {
        const active = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            disabled={disabled}
            onClick={() => onChange(option.value)}
            className={cn(
              "rounded-[1rem] border px-4 py-3 text-left transition",
              active
                ? "border-sky-400 bg-sky-50/80 shadow-[0_10px_30px_rgba(14,116,144,0.12)]"
                : "border-border/70 bg-background hover:border-sky-200 hover:bg-sky-50/40",
              disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer",
            )}
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-semibold text-foreground">{option.title}</span>
              <span
                className={cn(
                  "inline-flex h-5 min-w-5 items-center justify-center rounded-full border px-1.5 text-[11px] font-semibold",
                  active ? "border-sky-400 bg-sky-500 text-white" : "border-border/60 text-muted-foreground",
                )}
              >
                {active ? "当前" : "可选"}
              </span>
            </div>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">{option.description}</p>
          </button>
        )
      })}
    </div>
  )
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
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : tone === "warning"
        ? "border-amber-200 bg-amber-50 text-amber-700"
        : "border-slate-200 bg-slate-50 text-slate-600"

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
  const navigate = useNavigate()
  const pid = projectId ?? ""
  const projectQ = useProject(pid, { enabled: !!pid })
  const editProjectM = useEditProject()
  const capabilitiesQ = useSystemCapabilities()
  const authEnabled = capabilitiesQ.data?.authEnabled ?? false
  const globalLlmSettingsQ = useGlobalLlmSettings(capabilitiesQ.data !== undefined && !authEnabled)
  const updateGlobalLlmSettingsM = useUpdateGlobalLlmSettings()
  const myLlmSettingsQ = useMyLlmSettings(authEnabled)
  const updateMyLlmSettingsM = useUpdateMyLlmSettings()
  const directoryBinding = useProjectDirectoryBinding(pid)
  const directoryPermission = directoryBinding.permission
  const browserLocalMediaEnabled = capabilitiesQ.data?.browserLocalMediaEnabled ?? false
  const baiduNetdiskEnabled = capabilitiesQ.data?.baiduNetdiskEnabled ?? false

  const layersQ = useLayers(pid)
  const projectConfigQ = useProjectConfig(pid)
  const instancesQ = useInstances(pid)
  const importLearningObjectsM = useImportLearningObjectsFromBrowser(pid)
  const initializeBookLearningObjectsM = useInitializeBookLearningObjects(pid)
  const setLayerConfigM = useSetLayerConfig(pid)
  const setReviewRecommendationConfigM = useSetReviewRecommendationConfig(pid)
  const bulkRemapM = useBulkRemapRecallPointsInstance(pid)
  const projectType = projectConfigQ.data?.projectType ?? "COURSE"

  const existingLayerIndexes = useMemo(() => (layersQ.data ?? []).map((l) => l.layerIndex).sort((a, b) => a - b), [layersQ.data])
  const configuredLayerIndexes = useMemo(
    () =>
      Object.keys(projectConfigQ.data?.layerConfigs ?? {})
        .map((key) => Number(key))
        .filter((key) => Number.isInteger(key) && key >= 0)
        .sort((a, b) => a - b),
    [projectConfigQ.data?.layerConfigs],
  )
  const defaultLayerConfig = useMemo(
    () => ({ reviewChainTemplate: [{ kind: "CONVERGENCE" as const }], aggregationKNode: 10, aggregationKPoint: 200, thresholdRollUpEnabled: true }),
    [],
  )

  const [configLayerIndex, setConfigLayerIndex] = useState(0)
  const effectiveConfigLayerIndex = configLayerIndex
  const knownLayerIndexes = useMemo(
    () =>
      Array.from(new Set([...existingLayerIndexes, ...configuredLayerIndexes, effectiveConfigLayerIndex])).sort(
        (a, b) => a - b,
      ),
    [configuredLayerIndexes, effectiveConfigLayerIndex, existingLayerIndexes],
  )
  const selectedLayerExists = existingLayerIndexes.includes(effectiveConfigLayerIndex)
  const selectedLayerHasSavedConfig =
    projectConfigQ.data?.layerConfigs[String(effectiveConfigLayerIndex)] !== undefined

  const effectiveLayerConfig = useMemo(() => {
    const k = String(effectiveConfigLayerIndex)
    return projectConfigQ.data?.layerConfigs[k] ?? defaultLayerConfig
  }, [defaultLayerConfig, effectiveConfigLayerIndex, projectConfigQ.data?.layerConfigs])
  const templateConfigSignature = useMemo(
    () => JSON.stringify(effectiveLayerConfig.reviewChainTemplate),
    [effectiveLayerConfig.reviewChainTemplate],
  )
  const layerConfigVersion = `${effectiveConfigLayerIndex}:${effectiveLayerConfig.aggregationKNode}:${effectiveLayerConfig.aggregationKPoint}:${effectiveLayerConfig.thresholdRollUpEnabled}:${templateConfigSignature}`

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
  const aiStatusText = capabilitiesQ.data?.llmConfigured ? "LLM 已可用" : "LLM 未接通"
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
        showSuccessFeedback("目录权限已恢复", "现在可以扫描并导入这个项目的本地素材目录。")
        await importAuthorizedDirectory(true)
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
        "内容目录已导入",
        `已导入 ${scan.relativeFilePaths.length} 个媒体文件，新增 ${result.created_instances_count} 个实例。`,
      )
    } catch (err) {
      showErrorFeedback("导入本地目录失败", formatApiError(err))
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
      showSuccessFeedback("本地目录绑定已清除", "当前项目不再保留这个浏览器里的目录授权记录。")
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

  if (!pid) {
    return (
      <div className="space-y-4">
        <ContentNotice
          title="当前页面缺少项目上下文"
          message="当前链接缺少项目信息。请先返回项目列表，再重新进入项目设置。"
          action={<Button onClick={() => navigate("/projects")}>返回项目列表</Button>}
        />
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <Card className="theme-card">
        <CardHeader className="pb-4">
          <CardTitle>设置分区</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          <SettingsPanelSwitchCard
            title="基本设置"
            status={directoryStatusText}
            icon={Settings2}
            active={activePanel === "basic"}
            tone={directoryPermission === "granted" ? "success" : "default"}
            onClick={() => setActivePanel("basic")}
          />
          <SettingsPanelSwitchCard
            title="AI 设置"
            status={aiStatusText}
            icon={Sparkles}
            active={activePanel === "ai"}
            tone={capabilitiesQ.data?.llmConfigured ? "success" : "default"}
            onClick={() => setActivePanel("ai")}
          />
          <SettingsPanelSwitchCard
            title="缺失实例设置"
            status={missingStatusText}
            icon={TriangleAlert}
            active={activePanel === "missing"}
            tone={missingRepairCountsLoading || actionableMissingInstances.length > 0 ? "warning" : "default"}
            onClick={() => setActivePanel("missing")}
          />
        </CardContent>
      </Card>

      {activePanel === "basic" ? (
        <>
      <BasicInfoCard
        baiduNetdiskEnabled={baiduNetdiskEnabled}
        browserLocalMediaEnabled={browserLocalMediaEnabled}
        canChooseDirectory={canChooseDirectory}
        canClearDirectory={canClearDirectory}
        canRequestDirectoryPermission={canRequestDirectoryPermission}
        directoryAction={directoryAction}
        directoryBinding={directoryBinding}
        directoryBusy={directoryBusy}
        directoryPermission={directoryPermission}
        importError={importLearningObjectsM.error}
        isLoading={projectQ.isLoading}
        isPending={editProjectM.isPending}
        projectType={projectType}
        projectTitle={projectQ.project?.title ?? ""}
        queryError={projectQ.error}
        saveError={editProjectM.error}
        onAuthorizeDirectory={onAuthorizeDirectory}
        onClearDirectoryBinding={onClearDirectoryBinding}
        onOpenBaiduImport={() => setIsBaiduImportDialogOpen(true)}
        onImportAuthorizedDirectory={onImportAuthorizedDirectory}
        onRequestDirectoryPermission={onRequestDirectoryPermission}
        onSave={async (title) => {
          try {
            await editProjectM.mutateAsync({ projectId: pid, title })
            showSuccessFeedback("项目名称已更新", `当前项目现在显示为“${title}”。`)
          } catch (err) {
            showErrorFeedback("更新项目名称失败", formatApiError(err))
          }
        }}
      />

      {projectType === "BOOK" ? (
        <BookOutlineSetupCard
          draftValue={bookOutlineDraft}
          initialized={bookProjectAlreadyInitialized}
          isPending={initializeBookLearningObjectsM.isPending}
          mutationError={initializeBookLearningObjectsM.error}
          onChange={setBookOutlineDraft}
          onInitialize={onInitializeBookOutline}
          parsedCount={parsedBookOutlineItems.length}
          validationMessage={bookOutlineValidationMessage}
        />
      ) : null}

      <LayerConfigEditor
        key={layerConfigVersion}
        canSave={!!pid}
        existingLayerIndexes={existingLayerIndexes}
        initialConfig={effectiveLayerConfig}
        knownLayerIndexes={knownLayerIndexes}
        layersError={layersQ.error}
        mutationError={setLayerConfigM.error}
        projectConfigError={projectConfigQ.error}
        selectedLayerExists={selectedLayerExists}
        selectedLayerHasSavedConfig={selectedLayerHasSavedConfig}
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
                ? `第 ${effectiveConfigLayerIndex} 层现在使用 ${reviewChainTemplate.length} 个模板步骤，节点阈值 ${kNode}，复述点阈值 ${kPoint}，阈值自动上推已${thresholdRollUpEnabled ? "开启" : "关闭"}。`
                : `第 ${effectiveConfigLayerIndex} 层还不存在，已先保存预配置；等它被创建时会自动使用这 ${reviewChainTemplate.length} 个模板步骤、当前阈值和阈值自动上推${thresholdRollUpEnabled ? "开启" : "关闭"}状态。`,
            )
          } catch (err) {
            showErrorFeedback("保存层配置失败", formatApiError(err))
          }
        }}
        onSelectedLayerIndexChange={setConfigLayerIndex}
      />

      <BaiduNetdiskImportDialog
        projectId={pid}
        open={isBaiduImportDialogOpen}
        onOpenChange={setIsBaiduImportDialogOpen}
      />

      <ReviewRecommendationConfigCard
        config={projectConfigQ.data?.pushConfig ?? null}
        isLoading={projectConfigQ.isLoading}
        queryError={projectConfigQ.error}
        saveError={setReviewRecommendationConfigM.error}
        isPending={setReviewRecommendationConfigM.isPending}
        onSave={async ({ minRecallPointsToEnable, maxHistoryLen, recommendedBatchSize, forgettingCurveDecayPerDay }) => {
          try {
            await setReviewRecommendationConfigM.mutateAsync({
              minRecallPointsToEnable,
              maxHistoryLen,
              recommendedBatchSize,
              forgettingCurveDecayPerDay,
            })
            showSuccessFeedback(
              "推荐复习配置已保存",
              `现在会按最近 ${maxHistoryLen} 条历史、每批 ${recommendedBatchSize} 条、衰减率 ${forgettingCurveDecayPerDay.toFixed(2)} 来计算推荐复习。`,
            )
          } catch (err) {
            showErrorFeedback("保存推荐复习配置失败", formatApiError(err))
          }
        }}
      />
        </>
      ) : null}

      {activePanel === "ai" ? (
        <div className="space-y-5">
          {authEnabled ? (
            <>
              <UserLlmSettingsCard
                queryError={myLlmSettingsQ.error}
                saveError={updateMyLlmSettingsM.error}
                settings={myLlmSettingsQ.data}
                isLoading={myLlmSettingsQ.isLoading}
                isPending={updateMyLlmSettingsM.isPending}
                onClearApiKey={async ({ baseUrl, modelName, promptAssemblyMode }) => {
                  try {
                    await updateMyLlmSettingsM.mutateAsync({ baseUrl, modelName, promptAssemblyMode, clearApiKey: true })
                    showSuccessFeedback("我的 LLM 密钥已清除", "当前账号会停止使用已保存密钥；未重新保存前，这个账号的 LLM 能力视为未接通。")
                  } catch (err) {
                    showErrorFeedback("清除我的 LLM 密钥失败", formatApiError(err))
                  }
                }}
                onSave={async ({ baseUrl, modelName, promptAssemblyMode, apiKey }) => {
                  try {
                    await updateMyLlmSettingsM.mutateAsync({ baseUrl, modelName, promptAssemblyMode, apiKey })
                    showSuccessFeedback("我的 LLM 设置已保存", "当前账号之后在任意设备登录时都会复用这份 LLM 服务配置。")
                  } catch (err) {
                    showErrorFeedback("保存我的 LLM 设置失败", formatApiError(err))
                  }
                }}
              />
            </>
          ) : (
            <>
              <GlobalLlmSettingsCard
                title="全局 LLM 设置"
                saveLabel="保存全局设置"
                queryError={globalLlmSettingsQ.error}
                saveError={updateGlobalLlmSettingsM.error}
                settings={globalLlmSettingsQ.data}
                isLoading={globalLlmSettingsQ.isLoading}
                isPending={updateGlobalLlmSettingsM.isPending}
                onClearApiKey={async ({ baseUrl, modelName, promptAssemblyMode }) => {
                  try {
                    await updateGlobalLlmSettingsM.mutateAsync({ baseUrl, modelName, promptAssemblyMode, clearApiKey: true })
                    showSuccessFeedback("全局 LLM 密钥已清除", "系统会停止使用已保存的全局密钥。")
                  } catch (err) {
                    showErrorFeedback("清除全局 LLM 密钥失败", formatApiError(err))
                  }
                }}
                onSave={async ({ baseUrl, modelName, promptAssemblyMode, apiKey }) => {
                  try {
                    await updateGlobalLlmSettingsM.mutateAsync({ baseUrl, modelName, promptAssemblyMode, apiKey })
                    showSuccessFeedback("全局 LLM 设置已保存", "后端现在会通过已配置服务代理后续的大模型能力请求。")
                  } catch (err) {
                    showErrorFeedback("保存全局 LLM 设置失败", formatApiError(err))
                  }
                }}
              />
            </>
          )}
        </div>
      ) : null}

      {activePanel === "missing" ? (
      <Card className="theme-card">
        <CardHeader>
          <CardTitle>缺失材料修复</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          {projectType === "LOOSE_POINTS" ? (
            <div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">
              零散知识点项目不维护材料实例，因此这里没有缺失实例修复项。
            </div>
          ) : null}
          {instancesQ.isLoading ? <p className="text-sm text-muted-foreground">加载实例中...</p> : null}
          {instancesQ.error ? <p className="text-sm text-destructive">{formatApiError(instancesQ.error)}</p> : null}
          {!instancesQ.isLoading && !instancesQ.error && !missingRepairCountsLoading && actionableMissingInstances.length > 0 && projectType !== "LOOSE_POINTS" ? (
            <div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">
              这里只显示仍有活跃复述点需要迁移的缺失实例；已经没有迁移价值的旧实例会自动从列表里消失。
            </div>
          ) : null}
          {!instancesQ.isLoading && !instancesQ.error && missingRepairCountsLoading && projectType !== "LOOSE_POINTS" ? (
            <div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">正在整理仍需迁移的缺失实例...</div>
          ) : null}
          {!instancesQ.isLoading && !instancesQ.error && !missingRepairCountsLoading && actionableMissingInstances.length === 0 && projectType !== "LOOSE_POINTS" ? (
            <div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">当前没有需要迁移的缺失材料实例。</div>
          ) : null}

          <div className="space-y-3">
            {projectType !== "LOOSE_POINTS" ? actionableMissingInstances.map((instance) => {
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
            }) : null}
          </div>

          {projectType !== "LOOSE_POINTS" && bulkRemapM.error ? <p className="text-sm text-destructive">{formatApiError(bulkRemapM.error)}</p> : null}
        </CardContent>
      </Card>
      ) : null}
    </div>
  )
}

function ReviewRecommendationConfigCard(props: {
  config: {
    minRecallPointsToEnable: number
    maxHistoryLen: number
    recommendedBatchSize: number
    forgettingCurveDecayPerDay: number
  } | null
  isLoading: boolean
  queryError: unknown
  saveError: unknown
  isPending: boolean
  onSave: (params: {
    minRecallPointsToEnable: number
    maxHistoryLen: number
    recommendedBatchSize: number
    forgettingCurveDecayPerDay: number
  }) => Promise<void>
}) {
  const { config, isLoading, queryError, saveError, isPending, onSave } = props
  const [minRecallPointsToEnable, setMinRecallPointsToEnable] = useState("")
  const [maxHistoryLen, setMaxHistoryLen] = useState("")
  const [recommendedBatchSize, setRecommendedBatchSize] = useState("")
  const [forgettingCurveDecayPerDay, setForgettingCurveDecayPerDay] = useState("")

  useEffect(() => {
    if (!config) return
    setMinRecallPointsToEnable(String(config.minRecallPointsToEnable))
    setMaxHistoryLen(String(config.maxHistoryLen))
    setRecommendedBatchSize(String(config.recommendedBatchSize))
    setForgettingCurveDecayPerDay(String(config.forgettingCurveDecayPerDay))
  }, [config])

  const parsedMin = Number(minRecallPointsToEnable)
  const parsedHistory = Number(maxHistoryLen)
  const parsedBatch = Number(recommendedBatchSize)
  const parsedDecay = Number(forgettingCurveDecayPerDay)
  const canSave =
    Number.isFinite(parsedMin) &&
    parsedMin >= 0 &&
    Number.isInteger(parsedMin) &&
    Number.isFinite(parsedHistory) &&
    parsedHistory >= 0 &&
    Number.isInteger(parsedHistory) &&
    Number.isFinite(parsedBatch) &&
    parsedBatch >= 1 &&
    Number.isInteger(parsedBatch) &&
    Number.isFinite(parsedDecay) &&
    parsedDecay > 0

  return (
    <Card className="theme-card">
      <CardHeader>
        <CardTitle>推荐复习配置</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          这里配置的是只读推荐复习，不会替代正式复习任务。推荐页会按遗忘曲线给复述点排序，并按批次分组展示。
        </p>
        {isLoading ? <p className="text-sm text-muted-foreground">加载推荐复习配置中...</p> : null}
        {queryError ? <p className="text-sm text-destructive">{formatApiError(queryError)}</p> : null}
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="review-config-threshold">启用门槛</Label>
            <Input id="review-config-threshold" value={minRecallPointsToEnable} onChange={(e) => setMinRecallPointsToEnable(e.target.value)} disabled={isPending} />
            <p className="text-xs text-muted-foreground">活跃复述点少于这个数量时，推荐复习页会返回空列表。建议小项目保持 0。</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="review-config-history">历史窗口</Label>
            <Input id="review-config-history" value={maxHistoryLen} onChange={(e) => setMaxHistoryLen(e.target.value)} disabled={isPending} />
            <p className="text-xs text-muted-foreground">计算推荐指数时最多使用最近多少条正式复习记录。0 表示按“未复习”处理。</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="review-config-batch">每批条数</Label>
            <Input id="review-config-batch" value={recommendedBatchSize} onChange={(e) => setRecommendedBatchSize(e.target.value)} disabled={isPending} />
            <p className="text-xs text-muted-foreground">推荐复习页每次默认展示多少条，用户点“继续推荐”后会切到下一批。</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="review-config-decay">遗忘衰减率 λ / 天</Label>
            <Input id="review-config-decay" value={forgettingCurveDecayPerDay} onChange={(e) => setForgettingCurveDecayPerDay(e.target.value)} disabled={isPending} />
            <p className="text-xs text-muted-foreground">数值越大，系统越认为记忆衰减更快，推荐指数上升也越快。</p>
          </div>
        </div>
        <Button
          onClick={() =>
            void onSave({
              minRecallPointsToEnable: parsedMin,
              maxHistoryLen: parsedHistory,
              recommendedBatchSize: parsedBatch,
              forgettingCurveDecayPerDay: parsedDecay,
            })
          }
          disabled={!canSave || isPending}
        >
          {isPending ? "保存中..." : "保存推荐复习配置"}
        </Button>
        {saveError ? <p className="text-sm text-destructive">{formatApiError(saveError)}</p> : null}
      </CardContent>
    </Card>
  )
}

function BookOutlineSetupCard({
  draftValue,
  initialized,
  isPending,
  mutationError,
  onChange,
  onInitialize,
  parsedCount,
  validationMessage,
}: {
  draftValue: string
  initialized: boolean
  isPending: boolean
  mutationError: unknown
  onChange: (value: string) => void
  onInitialize: () => Promise<void>
  parsedCount: number
  validationMessage: string | null
}) {
  return (
    <Card className="theme-card">
      <CardHeader>
        <CardTitle>书本目录初始化</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 pt-0 text-sm">
        <div className="rounded-[1.2rem] border border-border/70 bg-muted/15 px-4 py-4 text-muted-foreground">
          书本项目会维护学习对象树，但目录来源不是媒体扫描，而是你手工提供的目录文本。系统会把末级目录项自动转换为可绑定复述点的书本实例。
        </div>

        {initialized ? (
          <div className="rounded-[1.2rem] border border-emerald-200 bg-emerald-50 px-4 py-4 text-emerald-700">
            当前书本项目已经存在目录节点和实例。如需重新初始化，请先清理现有目录结构后再执行。
          </div>
        ) : (
          <>
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

function BasicInfoCard({
  baiduNetdiskEnabled,
  browserLocalMediaEnabled,
  canChooseDirectory,
  canClearDirectory,
  canRequestDirectoryPermission,
  directoryAction,
  directoryBinding,
  directoryBusy,
  directoryPermission,
  importError,
  isLoading,
  isPending,
  projectType,
  projectTitle,
  queryError,
  saveError,
  onAuthorizeDirectory,
  onClearDirectoryBinding,
  onOpenBaiduImport,
  onImportAuthorizedDirectory,
  onRequestDirectoryPermission,
  onSave,
}: {
  baiduNetdiskEnabled: boolean
  browserLocalMediaEnabled: boolean
  canChooseDirectory: boolean
  canClearDirectory: boolean
  canRequestDirectoryPermission: boolean
  directoryAction: "authorize" | "request" | "clear" | "import" | null
  directoryBinding: ReturnType<typeof useProjectDirectoryBinding>
  directoryBusy: boolean
  directoryPermission: "unsupported" | "missing" | "prompt" | "granted" | "denied"
  importError: unknown
  isLoading: boolean
  isPending: boolean
  projectType: ProjectType
  projectTitle: string
  queryError: unknown
  saveError: unknown
  onAuthorizeDirectory: () => Promise<void>
  onClearDirectoryBinding: () => Promise<void>
  onOpenBaiduImport: () => void
  onImportAuthorizedDirectory: (silentSuccess?: boolean) => Promise<void>
  onRequestDirectoryPermission: () => Promise<void>
  onSave: (title: string) => Promise<void>
}) {
  const [titleDraft, setTitleDraft] = useState(projectTitle)

  useEffect(() => {
    setTitleDraft(projectTitle)
  }, [projectTitle])

  const trimmedTitle = titleDraft.trim()
  const canSave = !isLoading && !isPending && !!trimmedTitle && trimmedTitle !== projectTitle.trim()

  return (
    <Card className="theme-card">
      <CardHeader>
        <CardTitle>基本信息</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5 pt-0 text-sm">
        <section className="space-y-3">
          <div className="space-y-1">
            <div className="text-sm font-semibold text-foreground">项目名称</div>
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
                placeholder="输入新的项目名称"
                disabled={isLoading || isPending}
              />
            </div>
            <div className="flex items-center justify-end">
              <Button type="submit" disabled={!canSave} className="w-full md:w-auto">
                {isPending ? "保存中..." : "保存项目名称"}
              </Button>
            </div>
          </form>
          {queryError ? <p className="text-sm text-destructive">{formatApiError(queryError)}</p> : null}
          {saveError ? <p className="text-sm text-destructive">{formatApiError(saveError)}</p> : null}
        </section>

        <div className="border-t border-border/60" />

        <section className="space-y-3">
          <div className="space-y-1">
            <div className="text-sm font-semibold text-foreground">项目类型</div>
            <div className="text-sm text-muted-foreground">项目类型会统一约束当前项目里复述点是否需要学习对象树、实例和锚点。</div>
          </div>
          <div className="rounded-[1.2rem] border border-border/70 bg-muted/15 px-4 py-4">
            <div className="text-sm font-semibold text-foreground">{formatProjectTypeLabel(projectType)}</div>
            <div className="mt-1 text-sm text-muted-foreground">
              {projectType === "COURSE"
                ? "使用视频实例和可解析时间锚点。"
                : projectType === "BOOK"
                  ? "使用手工目录初始化的学习对象树，并为复述点绑定文本锚点。"
                  : "直接录入项目级零散知识点，不使用学习对象树，也不绑定锚点。"}
            </div>
          </div>
        </section>

        <div className="border-t border-border/60" />

        <section className="space-y-3">
          <div className="space-y-1">
            <div className="text-sm font-semibold text-foreground">素材接入</div>
          </div>

          {projectType === "COURSE" ? (
            <div className="space-y-3">
              {browserLocalMediaEnabled ? (
                <div className="theme-status-surface rounded-[1.35rem] border border-border/70 p-4">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-3">
                        <span className="theme-meta-strong">本地素材目录</span>
                        <span
                          className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${describeDirectoryPermissionTone(directoryPermission)}`}
                        >
                          {describeDirectoryPermission(directoryPermission)}
                        </span>
                      </div>
                      <div className="text-sm text-foreground">
                        {directoryBinding.handleName ? directoryBinding.handleName : "当前项目还没有绑定浏览器目录。"}
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2 lg:justify-end">
                      {directoryPermission === "granted" ? (
                        <>
                          <Button type="button" onClick={() => void onImportAuthorizedDirectory()} disabled={directoryBusy}>
                            {directoryAction === "import" ? "同步中..." : "同步目录内容"}
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => void onAuthorizeDirectory()}
                            disabled={!canChooseDirectory || directoryBusy}
                          >
                            {directoryAction === "authorize" ? "打开目录选择器..." : "更换目录"}
                          </Button>
                        </>
                      ) : null}

                      {(directoryPermission === "missing" || directoryPermission === "unsupported") ? (
                        <Button type="button" onClick={() => void onAuthorizeDirectory()} disabled={!canChooseDirectory || directoryBusy}>
                          {directoryAction === "authorize" ? "打开目录选择器..." : "选择目录"}
                        </Button>
                      ) : null}

                      {(directoryPermission === "prompt" || directoryPermission === "denied") ? (
                        <>
                          <Button
                            type="button"
                            onClick={() => void onRequestDirectoryPermission()}
                            disabled={!canRequestDirectoryPermission || directoryBusy}
                          >
                            {directoryAction === "request" ? "请求中..." : "继续授权"}
                          </Button>
                          <Button
                            type="button"
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
                        <span className="inline-flex items-center rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-700">
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
                ? "书本项目不依赖浏览器目录授权；请使用“书本目录初始化”把目录文本转换为学习对象树。"
                : "零散知识点项目不接入素材目录，也不会维护学习对象树。"}
            </div>
          )}

          {projectType === "COURSE" && directoryBinding.error ? <p className="text-sm text-destructive">{directoryBinding.error}</p> : null}
          {projectType === "COURSE" && !directoryBinding.supported ? (
            <p className="text-sm text-muted-foreground">当前浏览器不支持目录授权。首版建议使用桌面 Chrome 或 Edge。</p>
          ) : null}
          {projectType === "COURSE" && importError ? <p className="text-sm text-destructive">{formatApiError(importError)}</p> : null}
        </section>
      </CardContent>
    </Card>
  )
}

const SAVED_API_KEY_MASK = "********"

function SavedApiKeyInput({
  id,
  draftValue,
  onDraftChange,
  savedApiKeyConfigured,
  disabled,
  emptyPlaceholder,
  savedPlaceholder,
}: {
  id: string
  draftValue: string
  onDraftChange: (value: string) => void
  savedApiKeyConfigured: boolean
  disabled: boolean
  emptyPlaceholder: string
  savedPlaceholder: string
}) {
  const [isEditingSavedKey, setIsEditingSavedKey] = useState(false)

  useEffect(() => {
    setIsEditingSavedKey(false)
  }, [id, savedApiKeyConfigured])

  const showSavedMask = savedApiKeyConfigured && !isEditingSavedKey && !draftValue.trim()

  return (
    <Input
      id={id}
      type="password"
      value={showSavedMask ? SAVED_API_KEY_MASK : draftValue}
      onFocus={() => {
        if (showSavedMask && !disabled) {
          setIsEditingSavedKey(true)
          onDraftChange("")
        }
      }}
      onBlur={() => {
        if (!draftValue.trim()) {
          setIsEditingSavedKey(false)
        }
      }}
      onChange={(event) => onDraftChange(event.target.value)}
      placeholder={savedApiKeyConfigured ? savedPlaceholder : emptyPlaceholder}
      disabled={disabled}
      autoComplete="off"
    />
  )
}

function GlobalLlmSettingsCard({
  title,
  saveLabel,
  settings,
  isLoading,
  isPending,
  queryError,
  saveError,
  onSave,
  onClearApiKey,
}: {
  title: string
  saveLabel: string
  settings:
    | {
        baseUrl: string
        modelName: string
        promptAssemblyMode: LlmPromptAssemblyMode
        savedApiKeyConfigured: boolean
        savedApiKeyPreview: string | null
        llmConfigured: boolean
        storyGenerationConfigured: boolean
        llmSource: "user" | "global" | "env" | "none"
      }
    | undefined
  isLoading: boolean
  isPending: boolean
  queryError: unknown
  saveError: unknown
  onSave: (payload: { baseUrl: string; modelName: string; promptAssemblyMode: LlmPromptAssemblyMode; apiKey?: string }) => Promise<void>
  onClearApiKey: (payload: { baseUrl: string; modelName: string; promptAssemblyMode: LlmPromptAssemblyMode }) => Promise<void>
}) {
  const [baseUrlDraft, setBaseUrlDraft] = useState("")
  const [modelDraft, setModelDraft] = useState("")
  const [apiKeyDraft, setApiKeyDraft] = useState("")
  const [promptAssemblyModeDraft, setPromptAssemblyModeDraft] = useState<LlmPromptAssemblyMode>("system")

  useEffect(() => {
    setBaseUrlDraft(settings?.baseUrl ?? "")
    setModelDraft(settings?.modelName ?? "")
    setApiKeyDraft("")
    setPromptAssemblyModeDraft(settings?.promptAssemblyMode ?? "system")
  }, [settings?.baseUrl, settings?.modelName, settings?.promptAssemblyMode])

  const trimmedBaseUrl = baseUrlDraft.trim()
  const trimmedModel = modelDraft.trim()
  const trimmedApiKey = apiKeyDraft.trim()
  const canSave =
    !isLoading &&
    !isPending &&
    !!trimmedBaseUrl &&
    !!trimmedModel &&
    (
      trimmedBaseUrl !== (settings?.baseUrl ?? "") ||
      trimmedModel !== (settings?.modelName ?? "") ||
      promptAssemblyModeDraft !== (settings?.promptAssemblyMode ?? "system") ||
      !!trimmedApiKey
    )
  const canClearApiKey = !isLoading && !isPending && !!settings?.savedApiKeyConfigured

  return (
    <Card className="theme-card">
      <CardHeader>
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="space-y-1">
            <CardTitle>{title}</CardTitle>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${describeLlmSourceTone(settings?.llmSource ?? "none")}`}
            >
              {describeLlmSource(settings?.llmSource ?? "none")}
            </span>
            <span className="theme-meta px-3 py-1.5 text-xs">
              {settings?.llmConfigured ? "LLM 已可用" : "LLM 未可用"}
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="theme-status-surface space-y-3 rounded-[1.2rem] border border-border/70 p-4">
          <div className="grid gap-3">
            <div className="space-y-2">
              <Label htmlFor="globalLlmBaseUrl">Base URL</Label>
              <Input
                id="globalLlmBaseUrl"
                value={baseUrlDraft}
                onChange={(event) => setBaseUrlDraft(event.target.value)}
                placeholder="https://api.openai.com/v1"
                disabled={isLoading || isPending}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="globalLlmModel">模型名</Label>
              <Input
                id="globalLlmModel"
                value={modelDraft}
                onChange={(event) => setModelDraft(event.target.value)}
                placeholder="gpt-4o-mini"
                disabled={isLoading || isPending}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="globalLlmApiKey">API 密钥</Label>
              <SavedApiKeyInput
                id="globalLlmApiKey"
                draftValue={apiKeyDraft}
                onDraftChange={setApiKeyDraft}
                savedApiKeyConfigured={!!settings?.savedApiKeyConfigured}
                emptyPlaceholder="输入新的 API Key"
                savedPlaceholder="输入新的 API Key"
                disabled={isLoading || isPending}
              />
            </div>
            <div className="space-y-2">
              <Label>提示拼接模式</Label>
              <PromptAssemblyModeSelector
                value={promptAssemblyModeDraft}
                onChange={setPromptAssemblyModeDraft}
                disabled={isLoading || isPending}
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              disabled={!canSave}
              onClick={() =>
                void onSave({
                  baseUrl: trimmedBaseUrl,
                  modelName: trimmedModel,
                  promptAssemblyMode: promptAssemblyModeDraft,
                  apiKey: trimmedApiKey || undefined,
                })
              }
            >
              {isPending ? "保存中..." : saveLabel}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={!canClearApiKey}
              onClick={() =>
                void onClearApiKey({
                  baseUrl: trimmedBaseUrl || settings?.baseUrl || "",
                  modelName: trimmedModel || settings?.modelName || "",
                  promptAssemblyMode: promptAssemblyModeDraft,
                })
              }
            >
              清除已保存密钥
            </Button>
          </div>
        </div>

        {isLoading ? <p className="text-sm text-muted-foreground">加载{title}中...</p> : null}
        {queryError ? <p className="text-sm text-destructive">{formatApiError(queryError)}</p> : null}
        {saveError ? <p className="text-sm text-destructive">{formatApiError(saveError)}</p> : null}
      </CardContent>
    </Card>
  )
}

function UserLlmSettingsCard({
  settings,
  isLoading,
  isPending,
  queryError,
  saveError,
  onSave,
  onClearApiKey,
}: {
  settings:
    | {
        baseUrl: string
        modelName: string
        promptAssemblyMode: LlmPromptAssemblyMode
        savedApiKeyConfigured: boolean
        savedApiKeyPreview: string | null
        llmConfigured: boolean
        storyGenerationConfigured: boolean
        llmSource: "user" | "global" | "env" | "none"
      }
    | undefined
  isLoading: boolean
  isPending: boolean
  queryError: unknown
  saveError: unknown
  onSave: (payload: { baseUrl: string; modelName: string; promptAssemblyMode: LlmPromptAssemblyMode; apiKey?: string }) => Promise<void>
  onClearApiKey: (payload: { baseUrl: string; modelName: string; promptAssemblyMode: LlmPromptAssemblyMode }) => Promise<void>
}) {
  const [baseUrlDraft, setBaseUrlDraft] = useState("")
  const [modelDraft, setModelDraft] = useState("")
  const [apiKeyDraft, setApiKeyDraft] = useState("")
  const [promptAssemblyModeDraft, setPromptAssemblyModeDraft] = useState<LlmPromptAssemblyMode>("system")

  useEffect(() => {
    setBaseUrlDraft(settings?.baseUrl ?? "")
    setModelDraft(settings?.modelName ?? "")
    setApiKeyDraft("")
    setPromptAssemblyModeDraft(settings?.promptAssemblyMode ?? "system")
  }, [settings?.baseUrl, settings?.modelName, settings?.promptAssemblyMode])

  const trimmedBaseUrl = baseUrlDraft.trim()
  const trimmedModel = modelDraft.trim()
  const trimmedApiKey = apiKeyDraft.trim()
  const canSave =
    !isLoading &&
    !isPending &&
    !!trimmedBaseUrl &&
    !!trimmedModel &&
    (
      trimmedBaseUrl !== (settings?.baseUrl ?? "") ||
      trimmedModel !== (settings?.modelName ?? "") ||
      promptAssemblyModeDraft !== (settings?.promptAssemblyMode ?? "system") ||
      !!trimmedApiKey
    )
  const canClearApiKey = !isLoading && !isPending && !!settings?.savedApiKeyConfigured

  return (
    <Card className="theme-card">
      <CardHeader>
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="space-y-1">
            <CardTitle>我的 LLM 设置</CardTitle>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${describeLlmSourceTone(settings?.llmSource ?? "none")}`}
            >
              {describeLlmSource(settings?.llmSource ?? "none")}
            </span>
            <span className="theme-meta px-3 py-1.5 text-xs">
              {settings?.llmConfigured ? "当前账号已就绪" : "当前账号未配置"}
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="theme-status-surface space-y-3 rounded-[1.2rem] border border-border/70 p-4">
          <div className="grid gap-3">
            <div className="space-y-2">
              <Label htmlFor="userLlmBaseUrl">Base URL</Label>
              <Input
                id="userLlmBaseUrl"
                value={baseUrlDraft}
                onChange={(event) => setBaseUrlDraft(event.target.value)}
                placeholder="https://api.openai.com/v1"
                disabled={isLoading || isPending}
                autoComplete="off"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="userLlmModel">模型名</Label>
              <Input
                id="userLlmModel"
                value={modelDraft}
                onChange={(event) => setModelDraft(event.target.value)}
                placeholder="gpt-4o-mini"
                disabled={isLoading || isPending}
                autoComplete="off"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="userLlmApiKey">API 密钥</Label>
              <SavedApiKeyInput
                id="userLlmApiKey"
                draftValue={apiKeyDraft}
                onDraftChange={setApiKeyDraft}
                savedApiKeyConfigured={!!settings?.savedApiKeyConfigured}
                emptyPlaceholder="输入你的 API Key"
                savedPlaceholder="输入你的 API Key"
                disabled={isLoading || isPending}
              />
            </div>
            <div className="space-y-2">
              <Label>提示拼接模式</Label>
              <PromptAssemblyModeSelector
                value={promptAssemblyModeDraft}
                onChange={setPromptAssemblyModeDraft}
                disabled={isLoading || isPending}
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              disabled={!canSave}
              onClick={() =>
                void onSave({
                  baseUrl: trimmedBaseUrl,
                  modelName: trimmedModel,
                  promptAssemblyMode: promptAssemblyModeDraft,
                  apiKey: trimmedApiKey || undefined,
                })
              }
            >
              {isPending ? "保存中..." : "保存到我的账号"}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={!canClearApiKey}
              onClick={() =>
                void onClearApiKey({
                  baseUrl: trimmedBaseUrl || settings?.baseUrl || "",
                  modelName: trimmedModel || settings?.modelName || "",
                  promptAssemblyMode: promptAssemblyModeDraft,
                })
              }
            >
              清除我的密钥
            </Button>
          </div>
        </div>

        {isLoading ? <p className="text-sm text-muted-foreground">加载我的 LLM 设置中...</p> : null}
        {queryError ? <p className="text-sm text-destructive">{formatApiError(queryError)}</p> : null}
        {saveError ? <p className="text-sm text-destructive">{formatApiError(saveError)}</p> : null}
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
  selectedLayerExists,
  selectedLayerHasSavedConfig,
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
  selectedLayerExists: boolean
  selectedLayerHasSavedConfig: boolean
  saving: boolean
  selectedLayerIndex: number
}) {
  const [layerIndexDraft, setLayerIndexDraft] = useState(() => String(selectedLayerIndex))
  const [cfgKNode, setCfgKNode] = useState(() => String(initialConfig.aggregationKNode))
  const [cfgKPoint, setCfgKPoint] = useState(() => String(initialConfig.aggregationKPoint))
  const [cfgThresholdRollUpEnabled, setCfgThresholdRollUpEnabled] = useState(() => initialConfig.thresholdRollUpEnabled)
  const [cfgTemplateItems, setCfgTemplateItems] = useState<TemplateEditorItem[]>(() => toTemplateEditorItems(initialConfig.reviewChainTemplate))
  const [cfgErr, setCfgErr] = useState<string | null>(null)
  const [layerIndexErr, setLayerIndexErr] = useState<string | null>(null)
  const [pendingTemplateKind, setPendingTemplateKind] = useState<"" | "CONVERGENCE" | "REVIEW_TASK">("")
  const existingLayerSummary = existingLayerIndexes.length > 0 ? existingLayerIndexes.join(" / ") : "暂无"
  const layerStatusText = selectedLayerExists
    ? selectedLayerHasSavedConfig
      ? "当前层已经存在，下面显示的是它的已保存配置。"
      : "当前层已经存在，但还没有专属配置，当前显示的是系统默认值。"
    : selectedLayerHasSavedConfig
      ? "当前层还不存在，下面显示的是它的预配置；该层创建后会自动使用。"
      : "当前层还不存在，当前显示的是系统默认值；保存后会成为这层的预配置。"

  useEffect(() => {
    setLayerIndexDraft(String(selectedLayerIndex))
    setLayerIndexErr(null)
  }, [selectedLayerIndex])

  function onAppendTemplateItem() {
    if (!pendingTemplateKind) return
    setCfgTemplateItems((prev) => [...prev, createTemplateEditorItem(pendingTemplateKind)])
    setPendingTemplateKind("")
  }

  function applyLayerIndexDraft() {
    const raw = layerIndexDraft.trim()
    if (!raw) {
      setLayerIndexErr("层索引必须是大于等于 0 的整数")
      return
    }
    const next = Number(raw)
    if (!Number.isInteger(next) || next < 0) {
      setLayerIndexErr("层索引必须是大于等于 0 的整数")
      return
    }
    setLayerIndexErr(null)
    onSelectedLayerIndexChange(next)
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

  return (
    <Card className="theme-card">
      <CardHeader className="space-y-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-1">
            <CardTitle>层配置</CardTitle>
            <p className="text-sm text-muted-foreground">{layerStatusText}</p>
          </div>

          <div className="w-full max-w-[360px] shrink-0 space-y-3">
            <div className="space-y-2">
              <Label htmlFor="configLayer">已知层</Label>
              <select
                id="configLayer"
                aria-label="选择已知层"
                className="h-11 w-full rounded-xl border bg-background px-4 text-sm"
                value={String(selectedLayerIndex)}
                onChange={(e) => {
                  const next = Number(e.target.value)
                  if (!Number.isInteger(next) || next < 0) return
                  setLayerIndexDraft(String(next))
                  setLayerIndexErr(null)
                  onSelectedLayerIndexChange(next)
                }}
                disabled={knownLayerIndexes.length === 0 || saving}
              >
                {knownLayerIndexes.map((idx) => (
                  <option key={idx} value={idx}>
                    第 {idx} 层{existingLayerIndexes.includes(idx) ? "" : "（预配置）"}
                  </option>
                ))}
              </select>
              <p className="text-xs text-muted-foreground">当前已创建的层：{existingLayerSummary}</p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="customConfigLayer">跳到任意层索引</Label>
              <div className="flex gap-2">
                <Input
                  id="customConfigLayer"
                  inputMode="numeric"
                  value={layerIndexDraft}
                  onChange={(e) => {
                    setLayerIndexDraft(e.target.value.replace(/[^\d]/g, ""))
                    if (layerIndexErr) setLayerIndexErr(null)
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault()
                      applyLayerIndexDraft()
                    }
                  }}
                  disabled={saving}
                />
                <Button type="button" variant="outline" onClick={applyLayerIndexDraft} disabled={saving}>
                  切换
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">这里可以直接输入尚未创建的层索引，先保存预配置。</p>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="grid gap-4">
          <div className="grid gap-4 rounded-[1.2rem] border border-border/70 bg-muted/15 p-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="kNode">节点阈值</Label>
              <Input id="kNode" value={cfgKNode} onChange={(e) => setCfgKNode(e.target.value)} disabled={saving} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="kPoint">复述点阈值</Label>
              <Input id="kPoint" value={cfgKPoint} onChange={(e) => setCfgKPoint(e.target.value)} disabled={saving} />
            </div>
          </div>

          <div className="rounded-[1.2rem] border border-border/70 bg-muted/15 p-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="space-y-1">
                <Label>阈值自动上推</Label>
                <p className="text-xs text-muted-foreground">
                  {cfgThresholdRollUpEnabled
                    ? "达到节点数或复述点阈值后，系统会自动进入聚合周期。"
                    : "已关闭自动阈值上推。达到阈值后，候选任务会继续保留在这一层，直到你手动上推或重新开启。"}
                </p>
              </div>
              <Button
                type="button"
                variant={cfgThresholdRollUpEnabled ? "outline" : "default"}
                onClick={() => setCfgThresholdRollUpEnabled((prev) => !prev)}
                disabled={saving}
              >
                {cfgThresholdRollUpEnabled ? "已开启，点击关闭" : "已关闭，点击开启"}
              </Button>
            </div>
          </div>

          <div className="space-y-3 rounded-[1.2rem] border border-border/70 bg-muted/15 p-4">
            <Label>复习链模板</Label>

            <div className="overflow-hidden rounded-[1.1rem] border border-border/70 bg-background/90">
              {cfgTemplateItems.length === 0 ? (
                <div className="px-4 py-6 text-sm text-muted-foreground">
                  还没有模板步骤，请在下方选择步骤类型后点击加号。
                </div>
              ) : null}

              {cfgTemplateItems.map((item, index) => (
                <div
                  key={item.id}
                  className="border-t border-border/70 p-4 first:border-t-0"
                >
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div className="flex items-start gap-3">
                      <span className="inline-flex items-center rounded-full border border-[#d8e3ee] bg-[#f6f9fc] px-2.5 py-1 text-xs font-semibold text-[#5f7790]">
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
                        <div className="rounded-full border border-border/60 bg-muted/20 px-3 py-1.5 text-xs text-muted-foreground">这个步骤没有额外参数</div>
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

          </div>

          <div className="flex justify-end">
            <Button onClick={() => void onSaveLayerConfig()} disabled={saving || !canSave}>
              {saving ? "保存中..." : "保存配置"}
            </Button>
          </div>

          {layersError ? <p className="text-sm text-destructive">{formatApiError(layersError)}</p> : null}
          {projectConfigError ? <p className="text-sm text-destructive">{formatApiError(projectConfigError)}</p> : null}
          {layerIndexErr ? <p className="text-sm text-destructive">{layerIndexErr}</p> : null}
          {cfgErr ? <p className="text-sm text-destructive">{cfgErr}</p> : null}
          {mutationError ? <p className="text-sm text-destructive">{formatApiError(mutationError)}</p> : null}
        </div>
      </CardContent>
    </Card>
  )
}
