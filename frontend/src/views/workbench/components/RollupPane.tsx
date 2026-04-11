import { useEffect, useMemo, useState } from "react"
import { useQueries } from "@tanstack/react-query"
import { ChevronLeft, ChevronRight, ListChecks, Sparkles } from "lucide-react"
import { Link } from "react-router-dom"

import { getAggregationQueue, type Layer } from "@/ui/api/layers"
import { ApiError } from "@/ui/api/http"
import type { LearningTaskNode } from "@/ui/api/learningTaskNodes"
import { ContentEmptyState } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { cn } from "@/ui/utils"
import { formatLearningTaskNodeDisplayTitle } from "@/views/learningTasks/displayTitle"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function RollupTaskListItem({
  projectId,
  node,
  index,
  sourceLayerIndex,
}: {
  projectId: string
  node: LearningTaskNode
  index: number
  sourceLayerIndex: number
}) {
  return (
    <Link
      to={`/p/${projectId}/learning-task-nodes/${node.nodeId}`}
      className="group flex items-start gap-3 px-4 py-3 text-left transition-colors hover:[background:var(--theme-subtle-bg)]"
    >
      <span className="theme-icon-surface h-10 w-10 shrink-0 text-sm font-semibold">
        {index}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[15px] font-medium text-foreground">
          {formatLearningTaskNodeDisplayTitle(node.title, { sourceLayerIndex })}
        </span>
        <span className="mt-1 block text-xs text-muted-foreground">待推进 · 来源 L{sourceLayerIndex}</span>
      </span>
    </Link>
  )
}

