import { createLearningPyramidApi, type ApiRequester } from "../src/api/types"

describe("mobile domain api", () => {
  it("uses public scoped project paths", async () => {
    const calls: Array<{ path: string; method?: string; body?: unknown }> = []
    const requester: ApiRequester = {
      request: async <T,>({ path, method, body }: Parameters<ApiRequester["request"]>[0]) => {
        calls.push({ path, method, body })
        return [] as T
      },
    }
    const api = createLearningPyramidApi(requester)
    const scope = { subjectId: "subj_1", scopedProjectId: "proj_1" }

    await api.auth.me()
    await api.auth.login({ email: "me@example.com", password: "secret" })
    await api.auth.logout()
    await api.subjects.listSubjects()
    await api.subjects.listMaterials("subj_1")
    await api.learningObjects.listNodes(scope)
    await api.learningObjects.getNode(scope, "node_1")
    await api.learningObjects.listRecallPointsByNode(scope, "node_1")
    await api.media.getPlayback(scope, "inst_1")
    await api.review.getQueue(scope)
    await api.review.getReviewTask(scope, "task_1")
    await api.review.getRangeSnapshot(scope, "range_1")
    await api.review.listRecallPoints(scope)
    await api.review.listRecommendations(scope, { offset: 10, limit: 20 })
    await api.review.commitReviewTask(scope, "task_1", { canRecall: [0] })

    expect(calls).toEqual([
      { path: "/auth/me", method: undefined, body: undefined },
      { path: "/auth/login", method: "POST", body: { email: "me@example.com", password: "secret" } },
      { path: "/auth/logout", method: "POST", body: undefined },
      { path: "/subjects", method: undefined, body: undefined },
      { path: "/subjects/subj_1/materials", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/learning-object-nodes", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/learning-objects/node_1", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/learning-objects/node_1/recall-points", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/media/instances/inst_1/playback", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/queue", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/review-tasks/task_1", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/ranges/range_1", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/recall-points", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/review-recommendations?offset=10&limit=20", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/review-tasks/task_1/commit", method: "POST", body: { canRecall: [0] } },
    ])
  })
})
