import { type ChangeEvent, type KeyboardEvent, useEffect, useMemo, useRef, useState } from "react"
import { useQueries } from "@tanstack/react-query"
import { Activity, ArrowRight, Camera, ChevronDown, KeyRound, Mail, Save } from "lucide-react"
import { Link } from "react-router-dom"

import { type AuditLogEvent, listAuditLogEvents } from "@/ui/api/auditLog"
import { ApiError } from "@/ui/api/http"
import { ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useProjects } from "@/ui/queries/projects"
import { useChangeMyPassword, useMyProfile, useUpdateMyProfile, useUploadMyAvatar } from "@/ui/queries/profile"
import { useSystemCapabilities } from "@/ui/queries/system"
import { getLocalDateKey, loadDailyStudyTotalsByDate } from "@/ui/store/workbenchDailyStats"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { syncStudyMetricsSnapshot } from "@/ui/studyMetricsSync"
import { cn } from "@/ui/utils"

import {
  buildDateKeySpan,
  buildCurveGeometry,
  buildRecentDateKeys,
  formatDateKeyShortLabel,
  formatDateKeyWeekdayLabel,
  formatDateTimeLabel,
  formatDurationCompact,
  isLearningSubmitEvent,
  isReviewCommitEvent,
  isSuccessfulStudyEvent,
  type DailyStatPoint,
} from "./profileStats"

type ProfileDraft = {
  nickname: string
  bio: string
}

type LearningMetric = "effective" | "watch" | "compose" | "review" | "qa"
type LearningRange = "week" | "month" | "history"

type LearningMetricOption = {
  value: LearningMetric
  label: string
  stroke: string
  surface: string
  fillStart: string
  fillEnd: string
}

const learningMetricOptions: LearningMetricOption[] = [
  {
    value: "effective",
    label: "有效学习",
    stroke: "#2563eb",
    surface: "#eff6ff",
    fillStart: "rgba(37,99,235,0.22)",
    fillEnd: "rgba(37,99,235,0.03)",
  },
  {
    value: "watch",
    label: "内容接触",
    stroke: "#0f766e",
    surface: "#ecfeff",
    fillStart: "rgba(15,118,110,0.18)",
    fillEnd: "rgba(15,118,110,0.03)",
  },
  {
    value: "compose",
    label: "复述点构建",
    stroke: "#ef4444",
    surface: "#fef2f2",
    fillStart: "rgba(239,68,68,0.2)",
    fillEnd: "rgba(239,68,68,0.03)",
  },
  {
    value: "review",
    label: "复习时长",
    stroke: "#14b8a6",
    surface: "#ecfeff",
    fillStart: "rgba(20,184,166,0.2)",
    fillEnd: "rgba(20,184,166,0.03)",
  },
  {
    value: "qa",
    label: "AI 问答",
    stroke: "#7c3aed",
    surface: "#f5f3ff",
    fillStart: "rgba(124,58,237,0.18)",
    fillEnd: "rgba(124,58,237,0.03)",
  },
]

const learningRangeOptions: Array<{ value: LearningRange; label: string }> = [
  { value: "week", label: "周" },
  { value: "month", label: "月" },
  { value: "history", label: "历史" },
]

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function getLearningMetricValue(point: DailyStatPoint, metric: LearningMetric) {
  if (metric === "watch") return point.watchMs
  if (metric === "compose") return point.composeMs
  if (metric === "review") return point.reviewMs
  if (metric === "qa") return point.qaMs
  return point.effectiveMs
}

function getLearningMetricOption(metric: LearningMetric) {
  return learningMetricOptions.find((option) => option.value === metric) ?? learningMetricOptions[0]
}

function formatLearningMetricValue(_metric: LearningMetric, value: number) {
  return formatDurationCompact(value)
}

function formatLearningMetricAverage(_metric: LearningMetric, value: number) {
  const minutes = value / 60_000
  if (minutes <= 0) return "0m"
  if (minutes < 60) {
    const roundedMinutes = Math.round(minutes * 10) / 10
    return `${Number.isInteger(roundedMinutes) ? roundedMinutes : roundedMinutes.toFixed(1)}m`
  }
  const hours = minutes / 60
  const roundedHours = Math.round(hours * 10) / 10
  return `${Number.isInteger(roundedHours) ? roundedHours : roundedHours.toFixed(1)}h`
}

