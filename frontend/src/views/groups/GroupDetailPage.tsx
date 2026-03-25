import { type ChangeEvent, type ReactNode, useEffect, useMemo, useState } from "react"
import { useNavigate, useParams } from "react-router-dom"

import type { StudyGroupPostComment } from "@/ui/api/studyGroups"
import { ApiError } from "@/ui/api/http"
import { ContentEmptyState, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useCurrentUser } from "@/ui/queries/auth"
import {
  useCreateStudyGroupJoinRequest,
  useCreateStudyGroupPostComment,
  useCreateStudyGroupPost,
  useDeleteStudyGroupPostComment,
  useDeleteStudyGroupPost,
  useInviteStudyGroupMember,
  useJoinStudyGroup,
  useLeaveStudyGroup,
  useRemoveStudyGroupMember,
  useReviewStudyGroupJoinRequest,
  useStudyGroup,
  useStudyGroupComments,
  useStudyGroupJoinRequests,
  useStudyGroupMembers,
  useStudyGroupPosts,
  useUpdateStudyGroupMemberRole,
  useUpdateStudyGroup,
  useUploadStudyGroupAvatar,
} from "@/ui/queries/studyGroups"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function MetaTag(props: { children: ReactNode; tone?: "default" | "accent" | "danger" }) {
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

export function GroupDetailPage() {
  const nav = useNavigate()
  const { groupId = "" } = useParams()
  const currentUserQ = useCurrentUser()
  const groupQ = useStudyGroup(groupId)
  const membersQ = useStudyGroupMembers(groupId)
  const postsQ = useStudyGroupPosts(groupId)
  const commentsQ = useStudyGroupComments(groupId)
  const isGlobalAdmin = Boolean(currentUserQ.data?.roles.some((role) => role === "super_admin" || role === "admin"))
  const canManageGroupData = Boolean(
    groupQ.data && (isGlobalAdmin || groupQ.data.memberRole === "owner" || groupQ.data.memberRole === "admin"),
  )
  const joinRequestsQ = useStudyGroupJoinRequests(groupId, canManageGroupData)
  const updateGroup = useUpdateStudyGroup()
  const uploadGroupAvatar = useUploadStudyGroupAvatar()
  const joinGroup = useJoinStudyGroup()
  const leaveGroup = useLeaveStudyGroup()
  const createJoinRequest = useCreateStudyGroupJoinRequest()
  const createComment = useCreateStudyGroupPostComment()
  const createPost = useCreateStudyGroupPost()
  const deleteComment = useDeleteStudyGroupPostComment()
  const deletePost = useDeleteStudyGroupPost()
  const inviteMember = useInviteStudyGroupMember()
  const reviewJoinRequest = useReviewStudyGroupJoinRequest()
  const updateMemberRole = useUpdateStudyGroupMemberRole()
  const removeMember = useRemoveStudyGroupMember()
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [visibility, setVisibility] = useState("public")
  const [joinPolicy, setJoinPolicy] = useState("free")
  const [joinRequestMessage, setJoinRequestMessage] = useState("")
  const [invitePublicUid, setInvitePublicUid] = useState("")
  const [inviteRole, setInviteRole] = useState("member")
  const [postKind, setPostKind] = useState("discussion")
  const [postContent, setPostContent] = useState("")
  const [commentDrafts, setCommentDrafts] = useState<Record<string, string>>({})

  useEffect(() => {
    if (!groupQ.data) return
    setName(groupQ.data.name)
    setDescription(groupQ.data.description)
    setVisibility(groupQ.data.visibility)
    setJoinPolicy(groupQ.data.joinPolicy)
  }, [groupQ.data?.description, groupQ.data?.joinPolicy, groupQ.data?.name, groupQ.data?.visibility])

  const commentsByPostId = useMemo(() => {
    const map: Record<string, StudyGroupPostComment[]> = {}
    for (const comment of commentsQ.data ?? []) {
      const current = map[comment.postId] ?? []
      current.push(comment)
      map[comment.postId] = current
    }
    return map
  }, [commentsQ.data])

  if (groupQ.isLoading) {
    return <LoadingNotice title="正在加载小组详情" message="我们正在整理小组信息、成员和互动内容。" />
  }

  if (groupQ.error || !groupQ.data) {
    return <ErrorNotice title="学习小组加载失败" message={formatApiError(groupQ.error)} />
  }

  const group = groupQ.data
  const isMember = Boolean(group.memberRole)
  const canManage = isGlobalAdmin || group.memberRole === "owner" || group.memberRole === "admin"
  const canManageMembers = isGlobalAdmin || group.memberRole === "owner"
  const canJoin = !isMember && group.visibility === "public" && group.joinPolicy === "free" && group.status === "active"
  const canRequestJoin = !isMember && group.visibility === "public" && group.joinPolicy === "approval" && group.status === "active"
  const hasPendingJoinRequest = group.joinRequestStatus === "pending"
  const canLeave = isMember && group.memberRole !== "owner"
  const canPost = isMember && group.status === "active"

  async function onSaveSettings() {
    try {
      await updateGroup.mutateAsync({
        groupId,
        name,
        description,
        visibility,
        joinPolicy,
      })
      showSuccessFeedback("小组设置已更新", "新的小组名称、介绍和加入策略已经保存。")
    } catch (err) {
      showErrorFeedback("保存小组设置失败", formatApiError(err))
    }
  }

  async function onUploadGroupAvatar(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ""
    if (!file) return
    try {
      await uploadGroupAvatar.mutateAsync({ groupId, file })
      showSuccessFeedback("小组头像已更新", "新的小组头像已经保存，成员列表和大厅会同步显示。")
    } catch (err) {
      showErrorFeedback("上传小组头像失败", formatApiError(err))
    }
  }

  async function onJoin() {
    try {
      await joinGroup.mutateAsync(groupId)
      showSuccessFeedback("已加入学习小组", "现在你可以查看成员并发布互动内容。")
    } catch (err) {
      showErrorFeedback("加入学习小组失败", formatApiError(err))
    }
  }

  async function onLeave() {
    try {
      await leaveGroup.mutateAsync(groupId)
      showSuccessFeedback("已退出学习小组", "你仍然可以回到大厅继续寻找其他小组。")
      nav("/groups")
    } catch (err) {
      showErrorFeedback("退出学习小组失败", formatApiError(err))
    }
  }

  async function onCreateJoinRequest() {
    try {
      await createJoinRequest.mutateAsync({ groupId, message: joinRequestMessage })
      setJoinRequestMessage("")
      showSuccessFeedback("加入申请已提交", "组长或管理员审核通过后，你会自动成为小组成员。")
    } catch (err) {
      showErrorFeedback("提交加入申请失败", formatApiError(err))
    }
  }

  async function onInviteMember() {
    try {
      await inviteMember.mutateAsync({
        groupId,
        publicUid: invitePublicUid.trim(),
        role: inviteRole,
      })
      setInvitePublicUid("")
      setInviteRole("member")
      showSuccessFeedback("成员邀请已完成", "目标用户已经加入当前学习小组。")
    } catch (err) {
      showErrorFeedback("按 UID 邀请成员失败", formatApiError(err))
    }
  }

  async function onReviewJoinRequest(requestId: string, status: "approved" | "rejected", nickname: string) {
    try {
      await reviewJoinRequest.mutateAsync({ groupId, requestId, status })
      showSuccessFeedback(
        status === "approved" ? "申请已通过" : "申请已拒绝",
        status === "approved" ? `${nickname} 已加入当前学习小组。` : `${nickname} 的申请已处理完成。`,
      )
    } catch (err) {
      showErrorFeedback("处理加入申请失败", formatApiError(err))
    }
  }

  async function onCreatePost() {
    try {
      await createPost.mutateAsync({ groupId, kind: postKind, content: postContent })
      setPostContent("")
      setPostKind("discussion")
      showSuccessFeedback("互动内容已发布", "这条动态已经同步到小组时间线。")
    } catch (err) {
      showErrorFeedback("发布互动失败", formatApiError(err))
    }
  }

  async function onCreateComment(postId: string) {
    const content = (commentDrafts[postId] ?? "").trim()
    if (!content) return
    try {
      await createComment.mutateAsync({ groupId, postId, content })
      setCommentDrafts((current) => ({ ...current, [postId]: "" }))
      showSuccessFeedback("评论已发布", "这条回复已经同步到当前动态下面。")
    } catch (err) {
      showErrorFeedback("发布评论失败", formatApiError(err))
    }
  }

  async function onDeletePost(postId: string) {
    if (!window.confirm("确定删除这条动态吗？相关评论也会一起删除。")) return
    try {
      await deletePost.mutateAsync({ groupId, postId })
      showSuccessFeedback("动态已删除", "这条互动内容和关联评论已经移除。")
    } catch (err) {
      showErrorFeedback("删除动态失败", formatApiError(err))
    }
  }

  async function onDeleteComment(commentId: string) {
    if (!window.confirm("确定删除这条评论吗？")) return
    try {
      await deleteComment.mutateAsync({ groupId, commentId })
      showSuccessFeedback("评论已删除", "这条回复已经从当前动态中移除。")
    } catch (err) {
      showErrorFeedback("删除评论失败", formatApiError(err))
    }
  }

  async function onChangeMemberRole(userId: string, role: string, successMessage: string) {
    try {
      await updateMemberRole.mutateAsync({ groupId, userId, role })
      showSuccessFeedback("成员角色已更新", successMessage)
    } catch (err) {
      showErrorFeedback("更新成员角色失败", formatApiError(err))
    }
  }

  async function onRemoveMember(userId: string, nickname: string) {
    try {
      await removeMember.mutateAsync({ groupId, userId })
      showSuccessFeedback("成员已移出小组", `${nickname} 已经从当前学习小组移除。`)
    } catch (err) {
      showErrorFeedback("移除成员失败", formatApiError(err))
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-3xl border border-dashed border-[#d8e1ec] bg-[#f7fafc] text-lg font-semibold text-[#5c6f86]">
              {group.avatarUrl ? <img src={group.avatarUrl} alt={group.name} className="h-full w-full object-cover" /> : group.name.slice(0, 1).toUpperCase()}
            </div>
            <div className="space-y-3">
              <div>
                <CardTitle>{group.name}</CardTitle>
                <CardDescription className="mt-1">组长：{group.ownerNickname} · UID {group.ownerPublicUid}</CardDescription>
              </div>
              <p className="max-w-3xl text-sm leading-6 text-[#53657b]">{group.description || "这个小组还没有填写介绍。"}</p>
              <div className="flex flex-wrap gap-2">
                <MetaTag>{group.visibility === "public" ? "公开小组" : "私密小组"}</MetaTag>
                <MetaTag>{group.joinPolicy === "free" ? "自由加入" : group.joinPolicy === "approval" ? "需审核" : "仅邀请"}</MetaTag>
                <MetaTag>{group.memberCount} 位成员</MetaTag>
                <MetaTag tone={group.status === "active" ? "accent" : "danger"}>状态：{group.status}</MetaTag>
                {group.memberRole ? <MetaTag tone="accent">我的身份：{group.memberRole}</MetaTag> : null}
                {hasPendingJoinRequest ? <MetaTag tone="accent">我的申请：待审核</MetaTag> : null}
              </div>
            </div>
          </div>

          <div className="flex shrink-0 flex-wrap gap-2">
            <Button variant="outline" onClick={() => nav("/groups")}>
              返回大厅
            </Button>
            {canJoin ? (
              <Button onClick={() => void onJoin()} disabled={joinGroup.isPending}>
                {joinGroup.isPending ? "加入中..." : "加入小组"}
              </Button>
            ) : null}
            {canLeave ? (
              <Button variant="secondary" onClick={() => void onLeave()} disabled={leaveGroup.isPending}>
                {leaveGroup.isPending ? "退出中..." : "退出小组"}
              </Button>
            ) : null}
          </div>
        </CardHeader>
      </Card>

      {canManage ? (
        <Card>
          <CardHeader>
            <CardTitle>小组设置</CardTitle>
            <CardDescription>组长、管理员或后台管理员可以在这里调整基础配置。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="edit-group-name">小组名称</Label>
                <Input id="edit-group-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={60} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="edit-group-visibility">可见范围</Label>
                <select
                  id="edit-group-visibility"
                  className="h-10 w-full rounded-xl border border-input bg-white px-3 text-sm"
                  value={visibility}
                  onChange={(event) => setVisibility(event.target.value)}
                >
                  <option value="public">公开</option>
                  <option value="private">私密</option>
                </select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-group-description">小组介绍</Label>
              <textarea
                id="edit-group-description"
                className="min-h-28 w-full rounded-xl border border-input/90 bg-white px-4 py-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                maxLength={1000}
              />
            </div>
            <div className="space-y-2 sm:max-w-sm">
              <Label htmlFor="edit-group-join-policy">加入方式</Label>
              <select
                id="edit-group-join-policy"
                className="h-10 w-full rounded-xl border border-input bg-white px-3 text-sm"
                value={joinPolicy}
                onChange={(event) => setJoinPolicy(event.target.value)}
              >
                <option value="free">自由加入</option>
                <option value="approval">审核加入</option>
                <option value="invite_only">仅邀请</option>
              </select>
            </div>
            <div className="space-y-3 rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-dashed border-[#d8e1ec] bg-[#f7fafc] text-base font-semibold text-[#5c6f86]">
                  {group.avatarUrl ? <img src={group.avatarUrl} alt={group.name} className="h-full w-full object-cover" /> : group.name.slice(0, 1).toUpperCase()}
                </div>
                <div className="space-y-1">
                  <div className="text-sm font-medium text-foreground">小组头像</div>
                  <div className="text-xs leading-5 text-muted-foreground">支持 JPG、PNG、WebP，单张不超过 2 MB。</div>
                </div>
              </div>
              <div className="space-y-2 sm:max-w-sm">
                <Label htmlFor="group-avatar-upload">上传新头像</Label>
                <Input
                  id="group-avatar-upload"
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={(event) => void onUploadGroupAvatar(event)}
                  disabled={uploadGroupAvatar.isPending}
                />
              </div>
            </div>
            <Button onClick={() => void onSaveSettings()} disabled={updateGroup.isPending || !name.trim()}>
              {updateGroup.isPending ? "保存中..." : "保存小组设置"}
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {canRequestJoin || hasPendingJoinRequest ? (
        <Card>
          <CardHeader>
            <CardTitle>加入申请</CardTitle>
            <CardDescription>审核制小组支持先提交申请，再由组长或管理员进行处理。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {hasPendingJoinRequest ? (
              <ContentEmptyState title="申请已提交" message="当前申请正在等待审核，通过后你会自动成为正式成员。" />
            ) : (
              <>
                <div className="space-y-2">
                  <Label htmlFor="group-join-request-message">申请说明</Label>
                  <textarea
                    id="group-join-request-message"
                    className="min-h-28 w-full rounded-xl border border-input/90 bg-white px-4 py-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    value={joinRequestMessage}
                    onChange={(event) => setJoinRequestMessage(event.target.value)}
                    maxLength={300}
                    placeholder="可以简单介绍你的学习目标、希望一起攻克的内容，或者加入原因。"
                  />
                </div>
                <Button onClick={() => void onCreateJoinRequest()} disabled={createJoinRequest.isPending}>
                  {createJoinRequest.isPending ? "提交中..." : "提交加入申请"}
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Card>
          <CardHeader>
            <CardTitle>互动动态</CardTitle>
            <CardDescription>成员可以发布通知、讨论或打卡内容，方便一起推进学习节奏。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {canPost ? (
              <div className="space-y-4 rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
                <div className="grid gap-4 sm:grid-cols-[160px_minmax(0,1fr)]">
                  <div className="space-y-2">
                    <Label htmlFor="post-kind">动态类型</Label>
                    <select
                      id="post-kind"
                      className="h-10 w-full rounded-xl border border-input bg-white px-3 text-sm"
                      value={postKind}
                      onChange={(event) => setPostKind(event.target.value)}
                    >
                      <option value="discussion">讨论</option>
                      <option value="notice">公告</option>
                      <option value="checkin">打卡</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="post-content">内容</Label>
                    <textarea
                      id="post-content"
                      className="min-h-28 w-full rounded-xl border border-input/90 bg-white px-4 py-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      value={postContent}
                      onChange={(event) => setPostContent(event.target.value)}
                      maxLength={2000}
                    />
                  </div>
                </div>
                <Button onClick={() => void onCreatePost()} disabled={createPost.isPending || !postContent.trim()}>
                  {createPost.isPending ? "发布中..." : "发布动态"}
                </Button>
              </div>
            ) : (
              <ContentEmptyState
                title="当前不能发布动态"
                message={isMember ? "这个小组当前不是活跃状态，先恢复为 active 后再继续互动。" : "先加入学习小组，才能发布通知、讨论和打卡内容。"}
              />
            )}

            {postsQ.error ? <ErrorNotice title="动态加载失败" message={formatApiError(postsQ.error)} /> : null}
            {commentsQ.error ? <ErrorNotice title="评论加载失败" message={formatApiError(commentsQ.error)} /> : null}

            {!postsQ.error && (postsQ.data?.length ?? 0) === 0 ? (
              <ContentEmptyState title="还没有互动动态" message="可以先发一条欢迎消息、今日学习计划，或者一条打卡内容。" />
            ) : null}

            {postsQ.data?.map((post) => (
              <div key={post.postId} className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-semibold text-foreground">{post.authorNickname}</div>
                    <div className="text-xs text-muted-foreground">{post.authorPublicUid}</div>
                    <MetaTag tone="accent">{post.kind}</MetaTag>
                    <span className="text-xs text-muted-foreground">{new Date(post.createdAt).toLocaleString()}</span>
                  </div>
                  {canManage || post.authorUserId === currentUserQ.data?.userId ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => void onDeletePost(post.postId)}
                      disabled={deletePost.isPending}
                    >
                      {deletePost.isPending ? "删除中..." : "删除动态"}
                    </Button>
                  ) : null}
                </div>
                <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-[#53657b]">{post.content}</p>
                <div className="mt-4 space-y-3 rounded-[1rem] border border-dashed border-[#dbe4ee] bg-[#fbfcfe] p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium text-foreground">评论区</div>
                    <div className="text-xs text-muted-foreground">{(commentsByPostId[post.postId] ?? []).length} 条评论</div>
                  </div>

                  {(commentsByPostId[post.postId] ?? []).length === 0 ? (
                    <div className="text-xs text-muted-foreground">还没有人回复，来留下第一条评论吧。</div>
                  ) : (
                    (commentsByPostId[post.postId] ?? []).map((comment) => (
                      <div key={comment.commentId} className="rounded-2xl border border-[#e6edf5] bg-white px-3 py-2.5">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <div className="text-xs font-semibold text-foreground">{comment.authorNickname}</div>
                            <div className="text-xs text-muted-foreground">{comment.authorPublicUid}</div>
                            <span className="text-xs text-muted-foreground">{new Date(comment.createdAt).toLocaleString()}</span>
                          </div>
                          {canManage || comment.authorUserId === currentUserQ.data?.userId ? (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => void onDeleteComment(comment.commentId)}
                              disabled={deleteComment.isPending}
                            >
                              {deleteComment.isPending ? "删除中..." : "删除评论"}
                            </Button>
                          ) : null}
                        </div>
                        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[#53657b]">{comment.content}</p>
                      </div>
                    ))
                  )}

                  {canPost ? (
                    <div className="space-y-2">
                      <Label htmlFor={`comment-${post.postId}`}>写评论</Label>
                      <textarea
                        id={`comment-${post.postId}`}
                        className="min-h-24 w-full rounded-xl border border-input/90 bg-white px-4 py-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        value={commentDrafts[post.postId] ?? ""}
                        onChange={(event) =>
                          setCommentDrafts((current) => ({
                            ...current,
                            [post.postId]: event.target.value,
                          }))
                        }
                        maxLength={1000}
                        placeholder="补充你的想法、提问，或者给队友一点反馈。"
                      />
                      <Button
                        size="sm"
                        onClick={() => void onCreateComment(post.postId)}
                        disabled={createComment.isPending || !(commentDrafts[post.postId] ?? "").trim()}
                      >
                        {createComment.isPending ? "发送中..." : "发送评论"}
                      </Button>
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-6">
          {canManage ? (
            <Card>
              <CardHeader>
                <CardTitle>邀请与审批</CardTitle>
                <CardDescription>支持通过 UID 邀请用户入组，也可以集中处理待审核的加入申请。</CardDescription>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="space-y-4 rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
                  <div className="space-y-1">
                    <div className="text-sm font-medium text-foreground">通过 UID 邀请成员</div>
                    <div className="text-xs leading-5 text-muted-foreground">适合仅邀请小组，或者需要直接把用户加入当前学习小组时使用。</div>
                  </div>
                  <div className="grid gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="invite-public-uid">用户 UID</Label>
                      <Input
                        id="invite-public-uid"
                        value={invitePublicUid}
                        onChange={(event) => setInvitePublicUid(event.target.value)}
                        placeholder="例如 LP1A2B3C4D"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="invite-role">加入后角色</Label>
                      <select
                        id="invite-role"
                        className="h-10 w-full rounded-xl border border-input bg-white px-3 text-sm"
                        value={inviteRole}
                        onChange={(event) => setInviteRole(event.target.value)}
                      >
                        <option value="member">普通成员</option>
                        <option value="admin">小组管理员</option>
                      </select>
                    </div>
                  </div>
                  <Button onClick={() => void onInviteMember()} disabled={inviteMember.isPending || !invitePublicUid.trim()}>
                    {inviteMember.isPending ? "邀请中..." : "按 UID 邀请"}
                  </Button>
                </div>

                <div className="space-y-3">
                  <div className="space-y-1">
                    <div className="text-sm font-medium text-foreground">待审核申请</div>
                    <div className="text-xs leading-5 text-muted-foreground">审批通过后，对方会自动加入小组；拒绝后可以稍后重新申请。</div>
                  </div>

                  {joinRequestsQ.isLoading ? <LoadingNotice title="正在加载申请列表" message="马上就好，我们正在同步待审核的申请。" /> : null}
                  {joinRequestsQ.error ? <ErrorNotice title="申请列表加载失败" message={formatApiError(joinRequestsQ.error)} /> : null}

                  {!joinRequestsQ.isLoading && !joinRequestsQ.error && (joinRequestsQ.data?.length ?? 0) === 0 ? (
                    <ContentEmptyState title="暂时没有待审核申请" message="当前还没有新的加入申请，等用户提交后会显示在这里。" />
                  ) : null}

                  {joinRequestsQ.data?.map((item) => (
                    <div key={item.requestId} className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="text-sm font-semibold text-foreground">{item.requesterNickname}</div>
                        <div className="text-xs text-muted-foreground">{item.requesterPublicUid}</div>
                        <MetaTag tone="accent">{item.status}</MetaTag>
                      </div>
                      <div className="mt-2 text-xs text-muted-foreground">{new Date(item.createdAt).toLocaleString()}</div>
                      <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-[#53657b]">{item.message || "申请人没有填写附加说明。"}</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          onClick={() => void onReviewJoinRequest(item.requestId, "approved", item.requesterNickname)}
                          disabled={reviewJoinRequest.isPending}
                        >
                          通过
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => void onReviewJoinRequest(item.requestId, "rejected", item.requesterNickname)}
                          disabled={reviewJoinRequest.isPending}
                        >
                          拒绝
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle>成员列表</CardTitle>
              <CardDescription>通过 UID 和角色快速识别同组成员；组长可以继续调整成员角色或转让组长。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {membersQ.error ? <ErrorNotice title="成员列表加载失败" message={formatApiError(membersQ.error)} /> : null}

              {membersQ.data?.map((member) => (
                <div key={member.userId} className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-2xl border border-dashed border-[#d8e1ec] bg-[#f7fafc] text-sm font-semibold text-[#5c6f86]">
                      {member.avatarUrl ? <img src={member.avatarUrl} alt={member.nickname} className="h-full w-full object-cover" /> : member.nickname.slice(0, 1).toUpperCase()}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-foreground">{member.nickname}</div>
                      <div className="truncate text-xs text-muted-foreground">{member.publicUid}</div>
                    </div>
                    <MetaTag tone={member.role === "owner" ? "accent" : "default"}>{member.role}</MetaTag>
                  </div>

                  {canManageMembers && member.userId !== currentUserQ.data?.userId && member.role !== "owner" ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {member.role === "member" ? (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => void onChangeMemberRole(member.userId, "admin", `${member.nickname} 现在是小组管理员。`)}
                          disabled={updateMemberRole.isPending || removeMember.isPending}
                        >
                          设为管理员
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => void onChangeMemberRole(member.userId, "member", `${member.nickname} 已调整为普通成员。`)}
                          disabled={updateMemberRole.isPending || removeMember.isPending}
                        >
                          调整为成员
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => void onChangeMemberRole(member.userId, "owner", `组长已经转让给 ${member.nickname}。`)}
                        disabled={updateMemberRole.isPending || removeMember.isPending}
                      >
                        转让组长
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => void onRemoveMember(member.userId, member.nickname)}
                        disabled={updateMemberRole.isPending || removeMember.isPending}
                      >
                        移出小组
                      </Button>
                    </div>
                  ) : member.userId === currentUserQ.data?.userId ? (
                    <div className="mt-3 text-xs text-muted-foreground">这是你当前的成员身份。</div>
                  ) : null}
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
