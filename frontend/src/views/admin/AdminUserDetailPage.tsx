import { type ReactNode, useMemo } from "react"
import { Link, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { ContentEmptyState, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { useCurrentUser } from "@/ui/queries/auth"
import { useAdminActionLogs, useAdminUserDetail, useUpdateAdminUserRole, useUpdateAdminUserStatus } from "@/ui/queries/admin"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"
import { AdminNav } from "@/views/admin/AdminNav"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function formatDateTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function StatusPill(props: { children: ReactNode; tone?: "default" | "accent" | "danger" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-xs",
        props.tone === "accent"
          ? "border-primary/20 bg-[#eef5ff] text-[#1d4f8f]"
          : props.tone === "danger"
            ? "border-[#f5c2c7] bg-[#fff4f5] text-[#b42318]"
            : "border-[#dde5ee] bg-[#f8fafc] text-[#5b6b82]",
      )}
    >
      {props.children}
    </span>
  )
}

export function AdminUserDetailPage() {
  const { userId = "" } = useParams()
  const currentUserQ = useCurrentUser()
  const userDetailQ = useAdminUserDetail(userId)
  const activityQ = useAdminActionLogs({ limit: 100 })
  const updateUserStatus = useUpdateAdminUserStatus()
  const updateUserRole = useUpdateAdminUserRole()
  const isSuperAdmin = Boolean(currentUserQ.data?.roles.includes("super_admin"))

  const relatedActivity = useMemo(() => {
    return (activityQ.data ?? [])
      .filter((item) => item.targetId === userId || item.actorUserId === userId)
      .slice(0, 12)
  }, [activityQ.data, userId])

  async function onSetUserStatus(status: string) {
    try {
      await updateUserStatus.mutateAsync({ userId, status })
      showSuccessFeedback("用户状态已更新", `已将用户状态调整为 ${status}。`)
    } catch (err) {
      showErrorFeedback("更新用户状态失败", formatApiError(err))
    }
  }

  async function onToggleAdminRole(enabled: boolean) {
    try {
      await updateUserRole.mutateAsync({ userId, role: "admin", enabled })
      showSuccessFeedback(enabled ? "管理员已授权" : "管理员已移除", enabled ? "该用户现在可以访问后台管理页面。" : "该用户已经失去后台管理权限。")
    } catch (err) {
      showErrorFeedback("更新管理员角色失败", formatApiError(err))
    }
  }

  if (userDetailQ.isLoading) {
    return <LoadingNotice title="正在加载用户详情" message="我们正在整理该用户的资料、角色和小组信息。" />
  }

  if (userDetailQ.error || !userDetailQ.data) {
    return <ErrorNotice title="用户详情加载失败" message={formatApiError(userDetailQ.error)} />
  }

  const user = userDetailQ.data
  const isCurrentUser = currentUserQ.data?.userId === user.userId

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="text-sm text-muted-foreground">后台管理 / 用户详情</div>
            <div className="text-2xl font-semibold text-foreground">{user.nickname}</div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link to="/admin/users">返回用户列表</Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/admin">返回后台总览</Link>
            </Button>
          </div>
        </div>
        <AdminNav />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.9fr)]">
        <Card>
          <CardHeader>
            <CardTitle>账号概览</CardTitle>
            <CardDescription>这里把该用户的账号身份、公开资料和当前权限集中放在一起，方便我们快速判断和处理。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
              <div className="flex h-24 w-24 shrink-0 items-center justify-center overflow-hidden rounded-3xl border border-dashed border-[#d8e1ec] bg-[#f7fafc] text-3xl font-semibold text-[#5c6f86]">
                {user.avatarUrl ? <img src={user.avatarUrl} alt={user.nickname} className="h-full w-full object-cover" /> : user.nickname.slice(0, 1).toUpperCase()}
              </div>
              <div className="min-w-0 flex-1 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <div className="text-xl font-semibold text-foreground">{user.nickname}</div>
                  <StatusPill tone={user.status === "active" ? "accent" : user.status === "deleted" ? "danger" : "default"}>
                    {user.status}
                  </StatusPill>
                  {isCurrentUser ? <StatusPill>当前登录账号</StatusPill> : null}
                  {user.roles.map((role) => (
                    <StatusPill key={role}>{role}</StatusPill>
                  ))}
                </div>
                <div className="text-sm text-muted-foreground">{user.email}</div>
                <div className="text-sm text-muted-foreground">UID：{user.publicUid}</div>
                <p className="text-sm leading-6 text-[#53657b]">{user.bio || "这个用户还没有填写自我描述。"}</p>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
                <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground">注册时间</div>
                <div className="mt-2 text-sm font-medium text-foreground">{formatDateTime(user.createdAt)}</div>
              </div>
              <div className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
                <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground">最近更新</div>
                <div className="mt-2 text-sm font-medium text-foreground">{formatDateTime(user.updatedAt)}</div>
              </div>
              <div className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
                <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground">角色</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {user.roles.length > 0 ? user.roles.map((role) => <StatusPill key={role}>{role}</StatusPill>) : <StatusPill>普通用户</StatusPill>}
                </div>
              </div>
              <div className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
                <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground">学习小组</div>
                <div className="mt-2 text-sm font-medium text-foreground">{user.groups.length} 个</div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>后台操作</CardTitle>
            <CardDescription>这里先保留我们在第一轮已经打通的状态和角色调整能力，放到单个用户维度里更顺手。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button
              className="w-full"
              variant="outline"
              onClick={() => void onSetUserStatus("active")}
              disabled={updateUserStatus.isPending || updateUserRole.isPending || user.status === "active"}
            >
              激活账号
            </Button>
            <Button
              className="w-full"
              variant="secondary"
              onClick={() => void onSetUserStatus("suspended")}
              disabled={updateUserStatus.isPending || updateUserRole.isPending || user.status === "suspended"}
            >
              暂停账号
            </Button>
            <Button
              className="w-full"
              variant="destructive"
              onClick={() => void onSetUserStatus("deleted")}
              disabled={updateUserStatus.isPending || updateUserRole.isPending || user.status === "deleted"}
            >
              标记删除
            </Button>

            {isSuperAdmin && !user.roles.includes("super_admin") ? (
              user.roles.includes("admin") ? (
                <Button className="w-full" variant="secondary" onClick={() => void onToggleAdminRole(false)} disabled={updateUserRole.isPending || updateUserStatus.isPending}>
                  移除管理员权限
                </Button>
              ) : (
                <Button className="w-full" variant="outline" onClick={() => void onToggleAdminRole(true)} disabled={updateUserRole.isPending || updateUserStatus.isPending}>
                  设为管理员
                </Button>
              )
            ) : null}

            {user.roles.includes("super_admin") ? (
              <ContentEmptyState
                title="这是 super_admin 账号"
                message="当前页面不会提供 super_admin 角色的移除入口，避免误操作影响整站后台访问。"
              />
            ) : null}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>参与的小组</CardTitle>
          <CardDescription>展示这个用户当前加入了哪些学习小组、在里面是什么角色，以及什么时候加入的。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {user.groups.length === 0 ? (
            <ContentEmptyState title="这个用户还没有加入任何小组" message="后续如果要排查用户互动行为，我们可以等第三轮的小组详情页一起串起来。" />
          ) : null}

          {user.groups.map((group) => (
            <div key={group.groupId} className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 flex flex-1 gap-3">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-dashed border-[#d8e1ec] bg-[#f7fafc] text-sm font-semibold text-[#5c6f86]">
                    {group.avatarUrl ? <img src={group.avatarUrl} alt={group.name} className="h-full w-full object-cover" /> : group.name.slice(0, 1).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-sm font-semibold text-foreground">{group.name}</div>
                      <StatusPill tone={group.status === "active" ? "accent" : group.status === "blocked" || group.status === "dissolved" ? "danger" : "default"}>
                        {group.status}
                      </StatusPill>
                      <StatusPill>{group.memberRole}</StatusPill>
                      <StatusPill>{group.memberCount} 成员</StatusPill>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      组长：{group.ownerNickname} · UID {group.ownerPublicUid}
                    </div>
                    <p className="text-sm leading-6 text-[#53657b]">{group.description || "这个小组还没有填写介绍。"}</p>
                    <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                      <span>加入时间：{formatDateTime(group.joinedAt)}</span>
                      <span>可见性：{group.visibility}</span>
                      <span>加入策略：{group.joinPolicy}</span>
                    </div>
                  </div>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button asChild variant="outline" size="sm">
                    <Link to={`/groups/${group.groupId}`}>查看小组</Link>
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>最近后台记录</CardTitle>
          <CardDescription>这里先复用后台操作日志，把与该用户直接相关的最近记录拉出来，方便我们回看谁做过什么。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {activityQ.error ? <ErrorNotice title="后台记录加载失败" message={formatApiError(activityQ.error)} /> : null}
          {!activityQ.error && activityQ.isLoading ? <LoadingNotice title="正在加载后台记录" message="我们正在整理和这个用户有关的最近操作。" /> : null}
          {!activityQ.error && !activityQ.isLoading && relatedActivity.length === 0 ? (
            <ContentEmptyState title="最近没有找到相关后台记录" message="至少在最近 100 条后台操作里，还没有和这个用户直接关联的处理记录。" />
          ) : null}

          {relatedActivity.map((item) => (
            <div key={item.logId} className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <StatusPill>{item.actionType}</StatusPill>
                <span className="text-xs text-muted-foreground">{formatDateTime(item.createdAt)}</span>
              </div>
              <div className="mt-2 text-sm font-medium text-foreground">{item.summary}</div>
              <div className="mt-1 text-xs text-muted-foreground">
                操作者：{item.actorNickname} · {item.actorPublicUid}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
