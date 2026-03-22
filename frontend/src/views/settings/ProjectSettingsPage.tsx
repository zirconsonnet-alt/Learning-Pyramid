import { useEffect, useMemo, useState } from "react"
import { useQueries } from "@tanstack/react-query"
import { useNavigate, useParams } from "react-router-dom"

import { listRecallPointsByInstance, type Instance } from "@/ui/api/instances"
import { ApiError } from "@/ui/api/http"
import type { ReviewChainTemplateItem } from "@/ui/api/projectConfig"
import { ContentNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { formatMaterialReference, formatRecallPointReference } from "@/ui/displayIdentifiers"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { scanProjectDirectoryMedia, useProjectDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import { useEditProject, useProject } from "@/ui/queries/projects"
import { useSystemCapabilities } from "@/ui/queries/system"
import {
  useBulkRemapRecallPointsInstance,
  useImportLearningObjectsFromBrowser,
  useInstances,
  useLayers,
  useProjectConfig,
  useProjectStorageConfig,
  useSetExternalServices,
  useSetLayerConfig,
} from "@/ui/queries/workbench"
import { showErrorFeedback, showInfoFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { useThemeStore } from "@/ui/store/themeStore"
import { THEME_PRESETS } from "@/ui/theme/themePresets"
import { cn } from "@/ui/utils"

const BUILTIN_WHISPER_BASE_URL = "builtin://whisper"
let nextTemplateItemId = 1

type TemplateEditorItem = {
  id: number
  kind: "CONVERGENCE" | "REVIEW_TASK"
  count: string
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

function describeFsSyncPolicy(policy: "DISABLED" | "STARTUP_SYNC" | "MANUAL_SYNC") {
  if (policy === "DISABLED") return "已关闭"
  if (policy === "STARTUP_SYNC") return "启动时同步"
  return "手动同步"
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

function summarizeTemplateItems(items: ReviewChainTemplateItem[]) {
  return items
    .map((item) => {
      if (item.kind === "CONVERGENCE") return "收敛"
      return item.count && item.count > 1 ? `复习任务 × ${item.count}` : "复习任务"
    })
    .join(" · ")
}

function isDirectoryPickerAbort(err: unknown) {
  return err instanceof DOMException && err.name === "AbortError"
}

export function ProjectSettingsPage() {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const pid = projectId ?? ""
  const projectQ = useProject(pid, { enabled: !!pid })
  const editProjectM = useEditProject()
  const capabilitiesQ = useSystemCapabilities()
  const selectedTheme = useThemeStore((state) => state.theme)
  const setTheme = useThemeStore((state) => state.setTheme)
  const directoryBinding = useProjectDirectoryBinding(pid)
  const directoryPermission = directoryBinding.permission
  const browserLocalMediaEnabled = capabilitiesQ.data?.browserLocalMediaEnabled ?? false

  const layersQ = useLayers(pid)
  const projectConfigQ = useProjectConfig(pid)
  const storageConfigQ = useProjectStorageConfig(pid)
  const instancesQ = useInstances(pid)
  const importLearningObjectsM = useImportLearningObjectsFromBrowser(pid)
  const setLayerConfigM = useSetLayerConfig(pid)
  const setExternalServicesM = useSetExternalServices(pid)
  const bulkRemapM = useBulkRemapRecallPointsInstance(pid)

  const layerIndexes = useMemo(() => (layersQ.data ?? []).map((l) => l.layerIndex).sort((a, b) => a - b), [layersQ.data])
  const defaultLayerConfig = useMemo(
    () => ({ reviewChainTemplate: [{ kind: "CONVERGENCE" as const }], aggregationKNode: 10, aggregationKPoint: 200 }),
    [],
  )

  const [configLayerIndex, setConfigLayerIndex] = useState(0)
  const effectiveConfigLayerIndex = layerIndexes.includes(configLayerIndex) ? configLayerIndex : (layerIndexes[0] ?? 0)

  const effectiveLayerConfig = useMemo(() => {
    const k = String(effectiveConfigLayerIndex)
    return projectConfigQ.data?.layerConfigs[k] ?? defaultLayerConfig
  }, [defaultLayerConfig, effectiveConfigLayerIndex, projectConfigQ.data?.layerConfigs])
  const templateConfigSignature = useMemo(
    () => JSON.stringify(effectiveLayerConfig.reviewChainTemplate),
    [effectiveLayerConfig.reviewChainTemplate],
  )
  const layerConfigVersion = `${effectiveConfigLayerIndex}:${effectiveLayerConfig.aggregationKNode}:${effectiveLayerConfig.aggregationKPoint}:${templateConfigSignature}`
  const effectiveAsrModel = projectConfigQ.data?.externalServices?.asr?.model ?? ""

  const [remapTargets, setRemapTargets] = useState<Record<string, string>>({})
  const [directoryAction, setDirectoryAction] = useState<"authorize" | "request" | "clear" | "import" | null>(null)

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

  const canChooseDirectory = !!pid && !directoryBinding.loading && directoryBinding.supported
  const canRequestDirectoryPermission =
    !!pid && !directoryBinding.loading && (directoryPermission === "prompt" || directoryPermission === "denied")
  const canClearDirectory = !!pid && !directoryBinding.loading && directoryPermission !== "missing"
  const directoryBusy = directoryAction !== null

  async function onRemapMissingInstance(fromInstanceId: string) {
    const sourceInstance = missingInstances.find((item) => item.instanceId === fromInstanceId)
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
      <ProjectTitleCard
        isLoading={projectQ.isLoading}
        isPending={editProjectM.isPending}
        projectTitle={projectQ.project?.title ?? ""}
        queryError={projectQ.error}
        saveError={editProjectM.error}
        onSave={async (title) => {
          try {
            await editProjectM.mutateAsync({ projectId: pid, title })
            showSuccessFeedback("项目名称已更新", `当前项目现在显示为“${title}”。`)
          } catch (err) {
            showErrorFeedback("更新项目名称失败", formatApiError(err))
          }
        }}
      />

      <Card className="theme-card">
        <CardHeader>
          <CardTitle>界面主题</CardTitle>
          <CardDescription>主题只保存在当前浏览器，切换后工作台、树视图和登录页会一起生效。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-3">
            {THEME_PRESETS.map((theme) => {
              const isActive = selectedTheme === theme.id
              return (
                <button
                  key={theme.id}
                  type="button"
                  className={cn(
                    "theme-status-surface flex flex-col items-start gap-3 rounded-[1.2rem] border p-4 text-left transition-all duration-200",
                    isActive
                      ? "border-primary/45 shadow-[0_20px_46px_-30px_rgba(37,99,235,0.42)]"
                      : "hover:-translate-y-px hover:border-primary/20",
                  )}
                  onClick={() => setTheme(theme.id)}
                >
                  <div className="flex w-full items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-foreground">{theme.label}</div>
                    {isActive ? <span className="theme-meta-strong">当前</span> : null}
                  </div>
                  <div className="flex items-center gap-2">
                    {theme.preview.map((color) => (
                      <span
                        key={`${theme.id}-${color}`}
                        className="h-7 w-7 rounded-full border border-black/5 shadow-inner"
                        style={{ backgroundColor: color }}
                      />
                    ))}
                  </div>
                  <p className="text-sm leading-6 text-muted-foreground">{theme.description}</p>
                </button>
              )
            })}
          </div>
          <p className="text-xs text-muted-foreground">这是本地界面偏好，不会改动项目数据，也不会影响其他浏览器。</p>
        </CardContent>
      </Card>

      {browserLocalMediaEnabled ? (
        <Card className="theme-card">
          <CardHeader>
            <CardTitle>素材接入</CardTitle>
            <CardDescription>先确认当前目录状态，再在需要时同步目录内容。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
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
                  <div className="text-xs text-muted-foreground">
                    {directoryBinding.handleName
                      ? "目录记录已和当前项目关联。"
                      : "绑定后才可以把媒体文件导入成学习对象树。"}
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
                </div>
              </div>

              {(directoryPermission === "granted" || directoryPermission === "prompt" || directoryPermission === "denied") && canClearDirectory ? (
                <div className="mt-4 border-t border-border/60 pt-3">
                  <Button
                    type="button"
                    variant="ghost"
                    className="px-0 text-muted-foreground"
                    onClick={() => void onClearDirectoryBinding()}
                    disabled={!canClearDirectory || directoryBusy}
                  >
                    {directoryAction === "clear" ? "清除中..." : "清除本地绑定"}
                  </Button>
                </div>
              ) : null}
            </div>

            <details className="rounded-[1.1rem] border border-border/70 bg-muted/20 px-4 py-3">
              <summary className="cursor-pointer list-none text-sm font-medium text-foreground">了解目录导入机制</summary>
              <div className="mt-3 space-y-2 text-xs leading-6 text-muted-foreground">
                <p>浏览器目录授权和项目绑定是分开的。目录本身保存在当前浏览器里，项目只记录你绑定了哪一个目录句柄。</p>
                <p>重新同步时只会更新媒体文件和学习对象树，不会推进复习调度，也不会自动改动复述链。</p>
              </div>
            </details>

            {directoryBinding.error ? <p className="text-sm text-destructive">{directoryBinding.error}</p> : null}
            {!directoryBinding.supported ? (
              <p className="text-sm text-muted-foreground">当前浏览器不支持目录授权。首版建议使用桌面 Chrome 或 Edge。</p>
            ) : null}
            {importLearningObjectsM.error ? <p className="text-sm text-destructive">{formatApiError(importLearningObjectsM.error)}</p> : null}
          </CardContent>
        </Card>
      ) : (
        <Card className="theme-card">
          <CardHeader>
            <CardTitle>素材接入</CardTitle>
            <CardDescription>当前部署没有开启浏览器本地目录模式。</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            这个项目暂时不会显示目录选择器，你仍然可以在下面查看服务端路径和同步策略。
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_360px]">
        <LayerConfigEditor
          key={layerConfigVersion}
          canSave={!!pid}
          initialConfig={effectiveLayerConfig}
          layerIndexes={layerIndexes}
          layersError={layersQ.error}
          mutationError={setLayerConfigM.error}
          projectConfigError={projectConfigQ.error}
          selectedLayerIndex={effectiveConfigLayerIndex}
          saving={setLayerConfigM.isPending}
          onSave={async ({ kNode, kPoint, reviewChainTemplate }) => {
            try {
              await setLayerConfigM.mutateAsync({
                layerIndex: effectiveConfigLayerIndex,
                kNode,
                kPoint,
                reviewChainTemplate,
              })
              showSuccessFeedback(
                "层配置已保存",
                `第 ${effectiveConfigLayerIndex} 层现在使用 ${reviewChainTemplate.length} 个模板步骤，节点阈值 ${kNode}，复述点阈值 ${kPoint}。`,
              )
            } catch (err) {
              showErrorFeedback("保存层配置失败", formatApiError(err))
            }
          }}
          onSelectedLayerIndexChange={setConfigLayerIndex}
        />

        <div className="space-y-4">
          <Card className="theme-card">
            <CardHeader>
              <CardTitle>服务端路径</CardTitle>
              <CardDescription>只读查看当前项目的目录绑定。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              {storageConfigQ.isLoading ? <p className="text-sm text-muted-foreground">加载中...</p> : null}
              {storageConfigQ.error ? <p className="text-sm text-destructive">{formatApiError(storageConfigQ.error)}</p> : null}
              {storageConfigQ.data ? (
                <div className="space-y-3">
                  <div className="rounded-[1.1rem] border border-border/70 bg-background/85 px-4 py-3">
                    <div className="text-xs text-muted-foreground">项目根路径</div>
                    <div className="mt-2 break-all font-mono text-xs text-foreground">{storageConfigQ.data.projectRoot}</div>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-[1.1rem] border border-border/70 bg-muted/20 px-4 py-3">
                      <div className="text-xs text-muted-foreground">同步策略</div>
                      <div className="mt-1 font-medium text-foreground">{describeFsSyncPolicy(storageConfigQ.data.fsSyncPolicy)}</div>
                    </div>
                    <div className="rounded-[1.1rem] border border-border/70 bg-muted/20 px-4 py-3">
                      <div className="text-xs text-muted-foreground">学习对象目录</div>
                      <div className="mt-1 break-all font-mono text-xs text-foreground">{storageConfigQ.data.learningObjectRoot}</div>
                    </div>
                  </div>
                </div>
              ) : null}
              {!storageConfigQ.isLoading && !storageConfigQ.error && !storageConfigQ.data ? (
                <p className="text-sm text-muted-foreground">暂时还没有项目路径信息。</p>
              ) : null}
            </CardContent>
          </Card>

          {capabilitiesQ.data?.asrEnabled === false ? (
            <Card className="theme-card">
              <CardHeader>
                <CardTitle>语音转写</CardTitle>
                <CardDescription>当前部署已禁用 ASR。</CardDescription>
              </CardHeader>
            </Card>
          ) : (
            <AsrSettingsCard
              key={effectiveAsrModel}
              disabled={!pid}
              initialModel={effectiveAsrModel}
              isLoading={projectConfigQ.isLoading}
              isPending={setExternalServicesM.isPending}
              queryError={projectConfigQ.error}
              saveError={setExternalServicesM.error}
              onSave={async (model) => {
                const trimmedAsrModel = model.trim()
                try {
                  await setExternalServicesM.mutateAsync({
                    asr: {
                      baseUrl: BUILTIN_WHISPER_BASE_URL,
                      model: trimmedAsrModel || undefined,
                    },
                  })
                  showSuccessFeedback(
                    "转写设置已保存",
                    trimmedAsrModel ? `当前模型已切换为 ${trimmedAsrModel}。` : "当前已恢复默认转写模型。",
                  )
                } catch (err) {
                  showErrorFeedback("保存转写设置失败", formatApiError(err))
                }
              }}
            />
          )}
        </div>
      </div>

      <Card className="theme-card">
        <CardHeader>
          <CardTitle>缺失材料修复</CardTitle>
          <CardDescription>旧实例会被标记为缺失，相关复述点仍需要在这里手动迁移。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          {instancesQ.isLoading ? <p className="text-sm text-muted-foreground">加载实例中...</p> : null}
          {instancesQ.error ? <p className="text-sm text-destructive">{formatApiError(instancesQ.error)}</p> : null}
          {!instancesQ.isLoading && !instancesQ.error && missingInstances.length === 0 ? (
            <div className="rounded-xl border bg-muted/30 p-4 text-sm text-muted-foreground">当前没有缺失材料实例。</div>
          ) : null}

          <div className="space-y-3">
            {missingInstances.map((instance, index) => {
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
    </div>
  )
}

function ProjectTitleCard({
  isLoading,
  isPending,
  projectTitle,
  queryError,
  saveError,
  onSave,
}: {
  isLoading: boolean
  isPending: boolean
  projectTitle: string
  queryError: unknown
  saveError: unknown
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
        <CardTitle>项目名称</CardTitle>
        <CardDescription>这里改名后，项目列表、顶部标题和工作区里的项目名称会一起刷新。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="theme-status-surface rounded-[1.2rem] border border-border/70 p-4">
          <div className="text-xs text-muted-foreground">当前名称</div>
          <div className="mt-1 text-base font-semibold text-foreground">{projectTitle || (isLoading ? "加载中..." : "未找到项目")}</div>
        </div>

        <form
          className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]"
          onSubmit={(event) => {
            event.preventDefault()
            if (!canSave) return
            void onSave(trimmedTitle)
          }}
        >
          <div className="space-y-2">
            <Label htmlFor="projectTitle">新名称</Label>
            <Input
              id="projectTitle"
              value={titleDraft}
              onChange={(event) => setTitleDraft(event.target.value)}
              placeholder="请输入项目名称"
              disabled={isLoading || isPending}
            />
          </div>
          <div className="flex items-end">
            <Button type="submit" disabled={!canSave}>
              {isPending ? "保存中..." : "保存项目名称"}
            </Button>
          </div>
        </form>

        {queryError ? <p className="text-sm text-destructive">{formatApiError(queryError)}</p> : null}
        {saveError ? <p className="text-sm text-destructive">{formatApiError(saveError)}</p> : null}
      </CardContent>
    </Card>
  )
}

function AsrSettingsCard({
  disabled,
  initialModel,
  isLoading,
  isPending,
  onSave,
  queryError,
  saveError,
}: {
  disabled: boolean
  initialModel: string
  isLoading: boolean
  isPending: boolean
  onSave: (model: string) => Promise<void>
  queryError: unknown
  saveError: unknown
}) {
  const [asrModel, setAsrModel] = useState(initialModel)

  return (
    <Card className="theme-card">
      <CardHeader>
        <CardTitle>语音转写</CardTitle>
        <CardDescription>按项目覆盖本机 Whisper 使用的模型。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="flex items-center justify-between gap-3 rounded-[1.1rem] border border-border/70 bg-muted/20 px-4 py-3">
          <div>
            <div className="text-xs text-muted-foreground">转写引擎</div>
            <div className="mt-1 font-medium text-foreground">内置 Whisper 运行时</div>
          </div>
          <span className="inline-flex items-center rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-700">
            已启用
          </span>
        </div>

        <div className="space-y-2">
          <Label htmlFor="asrModel">模型（可选）</Label>
          <Input
            id="asrModel"
            value={asrModel}
            onChange={(e) => setAsrModel(e.target.value)}
            placeholder="留空使用默认 small，例如：small / medium / large-v3"
            disabled={isPending}
          />
          <p className="text-xs text-muted-foreground">只在需要切换模型时填写，留空会继续使用默认值。</p>
        </div>

        <div className="flex justify-end">
          <Button onClick={() => void onSave(asrModel)} disabled={isPending || disabled}>
            {isPending ? "保存中..." : "保存转写设置"}
          </Button>
        </div>

        {isLoading ? <p className="text-sm text-muted-foreground">加载当前转写设置中...</p> : null}
        {queryError ? <p className="text-sm text-destructive">{formatApiError(queryError)}</p> : null}
        {saveError ? <p className="text-sm text-destructive">{formatApiError(saveError)}</p> : null}
      </CardContent>
    </Card>
  )
}

function LayerConfigEditor({
  canSave,
  initialConfig,
  layerIndexes,
  layersError,
  mutationError,
  onSave,
  onSelectedLayerIndexChange,
  projectConfigError,
  saving,
  selectedLayerIndex,
}: {
  canSave: boolean
  initialConfig: { reviewChainTemplate: ReviewChainTemplateItem[]; aggregationKNode: number; aggregationKPoint: number }
  layerIndexes: number[]
  layersError: unknown
  mutationError: unknown
  onSave: (payload: { kNode: number; kPoint: number; reviewChainTemplate: ReviewChainTemplateItem[] }) => Promise<void>
  onSelectedLayerIndexChange: (layerIndex: number) => void
  projectConfigError: unknown
  saving: boolean
  selectedLayerIndex: number
}) {
  const [cfgKNode, setCfgKNode] = useState(() => String(initialConfig.aggregationKNode))
  const [cfgKPoint, setCfgKPoint] = useState(() => String(initialConfig.aggregationKPoint))
  const [cfgTemplateItems, setCfgTemplateItems] = useState<TemplateEditorItem[]>(() => toTemplateEditorItems(initialConfig.reviewChainTemplate))
  const [cfgErr, setCfgErr] = useState<string | null>(null)
  const templateSummary = summarizeTemplateItems(cfgTemplateItems.map((item) =>
    item.kind === "CONVERGENCE"
      ? { kind: "CONVERGENCE" as const }
      : Number(item.count) > 1
        ? { kind: "REVIEW_TASK" as const, count: Number(item.count) }
        : { kind: "REVIEW_TASK" as const },
  ))

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

    await onSave({ kNode, kPoint, reviewChainTemplate: items })
  }

  return (
    <Card className="theme-card">
      <CardHeader>
        <CardTitle>层配置</CardTitle>
        <CardDescription>先看当前层摘要，再只调整本次要改的参数。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="theme-status-surface space-y-4 rounded-[1.35rem] border border-border/70 p-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-1">
              <div className="theme-meta-strong">第 {selectedLayerIndex} 层</div>
              <div className="text-sm text-muted-foreground">当前层的模板和聚合阈值会影响后续新登记的任务。</div>
            </div>
            <div className="w-full max-w-[220px] space-y-2">
              <Label htmlFor="configLayer">切换层</Label>
              <select
                id="configLayer"
                className="h-11 w-full rounded-xl border bg-background px-4 text-sm"
                value={String(selectedLayerIndex)}
                onChange={(e) => onSelectedLayerIndexChange(Number(e.target.value))}
                disabled={layerIndexes.length === 0 || saving}
              >
                {layerIndexes.map((idx) => (
                  <option key={idx} value={idx}>
                    第 {idx} 层
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_160px_160px]">
            <div className="rounded-[1.1rem] border border-border/70 bg-background/85 px-4 py-3">
              <div className="text-xs text-muted-foreground">当前模板</div>
              <div className="mt-1 text-sm font-medium text-foreground">{templateSummary}</div>
            </div>
            <div className="rounded-[1.1rem] border border-border/70 bg-background/85 px-4 py-3">
              <div className="text-xs text-muted-foreground">节点阈值</div>
              <div className="mt-1 text-lg font-semibold text-foreground">{initialConfig.aggregationKNode}</div>
            </div>
            <div className="rounded-[1.1rem] border border-border/70 bg-background/85 px-4 py-3">
              <div className="text-xs text-muted-foreground">复述点阈值</div>
              <div className="mt-1 text-lg font-semibold text-foreground">{initialConfig.aggregationKPoint}</div>
            </div>
          </div>
        </div>

        <div className="grid gap-4">
          <div className="grid gap-4 rounded-[1.35rem] border border-border/70 bg-muted/20 p-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="kNode">节点阈值</Label>
              <Input id="kNode" value={cfgKNode} onChange={(e) => setCfgKNode(e.target.value)} disabled={saving} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="kPoint">复述点阈值</Label>
              <Input id="kPoint" value={cfgKPoint} onChange={(e) => setCfgKPoint(e.target.value)} disabled={saving} />
            </div>
          </div>

          <div className="space-y-3 rounded-[1.35rem] border border-border/70 bg-muted/20 p-4">
            <div className="space-y-1">
              <Label>复习链模板</Label>
              <p className="text-xs text-muted-foreground">这里只编辑初始化顺序，机制说明收进下方折叠区。</p>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setCfgTemplateItems((prev) => [...prev, createTemplateEditorItem("CONVERGENCE")])}
                disabled={saving}
              >
                追加收敛
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setCfgTemplateItems((prev) => [...prev, createTemplateEditorItem("REVIEW_TASK")])}
                disabled={saving}
              >
                追加复习任务
              </Button>
            </div>

            <div className="overflow-hidden rounded-[1.1rem] border border-border/70 bg-background/90">
              {cfgTemplateItems.length === 0 ? (
                <div className="px-4 py-6 text-sm text-muted-foreground">
                  还没有模板步骤，请先追加收敛或复习任务。
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
                        <div className="text-xs text-muted-foreground">
                          这个步骤没有额外参数。
                        </div>
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

            <details className="rounded-[1.1rem] border border-border/70 bg-background/70 px-4 py-3">
              <summary className="cursor-pointer list-none text-sm font-medium text-foreground">了解模板机制</summary>
              <div className="mt-3 space-y-2 text-xs leading-6 text-muted-foreground">
                <p>步骤顺序就是系统创建新复习链时的初始化顺序，越靠前越先执行。</p>
                <p>模板里至少需要一个“收敛”步骤，否则系统无法继续推进后续轮次。</p>
              </div>
            </details>
          </div>

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
      </CardContent>
    </Card>
  )
}