function formatLearningMetricVariance(value: number) {
  const roundedValue = Math.round(value * 10) / 10
  return Number.isInteger(roundedValue) ? `${roundedValue}` : roundedValue.toFixed(1)
}

function formatLearningMetricAxisLabel(metric: LearningMetric, value: number) {
  return formatLearningMetricAverage(metric, value)
}

function getLearningMetricStats(points: DailyStatPoint[], metric: LearningMetric) {
  const values = points.map((point) => getLearningMetricValue(point, metric))
  const total = values.reduce((sum, value) => sum + value, 0)
  const average = values.length > 0 ? total / values.length : 0
  const activePoints = points
    .map((point) => ({
      point,
      value: getLearningMetricValue(point, metric),
    }))
    .filter((entry) => entry.value > 0)
  const peakEntry = activePoints.reduce<(typeof activePoints)[number] | null>(
    (best, entry) => (best === null || entry.value > best.value ? entry : best),
    null,
  )
  const normalizedActiveValues = activePoints.map((entry) => entry.value / 60_000)
  const activeMean =
    normalizedActiveValues.length > 0
      ? normalizedActiveValues.reduce((sum, value) => sum + value, 0) / normalizedActiveValues.length
      : 0
  const stability =
    normalizedActiveValues.length > 1
      ? normalizedActiveValues.reduce((sum, value) => sum + (value - activeMean) ** 2, 0) / normalizedActiveValues.length
      : 0

  return {
    average,
    activeDays: activePoints.length,
    peakEntry,
    stability,
  }
}

function buildAxisTickIndices(total: number, maxLabels: number) {
  if (total <= 0) return []
  if (total <= maxLabels) return Array.from({ length: total }, (_, index) => index)
  if (maxLabels <= 1) return [0]
  return Array.from(new Set(Array.from({ length: maxLabels }, (_, index) => Math.round((index * (total - 1)) / (maxLabels - 1)))))
}

function MetricStatCard(props: {
  label: string
  value: string
  detail: string
}) {
  const { label, value, detail } = props

  return (
    <div className="theme-subtle-surface px-4 py-3">
      <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">{label}</div>
      <div className="mt-2 text-xl font-semibold tracking-tight text-foreground">{value}</div>
      <div className="mt-1 text-sm text-[color:var(--theme-subtle-text)]">{detail}</div>
    </div>
  )
}

function LearningViewSelect(props: {
  id: string
  label: string
  value: string
  disabled?: boolean
  onChange: (value: string) => void
  options: Array<{ value: string; label: string }>
}) {
  const { id, label, value, disabled, onChange, options } = props

  return (
    <label htmlFor={id} className="space-y-1">
      <div className="text-[10px] uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">{label}</div>
      <div className="relative min-w-[8.5rem]">
        <select
          id={id}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          className="theme-select h-10 w-full px-3 pr-10 font-medium"
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-muted-foreground">
          <ChevronDown className="h-4 w-4" />
        </div>
      </div>
    </label>
  )
}

