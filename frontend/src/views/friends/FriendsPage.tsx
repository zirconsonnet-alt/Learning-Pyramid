import { type ReactNode, useMemo, useState } from "react"
import { Copy, Mail, Sparkles, Trophy, UserMinus, UserPlus } from "lucide-react"

import type { Friend, FriendLeaderboardEntry, FriendRequest } from "@/ui/api/friends"
import { ApiError } from "@/ui/api/http"
import { ContentEmptyState, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/ui/components/ui/dialog"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useCurrentUser } from "@/ui/queries/auth"
import {
  useAcceptFriendRequest,
  useCancelFriendRequest,
  useCreateFriendRequest,
  useDeleteFriend,
  useFriendLeaderboard,
  useFriendProfile,
  useFriendRequests,
  useFriends,
  useRejectFriendRequest,
} from "@/ui/queries/friends"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"
import { formatDateTimeLabel, formatDurationCompact, formatLastStudyText } from "@/views/profile/profileStats"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function FriendAvatar(props: { user: { avatarUrl: string | null; nickname: string }; size?: "md" | "lg" }) {
  const { user, size = "md" } = props
  const sizeClass = size === "lg" ? "h-16 w-16 rounded-3xl text-lg" : "h-12 w-12 rounded-2xl text-base"
  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center overflow-hidden border border-dashed border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] font-semibold text-[color:var(--theme-subtle-text)]",
        sizeClass,
      )}
    >
      {user.avatarUrl ? <img src={user.avatarUrl} alt={user.nickname} className="h-full w-full object-cover" /> : user.nickname.slice(0, 1).toUpperCase()}
    </div>
  )
}

function MetaTag(props: { children: ReactNode; tone?: "default" | "accent" | "danger" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs",
        props.tone === "accent"
          ? "border-primary/20 bg-primary/10 text-primary"
          : props.tone === "danger"
            ? "border-destructive/20 bg-destructive/10 text-destructive"
            : "border-[color:var(--theme-soft-border)] text-[color:var(--theme-subtle-text)]",
      )}
    >
      {props.children}
    </span>
  )
}

function StatCard(props: { label: string; value: ReactNode; detail?: string }) {
  return (
    <div className="rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3">
      <div className="text-xs uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">{props.label}</div>
      <div className="mt-2 text-xl font-semibold tracking-tight text-foreground">{props.value}</div>
      {props.detail ? <div className="mt-1 text-xs text-muted-foreground">{props.detail}</div> : null}
    </div>
  )
}

function SummaryChip(props: { label: string; value: ReactNode; tone?: "default" | "accent" }) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-2",
        props.tone === "accent"
          ? "border-primary/20 bg-primary/10 text-primary"
          : "border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] text-[color:var(--theme-subtle-text)]",
      )}
    >
      <span className="text-[11px] uppercase tracking-[0.12em]">{props.label}</span>
      <span className="text-sm font-semibold tracking-tight text-foreground">{props.value}</span>
    </div>
  )
}

type FriendRequestAction =
  | { kind: "accept"; requestId: string; nickname: string }
  | { kind: "reject"; requestId: string; nickname: string }
  | { kind: "cancel"; requestId: string; nickname: string }

