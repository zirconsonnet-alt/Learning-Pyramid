import { type ReactNode, useState } from "react"
import { Link } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { ContentEmptyState, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useCurrentUser } from "@/ui/queries/auth"
import {
  useAdminActionLogs,
  useAdminGroupComments,
  useAdminGroupPosts,
  useAdminGroups,
  useAdminOverview,
  useAdminUsers,
  useDeleteAdminGroupComment,
  useDeleteAdminGroupPost,
  useUpdateAdminGroupStatus,
  useUpdateAdminUserRole,
  useUpdateAdminUserStatus,
} from "@/ui/queries/admin"
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

export function AdminPage() {
  const currentUserQ = useCurrentUser()
  const [userSearch, setUserSearch] = useState("")
  const [userStatus, setUserStatus] = useState("all")
  const [userRole, setUserRole] = useState("all")
  const [groupSearch, setGroupSearch] = useState("")
  const [groupStatus, setGroupStatus] = useState("all")
  const [contentSearch, setContentSearch] = useState("")
  const overviewQ = useAdminOverview()
  const usersQ = useAdminUsers({
    search: userSearch.trim() || undefined,
    status: userStatus === "all" ? undefined : userStatus,
    role: userRole === "all" ? undefined : userRole,
  })
  const groupsQ = useAdminGroups({
    search: groupSearch.trim() || undefined,
    status: groupStatus === "all" ? undefined : groupStatus,
  })
  const postsQ = useAdminGroupPosts({
    search: contentSearch.trim() || undefined,
    limit: 20,
  })
  const commentsQ = useAdminGroupComments({
    search: contentSearch.trim() || undefined,
    limit: 20,
  })
  const activityQ = useAdminActionLogs({ limit: 20 })
  const updateUserStatus = useUpdateAdminUserStatus()
  const updateUserRole = useUpdateAdminUserRole()
  const updateGroupStatus = useUpdateAdminGroupStatus()
  const deletePost = useDeleteAdminGroupPost()
  const deleteComment = useDeleteAdminGroupComment()
  const isSuperAdmin = Boolean(currentUserQ.data?.roles.includes("super_admin"))

  async function onSetUserStatus(userId: string, status: string) {
    try {
      await updateUserStatus.mutateAsync({ userId, status })
      showSuccessFeedback("用户状态已更新", `已将用户状态调整为 ${status}。`)
    } catch (err) {
      showErrorFeedback("更新用户状态失败", formatApiError(err))
    }
  }

  async function onSetGroupStatus(groupId: string, status: string) {
    try {
      await updateGroupStatus.mutateAsync({ groupId, status })
      showSuccessFeedback("小组状态已更新", `已将小组状态调整为 ${status}。`)
    } catch (err) {
      showErrorFeedback("更新小组状态失败", formatApiError(err))
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

  async function onDeletePost(postId: string) {
    try {
      await deletePost.mutateAsync(postId)
      showSuccessFeedback("帖子已删除", "这条小组动态和它的评论已经从系统中移除。")
    } catch (err) {
      showErrorFeedback("删除帖子失败", formatApiError(err))
    }
  }

  async function onDeleteComment(commentId: string) {
    try {
      await deleteComment.mutateAsync(commentId)
      showSuccessFeedback("评论已删除", "这条评论已经从当前小组互动中移除。")
    } catch (err) {
      showErrorFeedback("删除评论失败", formatApiError(err))
    }
  }

  if (overviewQ.isLoading && !overviewQ.data) {
    return <LoadingNotice title="正在加载后台数据" message="稍等一下，我们正在汇总用户、小组和互动统计。" />
  }

  if (overviewQ.error && !overviewQ.data) {
    return <ErrorNotice title="后台管理加载失败" message={formatApiError(overviewQ.error)} />
  }

  const stats = overviewQ.data
    ? [
        { label: "注册用户", value: overviewQ.data.users, help: "当前账号总量" },
        { label: "活跃用户", value: overviewQ.data.activeUsers, help: "状态为 active" },
        { label: "学习小组", value: overviewQ.data.groups, help: "已创建小组总量" },
        { label: "活跃小组", value: overviewQ.data.activeGroups, help: "状态为 active" },
        { label: "互动动态", value: overviewQ.data.posts, help: "小组内累计发帖数" },
        { label: "互动评论", value: overviewQ.data.comments, help: "小组内累计评论数" },
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

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
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
            <CardTitle className="text-lg">小组管理页</CardTitle>
            <CardDescription>需要巡检小组状态、批量看列表或继续深挖详情时，独立页面更顺手。</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline">
              <Link to="/admin/groups">前往小组管理</Link>
            </Button>
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
          <CardTitle>学习小组管理</CardTitle>
          <CardDescription>查看全量小组，按状态筛选，并快速执行归档、封禁或解封。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
            <div className="space-y-2">
              <Label htmlFor="admin-group-search">搜索小组</Label>
              <Input
                id="admin-group-search"
                value={groupSearch}
                onChange={(event) => setGroupSearch(event.target.value)}
                placeholder="小组名称 / 介绍"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="admin-group-status">状态筛选</Label>
              <select
                id="admin-group-status"
                className="h-10 w-full rounded-xl border border-input bg-white px-3 text-sm"
                value={groupStatus}
                onChange={(event) => setGroupStatus(event.target.value)}
              >
                <option value="all">全部状态</option>
                <option value="active">active</option>
                <option value="archived">archived</option>
                <option value="blocked">blocked</option>
                <option value="dissolved">dissolved</option>
              </select>
            </div>
          </div>

          {groupsQ.error ? <ErrorNotice title="小组列表加载失败" message={formatApiError(groupsQ.error)} /> : null}
          {!groupsQ.error && groupsQ.isLoading ? <LoadingNotice title="正在加载小组列表" message="后台正在刷新学习小组数据。" /> : null}
          {!groupsQ.error && !groupsQ.isLoading && (groupsQ.data?.length ?? 0) === 0 ? (
            <ContentEmptyState title="没有匹配的小组" message="可以调整搜索词或状态筛选后再试一次。" />
          ) : null}

          {groupsQ.data?.map((group) => (
            <div key={group.groupId} className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
              <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
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
                      <StatusPill>{group.visibility}</StatusPill>
                      <StatusPill>{group.joinPolicy}</StatusPill>
                      <StatusPill>{group.memberCount} 成员</StatusPill>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      组长：{group.ownerNickname} · UID {group.ownerPublicUid}
                    </div>
                    <p className="text-sm leading-6 text-[#53657b]">{group.description || "这个小组还没有填写介绍。"}</p>
                  </div>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  <Button asChild variant="outline" size="sm">
                    <Link to={`/admin/groups/${group.groupId}`}>查看详情</Link>
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void onSetGroupStatus(group.groupId, "active")}
                    disabled={updateGroupStatus.isPending || group.status === "active"}
                  >
                    激活
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => void onSetGroupStatus(group.groupId, "archived")}
                    disabled={updateGroupStatus.isPending || group.status === "archived"}
                  >
                    归档
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => void onSetGroupStatus(group.groupId, "blocked")}
                    disabled={updateGroupStatus.isPending || group.status === "blocked"}
                  >
                    封禁
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => void onSetGroupStatus(group.groupId, "dissolved")}
                    disabled={updateGroupStatus.isPending || group.status === "dissolved"}
                  >
                    解散
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>互动内容管理</CardTitle>
          <CardDescription>查看最近的小组帖子和评论，按关键词搜索，并在后台直接清理不合适内容。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="admin-content-search">搜索互动内容</Label>
            <Input
              id="admin-content-search"
              value={contentSearch}
              onChange={(event) => setContentSearch(event.target.value)}
              placeholder="小组名 / UID / 昵称 / 内容关键词"
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <div className="space-y-4">
              <div className="space-y-1">
                <div className="text-sm font-semibold text-foreground">最近帖子</div>
                <div className="text-sm text-muted-foreground">可以快速定位动态内容，并查看这条动态下面有多少条评论。</div>
              </div>

              {postsQ.error ? <ErrorNotice title="帖子列表加载失败" message={formatApiError(postsQ.error)} /> : null}
              {!postsQ.error && postsQ.isLoading ? <LoadingNotice title="正在加载帖子" message="后台正在同步最近的小组动态。" /> : null}
              {!postsQ.error && !postsQ.isLoading && (postsQ.data?.length ?? 0) === 0 ? (
                <ContentEmptyState title="没有匹配的帖子" message="可以调整搜索词，或者等新的小组动态产生后再来查看。" />
              ) : null}

              {postsQ.data?.map((post) => (
                <div key={post.postId} className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-semibold text-foreground">{post.groupName}</div>
                    <StatusPill>{post.kind}</StatusPill>
                    <StatusPill>{post.commentCount} 条评论</StatusPill>
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    作者：{post.authorNickname} · {post.authorPublicUid} · {new Date(post.createdAt).toLocaleString()}
                  </div>
                  <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-[#53657b]">{post.content}</p>
                  <div className="mt-3 flex justify-end">
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => void onDeletePost(post.postId)}
                      disabled={deletePost.isPending || deleteComment.isPending}
                    >
                      删除帖子
                    </Button>
                  </div>
                </div>
              ))}
            </div>

            <div className="space-y-4">
              <div className="space-y-1">
                <div className="text-sm font-semibold text-foreground">最近评论</div>
                <div className="text-sm text-muted-foreground">评论会带上原帖摘要，方便后台快速判断上下文。</div>
              </div>

              {commentsQ.error ? <ErrorNotice title="评论列表加载失败" message={formatApiError(commentsQ.error)} /> : null}
              {!commentsQ.error && commentsQ.isLoading ? <LoadingNotice title="正在加载评论" message="后台正在同步最近的小组评论。" /> : null}
              {!commentsQ.error && !commentsQ.isLoading && (commentsQ.data?.length ?? 0) === 0 ? (
                <ContentEmptyState title="没有匹配的评论" message="可以调整搜索词，或者等新的小组评论产生后再来查看。" />
              ) : null}

              {commentsQ.data?.map((comment) => (
                <div key={comment.commentId} className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-semibold text-foreground">{comment.groupName}</div>
                    <StatusPill>{comment.postKind}</StatusPill>
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    评论人：{comment.authorNickname} · {comment.authorPublicUid} · {new Date(comment.createdAt).toLocaleString()}
                  </div>
                  <div className="mt-3 rounded-2xl border border-dashed border-[#dbe4ee] bg-[#fbfcfe] px-3 py-2 text-xs leading-5 text-muted-foreground">
                    原帖摘要：{comment.postExcerpt || "原帖内容为空"}
                  </div>
                  <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-[#53657b]">{comment.content}</p>
                  <div className="mt-3 flex justify-end">
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => void onDeleteComment(comment.commentId)}
                      disabled={deleteComment.isPending || deletePost.isPending}
                    >
                      删除评论
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
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
            <ContentEmptyState title="还没有后台操作记录" message="等管理员执行用户、小组或内容管理动作后，这里会自动显示。" />
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
