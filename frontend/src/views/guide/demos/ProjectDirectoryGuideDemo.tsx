import { CheckCircle2, FolderOpen, UploadCloud } from "lucide-react"

import { GUIDE_SCENE_FIXTURES } from "./guideSceneFixtures"

type ProjectDirectoryGuideDemoProps = {
  state: "unbound" | "imported"
  highlight?: string
}

export function ProjectDirectoryGuideDemo({ state, highlight }: ProjectDirectoryGuideDemoProps) {
  const fixture = GUIDE_SCENE_FIXTURES.projectDirectory
  const highlightClass = "ring-2 ring-primary ring-offset-2 ring-offset-background"

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-4">
        <div className="mb-3 text-sm font-semibold text-foreground">项目设置 · {fixture.projectTitle}</div>
        <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-center">
          <div>
            <div className="text-sm font-medium text-foreground">本地素材目录</div>
            <div className="mt-1 text-xs leading-5 text-[color:var(--theme-subtle-text)]">
              当前状态：{state === "imported" ? "已授权" : fixture.permissionState}
            </div>
          </div>
          <button
            type="button"
            className={`inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-medium text-primary-foreground ${highlight === "authorize-button" ? highlightClass : ""}`}
          >
            <FolderOpen className="h-3.5 w-3.5" />
            选择并授权目录
          </button>
        </div>
      </div>

      <div className="rounded-lg border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-4">
        <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-center">
          <div>
            <div className="text-sm font-medium text-foreground">内容目录导入</div>
            <div className="mt-1 text-xs leading-5 text-[color:var(--theme-subtle-text)]">
              示例目录：{fixture.sampleDirectoryLabel}
            </div>
          </div>
          <button
            type="button"
            className={`inline-flex items-center justify-center gap-1.5 rounded-lg border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-3 py-2 text-xs font-medium text-foreground ${highlight === "import-button" ? highlightClass : ""}`}
          >
            <UploadCloud className="h-3.5 w-3.5" />
            导入内容目录
          </button>
        </div>
        {state === "imported" ? (
          <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-3 text-xs leading-5 text-emerald-800">
            <CheckCircle2 className="mr-1 inline h-3.5 w-3.5" />
            已导入 {fixture.importedCount} 个内容实例，工作台左侧会显示学习对象树。
          </div>
        ) : null}
      </div>
    </div>
  )
}