export function FriendsPage() {
  const currentUserQ = useCurrentUser()
  const friendsQ = useFriends()
  const incomingRequestsQ = useFriendRequests("incoming")
  const outgoingRequestsQ = useFriendRequests("outgoing")
  const leaderboardQ = useFriendLeaderboard()
  const createRequest = useCreateFriendRequest()
  const acceptRequest = useAcceptFriendRequest()
  const rejectRequest = useRejectFriendRequest()
  const cancelRequest = useCancelFriendRequest()
  const deleteFriend = useDeleteFriend()

  const [filterText, setFilterText] = useState("")
  const [addOpen, setAddOpen] = useState(false)
  const [targetUid, setTargetUid] = useState("")
  const [requestMessage, setRequestMessage] = useState("")
  const [profileFriend, setProfileFriend] = useState<Friend | null>(null)

  const friendProfileQ = useFriendProfile(profileFriend?.userId, Boolean(profileFriend))
  const friends = useMemo(() => friendsQ.data ?? [], [friendsQ.data])
  const incomingRequests = useMemo(() => incomingRequestsQ.data ?? [], [incomingRequestsQ.data])
  const outgoingRequests = useMemo(() => outgoingRequestsQ.data ?? [], [outgoingRequestsQ.data])
  const incomingPendingRequests = incomingRequests.filter((item) => item.status === "pending")
  const outgoingPendingRequests = outgoingRequests.filter((item) => item.status === "pending")
  const incomingPendingCount = incomingPendingRequests.length
  const outgoingPendingCount = outgoingPendingRequests.length
  const filteredFriends = useMemo(() => {
    if (!filterText.trim()) return friends
    const needle = filterText.trim().toLowerCase()
    return friends.filter((friend) => {
      const text = `${friend.nickname} ${friend.publicUid} ${friend.bio ?? ""}`.toLowerCase()
      return text.includes(needle)
    })
  }, [filterText, friends])
  const hasFilterText = filterText.trim().length > 0
  const showPendingRequestsPanel =
    incomingRequestsQ.isLoading ||
    outgoingRequestsQ.isLoading ||
    Boolean(incomingRequestsQ.error) ||
    Boolean(outgoingRequestsQ.error) ||
    incomingPendingCount > 0 ||
    outgoingPendingCount > 0

  async function onCopyMyUid() {
    const publicUid = currentUserQ.data?.publicUid?.trim()
    if (!publicUid) {
      showErrorFeedback("暂时没有可复制的 UID", "请稍后重试，或去个人中心确认账号资料是否已经加载。")
      return
    }
    try {
      await navigator.clipboard.writeText(publicUid)
      showSuccessFeedback("UID 已复制", "现在可以把它直接发给想添加你的朋友。")
    } catch {
      showErrorFeedback("复制失败", "当前环境暂时不支持自动复制，请手动复制你的 UID。")
    }
  }

  async function onCreateFriendRequest() {
    const trimmedUid = targetUid.trim()
    if (!trimmedUid) {
      showErrorFeedback("请输入好友 UID", "例如 LP1A2B3C4D。")
      return
    }
    try {
      await createRequest.mutateAsync({ publicUid: trimmedUid, message: requestMessage.trim() })
      showSuccessFeedback("好友申请已发送", "对方同意后，你们就可以互看资料和学习统计。")
      setTargetUid("")
      setRequestMessage("")
      setAddOpen(false)
    } catch (err) {
      showErrorFeedback("发送好友申请失败", formatApiError(err))
    }
  }

  async function onRequestAction(action: FriendRequestAction) {
    try {
      if (action.kind === "accept") {
        await acceptRequest.mutateAsync(action.requestId)
        showSuccessFeedback("已同意好友申请", `${action.nickname} 现在是你的好友，可以互相查看资料。`)
      } else if (action.kind === "reject") {
        await rejectRequest.mutateAsync(action.requestId)
        showSuccessFeedback("已拒绝好友申请", `${action.nickname} 的请求已处理。`)
      } else {
        await cancelRequest.mutateAsync(action.requestId)
        showSuccessFeedback("申请已撤回", `${action.nickname} 将不会再看到这条好友申请。`)
      }
    } catch (err) {
      showErrorFeedback("操作失败", formatApiError(err))
    }
  }

  async function onDeleteFriend(friend: Friend) {
    if (!window.confirm(`确定要和 ${friend.nickname} 解除好友关系吗？`)) return
    try {
      await deleteFriend.mutateAsync(friend.userId)
      showSuccessFeedback("好友已解除", `${friend.nickname} 将不再出现在好友列表中。`)
      if (profileFriend?.userId === friend.userId) {
        setProfileFriend(null)
      }
    } catch (err) {
      showErrorFeedback("解除好友失败", formatApiError(err))
    }
  }

  const profileSummary = friendProfileQ.data ?? profileFriend

  return (
    <>
      <div className="grid gap-4">
        <Card className="theme-card-main overflow-hidden">
          <CardHeader className="theme-card-header gap-4 pb-4">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="space-y-1">
                <CardTitle className="text-2xl">好友中心</CardTitle>
              </div>
              <div className="flex w-full flex-col gap-3 sm:flex-row lg:w-auto">
                <div className="w-full sm:w-72">
                  <Input
                    value={filterText}
                    onChange={(event) => setFilterText(event.target.value)}
                    placeholder="按昵称 / UID / 简介搜索好友"
                    className="border-[color:var(--theme-soft-border)] [background:white] [box-shadow:none]"
                  />
                </div>
                <Button type="button" onClick={() => setAddOpen(true)} className="sm:self-end [box-shadow:none]">
                  <UserPlus className="h-4 w-4" />
                  添加好友
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            {showPendingRequestsPanel ? (
              <div className="rounded-[1.2rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-4 sm:px-5">
                <div className="space-y-1">
                  <div className="text-base font-semibold tracking-tight text-foreground">待处理申请</div>
                  <div className="text-sm text-muted-foreground">这里只展示还没处理完的申请，避免把页面拆成几张大卡片。</div>
                </div>
                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  <PendingRequestColumn
                    title="待我处理"
                    description="收到的申请"
                    requests={incomingPendingRequests}
                    loading={incomingRequestsQ.isLoading}
                    error={incomingRequestsQ.error}
                    emptyTitle="暂无需要处理的申请"
                    emptyMessage="朋友给你发来好友申请后，会直接出现在这里。"
                    primaryActionLabel="同意"
                    secondaryActionLabel="拒绝"
                    actionsDisabled={acceptRequest.isPending || rejectRequest.isPending}
                    onPrimaryAction={(item) => onRequestAction({ kind: "accept", requestId: item.requestId, nickname: item.user.nickname })}
                    onSecondaryAction={(item) => onRequestAction({ kind: "reject", requestId: item.requestId, nickname: item.user.nickname })}
                  />
                  <PendingRequestColumn
                    title="等待对方"
                    description="我发出的申请"
                    requests={outgoingPendingRequests}
                    loading={outgoingRequestsQ.isLoading}
                    error={outgoingRequestsQ.error}
                    emptyTitle="暂无等待中的申请"
                    emptyMessage="发送好友申请后，只要对方还没处理，就会显示在这里。"
                    primaryActionLabel="撤回申请"
                    actionsDisabled={cancelRequest.isPending}
                    onPrimaryAction={(item) => onRequestAction({ kind: "cancel", requestId: item.requestId, nickname: item.user.nickname })}
                  />
                </div>
              </div>
            ) : null}

            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-end gap-2">
                {hasFilterText ? <MetaTag>结果 {filteredFriends.length}</MetaTag> : null}
              </div>

              {friendsQ.isLoading ? <LoadingNotice title="正在加载好友列表" message="请稍候，正在同步你的好友关系。" /> : null}
              {friendsQ.error ? <ErrorNotice title="好友列表加载失败" message={formatApiError(friendsQ.error)} /> : null}

              {!friendsQ.isLoading && !friendsQ.error && filteredFriends.length === 0 ? (
                <ContentEmptyState
                  title={friends.length === 0 ? "暂时还没有好友" : "没有找到匹配的好友"}
                  message={friends.length === 0 ? "使用上方按钮发送好友申请，或把自己的 UID 发给朋友。" : hasFilterText ? "换个更短的关键词，或者直接按 UID 搜索试试。" : "当前列表为空。"}
                  icon={Sparkles}
                  className="rounded-[1.1rem] border-[color:var(--theme-soft-border)] bg-transparent"
                />
              ) : null}

              {filteredFriends.length > 0 ? (
                <div className="overflow-hidden rounded-[1.15rem] border border-[color:var(--theme-soft-border)]">
                  {filteredFriends.map((friend) => (
                    <div key={friend.userId} className="border-b border-[color:var(--theme-soft-border)] px-4 py-4 last:border-b-0 sm:px-5">
                      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                        <div className="flex min-w-0 flex-1 items-start gap-4">
                          <FriendAvatar user={friend} />
                          <div className="min-w-0 space-y-1.5">
                            <div className="flex flex-wrap items-center gap-2">
                              <div className="text-base font-semibold text-foreground">{friend.nickname}</div>
                              <MetaTag>好友于 {new Date(friend.friendedAt).toLocaleDateString()}</MetaTag>
                            </div>
                            <div className="text-sm text-muted-foreground">UID {friend.publicUid}</div>
                            <p className="text-sm leading-6 text-[color:var(--theme-subtle-text)]">{friend.bio?.trim() || "这个朋友还没有填写简介。"}</p>
                          </div>
                        </div>
                        <div className="flex shrink-0 flex-wrap gap-2">
                          <Button type="button" size="sm" variant="outline" onClick={() => setProfileFriend(friend)} className="[box-shadow:none]">
                            查看资料
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => onDeleteFriend(friend)}
                            disabled={deleteFriend.isPending}
                            className="text-muted-foreground hover:text-destructive"
                          >
                            <UserMinus className="h-4 w-4" />
                            解除好友
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="mt-4">
        <FriendLeaderboard entries={leaderboardQ.data ?? []} loading={leaderboardQ.isLoading} error={leaderboardQ.error} />
      </div>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-w-xl rounded-[1.75rem] border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-0">
          <DialogHeader className="border-b border-[color:var(--theme-soft-border)] px-6 py-5">
            <DialogTitle className="text-2xl tracking-tight text-foreground">添加好友</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 px-6 pb-6 pt-3">
            <div className="flex flex-wrap gap-2">
              <SummaryChip label="好友" value={friendsQ.isLoading ? "..." : friends.length} />
              <SummaryChip label="待我处理" value={incomingRequestsQ.isLoading ? "..." : incomingPendingCount} tone={incomingPendingCount > 0 ? "accent" : "default"} />
              <SummaryChip label="等待对方" value={outgoingRequestsQ.isLoading ? "..." : outgoingPendingCount} />
            </div>
            <div className="flex flex-col gap-3 rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0 space-y-1">
                <div className="text-xs uppercase tracking-[0.12em] text-[color:var(--theme-subtle-text)]">我的好友 UID</div>
                <div className="text-xl font-semibold tracking-tight text-foreground">{currentUserQ.data?.publicUid ?? "正在加载..."}</div>
              </div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => void onCopyMyUid()}
                disabled={!currentUserQ.data?.publicUid}
                className="self-start [box-shadow:none] sm:self-center"
              >
                <Copy className="h-4 w-4" />
                复制 UID
              </Button>
            </div>
            <div className="space-y-2">
              <Label htmlFor="friend-uid">好友 UID</Label>
              <Input
                id="friend-uid"
                value={targetUid}
                onChange={(event) => setTargetUid(event.target.value)}
                placeholder="例如 LP1A2B3C4D"
                autoFocus
                maxLength={40}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="friend-message">打个招呼（可选）</Label>
              <textarea
                id="friend-message"
                className="min-h-28 w-full rounded-xl border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] px-4 py-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
                value={requestMessage}
                onChange={(event) => setRequestMessage(event.target.value)}
                maxLength={200}
                placeholder="简单介绍自己，或者说明想一起学什么。"
              />
            </div>
            <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <Button type="button" variant="secondary" onClick={() => setAddOpen(false)} disabled={createRequest.isPending}>
                取消
              </Button>
              <Button type="button" onClick={() => void onCreateFriendRequest()} disabled={createRequest.isPending}>
                {createRequest.isPending ? "发送中..." : "发送好友申请"}
              </Button>
            </div>
            {createRequest.error ? <p className="text-sm text-destructive">{formatApiError(createRequest.error)}</p> : null}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(profileFriend)} onOpenChange={(open) => !open && setProfileFriend(null)}>
        <DialogContent className="max-w-2xl rounded-[1.75rem] border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-0">
          <DialogHeader className="border-b border-[color:var(--theme-soft-border)] px-6 py-5">
            <DialogTitle className="text-2xl tracking-tight text-foreground">好友资料</DialogTitle>
          </DialogHeader>
          {profileSummary ? (
            <div className="space-y-5 px-6 py-6">
              <div className="flex items-start gap-4">
                <FriendAvatar user={profileSummary} size="lg" />
                <div className="min-w-0 space-y-1">
                  <div className="text-xl font-semibold text-foreground">{profileSummary.nickname}</div>
                  <div className="text-sm text-muted-foreground">UID {profileSummary.publicUid}</div>
                  {profileFriend ? (
                    <div className="text-xs uppercase tracking-[0.2em] text-[color:var(--theme-subtle-text)]">
                      成为好友于 {formatDateTimeLabel(profileFriend.friendedAt)}
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="space-y-2">
                <Label>个人简介</Label>
                <div className="rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3 text-sm leading-6 text-[color:var(--theme-subtle-text)]">
                  {profileSummary.bio?.trim() || "暂未填写。"}
                </div>
              </div>

              {friendProfileQ.isLoading ? <LoadingNotice title="正在加载学习统计" message="马上就好..." /> : null}
              {friendProfileQ.error ? <ErrorNotice title="好友资料加载失败" message={formatApiError(friendProfileQ.error)} /> : null}

              {friendProfileQ.data ? (
                <>
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <StatCard label="活跃学习" value={formatDurationCompact(friendProfileQ.data.stats.effectiveMs)} detail="兼容历史学习统计" />
                    <StatCard label="视频观看" value={formatDurationCompact(friendProfileQ.data.stats.watchMs)} />
                    <StatCard label="复述点录入" value={formatDurationCompact(friendProfileQ.data.stats.composeMs)} />
                    <StatCard label="复习用时" value={formatDurationCompact(friendProfileQ.data.stats.reviewMs)} />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <StatCard label="AI 问答" value={formatDurationCompact(friendProfileQ.data.stats.qaMs)} />
                    <StatCard label="学习动作" value={friendProfileQ.data.stats.totalActions} detail="学习任务提交 + 复习提交" />
                    <StatCard label="新建任务" value={friendProfileQ.data.stats.learningCount} />
                    <StatCard label="复习提交" value={friendProfileQ.data.stats.reviewCount} />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <StatCard label="活跃天数" value={friendProfileQ.data.stats.studyDays} />
                    <StatCard label="项目数" value={friendProfileQ.data.stats.projectCount} />
                    <StatCard
                      label="上次学习"
                      value={formatLastStudyText(friendProfileQ.data.stats.lastStudyAt).text}
                      detail={friendProfileQ.data.stats.lastStudyAt ? formatDateTimeLabel(friendProfileQ.data.stats.lastStudyAt) : "还没有学习记录"}
                    />
                  </div>
                </>
              ) : null}

              <div className="text-xs text-muted-foreground">好友资料仅限双方互加后可见。</div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  )
}

function PendingRequestColumn(props: {
  title: string
  description: string
  requests: FriendRequest[]
  loading: boolean
  error: unknown
  emptyTitle: string
  emptyMessage: string
  primaryActionLabel: string
  secondaryActionLabel?: string
  actionsDisabled?: boolean
  onPrimaryAction: (request: FriendRequest) => void
  onSecondaryAction?: (request: FriendRequest) => void
}) {
  const {
    title,
    description,
    requests,
    loading,
    error,
    emptyTitle,
    emptyMessage,
    primaryActionLabel,
    secondaryActionLabel,
    actionsDisabled = false,
    onPrimaryAction,
    onSecondaryAction,
  } = props

  return (
    <section className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="text-sm font-semibold text-foreground">{title}</div>
          <div className="text-xs text-muted-foreground">{description}</div>
        </div>
        <MetaTag tone={requests.length > 0 ? "accent" : "default"}>{requests.length}</MetaTag>
      </div>

      {loading ? <LoadingNotice title="正在加载好友申请" message="请稍候..." className="rounded-[1rem]" /> : null}
      {error ? <ErrorNotice title="好友申请加载失败" message={formatApiError(error)} className="rounded-[1rem]" /> : null}

      {!loading && !error && requests.length === 0 ? (
        <ContentEmptyState title={emptyTitle} message={emptyMessage} icon={Mail} className="rounded-[1rem] border-[color:var(--theme-soft-border)] bg-transparent" />
      ) : null}

      {requests.length > 0 ? (
        <div className="space-y-2">
          {requests.map((item) => (
            <div key={item.requestId} className="rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] px-3 py-3">
              <div className="flex items-start gap-3">
                <FriendAvatar user={item.user} size="md" />
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-semibold text-foreground">{item.user.nickname}</div>
                    <div className="text-xs text-muted-foreground">UID {item.user.publicUid}</div>
                  </div>
                  <div className="text-xs text-muted-foreground">{new Date(item.createdAt).toLocaleString()}</div>
                  {item.message?.trim() ? <p className="text-sm leading-6 text-[color:var(--theme-subtle-text)]">“{item.message.trim()}”</p> : null}
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button size="sm" onClick={() => onPrimaryAction(item)} disabled={actionsDisabled} className="[box-shadow:none]">
                  {primaryActionLabel}
                </Button>
                {onSecondaryAction && secondaryActionLabel ? (
                  <Button size="sm" variant="outline" onClick={() => onSecondaryAction(item)} disabled={actionsDisabled} className="[box-shadow:none]">
                    {secondaryActionLabel}
                  </Button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  )
}

function FriendLeaderboard(props: {
  entries: FriendLeaderboardEntry[]
  loading: boolean
  error: unknown
}) {
  const { entries, loading, error } = props

  return (
    <Card className="theme-card-main overflow-hidden">
      <CardHeader className="theme-card-header">
        <CardTitle className="flex items-center gap-2">
          <Trophy className="h-5 w-5 text-amber-500" />
          好友学习排行榜
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? <LoadingNotice title="正在计算排行榜" message="请稍候..." /> : null}
        {error ? <ErrorNotice title="排行榜加载失败" message={formatApiError(error)} /> : null}
        {!loading && !error && entries.length === 0 ? (
          <ContentEmptyState
            title="暂时没有榜单"
            message="结交几个好友后，这里会自动出现学习排行。"
            icon={Sparkles}
            className="rounded-[1.25rem] border-[color:var(--theme-soft-border)] bg-transparent"
          />
        ) : null}

        {entries.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-[0.18em] text-[color:var(--theme-subtle-text)]">
                  <th className="pb-3 pr-3">排名</th>
                  <th className="pb-3 pr-3">好友</th>
                  <th className="pb-3 pr-3">活跃学习</th>
                  <th className="pb-3 pr-3">学习动作</th>
                  <th className="pb-3 pr-3">活跃天数</th>
                  <th className="pb-3">上次学习</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[color:var(--theme-soft-border)]">
                {entries.map((entry, index) => {
                  const lastStudy = formatLastStudyText(entry.stats.lastStudyAt)
                  return (
                    <tr key={`${entry.user.userId}:${entry.isSelf ? "self" : "friend"}`} className="text-sm text-foreground">
                      <td className="py-3 pr-3 align-middle font-semibold">#{index + 1}</td>
                      <td className="py-3 pr-3 align-middle">
                        <div className="flex items-center gap-2">
                          <FriendAvatar user={entry.user} />
                          <div className="min-w-0">
                            <div className="truncate font-medium">{entry.isSelf ? `${entry.user.nickname}（我）` : entry.user.nickname}</div>
                            <div className="text-xs text-muted-foreground">UID {entry.user.publicUid}</div>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 pr-3 align-middle">
                        <div className="font-semibold text-primary">{formatDurationCompact(entry.stats.effectiveMs)}</div>
                        <div className="text-xs text-muted-foreground">
                          看 {formatDurationCompact(entry.stats.watchMs)} · 构 {formatDurationCompact(entry.stats.composeMs)} · 复 {formatDurationCompact(entry.stats.reviewMs)} · 问 {formatDurationCompact(entry.stats.qaMs)}
                        </div>
                      </td>
                      <td className="py-3 pr-3 align-middle">
                        <div className="font-medium">{entry.stats.totalActions}</div>
                        <div className="text-xs text-muted-foreground">
                          任务 {entry.stats.learningCount} · 复习 {entry.stats.reviewCount}
                        </div>
                      </td>
                      <td className="py-3 pr-3 align-middle">{entry.stats.studyDays}</td>
                      <td className="py-3 align-middle">
                        <div className={lastStudy.className}>{lastStudy.text}</div>
                        {entry.stats.lastStudyAt ? <div className="text-xs text-muted-foreground">{formatDateTimeLabel(entry.stats.lastStudyAt)}</div> : null}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
