import { useEffect, useMemo, useState } from "react"
import {
  Activity,
  ChevronDown,
  ChevronUp,
  Copy,
  Download,
  ExternalLink,
  FolderTree,
  Link2,
  RadioTower,
  ShieldAlert,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react"
import { Link, useSearchParams } from "react-router-dom"

import type { DesktopAgentSetupSession } from "@/ui/api/system"
import { ApiError } from "@/ui/api/http"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Label } from "@/ui/components/ui/label"
import { formatDesktopAgentReference } from "@/ui/displayIdentifiers"
import { useCurrentUser } from "@/ui/queries/auth"
import { useDesktopAgents } from "@/ui/queries/workbench"
import {
  useCreateDesktopAgentSetupSession,
  useDesktopAgentRelease,
  useDesktopAgentSetupCatalog,
  useSystemCapabilities,
} from "@/ui/queries/system"
import { showErrorFeedback, showInfoFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"
import {
  BoardEntryCard,
  ControlDeck,
  EmptyState,
  EntryNote,
  MetaChip,
  NarrativePanel,
  OpsSignalTile,
  SelectableTileButton,
  StatusSidebar,
  StatusField,
  SystemBoard,
  TonePill,
  WatchlistItem,
  WatchlistPanel,
} from "@/views/system/components/dashboardPrimitives"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "未记录"
  const dt = new Date(value)
  return Number.isNaN(dt.getTime()) ? value : dt.toLocaleString()
}

