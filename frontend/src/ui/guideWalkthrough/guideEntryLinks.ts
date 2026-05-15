export type GuideEntryLink = {
  index: string
  title: string
  body: string
  label: string
  to: string
  access: "free" | "member"
}

export const guideEntryLinks: GuideEntryLink[] = [
  {
    index: "1",
    title: "创建学科项目",
    body: "从新建学科、进入项目，到绑定并导入本地学习材料。",
    label: "去管理专业课的学习",
    to: "/subjects?walkthrough=create-subject-project",
    access: "free",
  },
  {
    index: "2",
    title: "学习复习",
    body: "进入工作台后，录入复述点、提交学习并完成复习闭环。",
    label: "去体验自动复习推送",
    to: "/subjects?walkthrough=study-review",
    access: "free",
  },
  {
    index: "3",
    title: "使用 AI 问答",
    body: "会员和 LLM 可用后，进入项目 AI 问答，选择学习对象并开始对话。",
    label: "去感受AI学习赋能",
    to: "/subjects?walkthrough=use-ai-chat",
    access: "member",
  },
  {
    index: "4",
    title: "使用番茄钟",
    body: "开启番茄钟，设定明早 9 点计划，绑定项目，然后查看计划。",
    label: "去定明早9点的番茄钟",
    to: "/pomodoro?walkthrough=use-pomodoro",
    access: "member",
  },
] as const
