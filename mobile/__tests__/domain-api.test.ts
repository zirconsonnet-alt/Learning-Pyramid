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
    await api.subjects.createSubject({ title: "数学" })
    await api.subjects.editSubject("subj_1", { title: "高等数学" })
    await api.subjects.deleteSubject("subj_1")
    await api.subjects.listMaterials("subj_1")
    await api.subjects.createMaterial("subj_1", { materialType: "BOOK", title: "线性代数" })
    await api.subjects.deleteMaterial("subj_1", "mat_1")
    await api.profile.getMyLlmSettings()
    await api.profile.updateMyLlmSettings({
      baseUrl: "https://llm.example.com/v1",
      modelName: "gpt-test",
      apiKey: "sk-test",
      promptAssemblyMode: "system",
    })
    await api.profile.getMyAsrSettings()
    await api.profile.updateMyAsrSettings({
      baseUrl: "https://asr.example.com/v1",
      modelName: "asr-test",
      clearApiKey: true,
    })
    await api.profile.getMyGlobalSettings()
    await api.system.getCapabilities()
    await api.system.askProjectLlm(scope, {
      prompt: "解释第一课",
      systemPrompt: "请使用简体中文回答。",
      learningObjectNodeId: "node_1",
    })
    await api.learningObjects.listNodes(scope)
    await api.learningObjects.getNode(scope, "node_1")
    await api.learningObjects.listRecallPointsByNode(scope, "node_1")
    await api.media.getPlayback(scope, "inst_1")
    await api.subtitles.getInstanceSubtitleFile(scope, "inst_1")
    await api.subtitles.uploadInstanceSubtitleFile(scope, "inst_1", {
      fileName: "lesson.srt",
      content: "1\n00:00:01,000 --> 00:00:02,000\n字幕\n",
    })
    await api.subtitles.deleteInstanceSubtitleFile(scope, "inst_1")
    await api.review.getQueue(scope)
    await api.review.getReviewTask(scope, "task_1")
    await api.review.getRangeSnapshot(scope, "range_1")
    await api.review.listRecallPoints(scope)
    await api.review.searchRecallPoints(scope, { q: "微分", limit: 12 })
    await api.review.listRecommendations(scope, { offset: 10, limit: 20 })
    await api.review.commitReviewTask(scope, "task_1", {
      canRecall: [0],
      appendedInsights: [{ recallPointId: "rp_1", insight: [{ kind: "TEXT", text: "补充理解" }] }],
    })
    await api.projectConfig.getProjectConfig(scope)
    await api.projectConfig.setLayerConfig(scope, 2, { thresholdRollUpEnabled: false })
    await api.learningTaskNodes.listNodes(scope)
    await api.learningTaskNodes.listRecallPointsByNode(scope, "task_node_1")
    await api.layers.listLayers(scope)
    await api.layers.getAggregationQueue(scope, 2)
    await api.layers.manualRollUp(scope, 2)
    await api.cloudAccounts.listBaiduNetdiskAccounts()
    await api.baiduNetdisk.listProjectFiles(scope, {
      accountId: "acct_1",
      dirPath: "/Course",
      page: 2,
      limit: 50,
    })
    await api.learningObjects.importFromBaiduNetdisk(scope, {
      accountId: "acct_1",
      items: [
        {
          fileId: "fs_1",
          path: "/Course/lesson.mp4",
          name: "lesson.mp4",
          isDir: false,
          sizeBytes: 1024,
          mimeType: "video/mp4",
          durationMs: 60000,
        },
      ],
    })
    await api.learningTasks.submitLearningTask(scope, {
      title: "第一课",
      items: [
        {
          question: [{ kind: "TEXT", text: "题面" }],
          answer: [{ kind: "TEXT", text: "答案" }],
          anchor: { instanceId: "inst_1", position: "t=12000" },
          references: [],
        },
      ],
    })

    expect(calls).toEqual([
      { path: "/auth/me", method: undefined, body: undefined },
      { path: "/auth/login", method: "POST", body: { email: "me@example.com", password: "secret" } },
      { path: "/auth/logout", method: "POST", body: undefined },
      { path: "/subjects", method: undefined, body: undefined },
      { path: "/subjects", method: "POST", body: { title: "数学" } },
      { path: "/subjects/subj_1", method: "PATCH", body: { title: "高等数学" } },
      { path: "/subjects/subj_1", method: "DELETE", body: undefined },
      { path: "/subjects/subj_1/materials", method: undefined, body: undefined },
      {
        path: "/subjects/subj_1/materials",
        method: "POST",
        body: { materialType: "BOOK", title: "线性代数" },
      },
      { path: "/subjects/subj_1/materials/mat_1", method: "DELETE", body: undefined },
      { path: "/profile/me/llm-settings", method: undefined, body: undefined },
      {
        path: "/profile/me/llm-settings",
        method: "PUT",
        body: {
          baseUrl: "https://llm.example.com/v1",
          modelName: "gpt-test",
          apiKey: "sk-test",
          promptAssemblyMode: "system",
        },
      },
      { path: "/profile/me/asr-settings", method: undefined, body: undefined },
      {
        path: "/profile/me/asr-settings",
        method: "PUT",
        body: {
          baseUrl: "https://asr.example.com/v1",
          modelName: "asr-test",
          clearApiKey: true,
        },
      },
      { path: "/profile/me/global-settings", method: undefined, body: undefined },
      { path: "/system/capabilities", method: undefined, body: undefined },
      {
        path: "/subjects/subj_1/projects/proj_1/llm/ask",
        method: "POST",
        body: {
          prompt: "解释第一课",
          systemPrompt: "请使用简体中文回答。",
          learningObjectNodeId: "node_1",
        },
      },
      { path: "/subjects/subj_1/projects/proj_1/learning-object-nodes", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/learning-objects/node_1", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/learning-objects/node_1/recall-points", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/media/instances/inst_1/playback", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/instances/inst_1/subtitle-file", method: undefined, body: undefined },
      {
        path: "/subjects/subj_1/projects/proj_1/instances/inst_1/subtitle-file",
        method: "POST",
        body: {
          fileName: "lesson.srt",
          content: "1\n00:00:01,000 --> 00:00:02,000\n字幕\n",
        },
      },
      { path: "/subjects/subj_1/projects/proj_1/instances/inst_1/subtitle-file", method: "DELETE", body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/queue", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/review-tasks/task_1", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/ranges/range_1", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/recall-points", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/recall-points/search?q=%E5%BE%AE%E5%88%86&limit=12", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/review-recommendations?offset=10&limit=20", method: undefined, body: undefined },
      {
        path: "/subjects/subj_1/projects/proj_1/review-tasks/task_1/commit",
        method: "POST",
        body: {
          canRecall: [0],
          appendedInsights: [{ recallPointId: "rp_1", insight: [{ kind: "TEXT", text: "补充理解" }] }],
        },
      },
      { path: "/subjects/subj_1/projects/proj_1/project-config", method: undefined, body: undefined },
      {
        path: "/subjects/subj_1/projects/proj_1/layers/2/config",
        method: "POST",
        body: { thresholdRollUpEnabled: false },
      },
      { path: "/subjects/subj_1/projects/proj_1/learning-task-nodes", method: undefined, body: undefined },
      {
        path: "/subjects/subj_1/projects/proj_1/learning-task-nodes/task_node_1/recall-points",
        method: undefined,
        body: undefined,
      },
      { path: "/subjects/subj_1/projects/proj_1/layers", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/aggregation-queue/2", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/layers/2/roll-up", method: "POST", body: {} },
      { path: "/profile/me/cloud-accounts/baidu-netdisk", method: undefined, body: undefined },
      {
        path: "/subjects/subj_1/projects/proj_1/baidu-netdisk/files?accountId=acct_1&dirPath=%2FCourse&page=2&limit=50",
        method: undefined,
        body: undefined,
      },
      {
        path: "/subjects/subj_1/projects/proj_1/import-learning-objects-from-baidu-netdisk",
        method: "POST",
        body: {
          accountId: "acct_1",
          items: [
            {
              fileId: "fs_1",
              path: "/Course/lesson.mp4",
              name: "lesson.mp4",
              isDir: false,
              sizeBytes: 1024,
              mimeType: "video/mp4",
              durationMs: 60000,
            },
          ],
        },
      },
      {
        path: "/subjects/subj_1/projects/proj_1/learning-tasks",
        method: "POST",
        body: {
          title: "第一课",
          items: [
            {
              question: [{ kind: "TEXT", text: "题面" }],
              answer: [{ kind: "TEXT", text: "答案" }],
              anchor: { instanceId: "inst_1", position: "t=12000" },
              references: [],
            },
          ],
        },
      },
    ])
  })
})
