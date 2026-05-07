import type { ReactNode } from "react"

import { ProjectDirectoryGuideDemo } from "./ProjectDirectoryGuideDemo"
import { SubjectProjectGuideDemo } from "./SubjectProjectGuideDemo"
import { WorkbenchRecallGuideDemo } from "./WorkbenchRecallGuideDemo"

export type GuideDemoRequest = {
  scene: string
  state: string
  highlight?: string
  title?: string
  caption?: string
  invalidReason?: string
}

export type GuideSceneState = {
  state: string
  label: string
  stateDescription: string
}

export type GuideSceneDefinition = {
  scene: string
  label: string
  description: string
  states: GuideSceneState[]
  highlights: string[]
  render: (request: { state: string; highlight?: string }) => ReactNode
}

export type GuideSceneResolution =
  | {
      status: "ready"
      title: string
      caption?: string
      stateLabel: string
      stateDescription: string
      content: ReactNode
      maintainerHint?: string
    }
  | {
      status: "fallback"
      reason: "invalid-directive" | "unknown-scene" | "unsupported-state"
      title: string
      caption?: string
      stateLabel?: string
      stateDescription?: string
      maintainerHint: string
    }
  | {
      status: "degraded"
      reason: "unsupported-highlight"
      title: string
      caption?: string
      stateLabel: string
      stateDescription: string
      content: ReactNode
      maintainerHint: string
    }

export const guideSceneRegistry: GuideSceneDefinition[] = [
  {
    scene: "subject-project",
    label: "创建学科和项目",
    description: "展示首次进入系统后创建学科、进入学科总面板并选择项目的路径。",
    states: [
      {
        state: "create-subject",
        label: "创建学科",
        stateDescription: "强调新建学科按钮和创建后需要继续进入项目设置的提示。",
      },
      {
        state: "project-choice",
        label: "选择项目",
        stateDescription: "展示学科总面板中的项目卡片，帮助读者找到下一步入口。",
      },
    ],
    highlights: ["new-subject-button", "default-project-card"],
    render: ({ state, highlight }) => <SubjectProjectGuideDemo state={state as "create-subject" | "project-choice"} highlight={highlight} />,
  },
  {
    scene: "project-directory",
    label: "绑定本地素材目录",
    description: "展示项目设置里的本地素材目录授权和同步目录内容操作。",
    states: [
      {
        state: "unbound",
        label: "尚未授权目录",
        stateDescription: "读者应找到本地素材目录卡片，并点击选择并授权目录。",
      },
      {
        state: "imported",
        label: "目录已同步",
        stateDescription: "展示目录授权后同步目录内容的完成状态。",
      },
    ],
    highlights: ["authorize-button", "import-button"],
    render: ({ state, highlight }) => <ProjectDirectoryGuideDemo state={state as "unbound" | "imported"} highlight={highlight} />,
  },
  {
    scene: "workbench-recall",
    label: "工作台录入复述点",
    description: "展示从学习对象树选择视频、暂停播放并填写复述点的核心学习闭环。",
    states: [
      {
        state: "editing-recall",
        label: "填写复述点",
        stateDescription: "读者可以核对学习对象、视频锚点、问题答案和提交学习入口。",
      },
    ],
    highlights: ["object-tree", "recall-form"],
    render: ({ highlight }) => <WorkbenchRecallGuideDemo state="editing-recall" highlight={highlight} />,
  },
]

export function validateGuideSceneReference(request: GuideDemoRequest) {
  const scene = guideSceneRegistry.find((entry) => entry.scene === request.scene)
  if (!scene) return { ok: false as const, reason: "unknown-scene" as const }
  const state = scene.states.find((entry) => entry.state === request.state)
  if (!state) return { ok: false as const, reason: "unsupported-state" as const, scene }
  if (request.highlight && !scene.highlights.includes(request.highlight)) {
    return { ok: true as const, reason: "unsupported-highlight" as const, scene, state }
  }
  return { ok: true as const, scene, state }
}

export function resolveGuideScene(request: GuideDemoRequest): GuideSceneResolution {
  if (request.invalidReason) {
    return {
      status: "fallback",
      reason: "invalid-directive",
      title: request.title || "指南场景配置不完整",
      caption: request.caption,
      maintainerHint: request.invalidReason,
    }
  }

  const validation = validateGuideSceneReference(request)
  if (!validation.ok) {
    return {
      status: "fallback",
      reason: validation.reason,
      title: request.title || "指南场景暂时不可用",
      caption: request.caption,
      maintainerHint: `scene="${request.scene}" state="${request.state}"`,
    }
  }

  const title = request.title || validation.scene.label
  if (validation.reason === "unsupported-highlight") {
    return {
      status: "degraded",
      reason: "unsupported-highlight",
      title,
      caption: request.caption,
      stateLabel: validation.state.label,
      stateDescription: validation.state.stateDescription,
      content: validation.scene.render({ state: request.state }),
      maintainerHint: `highlight="${request.highlight}" is not registered for scene="${request.scene}"`,
    }
  }

  return {
    status: "ready",
    title,
    caption: request.caption,
    stateLabel: validation.state.label,
    stateDescription: validation.state.stateDescription,
    content: validation.scene.render({ state: request.state, highlight: request.highlight }),
  }
}
