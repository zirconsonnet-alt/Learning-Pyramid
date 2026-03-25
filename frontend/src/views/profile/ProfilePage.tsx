import { type ChangeEvent, type ComponentType, useMemo, useRef, useState } from "react"
import { useQueries } from "@tanstack/react-query"
import {
  Activity,
  BookCopy,
  Camera,
  Clock3,
  Flame,
  FolderKanban,
  KeyRound,
  Mail,
  PenLine,
  Save,
  ShieldCheck,
} from "lucide-react"

import { listAuditLogEvents } from "@/ui/api/auditLog"
import { ApiError } from "@/ui/api/http"
import { ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useProjects } from "@/ui/queries/projects"
import { useChangeMyPassword, useMyProfile, useUpdateMyProfile, useUploadMyAvatar } from "@/ui/queries/profile"
import { getLocalDateKey, loadDailyPlaybackTotalsByDate } from "@/ui/store/workbenchDailyStats"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"

import {
  buildCurveGeometry,
  buildRecentDateKeys,
  formatDateTimeLabel,
  formatDurationCompact,
  formatLastStudyText,
  getLastStudyAt,
  isLearningSubmitEvent,
  isReviewCommitEvent,
  isSuccessfulStudyEvent,
  type DailyStatPoint,
  type ProjectActivitySnapshot,
} from "./profileStats"

