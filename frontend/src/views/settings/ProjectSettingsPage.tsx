import { useMemo, useState } from "react"
import { useQueries } from "@tanstack/react-query"
import { Link, useNavigate, useParams } from "react-router-dom"

import { listRecallPointsByInstance, type Instance } from "@/ui/api/instances"
import { ApiError } from "@/ui/api/http"
import type { ReviewChainTemplateItem } from "@/ui/api/projectConfig"
import { ContentNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { formatMaterialReference, formatRecallPointReference } from "@/ui/displayIdentifiers"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { scanProjectDirectoryManifest, useProjectDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import { useProject } from "@/ui/queries/projects"
import { useSystemCapabilities, useSystemRuntime } from "@/ui/queries/system"
import {
  useBulkRemapRecallPointsInstance,
  useInstances,
  useLayers,
  useProjectConfig,
  useProjectDesktopAgentStatus,
  useProjectMaterialSourceBinding,
  useProjectStorageConfig,
  useSetExternalServices,
  useSetLayerConfig,
  useSyncClientMediaManifest,
} from "@/ui/queries/workbench"
import { showErrorFeedback, showInfoFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"

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

function describeDesktopAgentStatus(status: string | null | undefined) {
  return status === "ONLINE" ? "在线" : "离线"
}

function describeRuntimeReadiness(ready: boolean | undefined, isLoading: boolean) {
  if (isLoading) return "更新中"
  if (ready === true) return "状态正常"
  if (ready === false) return "需要关注"
  return "暂无摘要"
}

function isDirectoryPickerAbort(err: unknown) {
  return err instanceof DOMException && err.name === "AbortError"
}

export function ProjectSettingsPage() {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const pid = projectId ?? ""
  const { projectTitle } = useProject(pid)
  const capabilitiesQ = useSystemCapabilities()
  const directoryBinding = useProjectDirectoryBinding(pid)
  const directoryPermission = directoryBinding.permission
  const isHostedMode = capabilitiesQ.data?.appMode === "hosted"
  const runtimeQ = useSystemRuntime(isHostedMode)

  const layersQ = useLayers(pid)
  const projectConfigQ = useProjectConfig(pid)
  const storageConfigQ = useProjectStorageConfig(pid)
  const materialSourceBindingQ = useProjectMaterialSourceBinding(pid)
  const desktopAgentStatusQ = useProjectDesktopAgentStatus(pid)
  const instancesQ = useInstances(pid)
  const setLayerConfigM = useSetLayerConfig(pid)
  const setExternalServicesM = useSetExternalServices(pid)
  const bulkRemapM = useBulkRemapRecallPointsInstance(pid)
  const syncManifestM = useSyncClientMediaManifest(pid)

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
  const [syncStatusText, setSyncStatusText] = useState<string | null>(null)
  const [directoryAction, setDirectoryAction] = useState<"authorize" | "request" | "clear" | null>(null)

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
  const canSyncLocalMedia = !!pid && !syncManifestM.isPending && directoryPermission === "granted"
  const directoryBusy = directoryAction !== null

  const boundDesktopAgent = desktopAgentStatusQ.data?.agent ?? null
  const relayRuntime = runtimeQ.data?.desktopAgentRelay

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

  async function onSyncLocalMediaManifest() {
    setSyncStatusText(null)
    try {
      const manifest = await scanProjectDirectoryManifest(pid)
      const report = await syncManifestM.mutateAsync(manifest)
      const summary = `同步完成：新增实例 ${report.created_instances_count}，标记缺失 ${report.marked_missing_count}，重建对象节点 ${report.replaced_learning_object_nodes_count}。`
      setSyncStatusText(summary)
      showSuccessFeedback("素材目录已同步", summary)
    } catch (err) {
      showErrorFeedback("素材目录同步失败", formatApiError(err))
    }
  }

  async function onAuthorizeDirectory() {
    if (!canChooseDirectory || directoryBusy) return
    setDirectoryAction("authorize")
    try {
      const permission = await directoryBinding.authorizeDirectory()
      setSyncStatusText(null)
      if (permission === "granted") {
        showSuccessFeedback("本地目录已绑定", "浏览器已经记录并授权当前项目的本地素材目录。")
      } else {
        showInfoFeedback("目录已记录", "目录已经保存到当前项目，但浏览器还需要你继续授予读取权限。")
      }
    } catch (err) {
      if (!isDirectoryPickerAbort(err)) {
        showErrorFeedback("绑定本地目录失败", formatApiError(err))
      }
    } finally {
      setDirectoryAction(null)
    }
  }

  async function onRequestDirectoryPermission() {
    if (!canRequestDirectoryPermission || directoryBusy) return
    setDirectoryAction("request")
    try {
      const permission = await directoryBinding.requestPermission()
      if (permission === "granted") {
        showSuccessFeedback("目录权限已恢复", "现在可以扫描并同步这个项目的本地素材目录。")
      } else if (permission === "denied") {
        showInfoFeedback("目录权限未授予", "浏览器仍未允许读取该目录，你可以重试或直接更换目录。")
      } else {
        showInfoFeedback("等待目录授权", "浏览器还没有授予读取权限，请继续完成授权。")
      }
    } catch (err) {
      showErrorFeedback("请求目录权限失败", formatApiError(err))
    } finally {
      setDirectoryAction(null)
    }
  }

  async function onClearDirectoryBinding() {
    if (!canClearDirectory || directoryBusy) return
    setDirectoryAction("clear")
    try {
      await directoryBinding.clearDirectory()
      setSyncStatusText(null)
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
    <div className="space-y-4">
      <div className="space-y-1">
        <h1 className="text-lg font-semibold">项目设置</h1>
        <p className="text-sm text-muted-foreground">
          项目：<span className="font-medium text-foreground">{projectTitle}</span>
        </p>
      </div>

      <div className="grid gap-4 xl:grid-cols-[380px_1fr]">
        <div className="space-y-4">
          {isHostedMode ? (
            <Card className="theme-card">
              <CardHeader>
                <CardTitle>桌面连接器</CardTitle>
                <CardDescription>桌面连接器下载和接入已经移到独立页面；这里保留当前项目的状态和常用入口。</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <div className="rounded-xl border bg-muted/30 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-muted-foreground">当前材料源</span>
                    <span>{materialSourceBindingQ.data?.sourceKind === "DESKTOP_AGENT_MANIFEST" ? "桌面连接器" : "服务器文件系统"}</span>
                  </div>
                  <div className="mt-3 text-xs text-muted-foreground">
                    {boundDesktopAgent
                      ? `已绑定设备：${boundDesktopAgent.deviceName}（${describeDesktopAgentStatus(boundDesktopAgent.status)}）`
                      : "当前项目还没有绑定桌面连接器。"}
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    逻辑根标签：{materialSourceBindingQ.data?.sourceRootLabel ?? "未设置"}
                  </div>
                </div>

                {desktopAgentStatusQ.data ? (
                  <div className="rounded-md border bg-muted/30 p-3 text-xs text-muted-foreground">
                    {desktopAgentStatusQ.data.agent
                      ? `设备当前${describeDesktopAgentStatus(desktopAgentStatusQ.data.agent.status)}，最近心跳：${formatLastSeenAt(
                          desktopAgentStatusQ.data.agent.lastSeenAt,
                        )}`
                      : "尚未绑定桌面设备。"}
                  </div>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  <Button asChild>
                    <Link to={`/system/desktop-agent?projectId=${encodeURIComponent(pid)}`}>打开 Desktop Agent 页面</Link>
                  </Button>
                  <Button asChild variant="outline">
                    <Link to="/system/relay-monitor">打开 Relay Monitor</Link>
                  </Button>
                </div>
                <div className="space-y-2 rounded-md border bg-muted/30 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-xs font-medium text-foreground">中继状态摘要</div>
                    <div className="text-xs text-muted-foreground">{describeRuntimeReadiness(runtimeQ.data?.ready, runtimeQ.isLoading)}</div>
                  </div>
                  {relayRuntime ? (
                    <>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div className="rounded-md border bg-background/80 p-2">
                          <div className="text-muted-foreground">在线设备</div>
                          <div className="mt-1 text-sm font-semibold text-foreground">{relayRuntime.connectedAgentCount}</div>
                        </div>
                        <div className="rounded-md border bg-background/80 p-2">
                          <div className="text-muted-foreground">活跃流</div>
                          <div className="mt-1 text-sm font-semibold text-foreground">{relayRuntime.activeStreamCount}</div>
                        </div>
                        <div className="rounded-md border bg-background/80 p-2">
                          <div className="text-muted-foreground">待处理探测</div>
                          <div className="mt-1 text-sm font-semibold text-foreground">{relayRuntime.pendingProbeCount}</div>
                        </div>
                        <div className="rounded-md border bg-background/80 p-2">
                          <div className="text-muted-foreground">活跃 HLS 转码</div>
                          <div className="mt-1 text-sm font-semibold text-foreground">{relayRuntime.activeHlsJobCount}</div>
                        </div>
                      </div>
                      <div className="space-y-1 text-xs text-muted-foreground">
                        <div>
                          当前摘要只保留在线状态、活跃传输和待处理探测。更详细的告警、转码记录和设备清单，请前往 Relay Monitor 查看。
                        </div>
                        {runtimeQ.data?.ready === false ? <div>当前中继链路存在异常，建议打开 Relay Monitor 查看详情。</div> : null}
                      </div>
                    </>
                  ) : (
                    <div className="text-xs text-muted-foreground">暂时还没有中继状态摘要。</div>
                  )}
                </div>
                {materialSourceBindingQ.error ? (
                  <p className="text-sm text-destructive">{formatApiError(materialSourceBindingQ.error)}</p>
                ) : null}
                {desktopAgentStatusQ.error ? (
                  <p className="text-sm text-destructive">{formatApiError(desktopAgentStatusQ.error)}</p>
                ) : null}
                {runtimeQ.error ? <p className="text-sm text-destructive">{formatApiError(runtimeQ.error)}</p> : null}
              </CardContent>
            </Card>
          ) : (
            <Card className="theme-card">
              <CardHeader>
                <CardTitle>本地素材目录</CardTitle>
                <CardDescription>网页模式下，播放器会通过浏览器授权直接读取你当前设备上的视频文件。</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="rounded-xl border bg-muted/30 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-muted-foreground">当前状态</span>
                    <span>{describeDirectoryPermission(directoryPermission)}</span>
                  </div>
                  <div className="mt-3 text-xs text-muted-foreground">
                    {directoryBinding.handleName
                      ? `已记录目录：${directoryBinding.handleName}`
                      : "还没有为当前项目绑定本地素材目录。"}
                  </div>
                </div>

                {directoryPermission === "granted" ? (
                  <div className="space-y-2">
                    <div className="flex flex-wrap gap-2">
                      <Button type="button" onClick={() => void onSyncLocalMediaManifest()} disabled={!canSyncLocalMedia}>
                        {syncManifestM.isPending ? "同步中..." : "扫描并同步目录"}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => void onAuthorizeDirectory()}
                        disabled={!canChooseDirectory || directoryBusy}
                      >
                        {directoryAction === "authorize" ? "打开目录选择器..." : "更换目录"}
                      </Button>
                    </div>
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

                {(directoryPermission === "missing" || directoryPermission === "unsupported") ? (
                  <div className="flex flex-wrap gap-2">
                    <Button type="button" onClick={() => void onAuthorizeDirectory()} disabled={!canChooseDirectory || directoryBusy}>
                      {directoryAction === "authorize" ? "打开目录选择器..." : "选择并授权目录"}
                    </Button>
                  </div>
                ) : null}

                {(directoryPermission === "prompt" || directoryPermission === "denied") ? (
                  <div className="space-y-2">
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        onClick={() => void onRequestDirectoryPermission()}
                        disabled={!canRequestDirectoryPermission || directoryBusy}
                      >
                        {directoryAction === "request" ? "请求中..." : "重新请求权限"}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        onClick={() => void onAuthorizeDirectory()}
                        disabled={!canChooseDirectory || directoryBusy}
                      >
                        {directoryAction === "authorize" ? "打开目录选择器..." : "更换目录"}
                      </Button>
                    </div>
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

                {!capabilitiesQ.data?.browserLocalMediaEnabled ? (
                  <div className="rounded-md border bg-muted/30 p-3 text-xs text-muted-foreground">
                    当前部署未启用浏览器本地媒体访问，播放器仍会回退到服务端媒体流。
                  </div>
                ) : null}
                {directoryBinding.error ? <p className="text-sm text-destructive">{directoryBinding.error}</p> : null}
                {syncManifestM.error ? <p className="text-sm text-destructive">{formatApiError(syncManifestM.error)}</p> : null}
                {syncStatusText ? <p className="text-sm text-muted-foreground">{syncStatusText}</p> : null}
                {!directoryBinding.supported ? (
                  <div className="rounded-md border bg-muted/30 p-3 text-xs text-muted-foreground">
                    当前浏览器不支持目录授权。首版建议使用桌面 Chrome 或 Edge。
                  </div>
                ) : null}
              </CardContent>
            </Card>
          )}

          <Card className="theme-card">
            <CardHeader>
              <CardTitle>项目路径</CardTitle>
              <CardDescription>当前项目的目录绑定与同步策略。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {storageConfigQ.isLoading ? <p className="text-sm text-muted-foreground">加载中...</p> : null}
              {storageConfigQ.error ? <p className="text-sm text-destructive">{formatApiError(storageConfigQ.error)}</p> : null}
              {storageConfigQ.data ? (
                <>
                  <div className="space-y-1">
                    <div className="text-xs text-muted-foreground">项目根路径</div>
                    <div className="break-all rounded-md border bg-muted/30 p-2 font-mono text-xs text-foreground">
                      {storageConfigQ.data.projectRoot}
                    </div>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">目录同步</span>
                    <span>{describeFsSyncPolicy(storageConfigQ.data.fsSyncPolicy)}</span>
                  </div>
                </>
              ) : null}
              {!storageConfigQ.isLoading && !storageConfigQ.error && !storageConfigQ.data ? (
                <div className="rounded-md border bg-muted/30 p-2 text-xs text-muted-foreground">
                  暂时还没有项目路径信息。
                </div>
              ) : null}
            </CardContent>
          </Card>

          {capabilitiesQ.data?.asrEnabled === false ? (
            <Card className="theme-card">
              <CardHeader>
                <CardTitle>语音转写</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="rounded-xl border bg-muted/30 p-4 text-muted-foreground">
                  当前部署已禁用 ASR。
                </div>
              </CardContent>
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
      </div>

      <Card className="theme-card">
        <CardHeader>
          <CardTitle>缺失材料修复</CardTitle>
          <CardDescription>旧实例会被标记为缺失，相关复述点仍需要在这里手动迁移。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
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
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="rounded-xl border bg-muted/30 p-4">
          <div className="space-y-1">
            <div className="font-semibold text-foreground">本机转写引擎</div>
          </div>
          <div className="mt-3 space-y-3">
            <div>
              <Label htmlFor="asrModel">模型（可选）</Label>
              <Input
                id="asrModel"
                value={asrModel}
                onChange={(e) => setAsrModel(e.target.value)}
                placeholder="留空使用默认 small，例如：small / medium / large-v3"
                disabled={isPending}
              />
            </div>
          </div>
        </div>

        <Button onClick={() => void onSave(asrModel)} disabled={isPending || disabled}>
          {isPending ? "保存中..." : "保存转写设置"}
        </Button>

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
        <CardDescription>配置每层的复习链模板与聚合阈值。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="grid gap-3">
          <div>
            <Label htmlFor="configLayer">目标层</Label>
            <select
              id="configLayer"
              className="mt-2 h-9 w-full rounded-md border bg-background px-3 text-sm"
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

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="kNode">节点阈值</Label>
              <Input id="kNode" value={cfgKNode} onChange={(e) => setCfgKNode(e.target.value)} disabled={saving} />
            </div>
            <div>
              <Label htmlFor="kPoint">复述点阈值</Label>
              <Input id="kPoint" value={cfgKPoint} onChange={(e) => setCfgKPoint(e.target.value)} disabled={saving} />
            </div>
          </div>

          <div className="space-y-3">
            <Label>复习链模板</Label>

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

            <div className="space-y-2">
              {cfgTemplateItems.length === 0 ? (
                <div className="rounded-xl border border-dashed border-border/70 bg-muted/20 px-4 py-6 text-sm text-muted-foreground">
                  还没有模板步骤，请先追加收敛或复习任务。
                </div>
              ) : null}

              {cfgTemplateItems.map((item, index) => (
                <div
                  key={item.id}
                  className="flex flex-col gap-3 rounded-xl border border-border/70 bg-muted/20 p-4 md:flex-row md:items-end md:justify-between"
                >
                  <div className="flex-1 space-y-2">
                    <div className="text-sm font-medium text-foreground">第 {index + 1} 步</div>
                    <div className="rounded-lg border bg-background px-3 py-2 text-sm text-foreground">
                      {item.kind === "CONVERGENCE" ? "收敛" : "复习任务"}
                    </div>
                    {item.kind === "REVIEW_TASK" ? (
                      <div className="max-w-[220px] space-y-1">
                        <Label htmlFor={`template-count-${item.id}`}>连续复习次数</Label>
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
                      <div className="text-xs text-muted-foreground">收敛步骤不需要额外参数。</div>
                    )}
                  </div>

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
              ))}
            </div>
          </div>

          <Button onClick={() => void onSaveLayerConfig()} disabled={saving || !canSave}>
            {saving ? "保存中..." : "保存配置"}
          </Button>

          {layersError ? <p className="text-sm text-destructive">{formatApiError(layersError)}</p> : null}
          {projectConfigError ? <p className="text-sm text-destructive">{formatApiError(projectConfigError)}</p> : null}
          {cfgErr ? <p className="text-sm text-destructive">{cfgErr}</p> : null}
          {mutationError ? <p className="text-sm text-destructive">{formatApiError(mutationError)}</p> : null}
        </div>
      </CardContent>
    </Card>
  )
}
