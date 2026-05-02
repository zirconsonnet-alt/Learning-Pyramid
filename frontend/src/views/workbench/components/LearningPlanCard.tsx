import { useEffect, useMemo, useState } from "react"

import type { LearningObjectNode } from "@/ui/api/learningObjects"
import { Button } from "@/ui/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/ui/components/ui/dialog"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import type { LearningPlanEvaluation } from "@/ui/learningPlans/learningPlanEvaluation"
import {
  addDaysToDateKey,
  makeLearningPlanId,
  normalizePlanTargetDays,
  type LearningPlan,
  type LearningPlanTargetKind,
} from "@/ui/store/learningPlanStore"
import { cn } from "@/ui/utils"

type LearningPlanCardProps = {
  projectId: string
  todayDateKey: string
  plan: LearningPlan | null
  evaluation: LearningPlanEvaluation | null
  nodes: LearningObjectNode[]
  onArchive: (planId: string) => void
  onSave: (plan: LearningPlan) => void
}

function formatPercent(value: number) {
  if (!Number.isFinite(value)) return "0%"
  return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`
}

function formatMaterialCount(evaluation: LearningPlanEvaluation) {
  if (evaluation.totalLeafCount <= 0) return "范围还没有可统计的末级内容"
  return `${evaluation.completedLeafCount}/${evaluation.totalLeafCount} 个末级内容已有学习痕迹`
}

function feasibilityLabel(feasibility: LearningPlanEvaluation["feasibility"]) {
  if (feasibility === "finished") return "已接近完成"
  if (feasibility === "very_easy") return "可能提前"
  if (feasibility === "hard") return "压力偏大"
  if (feasibility === "overdue") return "已经到期"
  if (feasibility === "unknown") return "继续采样"
  return "节奏正常"
}

function selectablePlanNodes(nodes: LearningObjectNode[]) {
  return nodes
    .filter((node) => node.kind === "container" || node.parentId === null)
    .sort((left, right) => left.title.localeCompare(right.title, "zh-Hans-CN"))
    .slice(0, 120)
}

function PlanEditorDialog({
  open,
  onOpenChange,
  projectId,
  todayDateKey,
  existingPlan,
  nodes,
  onSave,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  projectId: string
  todayDateKey: string
  existingPlan: LearningPlan | null
  nodes: LearningObjectNode[]
  onSave: (plan: LearningPlan) => void
}) {
  const [title, setTitle] = useState("")
  const [targetDays, setTargetDays] = useState("14")
  const [targetKind, setTargetKind] = useState<LearningPlanTargetKind>("PROJECT")
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([])

  useEffect(() => {
    setTitle(existingPlan?.title ?? "完成当前学习目标")
    setTargetDays(String(existingPlan?.targetDays ?? 14))
    setTargetKind(existingPlan?.targetKind ?? "PROJECT")
    setSelectedNodeIds(existingPlan?.learningObjectNodeIds ?? [])
  }, [existingPlan, open])

  const options = useMemo(() => selectablePlanNodes(nodes), [nodes])
  const normalizedDays = normalizePlanTargetDays(Number.parseInt(targetDays, 10))
  const selectedNodeSet = new Set(selectedNodeIds)

  function toggleNode(nodeId: string) {
    setSelectedNodeIds((current) =>
      current.includes(nodeId) ? current.filter((item) => item !== nodeId) : [...current, nodeId],
    )
  }

  function save() {
    const basePlan = existingPlan
    const next: LearningPlan = {
      planId: basePlan?.planId ?? makeLearningPlanId(projectId),
      projectId,
      title: title.trim() || "完成当前学习目标",
      targetKind,
      learningObjectNodeIds: targetKind === "LEARNING_OBJECT_NODES" ? selectedNodeIds : [],
      targetDays: normalizedDays,
      createdDateKey: basePlan?.createdDateKey ?? todayDateKey,
      dueDateKey: addDaysToDateKey(basePlan?.createdDateKey ?? todayDateKey, normalizedDays - 1),
      archivedAt: basePlan?.archivedAt ?? null,
      updatedAt: Date.now(),
    }
    onSave(next)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{existingPlan ? "编辑学习计划" : "创建学习计划"}</DialogTitle>
          <DialogDescription>
            定一个 N 天内要完成的范围。系统会按工作台里的学习痕迹和历史有效学习时长持续评估它是否现实。
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          <div className="grid gap-2">
            <Label htmlFor="learning-plan-title">计划目标</Label>
            <Input id="learning-plan-title" value={title} onChange={(event) => setTitle(event.target.value)} />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="learning-plan-days">完成期限</Label>
            <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
              <Input
                id="learning-plan-days"
                inputMode="numeric"
                value={targetDays}
                onChange={(event) => setTargetDays(event.target.value)}
              />
              <div className="text-sm text-muted-foreground">从开始日算起 {normalizedDays} 天，到 {addDaysToDateKey(existingPlan?.createdDateKey ?? todayDateKey, normalizedDays - 1)}</div>
            </div>
          </div>

          <div className="grid gap-2">
            <Label>目标范围</Label>
            <div className="grid gap-2 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => setTargetKind("PROJECT")}
                className={cn(
                  "rounded-[1rem] border px-4 py-3 text-left text-sm transition-colors",
                  targetKind === "PROJECT" ? "border-primary/30 bg-primary/10 text-foreground" : "border-border/70 bg-background text-muted-foreground",
                )}
              >
                <div className="font-semibold">整门学科 / 当前入口</div>
                <div className="mt-1 text-xs leading-5">把当前工作台能统计到的所有学习对象作为计划范围。</div>
              </button>
              <button
                type="button"
                onClick={() => setTargetKind("LEARNING_OBJECT_NODES")}
                className={cn(
                  "rounded-[1rem] border px-4 py-3 text-left text-sm transition-colors",
                  targetKind === "LEARNING_OBJECT_NODES" ? "border-primary/30 bg-primary/10 text-foreground" : "border-border/70 bg-background text-muted-foreground",
                )}
              >
                <div className="font-semibold">学习对象节点集合</div>
                <div className="mt-1 text-xs leading-5">勾选章节、目录或节点；系统会把它们下面的末级内容纳入计划。</div>
              </button>
            </div>
          </div>

          {targetKind === "LEARNING_OBJECT_NODES" ? (
            <div className="max-h-72 space-y-2 overflow-y-auto rounded-[1rem] border border-border/70 bg-muted/15 p-3">
              {options.length === 0 ? (
                <div className="px-2 py-3 text-sm text-muted-foreground">当前还没有可选择的学习对象节点。可以先按“整门学科”创建计划。</div>
              ) : null}
              {options.map((node) => (
                <label key={node.nodeId} className="flex cursor-pointer items-start gap-3 rounded-xl px-3 py-2 text-sm hover:bg-background">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={selectedNodeSet.has(node.nodeId)}
                    onChange={() => toggleNode(node.nodeId)}
                  />
                  <span>
                    <span className="font-medium text-foreground">{node.title}</span>
                    <span className="mt-1 block text-xs text-muted-foreground">{node.kind === "container" ? "目录节点" : "末级内容"}</span>
                  </span>
                </label>
              ))}
            </div>
          ) : null}
        </div>

        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>取消</Button>
          <Button onClick={save} disabled={targetKind === "LEARNING_OBJECT_NODES" && selectedNodeIds.length === 0}>保存计划</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function LearningPlanCard(props: LearningPlanCardProps) {
  const { projectId, todayDateKey, plan, evaluation, nodes, onArchive, onSave } = props
  const [editorOpen, setEditorOpen] = useState(false)

  return (
    <section className="rounded-[1.15rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3.5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[12px] font-medium text-muted-foreground">学习计划</div>
          <div className="mt-1 text-[17px] font-semibold tracking-[-0.02em] text-[color:var(--theme-soft-text-strong)]">
            {plan ? plan.title : "还没有计划"}
          </div>
        </div>
        {evaluation ? <span className="theme-meta-strong">{feasibilityLabel(evaluation.feasibility)}</span> : null}
      </div>

      {plan && evaluation ? (
        <div className="mt-3 space-y-3">
          <div>
            <div className="flex items-center justify-between gap-3 text-[12px] text-muted-foreground">
              <span>当前 {formatPercent(evaluation.progressRatio)}</span>
              <span>计划应到 {formatPercent(evaluation.expectedRatio)}</span>
            </div>
            <div className="theme-progress-track mt-2 h-2 overflow-hidden rounded-full">
              <div className="theme-progress-fill h-full rounded-full transition-[width] duration-500" style={{ width: formatPercent(evaluation.progressRatio) }} />
            </div>
          </div>
          <p className="text-[12px] leading-6 text-muted-foreground">{evaluation.summary}</p>
          <p className="text-[12px] leading-6 text-muted-foreground">{evaluation.dailySummary}</p>
          <div className="text-[12px] text-muted-foreground">{formatMaterialCount(evaluation)}</div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="outline" onClick={() => setEditorOpen(true)}>编辑计划</Button>
            <Button type="button" size="sm" variant="ghost" className="text-muted-foreground" onClick={() => onArchive(plan.planId)}>归档</Button>
          </div>
        </div>
      ) : (
        <div className="mt-3 space-y-3">
          <p className="text-[12px] leading-6 text-muted-foreground">
            规定 N 天内完成整门学科或一组学习对象。学习一段时间后，这里会判断它很难、正常，还是可能提前完成。
          </p>
          <Button type="button" size="sm" onClick={() => setEditorOpen(true)}>创建计划</Button>
        </div>
      )}

      <PlanEditorDialog
        open={editorOpen}
        onOpenChange={setEditorOpen}
        projectId={projectId}
        todayDateKey={todayDateKey}
        existingPlan={plan}
        nodes={nodes}
        onSave={onSave}
      />
    </section>
  )
}
