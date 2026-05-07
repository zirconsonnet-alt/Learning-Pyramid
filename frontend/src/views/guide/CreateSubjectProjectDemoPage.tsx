import { CheckCircle2, FolderOpen, ListChecks, Plus, RotateCcw, Settings2 } from "lucide-react"
import { useState } from "react"

import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { completeGuideWalkthroughStep } from "@/ui/guideWalkthrough/guideWalkthroughController"
import { cn } from "@/ui/utils"

type DemoStage = "subject-center" | "subject-dashboard" | "project-settings"
type DirectoryStatus = "missing" | "authorized" | "imported"

const SAMPLE_TREE = ["第 1 章 向量空间", "01 向量与线性组合.mp4", "02 基与维数.mp4"]

export function CreateSubjectProjectDemoPage() {
  const [stage, setStage] = useState<DemoStage>("subject-center")
  const [subjectTitle, setSubjectTitle] = useState("机器学习入门")
  const [subjectCreated, setSubjectCreated] = useState(false)
  const [directoryStatus, setDirectoryStatus] = useState<DirectoryStatus>("missing")

  function resetDemo() {
    setStage("subject-center")
    setSubjectTitle("机器学习入门")
    setSubjectCreated(false)
    setDirectoryStatus("missing")
  }

  function openSubjectDialog() {
    completeGuideWalkthroughStep("create-subject")
  }

  function submitSubject() {
    setSubjectCreated(true)
    setStage("subject-dashboard")
    completeGuideWalkthroughStep("create-subject-submit")
  }

  function openProjectSettings() {
    setStage("project-settings")
    completeGuideWalkthroughStep("choose-project")
  }

  function authorizeDirectory() {
    setDirectoryStatus("authorized")
    completeGuideWalkthroughStep("authorize-directory")
  }

  function importDirectory() {
    setDirectoryStatus("imported")
    completeGuideWalkthroughStep("import-directory")
  }

  return (
    <div className="space-y-5">
      <section className="theme-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-sm font-semibold text-foreground">创建学科项目引导演示</div>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              这里是一次性的虚拟演示环境，只模拟创建学科、打开项目设置、授权目录和同步内容，不会创建真实学科或项目。
            </p>
          </div>
          <Button type="button" variant="outline" onClick={resetDemo}>
            <RotateCcw className="h-4 w-4" />
            重新演示
          </Button>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="xl:sticky xl:top-28 xl:self-start">
          <Card className="theme-card-main">
            <CardHeader className="theme-card-header">
              <CardTitle>演示进度</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 pt-4 text-sm">
              {[
                ["创建学科", subjectCreated],
                ["打开项目设置", stage === "project-settings" || directoryStatus !== "missing"],
                ["授权目录", directoryStatus === "authorized" || directoryStatus === "imported"],
                ["同步内容", directoryStatus === "imported"],
              ].map(([label, done]) => (
                <div key={String(label)} className="flex items-center gap-2">
                  <CheckCircle2 className={cn("h-4 w-4", done ? "text-emerald-600" : "text-muted-foreground/50")} />
                  <span className={done ? "text-foreground" : "text-muted-foreground"}>{label}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </aside>

        <section className="space-y-5">
          <Card className="theme-card-main">
            <CardHeader className="theme-card-header">
              <div className="flex items-center justify-between gap-3">
                <CardTitle>学科中心</CardTitle>
                <Button type="button" data-guide-tour="new-subject-button" onClick={openSubjectDialog}>
                  <Plus className="h-4 w-4" />
                  新建学科
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 pt-4">
              <div data-guide-tour="create-subject-submit" className="rounded-[1.25rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] p-4">
                <div className="text-sm font-semibold text-foreground">创建新学科</div>
                <label className="mt-4 block space-y-2">
                  <span className="text-sm font-medium text-foreground">学科标题</span>
                  <input
                    value={subjectTitle}
                    onChange={(event) => setSubjectTitle(event.target.value)}
                    className="h-11 w-full rounded-xl border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] px-3 text-sm outline-none transition focus:border-primary/25"
                  />
                </label>
                <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                  <p className="text-sm leading-6 text-muted-foreground">演示提交只会更新当前页面状态，不会写入真实学科中心。</p>
                  <Button type="button" onClick={submitSubject} disabled={!subjectTitle.trim()}>
                    创建学科
                  </Button>
                </div>
              </div>

              {subjectCreated ? (
                <div className="rounded-[1.25rem] border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
                  “{subjectTitle.trim()}” 已在本次演示中创建，并自动带出一个默认网课项目。
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card className="theme-card-main">
            <CardHeader className="theme-card-header">
              <CardTitle>学科总面板</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 pt-4">
              <div className={cn("rounded-[1.25rem] border p-4", subjectCreated ? "border-primary/20 bg-primary/10" : "border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)]")}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-foreground">线性代数视频课</div>
                    <div className="mt-1 text-xs text-muted-foreground">默认网课项目 · 只存在于本次演示</div>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    data-guide-tour="subject-project-settings-entry"
                    onClick={openProjectSettings}
                    disabled={!subjectCreated}
                  >
                    <Settings2 className="h-4 w-4" />
                    项目设置
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="theme-card-main">
            <CardHeader className="theme-card-header">
              <CardTitle>项目设置</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 pt-4">
              <div className={cn("rounded-[1.25rem] border p-4", stage === "project-settings" ? "border-primary/20 bg-primary/10" : "border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)]")}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                      <FolderOpen className="h-4 w-4" />
                      本地素材目录
                    </div>
                    <div className="mt-2 text-sm leading-6 text-muted-foreground">
                      当前状态：
                      {directoryStatus === "missing" ? "未授权" : directoryStatus === "authorized" ? "已授权，等待同步" : "已同步 3 个演示条目"}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      data-guide-tour="authorize-directory-button"
                      onClick={authorizeDirectory}
                      disabled={stage !== "project-settings"}
                    >
                      选择并授权目录
                    </Button>
                    <Button
                      type="button"
                      data-guide-tour="import-directory-button"
                      onClick={importDirectory}
                      disabled={stage !== "project-settings" || directoryStatus === "missing"}
                    >
                      同步目录内容
                    </Button>
                  </div>
                </div>

                {directoryStatus === "imported" ? (
                  <div className="mt-4 rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-3">
                    <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                      <ListChecks className="h-4 w-4" />
                      演示导入结果
                    </div>
                    <div className="space-y-1.5">
                      {SAMPLE_TREE.map((item) => (
                        <div key={item} className="rounded-lg bg-[color:var(--theme-soft-bg)] px-3 py-2 text-sm text-foreground">
                          {item}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  )
}
