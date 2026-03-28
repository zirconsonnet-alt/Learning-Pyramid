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
      className="group flex items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-[#fbfdff]"
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[#f3f7fc] text-sm font-semibold text-[#2f5d93]">
        {index}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[15px] font-medium text-[#21384d]">
          {formatLearningTaskNodeDisplayTitle(node.title, { sourceLayerIndex })}
        </span>
        <span className="mt-1 block text-xs text-[#70839a]">待推进 · 来源 L{sourceLayerIndex}</span>
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
  isRollingUp,
  onRollUp,
  rollUpError,
}: {
  projectId: string
  layers: Layer[]
  layersLoading: boolean
  layersError: unknown
  learningTaskNodesById: Record<string, LearningTaskNode>
  learningTaskNodesLoading: boolean
  queueHasGate: boolean
  isRollingUp: boolean
  onRollUp: (layerIndex: number) => void
  rollUpError: unknown
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

  function goToLayer(position: number) {
    const nextLayer = layers[position]
    if (!nextLayer) return
    setSelectedLayerIndex(nextLayer.layerIndex)
  }

  return (
    <Card className="theme-card-main shrink-0" id="workbench-rollup-pane">
      <CardHeader className="theme-card-header flex-col gap-4 space-y-0 md:flex-row md:items-start md:justify-between">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[#e2e8f0] bg-[#f5f7fa] text-primary">
            <ListChecks className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <CardTitle>层推进与学习任务</CardTitle>
          </div>
        </div>

        <Button
          onClick={() => {
            if (selectedLayer) onRollUp(selectedLayer.layerIndex)
          }}
          disabled={queueHasGate || isRollingUp || !selectedLayer || selectedAggregationQueueQ?.isLoading || selectedCandidateCount === 0}
          className="w-full whitespace-nowrap md:w-auto"
        >
          {isRollingUp ? "上推中..." : "上推"}
        </Button>
      </CardHeader>

      <CardContent className="space-y-4 pt-5">
        {queueHasGate ? (
          <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm">
            门禁：队列非空时暂不能上推。请先完成当前复习任务，再继续层级推进。
          </div>
        ) : null}

        {layersLoading ? <div className="rounded-[1.15rem] bg-[#f6f8fb] px-4 py-4 text-sm text-[#647589]">正在加载层级任务...</div> : null}
        {layersError ? <p className="text-sm text-destructive">{formatApiError(layersError)}</p> : null}

        {!layersLoading && !layersError && layers.length === 0 ? (
          <ContentEmptyState icon={Sparkles} title="当前还没有层配置" message="等学习任务逐步形成层级结构后，这里就会出现可推进的层。" />
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
                    "border-[#d9e2eb] bg-white text-[#5e738b] hover:border-primary/25 hover:text-primary",
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
                className="absolute inset-y-0 -left-4 z-10 h-auto w-4 rounded-none border-0 bg-transparent p-0 text-[#5e738b] shadow-none outline-none hover:bg-transparent hover:text-slate-900 focus-visible:ring-0 focus-visible:ring-offset-0 sm:-left-5 sm:w-5"
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
                className="absolute inset-y-0 -right-4 z-10 h-auto w-4 rounded-none border-0 bg-transparent p-0 text-[#5e738b] shadow-none outline-none hover:bg-transparent hover:text-slate-900 focus-visible:ring-0 focus-visible:ring-offset-0 sm:-right-5 sm:w-5"
                onClick={() => goToLayer(selectedLayerPosition + 1)}
                disabled={selectedLayerPosition < 0 || selectedLayerPosition >= layers.length - 1}
                aria-label="下一层"
                title="下一层"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>

              <div className="theme-status-surface rounded-[1.15rem] border border-[#e2e8ef] px-4 py-4 sm:px-5">
                {selectedAggregationQueueQ?.isLoading ? (
                  <div className="rounded-[1.1rem] border border-[#e3e9f1] bg-[#fbfcfe] px-4 py-3 text-sm text-[#6f7f93]">
                    正在读取这一层的待推进学习任务。
                  </div>
                ) : selectedCandidateCount > 0 ? (
                  <div className="overflow-hidden rounded-[1.1rem] border border-[#e3e9f1] bg-white/80 divide-y divide-[#e3e9f1]">
                    {selectedNodeIds.map((nodeId, index) => {
                      const node = learningTaskNodesById[nodeId]
                      if (!node) {
                        return (
                          <div key={nodeId} className="px-4 py-3 text-sm text-[#6f7f93]">
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