export function RollupPane({
  projectId,
  layers,
  layersLoading,
  layersError,
  learningTaskNodesById,
  learningTaskNodesLoading,
  queueHasGate,
  actionableMissingGate,
  actionableMissingInstanceCount,
  isRollingUp,
  isThresholdRollUpUpdating,
  rollUpStrategy,
  onRollUp,
  onToggleThresholdRollUp,
  rollUpError,
  thresholdRollUpEnabledByLayerIndex,
}: {
  projectId: string
  layers: Layer[]
  layersLoading: boolean
  layersError: unknown
  learningTaskNodesById: Record<string, LearningTaskNode>
  learningTaskNodesLoading: boolean
  queueHasGate: boolean
  actionableMissingGate: boolean
  actionableMissingInstanceCount: number
  isRollingUp: boolean
  isThresholdRollUpUpdating: boolean
  rollUpStrategy: "MANUAL" | "THRESHOLD_AUTO" | "LEARNING_OBJECT_ISOMORPHIC"
  onRollUp: (layerIndex: number) => void
  onToggleThresholdRollUp: (layerIndex: number, enabled: boolean) => void
  rollUpError: unknown
  thresholdRollUpEnabledByLayerIndex: Record<number, boolean>
}) {
  const [selectedLayerIndex, setSelectedLayerIndex] = useState<number | null>(null)

  const aggregationQueueQs = useQueries({
    queries: layers.map((layer) => ({
      queryKey: ["aggQueue", projectId, layer.layerIndex],
      queryFn: () => getAggregationQueue(projectId, layer.layerIndex),
      enabled: !!projectId && Number.isFinite(layer.layerIndex),
      refetchInterval: 3000,
    })),
  })

  const candidateCountByLayerIndex = useMemo(
    () =>
      Object.fromEntries(
        layers.map((layer, index) => [layer.layerIndex, aggregationQueueQs[index]?.data?.currentNodeIds.length ?? 0]),
      ) as Record<number, number>,
    [aggregationQueueQs, layers],
  )

  useEffect(() => {
    if (layers.length === 0) {
      setSelectedLayerIndex(null)
      return
    }
    if (selectedLayerIndex !== null && layers.some((layer) => layer.layerIndex === selectedLayerIndex)) return
    const preferredLayer = layers.find((layer) => (candidateCountByLayerIndex[layer.layerIndex] ?? 0) > 0) ?? layers[0]
    setSelectedLayerIndex(preferredLayer.layerIndex)
  }, [candidateCountByLayerIndex, layers, selectedLayerIndex])

  const selectedLayerPosition = layers.findIndex((layer) => layer.layerIndex === selectedLayerIndex)
  const selectedLayer = selectedLayerPosition >= 0 ? layers[selectedLayerPosition] : null
  const selectedAggregationQueueQ = selectedLayerPosition >= 0 ? aggregationQueueQs[selectedLayerPosition] : null
  const selectedNodeIds = selectedAggregationQueueQ?.data?.currentNodeIds ?? []
  const selectedCandidateCount = selectedNodeIds.length
  const selectedSourceLayerIndex = selectedLayer ? Math.max(0, selectedLayer.layerIndex - 1) : 0
  const selectedThresholdRollUpEnabled = selectedLayer ? (thresholdRollUpEnabledByLayerIndex[selectedLayer.layerIndex] ?? true) : true
  const isThresholdStrategy = rollUpStrategy === "THRESHOLD_AUTO"
  const isIsomorphicStrategy = rollUpStrategy === "LEARNING_OBJECT_ISOMORPHIC"
  const actionLayerIndex = selectedLayer?.layerIndex ?? 0
  const strategyBannerTone = isIsomorphicStrategy
    ? "border-sky-200 bg-sky-50/80 text-sky-900"
    : !isThresholdStrategy
      ? "border-slate-200 bg-slate-50/80 text-slate-900"
      : selectedThresholdRollUpEnabled
        ? "border-emerald-200 bg-emerald-50/70 text-emerald-800"
        : "border-amber-200 bg-amber-50/80 text-amber-900"

  function goToLayer(position: number) {
    const nextLayer = layers[position]
    if (!nextLayer) return
    setSelectedLayerIndex(nextLayer.layerIndex)
  }

  return (
    <Card className="theme-card-main shrink-0" id="workbench-rollup-pane">
      <CardHeader className="theme-card-header flex-col gap-4 space-y-0 md:flex-row md:items-start md:justify-between">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <div className="theme-icon-surface h-10 w-10">
            <ListChecks className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <CardTitle>层推进与学习任务</CardTitle>
          </div>
        </div>

        <div className="flex w-full flex-col gap-2 md:w-auto md:flex-row">
          {isThresholdStrategy ? (
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                if (selectedLayer) onToggleThresholdRollUp(selectedLayer.layerIndex, !selectedThresholdRollUpEnabled)
              }}
              disabled={isThresholdRollUpUpdating || !selectedLayer}
              className="w-full whitespace-nowrap md:w-auto"
            >
              {isThresholdRollUpUpdating ? "保存中..." : selectedThresholdRollUpEnabled ? "禁止阈值上推" : "恢复阈值上推"}
            </Button>
          ) : null}
          <Button
            onClick={() => {
              if (isIsomorphicStrategy || selectedLayer) onRollUp(actionLayerIndex)
            }}
            disabled={
              queueHasGate ||
              actionableMissingGate ||
              isRollingUp ||
              (isIsomorphicStrategy ? false : !selectedLayer || selectedAggregationQueueQ?.isLoading || selectedCandidateCount === 0)
            }
            className="w-full whitespace-nowrap md:w-auto"
          >
            {isRollingUp ? "处理中..." : isIsomorphicStrategy ? "重新扫描对象树推进" : "上推"}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-5">
        {selectedLayer ? (
          <div
            className={cn(
              "rounded-2xl border p-4 text-sm",
              strategyBannerTone,
            )}
          >
            {isIsomorphicStrategy
              ? "当前项目使用学习对象树同构上推。只要某个对象节点下的实例都已有活跃复述点，系统就会把它推进到对应层级。"
              : !isThresholdStrategy
                ? "当前项目使用手动上推模式。系统不会自动按阈值推进，你可以在合适的时候手动触发。"
                : selectedThresholdRollUpEnabled
              ? `L${selectedLayer.layerIndex} 当前已开启阈值自动上推。达到节点数或复述点阈值后，系统会自动进入聚合周期。`
              : `L${selectedLayer.layerIndex} 当前已关闭阈值自动上推。达到阈值后不会自动上推，你仍然可以手动点击“上推”。`}
          </div>
        ) : null}

        {queueHasGate ? (
          <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm">
            门禁：队列非空时暂不能上推。请先完成当前复习任务，再继续层级推进。
          </div>
        ) : null}
        {actionableMissingGate ? (
          <div className="rounded-2xl border border-amber-300/70 bg-amber-50 p-4 text-sm text-amber-900">
            门禁：当前还有 {actionableMissingInstanceCount} 个待迁移的缺失实例。请先去项目设置完成修复，再继续推进结构。
          </div>
        ) : null}

        {layersLoading ? <div className="theme-subtle-surface px-4 py-4 text-sm">正在加载层级任务...</div> : null}
        {layersError ? <p className="text-sm text-destructive">{formatApiError(layersError)}</p> : null}

        {!layersLoading && !layersError && layers.length === 0 ? (
          <ContentEmptyState
            icon={Sparkles}
            title={isIsomorphicStrategy ? "当前还没有对象镜像层" : "当前还没有层配置"}
            message={isIsomorphicStrategy ? "继续学习后，系统会按学习对象树自动生成对应层级；你也可以点击上方按钮重新扫描。" : "等学习任务逐步形成层级结构后，这里就会出现可推进的层。"}
          />
        ) : null}

        {!layersLoading && !layersError && layers.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {layers.map((layer) => {
              const isActive = layer.layerIndex === selectedLayer?.layerIndex
              const candidateCount = candidateCountByLayerIndex[layer.layerIndex] ?? 0
              return (
                <button
                  key={layer.layerId}
                  type="button"
                  onClick={() => setSelectedLayerIndex(layer.layerIndex)}
                  aria-current={isActive ? "true" : undefined}
                  className={cn(
                    "flex h-10 min-w-[3.25rem] items-center justify-center rounded-xl border px-3 text-sm font-semibold transition-all",
                    "[border-color:var(--theme-soft-border)] [background:var(--theme-soft-bg)] text-[color:var(--theme-subtle-text)] hover:border-primary/25 hover:text-primary",
                    isActive && "border-primary/20 text-primary ring-2 ring-primary/25 ring-offset-2 ring-offset-background",
                  )}
                  title={`L${layer.layerIndex}${candidateCount > 0 ? `，${candidateCount} 项待推进` : "，当前无待推进任务"}`}
                  aria-label={`L${layer.layerIndex}${candidateCount > 0 ? `，${candidateCount} 项待推进` : "，当前无待推进任务"}`}
                >
                  {`L${layer.layerIndex}`}
                </button>
              )
            })}
          </div>
        ) : null}

        {selectedLayer ? (
          <div className="grid gap-3">
            <div className="relative overflow-visible">
              <div className="sr-only" aria-live="polite">
                {selectedAggregationQueueQ?.isLoading
                  ? `正在加载 L${selectedLayer.layerIndex} 的待推进任务`
                  : `当前层 L${selectedLayer.layerIndex}，共 ${selectedCandidateCount} 项待推进学习任务`}
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="absolute inset-y-0 -left-4 z-10 h-auto w-4 rounded-none border-0 bg-transparent p-0 text-[color:var(--theme-subtle-text)] shadow-none outline-none hover:bg-transparent hover:text-foreground focus-visible:ring-0 focus-visible:ring-offset-0 sm:-left-5 sm:w-5"
                onClick={() => goToLayer(selectedLayerPosition - 1)}
                disabled={selectedLayerPosition <= 0}
                aria-label="上一层"
                title="上一层"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="absolute inset-y-0 -right-4 z-10 h-auto w-4 rounded-none border-0 bg-transparent p-0 text-[color:var(--theme-subtle-text)] shadow-none outline-none hover:bg-transparent hover:text-foreground focus-visible:ring-0 focus-visible:ring-offset-0 sm:-right-5 sm:w-5"
                onClick={() => goToLayer(selectedLayerPosition + 1)}
                disabled={selectedLayerPosition < 0 || selectedLayerPosition >= layers.length - 1}
                aria-label="下一层"
                title="下一层"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>

              <div className="theme-status-surface rounded-[1.15rem] border border-[color:var(--theme-status-border)] px-4 py-4 sm:px-5">
                {selectedAggregationQueueQ?.isLoading ? (
                  <div className="theme-subtle-surface px-4 py-3 text-sm">
                    正在读取这一层的待推进学习任务。
                  </div>
                ) : selectedCandidateCount > 0 ? (
                  <div className="overflow-hidden rounded-[1.1rem] border [border-color:var(--theme-soft-border)] [background:var(--theme-soft-bg)] divide-y [divide-color:var(--theme-soft-border)]">
                    {selectedNodeIds.map((nodeId, index) => {
                      const node = learningTaskNodesById[nodeId]
                      if (!node) {
                        return (
                          <div key={nodeId} className="px-4 py-3 text-sm text-muted-foreground">
                            {learningTaskNodesLoading ? "正在加载学习任务..." : "节点信息同步中..."}
                          </div>
                        )
                      }
                      return (
                        <RollupTaskListItem
                          key={nodeId}
                          projectId={projectId}
                          node={node}
                          index={index + 1}
                          sourceLayerIndex={selectedSourceLayerIndex}
                        />
                      )
                    })}
                  </div>
                ) : (
                  <ContentEmptyState title="这一层当前没有待推进任务" message="可以先继续录入复述点或完成复习，随后再回来推进这一层。" />
                )}
              </div>
            </div>

            {selectedAggregationQueueQ?.error ? <p className="text-sm text-destructive">{formatApiError(selectedAggregationQueueQ.error)}</p> : null}
          </div>
        ) : null}

        {rollUpError ? <p className="text-sm text-destructive">{formatApiError(rollUpError)}</p> : null}
      </CardContent>
    </Card>
  )
}
