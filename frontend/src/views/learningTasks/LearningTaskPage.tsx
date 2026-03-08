import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { useLearningTask } from "@/ui/queries/learningTasks"
import { formatLearningTaskNodeDisplayTitle } from "@/views/learningTasks/displayTitle"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

export function LearningTaskPage() {
  const { projectId, learningTaskId } = useParams()
  const navigate = useNavigate()
  const pid = projectId ?? ""
  const taskId = learningTaskId ?? ""
  const taskQ = useLearningTask(pid, taskId)

  if (!pid || !taskId) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">缺少 projectId 或 learningTaskId。</p>
        <Button onClick={() => navigate("/projects")}>返回项目列表</Button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">{taskQ.data?.title ?? "学习任务"}</h1>
          <p className="text-sm text-muted-foreground">查看任务内容、复述点数量，以及对应复习链。</p>
        </div>
        <Button variant="outline" asChild>
          <Link to={`/p/${pid}/task-tree`}>返回学习任务树</Link>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>任务概览</CardTitle>
          <CardDescription>工作台按这个任务组织复习链和后续调度。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {taskQ.isLoading ? <p className="text-sm text-muted-foreground">加载中...</p> : null}
          {taskQ.error ? <p className="text-sm text-destructive">{formatApiError(taskQ.error)}</p> : null}

          {taskQ.data ? (
            <>
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">任务标题</div>
                  <div className="mt-1 font-medium text-foreground">{taskQ.data.title}</div>
                </div>
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">复述点数量</div>
                  <div className="mt-1 font-medium text-foreground">{taskQ.data.size}</div>
                </div>
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">所在层</div>
                  <div className="mt-1 font-medium text-foreground">
                    {taskQ.data.targetLayerIndex === null ? "-" : `L${taskQ.data.targetLayerIndex}`}
                  </div>
                </div>
              </div>

              <div className="rounded-md border p-4">
                <div className="text-xs text-muted-foreground">入口标题</div>
                <div className="mt-1 text-sm font-medium text-foreground">
                  {taskQ.data.entryNodeTitle
                    ? formatLearningTaskNodeDisplayTitle(taskQ.data.entryNodeTitle, {
                        sourceLayerIndex:
                          taskQ.data.targetLayerIndex === null ? undefined : Math.max(0, taskQ.data.targetLayerIndex - 1),
                      })
                    : "-"}
                </div>
              </div>

              <div className="flex flex-wrap gap-3">
                {taskQ.data.entryNodeId ? (
                  <Button variant="outline" asChild>
                    <Link to={`/p/${pid}/learning-task-nodes/${taskQ.data.entryNodeId}`}>查看入口节点</Link>
                  </Button>
                ) : null}
                {taskQ.data.reviewChainId ? (
                  <Button asChild>
                    <Link to={`/p/${pid}/review-chains/${taskQ.data.reviewChainId}`}>查看复习链</Link>
                  </Button>
                ) : null}
              </div>
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
