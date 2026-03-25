import { type ReactNode, useState } from "react"
import { Link } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { ContentEmptyState, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useAdminGroups, useUpdateAdminGroupStatus } from "@/ui/queries/admin"
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

export function AdminGroupsPage() {
  const [groupSearch, setGroupSearch] = useState("")
  const [groupStatus, setGroupStatus] = useState("all")
  const groupsQ = useAdminGroups({
    search: groupSearch.trim() || undefined,
    status: groupStatus === "all" ? undefined : groupStatus,
  })
  const updateGroupStatus = useUpdateAdminGroupStatus()

  async function onSetGroupStatus(groupId: string, status: string) {
    try {
      await updateGroupStatus.mutateAsync({ groupId, status })
      showSuccessFeedback("小组状态已更新", `已将小组状态调整为 ${status}。`)
    } catch (err) {
      showErrorFeedback("更新小组状态失败", formatApiError(err))
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <div className="space-y-1">
          <div className="text-sm text-muted-foreground">后台管理 / 小组管理</div>
          <div className="text-2xl font-semibold text-foreground">小组列表</div>
        </div>
        <AdminNav />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>学习小组管理</CardTitle>
          <CardDescription>这里专门处理小组筛选、状态巡检和跳转详情排查，和原方案里的独立小组页对齐。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
            <div className="space-y-2">
              <Label htmlFor="admin-group-search-page">搜索小组</Label>
              <Input
                id="admin-group-search-page"
                value={groupSearch}
                onChange={(event) => setGroupSearch(event.target.value)}
                placeholder="小组名称 / 介绍"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="admin-group-status-page">状态筛选</Label>
              <select
                id="admin-group-status-page"
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
    </div>
  )
}
