import { fireEvent, render } from "@testing-library/react-native"
import { Text } from "react-native"
import { SafeAreaView } from "react-native-safe-area-context"

import {
  PROJECT_SHELL_DESTINATIONS,
  buildContextMenuItems,
  getLearningContextStatus,
  getRouteGuardTarget,
  getVisibleScopedSettings,
} from "../src/navigation/mobileNavigation"
import { SubjectMaterialsScreen } from "../src/screens/SubjectMaterialsScreen"
import { SubjectsScreen } from "../src/screens/SubjectsScreen"
import { ContextMenu } from "../src/navigation/ContextMenu"
import { ProjectShell } from "../src/navigation/ProjectShell"

describe("mobile navigation domain", () => {
  it("classifies learning context states without a hidden current project", () => {
    expect(getLearningContextStatus({})).toBe("no-subject")
    expect(getLearningContextStatus({ subjectId: "subj_1" })).toBe("subject-only")
    expect(getLearningContextStatus({ subjectId: "subj_1", scopedProjectId: "proj_1" })).toBe("project")
    expect(getLearningContextStatus({ subjectId: "subj_1", invalid: true })).toBe("invalid")
  })

  it("keeps the project shell destination set stable and capped at five", () => {
    expect(PROJECT_SHELL_DESTINATIONS.map((item) => item.id)).toEqual([
      "learning",
      "ai",
      "review",
      "structure",
      "mine",
    ])
    expect(PROJECT_SHELL_DESTINATIONS).toHaveLength(5)
    expect(PROJECT_SHELL_DESTINATIONS.every((item) => item.requiredScope === "project" || item.id === "mine")).toBe(true)
  })

  it("derives scoped settings visibility from concrete context", () => {
    expect(getVisibleScopedSettings({})).toEqual({ projectSettings: false, subjectSettings: false })
    expect(getVisibleScopedSettings({ subjectId: "subj_1" })).toEqual({
      projectSettings: false,
      subjectSettings: true,
    })
    expect(getVisibleScopedSettings({ subjectId: "subj_1", scopedProjectId: "proj_1" })).toEqual({
      projectSettings: true,
      subjectSettings: true,
    })
  })

  it("guides missing project routes to the minimum missing context", () => {
    expect(getRouteGuardTarget("project", {})).toEqual({ pathname: "/" })
    expect(getRouteGuardTarget("project", { subjectId: "subj_1" })).toEqual({
      params: { subjectId: "subj_1" },
      pathname: "/subject/[subjectId]",
    })
    expect(getRouteGuardTarget("project", { subjectId: "subj_1", scopedProjectId: "proj_1" })).toBeNull()
  })

  it("builds context menu items without offering object settings for missing objects", () => {
    expect(buildContextMenuItems({}).map((item) => item.id)).toEqual(["select-subject"])
    expect(buildContextMenuItems({ subjectId: "subj_1" }).map((item) => item.id)).toEqual([
      "switch-subject",
      "subject-settings",
      "select-project",
      "subject-center",
    ])
    expect(buildContextMenuItems({ subjectId: "subj_1", scopedProjectId: "proj_1" }).map((item) => item.id)).toEqual([
      "switch-subject",
      "subject-settings",
      "switch-project",
      "project-settings",
      "subject-center",
      "project-center",
    ])
  })
})

describe("mobile setup states", () => {
  it("shows a start-learning subject setup state without project shell destinations", () => {
    const screen = render(
      <SubjectsScreen
        createSubject={() => undefined}
        deleteSubject={() => undefined}
        loading={false}
        openGlobalSettings={() => undefined}
        openSubject={() => undefined}
        openSubjectSettings={() => undefined}
        signOut={() => undefined}
        subjects={[]}
      />,
    )

    expect(screen.getByText("开始学习")).toBeTruthy()
    expect(screen.getByText("新建学科")).toBeTruthy()
    expect(screen.queryByText("AI")).toBeNull()
    expect(screen.queryByText("复习")).toBeNull()
    expect(screen.queryByText("结构")).toBeNull()
  })

  it("shows a project setup state for subject-only users without project shell destinations", () => {
    const screen = render(
      <SubjectMaterialsScreen
        createMaterial={() => undefined}
        deleteMaterial={() => undefined}
        loading={false}
        materials={[]}
        openMaterial={() => undefined}
      />,
    )

    expect(screen.getByText("项目中心")).toBeTruthy()
    expect(screen.getByText("暂无项目")).toBeTruthy()
    expect(screen.getByText("新建项目")).toBeTruthy()
    expect(screen.queryByText("AI")).toBeNull()
    expect(screen.queryByText("复习")).toBeNull()
    expect(screen.queryByText("结构")).toBeNull()
  })
})

