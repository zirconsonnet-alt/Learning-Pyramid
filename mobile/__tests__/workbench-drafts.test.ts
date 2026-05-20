import {
  buildSubmitLearningTaskItems,
  createRecallDraft,
  formatCourseAnchorPositionForInput,
  getIncompleteDraftReason,
  normalizeAnchorPositionForSubmit,
  setDraftRichText,
} from "../src/workbench/recallDrafts"

describe("mobile workbench recall drafts", () => {
  it("creates a course draft with rich content fields and a playback anchor", () => {
    const draft = createRecallDraft({
      projectType: "COURSE",
      instanceId: "inst_1",
      currentMs: 12750,
      localId: "draft_1",
      now: 1710000000000,
    })

    expect(draft).toEqual({
      localId: "draft_1",
      instanceId: "inst_1",
      position: "t=12750",
      question: [],
      answer: [],
      references: [],
      createdAt: 1710000000000,
      updatedAt: 1710000000000,
    })
  })

  it("normalizes editable course anchors before submit", () => {
    expect(formatCourseAnchorPositionForInput("t=1077000")).toBe("17:57")
    expect(normalizeAnchorPositionForSubmit("17:57", "COURSE")).toBe("t=1077000")
    expect(normalizeAnchorPositionForSubmit("1:02:03", "COURSE")).toBe("t=3723000")
    expect(normalizeAnchorPositionForSubmit("t=12000", "COURSE")).toBe("t=12000")
  })

  it("uses text anchors for book projects and no anchor for loose points", () => {
    const bookDraft = createRecallDraft({
      projectType: "BOOK",
      instanceId: "inst_book",
      currentMs: 0,
      localId: "book_1",
      now: 1710000000000,
    })
    const looseDraft = createRecallDraft({
      projectType: "LOOSE_POINTS",
      instanceId: null,
      currentMs: 0,
      localId: "loose_1",
      now: 1710000000000,
    })

    expect(bookDraft.position).toBe("")
    expect(looseDraft.position).toBeNull()
  })

  it("builds learning task items from complete rich drafts with references", () => {
    const draft = {
      localId: "draft_1",
      instanceId: "inst_1",
      position: "17:57",
      question: [{ kind: "TEXT" as const, text: "问题" }],
      answer: [{ kind: "TEXT" as const, text: "答案" }],
      references: ["rp_1"],
      createdAt: 1710000000000,
      updatedAt: 1710000001000,
    }

    expect(getIncompleteDraftReason(draft, "COURSE")).toBeNull()
    expect(buildSubmitLearningTaskItems([draft], "COURSE")).toEqual([
      {
        question: [{ kind: "TEXT", text: "问题" }],
        answer: [{ kind: "TEXT", text: "答案" }],
        anchor: { instanceId: "inst_1", position: "t=1077000" },
        references: ["rp_1"],
      },
    ])
  })

  it("rejects incomplete drafts before submit payload creation", () => {
    const draft = createRecallDraft({
      projectType: "COURSE",
      instanceId: "inst_1",
      currentMs: 0,
      localId: "draft_1",
      now: 1710000000000,
    })

    expect(getIncompleteDraftReason(draft, "COURSE")).toBe("题面不能为空")
    expect(() => buildSubmitLearningTaskItems([draft], "COURSE")).toThrow("题面不能为空")
  })

  it("updates draft rich text without changing images or references", () => {
    const draft = {
      localId: "draft_1",
      instanceId: "inst_1",
      position: "t=0",
      question: [
        { kind: "TEXT" as const, text: "旧题" },
        { kind: "IMAGE" as const, assetId: "asset_1" },
      ],
      answer: [{ kind: "TEXT" as const, text: "答案" }],
      references: ["rp_1"],
      createdAt: 1710000000000,
      updatedAt: 1710000001000,
    }

    expect(setDraftRichText(draft, "question", "新题")).toEqual({
      ...draft,
      question: [
        { kind: "TEXT", text: "新题" },
        { kind: "IMAGE", assetId: "asset_1" },
      ],
    })
  })
})
