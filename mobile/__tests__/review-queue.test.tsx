import { fireEvent, render } from "@testing-library/react-native"

import type { RecallPoint } from "../src/api/review"
import { ReviewQueueScreen } from "../src/screens/ReviewQueueScreen"

const firstRecallPoint: RecallPoint = {
  projectId: "proj_1",
  recallPointId: "rp_1",
  createdAt: "2026-05-18T00:00:00Z",
  state: "ACTIVE",
  deletedAt: null,
  question: [{ kind: "TEXT", text: "第一题？" }],
  answer: [{ kind: "TEXT", text: "第一题答案" }],
  anchor: null,
  references: [],
  insights: [],
}

const secondRecallPoint: RecallPoint = {
  projectId: "proj_1",
  recallPointId: "rp_2",
  createdAt: "2026-05-18T00:00:00Z",
  state: "ACTIVE",
  deletedAt: null,
  question: [{ kind: "TEXT", text: "第二题？" }],
  answer: [{ kind: "TEXT", text: "第二题答案" }],
  anchor: null,
  references: [],
  insights: [],
}

describe("ReviewQueueScreen", () => {
  it("submits canRecall in range order for the queue head review task", () => {
    const submit = jest.fn()
    const screen = render(
      <ReviewQueueScreen
        committing={false}
        errorMessage={null}
        loading={false}
        onCommit={submit}
        recallPointIds={["rp_1", "rp_2"]}
        recallPoints={[secondRecallPoint, firstRecallPoint]}
        reviewTaskId="task_1"
        submitted={false}
      />,
    )

    fireEvent.press(screen.getByText("显示答案"))
    expect(screen.getByText("第一题答案")).toBeTruthy()
    fireEvent.press(screen.getByText("记得"))
    fireEvent.press(screen.getByText("显示答案"))
    expect(screen.getByText("第二题答案")).toBeTruthy()
    fireEvent.press(screen.getByText("不记得"))
    fireEvent.press(screen.getByText("提交复习"))

    expect(submit).toHaveBeenCalledWith({ reviewTaskId: "task_1", canRecall: [1, 0] })
  })

  it("does not expose submit when there is no queue head", () => {
    const submit = jest.fn()
    const screen = render(
      <ReviewQueueScreen
        committing={false}
        errorMessage={null}
        loading={false}
        onCommit={submit}
        recallPointIds={[]}
        recallPoints={[]}
        reviewTaskId={null}
        submitted={false}
      />,
    )

    expect(screen.getByText("暂无复习任务")).toBeTruthy()
    expect(screen.queryByText("提交复习")).toBeNull()
  })
})
