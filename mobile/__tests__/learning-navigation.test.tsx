import { render } from "@testing-library/react-native"

import { ProjectScreen } from "../src/screens/ProjectScreen"
import { SubjectMaterialsScreen } from "../src/screens/SubjectMaterialsScreen"

describe("ProjectScreen", () => {
  it("renders learning object titles", () => {
    const screen = render(
      <ProjectScreen
        loading={false}
        nodes={[
          { kind: "container", projectId: "p1", nodeId: "root", parentId: null, children: ["leaf"], title: "课程" },
          { kind: "leaf", projectId: "p1", nodeId: "leaf", parentId: "root", instanceId: "i1", title: "第一课" },
        ]}
        openNode={() => undefined}
      />,
    )

    expect(screen.getByText("课程")).toBeTruthy()
    expect(screen.getByText("第一课")).toBeTruthy()
  })

  it("renders a load error instead of an empty list", () => {
    const screen = render(<ProjectScreen errorMessage="加载失败" loading={false} nodes={[]} openNode={() => undefined} />)

    expect(screen.getByText("加载失败")).toBeTruthy()
  })

  it("keeps subject-only users in project setup instead of showing project shell tabs", () => {
    const screen = render(
      <SubjectMaterialsScreen
        createMaterial={() => undefined}
        deleteMaterial={() => undefined}
        loading={false}
        materials={[]}
        openMaterial={() => undefined}
      />,
    )

    expect(screen.getByText("暂无项目")).toBeTruthy()
    expect(screen.getByText("新建项目")).toBeTruthy()
    expect(screen.queryByText("学习")).toBeNull()
    expect(screen.queryByText("AI")).toBeNull()
    expect(screen.queryByText("我的")).toBeNull()
  })

  it("keeps subject settings available from subject center rows", () => {
    const screen = render(
      <SubjectMaterialsScreen
        createMaterial={() => undefined}
        deleteMaterial={() => undefined}
        loading={false}
        materials={[
          {
            createdAt: "2026-05-18T00:00:00Z",
            materialId: "mat_1",
            materialType: "COURSE",
            scopedProjectId: "proj_1",
            subjectId: "subj_1",
            title: "网课材料",
          },
        ]}
        openMaterial={() => undefined}
        openSubjectSettings={() => undefined}
      />,
    )

    expect(screen.getByText("学科设置")).toBeTruthy()
  })
})
