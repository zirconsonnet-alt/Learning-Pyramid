import { ListTree, PlayCircle, Save } from "lucide-react"

import { GUIDE_SCENE_FIXTURES } from "./guideSceneFixtures"

type WorkbenchRecallGuideDemoProps = {
  state: "editing-recall"
  highlight?: string
}

export function WorkbenchRecallGuideDemo({ highlight }: WorkbenchRecallGuideDemoProps) {
  const fixture = GUIDE_SCENE_FIXTURES.workbenchRecall
  const highlightClass = "ring-2 ring-primary ring-offset-2 ring-offset-background"

  return (
    <div className="grid gap-4 lg:grid-cols-[0.9fr_1.25fr]">
      <aside className={`rounded-lg border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-4 ${highlight === "object-tree" ? highlightClass : ""}`}>
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
          <ListTree className="h-4 w-4 text-primary" />
          学习对象
        </div>
        <div className="rounded-lg bg-[color:var(--theme-subtle-bg)] px-3 py-2 text-sm text-foreground">{fixture.selectedObject}</div>
      </aside>

      <section className="space-y-3 rounded-lg border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-4">
        <div className="flex items-center justify-between rounded-lg bg-slate-900 px-3 py-3 text-white">
          <div className="flex items-center gap-2 text-sm">
            <PlayCircle className="h-4 w-4" />
            视频暂停在 {fixture.currentTime}
          </div>
          <button type="button" className="rounded-md bg-white/10 px-2 py-1 text-xs">
            添加复述点
          </button>
        </div>
        <div className={`space-y-3 rounded-lg border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] p-3 ${highlight === "recall-form" ? highlightClass : ""}`}>
          <div>
            <div className="mb-1 text-xs font-medium text-[color:var(--theme-subtle-text)]">问题</div>
            <div className="rounded-md bg-[color:var(--theme-card-main-bg)] px-3 py-2 text-sm text-foreground">{fixture.recallQuestion}</div>
          </div>
          <div>
            <div className="mb-1 text-xs font-medium text-[color:var(--theme-subtle-text)]">答案</div>
            <div className="rounded-md bg-[color:var(--theme-card-main-bg)] px-3 py-2 text-sm leading-6 text-foreground">{fixture.recallAnswer}</div>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-xs text-[color:var(--theme-subtle-text)]">学习任务标题：{fixture.taskTitle}</div>
            <button type="button" className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-medium text-primary-foreground">
              <Save className="h-3.5 w-3.5" />
              提交学习
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}
