import {
  buildSubmitLearningTaskItems,
  createRecallDraft,
  getIncompleteDraftReason,
  recallDraftTextToRichContent,
} from "../src/workbench/recallDrafts"

describe("mobile workbench recall drafts", () => {
  it("creates a draft anchored to the current playback time", () => {
    const draft = createRecallDraft({
      instanceId: "inst_1",
      currentMs: 12750,
      localId: "draft_1",
      now: 1710000000000,
    })

    expect(draft).toEqual({
      localId: "draft_1",
      instanceId: "inst_1",
      position: "t=12750",
      questionText: "",
      answerText: "",
      createdAt: 1710000000000,
      updatedAt: 1710000000000,
    })
  })

  it("builds learning task items from complete text drafts", () => {
    const draft = {
      localId: "draft_1",
      instanceId: "inst_1",
      position: "t=12000",
      questionText: "问题",
      answerText: "答案",
      createdAt: 1710000000000,
      updatedAt: 1710000001000,
    }

    expect(getIncompleteDraftReason(draft)).toBeNull()
    expect(buildSubmitLearningTaskItems([draft])).toEqual([
      {
        question: [{ kind: "TEXT", text: "问题" }],
        answer: [{ kind: "TEXT", text: "答案" }],
        anchor: { instanceId: "inst_1", position: "t=12000" },
        references: [],
      },
    ])
  })

  it("rejects incomplete drafts before submit payload creation", () => {
    const draft = createRecallDraft({
      instanceId: "inst_1",
      currentMs: 0,
      localId: "draft_1",
      now: 1710000000000,
    })

    expect(getIncompleteDraftReason(draft)).toBe("题面不能为空")
    expect(() => buildSubmitLearningTaskItems([draft])).toThrow("题面不能为空")
  })

  it("trims text before creating rich content", () => {
    expect(recallDraftTextToRichContent("  题面  ")).toEqual([{ kind: "TEXT", text: "题面" }])
  })
})
