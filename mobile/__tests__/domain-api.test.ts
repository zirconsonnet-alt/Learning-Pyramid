import { createLearningPyramidApi, type ApiRequester } from "../src/api/types"

describe("mobile domain api", () => {
  it("uses public scoped project paths", async () => {
    const calls: string[] = []
    const requester: ApiRequester = {
      request: async <T,>({ path }: Parameters<ApiRequester["request"]>[0]) => {
        calls.push(path)
        return [] as T
      },
    }
    const api = createLearningPyramidApi(requester)

    await api.learningObjects.listNodes({ subjectId: "subj_1", scopedProjectId: "proj_1" })
    expect(calls[0]).toBe("/subjects/subj_1/projects/proj_1/learning-object-nodes")
  })
})
