import { type ReactNode, useState } from "react"
import { Link } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { ContentEmptyState, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useCurrentUser } from "@/ui/queries/auth"
import { useAdminUsers, useUpdateAdminUserRole, useUpdateAdminUserStatus } from "@/ui/queries/admin"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"
import { AdminNav } from "@/views/admin/AdminNav"

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

export function AdminUsersPage() {
  const currentUserQ = useCurrentUser()
  const [userSearch, setUserSearch] = useState("")
  const [userStatus, setUserStatus] = useState("all")
  const [userRole, setUserRole] = useState("all")
  const usersQ = useAdminUsers({
    search: userSearch.trim() || undefined,
    status: userStatus === "all" ? undefined : userStatus,
    role: userRole === "all" ? undefined : userRole,
  })
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

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <div className="space-y-1">
          <div className="text-sm text-muted-foreground">后台管理 / 用户管理</div>
          <div className="text-2xl font-semibold text-foreground">用户列表</div>
        </div>
        <AdminNav />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>用户管理</CardTitle>
          <CardDescription>这里专门处理用户筛选、状态调整和后台管理员授权，比总览页更适合连续排查用户问题。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px_220px]">
            <div className="space-y-2">
              <Label htmlFor="admin-user-search-page">搜索用户</Label>
              <Input
                id="admin-user-search-page"
                value={userSearch}
                onChange={(event) => setUserSearch(event.target.value)}
                placeholder="邮箱 / 昵称 / UID"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="admin-user-status-page">状态筛选</Label>
              <select
                id="admin-user-status-page"
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
              <Label htmlFor="admin-user-role-page">角色筛选</Label>
              <select
                id="admin-user-role-page"
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
    </div>
  )
}
