import { FolderTree, Waypoints, type LucideIcon } from "lucide-react"
import { useSearchParams } from "react-router-dom"

import { Button } from "@/ui/components/ui/button"
import { cn } from "@/ui/utils"
import { ObjectTreePage as LearningObjectTreePanel } from "@/views/trees/ObjectTreePage"
import { TaskTreePage as LearningTaskTreePanel } from "@/views/trees/TaskTreePage"

type StructureViewMode = "object" | "task"

function StructureViewModeButton(props: {
  mode: StructureViewMode
  label: string
  icon: LucideIcon
  active: boolean
  onSelect: (mode: StructureViewMode) => void
}) {
  const { mode, label, icon: Icon, active, onSelect } = props
  return (
    <Button
      type="button"
      variant="ghost"
      className={cn(
        "h-10 rounded-full border px-4 text-sm font-medium transition-colors",
        active
          ? "border-primary/15 bg-[hsl(var(--primary)/0.08)] text-foreground"
          : "border-border/60 bg-white text-muted-foreground hover:border-primary/15 hover:text-foreground",
      )}
      onClick={() => onSelect(mode)}
      aria-pressed={active}
    >
      <Icon className="h-4 w-4" />
      {label}
    </Button>
  )
}

export function StructureViewPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedMode = searchParams.get("view")
  const mode: StructureViewMode = requestedMode === "object" ? "object" : "task"

  function handleModeChange(nextMode: StructureViewMode) {
    if (nextMode === mode) return
    const nextSearchParams = new URLSearchParams(searchParams)
    nextSearchParams.set("view", nextMode)
    setSearchParams(nextSearchParams, { replace: true })
  }

  return (
    <div className="space-y-4">
      <section className="theme-card-main px-5 py-4">
        <div className="flex flex-wrap items-center gap-2" role="tablist" aria-label="结构视图类型切换">
          <StructureViewModeButton
            mode="task"
            label="学习任务树"
            icon={Waypoints}
            active={mode === "task"}
            onSelect={handleModeChange}
          />
          <StructureViewModeButton
            mode="object"
            label="学习对象树"
            icon={FolderTree}
            active={mode === "object"}
            onSelect={handleModeChange}
          />
        </div>
      </section>

      {mode === "object" ? <LearningObjectTreePanel /> : <LearningTaskTreePanel />}
    </div>
  )
}
