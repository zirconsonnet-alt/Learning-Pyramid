import { BookOpen, FolderPlus, Plus } from "lucide-react"

import { GUIDE_SCENE_FIXTURES } from "./guideSceneFixtures"

type SubjectProjectGuideDemoProps = {
  state: "create-subject" | "project-choice"
  highlight?: string
}

export function SubjectProjectGuideDemo({ state, highlight }: SubjectProjectGuideDemoProps) {
  const fixture = GUIDE_SCENE_FIXTURES.subjectProject
  const highlightClass = "ring-2 ring-primary ring-offset-2 ring-offset-background"

  return (
    <div className="grid gap-4 md:grid-cols-[1fr_1.15fr]">
      <div className="rounded-lg border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="text-sm font-semibold text-foreground">学科中心</div>
          <button
            type="button"
            className={`inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-medium text-primary-foreground ${highlight === "new-subject-button" ? highlightClass : ""}`}
          >
            <Plus className="h-3.5 w-3.5" />
            新建学科
          </button>
        </div>
        <div className="rounded-lg border border-dashed border-[color:var(--theme-soft-border)] bg-[color:var(--theme-subtle-bg)] p-4">
          <BookOpen className="mb-3 h-5 w-5 text-primary" />
          <div className="text-sm font-medium text-foreground">{fixture.subjectTitle}</div>
          <div className="mt-1 text-xs leading-5 text-[color:var(--theme-subtle-text)]">先创建学科，再进入学科总面板选择项目。</div>
        </div>
      </div>

      <div className="rounded-lg border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-4">
        <div className="mb-3 text-sm font-semibold text-foreground">学科总面板</div>
        <div className={`rounded-lg border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] p-4 ${highlight === "default-project-card" ? highlightClass : ""}`}>
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <FolderPlus className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <div className="text-sm font-medium text-foreground">{fixture.projectTitle}</div>
              <div className="mt-1 text-xs text-[color:var(--theme-subtle-text)]">{fixture.projectType}</div>
              {state === "create-subject" ? <p className="mt-3 text-xs leading-5 text-[color:var(--theme-warm-text)]">{fixture.setupNotice}</p> : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
