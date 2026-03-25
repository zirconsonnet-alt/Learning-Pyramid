import { type ReactNode, useMemo } from "react"
import { Link, useParams } from "react-router-dom"

import type { StudyGroupPostComment } from "@/ui/api/studyGroups"
import { ApiError } from "@/ui/api/http"
import { ContentEmptyState, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { useDeleteAdminGroupComment, useDeleteAdminGroupPost, useAdminGroupDetail, useUpdateAdminGroupStatus } from "@/ui/queries/admin"
import { useReviewStudyGroupJoinRequest } from "@/ui/queries/studyGroups"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"
import { AdminNav } from "@/views/admin/AdminNav"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function formatDateTime(value: string | null) {
  if (!value) return "—"
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

export function AdminGroupDetailPage() {
  const { groupId = "" } = useParams()
  const groupDetailQ = useAdminGroupDetail(groupId)
  const updateGroupStatus = useUpdateAdminGroupStatus()
  const reviewJoinRequest = useReviewStudyGroupJoinRequest()
  const deletePost = useDeleteAdminGroupPost()
  const deleteComment = useDeleteAdminGroupComment()

  const commentsByPostId = useMemo(() => {
    const map: Record<string, StudyGroupPostComment[]> = {}
    for (const comment of groupDetailQ.data?.comments ?? []) {
      const current = map[comment.postId] ?? []
      current.push(comment)
      map[comment.postId] = current
    }
    return map
  }, [groupDetailQ.data?.comments])

  async function onSetGroupStatus(status: string) {
    try {
      await updateGroupStatus.mutateAsync({ groupId, status })
      showSuccessFeedback("小组状态已更新", `已将小组状态调整为 ${status}。`)
    } catch (err) {
      showErrorFeedback("更新小组状态失败", formatApiError(err))
    }
  }

  async function onReviewJoinRequest(requestId: string, status: "approved" | "rejected", nickname: string) {
    try {
      await reviewJoinRequest.mutateAsync({ groupId, requestId, status })
      showSuccessFeedback(
        status === "approved" ? "申请已通过" : "申请已拒绝",
        status === "approved" ? `${nickname} 已加入当前学习小组。` : `${nickname} 的申请已经处理完成。`,
      )
    } catch (err) {
      showErrorFeedback("处理入组申请失败", formatApiError(err))
    }
  }

  async function onDeletePost(postId: string) {
    if (!window.confirm("确定删除这条小组动态吗？相关评论也会一起删除。")) return
    try {
      await deletePost.mutateAsync(postId)
      showSuccessFeedback("帖子已删除", "这条动态和它的评论已经从当前小组中移除。")
    } catch (err) {
      showErrorFeedback("删除帖子失败", formatApiError(err))
    }
  }

  async function onDeleteComment(commentId: string) {
    if (!window.confirm("确定删除这条评论吗？")) return
    try {
      await deleteComment.mutateAsync(commentId)
      showSuccessFeedback("评论已删除", "这条评论已经从当前小组中移除。")
    } catch (err) {
      showErrorFeedback("删除评论失败", formatApiError(err))
    }
  }

  if (groupDetailQ.isLoading) {
    return <LoadingNotice title="正在加载小组详情" message="我们正在整理小组资料、成员、入组申请和互动内容。" />
  }

  if (groupDetailQ.error || !groupDetailQ.data) {
    return <ErrorNotice title="小组详情加载失败" message={formatApiError(groupDetailQ.error)} />
  }

  const group = groupDetailQ.data
  const pendingRequests = group.joinRequests.filter((item) => item.status === "pending")

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="text-sm text-muted-foreground">后台管理 / 小组详情</div>
            <div className="text-2xl font-semibold text-foreground">{group.name}</div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link to={`/groups/${group.groupId}`}>查看前台小组页</Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/admin/groups">返回小组列表</Link>
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
            <CardTitle>小组概览</CardTitle>
            <CardDescription>这里汇总小组当前的公开资料、组长信息和运行状态，方便我们先做整体判断。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
              <div className="flex h-24 w-24 shrink-0 items-center justify-center overflow-hidden rounded-3xl border border-dashed border-[#d8e1ec] bg-[#f7fafc] text-3xl font-semibold text-[#5c6f86]">
                {group.avatarUrl ? <img src={group.avatarUrl} alt={group.name} className="h-full w-full object-cover" /> : group.name.slice(0, 1).toUpperCase()}
              </div>
              <div className="min-w-0 flex-1 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <div className="text-xl font-semibold text-foreground">{group.name}</div>
                  <StatusPill tone={group.status === "active" ? "accent" : group.status === "blocked" || group.status === "dissolved" ? "danger" : "default"}>
                    {group.status}
                  </StatusPill>
                  <StatusPill>{group.visibility}</StatusPill>
                  <StatusPill>{group.joinPolicy}</StatusPill>
                  <StatusPill>{group.memberCount} 成员</StatusPill>
                </div>
                <div className="text-sm text-muted-foreground">
                  组长：
                  {" "}
                  <Link to={`/admin/users/${group.ownerUserId}`} className="font-medium text-foreground hover:underline">
                    {group.ownerNickname}
                  </Link>
                  {" "}
                  · UID {group.ownerPublicUid}
                </div>
                <p className="text-sm leading-6 text-[#53657b]">{group.description || "这个小组还没有填写介绍。"}</p>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
                <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground">创建时间</div>
                <div className="mt-2 text-sm font-medium text-foreground">{formatDateTime(group.createdAt)}</div>
              </div>
              <div className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
                <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground">最近更新</div>
                <div className="mt-2 text-sm font-medium text-foreground">{formatDateTime(group.updatedAt)}</div>
              </div>
              <div className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
                <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground">帖子数量</div>
                <div className="mt-2 text-sm font-medium text-foreground">{group.posts.length} 条</div>
              </div>
              <div className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
                <div className="text-xs uppercase tracking-[0.12em] text-muted-foreground">待处理申请</div>
                <div className="mt-2 text-sm font-medium text-foreground">{pendingRequests.length} 条</div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>后台操作</CardTitle>
            <CardDescription>这一栏保留后台管理最常用的状态调整入口，处理风控或运营问题会更直接。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button
              className="w-full"
              variant="outline"
              onClick={() => void onSetGroupStatus("active")}
              disabled={updateGroupStatus.isPending || group.status === "active"}
            >
              激活小组
            </Button>
            <Button
              className="w-full"
              variant="secondary"
              onClick={() => void onSetGroupStatus("archived")}
              disabled={updateGroupStatus.isPending || group.status === "archived"}
            >
              归档小组
            </Button>
            <Button
              className="w-full"
              variant="secondary"
              onClick={() => void onSetGroupStatus("blocked")}
              disabled={updateGroupStatus.isPending || group.status === "blocked"}
            >
              封禁小组
            </Button>
            <Button
              className="w-full"
              variant="destructive"
              onClick={() => void onSetGroupStatus("dissolved")}
              disabled={updateGroupStatus.isPending || group.status === "dissolved"}
            >
              解散小组
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>成员列表</CardTitle>
          <CardDescription>这里按当前成员关系展示组长、管理员和普通成员，便于我们快速定位相关账号。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {group.members.length === 0 ? <ContentEmptyState title="这个小组还没有成员" message="理论上正常小组至少会有 1 个组长；如果这里为空，建议后面再补一轮数据排查。" /> : null}

          {group.members.map((member) => (
            <div key={member.userId} className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div className="min-w-0 flex flex-1 gap-3">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-dashed border-[#d8e1ec] bg-[#f7fafc] text-sm font-semibold text-[#5c6f86]">
                    {member.avatarUrl ? <img src={member.avatarUrl} alt={member.nickname} className="h-full w-full object-cover" /> : member.nickname.slice(0, 1).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-sm font-semibold text-foreground">{member.nickname}</div>
                      <StatusPill>{member.role}</StatusPill>
                    </div>
                    <div className="text-xs text-muted-foreground">UID：{member.publicUid}</div>
                    <div className="text-xs text-muted-foreground">加入时间：{formatDateTime(member.joinedAt)}</div>
                  </div>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button asChild variant="outline" size="sm">
                    <Link to={`/admin/users/${member.userId}`}>查看用户</Link>
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>入组申请</CardTitle>
          <CardDescription>后台可以直接看到当前小组的入组申请，并在需要时帮助组长快速处理。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {group.joinRequests.length === 0 ? <ContentEmptyState title="当前没有入组申请" message="如果后续切到 approval 模式，这里会直接显示等待处理的申请。" /> : null}

          {group.joinRequests.map((item) => (
            <div key={item.requestId} className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 flex-1 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-semibold text-foreground">{item.requesterNickname}</div>
                    <StatusPill tone={item.status === "approved" ? "accent" : item.status === "rejected" ? "danger" : "default"}>
                      {item.status}
                    </StatusPill>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    UID：{item.requesterPublicUid} · 提交时间：{formatDateTime(item.createdAt)}
                  </div>
                  <p className="text-sm leading-6 text-[#53657b]">{item.message || "申请人没有附加说明。"}</p>
                  {item.status !== "pending" ? (
                    <div className="text-xs text-muted-foreground">处理时间：{formatDateTime(item.reviewedAt)}</div>
                  ) : null}
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  <Button asChild variant="outline" size="sm">
                    <Link to={`/admin/users/${item.requesterUserId}`}>查看用户</Link>
                  </Button>
                  {item.status === "pending" ? (
                    <>
                      <Button size="sm" onClick={() => void onReviewJoinRequest(item.requestId, "approved", item.requesterNickname)} disabled={reviewJoinRequest.isPending}>
                        通过
                      </Button>
                      <Button variant="secondary" size="sm" onClick={() => void onReviewJoinRequest(item.requestId, "rejected", item.requesterNickname)} disabled={reviewJoinRequest.isPending}>
                        拒绝
                      </Button>
                    </>
                  ) : null}
                </div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>互动内容</CardTitle>
          <CardDescription>这里把帖子和评论放在一起看，方便我们一边判断上下文，一边直接做清理操作。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {group.posts.length === 0 ? <ContentEmptyState title="这个小组还没有互动内容" message="如果需要验证前台互动链路，可以后面再补一条测试数据。" /> : null}

          {group.posts.map((post) => {
            const comments = commentsByPostId[post.postId] ?? []
            return (
              <div key={post.postId} className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
                <div className="flex flex-col gap-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="text-sm font-semibold text-foreground">{post.authorNickname}</div>
                        <StatusPill>{post.kind}</StatusPill>
                        <StatusPill>{comments.length} 条评论</StatusPill>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        UID：{post.authorPublicUid} · 发布时间：{formatDateTime(post.createdAt)}
                      </div>
                    </div>
                    <div className="flex shrink-0 flex-wrap gap-2">
                      <Button asChild variant="outline" size="sm">
                        <Link to={`/admin/users/${post.authorUserId}`}>查看作者</Link>
                      </Button>
                      <Button variant="destructive" size="sm" onClick={() => void onDeletePost(post.postId)} disabled={deletePost.isPending || deleteComment.isPending}>
                        删除帖子
                      </Button>
                    </div>
                  </div>
                  <p className="text-sm leading-7 text-[#314052]">{post.content}</p>

                  <div className="space-y-3 rounded-[1rem] border border-dashed border-[#dde5ee] bg-[#fbfcfe] p-4">
                    <div className="text-sm font-medium text-foreground">评论</div>
                    {comments.length === 0 ? <ContentEmptyState title="这条帖子还没有评论" message="当前不需要进一步处理评论内容。" className="bg-transparent" /> : null}
                    {comments.map((comment) => (
                      <div key={comment.commentId} className="rounded-[1rem] border border-[#e3e8ef] bg-white p-4">
                        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                          <div className="space-y-2">
                            <div className="text-sm font-semibold text-foreground">{comment.authorNickname}</div>
                            <div className="text-xs text-muted-foreground">
                              UID：{comment.authorPublicUid} · 发布时间：{formatDateTime(comment.createdAt)}
                            </div>
                            <p className="text-sm leading-6 text-[#53657b]">{comment.content}</p>
                          </div>
                          <div className="flex shrink-0 flex-wrap gap-2">
                            <Button asChild variant="outline" size="sm">
                              <Link to={`/admin/users/${comment.authorUserId}`}>查看评论人</Link>
                            </Button>
                            <Button variant="destructive" size="sm" onClick={() => void onDeleteComment(comment.commentId)} disabled={deleteComment.isPending || deletePost.isPending}>
                              删除评论
                            </Button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )
          })}
        </CardContent>
      </Card>
    </div>
  )
}
