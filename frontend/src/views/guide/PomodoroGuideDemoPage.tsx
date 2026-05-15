import { AlarmClock, CalendarClock, CheckCircle2, Laptop, Play, Plus } from "lucide-react"
import { useState } from "react"

import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { completeGuideWalkthroughStep } from "@/ui/guideWalkthrough/guideWalkthroughController"
import { cn } from "@/ui/utils"

export function PomodoroGuideDemoPage() {
  const [enabled, setEnabled] = useState(false)
  const [planCreated, setPlanCreated] = useState(false)
  const [projectBound, setProjectBound] = useState(false)
  const [webReady, setWebReady] = useState(false)

  function enableClock() {
    setEnabled(true)
    completeGuideWalkthroughStep("pomodoro-enable-clock")
  }

  function createPlan() {
    setPlanCreated(true)
    completeGuideWalkthroughStep("pomodoro-create-plan")
  }

  function bindProject() {
    setProjectBound(true)
    completeGuideWalkthroughStep("pomodoro-bind-project")
  }

  function enterWeb() {
    setWebReady(true)
    completeGuideWalkthroughStep("pomodoro-enter-web")
  }

  return (
    <div className="space-y-5">
      <section className="theme-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-sm font-semibold text-foreground">番茄钟引导演示</div>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              这里用虚拟计划演示开启番茄钟、设定计划、绑定项目，以及番茄开始后登录网页进入工作台的完整路径。
            </p>
          </div>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="space-y-5 xl:sticky xl:top-28 xl:self-start">
          <Card className="theme-card-main">
            <CardHeader className="theme-card-header">
              <CardTitle>演示进度</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 pt-4 text-sm">
              {[
                ["开启番茄钟", enabled],
                ["设定计划", planCreated],
                ["绑定项目", projectBound],
                ["网页就绪", webReady],
              ].map(([label, done]) => (
                <div key={String(label)} className="flex items-center gap-2">
                  <CheckCircle2 className={cn("h-4 w-4", done ? "text-emerald-600" : "text-muted-foreground/50")} />
                  <span className={done ? "text-foreground" : "text-muted-foreground"}>{label}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </aside>

        <section className="grid gap-5 xl:grid-cols-2">
          <Card className="theme-card-main">
            <CardHeader className="theme-card-header">
              <CardTitle className="flex items-center gap-2">
                <AlarmClock className="h-5 w-5" />
                总开关
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 pt-4">
              <div className="rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3 text-sm leading-6 text-muted-foreground">
                先打开番茄钟，总开关开启后计划才会按时间生效。
              </div>
              <button
                type="button"
                data-guide-tour="pomodoro-session-status"
                className={cn(
                  "flex w-full items-center justify-between rounded-[1rem] border px-4 py-3 text-left text-sm transition-colors",
                  enabled ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] text-foreground",
                )}
                onClick={enableClock}
              >
                <span>{enabled ? "番茄钟已开启" : "开启番茄钟"}</span>
                <span className={cn("h-6 w-11 rounded-full p-1 transition-colors", enabled ? "bg-emerald-500" : "bg-muted")}>
                  <span className={cn("block h-4 w-4 rounded-full bg-white transition-transform", enabled ? "translate-x-5" : "")} />
                </span>
              </button>
            </CardContent>
          </Card>

          <Card className="theme-card-main" data-guide-tour="pomodoro-plan-editor">
            <CardHeader className="theme-card-header">
              <CardTitle className="flex items-center gap-2">
                <CalendarClock className="h-5 w-5" />
                番茄计划
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 pt-4">
              <div className="grid gap-3 text-sm sm:grid-cols-2">
                <div className="rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3">
                  明早 9:00
                </div>
                <div className="rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3">
                  2 个番茄
                </div>
                <div className="rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3">
                  学习 25m
                </div>
                <div className="rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3">
                  休息 5m
                </div>
              </div>
              <Button type="button" variant={planCreated ? "outline" : "default"} onClick={createPlan}>
                <Plus className="h-4 w-4" />
                {planCreated ? "计划已设定" : "新建计划"}
              </Button>
            </CardContent>
          </Card>

          <Card className="theme-card-main" data-guide-tour="pomodoro-project-binding">
            <CardHeader className="theme-card-header">
              <CardTitle>绑定学习项目</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 pt-4">
              <div className="rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3 text-sm">
                计划 1：概率论与数理统计 · 网课材料
              </div>
              <Button type="button" variant={projectBound ? "outline" : "default"} onClick={bindProject}>
                <Play className="h-4 w-4" />
                {projectBound ? "项目已绑定" : "绑定到番茄计划"}
              </Button>
            </CardContent>
          </Card>

          <Card className="theme-card-main" data-guide-tour="pomodoro-web-entry-reminder">
            <CardHeader className="theme-card-header">
              <CardTitle className="flex items-center gap-2">
                <Laptop className="h-5 w-5" />
                番茄开始后
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 pt-4">
              <div className="rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3 text-sm leading-6 text-muted-foreground">
                到点前后保持网页登录并打开；学习时间开始后，从番茄钟进入绑定项目的工作台。
              </div>
              <Button type="button" variant={webReady ? "outline" : "default"} onClick={enterWeb}>
                <Laptop className="h-4 w-4" />
                {webReady ? "网页已就绪" : "登录网页进入工作台"}
              </Button>
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  )
}