type ProfileDraft = {
  nickname: string
  bio: string
}

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function StatTile({
  icon: Icon,
  label,
  value,
  hint,
}: {
  icon: ComponentType<{ className?: string }>
  label: string
  value: string
  hint: string
}) {
  return (
    <div className="rounded-[1.4rem] border border-[#d6e2ee] bg-white/86 p-4 shadow-[0_16px_36px_-30px_rgba(15,23,42,0.28)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[11px] uppercase tracking-[0.14em] text-[#7a8ca3]">{label}</div>
          <div className="mt-2 text-[1.7rem] font-semibold tracking-tight text-[#17324d]">{value}</div>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[#dbe6f1] bg-[#f5f9fd] text-[#406489]">
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <div className="mt-2 text-sm leading-6 text-[#6f8195]">{hint}</div>
    </div>
  )
}

function LearningCurve({
  points,
  totalPlaybackMs,
  totalActions,
}: {
  points: DailyStatPoint[]
  totalPlaybackMs: number
  totalActions: number
}) {
  const chartWidth = 640
  const chartHeight = 220
  const geometry = buildCurveGeometry(points, chartWidth, chartHeight)

  return (
    <div className="rounded-[1.6rem] border border-[#d4e0ec] bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(245,250,255,0.88))] p-5 shadow-[0_18px_40px_-34px_rgba(20,58,101,0.28)]">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-[#7286a0]">近 7 天学习曲线</div>
          <div className="mt-2 text-2xl font-semibold tracking-tight text-[#16314c]">{formatDurationCompact(totalPlaybackMs)}</div>
          <div className="mt-1 text-sm text-[#6d7f95]">过去 7 天的学习时长来自工作台回放统计，下面这条线按每天的学习时长绘制。</div>
        </div>
        <div className="grid min-w-[10rem] gap-2 text-right">
          <div>
            <div className="text-[11px] uppercase tracking-[0.14em] text-[#8a9ab0]">最高单日</div>
            <div className="mt-1 text-base font-semibold text-[#213c57]">
              {formatDurationCompact(Math.max(...points.map((point) => point.playbackMs), 0))}
            </div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-[0.14em] text-[#8a9ab0]">近 7 天动作</div>
            <div className="mt-1 text-base font-semibold text-[#213c57]">{totalActions} 次</div>
          </div>
        </div>
      </div>

      <div className="mt-5 overflow-hidden rounded-[1.4rem] border border-[#dbe5ef] bg-white/90 px-3 py-4">
        <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="h-56 w-full" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="profile-curve-fill" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="rgba(56,149,255,0.34)" />
              <stop offset="100%" stopColor="rgba(56,149,255,0.04)" />
            </linearGradient>
            <linearGradient id="profile-curve-line" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#3b82f6" />
              <stop offset="100%" stopColor="#38bdf8" />
            </linearGradient>
          </defs>

          {geometry.gridLines.map((lineY, index) => (
            <line
              key={`grid-${index}`}
              x1="16"
              x2={chartWidth - 16}
              y1={lineY}
              y2={lineY}
              stroke="rgba(148, 163, 184, 0.18)"
              strokeDasharray="6 8"
            />
          ))}

          <path d={geometry.areaPath} fill="url(#profile-curve-fill)" />
          <path d={geometry.linePath} fill="none" stroke="url(#profile-curve-line)" strokeWidth="4" strokeLinecap="round" />

          {geometry.nodes.map((node) => (
            <g key={node.dateKey}>
              <line
                x1={node.x}
                x2={node.x}
                y1={geometry.baselineY}
                y2={Math.max(geometry.baselineY - node.columnHeight, node.y)}
                stroke="rgba(59,130,246,0.14)"
                strokeWidth="10"
                strokeLinecap="round"
              />
              <circle cx={node.x} cy={node.y} r="6.5" fill="#ffffff" stroke="#2f7ef7" strokeWidth="3" />
            </g>
          ))}
        </svg>

        <div className="mt-3 grid grid-cols-7 gap-2">
          {points.map((point) => (
            <div key={point.dateKey} className="rounded-2xl bg-[#f6f9fc] px-2 py-2 text-center">
              <div className="text-[10px] uppercase tracking-[0.08em] text-[#7b8da4]">{point.shortLabel}</div>
              <div className="mt-1 text-[11px] text-[#93a2b5]">{point.weekdayLabel}</div>
              <div className="mt-2 text-xs font-semibold text-[#21405f]">{formatDurationCompact(point.playbackMs)}</div>
              <div className="mt-1 text-[11px] text-[#718398]">{point.totalActions} 次动作</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export function ProfilePage() {
  const avatarInputRef = useRef<HTMLInputElement | null>(null)
  const profileQ = useMyProfile()
  const projectsQ = useProjects()
  const updateProfile = useUpdateMyProfile()
  const changePassword = useChangeMyPassword()
  const uploadAvatar = useUploadMyAvatar()

  const [isProfileEditing, setIsProfileEditing] = useState(false)
  const [profileDraft, setProfileDraft] = useState<ProfileDraft | null>(null)
  const [isPasswordEditing, setIsPasswordEditing] = useState(false)
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")

  const profile = profileQ.data ?? null
  const projects = useMemo(() => projectsQ.data ?? [], [projectsQ.data])
  const auditLogQs = useQueries({
    queries: projects.map((project) => ({
      queryKey: ["auditLogEvents", project.projectId],
      queryFn: () => listAuditLogEvents(project.projectId),
      enabled: !projectsQ.isLoading && !projectsQ.error,
      staleTime: 60_000,
      refetchInterval: 60_000,
    })),
  })

  const recentDateKeys = useMemo(() => buildRecentDateKeys(7), [])
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

  const projectActivitySnapshots = useMemo<ProjectActivitySnapshot[]>(() => {
    return projects
      .map((project, index) => {
        const successfulEvents = (auditLogQs[index]?.data ?? []).filter(isSuccessfulStudyEvent)
        const learningCount = successfulEvents.filter(isLearningSubmitEvent).length
        const reviewCount = successfulEvents.filter(isReviewCommitEvent).length
        return {
          projectId: project.projectId,
          title: project.title,
          state: project.state,
          learningCount,
          reviewCount,
          totalActions: learningCount + reviewCount,
          lastStudyAt: getLastStudyAt(successfulEvents),
        }
      })
      .sort((left, right) => {
        const leftTime = left.lastStudyAt ? Date.parse(left.lastStudyAt) : 0
        const rightTime = right.lastStudyAt ? Date.parse(right.lastStudyAt) : 0
        return rightTime - leftTime
      })
  }, [auditLogQs, projects])

  const allStudyEvents = useMemo(
    () => auditLogQs.flatMap((query) => (query.data ?? []).filter(isSuccessfulStudyEvent)),
    [auditLogQs],
  )

  const playbackTotalsByDate = useMemo(
    () => loadDailyPlaybackTotalsByDate(projects.map((project) => project.projectId)),
    [projects],
  )

  const recentActionCountsByDate = useMemo(() => {
    const learningByDate: Record<string, number> = {}
    const reviewByDate: Record<string, number> = {}

    for (const event of allStudyEvents) {
      const dateKey = getLocalDateKey(new Date(event.occurredAt))
      if (isLearningSubmitEvent(event)) {
        learningByDate[dateKey] = (learningByDate[dateKey] ?? 0) + 1
      } else if (isReviewCommitEvent(event)) {
        reviewByDate[dateKey] = (reviewByDate[dateKey] ?? 0) + 1
      }
    }

    return { learningByDate, reviewByDate }
  }, [allStudyEvents])

  const recentSeries = useMemo<DailyStatPoint[]>(() => {
    return recentDateKeys.map((dateKey) => {
      const learningCount = recentActionCountsByDate.learningByDate[dateKey] ?? 0
      const reviewCount = recentActionCountsByDate.reviewByDate[dateKey] ?? 0
      const date = new Date(`${dateKey}T00:00:00`)
      return {
        dateKey,
        shortLabel: `${date.getMonth() + 1}.${date.getDate()}`,
        weekdayLabel: date.toLocaleDateString("zh-CN", { weekday: "short" }),
        playbackMs: playbackTotalsByDate[dateKey] ?? 0,
        learningCount,
        reviewCount,
        totalActions: learningCount + reviewCount,
      }
    })
  }, [playbackTotalsByDate, recentActionCountsByDate.learningByDate, recentActionCountsByDate.reviewByDate, recentDateKeys])

  const activeDayKeys = useMemo(() => {
    const set = new Set<string>()
    for (const [dateKey, playbackMs] of Object.entries(playbackTotalsByDate)) {
      if (playbackMs > 0) set.add(dateKey)
    }
    for (const event of allStudyEvents) {
      set.add(getLocalDateKey(new Date(event.occurredAt)))
    }
    return set
  }, [allStudyEvents, playbackTotalsByDate])

  const streakDays = useMemo(() => {
    let streak = 0
    const cursor = new Date()
    cursor.setHours(0, 0, 0, 0)

    for (;;) {
      const dateKey = getLocalDateKey(cursor)
      if (!activeDayKeys.has(dateKey)) break
      streak += 1
      cursor.setDate(cursor.getDate() - 1)
    }

    return streak
  }, [activeDayKeys])

  const totalLearningCount = allStudyEvents.filter(isLearningSubmitEvent).length
  const totalReviewCount = allStudyEvents.filter(isReviewCommitEvent).length
  const totalRecentPlaybackMs = recentSeries.reduce((sum, point) => sum + point.playbackMs, 0)
  const totalRecentActions = recentSeries.reduce((sum, point) => sum + point.totalActions, 0)
  const recentLearningCount = recentSeries.reduce((sum, point) => sum + point.learningCount, 0)
  const recentReviewCount = recentSeries.reduce((sum, point) => sum + point.reviewCount, 0)
  const activeProjectCount = projects.filter((project) => project.state !== "DELETED").length
  const lastStudyAt = projectActivitySnapshots.find((item) => item.lastStudyAt)?.lastStudyAt ?? null
  const lastStudyDisplay = formatLastStudyText(lastStudyAt)
  const activityLoading = projectsQ.isLoading || auditLogQs.some((query) => query.isLoading)
  const activityError = projectsQ.error ?? auditLogQs.find((query) => query.error)?.error ?? null
  const overallActionCount = totalLearningCount + totalReviewCount
  const learningShare = overallActionCount > 0 ? Math.round((totalLearningCount / overallActionCount) * 100) : 0
  const reviewShare = overallActionCount > 0 ? Math.round((totalReviewCount / overallActionCount) * 100) : 0

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
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-[minmax(21rem,25rem)_minmax(0,1fr)] xl:items-start">
        <aside className="xl:sticky xl:top-28 xl:self-start">
          <div className="theme-card-main overflow-hidden">
            <div className="theme-card-header px-6 py-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-[11px] uppercase tracking-[0.18em] text-[#7a8ca3]">Profile Card</div>
                  <div className="mt-2 text-2xl font-semibold tracking-tight text-[#15314b]">账户信息</div>
                </div>
                <div className="theme-meta">{formatDateTimeLabel(profile.createdAt).split(" ")[0]}</div>
              </div>
            </div>

            <div className="space-y-6 px-6 py-6">
              <div className="rounded-[1.8rem] border border-[#d8e3ef] bg-[linear-gradient(135deg,rgba(255,255,255,0.94),rgba(241,247,253,0.84))] p-5 shadow-[0_20px_42px_-34px_rgba(20,58,101,0.32)]">
                <div className="flex items-start gap-4">
                  <input ref={avatarInputRef} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={onSelectAvatar} />
                  <button
                    type="button"
                    onClick={() => avatarInputRef.current?.click()}
                    disabled={uploadAvatar.isPending}
                    className="group relative flex h-24 w-24 shrink-0 items-center justify-center overflow-hidden rounded-[1.7rem] border border-[#d9e5f0] bg-[#eff5fb] text-3xl font-semibold text-[#587089] transition hover:border-[#bfd2e6] hover:shadow-[0_16px_30px_-24px_rgba(20,58,101,0.35)] disabled:cursor-wait"
                    aria-label={uploadAvatar.isPending ? "头像上传中" : "点击修改头像"}
                    title={uploadAvatar.isPending ? "头像上传中..." : "点击修改头像"}
                  >
                    {profile.avatarUrl ? (
                      <img src={profile.avatarUrl} alt={profile.nickname} className="h-full w-full object-cover" />
                    ) : (
                      (profile.nickname || profile.email).slice(0, 1).toUpperCase()
                    )}
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#18314b]/0 text-white opacity-0 transition group-hover:bg-[#18314b]/56 group-hover:opacity-100">
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
                            maxLength={40}
                            className="h-11 max-w-[16rem] border-[#d7e2ee] bg-white/92 text-[1.45rem] font-semibold tracking-tight text-[#17314b]"
                          />
                        ) : (
                          <div className="truncate text-2xl font-semibold tracking-tight text-[#16314d]">{nickname || "未设置昵称"}</div>
                        )}
                        <div className="mt-2 font-mono text-sm font-medium text-[#6a7f96]">UID {profile.publicUid}</div>
                      </div>
                      {!isProfileEditing ? (
                        <Button type="button" size="sm" variant="outline" className="shrink-0 rounded-full" onClick={openProfileEditor}>
                          修改昵称
                        </Button>
                      ) : (
                        <span className="theme-meta shrink-0">正在编辑</span>
                      )}
                    </div>
                    <div className="text-sm leading-6 text-[#6d8095]">个人主页会展示你的昵称、头像和自我描述，右侧则记录你的学习节奏。</div>
                    <div className="flex flex-wrap gap-2 pt-1">
                      <Button type="button" size="sm" variant="ghost" onClick={openProfileEditor}>
                        <PenLine className="h-3.5 w-3.5" />
                        编辑资料
                      </Button>
                    </div>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <div className="rounded-[1.4rem] border border-[#dbe4ee] bg-white/86 p-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[#dce6f0] bg-[#f4f8fc] text-[#53708e]">
                      <Mail className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs uppercase tracking-[0.14em] text-[#8a9ab0]">邮箱</div>
                      <div className="mt-1 truncate text-sm font-medium text-[#1e3a56]">{profile.email}</div>
                    </div>
                  </div>
                </div>

                <div className="rounded-[1.4rem] border border-[#dbe4ee] bg-white/86 p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-2xl border border-[#dce6f0] bg-[#f4f8fc] text-[#53708e]">
                        <KeyRound className="h-4 w-4" />
                      </div>
                      <div className="min-w-0">
                        <div className="text-xs uppercase tracking-[0.14em] text-[#8a9ab0]">密码</div>
                        {!isPasswordEditing ? (
                          <div className="mt-1 text-sm font-medium tracking-[0.22em] text-[#1e3a56]">••••••••</div>
                        ) : (
                          <div className="mt-3 grid gap-3">
                            <div className="space-y-1.5">
                              <Label htmlFor="current-password">当前密码</Label>
                              <Input id="current-password" type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} className="border-[#d7e2ee] bg-white/92" />
                            </div>
                            <div className="space-y-1.5">
                              <Label htmlFor="new-password">新密码</Label>
                              <Input id="new-password" type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} className="border-[#d7e2ee] bg-white/92" />
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
                  <div className="text-xs uppercase tracking-[0.14em] text-[#8a9ab0]">自我描述</div>
                  {!isProfileEditing ? (
                    <Button type="button" size="sm" variant="ghost" onClick={openProfileEditor}>
                      编辑
                    </Button>
                  ) : null}
                </div>

                {isProfileEditing ? (
                  <div className="mt-4 space-y-2">
                    <textarea value={bio} onChange={(event) => updateDraft("bio", event.target.value.slice(0, 120))} maxLength={120} className="min-h-32 w-full rounded-[1.2rem] border border-[#d7e2ee] bg-white/94 px-4 py-3 text-sm leading-6 text-[#17314b] outline-none transition focus-visible:ring-2 focus-visible:ring-ring" placeholder="写一点你的学习方向、偏好的材料类型，或者现在最想攻克的内容。" />
                    <div className={cn("text-right text-xs", bioRemaining < 0 ? "text-destructive" : "text-[#7a8da3]")}>还可输入 {Math.max(0, bioRemaining)} 字</div>
                  </div>
                ) : (
                  <div className="mt-4 rounded-[1.2rem] border border-dashed border-[#d8e2ee] bg-[#f7fafd] px-4 py-4 text-sm leading-7 text-[#334f6b]">
                    {profile.bio.trim() || "还没有留下自我描述。"}
                  </div>
                )}
              </div>

              {isProfileEditing || isPasswordEditing ? (
                <div className="flex items-center justify-end gap-3 border-t border-[#dce5ef] pt-2">
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

        <section className="theme-card-main overflow-hidden">
          <div className="theme-card-header px-6 py-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-[#7a8ca3]">Learning Mirror</div>
                <div className="mt-2 text-2xl font-semibold tracking-tight text-[#15314b]">学习统计</div>
                <div className="mt-2 max-w-2xl text-sm leading-6 text-[#6d8095]">这里改成和用户指南一致的页面级滚动，统计内容跟随页面自然展开。</div>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className="theme-meta">{activityLoading ? "统计同步中" : `${projects.length} 个项目`}</span>
                <span className={cn("theme-meta", lastStudyDisplay.className)}>{lastStudyDisplay.text}</span>
              </div>
            </div>
          </div>

          <div className="space-y-5 px-6 py-6">
            <div className="rounded-[1.8rem] border border-[#d5e0eb] bg-[radial-gradient(circle_at_top_left,rgba(115,163,255,0.16),transparent_42%),linear-gradient(135deg,rgba(255,255,255,0.96),rgba(241,247,253,0.88))] p-5 shadow-[0_22px_44px_-34px_rgba(20,58,101,0.28)]">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="space-y-2">
                  <span className="theme-meta-strong">当前节奏</span>
                  <div className="text-3xl font-semibold tracking-tight text-[#17324d]">{formatDurationCompact(totalRecentPlaybackMs)}</div>
                  <div className="text-sm leading-6 text-[#6e8096]">过去 7 天的学习时长来自工作台回放统计，历史提交来自每个项目的审计记录。</div>
                </div>
                <div className="grid min-w-[13rem] gap-3 sm:grid-cols-2">
                  <div className="rounded-[1.2rem] border border-[#d7e3ef] bg-white/84 px-4 py-3">
                    <div className="text-[11px] uppercase tracking-[0.14em] text-[#8a9ab0]">最近学习</div>
                    <div className="mt-1 text-sm font-semibold text-[#203c58]">{lastStudyAt ? formatDateTimeLabel(lastStudyAt) : "暂无记录"}</div>
                  </div>
                  <div className="rounded-[1.2rem] border border-[#d7e3ef] bg-white/84 px-4 py-3">
                    <div className="text-[11px] uppercase tracking-[0.14em] text-[#8a9ab0]">连续推进</div>
                    <div className="mt-1 text-sm font-semibold text-[#203c58]">{streakDays > 0 ? `${streakDays} 天` : "从今天开始"}</div>
                  </div>
                </div>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
              <StatTile icon={FolderKanban} label="学习项目" value={String(activeProjectCount)} hint="当前仍在运行中的项目数量。" />
              <StatTile icon={BookCopy} label="学习任务提交" value={String(totalLearningCount)} hint="累计正式提交到主闭环的学习任务次数。" />
              <StatTile icon={ShieldCheck} label="复习提交" value={String(totalReviewCount)} hint="累计正式完成的复习提交次数。" />
              <StatTile icon={Flame} label="连续学习" value={streakDays > 0 ? `${streakDays} 天` : "0 天"} hint="连续出现学习动作或学习时长的自然日。" />
            </div>

            <LearningCurve points={recentSeries} totalPlaybackMs={totalRecentPlaybackMs} totalActions={totalRecentActions} />

            <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)]">
              <div className="rounded-[1.6rem] border border-[#d4e0ec] bg-white/90 p-5 shadow-[0_18px_40px_-34px_rgba(20,58,101,0.28)]">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-[11px] uppercase tracking-[0.16em] text-[#7a8ca3]">最近活跃项目</div>
                    <div className="mt-1 text-lg font-semibold text-[#17324d]">最近在推进什么</div>
                  </div>
                  <div className="theme-meta">{projectActivitySnapshots.filter((item) => item.lastStudyAt).length} 个有记录</div>
                </div>
                {activityError ? (
                  <div className="mt-4 rounded-[1.2rem] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    统计加载失败：{formatApiError(activityError)}
                  </div>
                ) : null}

                <div className="mt-4 space-y-3">
                  {projectActivitySnapshots.slice(0, 6).map((item) => {
                    const lastStudy = formatLastStudyText(item.lastStudyAt)
                    return (
                      <div key={item.projectId} className="rounded-[1.25rem] border border-[#dbe4ee] bg-[#fbfdff] px-4 py-4 shadow-[0_12px_28px_-26px_rgba(15,23,42,0.3)]">
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div className="min-w-0">
                            <div className="truncate text-sm font-semibold text-[#1d3954]">{item.title}</div>
                            <div className="mt-1 text-xs text-[#7b8da3]">学习提交 {item.learningCount} 次 · 复习提交 {item.reviewCount} 次</div>
                          </div>
                          <span className={cn("text-xs font-medium", lastStudy.className)}>{lastStudy.text}</span>
                        </div>
                      </div>
                    )
                  })}

                  {projectActivitySnapshots.length === 0 && !activityLoading ? (
                    <div className="rounded-[1.25rem] border border-dashed border-[#d8e3ef] bg-[#f7fafd] px-4 py-6 text-sm leading-6 text-[#6e8197]">
                      还没有项目或学习动作。创建一个项目并开始录入复述点后，这里会出现最近的推进痕迹。
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="space-y-5">
                <div className="rounded-[1.6rem] border border-[#d4e0ec] bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(244,249,255,0.88))] p-5 shadow-[0_18px_40px_-34px_rgba(20,58,101,0.28)]">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[#dae4ef] bg-[#f6f9fc] text-[#4e7092]">
                      <Activity className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="text-[11px] uppercase tracking-[0.16em] text-[#7a8ca3]">学习动作分布</div>
                      <div className="mt-1 text-lg font-semibold text-[#17324d]">学习与复习的比例</div>
                    </div>
                  </div>

                  <div className="mt-4 space-y-4">
                    <div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-[#294867]">学习任务提交</span>
                        <span className="font-semibold text-[#17324d]">{learningShare}%</span>
                      </div>
                      <div className="mt-2 h-2.5 rounded-full bg-[#e6edf5]">
                        <div className="h-full rounded-full bg-[linear-gradient(90deg,#3b82f6,#38bdf8)]" style={{ width: `${learningShare}%` }} />
                      </div>
                    </div>

                    <div>
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-[#294867]">复习提交</span>
                        <span className="font-semibold text-[#17324d]">{reviewShare}%</span>
                      </div>
                      <div className="mt-2 h-2.5 rounded-full bg-[#e6edf5]">
                        <div className="h-full rounded-full bg-[linear-gradient(90deg,#0f766e,#2dd4bf)]" style={{ width: `${reviewShare}%` }} />
                      </div>
                    </div>
                  </div>
                </div>

                <div className="rounded-[1.6rem] border border-[#d4e0ec] bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(244,249,255,0.88))] p-5 shadow-[0_18px_40px_-34px_rgba(20,58,101,0.28)]">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[#dae4ef] bg-[#f6f9fc] text-[#4e7092]">
                      <Clock3 className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="text-[11px] uppercase tracking-[0.16em] text-[#7a8ca3]">近 7 天摘要</div>
                      <div className="mt-1 text-lg font-semibold text-[#17324d]">把最近一周压成四个数字</div>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <div className="rounded-[1.2rem] border border-[#dbe4ee] bg-white/84 px-4 py-3">
                      <div className="text-[11px] uppercase tracking-[0.14em] text-[#8a9ab0]">学习时长</div>
                      <div className="mt-1 text-base font-semibold text-[#203c58]">{formatDurationCompact(totalRecentPlaybackMs)}</div>
                    </div>
                    <div className="rounded-[1.2rem] border border-[#dbe4ee] bg-white/84 px-4 py-3">
                      <div className="text-[11px] uppercase tracking-[0.14em] text-[#8a9ab0]">学习提交</div>
                      <div className="mt-1 text-base font-semibold text-[#203c58]">{recentLearningCount} 次</div>
                    </div>
                    <div className="rounded-[1.2rem] border border-[#dbe4ee] bg-white/84 px-4 py-3">
                      <div className="text-[11px] uppercase tracking-[0.14em] text-[#8a9ab0]">复习提交</div>
                      <div className="mt-1 text-base font-semibold text-[#203c58]">{recentReviewCount} 次</div>
                    </div>
                    <div className="rounded-[1.2rem] border border-[#dbe4ee] bg-white/84 px-4 py-3">
                      <div className="text-[11px] uppercase tracking-[0.14em] text-[#8a9ab0]">账号建立</div>
                      <div className="mt-1 text-base font-semibold text-[#203c58]">{formatDateTimeLabel(profile.createdAt).split(" ")[0]}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
