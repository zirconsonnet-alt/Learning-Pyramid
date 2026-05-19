import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { ChevronRight, FileVideo, FolderOpen, HardDriveDownload, RefreshCw } from "lucide-react"
import { Link } from "react-router-dom"

import { listProjectBaiduNetdiskFiles, type BaiduNetdiskFileItem } from "@/ui/api/baiduNetdisk"
import { ApiError } from "@/ui/api/http"
import type { ScopedProjectRef } from "@/ui/api/projectScope"
import { Button } from "@/ui/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/ui/components/ui/dialog"
import { useBaiduNetdiskCloudAccounts } from "@/ui/queries/cloudAccounts"
import { useImportLearningObjectsFromBaiduNetdisk } from "@/ui/queries/workbench"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function formatSize(sizeBytes: number | null) {
  if (!sizeBytes || sizeBytes <= 0) return "大小未知"
  const units = ["B", "KB", "MB", "GB", "TB"]
  let value = sizeBytes
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  const rounded = value >= 10 || unitIndex === 0 ? Math.round(value) : Math.round(value * 10) / 10
  return `${rounded}${units[unitIndex]}`
}

function formatDuration(durationMs: number | null) {
  if (!durationMs || durationMs <= 0) return "时长未知"
  const totalSeconds = Math.floor(durationMs / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
  return `${minutes}:${String(seconds).padStart(2, "0")}`
}

function isVideoItem(item: BaiduNetdiskFileItem) {
  if (item.isDir) return false
  if (item.mimeType?.startsWith("video/")) return true
  return /\.(mp4|m4v|mkv|webm|mov|avi|flv|ts|m2ts)$/i.test(item.name)
}

function isImportableItem(item: BaiduNetdiskFileItem) {
  return item.isDir || isVideoItem(item)
}

function buildParentDir(path: string) {
  if (!path || path === "/") return "/"
  const segments = path.split("/").filter(Boolean)
  if (segments.length <= 1) return "/"
  return `/${segments.slice(0, -1).join("/")}`
}

function buildPathSegments(path: string) {
  const segments = path.split("/").filter(Boolean)
  return [
    { label: "根目录", path: "/" },
    ...segments.map((segment, index) => ({
      label: segment,
      path: `/${segments.slice(0, index + 1).join("/")}`,
    })),
  ]
}

function normalizeBaiduPath(path: string) {
  const segments = path.split("/").filter(Boolean)
  return segments.length > 0 ? `/${segments.join("/")}` : "/"
}

function isSameOrDescendantPath(path: string, maybeAncestor: string) {
  const normalizedPath = normalizeBaiduPath(path)
  const normalizedAncestor = normalizeBaiduPath(maybeAncestor)
  return normalizedPath === normalizedAncestor || normalizedPath.startsWith(`${normalizedAncestor}/`)
}

export function BaiduNetdiskImportDialog({
  subjectId,
  projectId,
  open,
  onOpenChange,
}: {
  subjectId: string
  projectId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const accountsQ = useBaiduNetdiskCloudAccounts(open)
  const projectScope: ScopedProjectRef | null = subjectId && projectId ? { subjectId, scopedProjectId: projectId } : null
  const importMutation = useImportLearningObjectsFromBaiduNetdisk(projectScope)

  const [dirPath, setDirPath] = useState("/")
  const [openSessionSeq, setOpenSessionSeq] = useState(0)
  const [selectedItemsBySession, setSelectedItemsBySession] = useState<Record<string, Record<string, BaiduNetdiskFileItem>>>({})
  const accountId = accountsQ.data?.[0]?.accountId ?? ""
  const hasAccount = (accountsQ.data?.length ?? 0) > 0
  const selectionSessionKey = `${subjectId}:${projectId}:${accountId}:${openSessionSeq}`
  const selectedItemsByPath = useMemo(
    () => selectedItemsBySession[selectionSessionKey] ?? {},
    [selectedItemsBySession, selectionSessionKey],
  )

  const filesQ = useQuery({
    queryKey: ["baiduNetdiskFiles", subjectId, projectId, accountId, dirPath],
    queryFn: ({ signal }) =>
      listProjectBaiduNetdiskFiles(
        projectScope as ScopedProjectRef,
        { accountId, dirPath, page: 1, limit: 200 },
        { signal, timeoutMs: 90_000 },
      ),
    enabled: open && !!projectScope && !!accountId,
    staleTime: 10_000,
  })

  const visibleItems = useMemo(() => {
    const items = filesQ.data?.items ?? []
    return [...items].sort((left, right) => {
      if (left.isDir !== right.isDir) return left.isDir ? -1 : 1
      return left.name.localeCompare(right.name, "zh-CN")
    })
  }, [filesQ.data?.items])

  const selectedItems = useMemo(
    () => Object.values(selectedItemsByPath).sort((left, right) => left.path.localeCompare(right.path, "zh-CN")),
    [selectedItemsByPath],
  )
  const pathSegments = useMemo(() => buildPathSegments(dirPath), [dirPath])

  function toggleItem(item: BaiduNetdiskFileItem) {
    if (!isImportableItem(item)) return
    const itemPath = normalizeBaiduPath(item.path)
    setSelectedItemsBySession((current) => {
      const currentSelection = current[selectionSessionKey] ?? {}
      const nextSelection = { ...currentSelection }
      if (nextSelection[itemPath]) {
        delete nextSelection[itemPath]
      } else {
        for (const selectedPath of Object.keys(nextSelection)) {
          if (isSameOrDescendantPath(selectedPath, itemPath) || isSameOrDescendantPath(itemPath, selectedPath)) {
            delete nextSelection[selectedPath]
          }
        }
        nextSelection[itemPath] = item
      }
      const next = { ...current }
      if (Object.keys(nextSelection).length > 0) next[selectionSessionKey] = nextSelection
      else delete next[selectionSessionKey]
      return next
    })
  }

  async function onImport() {
    if (!accountId || selectedItems.length <= 0) return
    try {
      const result = await importMutation.mutateAsync({
        accountId,
        items: selectedItems.map((item) => ({
          fileId: item.fileId,
          path: item.path,
          name: item.name,
          isDir: item.isDir,
          sizeBytes: item.sizeBytes ?? undefined,
          mimeType: item.mimeType ?? undefined,
          durationMs: item.durationMs ?? undefined,
        })),
      })
      showSuccessFeedback(
        "百度网盘视频已导入",
        `本次导入 ${result.imported_count} 个视频，新增 ${result.created_instances_count} 个实例。`,
      )
      onOpenChange(false)
    } catch (err) {
      showErrorFeedback("导入百度网盘视频失败", formatApiError(err))
    }
  }

  function handleOpenChange(nextOpen: boolean) {
    if (nextOpen) {
      setDirPath("/")
      setOpenSessionSeq((current) => current + 1)
    } else {
      setSelectedItemsBySession((current) => {
        const next = { ...current }
        delete next[selectionSessionKey]
        return next
      })
    }
    onOpenChange(nextOpen)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>从百度网盘导入视频</DialogTitle>
        </DialogHeader>

        {accountsQ.isLoading ? <div className="px-1 py-8 text-sm text-muted-foreground">正在加载已绑定账号...</div> : null}

        {!accountsQ.isLoading && !accountsQ.error && !hasAccount ? (
          <div className="rounded-[1.2rem] border border-dashed border-border/70 bg-muted/15 px-4 py-5 text-sm leading-6 text-muted-foreground">
            当前还没有可用的百度网盘账号。请先到{" "}
            <Link to="/profile" className="font-medium text-primary underline underline-offset-4">
              个人中心
            </Link>{" "}
            完成账号绑定，再回来导入视频。
          </div>
        ) : null}

        {accountsQ.error ? <div className="rounded-[1.2rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{formatApiError(accountsQ.error)}</div> : null}

        {!accountsQ.isLoading && !accountsQ.error && hasAccount ? (
          <div className="space-y-3">
            <div className="rounded-[1.2rem] border border-border/70 bg-muted/15 p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0">
                  <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">目录</div>
                  <div className="mt-2 flex flex-wrap items-center gap-1 text-sm">
                    {pathSegments.map((segment, index) => (
                      <div key={segment.path} className="flex items-center gap-1">
                        {index > 0 ? <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" /> : null}
                        <button
                          type="button"
                          className="rounded-full px-2 py-1 text-left text-foreground hover:bg-background"
                          onClick={() => setDirPath(segment.path)}
                        >
                          {segment.label}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button type="button" variant="outline" onClick={() => setDirPath(buildParentDir(dirPath))} disabled={dirPath === "/"}>
                    返回上级
                  </Button>
                  <Button type="button" variant="outline" onClick={() => void filesQ.refetch()} disabled={!accountId || filesQ.isFetching}>
                    <RefreshCw className={cn("h-4 w-4", filesQ.isFetching ? "animate-spin" : "")} />
                    刷新
                  </Button>
                </div>
              </div>
            </div>

            <div className="max-h-[28rem] overflow-y-auto rounded-[1.2rem] border border-border/70 bg-background">
              {filesQ.isLoading ? <div className="px-4 py-10 text-center text-sm text-muted-foreground">正在读取百度网盘目录...</div> : null}
              {filesQ.error ? <div className="px-4 py-6 text-sm text-destructive">{formatApiError(filesQ.error)}</div> : null}
              {!filesQ.isLoading && !filesQ.error && visibleItems.length <= 0 ? (
                <div className="px-4 py-10 text-center text-sm text-muted-foreground">这个目录里暂时没有可展示的文件。</div>
              ) : null}

              {!filesQ.isLoading &&
                !filesQ.error &&
                visibleItems.map((item) => {
                  const itemPath = normalizeBaiduPath(item.path)
                  const selected = Boolean(selectedItemsByPath[itemPath])
                  const selectable = isImportableItem(item)
                  return (
                    <div key={item.path} className="flex items-center gap-3 border-t border-border/60 px-4 py-3 first:border-t-0">
                      {item.isDir ? (
                        <>
                          <input
                            type="checkbox"
                            className="h-4 w-4 shrink-0"
                            checked={selected}
                            aria-label={`选择文件夹 ${item.name}`}
                            onChange={() => toggleItem(item)}
                          />
                          <button type="button" className="flex min-w-0 flex-1 items-center gap-3 text-left" onClick={() => setDirPath(item.path)}>
                            <div className="theme-icon-surface h-10 w-10 shrink-0">
                              <FolderOpen className="h-4 w-4" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="truncate text-sm font-medium text-foreground">{item.name}</div>
                              <div className="mt-1 text-xs text-muted-foreground">导入整个文件夹</div>
                            </div>
                          </button>
                          <Button type="button" variant="ghost" size="icon" onClick={() => setDirPath(item.path)} aria-label={`打开 ${item.name}`}>
                            <ChevronRight className="h-4 w-4" />
                          </Button>
                        </>
                      ) : (
                        <>
                          <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-3">
                            <input type="checkbox" className="h-4 w-4 shrink-0" checked={selected} disabled={!selectable} onChange={() => toggleItem(item)} />
                            <div className="theme-icon-surface h-10 w-10 shrink-0">
                              <FileVideo className="h-4 w-4" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="truncate text-sm font-medium text-foreground">{item.name}</div>
                              <div className="mt-1 text-xs text-muted-foreground">
                                {selectable ? `${formatDuration(item.durationMs)} · ${formatSize(item.sizeBytes)}` : "当前仅支持导入视频文件"}
                              </div>
                            </div>
                          </label>
                          <div className="text-xs text-muted-foreground">{item.mimeType ?? "mime 未知"}</div>
                        </>
                      )}
                    </div>
                  )
                })}
            </div>

            {selectedItems.length > 0 ? (
              <div className="space-y-2 text-xs text-muted-foreground">
                <div className="flex items-center justify-between gap-3">
                  <span>已选 {selectedItems.length} 项</span>
                  <button
                    type="button"
                    className="font-medium text-primary"
                    onClick={() =>
                      setSelectedItemsBySession((current) => {
                        const next = { ...current }
                        delete next[selectionSessionKey]
                        return next
                      })
                    }
                  >
                    清空
                  </button>
                </div>
                <div className="max-h-20 space-y-1 overflow-y-auto">
                  {selectedItems.slice(0, 5).map((item) => (
                    <div key={item.path} className="truncate">
                      {item.isDir ? "文件夹" : "视频"} · {item.path}
                    </div>
                  ))}
                  {selectedItems.length > 5 ? <div>还有 {selectedItems.length - 5} 项</div> : null}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)} disabled={importMutation.isPending}>
            取消
          </Button>
          <Button type="button" onClick={() => void onImport()} disabled={!accountId || selectedItems.length <= 0 || importMutation.isPending}>
            <HardDriveDownload className="h-4 w-4" />
            {importMutation.isPending ? "导入中..." : selectedItems.length > 0 ? `导入 ${selectedItems.length} 项` : "导入所选内容"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
