import { type ReactNode, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { ContentEmptyState, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useFindUserByUid } from "@/ui/queries/profile"
import { useCreateStudyGroup, useJoinStudyGroup, useStudyGroups } from "@/ui/queries/studyGroups"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function MetaTag(props: { children: ReactNode; tone?: "default" | "accent" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-xs",
        props.tone === "accent"
          ? "border-primary/20 bg-[#eef5ff] text-[#1d4f8f]"
          : "border-[#dde5ee] bg-[#f8fafc] text-[#5b6b82]",
      )}
    >
      {props.children}
    </span>
  )
}

export function GroupsPage() {
  const nav = useNavigate()
  const groupsQ = useStudyGroups()
  const createGroup = useCreateStudyGroup()
  const joinGroup = useJoinStudyGroup()
  const findUserByUid = useFindUserByUid()
  const [filterText, setFilterText] = useState("")
  const [lookupUid, setLookupUid] = useState("")
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [visibility, setVisibility] = useState("public")
  const [joinPolicy, setJoinPolicy] = useState("free")

  const groups = useMemo(() => {
    const items = groupsQ.data ?? []
    const needle = filterText.trim().toLowerCase()
    if (!needle) return items
    return items.filter((group) => {
      const text = `${group.name} ${group.description} ${group.ownerNickname} ${group.ownerPublicUid}`.toLowerCase()
      return text.includes(needle)
    })
  }, [filterText, groupsQ.data])

  async function onCreateGroup() {
    try {
      const created = await createGroup.mutateAsync({
        name,
        description,
        visibility,
        joinPolicy,
      })
      setName("")
      setDescription("")
      setVisibility("public")
      setJoinPolicy("free")
      showSuccessFeedback("学习小组已创建", "已经把你设为组长，可以继续到详情页发第一条动态。")
      nav(`/groups/${created.groupId}`)
    } catch (err) {
      showErrorFeedback("创建学习小组失败", formatApiError(err))
    }
  }

  async function onJoinGroup(groupId: string) {
    try {
      await joinGroup.mutateAsync(groupId)
      showSuccessFeedback("已加入学习小组", "现在你可以进入小组详情页开始互动。")
      nav(`/groups/${groupId}`)
    } catch (err) {
      showErrorFeedback("加入学习小组失败", formatApiError(err))
    }
  }

  async function onFindUser() {
    const uid = lookupUid.trim()
    if (!uid) {
      showErrorFeedback("请输入 UID", "例如 LPABCD123 这样的公开 UID。")
      return
    }
    try {
      await findUserByUid.mutateAsync(uid)
    } catch (err) {
      showErrorFeedback("查找用户失败", formatApiError(err))
    }
  }

  if (groupsQ.isLoading) {
    return <LoadingNotice title="正在加载学习小组" message="稍等一下，我们正在整理你可见的小组列表。" />
  }

  if (groupsQ.error) {
    return <ErrorNotice title="学习小组加载失败" message={formatApiError(groupsQ.error)} />
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(340px,0.75fr)]">
      <Card>
        <CardHeader className="gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-1.5">
            <CardTitle>学习小组大厅</CardTitle>
            <CardDescription>这里会显示你已加入的小组，以及当前可直接加入的公开小组。</CardDescription>
          </div>
          <div className="w-full sm:w-72">
            <Input value={filterText} onChange={(event) => setFilterText(event.target.value)} placeholder="按名称、描述、UID 过滤" />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {groups.length === 0 ? (
            <ContentEmptyState title="暂时没有匹配的小组" message="可以先创建一个学习小组，或者清空筛选条件重新查看。" />
          ) : (
            groups.map((group) => {
              const canQuickJoin = !group.memberRole && group.visibility === "public" && group.joinPolicy === "free" && group.status === "active"
              return (
                <div key={group.groupId} className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 flex flex-1 gap-3">
                      <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-dashed border-[#d8e1ec] bg-[#f7fafc] text-sm font-semibold text-[#5c6f86]">
                        {group.avatarUrl ? <img src={group.avatarUrl} alt={group.name} className="h-full w-full object-cover" /> : group.name.slice(0, 1).toUpperCase()}
                      </div>
                      <div className="min-w-0 flex-1 space-y-3">
                        <div>
                          <div className="text-base font-semibold text-foreground">{group.name}</div>
                          <div className="mt-1 text-sm text-muted-foreground">
                            组长：{group.ownerNickname} · UID {group.ownerPublicUid}
                          </div>
                        </div>
                        <p className="text-sm leading-6 text-[#53657b]">{group.description || "这个小组还没有填写介绍。"}</p>
                        <div className="flex flex-wrap gap-2">
                          <MetaTag>{group.visibility === "public" ? "公开可见" : "私密小组"}</MetaTag>
                          <MetaTag>{group.joinPolicy === "free" ? "自由加入" : group.joinPolicy === "approval" ? "需审核" : "仅邀请"}</MetaTag>
                          <MetaTag>{group.memberCount} 位成员</MetaTag>
                          <MetaTag tone={group.memberRole ? "accent" : "default"}>
                            {group.memberRole ? `我的身份：${group.memberRole}` : `状态：${group.status}`}
                          </MetaTag>
                        </div>
                      </div>
                    </div>
                    <div className="flex shrink-0 flex-wrap gap-2">
                      <Button variant="outline" onClick={() => nav(`/groups/${group.groupId}`)}>
                        查看详情
                      </Button>
                      {canQuickJoin ? (
                        <Button onClick={() => void onJoinGroup(group.groupId)} disabled={joinGroup.isPending}>
                          {joinGroup.isPending ? "加入中..." : "快速加入"}
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </CardContent>
      </Card>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>创建学习小组</CardTitle>
            <CardDescription>先做 MVP：支持建组、公开/私密、加入策略和后续互动。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="group-name">小组名称</Label>
              <Input id="group-name" value={name} onChange={(event) => setName(event.target.value)} maxLength={60} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="group-description">小组介绍</Label>
              <textarea
                id="group-description"
                className="min-h-28 w-full rounded-xl border border-input/90 bg-white px-4 py-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                maxLength={1000}
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="group-visibility">可见范围</Label>
                <select
                  id="group-visibility"
                  className="h-10 w-full rounded-xl border border-input bg-white px-3 text-sm"
                  value={visibility}
                  onChange={(event) => setVisibility(event.target.value)}
                >
                  <option value="public">公开</option>
                  <option value="private">私密</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="group-join-policy">加入方式</Label>
                <select
                  id="group-join-policy"
                  className="h-10 w-full rounded-xl border border-input bg-white px-3 text-sm"
                  value={joinPolicy}
                  onChange={(event) => setJoinPolicy(event.target.value)}
                >
                  <option value="free">自由加入</option>
                  <option value="approval">审核加入</option>
                  <option value="invite_only">仅邀请</option>
                </select>
              </div>
            </div>
            <Button
              type="button"
              onClick={() => void onCreateGroup()}
              disabled={createGroup.isPending || !name.trim()}
              className="w-full"
            >
              {createGroup.isPending ? "创建中..." : "创建学习小组"}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>通过 UID 找同学</CardTitle>
            <CardDescription>输入公开 UID，就能快速确认对方昵称、头像和简介。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-3">
              <Input value={lookupUid} onChange={(event) => setLookupUid(event.target.value)} placeholder="输入公开 UID" />
              <Button type="button" onClick={() => void onFindUser()} disabled={findUserByUid.isPending}>
                {findUserByUid.isPending ? "查找中..." : "查找"}
              </Button>
            </div>

            {findUserByUid.data ? (
              <div className="rounded-[1rem] border border-[#e3e8ef] bg-white/80 p-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-2xl border border-dashed border-[#d8e1ec] bg-[#f7fafc] text-sm font-semibold text-[#5c6f86]">
                    {findUserByUid.data.avatarUrl ? (
                      <img src={findUserByUid.data.avatarUrl} alt={findUserByUid.data.nickname} className="h-full w-full object-cover" />
                    ) : (
                      findUserByUid.data.nickname.slice(0, 1).toUpperCase()
                    )}
                  </div>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-foreground">{findUserByUid.data.nickname}</div>
                    <div className="truncate text-xs text-muted-foreground">{findUserByUid.data.publicUid}</div>
                  </div>
                </div>
                <p className="mt-3 text-sm leading-6 text-[#53657b]">{findUserByUid.data.bio || "这个用户还没有填写自我描述。"}</p>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
