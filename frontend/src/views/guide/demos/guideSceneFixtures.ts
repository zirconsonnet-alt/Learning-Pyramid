export const GUIDE_SCENE_FIXTURES = {
  subjectProject: {
    subjectTitle: "机器学习入门",
    projectTitle: "线性代数视频课",
    projectType: "网课项目",
    setupNotice: "创建后请到项目设置中绑定本地素材目录，并手动同步目录内容。",
  },
  projectDirectory: {
    projectTitle: "线性代数视频课",
    sampleDirectoryLabel: "示例课程素材",
    permissionState: "未授权",
    importedCount: 8,
    sampleTree: ["第 1 章 向量空间", "01 向量与线性组合.mp4", "02 基与维数.mp4"],
  },
  workbenchRecall: {
    projectTitle: "线性代数视频课",
    selectedObject: "01 向量与线性组合.mp4",
    currentTime: "17:57",
    recallQuestion: "线性组合的目标是什么？",
    recallAnswer: "用一组基向量和对应系数表示目标向量。",
    taskTitle: "线性组合第一轮复述",
  },
} as const