describe("project shell", () => {
  const destinationRenderers = {
    renderAi: () => <Text>AI问答内容</Text>,
    renderReview: () => <Text>复习推荐内容</Text>,
    renderStructure: () => <Text>结构视图内容</Text>,
  }

  it("renders current context and exactly five project destinations", () => {
    const screen = render(
      <ProjectShell
        context={{
          projectTitle: "网课材料",
          scopedProjectId: "proj_1",
          subjectId: "subj_1",
          subjectTitle: "高等数学",
        }}
        openGlobalSettings={() => undefined}
        {...destinationRenderers}
        renderLearning={() => <Text>学习内容</Text>}
        signOut={() => undefined}
      />,
    )

    expect(screen.getByText("高等数学 · 网课材料")).toBeTruthy()
    expect(screen.getByText("学习内容")).toBeTruthy()
    expect(screen.queryByText("‹")).toBeNull()
    expect(PROJECT_SHELL_DESTINATIONS.map((destination) => screen.getByText(destination.label))).toHaveLength(5)
    expect(screen.queryByText("切换学科")).toBeNull()
    expect(screen.queryByText("学科中心")).toBeNull()
  })

  it("keeps the custom project chrome inside the device safe area", () => {
    const screen = render(
      <ProjectShell
        context={{
          projectTitle: "网课材料",
          scopedProjectId: "proj_1",
          subjectId: "subj_1",
          subjectTitle: "高等数学",
        }}
        openGlobalSettings={() => undefined}
        {...destinationRenderers}
        renderLearning={() => <Text>学习内容</Text>}
        signOut={() => undefined}
      />,
    )

    expect(screen.UNSAFE_getByType(SafeAreaView)).toBeTruthy()
  })

  it("keeps scoped management actions inside the context sheet", () => {
    const screen = render(
      <ProjectShell
        context={{
          projectTitle: "网课材料",
          scopedProjectId: "proj_1",
          subjectId: "subj_1",
          subjectTitle: "高等数学",
        }}
        openGlobalSettings={() => undefined}
        {...destinationRenderers}
        renderLearning={() => <Text>学习内容</Text>}
        signOut={() => undefined}
      />,
    )

    expect(screen.queryByText("切换学科")).toBeNull()
    fireEvent.press(screen.getByText("高等数学 · 网课材料"))
    expect(screen.getByText("当前上下文")).toBeTruthy()
    expect(screen.getByText("切换学科")).toBeTruthy()
    expect(screen.getByText("学科设置")).toBeTruthy()
    expect(screen.getByText("切换项目")).toBeTruthy()
    expect(screen.getByText("项目设置")).toBeTruthy()
    expect(screen.getByText("学科中心")).toBeTruthy()
    expect(screen.getByText("项目中心")).toBeTruthy()
  })

  it("keeps project context when switching to project-scoped destinations", () => {
    const screen = render(
      <ProjectShell
        context={{
          projectTitle: "网课材料",
          scopedProjectId: "proj_1",
          subjectId: "subj_1",
          subjectTitle: "高等数学",
        }}
        openGlobalSettings={() => undefined}
        {...destinationRenderers}
        renderLearning={() => <Text>学习内容</Text>}
        signOut={() => undefined}
      />,
    )

    expect(screen.getByText("学习内容")).toBeTruthy()
    fireEvent.press(screen.getByText("AI"))
    expect(screen.getAllByText("AI").length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("高等数学 · 网课材料")).toBeTruthy()
    expect(screen.getByText("AI问答内容")).toBeTruthy()
    expect(screen.queryByText("当前项目暂未开放 AI。")).toBeNull()

    fireEvent.press(screen.getByText("复习"))
    expect(screen.getByText("复习推荐内容")).toBeTruthy()
    expect(screen.queryByText("当前项目暂无独立复习入口。")).toBeNull()

    fireEvent.press(screen.getByText("结构"))
    expect(screen.getByText("结构视图内容")).toBeTruthy()
    expect(screen.queryByText("当前项目结构请先在学习页查看。")).toBeNull()
  })

  it("renders Mine as the fifth project destination without scoped settings", () => {
    const screen = render(
      <ProjectShell
        context={{
          projectTitle: "网课材料",
          scopedProjectId: "proj_1",
          subjectId: "subj_1",
          subjectTitle: "高等数学",
        }}
        openGlobalSettings={() => undefined}
        {...destinationRenderers}
        renderLearning={() => <Text>学习内容</Text>}
        signOut={() => undefined}
      />,
    )

    fireEvent.press(screen.getByText("我的"))
    expect(screen.getByText("个人中心")).toBeTruthy()
    expect(screen.getByText("全局设置")).toBeTruthy()
  })
})

describe("scoped context controls", () => {
  it("shows only valid scoped settings for each context state", () => {
    const noSubject = render(<ContextMenu context={{}} onDismiss={() => undefined} visible />)
    expect(noSubject.getByText("选择学科")).toBeTruthy()
    expect(noSubject.queryByText("学科设置")).toBeNull()
    expect(noSubject.queryByText("项目设置")).toBeNull()

    const subjectOnly = render(<ContextMenu context={{ subjectId: "subj_1", subjectTitle: "高等数学" }} onDismiss={() => undefined} visible />)
    expect(subjectOnly.getByText("学科设置")).toBeTruthy()
    expect(subjectOnly.getByText("选择项目")).toBeTruthy()
    expect(subjectOnly.queryByText("项目设置")).toBeNull()

    const project = render(
      <ContextMenu
        context={{
          projectTitle: "网课材料",
          scopedProjectId: "proj_1",
          subjectId: "subj_1",
          subjectTitle: "高等数学",
        }}
        onDismiss={() => undefined}
        visible
      />,
    )
    expect(project.getByText("学科设置")).toBeTruthy()
    expect(project.getByText("项目设置")).toBeTruthy()
    expect(project.getByText("项目中心")).toBeTruthy()
  })
})
