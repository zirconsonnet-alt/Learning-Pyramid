import { CheckCircle2, ListTree, PlayCircle, RotateCcw, Save } from "lucide-react"
import { useMemo, useState } from "react"

import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { completeGuideWalkthroughStep } from "@/ui/guideWalkthrough/guideWalkthroughController"
import { cn } from "@/ui/utils"

type DemoLearningObject = {
  id: string
  title: string
  chapter: string
}

type DemoReviewCard = {
  id: string
  prompt: string
  expected: string
}

const DEMO_VIDEO_URL = "/api/guide/demo-media/study-review"

const DEMO_OBJECTS: DemoLearningObject[] = [
  { id: "lesson-1", title: "01 向量与线性组合.mp4", chapter: "第 1 章 向量空间" },
  { id: "lesson-2", title: "02 基与维数.mp4", chapter: "第 1 章 向量空间" },
  { id: "lesson-3", title: "03 线性无关.mp4", chapter: "第 1 章 向量空间" },
]

const DEMO_REVIEW_CARDS: DemoReviewCard[] = [
  {
    id: "review-1",
    prompt: "线性组合的目标是什么？",
    expected: "用一组基向量和对应系数表示目标向量。",
  },
  {
    id: "review-2",
    prompt: "基和维数描述了什么？",
    expected: "基给出最小生成集合，维数表示基向量数量。",
  },
]

