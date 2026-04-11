import { type ReactNode, useState } from "react"
import { Link } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { ContentEmptyState, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useCurrentUser } from "@/ui/queries/auth"
import { useAdminActionLogs, useAdminOverview, useAdminUsers, useUpdateAdminUserRole, useUpdateAdminUserStatus } from "@/ui/queries/admin"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"
import { AdminNav } from "@/views/admin/AdminNav"
import { formatDurationCompact } from "@/views/profile/profileStats"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
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

export function AdminPage() {
  const currentUserQ = useCurrentUser()
  const [userSearch, setUserSearch] = useState("")
  const [userStatus, setUserStatus] = useState("all")
  const [userRole, setUserRole] = useState("all")
  const overviewQ = useAdminOverview()
  const usersQ = useAdminUsers({
    search: userSearch.trim() || undefined,
    status: userStatus === "all" ? undefined : userStatus,
    role: userRole === "all" ? undefined : userRole,
  })
  const activityQ = useAdminActionLogs({ limit: 20 })
  const updateUserStatus = useUpdateAdminUserStatus()
  const updateUserRole = useUpdateAdminUserRole()
  const isSuperAdmin = Boolean(currentUserQ.data?.roles.includes("super_admin"))

  async function onSetUserStatus(userId: string, status: string) {
    try {
      await updateUserStatus.mutateAsync({ userId, status })
      showSuccessFeedback("用户状态已更新", `已将用户状态调整为 ${status}。`)
    } catch (err) {
      showErrorFeedback("更新用户状态失败", formatApiError(err))
    }
  }

  async function onToggleAdminRole(userId: string, enabled: boolean) {
    try {
      await updateUserRole.mutateAsync({ userId, role: "admin", enabled })
      showSuccessFeedback(enabled ? "管理员已授权" : "管理员已移除", enabled ? "该用户现在可以访问后台管理页面。" : "该用户已经失去后台管理权限。")
    } catch (err) {
      showErrorFeedback("更新管理员角色失败", formatApiError(err))
    }
  }

  if (overviewQ.isLoading && !overviewQ.data) {
    return <LoadingNotice title="正在加载后台数据" message="稍等一下，我们正在汇总用户与后台统计。" />
  }

  if (overviewQ.error && !overviewQ.data) {
    return <ErrorNotice title="后台管理加载失败" message={formatApiError(overviewQ.error)} />
  }

  const stats = overviewQ.data
    ? [
        { label: "注册用户", value: overviewQ.data.users, help: "当前账号总量" },
        { label: "活跃用户", value: overviewQ.data.activeUsers, help: "状态为 active" },
        { label: "学习用户", value: overviewQ.data.studyUsers, help: "至少同步过一次学习时长" },
        { label: "近 7 日学习用户", value: overviewQ.data.studyUsers7d, help: "最近 7 天有学习同步记录" },
        { label: "累计有效学习", value: formatDurationCompact(overviewQ.data.effectiveStudyMs), help: "去重后的累计学习时长" },
        { label: "材料接触", value: formatDurationCompact(overviewQ.data.watchMs), help: "累计材料播放/阅读时长" },
        { label: "复述点构建", value: formatDurationCompact(overviewQ.data.composeMs), help: "累计编辑与构建时长" },
        { label: "复习时长", value: formatDurationCompact(overviewQ.data.reviewMs), help: "累计复习交互时长" },
        { label: "AI 问答", value: formatDurationCompact(overviewQ.data.qaMs), help: "累计 AI 问答交互时长" },
      ]
    : []

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <div className="space-y-1">
          <div className="text-sm text-muted-foreground">后台管理 / 总览</div>
          <div className="text-2xl font-semibold text-foreground">后台总控台</div>
        </div>
        <AdminNav />
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {stats.map((item) => (
          <Card key={item.label}>
            <CardHeader className="pb-3">
              <CardDescription>{item.label}</CardDescription>
              <CardTitle className="text-2xl">{item.value}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">{item.help}</CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">会员运营页</CardTitle>
            <CardDescription>订单、邀请码和优惠券都收在一起，更适合处理会员转化和风控动作。</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline">
              <Link to="/admin/membership">前往会员运营</Link>
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">用户管理页</CardTitle>
            <CardDescription>需要连续处理用户状态、角色和资料问题时，独立页面会更专注。</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline">
              <Link to="/admin/users">前往用户管理</Link>
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">旧社区入口已收口</CardTitle>
            <CardDescription>前台已经切回好友体系，后台只保留当前仍在使用的管理能力，避免历史模块继续干扰主流程。</CardDescription>
          </CardHeader>
          <CardContent className="text-sm leading-6 text-muted-foreground">
            历史数据仍保留在存储层，便于后续迁移、核对或按需要做一次性清理。
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>用户管理</CardTitle>
          <CardDescription>支持按邮箱、昵称、UID、状态和角色筛选，并快速调整用户状态；超级管理员还可以授予后台管理员权限。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px_220px]">
            <div className="space-y-2">
              <Label htmlFor="admin-user-search">搜索用户</Label>
              <Input
                id="admin-user-search"
                value={userSearch}
                onChange={(event) => setUserSearch(event.target.value)}
                placeholder="邮箱 / 昵称 / UID"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="admin-user-status">状态筛选</Label>
              <select
                id="admin-user-status"
                className="h-10 w-full rounded-xl border border-input bg-white px-3 text-sm"
                value={userStatus}
                onChange={(event) => setUserStatus(event.target.value)}
              >
                <option value="all">全部状态</option>
                <option value="active">active</option>
                <option value="suspended">suspended</option>
                <option value="deleted">deleted</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="admin-user-role">角色筛选</Label>
              <select
                id="admin-user-role"
                className="h-10 w-full rounded-xl border border-input bg-white px-3 text-sm"
                value={userRole}
                onChange={(event) => setUserRole(event.target.value)}
              >
                <option value="all">全部角色</option>
                <option value="super_admin">super_admin</option>
                <option value="admin">admin</option>
                <option value="none">普通用户</option>
              </select>
            </div>
          </div>

          {usersQ.error ? <ErrorNotice title="用户列表加载失败" message={formatApiError(usersQ.error)} /> : null}
          {!usersQ.error && usersQ.isLoading ? <LoadingNotice title="正在加载用户列表" message="后台正在刷新用户数据。" /> : null}
          {!usersQ.error && !usersQ.isLoading && (usersQ.data?.length ?? 0) === 0 ? (
            <ContentEmptyState title="没有匹配的用户" message="可以调整搜索词或状态筛选后再试一次。" />
          ) : null}

          {usersQ.data?.map((user) => (
            <div key={user.userId} className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
              <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                <div className="min-w-0 flex-1 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-semibold text-foreground">{user.nickname}</div>
                    <StatusPill tone={user.status === "active" ? "accent" : user.status === "deleted" ? "danger" : "default"}>
                      {user.status}
                    </StatusPill>
                    {user.roles.map((role) => (
                      <StatusPill key={role}>{role}</StatusPill>
                    ))}
                  </div>
                  <div className="text-sm text-muted-foreground">{user.email}</div>
                  <div className="text-xs text-muted-foreground">UID：{user.publicUid}</div>
                  <p className="text-sm leading-6 text-[#53657b]">{user.bio || "这个用户还没有填写自我描述。"}</p>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  <Button asChild variant="outline" size="sm">
                    <Link to={`/admin/users/${user.userId}`}>查看详情</Link>
                  </Button>
                  {isSuperAdmin && !user.roles.includes("super_admin") ? (
                    user.roles.includes("admin") ? (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => void onToggleAdminRole(user.userId, false)}
                        disabled={updateUserRole.isPending}
                      >
                        移除管理员
                      </Button>
                    ) : (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => void onToggleAdminRole(user.userId, true)}
                        disabled={updateUserRole.isPending}
                      >
                        设为管理员
                      </Button>
                    )
                  ) : null}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void onSetUserStatus(user.userId, "active")}
                    disabled={updateUserStatus.isPending || updateUserRole.isPending || user.status === "active"}
                  >
                    激活
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => void onSetUserStatus(user.userId, "suspended")}
                    disabled={updateUserStatus.isPending || updateUserRole.isPending || user.status === "suspended"}
                  >
                    暂停
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => void onSetUserStatus(user.userId, "deleted")}
                    disabled={updateUserStatus.isPending || updateUserRole.isPending || user.status === "deleted"}
                  >
                    删除
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>后台说明</CardTitle>
          <CardDescription>这轮后台只保留用户、会员和操作记录相关能力，避免历史模块继续占据主要位置。</CardDescription>
        </CardHeader>
        <CardContent className="text-sm leading-6 text-muted-foreground">
          如果后续要做彻底清理，我们可以继续处理存储结构和迁移脚本；这轮先把主入口、常用后台页面和测试切回当前的好友方案。
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>最近后台操作</CardTitle>
          <CardDescription>保留最近的管理员操作轨迹，方便我们回溯谁在什么时间处理了哪些内容。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {activityQ.error ? <ErrorNotice title="操作日志加载失败" message={formatApiError(activityQ.error)} /> : null}
          {!activityQ.error && activityQ.isLoading ? <LoadingNotice title="正在加载操作日志" message="后台正在同步最近的管理员操作记录。" /> : null}
          {!activityQ.error && !activityQ.isLoading && (activityQ.data?.length ?? 0) === 0 ? (
            <ContentEmptyState title="还没有后台操作记录" message="等管理员执行用户、会员或其他后台动作后，这里会自动显示。" />
          ) : null}

          {activityQ.data?.map((item) => (
            <div key={item.logId} className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <div className="text-sm font-semibold text-foreground">{item.actorNickname}</div>
                <StatusPill>{item.actorPublicUid}</StatusPill>
                <StatusPill>{item.actionType}</StatusPill>
                <span className="text-xs text-muted-foreground">{new Date(item.createdAt).toLocaleString()}</span>
              </div>
              <div className="mt-2 text-xs text-muted-foreground">
                目标：{item.targetKind} · {item.targetId}
              </div>
              <p className="mt-3 text-sm leading-6 text-[#53657b]">{item.summary}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