function LearningCurve(props: {
  points: DailyStatPoint[]
  metric: LearningMetric
  range: LearningRange
  onSelectMetric: (metric: LearningMetric) => void
}) {
  const { points, metric, range, onSelectMetric } = props
  const chartWidth = 640
  const chartHeight = 236
  const selectedOption = getLearningMetricOption(metric)
  const metricLabel = selectedOption.label
  const selectedMaxValue = Math.max(...points.map((point) => Math.max(0, getLearningMetricValue(point, metric))), 1)
  const geometryByMetric = Object.fromEntries(
    learningMetricOptions.map((option) => [
      option.value,
      buildCurveGeometry(points, chartWidth, chartHeight, (point) => getLearningMetricValue(point, option.value)),
    ]),
  ) as Record<LearningMetric, ReturnType<typeof buildCurveGeometry<DailyStatPoint>>>
  const selectedGeometry = geometryByMetric[metric]
  const stats = getLearningMetricStats(points, metric)
  const gridLabels = selectedGeometry.gridLines.map((_, index) => formatLearningMetricAxisLabel(metric, selectedMaxValue * ((3 - index) / 3)))
  const selectedGradientId = `profile-curve-fill-${metric}`
  const xAxisTickIndices = buildAxisTickIndices(points.length, range === "week" ? 7 : 6)

  return (
    <div className="theme-soft-surface rounded-[1.6rem] p-5">
      <div className="theme-subtle-surface overflow-hidden rounded-[1.4rem] px-3 py-4">
        <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="h-56 w-full" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id={selectedGradientId} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor={selectedOption.fillStart} />
              <stop offset="100%" stopColor={selectedOption.fillEnd} />
            </linearGradient>
          </defs>

          {selectedGeometry.gridLines.map((lineY, index) => (
            <g key={`grid-${index}`}>
              <line
                x1="44"
                x2={chartWidth - 44}
                y1={lineY}
                y2={lineY}
                stroke="var(--theme-soft-border)"
                strokeDasharray="6 8"
              />
              <text x="36" y={lineY + 4} textAnchor="end" fontSize="11" fill="var(--theme-subtle-text)">
                {gridLabels[index]}
              </text>
            </g>
          ))}

          {learningMetricOptions
            .filter((option) => option.value !== metric)
            .map((option) => {
              const geometry = geometryByMetric[option.value]
              return (
                <g
                  key={option.value}
                  onClick={() => onSelectMetric(option.value)}
                  className="cursor-pointer"
                  style={{ opacity: 0.34 }}
                >
                  <path d={geometry.linePath} fill="none" stroke={option.stroke} strokeWidth="2.5" strokeLinecap="round" strokeDasharray="9 9" />
                </g>
              )
            })}

          <path d={selectedGeometry.areaPath} fill={`url(#${selectedGradientId})`} />
          <path d={selectedGeometry.linePath} fill="none" stroke={selectedOption.stroke} strokeWidth="4" strokeLinecap="round" />

          {selectedGeometry.nodes.map((node) => (
            <g key={node.dateKey}>
              <title>{`${node.shortLabel} ${node.weekdayLabel} · ${metricLabel}：${formatLearningMetricValue(metric, node.metricValue)}`}</title>
              <line
                x1={node.x}
                x2={node.x}
                y1={selectedGeometry.baselineY}
                y2={Math.max(selectedGeometry.baselineY - node.columnHeight, node.y)}
                stroke={`${selectedOption.stroke}26`}
                strokeWidth="10"
                strokeLinecap="round"
              />
              <circle cx={node.x} cy={node.y} r="6.5" fill="var(--theme-subtle-bg)" stroke={selectedOption.stroke} strokeWidth="3" />
            </g>
          ))}

          {xAxisTickIndices.map((index) => {
            const node = selectedGeometry.nodes[index]
            if (!node) return null
            return (
              <g key={`axis-${node.dateKey}`}>
                <line x1={node.x} x2={node.x} y1={selectedGeometry.baselineY} y2={selectedGeometry.baselineY + 6} stroke="var(--theme-soft-border)" />
                <text x={node.x} y={chartHeight - 8} textAnchor="middle" fontSize="11" fill="var(--theme-subtle-text)">
                  {node.shortLabel}
                </text>
              </g>
            )
          })}
        </svg>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricStatCard label="日均" value={formatLearningMetricAverage(metric, stats.average)} detail="当前范围平均值" />
        <MetricStatCard
          label="峰值日"
          value={stats.peakEntry ? stats.peakEntry.point.shortLabel : "暂无"}
          detail={
            stats.peakEntry
              ? `${stats.peakEntry.point.weekdayLabel} · ${formatLearningMetricValue(metric, stats.peakEntry.value)}`
              : "当前范围还没有活跃记录"
          }
        />
        <MetricStatCard label="活跃天数" value={`${stats.activeDays} 天`} detail="当前范围有记录的天数" />
        <MetricStatCard label="稳定指数" value={formatLearningMetricVariance(stats.stability)} detail="活跃日方差" />
      </div>
    </div>
  )
}