export function StudyReviewDemoWorkbenchPage() {
  const [selectedObjectId, setSelectedObjectId] = useState(DEMO_OBJECTS[0].id)
  const [recallQuestion, setRecallQuestion] = useState("线性组合的目标是什么？")
  const [recallAnswer, setRecallAnswer] = useState("用一组基向量和对应系数表示目标向量。")
  const [learningSubmitted, setLearningSubmitted] = useState(false)
  const [reviewIndex, setReviewIndex] = useState(0)
  const [reviewDraft, setReviewDraft] = useState("")
  const [memoryChoice, setMemoryChoice] = useState<"remembered" | "forgotten" | null>(null)
  const [reviewSubmitted, setReviewSubmitted] = useState(false)

  const selectedObject = useMemo(
    () => DEMO_OBJECTS.find((item) => item.id === selectedObjectId) ?? DEMO_OBJECTS[0],
    [selectedObjectId],
  )
  const currentReviewCard = DEMO_REVIEW_CARDS[Math.min(reviewIndex, DEMO_REVIEW_CARDS.length - 1)]

  function handleSelectObject(objectId: string) {
    setSelectedObjectId(objectId)
    completeGuideWalkthroughStep("select-learning-object")
  }

  function handleOpenRecallComposer() {
    completeGuideWalkthroughStep("add-recall-point")
  }

  function handleQuestionFocus() {
    completeGuideWalkthroughStep("fill-recall-question")
  }

  function handleAnswerFocus() {
    completeGuideWalkthroughStep("fill-recall-answer")
  }

  function handleSubmitLearning() {
    setLearningSubmitted(true)
    setReviewDraft("")
    setMemoryChoice(null)
    setReviewSubmitted(false)
    completeGuideWalkthroughStep("submit-learning")
  }

  function handleSubmitReviewAnswer() {
    completeGuideWalkthroughStep("submit-review-answer")
  }

  function handleChooseMemory(choice: "remembered" | "forgotten") {
    setMemoryChoice(choice)
    completeGuideWalkthroughStep("mark-review-result")
  }

  function handleSubmitReview() {
    setReviewSubmitted(true)
    completeGuideWalkthroughStep("submit-review")
  }

  function handleReplayDemo() {
    setLearningSubmitted(false)
    setReviewIndex(0)
    setReviewDraft("")
    setMemoryChoice(null)
    setReviewSubmitted(false)
  }

  return (
    <div className="space-y-5">
      <section className="theme-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="text-sm font-semibold text-foreground">学习复习引导演示工作台</div>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              这里是一次性的虚拟演示环境，只用于跟随引导体验录入复述点和做复习，不会进入你的学科或项目中心。
            </p>
          </div>
          <Button type="button" variant="outline" onClick={handleReplayDemo}>
            <RotateCcw className="h-4 w-4" />
            重新演示
          </Button>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1.2fr)_320px]">
        <aside className="xl:sticky xl:top-28 xl:self-start">
          <Card className="theme-card-main">
            <CardHeader className="theme-card-header">
              <div className="flex items-center gap-3">
                <div className="theme-icon-surface h-10 w-10">
                  <ListTree className="h-5 w-5" />
                </div>
                <div>
                  <CardTitle>内容目录</CardTitle>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3 pt-4">
              <div className="rounded-[1rem] border border-dashed border-border/70 bg-[color:var(--theme-soft-bg)] px-3 py-2 text-xs text-muted-foreground">
                服务端演示项目素材
              </div>
              <div className="space-y-2">
                {DEMO_OBJECTS.slice(0, 1).map((item) => {
                  const active = item.id === selectedObjectId
                  return (
                    <button
                      key={item.id}
                      type="button"
                      data-guide-tour="learning-object-tree-item"
                      className={cn(
                        "w-full rounded-[1rem] border px-3 py-3 text-left transition-colors",
                        active
                          ? "border-primary/20 bg-primary/10 shadow-[0_10px_22px_-20px_hsl(var(--primary)/0.28)]"
                          : "border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] hover:border-primary/15 hover:bg-accent/60",
                      )}
                      onClick={() => handleSelectObject(item.id)}
                    >
                      <div className="text-xs text-muted-foreground">{item.chapter}</div>
                      <div className="mt-1 text-sm font-medium text-foreground">{item.title}</div>
                    </button>
                  )
                })}
                {DEMO_OBJECTS.slice(1).map((item) => {
                  const active = item.id === selectedObjectId
                  return (
                    <button
                      key={item.id}
                      type="button"
                      className={cn(
                        "w-full rounded-[1rem] border px-3 py-3 text-left transition-colors",
                        active
                          ? "border-primary/20 bg-primary/10 shadow-[0_10px_22px_-20px_hsl(var(--primary)/0.28)]"
                          : "border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] hover:border-primary/15 hover:bg-accent/60",
                      )}
                      onClick={() => handleSelectObject(item.id)}
                    >
                      <div className="text-xs text-muted-foreground">{item.chapter}</div>
                      <div className="mt-1 text-sm font-medium text-foreground">{item.title}</div>
                    </button>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        </aside>

        <section className="space-y-4">
          <Card className="theme-card-main overflow-hidden">
            <CardContent className="p-0">
              <div className="border-b border-border/60 px-5 py-4">
                <div className="text-sm font-semibold text-foreground">{selectedObject.title}</div>
                <div className="mt-1 text-xs text-muted-foreground">服务端演示视频资源，仅用于本次引导</div>
              </div>
              <div className="bg-slate-950 p-4">
                <video
                  key={selectedObject.id}
                  controls
                  preload="metadata"
                  playsInline
                  src={DEMO_VIDEO_URL}
                  className="aspect-video w-full rounded-[1rem] bg-black"
                />
                <div className="mt-3 flex items-center gap-2 text-xs text-white/72">
                  <PlayCircle className="h-4 w-4" />
                  演示里的视频和复述流程都只存在于当前引导。
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="theme-card-main">
            <CardHeader className="theme-card-header">
              <div className="flex items-center justify-between gap-3">
                <CardTitle>复述点录入</CardTitle>
                <Button type="button" variant="outline" data-guide-tour="add-recall-point-button" onClick={handleOpenRecallComposer}>
                  添加复述点
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 pt-4">
              <div data-guide-tour="recall-question-editor" className="space-y-2">
                <label className="text-sm font-medium text-foreground">问题</label>
                <textarea
                  value={recallQuestion}
                  onFocus={handleQuestionFocus}
                  onChange={(event) => setRecallQuestion(event.target.value)}
                  className="min-h-[96px] w-full rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] px-4 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary/25"
                />
              </div>

              <div data-guide-tour="recall-answer-editor" className="space-y-2">
                <label className="text-sm font-medium text-foreground">答案</label>
                <textarea
                  value={recallAnswer}
                  onFocus={handleAnswerFocus}
                  onChange={(event) => setRecallAnswer(event.target.value)}
                  className="min-h-[132px] w-full rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] px-4 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary/25"
                />
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-sm text-muted-foreground">
                  {learningSubmitted ? "已保存到本次演示会话，不会写入任何真实项目。" : "这里模拟的是演示会话内的录入，不会生成真实复述点。"}
                </div>
                <Button type="button" data-guide-tour="submit-learning-button" onClick={handleSubmitLearning}>
                  <Save className="h-4 w-4" />
                  提交学习
                </Button>
              </div>
            </CardContent>
          </Card>
        </section>

        <aside className="xl:sticky xl:top-28 xl:self-start">
          <Card data-guide-tour="review-pane" className="theme-card-main">
            <CardHeader className="theme-card-header">
              <CardTitle>复习演示</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 pt-4">
              <div className="rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-4">
                <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">复习题面</div>
                <div className="mt-2 text-sm font-medium leading-6 text-foreground">{currentReviewCard.prompt}</div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">你的回忆答案</label>
                <textarea
                  value={reviewDraft}
                  onChange={(event) => setReviewDraft(event.target.value)}
                  className="min-h-[120px] w-full rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] px-4 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-primary/25"
                />
                <Button type="button" variant="outline" data-guide-tour="submit-review-answer-button" onClick={handleSubmitReviewAnswer}>
                  提交回忆答案
                </Button>
              </div>

              <div className="rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-4">
                <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">标准答案</div>
                <div className="mt-2 text-sm leading-6 text-foreground">{currentReviewCard.expected}</div>
              </div>

              <div data-guide-tour="review-memory-choice-buttons" className="flex flex-wrap gap-2">
                <Button type="button" variant={memoryChoice === "remembered" ? "default" : "outline"} onClick={() => handleChooseMemory("remembered")}>
                  记得
                </Button>
                <Button type="button" variant={memoryChoice === "forgotten" ? "default" : "outline"} onClick={() => handleChooseMemory("forgotten")}>
                  不记得
                </Button>
              </div>

              <Button type="button" className="w-full" data-guide-tour="submit-review-button" onClick={handleSubmitReview}>
                提交复习结果
              </Button>

              {reviewSubmitted ? (
                <div className="rounded-[1rem] border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
                  <div className="flex items-center gap-2 font-medium">
                    <CheckCircle2 className="h-4 w-4" />
                    本次演示复习已完成
                  </div>
                  <div className="mt-2 leading-6">
                    结果只停留在当前演示页，不会出现在你的项目中心，也不会影响真实复习队列。
                  </div>
                </div>
              ) : (
                <div className="text-sm leading-6 text-muted-foreground">
                  这里模拟的是演示复习闭环，帮助你理解真实工作台里的操作顺序。
                </div>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  )
}