function formatBytes(value: number | null | undefined) {
  const size = Math.max(0, Number(value ?? 0))
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`
  return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

function formatTimeRemaining(value: string | null | undefined) {
  if (!value) return "未生成"
  const expiresAt = new Date(value)
  if (Number.isNaN(expiresAt.getTime())) return value
  const diffMs = expiresAt.getTime() - Date.now()
  if (diffMs <= 0) return "已过期"
  const totalMinutes = Math.ceil(diffMs / 60_000)
  if (totalMinutes < 60) return `剩余 ${totalMinutes} 分钟`
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return minutes > 0 ? `剩余 ${hours} 小时 ${minutes} 分钟` : `剩余 ${hours} 小时`
}

function describeAsset(kind: "installer_exe" | "installer_zip" | "standalone_zip") {
  if (kind === "installer_exe") return "Windows 安装器"
  if (kind === "installer_zip") return "ZIP 安装包"
  return "Standalone ZIP"
}

function describeSourceKind(kind: string | null | undefined) {
  const normalized = kind?.trim().toUpperCase()
  if (normalized === "DESKTOP_AGENT_MANIFEST") return "桌面连接器"
  if (normalized === "SERVER_FS") return "服务器文件系统"
  return kind?.trim() || "未设置"
}

function formatDesktopBinding(agentId: string | null | undefined, deviceName?: string | null) {
  return formatDesktopAgentReference(agentId, deviceName, "桌面设备待确认")
}

type Tone = "slate" | "sky" | "amber" | "emerald" | "rose"
type StepperState = "complete" | "current" | "pending" | "warning" | "blocked"

function pickPanelTone(tones: Tone[], fallback: Tone = "slate") {
  if (tones.includes("rose")) return "rose"
  if (tones.includes("amber")) return "amber"
  if (tones.includes("sky")) return "sky"
  if (tones.includes("emerald")) return "emerald"
  return fallback
}

function describeSignature(status: string) {
  const normalized = status.trim().toUpperCase()
  if (normalized === "SIGNED") return { label: "已签名", tone: "emerald" as const }
  if (normalized === "UNSIGNED") return { label: "未签名", tone: "rose" as const }
  if (normalized === "UNSUPPORTED") return { label: "不支持签名校验", tone: "amber" as const }
  if (normalized === "UNKNOWN") return { label: "签名未知", tone: "slate" as const }
  return { label: status, tone: "slate" as const }
}

function describeStepperState(state: StepperState) {
  if (state === "complete") {
    return {
      label: "已完成",
      tone: "emerald" as const,
      nodeClass: "border-emerald-200 bg-emerald-50 text-emerald-700",
      lineClass: "bg-emerald-200",
      cardClass: "border-emerald-200/80 bg-emerald-50/75",
    }
  }
  if (state === "current") {
    return {
      label: "当前步骤",
      tone: "sky" as const,
      nodeClass: "border-primary/20 bg-primary/10 text-primary",
      lineClass: "bg-primary/15",
      cardClass: "border-primary/20 bg-[#f7faff] ring-1 ring-primary/10 shadow-[0_22px_44px_-34px_rgba(30,58,95,0.28)]",
    }
  }
  if (state === "warning") {
    return {
      label: "需处理",
      tone: "amber" as const,
      nodeClass: "border-amber-200 bg-amber-50 text-amber-700",
      lineClass: "bg-amber-200",
      cardClass: "border-amber-200/80 bg-amber-50/85",
    }
  }
  if (state === "blocked") {
    return {
      label: "被阻塞",
      tone: "rose" as const,
      nodeClass: "border-rose-200 bg-rose-50 text-rose-700",
      lineClass: "bg-rose-200",
      cardClass: "border-rose-200/80 bg-rose-50/85",
    }
  }
  return {
    label: "待执行",
    tone: "slate" as const,
    nodeClass: "border-slate-200 bg-white text-slate-500",
    lineClass: "bg-slate-200",
    cardClass: "border-border/70 bg-white/88",
  }
}

function StepCard(props: {
  index: string
  icon: LucideIcon
  title: string
  description: string
  status: string
  summary: string
  state: StepperState
  isLast?: boolean
}) {
  const { index, icon: Icon, title, description, status, summary, state, isLast = false } = props
  const meta = describeStepperState(state)
  return (
    <div className="flex gap-4">
      <div className="flex w-12 shrink-0 flex-col items-center">
        <div className={cn("flex h-12 w-12 items-center justify-center rounded-full border shadow-[0_14px_30px_-24px_rgba(15,23,42,0.3)]", meta.nodeClass)}>
          <Icon className="h-5 w-5" />
        </div>
        {!isLast ? <div className={cn("mt-2 w-px flex-1 rounded-full", meta.lineClass)} /> : null}
      </div>

      <div className={cn("flex-1 rounded-[1.3rem] border p-4 transition-all duration-200", meta.cardClass)}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Step {index}</div>
            <div className="mt-1 text-base font-semibold text-slate-950">{title}</div>
          </div>
          <div className="flex flex-wrap gap-2">
            <TonePill tone={meta.tone}>{meta.label}</TonePill>
            <TonePill tone={meta.tone}>{status}</TonePill>
          </div>
        </div>

        <p className="mt-3 text-sm leading-6 text-slate-600">{description}</p>
        <EntryNote tone={meta.tone}>{summary}</EntryNote>
      </div>
    </div>
  )
}

export function DesktopAgentPage() {
  const capabilitiesQ = useSystemCapabilities()
  const isHostedMode = capabilitiesQ.data?.appMode === "hosted"
  const currentUserQ = useCurrentUser(capabilitiesQ.data?.authEnabled ?? false)
  const desktopAgentReleaseQ = useDesktopAgentRelease(undefined, isHostedMode)
  const setupCatalogQ = useDesktopAgentSetupCatalog(isHostedMode)
  const createSetupSessionM = useCreateDesktopAgentSetupSession()
  const desktopAgentsQ = useDesktopAgents(isHostedMode)
  const [searchParams] = useSearchParams()
  const preferredProjectFromUrl = searchParams.get("projectId")?.trim() || ""
  const availableProjects = useMemo(() => setupCatalogQ.data?.projects ?? [], [setupCatalogQ.data?.projects])
  const initialProjectId =
    (preferredProjectFromUrl && availableProjects.some((item) => item.projectId === preferredProjectFromUrl) ? preferredProjectFromUrl : "") ||
    availableProjects[0]?.projectId ||
    ""
  const [preferredProjectId, setPreferredProjectId] = useState(initialProjectId)
  const [selectedRootKey, setSelectedRootKey] = useState("")
  const [setupSession, setSetupSession] = useState<DesktopAgentSetupSession | null>(null)
  const [showOtherAssets, setShowOtherAssets] = useState(false)
  const [currentTime, setCurrentTime] = useState(() => Date.now())

  const agentsById = useMemo(() => new Map((desktopAgentsQ.data ?? []).map((item) => [item.agentId, item])), [desktopAgentsQ.data])
  const resolvedPreferredProjectId =
    preferredProjectId && availableProjects.some((item) => item.projectId === preferredProjectId) ? preferredProjectId : initialProjectId
  const selectedProject = availableProjects.find((item) => item.projectId === resolvedPreferredProjectId) ?? availableProjects[0] ?? null

  const selectedRoot = selectedProject?.candidateRoots.find((item) => item.rootKey === selectedRootKey) ?? selectedProject?.candidateRoots[0] ?? null
  const latestRelease = desktopAgentReleaseQ.data?.latest ?? null
  const releasePolicy = desktopAgentReleaseQ.data?.policy ?? null
  const preferredAsset =
    latestRelease?.preferredAsset ??
    latestRelease?.assets.find((asset) => asset.kind === "installer_exe") ??
    latestRelease?.assets[0] ??
    null
  const selectedAgent = selectedProject?.desktopAgentId ? agentsById.get(selectedProject.desktopAgentId) ?? null : null
  const onlineAgentCount = (desktopAgentsQ.data ?? []).filter((item) => item.status === "ONLINE").length
  const boundProjectCount = availableProjects.filter((item) => item.sourceKind === "DESKTOP_AGENT_MANIFEST").length
  const boundOnlineProjectCount = availableProjects.filter(
    (item) => item.sourceKind === "DESKTOP_AGENT_MANIFEST" && item.desktopAgentId && agentsById.get(item.desktopAgentId)?.status === "ONLINE",
  ).length
  const offlineBoundProjects = availableProjects.filter(
    (item) => item.sourceKind === "DESKTOP_AGENT_MANIFEST" && (!item.desktopAgentId || agentsById.get(item.desktopAgentId)?.status !== "ONLINE"),
  )
  const offlineBoundProjectCount = offlineBoundProjects.length
  const unboundProjects = availableProjects.filter((item) => item.sourceKind !== "DESKTOP_AGENT_MANIFEST")

  useEffect(() => {
    if (!setupSession) return
    const timer = window.setInterval(() => {
      setCurrentTime(Date.now())
    }, 30_000)
    return () => window.clearInterval(timer)
  }, [setupSession])

  const setupCodeExpired = setupSession ? new Date(setupSession.expiresAt).getTime() <= currentTime : false

  function selectProject(projectId: string, rootKey?: string) {
    const project = availableProjects.find((item) => item.projectId === projectId) ?? null
    setPreferredProjectId(projectId)
    setSelectedRootKey(rootKey ?? project?.candidateRoots[0]?.rootKey ?? "")
  }

  async function onGenerateSetupCode() {
    try {
      const session = await createSetupSessionM.mutateAsync(resolvedPreferredProjectId || null)
      setSetupSession(session)
      showSuccessFeedback(
        "接入码已生成",
        `${selectedProject?.title ?? "当前范围"} 的接入码已准备好，${formatTimeRemaining(session.expiresAt)}。`,
      )
    } catch (err) {
      showErrorFeedback("生成接入码失败", formatApiError(err))
    }
  }

  async function onCopySetupCode() {
    if (!setupSession?.setupCode) return
    try {
      await navigator.clipboard.writeText(setupSession.setupCode)
      showSuccessFeedback("接入码已复制", "现在可以回到 Windows 客户端直接粘贴这条接入码。")
    } catch (err) {
      showErrorFeedback("复制接入码失败", formatApiError(err))
    }
  }

  function onDownloadAsset(assetName: string, assetKind: "installer_exe" | "installer_zip" | "standalone_zip") {
    showInfoFeedback("开始下载安装包", `${describeAsset(assetKind)} ${assetName} 已开始下载。`)
  }

  if (!isHostedMode) {
    return (
      <div className="space-y-2">
        <h1 className="text-lg font-semibold">Desktop Agent</h1>
        <p className="text-sm text-muted-foreground">当前运行模式不是 hosted，这个页面不可用。</p>
      </div>
    )
  }

  const setupCodeStatus = !setupSession ? "未生成" : setupCodeExpired ? "已过期" : "待客户端使用"
  const setupCodeTone: Tone = !setupSession ? "slate" : setupCodeExpired ? "amber" : "emerald"
  const selectedBinding =
    selectedProject?.sourceKind === "DESKTOP_AGENT_MANIFEST" && selectedAgent
      ? `${formatDesktopBinding(selectedProject.desktopAgentId, selectedAgent.deviceName)} · ${selectedAgent.status === "ONLINE" ? "在线" : "离线"}`
      : selectedProject?.sourceKind === "DESKTOP_AGENT_MANIFEST"
        ? `${formatDesktopBinding(selectedProject.desktopAgentId)} · 等待上线确认`
        : "当前未绑定桌面连接器"
  const selectedClientStatus =
    selectedProject?.sourceKind !== "DESKTOP_AGENT_MANIFEST"
      ? "未绑定"
      : selectedAgent?.status === "ONLINE"
        ? "客户端在线"
        : "等待客户端上线"
  const preferredAssetSignature = preferredAsset ? describeSignature(preferredAsset.signature.status) : null
  const downloadStepState: StepperState = !preferredAsset
    ? "blocked"
    : setupSession || selectedProject?.sourceKind === "DESKTOP_AGENT_MANIFEST"
      ? "complete"
      : "current"
  const codeStepState: StepperState = !preferredAsset
    ? "blocked"
    : !setupSession
      ? "pending"
      : setupCodeExpired
        ? "warning"
        : selectedProject?.sourceKind === "DESKTOP_AGENT_MANIFEST"
          ? "complete"
          : "current"
  const finishStepState: StepperState =
    selectedProject?.sourceKind === "DESKTOP_AGENT_MANIFEST"
      ? selectedAgent?.status === "ONLINE"
        ? "complete"
        : "warning"
      : setupSession && !setupCodeExpired
        ? "current"
        : "pending"
  const stepperItems = [
    {
      index: "1",
      icon: Download,
      title: "下载客户端",
      description: preferredAsset ? `推荐先使用 ${describeAsset(preferredAsset.kind)} 完成首次安装。` : "当前服务器还没有发布安装包，流程会停在这一步。",
      status: !preferredAsset ? "等待发布" : setupSession || selectedProject?.sourceKind === "DESKTOP_AGENT_MANIFEST" ? "已进入下一步" : "先完成安装",
      summary: preferredAsset
        ? `${describeAsset(preferredAsset.kind)} · ${latestRelease?.version ?? "最新版本"} · ${preferredAssetSignature?.label ?? "签名未知"}`
        : "需要先在服务器发布至少一个可下载的 Windows 客户端安装包。",
      state: downloadStepState,
    },
    {
      index: "2",
      icon: Link2,
      title: "生成接入码",
      description: setupSession ? "接入码已生成，可直接在 Windows 客户端粘贴。" : "接入码会包含服务器地址、项目和逻辑根信息。",
      status: !preferredAsset ? "等待上一步" : !setupSession ? "待生成" : setupCodeExpired ? "需要刷新" : selectedProject?.sourceKind === "DESKTOP_AGENT_MANIFEST" ? "已完成" : "当前步骤",
      summary: setupSession
        ? `${formatTimeRemaining(setupSession.expiresAt)} · 截止 ${formatDateTime(setupSession.expiresAt)}`
        : "生成后可以直接复制到桌面端，不需要手工拼服务器地址和项目参数。",
      state: codeStepState,
    },
    {
      index: "3",
      icon: ShieldCheck,
      title: "完成接入",
      description:
        selectedProject?.sourceKind === "DESKTOP_AGENT_MANIFEST"
          ? `当前项目已绑定 ${selectedAgent?.deviceName ?? "设备"}，等待客户端在线即可。`
          : "客户端完成接入后，再在本地确认一次目录即可。",
      status:
        selectedProject?.sourceKind === "DESKTOP_AGENT_MANIFEST"
          ? selectedAgent?.status === "ONLINE"
            ? "已在线"
            : "等待上线"
          : setupSession && !setupCodeExpired
            ? "等待桌面端执行"
            : "待接入",
      summary:
        selectedProject?.sourceKind === "DESKTOP_AGENT_MANIFEST"
          ? `${selectedAgent?.deviceName ?? "设备"} · 最近心跳 ${formatDateTime(selectedAgent?.lastSeenAt)}`
          : "把接入码粘贴到 Windows 客户端后，再按提示选择本地目录完成绑定。",
      state: finishStepState,
    },
  ] as const
  const completedStepCount = stepperItems.filter((item) => item.state === "complete").length
  const currentStep = stepperItems.find((item) => item.state === "current")
    ?? stepperItems.find((item) => item.state === "warning" || item.state === "blocked")
    ?? stepperItems.find((item) => item.state === "pending")
    ?? stepperItems[stepperItems.length - 1]
  const currentStepMeta = describeStepperState(currentStep.state)
  const flowAction =
    !preferredAsset
      ? "先在服务器发布或检查 Windows 客户端安装包。"
      : !setupSession || setupCodeExpired
        ? "生成一条新的接入码，并复制到 Windows 客户端。"
        : selectedProject?.sourceKind !== "DESKTOP_AGENT_MANIFEST"
          ? "回到 Windows 客户端粘贴接入码，完成本地目录绑定。"
          : selectedAgent?.status === "ONLINE"
            ? "当前项目已经在线，可以继续到项目设置确认目录和根路径。"
            : "项目已绑定但设备还没上线，优先检查客户端是否已启动并联网。"
  const releaseInstallMode = preferredAsset
    ? preferredAsset.silentInstall.supported
      ? `${preferredAsset.silentInstall.strategy}${preferredAsset.silentInstall.relaunch ? " · 安装后拉起" : ""}`
      : "不支持静默安装"
    : "未提供"
  const releaseFocusTone: Tone = !preferredAsset ? "rose" : preferredAssetSignature?.tone ?? "sky"
  const setupScopeLabel = selectedProject ? `${selectedProject.title} / ${selectedRoot?.label ?? "默认根目录"}` : "不预选项目"
  const heroWatchlist: Array<{ title: string; detail: string; tone: Tone }> = []
  if (!preferredAsset) {
    heroWatchlist.push({
      title: "安装包缺失",
      detail: "当前服务器还没有发布可下载的桌面客户端，流程会停在 Step 1。",
      tone: "rose",
    })
  }
  if (setupSession && setupCodeExpired) {
    heroWatchlist.push({
      title: "接入码已过期",
      detail: "当前 setup code 已经过期，需要先刷新一条新的接入码再回到桌面端。",
      tone: "amber",
    })
  }
  if (selectedProject?.sourceKind === "DESKTOP_AGENT_MANIFEST" && selectedAgent?.status !== "ONLINE") {
    heroWatchlist.push({
      title: "目标设备未上线",
      detail: `${selectedAgent?.deviceName ?? "当前绑定设备"} 还没有在线，请先检查客户端启动状态和网络连通性。`,
      tone: "amber",
    })
  }
  if (offlineBoundProjectCount > 0) {
    heroWatchlist.push({
      title: "存在离线绑定项目",
      detail: `${offlineBoundProjectCount} 个项目仍绑定到离线设备，可能影响当前账号下的本地素材可用性。`,
      tone: "amber",
    })
  }
  if (!heroWatchlist.length) {
    heroWatchlist.push({
      title: "接入面整体平稳",
      detail: "安装包、接入码和当前绑定状态都没有出现明显阻塞，可以继续做新设备接入或项目绑定确认。",
      tone: "emerald",
    })
  }
  const heroWatchlistTone = pickPanelTone(
    heroWatchlist.map((item) => item.tone),
    "slate",
  )
  const setupWatchlistTone: Tone = setupSession ? (setupCodeExpired ? "amber" : "emerald") : "slate"
  const intakeOverviewTone: Tone = offlineBoundProjectCount > 0 ? "amber" : unboundProjects.length > 0 ? "slate" : "emerald"
  const intakeWatchlistTone: Tone = offlineBoundProjects.length ? "amber" : unboundProjects.length ? "slate" : "emerald"
  const bindingFocusTone: Tone =
    !selectedProject || selectedProject.sourceKind !== "DESKTOP_AGENT_MANIFEST" ? "slate" : selectedAgent?.status === "ONLINE" ? "emerald" : "amber"
  const bindingEnvelopeTone: Tone =
    !selectedProject || selectedProject.sourceKind !== "DESKTOP_AGENT_MANIFEST" ? "slate" : selectedAgent?.status === "ONLINE" ? "emerald" : "amber"
  const policyBoardTone: Tone = !preferredAsset ? "rose" : setupSession && setupCodeExpired ? "amber" : "emerald"

  return (
    <div className="space-y-5 pb-4">
      <section className="theme-card-main overflow-hidden">
        <div className="grid gap-6 p-6 sm:p-7 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              <MetaChip strong>接入流程</MetaChip>
              <MetaChip>{availableProjects.length} 个项目可接入</MetaChip>
              <MetaChip>{onlineAgentCount} 台连接器在线</MetaChip>
              <MetaChip>{`已推进 ${completedStepCount}/3`}</MetaChip>
            </div>

            <div className="space-y-3">
              <h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-[2.35rem]">跟着流程条走：先装客户端，再发接入码，最后确认设备上线。</h1>
              <p className="max-w-3xl text-sm leading-7 text-[#5f7188] sm:text-base">
                当前步骤、卡点和下一步都会直接显示在这里。按顺序完成安装、发码和上线确认，就能把项目接入到桌面连接器。
              </p>
            </div>

            <SystemBoard
              eyebrow="接入进度"
              title={`当前 Step ${currentStep.index} · ${currentStep.title}`}
              description="接入流程分成安装、发码和上线三步；当前状态和下一步会直接显示在这里。"
              tone={currentStepMeta.tone}
              headerRight={
                <div className="flex flex-wrap gap-2">
                  <TonePill tone={currentStepMeta.tone}>{currentStepMeta.label}</TonePill>
                  <TonePill tone={currentStepMeta.tone}>{`已推进 ${completedStepCount}/3`}</TonePill>
                </div>
              }
              className="rounded-[1.4rem] bg-white/72 shadow-[0_18px_40px_-34px_rgba(15,23,42,0.18)] sm:p-5"
              bodyClassName="space-y-4"
            >
                {stepperItems.map((step, index) => (
                  <StepCard
                    key={step.index}
                    index={step.index}
                    icon={step.icon}
                    title={step.title}
                    description={step.description}
                    status={step.status}
                    summary={step.summary}
                    state={step.state}
                    isLast={index === stepperItems.length - 1}
                  />
                ))}
            </SystemBoard>
          </div>

          <StatusSidebar
            eyebrow="当前状态"
            title="接入状态"
            badge={<TonePill tone={selectedAgent?.status === "ONLINE" ? "emerald" : setupSession && !setupCodeExpired ? "sky" : "amber"}>{selectedClientStatus}</TonePill>}
            bodyClassName="gap-3"
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <OpsSignalTile
                icon={FolderTree}
                label="当前范围"
                value={`${availableProjects.length} 个项目`}
                detail={`已绑定 ${boundProjectCount} 个；未绑定 ${unboundProjects.length} 个。`}
                tone={availableProjects.length > 0 ? "sky" : "slate"}
              />
              <OpsSignalTile
                icon={RadioTower}
                label="设备在线"
                value={`${onlineAgentCount}/${desktopAgentsQ.data?.length ?? 0}`}
                detail={`在线绑定项目 ${boundOnlineProjectCount} 个；离线绑定 ${offlineBoundProjectCount} 个。`}
                tone={offlineBoundProjectCount > 0 ? "amber" : "emerald"}
              />
              <OpsSignalTile
                icon={Link2}
                label="接入码"
                value={setupCodeStatus}
                detail={setupSession ? `${formatTimeRemaining(setupSession.expiresAt)} · 作用域 ${setupScopeLabel}` : "生成后会附带项目和逻辑根信息。"}
                tone={setupSession ? (setupCodeExpired ? "amber" : "sky") : "slate"}
              />
              <OpsSignalTile
                icon={Activity}
                label="当前动作"
                value={`Step ${currentStep.index}`}
                detail={flowAction}
                tone={currentStepMeta.tone}
              />
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <StatusField label="当前账号" value={currentUserQ.data?.email ?? "未登录"} />
              <StatusField label="默认项目" value={selectedProject?.title ?? "未预选项目"} emphasize />
              <StatusField label="流程推进" value={`已完成 ${completedStepCount}/3；当前 Step ${currentStep.index}`} emphasize />
              <StatusField label="当前绑定" value={selectedBinding} />
              <StatusField label="当前逻辑根" value={selectedRoot?.label ?? "等待选择逻辑根"} />
              <StatusField label="最近心跳" value={formatDateTime(selectedAgent?.lastSeenAt)} />
              <StatusField label="接入码状态" value={setupCodeStatus} />
            </div>

            <WatchlistPanel
              title="当前待处理"
              description="查看安装包、接入码和设备状态里的待处理事项。"
              tone={heroWatchlistTone}
              bodyClassName="space-y-3"
            >
                {heroWatchlist.map((item) => (
                  <WatchlistItem key={`${item.title}-${item.detail}`} title={item.title} detail={item.detail} tone={item.tone} />
                ))}
            </WatchlistPanel>
          </StatusSidebar>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="theme-card overflow-hidden">
              <CardHeader className="theme-card-header gap-3">
                <CardTitle>客户端下载</CardTitle>
                <CardDescription>先下载推荐安装包；如果需要 ZIP 或便携版，可以在下方展开其他版本。</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                {latestRelease ? (
                  <div className="space-y-4">
                    <SystemBoard
                      eyebrow="推荐安装包"
                      title={preferredAsset ? describeAsset(preferredAsset.kind) : "等待安装包"}
                      description={`${latestRelease.version} · 发布时间 ${formatDateTime(latestRelease.publishedAt)}`}
                      tone={releaseFocusTone}
                      headerRight={preferredAssetSignature ? <TonePill tone={preferredAssetSignature.tone}>{preferredAssetSignature.label}</TonePill> : null}
                      bodyClassName="space-y-4"
                    >
                      <div className="flex flex-wrap gap-2">
                        <MetaChip>{latestRelease.version}</MetaChip>
                        <MetaChip>{preferredAsset ? formatBytes(preferredAsset.sizeBytes) : "未提供体积"}</MetaChip>
                        <MetaChip>{releaseInstallMode}</MetaChip>
                      </div>

                      {preferredAsset ? (
                        <div className="flex flex-wrap gap-2">
                          <Button asChild size="lg" className="min-w-[14rem] justify-between">
                            <a href={preferredAsset.downloadPath} onClick={() => onDownloadAsset(preferredAsset.name, preferredAsset.kind)}>
                              <span className="flex items-center gap-2">
                                <Download className="h-4 w-4" />
                                下载 {describeAsset(preferredAsset.kind)}
                              </span>
                              <ExternalLink className="h-4 w-4" />
                            </a>
                          </Button>
                          {latestRelease.assets.length > 1 ? (
                            <Button type="button" variant="outline" onClick={() => setShowOtherAssets((value) => !value)}>
                              {showOtherAssets ? "收起其他安装包" : "查看其他安装包"}
                            </Button>
                          ) : null}
                        </div>
                      ) : null}
                    </SystemBoard>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <OpsSignalTile
                        icon={Download}
                        label="推荐安装包"
                        value={preferredAsset ? describeAsset(preferredAsset.kind) : "未发布"}
                        detail={preferredAsset ? `${formatBytes(preferredAsset.sizeBytes)} · ${latestRelease.version}` : "当前服务器还没有发布推荐安装包。"}
                        tone={preferredAsset ? "sky" : "rose"}
                      />
                      <OpsSignalTile
                        icon={ShieldCheck}
                        label="签名策略"
                        value={preferredAssetSignature?.label ?? "未提供"}
                        detail={
                          releasePolicy?.requireSigned
                            ? `服务器策略要求仅展示已签名安装包；当前可见 ${releasePolicy.visibleAssetCount} / 总计 ${releasePolicy.totalAssetCount}。`
                            : "当前服务器不强制签名校验；如果有已签名版本，可以优先选择。"
                        }
                        tone={releasePolicy?.requireSigned ? "sky" : preferredAssetSignature?.tone ?? "slate"}
                      />
                      <OpsSignalTile
                        icon={Activity}
                        label="安装能力"
                        value={releaseInstallMode}
                        detail={preferredAsset?.silentInstall.supported ? "当前推荐安装包支持静默安装，便于后续升级和部署。" : "当前推荐安装包不提供静默安装能力。"}
                        tone={preferredAsset?.silentInstall.supported ? "emerald" : "slate"}
                      />
                      <OpsSignalTile
                        icon={RadioTower}
                        label="可下载版本"
                        value={`${latestRelease.assets.length} 个资产`}
                        detail="当前提供推荐安装包和其他可选下载版本。"
                        tone={latestRelease.assets.length > 1 ? "slate" : "emerald"}
                      />
                    </div>
                  </div>
                ) : (
                  <EmptyState message="当前服务器还没有发布桌面连接器安装包。" />
                )}

                {latestRelease && latestRelease.assets.length > 1 ? (
                <SystemBoard
                  title="其他安装包"
                    description="ZIP 和便携版适合调试、临时分发或不安装直接运行。"
                  tone="slate"
                    headerRight={showOtherAssets ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                    bodyClassName="space-y-3"
                  >
                    {showOtherAssets ? (
                      <div className="flex flex-wrap gap-2">
                        {latestRelease.assets
                          .filter((asset) => asset.name !== preferredAsset?.name)
                          .map((asset) => {
                            const signature = describeSignature(asset.signature.status)
                            return (
                              <Button key={asset.name} asChild variant="outline" size="sm">
                                <a href={asset.downloadPath} onClick={() => onDownloadAsset(asset.name, asset.kind)}>
                                  {describeAsset(asset.kind)}
                                  <span className="text-xs text-muted-foreground">{signature.label}</span>
                                </a>
                              </Button>
                            )
                          })}
                      </div>
                    ) : null}
                  </SystemBoard>
                ) : null}

                {desktopAgentReleaseQ.error ? <p className="text-sm text-destructive">{formatApiError(desktopAgentReleaseQ.error)}</p> : null}
              </CardContent>
            </Card>

            <Card className="theme-card overflow-hidden">
              <CardHeader className="theme-card-header gap-3">
                <CardTitle>接入码</CardTitle>
                <CardDescription>在这里选择默认项目和逻辑根，生成后可以直接复制到 Windows 客户端。</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <ControlDeck
                  title={setupScopeLabel}
                  description={flowAction}
                  badge={<TonePill tone={setupSession ? (setupCodeExpired ? "amber" : "sky") : "slate"}>{setupCodeStatus}</TonePill>}
                  tone={setupSession ? (setupCodeExpired ? "amber" : "sky") : "slate"}
                  bodyClassName="grid gap-3 sm:grid-cols-3"
                >
                  <StatusField label="预选项目" value={selectedProject?.title ?? "不预选项目"} emphasize />
                  <StatusField label="逻辑根" value={selectedRoot?.label ?? "默认根目录"} />
                  <StatusField label="目标绑定" value={selectedClientStatus} />
                </ControlDeck>

                <div className="space-y-2">
                  <Label htmlFor="desktop-agent-preferred-project">默认项目</Label>
                  <select
                    id="desktop-agent-preferred-project"
                    className="h-10 w-full rounded-xl border bg-background px-3 text-sm shadow-[0_10px_24px_-20px_rgba(15,23,42,0.18)]"
                    value={resolvedPreferredProjectId}
                    onChange={(e) => selectProject(e.target.value)}
                    disabled={setupCatalogQ.isLoading || createSetupSessionM.isPending}
                  >
                    <option value="">不预选项目</option>
                    {availableProjects.map((project) => (
                      <option key={project.projectId} value={project.projectId}>
                        {project.title}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button size="lg" type="button" onClick={() => void onGenerateSetupCode()} disabled={createSetupSessionM.isPending} className="min-w-[10rem]">
                    <Link2 className="h-4 w-4" />
                    {createSetupSessionM.isPending ? "生成中..." : setupSession ? "刷新接入码" : "生成接入码"}
                  </Button>
                  <Button type="button" variant="outline" onClick={() => void onCopySetupCode()} disabled={!setupSession?.setupCode}>
                    <Copy className="h-4 w-4" />
                    复制到剪贴板
                  </Button>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <OpsSignalTile
                    icon={FolderTree}
                    label="预选范围"
                    value={selectedProject?.title ?? "不预选项目"}
                    detail={selectedRoot?.label ?? "默认根目录"}
                    tone={selectedProject ? "sky" : "slate"}
                  />
                  <OpsSignalTile
                    icon={RadioTower}
                    label="目标绑定"
                    value={selectedBinding}
                    detail={
                      selectedProject?.sourceKind === "DESKTOP_AGENT_MANIFEST"
                        ? "当前项目已经绑定过桌面客户端；如果设备离线，需要优先确认客户端状态。"
                        : "当前项目还没有桌面端绑定，可以开始首次接入。"
                    }
                    tone={selectedProject?.sourceKind === "DESKTOP_AGENT_MANIFEST" ? (selectedAgent?.status === "ONLINE" ? "emerald" : "amber") : "slate"}
                  />
                </div>

                <SystemBoard
                  eyebrow="当前接入码"
                  title={setupCodeStatus}
                  description="查看当前接入码、有效期和使用状态。"
                  tone={setupCodeTone}
                  headerRight={<TonePill tone={setupCodeTone}>{setupCodeStatus}</TonePill>}
                  bodyClassName="space-y-4"
                >
                  <EntryNote tone={setupCodeTone} className="break-all font-mono text-foreground">
                    {setupSession?.setupCode ?? "生成后会显示在这里。"}
                  </EntryNote>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <StatusField
                      label="有效期"
                      value={setupSession ? `${formatTimeRemaining(setupSession.expiresAt)} · 截止 ${formatDateTime(setupSession.expiresAt)}` : "生成后显示有效期。"}
                    />
                    <StatusField
                      label="当前状态"
                      value={setupSession ? (setupCodeExpired ? "当前接入码已过期，请重新生成。" : "当前接入码尚可使用，可直接回到桌面端完成接入。") : "等待生成第一条接入码。"}
                      emphasize
                    />
                  </div>
                </SystemBoard>

                <WatchlistPanel
                  title="当前待办"
                  description="查看接入码刷新、首次生成和继续接入等待办。"
                  tone={setupWatchlistTone}
                  bodyClassName="space-y-3"
                >
                    {setupSession ? (
                      <WatchlistItem
                        title={setupCodeExpired ? "接入码需要刷新" : "接入码已就绪"}
                        detail={
                          setupCodeExpired
                            ? "当前接入码已过期，请先点击“刷新接入码”，再回到 Windows 客户端粘贴。"
                            : "当前接入码尚可使用，可直接在桌面端继续完成接入。"
                        }
                        tone={setupCodeExpired ? "amber" : "emerald"}
                      />
                    ) : (
                      <WatchlistItem
                        title="等待生成第一条接入码"
                        detail="先选定默认项目或保留为空，再生成接入码，桌面端就能直接获得服务器地址和范围信息。"
                        tone="slate"
                      />
                    )}
                </WatchlistPanel>

                {createSetupSessionM.error ? <p className="text-sm text-destructive">{formatApiError(createSetupSessionM.error)}</p> : null}
              </CardContent>
            </Card>
          </div>

          <Card className="theme-card overflow-hidden">
            <CardHeader className="theme-card-header gap-3">
              <CardTitle>项目接入</CardTitle>
              <CardDescription>先看哪些项目还没接入或需要恢复，再进入单个项目确认逻辑根和目录映射。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="grid gap-3 xl:grid-cols-[0.92fr_1.08fr]">
                <SystemBoard
                  eyebrow="接入概览"
                  title="当前接入情况"
                  description="查看项目接入数量、离线绑定和待接入情况。"
                  tone={intakeOverviewTone}
                  bodyClassName="grid gap-3 sm:grid-cols-3 xl:grid-cols-1"
                >
                    <OpsSignalTile
                      icon={FolderTree}
                      label="项目总数"
                      value={`${availableProjects.length}`}
                      detail={`已绑定 ${boundProjectCount} 个`}
                      tone={availableProjects.length > 0 ? "sky" : "slate"}
                    />
                    <OpsSignalTile
                      icon={RadioTower}
                      label="等待上线"
                      value={`${offlineBoundProjectCount}`}
                      detail="这些项目已经绑定桌面端，但目标设备当前不在线。"
                      tone={offlineBoundProjectCount > 0 ? "amber" : "emerald"}
                    />
                    <OpsSignalTile
                      icon={Link2}
                      label="未绑定"
                      value={`${unboundProjects.length}`}
                      detail="这些项目还没有完成桌面端首次接入。"
                      tone={unboundProjects.length > 0 ? "slate" : "emerald"}
                    />
                </SystemBoard>

                <WatchlistPanel
                  title="优先处理"
                  description={
                    offlineBoundProjects.length
                      ? `当前有 ${offlineBoundProjects.length} 个项目绑定到了离线设备，请先恢复这些项目。`
                      : unboundProjects.length
                        ? `当前有 ${unboundProjects.length} 个项目仍未完成桌面端接入，可以继续补首批设备。`
                        : "当前没有离线绑定或待接入项目，项目接入状态稳定。"
                  }
                  tone={intakeWatchlistTone}
                  bodyClassName="space-y-2"
                >
                    {(offlineBoundProjects.length ? offlineBoundProjects : unboundProjects).slice(0, 3).map((project) => (
                      <WatchlistItem
                        key={`intake-${project.projectId}`}
                        title={project.title}
                        detail={
                          project.sourceKind === "DESKTOP_AGENT_MANIFEST"
                            ? `${formatDesktopBinding(project.desktopAgentId)} 当前还未在线。`
                            : "当前还没有桌面端绑定，可以开始首次接入。"
                        }
                        tone={project.sourceKind === "DESKTOP_AGENT_MANIFEST" ? "amber" : "slate"}
                      />
                    ))}
                    {!offlineBoundProjects.length && !unboundProjects.length ? (
                      <WatchlistItem title="当前接入平稳" detail="所有可接入项目都已经处于在线绑定或无待处理状态。" tone="emerald" />
                    ) : null}
                </WatchlistPanel>
              </div>

              {availableProjects.length ? (
                <div className="space-y-3">
                  {availableProjects.map((project) => {
                    const isSelected = selectedProject?.projectId === project.projectId
                    const boundAgent = project.desktopAgentId ? agentsById.get(project.desktopAgentId) ?? null : null
                    const itemTone: Tone =
                      project.sourceKind !== "DESKTOP_AGENT_MANIFEST" ? "slate" : boundAgent?.status === "ONLINE" ? "emerald" : "amber"

                    return (
                      <BoardEntryCard
                        key={project.projectId}
                        title={project.title}
                        meta={
                          <>
                            <MetaChip>{describeSourceKind(project.sourceKind)}</MetaChip>
                            <TonePill tone={itemTone}>
                              {project.sourceKind === "DESKTOP_AGENT_MANIFEST" ? (boundAgent?.status === "ONLINE" ? "已绑定 · 在线" : "已绑定 · 离线") : "未绑定"}
                            </TonePill>
                            {isSelected ? <TonePill tone="sky">当前查看</TonePill> : null}
                          </>
                        }
                        headerRight={
                          <div className="text-right text-xs text-muted-foreground">
                            <div className="font-medium text-slate-950">
                              {project.sourceKind === "DESKTOP_AGENT_MANIFEST"
                                ? boundAgent
                                  ? `${formatDesktopBinding(project.desktopAgentId, boundAgent.deviceName)} · ${boundAgent.appVersion}`
                                  : `${formatDesktopBinding(project.desktopAgentId)} · 等待上线确认`
                                : "等待首次接入"}
                            </div>
                            <div className="mt-1">{describeSourceKind(project.sourceKind)}</div>
                            {!isSelected ? (
                              <Button size="sm" variant="outline" type="button" className="mt-3" onClick={() => selectProject(project.projectId)}>
                                查看项目
                              </Button>
                            ) : null}
                          </div>
                        }
                        tone={itemTone}
                        className={cn(
                          isSelected
                            ? "border-primary/20 bg-[#f7faff] shadow-[0_22px_44px_-34px_rgba(30,58,95,0.34)] ring-1 ring-primary/10"
                            : "",
                        )}
                        bodyClassName="space-y-3"
                      >
                        <EntryNote tone={itemTone} className={itemTone === "amber" ? "text-amber-900" : undefined}>
                          {project.sourceKind === "DESKTOP_AGENT_MANIFEST"
                            ? boundAgent?.status === "ONLINE"
                              ? "当前项目已经绑定到在线桌面端，可以继续确认逻辑根和本地目录映射。"
                              : "当前项目已经绑定桌面端，但目标设备还未在线，先恢复设备连接。"
                            : "当前项目还没有桌面端绑定，生成接入码后就能开始首次本地目录映射。"}
                        </EntryNote>

                        <div className="flex flex-wrap gap-2">
                          {project.candidateRoots.length ? (
                            project.candidateRoots.map((root) => (
                              <SelectableTileButton
                                key={`${project.projectId}-${root.rootKey}`}
                                selected={isSelected && selectedRoot?.rootKey === root.rootKey}
                                title={root.label}
                                description={root.relativePath ? `相对根路径：${root.relativePath}` : "默认根目录"}
                                detail={root.sourceRootLabel ? `逻辑根标签：${root.sourceRootLabel}` : undefined}
                                onClick={() => selectProject(project.projectId, root.rootKey)}
                              />
                            ))
                          ) : (
                            <EntryNote tone="slate" className="text-muted-foreground">当前还没有可用的逻辑根选项。</EntryNote>
                          )}
                        </div>
                      </BoardEntryCard>
                    )
                  })}
                </div>
              ) : (
                <EmptyState message="当前账号还没有可接入的项目。" />
              )}

              {setupCatalogQ.error ? <p className="text-sm text-destructive">{formatApiError(setupCatalogQ.error)}</p> : null}
              {desktopAgentsQ.error ? <p className="text-sm text-destructive">{formatApiError(desktopAgentsQ.error)}</p> : null}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card className="theme-card overflow-hidden">
            <CardHeader className="theme-card-header gap-3">
              <CardTitle>当前项目详情</CardTitle>
              <CardDescription>查看当前项目的逻辑根、绑定设备和本地目录映射提示。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              {selectedProject ? (
                <>
                  <ControlDeck
                    title={selectedProject.title}
                    description={
                      selectedProject.sourceKind === "DESKTOP_AGENT_MANIFEST"
                        ? selectedAgent?.status === "ONLINE"
                          ? "当前项目已经绑定到在线桌面端，可以继续确认逻辑根和本地目录映射。"
                          : "当前项目已经绑定桌面端，但目标设备还未在线，先恢复设备连接。"
                        : "当前项目还没有桌面端绑定，后续会通过接入码完成首次本地目录映射。"
                    }
                    badge={
                      <div className="flex flex-wrap gap-2">
                        <TonePill tone={selectedProject.sourceKind === "DESKTOP_AGENT_MANIFEST" ? "sky" : "slate"}>{describeSourceKind(selectedProject.sourceKind)}</TonePill>
                        {selectedProject.sourceRootLabel ? <TonePill tone="sky">{`标签：${selectedProject.sourceRootLabel}`}</TonePill> : null}
                      </div>
                    }
                    tone={bindingFocusTone}
                    bodyClassName="grid gap-3 sm:grid-cols-2"
                  >
                    <StatusField label="逻辑根名称" value={selectedRoot?.label ?? "默认根目录"} emphasize />
                    <StatusField label="相对根路径" value={selectedRoot?.relativePath || "默认根目录"} />
                    <StatusField label="逻辑根标签" value={selectedRoot?.sourceRootLabel ?? selectedProject.sourceRootLabel ?? "未设置"} />
                    <StatusField label="绑定设备" value={selectedBinding} />
                    <StatusField label="最近心跳" value={formatDateTime(selectedAgent?.lastSeenAt)} />
                    <StatusField label="本地状态" value={selectedClientStatus} />
                  </ControlDeck>

                  <SystemBoard
                    eyebrow="目录映射"
                    title="本地目录映射"
                    description="服务端只记录逻辑根标签和相对路径，本机目录路径只保留在当前桌面端。"
                    tone="sky"
                    bodyClassName="space-y-3"
                  >
                    <NarrativePanel
                      icon={FolderTree}
                      title="服务器不会保存 Windows 绝对路径"
                      description="桌面客户端只会上报相对路径清单和逻辑根标签，避免把本地磁盘路径带进服务端元数据。"
                      tone="sky"
                    />
                    <NarrativePanel
                      icon={Link2}
                      title="首次接入时再完成本地映射"
                      description="同一个项目可以先在服务端保持稳定的逻辑根语义，等客户端接入后再由你在本地确认真实目录。"
                      tone="slate"
                    />
                  </SystemBoard>

                  <WatchlistPanel
                    title="当前提示"
                    description="根据当前项目状态给出下一步建议。"
                    tone={bindingEnvelopeTone}
                    bodyClassName="space-y-3"
                  >
                    <WatchlistItem
                      title={selectedProject.sourceKind === "DESKTOP_AGENT_MANIFEST" ? "项目已存在桌面绑定" : "项目等待首次接入"}
                      detail={
                        selectedProject.sourceKind === "DESKTOP_AGENT_MANIFEST"
                          ? selectedAgent?.status === "ONLINE"
                            ? `${selectedAgent?.deviceName ?? "当前设备"} 已在线，可以直接校验目录与根路径。`
                            : `${selectedAgent?.deviceName ?? "当前设备"} 还未在线，建议先恢复桌面端。`
                          : "当前项目还没有桌面端绑定，生成接入码后可在本地完成目录绑定。"
                      }
                      tone={bindingEnvelopeTone}
                    />
                  </WatchlistPanel>

                  <Button asChild variant="outline" className="w-full justify-between">
                    <Link to={`/p/${selectedProject.projectId}/settings`}>
                      打开项目设置
                      <ExternalLink className="h-4 w-4" />
                    </Link>
                  </Button>
                </>
              ) : (
                <EmptyState message="先从左侧选一个项目，即可查看对应的逻辑根详情。" />
              )}
            </CardContent>
          </Card>

          <Card className="theme-card overflow-hidden">
            <CardHeader className="theme-card-header gap-3">
              <CardTitle>使用提示</CardTitle>
              <CardDescription>首次接入和异常恢复前，先看这里的安装与排查建议。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <SystemBoard
                eyebrow="接入建议"
                title="安装与接入策略"
                description="查看推荐安装方式，以及遇到异常时先检查什么。"
                tone={policyBoardTone}
                bodyClassName="space-y-3"
              >
                <NarrativePanel
                  icon={ShieldCheck}
                  title="推荐使用安装器完成首次接入"
                  description="安装器版本更适合自启、更新和桌面环境下的稳定常驻。"
                  tone="emerald"
                />
                <NarrativePanel
                  icon={ShieldAlert}
                  title="异常时优先排查签名与在线状态"
                  description="如果当前显示未签名、等待客户端上线或接入码已过期，先检查安装包来源、客户端启动状态和目标 Windows 设备是否在线。"
                  tone={!preferredAsset ? "rose" : "amber"}
                />
              </SystemBoard>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