export function ProfilePage() {
  const avatarInputRef = useRef<HTMLInputElement | null>(null)
  const profileQ = useMyProfile()
  const projectsQ = useProjects()
  const capabilitiesQ = useSystemCapabilities()
  const updateProfile = useUpdateMyProfile()
  const changePassword = useChangeMyPassword()
  const uploadAvatar = useUploadMyAvatar()

  const [selectedLearningProjectId, setSelectedLearningProjectId] = useState("all")
  const [selectedLearningMetric, setSelectedLearningMetric] = useState<LearningMetric>("effective")
  const [selectedLearningRange, setSelectedLearningRange] = useState<LearningRange>("week")
  const [isProfileEditing, setIsProfileEditing] = useState(false)
  const [profileDraft, setProfileDraft] = useState<ProfileDraft | null>(null)
  const [isPasswordEditing, setIsPasswordEditing] = useState(false)
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [studyMetricSyncRevision, setStudyMetricSyncRevision] = useState(0)

  const profile = profileQ.data ?? null
  const activeProjects = useMemo(() => (projectsQ.data ?? []).filter((project) => project.state !== "DELETED"), [projectsQ.data])
  const auditLogQs = useQueries({
    queries: activeProjects.map((project) => ({
      queryKey: ["auditLogEvents", project.projectId],
      queryFn: () => listAuditLogEvents(project.projectId),
      enabled: !projectsQ.isLoading && !projectsQ.error,
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    })),
  })
  const nickname = profileDraft?.nickname ?? profile?.nickname ?? ""
  const bio = profileDraft?.bio ?? profile?.bio ?? ""
  const bioRemaining = 120 - bio.length
  const isProfileDirty = Boolean(
    isProfileEditing &&
      profileDraft &&
      (profileDraft.nickname.trim() !== (profile?.nickname ?? "").trim() || profileDraft.bio !== (profile?.bio ?? "")),
  )
  const hasPasswordInput = currentPassword.trim().length > 0 || newPassword.trim().length > 0
  const isSaving = updateProfile.isPending || changePassword.isPending
  const effectiveSelectedLearningProjectId =
    selectedLearningProjectId === "all" || activeProjects.some((project) => project.projectId === selectedLearningProjectId)
      ? selectedLearningProjectId
      : "all"

  const successfulStudyEventsByProjectId = useMemo<Record<string, AuditLogEvent[]>>(() => {
    const eventsByProjectId: Record<string, AuditLogEvent[]> = {}
    activeProjects.forEach((project, index) => {
      eventsByProjectId[project.projectId] = (auditLogQs[index]?.data ?? []).filter(isSuccessfulStudyEvent)
    })
    return eventsByProjectId
  }, [activeProjects, auditLogQs])

  const selectedLearningProjectIds = useMemo(
    () => (effectiveSelectedLearningProjectId === "all" ? activeProjects.map((project) => project.projectId) : [effectiveSelectedLearningProjectId]),
    [activeProjects, effectiveSelectedLearningProjectId],
  )

  const selectedStudyMetricWindow = useMemo(() => {
    if (selectedLearningRange === "week") {
      const dateKeys = buildRecentDateKeys(7)
      return { dateFrom: dateKeys[0], dateTo: dateKeys[dateKeys.length - 1] }
    }
    if (selectedLearningRange === "month") {
      const dateKeys = buildRecentDateKeys(30)
      return { dateFrom: dateKeys[0], dateTo: dateKeys[dateKeys.length - 1] }
    }
    return { dateFrom: undefined, dateTo: undefined }
  }, [selectedLearningRange])

  useEffect(() => {
    if (!capabilitiesQ.data?.authEnabled) return
    if (selectedLearningProjectIds.length === 0) return

    let cancelled = false

    async function runStudyMetricsSync() {
      try {
        await syncStudyMetricsSnapshot({
          projectIds: selectedLearningProjectIds,
          dateFrom: selectedStudyMetricWindow.dateFrom,
          dateTo: selectedStudyMetricWindow.dateTo,
        })
        if (!cancelled) {
          setStudyMetricSyncRevision((current) => current + 1)
        }
      } catch {
        // Keep the profile page readable when hosted sync is temporarily unavailable.
      }
    }

    void runStudyMetricsSync()
    return () => {
      cancelled = true
    }
  }, [capabilitiesQ.data?.authEnabled, selectedLearningProjectIds, selectedStudyMetricWindow])

  const selectedStudyEvents = useMemo(
    () => selectedLearningProjectIds.flatMap((projectId) => successfulStudyEventsByProjectId[projectId] ?? []),
    [selectedLearningProjectIds, successfulStudyEventsByProjectId],
  )

  const selectedStudyTotalsByDate = useMemo(
    () => loadDailyStudyTotalsByDate(selectedLearningProjectIds),
    [selectedLearningProjectIds, studyMetricSyncRevision],
  )

  const selectedActionCountsByDate = useMemo(() => {
    const learningByDate: Record<string, number> = {}
    const reviewByDate: Record<string, number> = {}

    for (const event of selectedStudyEvents) {
      const dateKey = getLocalDateKey(new Date(event.occurredAt))
      if (isLearningSubmitEvent(event)) {
        learningByDate[dateKey] = (learningByDate[dateKey] ?? 0) + 1
      } else if (isReviewCommitEvent(event)) {
        reviewByDate[dateKey] = (reviewByDate[dateKey] ?? 0) + 1
      }
    }

    return { learningByDate, reviewByDate }
  }, [selectedStudyEvents])

  const visibleDateKeys = useMemo(() => {
    if (selectedLearningRange === "week") return buildRecentDateKeys(7)
    if (selectedLearningRange === "month") return buildRecentDateKeys(30)

    const earliestDateKey = [
      ...Object.keys(selectedStudyTotalsByDate),
      ...Object.keys(selectedActionCountsByDate.learningByDate),
      ...Object.keys(selectedActionCountsByDate.reviewByDate),
    ]
      .filter(Boolean)
      .sort()[0]

    return buildDateKeySpan(earliestDateKey ?? getLocalDateKey())
  }, [selectedActionCountsByDate, selectedLearningRange, selectedStudyTotalsByDate])

  const recentSeries = useMemo<DailyStatPoint[]>(
    () =>
      visibleDateKeys.map((dateKey) => {
        const learningCount = selectedActionCountsByDate.learningByDate[dateKey] ?? 0
        const reviewCount = selectedActionCountsByDate.reviewByDate[dateKey] ?? 0
        return {
          dateKey,
          shortLabel: formatDateKeyShortLabel(dateKey),
          weekdayLabel: formatDateKeyWeekdayLabel(dateKey),
          effectiveMs: selectedStudyTotalsByDate[dateKey]?.effectiveMs ?? 0,
          watchMs: selectedStudyTotalsByDate[dateKey]?.watchMs ?? 0,
          composeMs: selectedStudyTotalsByDate[dateKey]?.composeMs ?? 0,
          reviewMs: selectedStudyTotalsByDate[dateKey]?.reviewMs ?? 0,
          qaMs: selectedStudyTotalsByDate[dateKey]?.qaMs ?? 0,
          learningCount,
          reviewCount,
          totalActions: learningCount + reviewCount,
        }
      }),
    [selectedActionCountsByDate, selectedStudyTotalsByDate, visibleDateKeys],
  )

  const learningViewLoading = projectsQ.isLoading || auditLogQs.some((query) => query.isLoading)
  const learningViewError = projectsQ.error ?? auditLogQs.find((query) => query.error)?.error ?? null

  function openProfileEditor() {
    if (!profile) return
    setIsProfileEditing(true)
    setProfileDraft((current) =>
      current ?? {
        nickname: profile.nickname,
        bio: profile.bio,
      },
    )
  }

  function updateDraft(field: keyof ProfileDraft, value: string) {
    if (!profile) return
    setProfileDraft((current) => ({
      nickname: current?.nickname ?? profile.nickname,
      bio: current?.bio ?? profile.bio,
      [field]: value,
    }))
  }

  function onProfileFieldKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return
    event.preventDefault()
    void onSaveChanges()
  }

  function resetProfileEditor() {
    setIsProfileEditing(false)
    setProfileDraft(null)
  }

  function resetPasswordEditor() {
    setIsPasswordEditing(false)
    setCurrentPassword("")
    setNewPassword("")
  }

  function cancelEdits() {
    resetProfileEditor()
    resetPasswordEditor()
  }

  async function onSaveChanges() {
    const trimmedNickname = nickname.trim()
    if (isProfileEditing && !trimmedNickname) {
      showErrorFeedback("昵称不能为空", "请先填写一个可展示的昵称。")
      return
    }

    if (isPasswordEditing && hasPasswordInput && (!currentPassword.trim() || !newPassword.trim())) {
      showErrorFeedback("密码填写不完整", "修改密码时需要同时填写当前密码和新密码。")
      return
    }

    let savedProfile = false
    let changedPassword = false

    if (isProfileDirty) {
      try {
        await updateProfile.mutateAsync({ nickname: trimmedNickname, bio })
        savedProfile = true
        resetProfileEditor()
      } catch (err) {
        showErrorFeedback("保存资料失败", formatApiError(err))
        return
      }
    } else if (isProfileEditing) {
      resetProfileEditor()
    }

    if (isPasswordEditing && hasPasswordInput) {
      try {
        await changePassword.mutateAsync({ currentPassword, newPassword })
        changedPassword = true
        resetPasswordEditor()
      } catch (err) {
        showErrorFeedback("修改密码失败", formatApiError(err))
        return
      }
    } else if (isPasswordEditing) {
      resetPasswordEditor()
    }

    if (!savedProfile && !changedPassword) return

    if (savedProfile && changedPassword) {
      showSuccessFeedback("个人资料已更新", "昵称、自我描述和密码都已经保存。")
      return
    }

    if (savedProfile) {
      showSuccessFeedback("资料已更新", "昵称和自我描述已经保存。")
      return
    }

    showSuccessFeedback("密码已更新", "当前设备上的会话会继续保留，其他设备需要重新登录。")
  }

  async function onSelectAvatar(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (!file) return
    try {
      await uploadAvatar.mutateAsync(file)
      showSuccessFeedback("头像已更新", "新的头像已经上传完成。")
    } catch (err) {
      showErrorFeedback("上传头像失败", formatApiError(err))
    }
  }

  if (profileQ.isLoading) {
    return <LoadingNotice title="正在加载个人资料" message="稍等一下，我们正在准备你的账号信息。" />
  }

  if (profileQ.error || !profile) {
    return <ErrorNotice title="个人资料加载失败" message={formatApiError(profileQ.error)} />
  }

  return (
    <div className="mx-auto max-w-6xl">
      <div className="grid gap-6 xl:grid-cols-[minmax(21rem,25rem)_minmax(0,1fr)] xl:items-start">
        <section className="order-2 xl:order-2">
          <div className="space-y-6">
            <div className="theme-card-main overflow-hidden">
              <div className="theme-card-header px-6 py-5">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                  <div>
                    <div className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--theme-subtle-text)]">Learning View</div>
                    <div className="mt-2 flex items-center gap-2 text-2xl font-semibold tracking-tight text-foreground">
                      <Activity className="h-5 w-5 text-primary" />
                      学习视图
                    </div>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-3">
                    <LearningViewSelect
                      id="learning-project-scope"
                      label="项目"
                      value={effectiveSelectedLearningProjectId}
                      disabled={learningViewLoading}
                      onChange={setSelectedLearningProjectId}
                      options={[
                        { value: "all", label: "总视图" },
                        ...activeProjects.map((project) => ({
                          value: project.projectId,
                          label: project.title,
                        })),
                      ]}
                    />
                    <LearningViewSelect
                      id="learning-range-scope"
                      label="范围"
                      value={selectedLearningRange}
                      disabled={learningViewLoading}
                      onChange={(value) => setSelectedLearningRange(value as LearningRange)}
                      options={learningRangeOptions}
                    />
                    <LearningViewSelect
                      id="learning-metric-scope"
                      label="指标"
                      value={selectedLearningMetric}
                      disabled={learningViewLoading}
                      onChange={(value) => setSelectedLearningMetric(value as LearningMetric)}
                      options={learningMetricOptions.map((option) => ({
                        value: option.value,
                        label: option.label,
                      }))}
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-5 px-6 py-6">
                {learningViewError ? (
                  <div className="theme-warm-surface rounded-[1.3rem] px-4 py-3 text-sm leading-6">
                    学习视图加载失败：{formatApiError(learningViewError)}
                  </div>
                ) : null}

                {!learningViewError && learningViewLoading ? (
                  <div className="theme-subtle-surface rounded-[1.4rem] border-dashed px-5 py-10 text-center text-sm text-[color:var(--theme-subtle-text)]">
                    正在整理最近 7 天的学习视图。
                  </div>
                ) : null}

                {!learningViewError && !learningViewLoading && activeProjects.length === 0 ? (
                  <div className="theme-subtle-surface rounded-[1.4rem] border-dashed px-5 py-10 text-center text-sm text-[color:var(--theme-subtle-text)]">
                    还没有可统计的项目。创建项目后，这里会提供总视图和项目视图。
                  </div>
                ) : null}

                {!learningViewError && !learningViewLoading && activeProjects.length > 0 ? (
                  <LearningCurve
                    points={recentSeries}
                    metric={selectedLearningMetric}
                    range={selectedLearningRange}
                    onSelectMetric={setSelectedLearningMetric}
                  />
                ) : null}
              </div>
            </div>
          </div>
        </section>

        <aside className="order-1 xl:order-1 xl:sticky xl:top-28 xl:self-start">
          <div className="theme-card-main overflow-hidden">
            <div className="theme-card-header px-6 py-5">
              <div className="flex items-start gap-4">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--theme-subtle-text)]">Profile Card</div>
                  <div className="mt-2 text-2xl font-semibold tracking-tight text-foreground">账户信息</div>
                </div>
              </div>
            </div>

            <div className="space-y-6 px-6 py-6">
              <div className="theme-soft-surface rounded-[1.8rem] p-5">
                <div className="flex items-start gap-4">
                  <input ref={avatarInputRef} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={onSelectAvatar} />
                  <button
                    type="button"
                    onClick={() => avatarInputRef.current?.click()}
                    disabled={uploadAvatar.isPending}
                    className="group relative flex h-24 w-24 shrink-0 items-center justify-center overflow-hidden rounded-[1.7rem] border border-[color:var(--theme-subtle-border)] bg-[color:var(--theme-subtle-bg)] text-3xl font-semibold text-[color:var(--theme-subtle-text)] transition hover:border-primary/20 hover:shadow-[var(--theme-soft-shadow)] disabled:cursor-wait"
                    aria-label={uploadAvatar.isPending ? "头像上传中" : "点击修改头像"}
                    title={uploadAvatar.isPending ? "头像上传中..." : "点击修改头像"}
                  >
                    {profile.avatarUrl ? (
                      <img src={profile.avatarUrl} alt={profile.nickname} className="h-full w-full object-cover" />
                    ) : (
                      (profile.nickname || profile.email).slice(0, 1).toUpperCase()
                    )}
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-foreground/0 text-background opacity-0 transition group-hover:bg-foreground/50 group-hover:opacity-100">
                      <Camera className="h-4 w-4" />
                      <span className="mt-1 text-[11px] font-medium">{uploadAvatar.isPending ? "上传中..." : "修改头像"}</span>
                    </div>
                  </button>
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        {isProfileEditing ? (
                          <Input
                            value={nickname}
                            onChange={(event) => updateDraft("nickname", event.target.value)}
                            onKeyDown={onProfileFieldKeyDown}
                            maxLength={40}
                            className="inline-flex h-auto min-w-[8rem] max-w-full rounded-none border-0 bg-transparent px-0 py-0 text-2xl font-semibold tracking-tight text-foreground shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
                          />
                        ) : (
                          <div className="truncate text-2xl font-semibold tracking-tight text-foreground">{nickname || "未设置昵称"}</div>
                        )}
                        <div className="mt-2 font-mono text-sm font-medium text-[color:var(--theme-subtle-text)]">UID {profile.publicUid}</div>
                        <div className="mt-1 whitespace-nowrap text-sm leading-6 text-muted-foreground">
                          注册时间 {formatDateTimeLabel(profile.createdAt).split(" ")[0]}
                        </div>
                        <div className="mt-4">
                          <Button asChild size="sm" className="w-fit">
                            <Link to="/membership">
                              进入会员中心
                              <ArrowRight className="h-4 w-4" />
                            </Link>
                          </Button>
                        </div>
                      </div>
                      {!isProfileEditing ? (
                        <Button type="button" size="sm" variant="outline" className="shrink-0 rounded-full" onClick={openProfileEditor}>
                          修改昵称
                        </Button>
                      ) : (
                        <span className="theme-meta shrink-0">正在编辑</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <div className="theme-soft-surface rounded-[1.4rem] p-4">
                  <div className="flex items-center gap-3">
                    <div className="theme-icon-surface h-10 w-10">
                      <Mail className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">邮箱</div>
                      <div className="mt-1 truncate text-sm font-medium text-foreground">{profile.email}</div>
                    </div>
                  </div>
                </div>

                <div className="theme-soft-surface rounded-[1.4rem] p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <div className="theme-icon-surface mt-0.5 h-10 w-10">
                        <KeyRound className="h-4 w-4" />
                      </div>
                      <div className="min-w-0">
                        <div className="text-xs uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">密码</div>
                        {!isPasswordEditing ? (
                          <div className="mt-1 text-sm font-medium tracking-[0.22em] text-foreground">••••••••</div>
                        ) : (
                          <div className="mt-3 grid gap-3">
                            <div className="space-y-1.5">
                              <Label htmlFor="current-password">当前密码</Label>
                              <Input
                                id="current-password"
                                type="password"
                                value={currentPassword}
                                onChange={(event) => setCurrentPassword(event.target.value)}
                                className="border-[color:var(--theme-subtle-border)] bg-[color:var(--theme-subtle-bg)]"
                              />
                            </div>
                            <div className="space-y-1.5">
                              <Label htmlFor="new-password">新密码</Label>
                              <Input
                                id="new-password"
                                type="password"
                                value={newPassword}
                                onChange={(event) => setNewPassword(event.target.value)}
                                className="border-[color:var(--theme-subtle-border)] bg-[color:var(--theme-subtle-bg)]"
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                    {!isPasswordEditing ? (
                      <Button type="button" size="sm" variant="ghost" onClick={() => setIsPasswordEditing(true)}>
                        修改
                      </Button>
                    ) : null}
                  </div>
                </div>
              </div>

              <div className="space-y-4 pt-1">
                <div className="flex items-center justify-between gap-4">
                  <div className="text-xs uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">自我描述</div>
                  {!isProfileEditing ? (
                    <Button type="button" size="sm" variant="ghost" onClick={openProfileEditor}>
                      编辑
                    </Button>
                  ) : null}
                </div>

                {isProfileEditing ? (
                  <div className="mt-4 space-y-2">
                    <textarea
                      value={bio}
                      onChange={(event) => updateDraft("bio", event.target.value.slice(0, 120))}
                      maxLength={120}
                      className="min-h-32 w-full rounded-[1.2rem] border border-[color:var(--theme-subtle-border)] bg-[color:var(--theme-subtle-bg)] px-4 py-3 text-sm leading-6 text-foreground outline-none transition focus-visible:ring-2 focus-visible:ring-ring"
                      placeholder="写一点你的学习方向、偏好的项目类型，或者现在最想攻克的内容。"
                    />
                    <div className={cn("text-right text-xs", bioRemaining < 0 ? "text-destructive" : "text-[color:var(--theme-subtle-text)]")}>
                      还可输入 {Math.max(0, bioRemaining)} 字
                    </div>
                  </div>
                ) : (
                  <div className="theme-subtle-surface mt-4 rounded-[1.2rem] border-dashed px-4 py-4 text-sm leading-7 text-[color:var(--theme-subtle-text)]">
                    {profile.bio.trim() || "还没有留下自我描述。"}
                  </div>
                )}
              </div>

              {isProfileEditing || isPasswordEditing ? (
                <div className="flex items-center justify-end gap-3 border-t border-border/60 pt-2">
                  <Button type="button" variant="ghost" onClick={cancelEdits} disabled={isSaving}>
                    取消
                  </Button>
                  <Button type="button" onClick={() => void onSaveChanges()} disabled={isSaving || (!isProfileDirty && !hasPasswordInput)}>
                    <Save className="h-4 w-4" />
                    {isSaving ? "保存中..." : "保存更改"}
                  </Button>
                </div>
              ) : null}
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
